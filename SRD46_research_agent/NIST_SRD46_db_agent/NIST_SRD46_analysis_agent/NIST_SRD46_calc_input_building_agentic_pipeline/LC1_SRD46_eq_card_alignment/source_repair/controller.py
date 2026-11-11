"""Compiler-equivalent LC1 gates and bounded repair of immutable source rows."""
from __future__ import annotations

import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

from .records import digest, pair_ids, pair_key, provenance_issues, selected_rows


def io_path(path):
    value = os.path.abspath(os.fspath(path))
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        value = "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
    return Path(value)


def write_json(path, value):
    target = io_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(target)


def compile_repaired_pairs(card, pair_keys, output_dir, chemical_system=None):
    """Use the native source -> species -> free-energy compiler, without APIs.

    Only requested pairs are returned. Their authoritative H/ligand and
    metal/OH prerequisites are included, exactly as in the normal LC2 builder.
    All artifact directories must belong to the caller's new attempt.
    """
    core = io_path(__file__).parents[3] / "NIST_SRD46_core_numcalc_pipeline"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.ref_eq_SRD46_json_cards_builder import (
        build_or_load_ref_card, _validated_dependency_networks)
    contracts = None
    if chemical_system:
        from LC2_free_energy_card_building.LC2_1_card_initializer.LC2_1_ref_eq_card_orchestrator import _ligand_component_contracts
        contracts = _ligand_component_contracts(chemical_system)
    wanted = None if pair_keys is None else set(pair_keys)
    results = []
    networks = card.get("equilibrium_networks", [])
    available = {pair_key(pair) for pair in networks}
    if wanted and not wanted <= available:
        raise ValueError(f"Repair pair is outside the fixed catalog: {sorted(wanted - available)}")
    for pair in networks:
        key = pair_key(pair)
        if wanted is not None and key not in wanted:
            continue
        _md, _card, md_path = build_or_load_ref_card(
            pair, storage_dir=io_path(output_dir) / key,
            dependency_networks=_validated_dependency_networks(pair, networks),
            ligand_component_contracts=contracts,
        )
        results.append({"pair_key": key, "json_path": str(md_path.with_suffix(".json")),
                        "md_path": str(md_path)})
    return results


def inspect_selection(card, chemical_system, output_dir):
    """Return structured failures; never equate a numerical patch with evidence."""
    diagnostics, artifacts = [], []
    source_owners = {}
    for entry in card.get("equilibrium_networks", []):
        for row in selected_rows(entry):
            source_owners[int(row["vlm_id"])] = entry
    for pair in card.get("equilibrium_networks", []):
        key = pair_key(pair)
        base = {"pair_key": key, "pair_keys": [key], "metal_id": pair_ids(pair)[0],
                "issue_key": key,
                "ligand_id": pair_ids(pair)[1], "source_pair_sha256": digest(pair),
                "repair_scope": "source_selection"}
        issues = provenance_issues(pair)
        if issues:
            diagnostics.append({**base, "error_code": "source_provenance_invalid",
                                "issues": issues})
            continue
        try:
            artifacts += compile_repaired_pairs(card, [key], output_dir, chemical_system)
        except Exception as exc:
            diagnostic = getattr(exc, "diagnostic", None)
            if diagnostic is None:
                # Infrastructure, missing packages and malformed unrelated
                # inputs are not invitations to invent new chemistry.
                if not isinstance(exc, (ValueError, LookupError)):
                    raise
                diagnostic = {"error_code": "source_compile_failure", "message": str(exc)}
            owners = {}
            for reaction in diagnostic.get("unresolved_reactions", []):
                # vlm_median(<row>/<row>) belongs to the pair of its rows.
                match = re.match(r"vlm_(?:[a-z]+\()?(\d+)", str(reaction.get("source_id", "")))
                owner = source_owners.get(int(match.group(1))) if match else None
                if owner:
                    owners[pair_key(owner)] = owner
            if not owners:
                owners[key] = pair
            for owner_key, owner in owners.items():
                diagnostics.append({**diagnostic, **base,
                    "pair_key": owner_key, "pair_keys": [owner_key], "issue_key": owner_key,
                    "metal_id": pair_ids(owner)[0], "ligand_id": pair_ids(owner)[1],
                    "source_pair_sha256": digest(owner), "compiled_pair_key": key})
    # A prerequisite can fail in its own card and a dependent card. It is one
    # source issue, with both compiler diagnostics retained for the reviewer.
    unique = {}
    for diagnostic in diagnostics:
        key = diagnostic["pair_key"]
        if key in unique:
            unique[key].setdefault("related_diagnostics", []).append(diagnostic)
        else:
            unique[key] = diagnostic
    diagnostics = list(unique.values())
    return {"status": "ok" if not diagnostics else "source_repair_required",
            "diagnostics": diagnostics, "artifacts": artifacts, "card_sha256": digest(card)}


def selection_signature(card):
    """Ignore new prose when detecting a repeated scientific selection."""
    return digest([{"pair_key": pair_key(p), "rows": selected_rows(p),
                    "patches": (p.get("patch_notes") or {}).get("patches", [])}
                   for p in card.get("equilibrium_networks", [])])


def _ensure_validated_selection(*, card, chemical_system, purpose, tasks,
        request_T_C=25.0, request_I_M=0.1, output_dir, repair_enabled=True,
        max_rounds=None, attempts_by_issue=None, diagnostic=None, repair_runner=None,
        _persist=None, _seen_signatures=None):
    """Validate, repair affected pairs, and compile again with a shared budget."""
    from SRD46_calc_input_building_config import AGENT_CONFIG as cfg
    from .agent import run_source_repair
    runner = repair_runner or run_source_repair
    limit = int(getattr(cfg, "SOURCE_REPAIR_MAX_ROUNDS", 2))
    if max_rounds is not None:
        limit = min(limit, max(0, int(max_rounds)))
    counts = dict(attempts_by_issue or {})
    current = deepcopy(card)
    original_pairs = {pair_key(p): pair_ids(p) for p in current.get("equilibrium_networks", [])}
    scope_sha = digest(chemical_system)
    root = io_path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    report = {"schema": "srd46-source-repair/v1", "chemical_system_sha256": scope_sha,
              "initial_card_sha256": digest(current), "rounds": []}
    seen = set(_seen_signatures or ()) | {selection_signature(current)}
    gate = inspect_selection(current, chemical_system, root / "gate_00")
    if diagnostic and gate["status"] == "ok":
        targets = diagnostic.get("pair_keys") or [diagnostic.get("pair_key")]
        targets = [key for key in targets if key in original_pairs]
        if not targets:
            gate = {**gate, "status": "needs_human", "diagnostics": [diagnostic]}
        else:
            gate["status"] = "source_repair_required"
            gate["diagnostics"] = [{**diagnostic, "pair_key": key, "pair_keys": [key], "issue_key": key}
                                   for key in targets]
    for round_number in range(1, limit + 1):
        if gate["status"] != "source_repair_required" or not repair_enabled:
            break
        changed = False
        for failure in gate["diagnostics"]:
            key = failure["pair_key"]
            # Pair identity deliberately spans early and late diagnostics: a
            # changed error message cannot buy another two attempts.
            issue = key
            if counts.get(issue, 0) >= int(getattr(cfg, "SOURCE_REPAIR_MAX_ROUNDS", 2)):
                gate["status"] = "repair_budget_exhausted"
                break
            counts[issue] = counts.get(issue, 0) + 1
            if _persist:
                # Reserve before model execution: even an interrupted call
                # consumes this scoped attempt and cannot overwrite its log.
                _persist(counts, seen, current, "dispatch_reserved",
                         {"issue_key": issue, "diagnostic": failure})
            out = runner(card=current, diagnostic=failure, chemical_system=chemical_system,
                         purpose=purpose, tasks=tasks, request_T_C=request_T_C,
                         request_I_M=request_I_M,
                         output_dir=root / f"round_{round_number:02d}" / key)
            report["rounds"].append({"pair_key": key, "attempt": counts[issue], **out})
            if out.get("status") != "ok":
                gate["status"] = out.get("status", "repair_incomplete")
                detail = deepcopy(out.get("diagnostic") or failure)
                detail["failure_stage"] = next(
                    ("LC1." + stage for stage in ("source_pre", "source_post") if stage in root.parts),
                    detail.get("failure_stage", "LC1.source_repair"),
                )
                detail["repair_status"] = gate["status"]
                detail["source_repair_attempts_by_issue"] = dict(counts)
                if out.get("question"):
                    detail["question"] = out["question"]
                    detail["message"] = out["question"]
                elif out.get("_error") or out.get("error"):
                    detail["message"] = out.get("_error") or out["error"]
                gate["diagnostics"] = [detail]
                break
            candidate = out["card"]
            if {pair_key(p): pair_ids(p) for p in candidate["equilibrium_networks"]} != original_pairs:
                raise ValueError("Source repair changed the chemical catalog scope")
            new_sha = selection_signature(candidate)
            if new_sha in seen:
                gate["status"] = "identical_repair_rejected"
                break
            seen.add(new_sha)
            current = candidate
            changed = True
            if _persist:
                _persist(counts, seen, current, "selection_returned", {"issue_key": issue})
        if gate["status"] != "source_repair_required":
            break
        if not changed:
            break
        gate = inspect_selection(current, chemical_system, root / f"gate_{round_number:02d}")
    if gate["status"] == "source_repair_required":
        gate["status"] = "repair_budget_exhausted" if repair_enabled else "source_repair_required"
    report.update(status=gate["status"], final_gate=gate,
                  final_card_sha256=digest(current), source_repair_attempts_by_issue=counts)
    report_path = write_json(root / "source_repair_report.json", report)
    card_path = write_json(root / "validated_eqmap_card.json", current)
    diagnostic = gate["diagnostics"][0] if gate["diagnostics"] else None
    error = None
    if gate["status"] != "ok":
        detail = (diagnostic or {}).get("message") or gate["status"]
        error = (
            f"Source repair {gate['status']}: {detail}; actual attempts by pair: "
            + json.dumps(counts, sort_keys=True)
        )
    return {"status": gate["status"], "card": current, "eq_map_card_path": card_path,
            "report_path": report_path, "diagnostic": (gate["diagnostics"][0] if gate["diagnostics"] else None),
            "source_repair_attempts_by_issue": counts, "report": report, "_error": error}


def ensure_validated_selection(*, card, chemical_system, purpose, tasks,
        request_T_C=25.0, request_I_M=0.1, output_dir, repair_enabled=True,
        max_rounds=None, attempts_by_issue=None, diagnostic=None, repair_runner=None):
    """Durable validation invocation; prior compatible repairs retain their budget."""
    base = io_path(output_dir)
    binding = {"schema": "srd46-source-validation-binding/v1", "input_sha256": digest(card),
               "chemical_system_sha256": digest(chemical_system), "purpose": purpose, "tasks": tasks,
               "request_T_C": float(request_T_C), "request_I_M": float(request_I_M),
               "diagnostic_sha256": digest(diagnostic),
               "workflow_sha256": digest(io_path(__file__).with_name("WORKFLOW.md").read_text(encoding="utf-8")),
               "implementation_sha256": digest({name: io_path(__file__).with_name(name).read_text(encoding="utf-8")
                    for name in ("controller.py", "records.py", "agent.py")})}
    bucket = base / "bindings" / digest(binding)
    bucket.mkdir(parents=True, exist_ok=True)
    lock = bucket / "validation.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        fd = None
        state_path = bucket / "validation_state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("binding") != binding:
                raise ValueError("Source repair receipt scope or input binding differs")
            if (not isinstance(state.get("counts"), dict) or
                    any(not isinstance(v, int) or v < 0 for v in state["counts"].values()) or
                    not isinstance(state.get("invocation"), int) or state["invocation"] < 1):
                raise ValueError("Invalid persisted source repair budget receipt")
        else:
            state = {"binding": binding, "counts": {}, "seen": [], "invocation": 0, "events": []}
        counts = dict(state["counts"])
        for key, value in (attempts_by_issue or {}).items():
            counts[key] = max(counts.get(key, 0), int(value))
        state["counts"] = counts
        state["invocation"] += 1
        invocation = bucket / f"validation_{state['invocation']:04d}"
        invocation.mkdir(exist_ok=False)
        current = deepcopy(card)
        prior_complete = state.get("status") == "ok"
        checkpoint_rejected = None
        if state.get("checkpoint"):
            checkpoint_path = io_path(state["checkpoint"])
            # A copied state can still name the previous run directory. Do not
            # reuse that other workspace, or abort rebuilding on a missing file.
            if io_path(bucket.resolve()) not in io_path(checkpoint_path.resolve()).parents:
                checkpoint_rejected = "outside_binding_directory"
            elif not checkpoint_path.is_file():
                checkpoint_rejected = "missing_checkpoint"
            else:
                try:
                    checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    checkpoint_rejected = "missing_checkpoint"
                else:
                    checkpoint = json.loads(checkpoint_text)
                    if checkpoint.get("binding") != binding:
                        raise ValueError("Accepted source repair checkpoint binding differs")
                    current = checkpoint["card"]
            if checkpoint_rejected:
                prior_complete = False
        sequence = 0

        def persist(current_counts, seen, current_card, status, event):
            nonlocal sequence
            sequence += 1
            snapshot = {"binding": binding, "counts": dict(current_counts), "seen": sorted(seen),
                        "card": current_card, "status": status, "event": event}
            checkpoint = write_json(invocation / f"checkpoint_{sequence:04d}.json", snapshot)
            state.update(counts=dict(current_counts), seen=sorted(seen), checkpoint=checkpoint, status=status)
            state["events"].append({"invocation": state["invocation"], "checkpoint": checkpoint,
                                    "status": status, **event})
            temporary = state_path.with_suffix(".tmp")
            write_json(temporary, state)
            os.replace(str(temporary), str(state_path))

        persist(counts, state.get("seen", []), current, "validation_started",
                {"checkpoint_rejected": checkpoint_rejected,
                 "rejected_checkpoint": state["checkpoint"]} if checkpoint_rejected else {})
        result = _ensure_validated_selection(card=current, chemical_system=chemical_system,
            purpose=purpose, tasks=tasks, request_T_C=request_T_C, request_I_M=request_I_M,
            output_dir=invocation, repair_enabled=repair_enabled, max_rounds=max_rounds,
            attempts_by_issue=counts, diagnostic=None if prior_complete else diagnostic, repair_runner=repair_runner,
            _persist=persist, _seen_signatures=state.get("seen", []))
        persist(result["source_repair_attempts_by_issue"], state.get("seen", []),
                result["card"], result["status"], {"report_path": result["report_path"]})
        result["validation_state_path"] = str(state_path)
        return result
    finally:
        # Only the lock created by this invocation is removed. Prior reports
        # and checkpoints remain immutable; a killed process leaves a visible
        # stale lock for explicit recovery, never an automatic extra attempt.
        if fd is not None:
            os.close(fd)
        lock.unlink()


def repair_lc1_selection(*, previous_lc1, diagnostic, purpose, tasks, output_dir,
                         request_T_C=25.0, request_I_M=0.1, max_rounds=None):
    """Repair a saved LC1 result without alignment, catalog edits, or fresh scope."""
    prior = deepcopy(previous_lc1)
    card = json.loads(io_path(prior["eq_map_card_path"]).read_text(encoding="utf-8"))
    catalog = prior.get("system_catalog")
    if not catalog and prior.get("system_catalog_path"):
        envelope = json.loads(io_path(prior["system_catalog_path"]).read_text(encoding="utf-8"))
        catalog = envelope.get("system_catalog", envelope)
    if not catalog:
        raise ValueError("Scoped source repair requires the original system catalog")
    chemical_system = catalog.get("chemical_system", prior.get("chemical_system"))
    if not chemical_system:
        raise ValueError("Original chemical_system is missing")
    result = ensure_validated_selection(card=card, chemical_system=chemical_system,
        purpose=purpose, tasks=tasks, output_dir=output_dir, request_T_C=request_T_C,
        request_I_M=request_I_M, max_rounds=max_rounds,
        attempts_by_issue=prior.get("source_repair_attempts_by_issue"), diagnostic=diagnostic)
    prior.update(status=result["status"], eq_map_card_path=result["eq_map_card_path"],
                 source_repair_report_path=result["report_path"],
                 source_repair_attempts_by_issue=result["source_repair_attempts_by_issue"],
                 source_repair_diagnostic=result["diagnostic"])
    if result.get("_error"):
        prior["_error"] = result["_error"]
    prior["source_repair_diagnostics"] = result["report"]["final_gate"]["diagnostics"]
    prior["source_repair_previous_eq_map_card_path"] = previous_lc1["eq_map_card_path"]
    write_json(io_path(output_dir) / "repaired_lc1_result.json", prior)
    return prior
