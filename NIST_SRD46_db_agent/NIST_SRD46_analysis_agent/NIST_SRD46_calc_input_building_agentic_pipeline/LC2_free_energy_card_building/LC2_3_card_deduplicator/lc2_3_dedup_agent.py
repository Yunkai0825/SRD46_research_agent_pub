"""LC2_3 — Groupwise LLM deduplication orchestrator.

Pipeline
--------
1. Read the dedup report (``deduplication_check.md``) produced by LC2_2
   into a :class:`DedupReport`.  LC2_3 **never re-merges** — LC2_2 has
   already built the final merged card and enumerated every group.
2. Split groups into multi-member (>1 species) and singletons.
3. For each multi-member group, dispatch an *independent* LLM subagent
   in parallel (one agent ↔ one group) — :func:`run_group_agent`.
4. For all singletons, dispatch ONE batched LLM agent —
   :func:`run_singletons_agent`.
5. Combine every keep decision and apply it deterministically to the
   merged card markdown via :func:`apply_decisions_to_card`: dropped
   species are flagged ``include = false`` (audit-preserving) in
   Section 5.  The result is written as the deduplicated card.

The LLM pathways live in :mod:`_pair_dedup_subagent`; the deterministic
apply engine lives in :mod:`_dedup_engine`.  This file only orchestrates
*which* decisions are produced and *where* artefacts land.

Public API
----------
* :func:`configure_lc2_3_session`
* :func:`run_lc2_3`
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── path bootstrap: import LC2's external deps (shared LLM engine, card
#    helpers, analysis toolbox) as bare top-level packages WITHOUT pulling
#    in the heavy NIST_SRD46_analysis_agent package __init__ chain. ──────
_THIS = Path(__file__).absolute()
_PIPELINE_ROOT = _THIS.parents[2]   # NIST_SRD46_calc_input_building_agentic_pipeline/
_ANALYSIS_ROOT = _THIS.parents[3]   # NIST_SRD46_analysis_agent/
_DB_AGENT_ROOT = _THIS.parents[4]   # NIST_SRD46_db_agent/
_SRD46_ROOT    = _THIS.parents[5]   # SRD46_research_agent/
for _p in (_PIPELINE_ROOT, _ANALYSIS_ROOT, _DB_AGENT_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from general_db_query_engine.general_subagent_delegation_helpers._parallel_dispatch import (
    dispatch_parallel,
)
from analysis_agent_toolbox.calc_wrappers import _require_purpose_tasks
from card_management_helpers.dedup_md_card_reader import (
    DedupGroup,
    DedupReport,
    parse_dedup_markdown,
)
from ._dedup_engine import (
    group_to_payload,
    split_groups,
)
from ._dedup_decision import load_general_plan
from ._pair_dedup_subagent import run_group_agent, run_singletons_agent
from ._pair_dedup_subagent._agent_common import cfg
from ..LC2_2_card_db_merger.element_inventory import (
    ElementInventoryEntry,
    card_include_index,
    inventory_from_json,
)
from ._element_dedup_orchestrator.instruction_agent import (
    build_element_instructions,
    run_element_review_phase,
)
from ._element_dedup_orchestrator.review_report import (
    diff_to_json,
    materialize_review,
    render_diff,
    render_entries_by_element,
    render_mark_history,
    render_post_dedup_report,
    selection_diff,
    solid_family_warnings,
)
from ..agent_context_artifacts import write_agent_context_index

log = logging.getLogger("Analysis.LC2_3")


# ════════════════════════════════════════════════════════════════════
#  Session state
# ════════════════════════════════════════════════════════════════════

_SESSION: Dict[str, Any] = {
    "session_dir":    None,
    "history":        None,
    "stats":          None,
    "working_memory": None,
    "debug":          False,
    "call_index":     0,
}


def configure_lc2_3_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or Path.cwd()
    Path(base).mkdir(parents=True, exist_ok=True)
    # Never reuse an earlier call directory: stale context manifests could
    # otherwise satisfy a later run's context-count audit.
    while True:
        _SESSION["call_index"] += 1
        out = Path(base) / f"LC2_3_call_{_SESSION['call_index']:02d}"
        try:
            out.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return out


def _slug(text: str) -> str:
    """Filesystem-safe slug for a per-sub-agent context folder name."""
    s = re.sub(r"[^0-9A-Za-z._-]+", "_", str(text or "").strip())
    return s.strip("_")[:48] or "x"


def _file_artifact(path: str | Path | None) -> Optional[Dict[str, Any]]:
    """Describe one persisted artifact without embedding its content.

    ``.absolute()`` — never ``.resolve()`` — so mapped-drive records stay in
    drive-letter form instead of the ~30-char-longer UNC expansion.
    """
    if path is None:
        return None
    item = Path(path)
    if not item.is_file():
        return {"path": str(item.absolute()), "exists": False}
    data = item.read_bytes()
    return {
        "path": str(item.absolute()),
        "exists": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _write_instruction_snapshot(
    call_dir: Path,
    generation: int,
    instructions: Dict[str, str],
    *,
    reason: str,
    case_recommendations: str = "",
) -> Path:
    """Version the exact element instructions used by one generation."""
    path = call_dir / f"element_instructions_generation_{generation:02d}.md"
    body = (
        "# Element deduplication instructions\n\n"
        f"- generation: {generation}\n"
        f"- reason: {reason}\n\n"
    )
    if case_recommendations.strip():
        body += (
            "## Case-specific recommendations (child system prompts)\n\n"
            f"{case_recommendations.strip()}\n\n"
            "## Element instructions\n\n"
        )
    body += "\n".join(
        f"- **{element}**: {instruction}"
        for element, instruction in sorted(instructions.items())
    ) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


_ADDENDUM_HEADER = "## Calculation-specific addendum"


def _compose_plan_doc(plan: str, case_recommendations: str) -> str:
    """Audit view of the full drafted plan: static defaults plus the
    supervisor's case-specific recommendations (delivered to workers via
    their system prompts)."""
    recommendations = (case_recommendations or "").strip()
    if not recommendations:
        return plan
    section = (
        "## Case-specific recommendations (element supervisor — appended to "
        "child system prompts)\n\n"
        f"{recommendations}\n"
    )
    if _ADDENDUM_HEADER in plan:
        return plan.replace(_ADDENDUM_HEADER, f"{section}\n{_ADDENDUM_HEADER}", 1)
    return f"{plan.rstrip()}\n\n{section}"


def _write_lc2_3_manifest(call_dir: Path, payload: Dict[str, Any]) -> Path:
    """Write the authoritative LC2_3 run manifest."""
    path = call_dir / "lc2_3_manifest.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def _element_instruction_block(
    payload: Dict[str, Any],
    instructions: Dict[str, str],
) -> str:
    rows = [
        f"- {element}: {instructions[element]}"
        for element in sorted(payload.get("elements", []))
        if element in instructions
    ]
    return (
        "[Element-level chemistry instructions]\n" + "\n".join(rows)
        if rows else ""
    )


def _run_dedup_pass(
    *,
    report_obj: DedupReport,
    inventory: List[ElementInventoryEntry],
    plan: str,
    element_instructions: Dict[str, str],
    generation_dir: Path,
    debug: bool,
    case_recommendations: str = "",
) -> Dict[str, Any]:
    """Dispatch one complete pass from the immutable report.

    Sorting and element-to-group routing are deterministic.  Only the LLM
    decisions vary; a full restart calls this function again with the same
    original report and revised plain-text element instructions.
    ``case_recommendations`` is appended to every worker's system prompt.
    """
    multi, singles = split_groups(report_obj)
    multi = sorted(multi, key=lambda g: (g.phase, g.core_label))
    singles = sorted(singles, key=lambda g: (g.phase, g.core_label))
    generation_dir.mkdir(parents=True, exist_ok=True)
    subagents_root = generation_dir / "subagents"
    (generation_dir / "plan_supplied_to_workers.md").write_text(
        plan, encoding="utf-8",
    )
    (generation_dir / "case_recommendations.md").write_text(
        ((case_recommendations or "").strip() or "(none committed)") + "\n",
        encoding="utf-8",
    )
    (generation_dir / "element_instructions.json").write_text(
        json.dumps(element_instructions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    dispatch_manifest: Dict[str, Any] = {
        "artifact_kind": "LC2_3 dedup generation",
        "generation_directory": str(generation_dir.absolute()),
        "case_recommendations_in_system_prompts": bool(
            (case_recommendations or "").strip()
        ),
        "multi_group_workers": [],
        "singleton_worker": None,
    }

    multi_results: List[Dict[str, Any]] = []
    if multi:
        tasks_payload: List[Dict[str, Any]] = []
        for index, group in enumerate(multi, start=1):
            payload = group_to_payload(group, inventory)
            element_block = _element_instruction_block(payload, element_instructions)
            group_plan = "\n\n".join(
                block for block in (plan, element_block) if block.strip()
            )
            tasks_payload.append({
                "label": f"{group.phase}::{group.core_label}",
                "plan": group_plan,
                "case_recommendations": case_recommendations,
                "subagent_dir": str(
                    subagents_root
                    / f"group_{index:02d}_{_slug(group.phase)}_{_slug(group.core_label)}"
                ),
                "group_payload": json.dumps(payload),
            })
            dispatch_manifest["multi_group_workers"].append({
                "label": f"{group.phase}::{group.core_label}",
                "elements": payload.get("elements", []),
                "context_directory": tasks_payload[-1]["subagent_dir"],
                "receives_general_plan": bool(plan.strip()),
                "receives_element_instructions": bool(element_block.strip()),
                "receives_case_recommendations": bool(
                    (case_recommendations or "").strip()
                ),
            })
        dispatched = dispatch_parallel(
            json.dumps(tasks_payload),
            run_group_agent,
            max_workers=min(5, len(multi)),
            runner_kwargs_keys=(
                "plan", "subagent_dir", "group_payload", "case_recommendations",
            ),
            default_agent="lc2_3_group",
        )
        multi_results = dispatched.get("results", []) or []

    singleton_result: Optional[Dict[str, Any]] = None
    if singles:
        singleton_payload = [group_to_payload(group, inventory) for group in singles]
        all_instruction_rows = [
            f"- {element}: {instruction}"
            for element, instruction in sorted(element_instructions.items())
        ]
        singleton_instruction_block = (
            "[Element-level chemistry instructions]\n"
            + "\n".join(all_instruction_rows)
        )
        # A targeted redispatch carries supervisor guidance in ``plan``.  It
        # must reach singleton workers as well as multi-member workers.
        singleton_plan = "\n\n".join(
            block for block in (plan, singleton_instruction_block)
            if block.strip()
        )
        singleton_result = run_singletons_agent(
            singletons_payload=json.dumps(singleton_payload),
            plan=singleton_plan,
            case_recommendations=case_recommendations,
            subagent_dir=str(subagents_root / "singletons"),
            debug=debug,
        )
        dispatch_manifest["singleton_worker"] = {
            "group_count": len(singles),
            "context_directory": str(subagents_root / "singletons"),
            "receives_general_or_targeted_plan": bool(plan.strip()),
            "receives_element_instructions": bool(all_instruction_rows),
            "receives_case_recommendations": bool(
                (case_recommendations or "").strip()
            ),
        }

    decision_dicts: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    for result in multi_results:
        if result and result.get("decision"):
            decision_dicts.append(result["decision"])
        else:
            failures.append({
                "kind": "group",
                "label": (result or {}).get("label")
                or f"{(result or {}).get('phase')}::{(result or {}).get('core_label')}",
                "error": (result or {}).get("error"),
            })
    if singleton_result:
        if singleton_result.get("decisions"):
            decision_dicts.extend(singleton_result["decisions"])
        else:
            failures.append({
                "kind": "singletons",
                "error": singleton_result.get("error"),
            })

    pass_result = {
        "decisions": decision_dicts,
        "failures": failures,
        "multi": multi,
        "singles": singles,
        "iterations": sum((r or {}).get("iterations", 0) for r in multi_results)
        + int((singleton_result or {}).get("iterations", 0)),
        "n_tools": sum((r or {}).get("n_tools", 0) for r in multi_results)
        + int((singleton_result or {}).get("n_tools", 0)),
        "agent_call_count": len(multi_results) + (1 if singleton_result else 0),
    }
    dispatch_manifest.update({
        "agent_call_count": pass_result["agent_call_count"],
        "decisions": decision_dicts,
        "failures": failures,
    })
    (generation_dir / "generation_manifest.json").write_text(
        json.dumps(dispatch_manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return pass_result


def _skip_dedup_pass(
    *,
    report_obj: DedupReport,
    plan: str,
    element_instructions: Dict[str, str],
    case_recommendations: str,
    generation_dir: Path,
) -> Dict[str, Any]:
    """Supervisor-committed skip: deterministic keep-all, no worker dispatch.

    Every group receives an explicit keep-all decision so no entry is left
    ``not examined``; the review phase still gates the final commit.
    """
    generation_dir.mkdir(parents=True, exist_ok=True)
    (generation_dir / "plan_supplied_to_workers.md").write_text(
        plan, encoding="utf-8",
    )
    (generation_dir / "case_recommendations.md").write_text(
        ((case_recommendations or "").strip() or "(none committed)") + "\n",
        encoding="utf-8",
    )
    (generation_dir / "element_instructions.json").write_text(
        json.dumps(element_instructions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    decisions = [
        {
            "phase": group.phase,
            "core_label": group.core_label,
            "keep_species": [
                {"name": species.name, "source": species.source}
                for species in group.species
            ],
            "rationale": "supervisor skip: no deduplication needed",
        }
        for group in report_obj.groups
    ]
    (generation_dir / "generation_manifest.json").write_text(
        json.dumps({
            "artifact_kind": "LC2_3 dedup generation",
            "generation_directory": str(generation_dir.absolute()),
            "skipped_by_supervisor": True,
            "case_recommendations_in_system_prompts": bool(
                (case_recommendations or "").strip()
            ),
            "agent_call_count": 0,
            "decisions": decisions,
            "failures": [],
            "multi_group_workers": [],
            "singleton_worker": None,
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return {
        "decisions": decisions,
        "failures": [],
        "multi": [],
        "singles": [],
        "iterations": 0,
        "n_tools": 0,
        "agent_call_count": 0,
    }


def _subset_report(
    report: DedupReport,
    group_keys: set[tuple[str, str]],
) -> DedupReport:
    """Return an immutable-input report view containing selected groups only."""
    return DedupReport(
        system_name=report.system_name,
        baseline_source=report.baseline_source,
        sources_present=list(report.sources_present),
        component_mapping=list(report.component_mapping),
        groups=[group for group in report.groups if group.key in group_keys],
        totals=dict(report.totals),
    )

def run_lc2_3(
    *,
    purpose: str,
    tasks: str,
    dedup_md: str,                       # text of LC2_2 deduplication_check.md
    merged_card_path: str | Path,
    system_name: str,
    output_dir: str | Path,
    elements: Optional[List[str]] = None,
    element_inventory_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Run element-instructed deduplication with fresh-context review.

    ``dedup_md`` is the *text* of the LC2_2 ``deduplication_check.md``
    report; ``merged_card_path`` points at the LC2_2 merged card.

    ``element_inventory_path`` is LC2_2's immutable element-owned inventory.
    LC2_3 never re-merges databases.  A supervisory redo restores this
    original merged card/report and reruns only the dedup fan-out.
    """
    _ = elements
    purpose, tasks_text = _require_purpose_tasks(purpose, tasks)

    if _SESSION["session_dir"] is None:
        configure_lc2_3_session(session_dir=Path.cwd() / "_lc2_3_adhoc_session")

    call_dir = _per_call_dir()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    merged_card_path = Path(merged_card_path)
    if not merged_card_path.exists():
        raise FileNotFoundError(f"LC2_3: merged card not found: {merged_card_path}")

    history = _SESSION["history"]
    stats   = _SESSION["stats"]
    debug   = _SESSION["debug"]

    card_text = merged_card_path.read_text(encoding="utf-8")
    input_dedup_path = call_dir / "input_deduplication_check.md"
    input_dedup_path.write_text(dedup_md or "", encoding="utf-8")
    manifest_payload: Dict[str, Any] = {
        "schema_version": 1,
        "artifact_kind": "LC2_3 deduplication run",
        "stage": "LC2_3",
        "call_id": call_dir.name,
        "status": "running",
        "invocation": {
            "purpose": purpose,
            "tasks": tasks_text,
            "system_name": system_name,
            "debug": debug,
        },
        "inputs": {
            "merged_card": _file_artifact(merged_card_path),
            "deduplication_report_snapshot": _file_artifact(input_dedup_path),
            "element_inventory": _file_artifact(element_inventory_path),
        },
        "instruction_snapshots": [],
        "state_transitions": [],
        "outputs": {},
    }

    # ── 1. Parse the LC2_2 dedup report ───────────────────────────
    if not (dedup_md or "").strip():
        # No report means no entry can be examined.  Preserve the merged card
        # for diagnosis but fail closed so it cannot silently reach LC2_4.
        out_card = output_dir / "free_energy_card_deduplicated.md"
        out_card.write_text(card_text, encoding="utf-8")
        report = (f"# LC2_3 dispatch report (call {_SESSION['call_index']:02d})\n\n"
                  f"**Status**: failed — empty dedup_md, no dedup applied.\n")
        (call_dir / "report.md").write_text(report, encoding="utf-8")
        context_json, context_md = write_agent_context_index(call_dir)
        context_index = json.loads(context_json.read_text(encoding="utf-8"))
        manifest_payload.update({
            "status": "failed",
            "failure": "empty_deduplication_report",
            "agent_context": {
                "index_json": _file_artifact(context_json),
                "index_markdown": _file_artifact(context_md),
                "expected_calls": 0,
                "documented_calls": 0,
                "complete": context_index.get(
                    "all_context_bundles_complete", False
                ),
            },
            "outputs": {"unchanged_card": _file_artifact(out_card)},
        })
        manifest_path = _write_lc2_3_manifest(call_dir, manifest_payload)
        log.warning("LC2_3 received empty dedup_md; emitting merged card unchanged.")
        return {
            "status": "failed", "output_dir": str(call_dir),
            "enriched_card_path": str(out_card), "dedup_md_path": None,
            "manifest_path": str(manifest_path),
            "n_groups": 0, "n_multi_groups": 0, "n_singletons": 0,
            "n_decisions": 0, "n_dropped": 0, "elapsed_s": 0.0,
            "report": report,
        }

    report_obj: DedupReport = parse_dedup_markdown(dedup_md)
    multi, singles = split_groups(report_obj)

    inventory: List[ElementInventoryEntry] = []
    if element_inventory_path:
        inventory_path = Path(element_inventory_path)
        if not inventory_path.is_file():
            raise FileNotFoundError(
                f"LC2_3 element inventory not found: {inventory_path}"
            )
        inventory = inventory_from_json(inventory_path.read_text(encoding="utf-8"))

    log.info(
        "LC2_3 read %d groups (multi=%d, singletons=%d) for %s",
        len(report_obj.groups), len(multi), len(singles), system_name,
    )
    if history is not None:
        history.log("LC2_3_dispatch_start",
                    call_index=_SESSION["call_index"],
                    n_groups=len(report_obj.groups), n_multi=len(multi),
                    n_singletons=len(singles))

    t0 = time.time()

    # ── 1b. Element supervisor instruction + general plan ─────────
    failures: List[Dict[str, Any]] = []
    instruction_res = build_element_instructions(
        purpose=purpose,
        tasks=tasks_text,
        inventory=inventory,
        subagent_dir=call_dir / "element_instruction_supervisor",
        debug=debug,
    )
    element_instructions = instruction_res.get("instructions") or {}
    orchestration_session = instruction_res.get("session")
    instruction_error = instruction_res.get("error")
    if instruction_error or not element_instructions or orchestration_session is None:
        failure = instruction_error or "instruction_gate_not_committed"
        failures.append({"kind": "element_instruction_gate", "error": failure})
        out_card = output_dir / "free_energy_card_deduplicated.md"
        out_card.write_text(card_text, encoding="utf-8")
        failed_report = (
            f"# LC2_3 element orchestration failure (call {_SESSION['call_index']:02d})\n\n"
            "- status: failed\n"
            "- phase: instruction\n"
            "- dedup_started: false\n"
            f"- error: {failure}\n"
            "\nThe instruction commit gate did not pass, so no default dedup "
            "operation or downstream review was run.\n"
        )
        (call_dir / "report.md").write_text(failed_report, encoding="utf-8")
        context_json, context_md = write_agent_context_index(call_dir)
        context_index = json.loads(context_json.read_text(encoding="utf-8"))
        expected_instruction_calls = (
            0 if failure == "empty_element_inventory" else 1
        )
        manifest_payload.update({
            "status": "failed",
            "failure": failure,
            "orchestration_session_id": (
                getattr(orchestration_session, "session_id", None)
            ),
            "agent_context": {
                "index_json": _file_artifact(context_json),
                "index_markdown": _file_artifact(context_md),
                "expected_calls": expected_instruction_calls,
                "documented_calls": context_index["agent_turn_count"],
                "complete": (
                    context_index["agent_turn_count"]
                    == expected_instruction_calls
                    and context_index.get(
                        "all_context_bundles_complete", False
                    )
                ),
            },
            "outputs": {"unchanged_card": _file_artifact(out_card)},
        })
        manifest_path = _write_lc2_3_manifest(call_dir, manifest_payload)
        return {
            "status": "failed",
            "output_dir": str(call_dir),
            "enriched_card_path": str(out_card),
            "dedup_md_path": None,
            "element_table_path": None,
            "manifest_path": str(manifest_path),
            "n_groups": len(report_obj.groups),
            "n_multi_groups": len(multi),
            "n_singletons": len(singles),
            "n_decisions": 0,
            "n_dropped": 0,
            "n_failures": 1,
            "review_turns": 0,
            "full_restarts": 0,
            "stage_done": False,
            "final_committed": False,
            "elapsed_s": round(time.time() - t0, 3),
            "report": failed_report,
        }
    skip_dedup = bool(instruction_res.get("skip_dedup"))
    instruction_snapshot = _write_instruction_snapshot(
        call_dir,
        1,
        element_instructions,
        reason=(
            "initial committed instruction gate"
            + (" — supervisor committed skip_dedup (keep-all)" if skip_dedup else "")
        ),
        case_recommendations=(
            instruction_res.get("case_recommendations") or ""
        ),
    )
    case_recommendations = (
        instruction_res.get("case_recommendations") or ""
    ).strip()
    # Stable alias always reflects the latest generation; versioned files
    # preserve the earlier instructions for audit.
    (call_dir / "element_instructions.md").write_text(
        instruction_snapshot.read_text(encoding="utf-8"), encoding="utf-8",
    )
    manifest_payload["orchestration_session_id"] = (
        orchestration_session.session_id
    )
    manifest_payload["instruction_snapshots"].append(
        _file_artifact(instruction_snapshot)
    )

    # The supervisor is the sole calculation-aware plan author: workers read
    # the static defaults from the user-message plan and the supervisor's
    # case-specific recommendations from their system prompts.  The former
    # purpose-only addendum agent is retired — it saw neither the inventory
    # nor the design questions.
    plan = load_general_plan()
    expected_agent_calls = 1  # element-instruction agent
    total_n_tools = int(instruction_res.get("n_tools", 0))
    total_n_iters = int(instruction_res.get("iterations", 0))
    try:
        (call_dir / "dedup_plan.md").write_text(
            _compose_plan_doc(plan, case_recommendations),
            encoding="utf-8",
        )
    except OSError as exc:                      # pragma: no cover
        log.warning("LC2_3 could not write dedup_plan.md: %s", exc)
    if history is not None:
        history.log("LC2_3_plan_ready",
                    call_index=_SESSION["call_index"],
                    has_case_recommendations=bool(case_recommendations),
                    skip_dedup=skip_dedup)

    # ── 2. Complete dedup pass, then fresh-context supervision ────
    generation = 1
    if skip_dedup:
        dedup_pass = _skip_dedup_pass(
            report_obj=report_obj,
            plan=plan,
            element_instructions=element_instructions,
            case_recommendations=case_recommendations,
            generation_dir=call_dir / f"generation_{generation:02d}",
        )
    else:
        dedup_pass = _run_dedup_pass(
            report_obj=report_obj,
            inventory=inventory,
            plan=plan,
            element_instructions=element_instructions,
            case_recommendations=case_recommendations,
            generation_dir=call_dir / f"generation_{generation:02d}",
            debug=debug,
        )
    expected_agent_calls += int(dedup_pass.get("agent_call_count", 0))
    total_n_tools += int(dedup_pass.get("n_tools", 0))
    total_n_iters += int(dedup_pass.get("iterations", 0))
    manifest_payload["state_transitions"].append({
        "kind": "initial_dedup_generation",
        "generation": generation,
        "skipped_by_supervisor": skip_dedup,
        "generation_manifest": _file_artifact(
            call_dir / f"generation_{generation:02d}" / "generation_manifest.json"
        ),
    })
    failures.extend(dedup_pass["failures"])
    decision_dicts = dedup_pass["decisions"]
    overrides: Dict[str, tuple[bool, str]] = {}
    materialized = materialize_review(
        original_card_text=card_text,
        report=report_obj,
        decision_dicts=decision_dicts,
        overrides=overrides,
        inventory=inventory,
    )
    mark_history: Dict[tuple[str, str], List[Dict[str, str]]] = {}

    def record_generation_marks(generation_number: int) -> None:
        for row in materialized.decision_audit:
            key = (str(row["name"]), str(row["source"]))
            mark_history.setdefault(key, []).append({
                "stage": f"generation {generation_number}",
                "mark": str(row.get("decision", "not examined")),
                "reason": str(row.get("rationale", "")),
            })

    record_generation_marks(generation)
    original_include = card_include_index(card_text)
    latest_diff_rows = selection_diff(
        {
            key: original_include.get(key, True)
            for key in materialized.include_by_key
        },
        materialized.include_by_key,
        inventory,
        reason="initial dedup pass",
    )

    max_restarts = int(getattr(cfg, "LC2_3_MAX_FULL_REDEDUP", 2))
    max_review_turns = int(getattr(
        cfg,
        "LC2_3_MAX_REVIEW_TURNS",
        max(12, 2 * len(element_instructions) + 4),
    ))
    restarts = 0
    targeted_reruns = 0
    review_turns = 0
    stage_done = False
    stage_summary = "Final table not yet committed."
    warning_acknowledgement: Optional[Dict[str, Any]] = None
    supervisor_error: Optional[str] = None

    while inventory and review_turns < max_review_turns and not stage_done:
        review_turns += 1
        review_dir = call_dir / f"review_pass_{review_turns:02d}"
        review_dir.mkdir(parents=True, exist_ok=True)
        post_report = render_post_dedup_report(
            report=report_obj,
            materialized=materialized,
            inventory=inventory,
            generation=generation,
            mark_history=mark_history,
        )
        element_table = render_entries_by_element(
            inventory=inventory,
            materialized=materialized,
            mark_history=mark_history,
        )
        latest_diff = render_diff(latest_diff_rows)
        (review_dir / "deduplication_check_post.md").write_text(
            post_report, encoding="utf-8",
        )
        (review_dir / "deduplicated_entries_by_element.md").write_text(
            element_table, encoding="utf-8",
        )
        (review_dir / "review_diff.md").write_text(latest_diff, encoding="utf-8")
        (review_dir / "review_diff.json").write_text(
            diff_to_json(latest_diff_rows), encoding="utf-8",
        )
        (review_dir / "free_energy_card_deduplicated.md").write_text(
            materialized.card_text, encoding="utf-8",
        )

        warnings = solid_family_warnings(
            inventory=inventory,
            include_by_key=materialized.include_by_key,
            instructions=element_instructions,
            purpose=purpose,
            tasks=tasks_text,
        )
        unexamined_groups: Dict[tuple[str, str], int] = {}
        for row in materialized.decision_audit:
            if row.get("decision") != "not examined":
                continue
            key = (str(row["phase"]), str(row["core_label"]))
            unexamined_groups[key] = unexamined_groups.get(key, 0) + 1
        blocking_errors = [
            "Dedup group "
            f"{phase}::{core} has {count} not-examined entr"
            f"{'y' if count == 1 else 'ies'}; redispatch that target or "
            "restart the full pass before committing."
            for (phase, core), count in sorted(unexamined_groups.items())
        ]
        state_before_sha256 = hashlib.sha256(
            materialized.card_text.encode("utf-8")
        ).hexdigest()
        review_res = run_element_review_phase(
            session=orchestration_session,
            purpose=purpose,
            tasks=tasks_text,
            inventory=inventory,
            post_report=post_report,
            element_table=element_table,
            latest_diff=latest_diff,
            blocking_warnings=warnings,
            blocking_errors=blocking_errors,
            full_restarts_remaining=max_restarts - restarts,
            subagent_dir=review_dir / "supervisor",
            debug=debug,
        )
        expected_agent_calls += 1
        total_n_tools += int(review_res.get("n_tools", 0))
        total_n_iters += int(review_res.get("iterations", 0))
        action = review_res.get("action")
        review_action_path = review_dir / "review_action.json"
        review_action_path.write_text(
            json.dumps({
                "review_turn": review_turns,
                "session_id": orchestration_session.session_id,
                "commit_warnings": warnings,
                "blocking_errors": blocking_errors,
                "accepted_action": action,
                "agent_error": review_res.get("error"),
                "state_before_sha256": state_before_sha256,
            }, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        if not action:
            manifest_payload["state_transitions"].append({
                "kind": "review_without_accepted_action",
                "review_turn": review_turns,
                "action_artifact": _file_artifact(review_action_path),
            })
            supervisor_error = review_res.get("error") or "no_review_action"
            break

        before = dict(materialized.include_by_key)
        if action["kind"] == "set_entry_include":
            overrides[action["entry_key"]] = (
                action["include"], action["reason"],
            )
            materialized = materialize_review(
                original_card_text=card_text,
                report=report_obj,
                decision_dicts=decision_dicts,
                overrides=overrides,
                inventory=inventory,
            )
            entry = next(
                item for item in inventory
                if item.entry_key == action["entry_key"]
            )
            mark_history.setdefault(entry.species_key, []).append({
                "stage": f"review {review_turns}",
                "mark": "kept" if action["include"] else "dropped",
                "reason": action["reason"],
            })
            latest_diff_rows = selection_diff(
                before,
                materialized.include_by_key,
                inventory,
                reason=action["reason"],
            )
            manifest_payload["state_transitions"].append({
                "kind": "direct_entry_override",
                "review_turn": review_turns,
                "action_artifact": _file_artifact(review_action_path),
                "state_before_sha256": state_before_sha256,
                "state_after_sha256": hashlib.sha256(
                    materialized.card_text.encode("utf-8")
                ).hexdigest(),
            })
            continue

        if action["kind"] == "dispatch_target_dedup":
            by_entry_key = {entry.entry_key: entry for entry in inventory}
            target_group_keys = {
                (
                    by_entry_key[entry_key].phase,
                    by_entry_key[entry_key].core_label,
                )
                for entry_key in action["entry_keys"]
            }
            target_report = _subset_report(report_obj, target_group_keys)
            if not target_report.groups:
                supervisor_error = "targeted_redispatch_resolved_no_groups"
                break
            targeted_reruns += 1
            targeted_plan = "\n\n".join(block for block in (
                plan,
                "[Targeted supervisor guidance]\n"
                + action["guidance"]
                + "\n[Reason for redispatch]\n"
                + action["reason"],
            ) if block.strip())
            target_pass = _run_dedup_pass(
                report_obj=target_report,
                inventory=inventory,
                plan=targeted_plan,
                element_instructions=element_instructions,
                case_recommendations=case_recommendations,
                generation_dir=(
                    call_dir / f"targeted_review_{review_turns:02d}"
                ),
                debug=debug,
            )
            expected_agent_calls += int(target_pass.get("agent_call_count", 0))
            total_n_tools += int(target_pass.get("n_tools", 0))
            total_n_iters += int(target_pass.get("iterations", 0))
            failures.extend(target_pass["failures"])
            replacement_keys = {
                (decision["phase"], decision["core_label"])
                for decision in target_pass["decisions"]
            }
            decision_dicts = [
                decision for decision in decision_dicts
                if (decision["phase"], decision["core_label"])
                not in replacement_keys
            ] + target_pass["decisions"]
            materialized = materialize_review(
                original_card_text=card_text,
                report=report_obj,
                decision_dicts=decision_dicts,
                overrides=overrides,
                inventory=inventory,
            )
            latest_diff_rows = selection_diff(
                before,
                materialized.include_by_key,
                inventory,
                reason=f"targeted redispatch: {action['reason']}",
            )
            for row in materialized.decision_audit:
                if (row["phase"], row["core_label"]) not in target_group_keys:
                    continue
                key = (str(row["name"]), str(row["source"]))
                mark_history.setdefault(key, []).append({
                    "stage": f"targeted review {review_turns}",
                    "mark": str(row.get("decision", "not examined")),
                    "reason": str(row.get("rationale", action["reason"])),
                })
            target_manifest_path = (
                call_dir / f"targeted_review_{review_turns:02d}"
                / "target_dispatch.json"
            )
            target_manifest_path.write_text(
                json.dumps({
                    "review_turn": review_turns,
                    "requested_entry_keys": action["entry_keys"],
                    "expanded_group_keys": [
                        {"phase": phase, "core_label": core}
                        for phase, core in sorted(target_group_keys)
                    ],
                    "guidance": action["guidance"],
                    "reason": action["reason"],
                    "generation_manifest": str(
                        target_manifest_path.with_name("generation_manifest.json")
                    ),
                    "state_before_sha256": state_before_sha256,
                    "state_after_sha256": hashlib.sha256(
                        materialized.card_text.encode("utf-8")
                    ).hexdigest(),
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            manifest_payload["state_transitions"].append({
                "kind": "targeted_redispatch",
                "review_turn": review_turns,
                "action_artifact": _file_artifact(review_action_path),
                "target_manifest": _file_artifact(target_manifest_path),
            })
            continue

        if action["kind"] == "redo_all_dedup":
            restarts += 1
            element_instructions.update(action["instructions"])
            orchestration_session.instructions = dict(element_instructions)
            if (action.get("case_recommendations") or "").strip():
                case_recommendations = action["case_recommendations"].strip()
                orchestration_session.case_recommendations = case_recommendations
                if plan:
                    try:
                        (call_dir / "dedup_plan.md").write_text(
                            _compose_plan_doc(plan, case_recommendations),
                            encoding="utf-8",
                        )
                    except OSError as exc:      # pragma: no cover
                        log.warning(
                            "LC2_3 could not rewrite dedup_plan.md: %s", exc,
                        )
            orchestration_session.phase = "dedup"
            overrides = {}
            generation += 1
            instruction_snapshot = _write_instruction_snapshot(
                call_dir,
                generation,
                element_instructions,
                reason=action["reason"],
                case_recommendations=case_recommendations,
            )
            (call_dir / "element_instructions.md").write_text(
                instruction_snapshot.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            manifest_payload["instruction_snapshots"].append(
                _file_artifact(instruction_snapshot)
            )
            dedup_pass = _run_dedup_pass(
                report_obj=report_obj,
                inventory=inventory,
                plan=plan,
                element_instructions=element_instructions,
                case_recommendations=case_recommendations,
                generation_dir=call_dir / f"generation_{generation:02d}",
                debug=debug,
            )
            expected_agent_calls += int(dedup_pass.get("agent_call_count", 0))
            total_n_tools += int(dedup_pass.get("n_tools", 0))
            total_n_iters += int(dedup_pass.get("iterations", 0))
            failures = [
                f for f in failures if f.get("kind") == "element_instruction"
            ] + dedup_pass["failures"]
            decision_dicts = dedup_pass["decisions"]
            materialized = materialize_review(
                original_card_text=card_text,
                report=report_obj,
                decision_dicts=decision_dicts,
                overrides=overrides,
                inventory=inventory,
            )
            record_generation_marks(generation)
            latest_diff_rows = selection_diff(
                before,
                materialized.include_by_key,
                inventory,
                reason=f"full re-deduplication: {action['reason']}",
            )
            manifest_payload["state_transitions"].append({
                "kind": "full_dedup_restart",
                "review_turn": review_turns,
                "generation": generation,
                "action_artifact": _file_artifact(review_action_path),
                "instruction_snapshot": _file_artifact(instruction_snapshot),
                "generation_manifest": _file_artifact(
                    call_dir / f"generation_{generation:02d}"
                    / "generation_manifest.json"
                ),
                "state_before_sha256": state_before_sha256,
                "state_after_sha256": hashlib.sha256(
                    materialized.card_text.encode("utf-8")
                ).hexdigest(),
            })
            continue

        if action["kind"] == "commit_final":
            orchestration_session.closed = True
            orchestration_session.phase = "closed"
            stage_done = True
            stage_summary = action["summary"]
            if action.get("confirmed_warnings"):
                warning_acknowledgement = {
                    "flags": action.get("confirmed_warnings", []),
                    "rationale": action.get("warning_rationale", ""),
                }
            manifest_payload["state_transitions"].append({
                "kind": "final_commit",
                "review_turn": review_turns,
                "action_artifact": _file_artifact(review_action_path),
                "confirmed_flags": action.get("confirmed_warnings", []),
                "warning_rationale": action.get("warning_rationale", ""),
                "state_sha256": state_before_sha256,
            })

    if inventory and not stage_done and supervisor_error is None:
        supervisor_error = (
            f"review turn limit reached ({max_review_turns}) without stage_done"
        )
    if supervisor_error:
        failures.append({"kind": "element_review", "error": supervisor_error})

    new_card_text = materialized.card_text
    out_card = output_dir / "free_energy_card_deduplicated.md"
    out_card.write_text(new_card_text, encoding="utf-8")
    edit_audit = [edit for edit in materialized.edit_audit if not edit.new_include]
    n_dropped = len(edit_audit)

    final_post_report = render_post_dedup_report(
        report=report_obj,
        materialized=materialized,
        inventory=inventory,
        generation=generation,
        mark_history=mark_history,
    )
    final_element_table = render_entries_by_element(
        inventory=inventory,
        materialized=materialized,
        mark_history=mark_history,
    )
    final_post_path = output_dir / "deduplication_check_post.md"
    final_table_path = output_dir / "deduplicated_entries_by_element.md"
    final_diff_path = output_dir / "review_diff.md"
    final_diff_json_path = output_dir / "review_diff.json"
    final_history_path = output_dir / "dedup_mark_history.md"
    final_post_path.write_text(final_post_report, encoding="utf-8")
    final_table_path.write_text(final_element_table, encoding="utf-8")
    final_diff_path.write_text(render_diff(latest_diff_rows), encoding="utf-8")
    final_diff_json_path.write_text(
        diff_to_json(latest_diff_rows), encoding="utf-8",
    )
    final_history_path.write_text(
        render_mark_history(inventory=inventory, mark_history=mark_history),
        encoding="utf-8",
    )

    context_index_json, context_index_md = write_agent_context_index(call_dir)
    context_index = json.loads(
        context_index_json.read_text(encoding="utf-8")
    )
    context_complete = (
        context_index["agent_turn_count"] == expected_agent_calls
        and context_index.get("all_context_bundles_complete", False)
    )
    if not context_complete:
        failures.append({
            "kind": "agent_context_audit",
            "error": (
                f"documented {context_index['agent_turn_count']} of "
                f"{expected_agent_calls} expected LC2_3 agent turns"
            ),
        })
    final_status = (
        "failed" if not stage_done or not context_complete
        else "ok" if not failures
        else "ok_with_failures"
    )
    manifest_payload.update({
        "status": final_status,
        "limits": {
            "max_tool_iterations_per_turn": cfg.MAX_TOOL_ITERATIONS,
            "max_turn_seconds": cfg.MAX_TURN_SECONDS,
            "max_review_turns": max_review_turns,
            "max_full_restarts": max_restarts,
        },
        "counts": {
            "groups": len(report_obj.groups),
            "multi_groups": len(multi),
            "singleton_groups": len(singles),
            "decisions": len(decision_dicts),
            "dropped": n_dropped,
            "review_turns": review_turns,
            "full_restarts": restarts,
            "targeted_reruns": targeted_reruns,
            "failures": len(failures),
            "agent_iterations": total_n_iters,
            "agent_tool_calls": total_n_tools,
        },
        "commit": {
            "completed": stage_done,
            "summary": stage_summary,
            "flag_acknowledgement": warning_acknowledgement,
        },
        "failures": failures,
        "agent_context": {
            "index_json": _file_artifact(context_index_json),
            "index_markdown": _file_artifact(context_index_md),
            "expected_calls": expected_agent_calls,
            "documented_calls": context_index["agent_turn_count"],
            "complete": context_complete,
        },
        "outputs": {
            "deduplicated_card": _file_artifact(out_card),
            "post_dedup_report": _file_artifact(final_post_path),
            "element_table": _file_artifact(final_table_path),
            "latest_diff_markdown": _file_artifact(final_diff_path),
            "latest_diff_json": _file_artifact(final_diff_json_path),
            "dedup_mark_history": _file_artifact(final_history_path),
            "latest_element_instructions": _file_artifact(
                call_dir / "element_instructions.md"
            ),
        },
    })
    manifest_path = _write_lc2_3_manifest(call_dir, manifest_payload)

    # ── 6. Audit report (human-readable; no JSON sidecars) ────────
    elapsed = time.time() - t0
    elapsed_llm = time.time() - t0
    n_tool_calls = total_n_tools
    n_iters = total_n_iters

    report = _render_report(
        call_index=_SESSION["call_index"],
        out_card=out_card, merged_card_path=merged_card_path,
        report_obj=report_obj, multi=multi, singles=singles,
        decisions=decision_dicts, edit_audit=edit_audit, failures=failures,
        elapsed_llm=elapsed_llm, elapsed=elapsed,
        n_iters=n_iters, n_tool_calls=n_tool_calls,
    )
    report += (
        "\n## Element-level supervisory review\n\n"
        f"- final_committed: {str(stage_done).lower()}\n"
        f"- orchestration_session_id: {orchestration_session.session_id}\n"
        f"- review_turns: {review_turns}\n"
        f"- full_restarts: {restarts}\n"
        f"- targeted_reruns: {targeted_reruns}\n"
        f"- summary: {stage_summary}\n"
        f"- commit_flag_acknowledgement: "
        f"{json.dumps(warning_acknowledgement, ensure_ascii=False) if warning_acknowledgement else 'none'}\n"
        f"- run_manifest: `{manifest_path}`\n"
        f"- agent_context_index: `{context_index_md}`\n"
        f"- agent_context_complete: "
        f"{str(context_complete).lower()} "
        f"({context_index['agent_turn_count']}/{expected_agent_calls})\n"
        f"- post_dedup_report: `{final_post_path}`\n"
        f"- element_table: `{final_table_path}`\n"
        f"- latest_diff: `{final_diff_path}`\n"
        f"- mark_history: `{final_history_path}`\n"
    )
    report_path = call_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    manifest_payload["elapsed_s"] = round(elapsed, 3)
    manifest_payload["outputs"]["human_report"] = _file_artifact(report_path)
    _write_lc2_3_manifest(call_dir, manifest_payload)

    if stats is not None:
        stats.incr("LC2_3", "dispatch_calls", 1)
        stats.incr("LC2_3", "groups",     len(report_obj.groups))
        stats.incr("LC2_3", "multi",      len(multi))
        stats.incr("LC2_3", "singletons", len(singles))
        stats.incr("LC2_3", "decisions",  len(decision_dicts))
        stats.incr("LC2_3", "dropped",    n_dropped)
        stats.incr("LC2_3", "failures",   len(failures))
        stats.incr("LC2_3", "llm_iterations", n_iters)
        stats.incr("LC2_3", "tool_calls",     n_tool_calls)

    if _SESSION["working_memory"] is not None:
        try:
            _SESSION["working_memory"].set("enriched_card_path", str(out_card))
        except Exception as exc:                # pragma: no cover
            log.warning("working_memory.set failed: %s", exc)

    if history is not None:
        history.log("LC2_3_dispatch_end",
                    call_index=_SESSION["call_index"],
                    elapsed_s=elapsed,
                    n_groups=len(report_obj.groups),
                    n_decisions=len(decision_dicts),
                    n_dropped=n_dropped, n_failures=len(failures))

    return {
        "status":             final_status,
        "output_dir":         str(call_dir),
        "enriched_card_path": str(out_card),
        "dedup_md_path":      str(final_post_path),
        "element_table_path": str(final_table_path),
        "manifest_path":      str(manifest_path),
        "agent_context_index_path": str(context_index_json),
        "agent_context_complete": context_complete,
        "n_groups":           len(report_obj.groups),
        "n_multi_groups":     len(multi),
        "n_singletons":       len(singles),
        "n_decisions":        len(decision_dicts),
        "n_dropped":          n_dropped,
        "n_failures":         len(failures),
        "review_turns":       review_turns,
        "full_restarts":      restarts,
        "targeted_reruns":    targeted_reruns,
        "stage_done":         stage_done,
        "final_committed":    stage_done,
        "commit_flag_acknowledgement": warning_acknowledgement,
        "orchestration_session_id": orchestration_session.session_id,
        "elapsed_s":          round(elapsed, 3),
        "report":             report,
    }


# ════════════════════════════════════════════════════════════════════
#  Report rendering
# ════════════════════════════════════════════════════════════════════

def _render_report(
    *,
    call_index: int,
    out_card: Path,
    merged_card_path: Path,
    report_obj: DedupReport,
    multi: List[DedupGroup],
    singles: List[DedupGroup],
    decisions: List[Dict[str, Any]],
    edit_audit: List[Any],
    failures: List[Dict[str, Any]],
    elapsed_llm: float,
    elapsed: float,
    n_iters: int,
    n_tool_calls: int,
) -> str:
    multi_keys = {(g.phase, g.core_label) for g in multi}
    single_keys = {(g.phase, g.core_label) for g in singles}

    lines = [
        f"# LC2_3 dispatch report (call {call_index:02d})",
        "",
        f"- merged_card:        `{merged_card_path}`",
        f"- deduplicated_card:  `{out_card}`",
        f"- elapsed_s (llm):    {elapsed_llm:.2f}",
        f"- elapsed_s (total):  {elapsed:.2f}",
        f"- llm_iterations:     {n_iters}",
        f"- llm_tool_calls:     {n_tool_calls}",
        "",
        f"- n_groups:           {len(report_obj.groups)}",
        f"- n_multi_groups:     {len(multi)}",
        f"- n_singletons:       {len(singles)}",
        f"- n_decisions:        {len(decisions)}",
        f"- n_dropped:          {len(edit_audit)}",
        f"- n_failures:         {len(failures)}",
        "",
        "## Multi-member group verdicts",
        "",
        "| phase | core_label | keep_species | rationale |",
        "|-------|------------|------------|-----------|",
    ]
    for d in decisions:
        if (d["phase"], d["core_label"]) in multi_keys:
            kept = d.get("keep_species")
            if kept is None:  # legacy, unambiguous decisions only
                kept_text = ", ".join(f"`{n}`" for n in d.get("keep_names", []))
            else:
                kept_text = ", ".join(
                    f"`{s['name']}` [{s['source']}]" for s in kept
                )
            lines.append(
                f"| {d['phase']} | `{d['core_label']}` "
                f"| {kept_text} "
                f"| {d['rationale']} |"
            )
    lines += [
        "",
        "## Singleton verdicts",
        "",
        "| phase | core_label | kept | rationale |",
        "|-------|------------|------|-----------|",
    ]
    for d in decisions:
        if (d["phase"], d["core_label"]) in single_keys:
            kept = d.get("keep_species")
            if kept is None:  # legacy, unambiguous decisions only
                kept = d.get("keep_names", [])
            lines.append(
                f"| {d['phase']} | `{d['core_label']}` "
                f"| {'yes' if kept else 'NO'} "
                f"| {d['rationale']} |"
            )
    lines += [
        "",
        "## Dropped species (include → false)",
        "",
        "| label | source | phase | note |",
        "|-------|--------|-------|------|",
    ]
    for e in edit_audit:
        lines.append(f"| `{e.label}` | {e.source} | {e.phase} | {e.note} |")
    if failures:
        lines += ["", "## Failures", ""]
        for f in failures:
            lines.append(f"- {f}")
    return "\n".join(lines) + "\n"


__all__ = ["configure_lc2_3_session", "run_lc2_3"]
