"""Native continuation of an explicitly recorded, prepared solver handover.

The original model exchanges and completed card-building returns are replayed;
the normal solver then resumes its own numerical checkpoints in the same run.
The workspace must match the selected boundary. Only its deterministic solver
checkpoints may advance beyond that boundary.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import time

from ..general_db_query_engine.general_first_principle_API_call_reconstruct import (
    ReconstructionMismatch, current_session,
)
from ..general_db_query_engine.general_first_principle_API_call_reconstruct.paths import filesystem_path, display_path


def _json(path):
    return json.loads(filesystem_path(path).read_text(encoding="utf-8"))


def _sha(path):
    with filesystem_path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _relative(path, root):
    # Long-path prefixes are a filesystem representation, not a different root.
    return display_path(path).relative_to(display_path(root))


def inspect_handover(source, destination, settings):
    """Read-only validation; no model, solver, source rewrite or fallback."""
    source, destination = Path(source), Path(destination).absolute()
    launch = _json(source / "analysis_run.json")
    if launch.get("settings") != settings:
        raise ReconstructionMismatch("Continuation question/settings differ from the saved run")
    marker = _json(source / "planned_stage_boundary.json")
    if (marker.get("schema") != "srd46-planned-solver-handover/v1"
            or marker.get("status") != "parked_before_solver"
            or marker.get("operation") != "planned.before_first_solver"):
        raise ReconstructionMismatch("No supported prepared solver handover in selected ledger")
    event_id = marker["event_id"]
    receipt = _json(source / "operations" / f"{event_id:06d}.receipt.json")
    result_path = source / "operations" / receipt["result_file"]
    if (receipt.get("name") != marker["operation"]
            or receipt.get("arguments") != marker.get("arguments")
            or _sha(result_path) != receipt.get("result_sha256")
            or receipt.get("result_sha256") != marker.get("result_sha256")):
        raise ReconstructionMismatch("Prepared handover receipt differs from its marker")
    old_root = Path(launch["session_dir"])
    if str(marker["session_root"]) != str(old_root):
        raise ReconstructionMismatch("Prepared handover belongs to another session")
    value = _json(result_path)
    for key in ("operation", "session_root", "wall_time", "perf_counter"):
        if key not in value.get("result", {}) or value["result"][key] != marker.get(key):
            raise ReconstructionMismatch(f"Prepared handover marker differs from its result: {key}")
    inventory = value["snapshot"]["files"]
    indexed = {entry["path"]: entry for entry in inventory}
    for role in ("card_source", "calc_input"):
        original = marker["arguments"]["kwargs"][role]
        relative = _relative(original, old_root)
        expected = marker["arguments"][role + "_sha256"]
        entry = indexed.get(relative.as_posix())
        if not entry or entry["sha256"] != expected:
            raise ReconstructionMismatch(f"Prepared {role} is absent from the snapshot")
        if _sha(source / "artifacts" / expected) != expected:
            raise ReconstructionMismatch(f"Prepared {role} snapshot bytes differ")
        if _sha(destination / relative) != expected:
            raise ReconstructionMismatch(f"Current {role} differs from the prepared solver input")
    solver_relative = _relative(marker["arguments"]["kwargs"]["output_dir"], old_root)
    if solver_relative.name != "solver" or len(solver_relative.parts) != 2:
        raise ReconstructionMismatch("Prepared solver is not inside one native L1 call")
    call_relative = solver_relative.parent
    for relative in (call_relative / "input.json",):
        entry = indexed.get(relative.as_posix())
        if not entry or _sha(destination / relative) != entry["sha256"]:
            raise ReconstructionMismatch("Prepared L1 brief differs from the current call")
    # Validate every source blob before admitting the boundary workspace.
    for entry in inventory:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ReconstructionMismatch("Prepared snapshot path escapes its run")
        blob = source / "artifacts" / entry["sha256"]
        if filesystem_path(blob).stat().st_size != entry["bytes"] or _sha(blob) != entry["sha256"]:
            raise ReconstructionMismatch(f"Prepared snapshot blob differs: {relative}")
    # Only the selected deterministic solver may have newer numerical files.
    # Later reports, model context, other branches and stage cards would leak
    # future state into live tools after replay, so reject them without editing.
    expected_calls = {Path(relative).parts[0] for relative in indexed
                      if Path(relative).parts[0].startswith('L1_call_')}
    if any(p.name not in expected_calls for p in filesystem_path(destination).glob('L1_call_*')):
        raise ReconstructionMismatch('Workspace has an L1 call absent from the selected boundary')
    for path in filesystem_path(destination).rglob('*'):
        if not path.is_file():
            continue
        relative = _relative(path, destination)
        if (relative.parts[:2] == ('run_provenance', 'first_principle_reconstruction')
                or solver_relative == relative or solver_relative in relative.parents):
            continue
        expected = indexed.get(relative.as_posix())
        if not expected or _sha(path) != expected['sha256']:
            raise ReconstructionMismatch(
                f'Workspace differs from the selected first-principle boundary: {relative}')
    for relative, entry in indexed.items():
        rel = Path(relative)
        if (rel.parts[:2] == ('run_provenance', 'first_principle_reconstruction')
                or solver_relative == rel or solver_relative in rel.parents):
            continue
        if not filesystem_path(destination / rel).is_file():
            raise ReconstructionMismatch(f'Missing boundary artifact: {relative}')
    return {"source": str(source), "root": str(destination), "old_root": str(old_root),
            "marker": marker, "inventory": inventory, "call_relative": call_relative.as_posix(),
            "boundary": {"kind": "planned_operation", "event_id": event_id,
                         "name": marker["operation"]}}


def active_plan():
    session = current_session()
    return getattr(session, "analysis_continuation", None) if session else None


def replaying_preparation():
    session = current_session()
    return bool(active_plan() and not session.live)


def native_clock(module, kind, original):
    """Replay the recorded native duration clocks without changing regular runs."""
    session, plan = current_session(), active_plan()
    if not plan:
        return original()
    if not session.live:
        return float(session.operation("planned.native_clock." + kind,
                                       {"module": module}, original))
    anchor = plan["marker"].get("wall_time" if kind == "time" else "perf_counter")
    if anchor is None or session.live_started_monotonic is None:
        raise ReconstructionMismatch("Continuation clock has no saved anchor")
    return float(anchor) + max(0.0, time.monotonic() - session.live_started_monotonic)


def seed_working_memory(memory):
    """Restore only the original in-memory prefix, retaining later files intact."""
    session, plan = current_session(), active_plan()
    if not plan or session.live:
        return
    initial = next(r for r in session.verified_source_records()
                   if r.get("name") == "analysis.initial_workspace")
    files = session.verified_operation_result(initial["id"])["snapshot"]
    old = next((e for e in files if e["path"] == "working_memory.json"), None)
    plan["working_memory"] = memory
    memory._store = _json(session.source_dir / "artifacts" / old["sha256"]) if old else {}


def saved_l0_prompt(system_prompt, user_message, memory, tools):
    """Resume the recorded L0 instructions after verifying its initial context.

    Only the first verified agent entry may supply L0's prompt. Fresh sessions
    and agents first entered after the replay boundary use current instructions.
    """
    session = current_session()
    if not (replaying_preparation() or (
            session is not None and getattr(session, 'mode', None) == 'reconstruction'
            and not session.live)):
        return system_prompt
    entries = [r for r in session.verified_source_records()
               if r.get("name") == "runtime.agent_enter"]
    if not entries:
        raise ReconstructionMismatch("Saved L0 entry is unavailable")
    entry = min(entries, key=lambda r: r["start_sequence"])
    arguments = entry["arguments"]
    if (entry.get("parent_ids") or arguments.get("entrypoint") != "agent_turn"
            or session.canonicalize(arguments.get("user_message")) != session.canonicalize(user_message)
            or session.canonicalize(arguments.get("memory")) != session.canonicalize(memory)):
        raise ReconstructionMismatch("Saved L0 question or initial memory differs")
    saved = session.rebind(arguments.get("system_prompt"))
    if not isinstance(saved, str) or not saved or not tools:
        raise ReconstructionMismatch("Saved L0 instructions/tools are unavailable")
    return saved


def saved_l1_prompt(system_prompt, user_message, tools):
    """Continue the already-started agent with its saved system instructions.

    The caller's exact brief and empty initial memory must identify one saved
    L1 entry. New agents after the boundary always use current instructions.
    """
    session = current_session()
    if not replaying_preparation():
        return system_prompt
    entries = [r for r in session.verified_source_records()
               if r.get("name") == "runtime.agent_enter"
               and not r.get("parent_ids")
               and session.canonicalize(r["arguments"].get("user_message")) == session.canonicalize(user_message)
               and r["arguments"].get("memory") == []]
    if len(entries) != 1:
        raise ReconstructionMismatch("Saved L1 entry cannot be identified uniquely")
    entry = entries[0]
    # Every actual call in the recorded prefix will additionally pass the
    # native parser and strict request matcher; no replacement response exists.
    saved = session.rebind(entry["arguments"]["system_prompt"])
    if not isinstance(saved, str) or not tools:
        raise ReconstructionMismatch("Saved L1 instructions/tools are unavailable")
    return saved


def _verify_snapshot(saved):
    """Consume recorded stage state without writing old blobs over live files."""
    session = current_session()
    for entry in saved.get("files", []):
        blob = session.source_dir / "artifacts" / entry["sha256"]
        if _sha(blob) != entry["sha256"]:
            raise ReconstructionMismatch("Completed stage snapshot is damaged")
        # A later interrupted invocation must still have the bytes referenced
        # by its own replayed stage receipts. Only the new provenance ledger is
        # populated; the current scientific workspace is never restored here.
        retained = filesystem_path(session.output_dir / "artifacts" / entry["sha256"])
        retained.parent.mkdir(parents=True, exist_ok=True)
        if not retained.exists():
            shutil.copyfile(filesystem_path(blob), retained)
        if _sha(retained) != entry["sha256"]:
            raise ReconstructionMismatch("Retained stage snapshot is damaged")


def completed_stage(stage, function, *args, **kwargs):
    session = current_session()
    if not replaying_preparation():
        return function(*args, **kwargs)
    from .analysis_reconstruction import _encode, _decode
    result = session.operation("planned.completed_" + stage,
                               {"args": _encode(list(args)), "kwargs": _encode(kwargs)},
                               lambda: session.reject("A completed preparation stage attempted live execution"),
                               restore=_verify_snapshot)
    result = _decode(result)
    keys = {"LC1": ("system_catalog_path", "eq_map_card_path"),
            "LC2": ("final_card_path",), "LC3": ("final_card_path",)}[stage]
    plan = active_plan()
    indexed = {e["path"]: e for e in plan["inventory"]}
    for key in keys:
        path = result.get(key)
        if not path and stage == "LC1":
            # These are the existing native caller's LC1 fallback filenames.
            filename = {"system_catalog_path": "lc1_sweep_input.json",
                        "eq_map_card_path": "lc1_2_eqmap_card.json"}[key]
            path = Path(kwargs["output_dir"]) / filename
        if not path:
            raise ReconstructionMismatch(f"Completed {stage} lacks {key}")
        relative = _relative(path, plan["root"])
        entry = indexed.get(relative.as_posix())
        if not entry or _sha(path) != entry["sha256"]:
            raise ReconstructionMismatch(f"Completed {stage} artifact changed: {key}")
    return result


def _restore_gate_state(saved):
    _verify_snapshot(saved)
    plan = active_plan()
    memory = plan.get("working_memory")
    if memory is None:
        return
    stores = [item["state"] for key, item in saved.get("shared", {}).items()
              if key.endswith(".working_memory") and item.get("state") is not None]
    if stores:
        if not all(isinstance(s, dict) and s == stores[0] for s in stores):
            raise ReconstructionMismatch("Prepared working-memory aliases disagree")
        # Canonical receipt JSON sorts mapping keys. The native renderer uses
        # insertion order, so restore the byte-backed memory file's order too.
        entry = next((e for e in saved.get('files', [])
                      if e['path'] == 'working_memory.json'), None)
        if entry is None:
            if stores[0]:
                raise ReconstructionMismatch('Prepared working-memory ordering has no saved source')
            ordered = {}
        else:
            session = current_session()
            ordered = _json(session.source_dir / 'artifacts' / entry['sha256'])
            ordered = getattr(session, 'rebind', lambda value: value)(ordered)
            if ordered != stores[0]:
                raise ReconstructionMismatch('Prepared working-memory file differs from saved state')
        memory._store = ordered


def solver_handover(function, *args, **kwargs):
    session, plan = current_session(), active_plan()
    if not plan or session.live:
        return function(*args, **kwargs)
    from .analysis_reconstruction import _encode
    arguments = {"args": _encode(list(args)), "kwargs": _encode(kwargs),
                 "card_source_sha256": _sha(kwargs["card_source"]),
                 "calc_input_sha256": _sha(kwargs["calc_input"])}
    def live():
        session.live_clock_anchor = float(plan["marker"]["wall_time"])
        return function(*args, **kwargs)
    return session.resume_operation("planned.before_first_solver", arguments,
                                    live, restore=_restore_gate_state)


def preserve_initial_files(_inventory):
    """Keep the verified boundary workspace in place while replaying its prefix."""
    if not active_plan():
        raise ReconstructionMismatch("In-place preservation requires an explicit continuation")


__all__ = ["inspect_handover", "native_clock",
           "seed_working_memory", "saved_l1_prompt", "completed_stage",
           "solver_handover", "replaying_preparation", "preserve_initial_files"]
