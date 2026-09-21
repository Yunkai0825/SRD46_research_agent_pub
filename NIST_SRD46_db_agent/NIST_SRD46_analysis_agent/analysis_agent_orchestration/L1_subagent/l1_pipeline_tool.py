"""The idempotent LC1→LC2→LC3 build-and-solve tool used by L1."""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ....general_db_query_engine.general_checkpointing import atomic_write_json

from .l1_artifacts import (
    _build_reference_constants_artifact,
    _collect_default_verdicts,
    _render_pipeline_result,
)
from .l1_estimation_audit import _build_model_coverage, _build_topology_summary
from .l1_state import _L1State, _rel_to_session, _stat_incr, _wm_append


log = logging.getLogger("Analysis.L1")


def _failed_stage(built: Optional[Dict[str, Any]]) -> str:
    """Best-effort identify which LC layer failed for the status object."""

    if not isinstance(built, dict):
        return "unknown"
    lc3 = built.get("lc3")
    if isinstance(lc3, dict) and lc3.get("status") not in ("ok", None):
        for stage in ("lc3_4", "lc3_3", "lc3_2", "lc3_1"):
            info = lc3.get(stage)
            if isinstance(info, dict) and info.get("status") not in ("ok", None):
                return stage.upper()
        nested_error = str(lc3.get("_error") or "")
        nested_match = re.search(r"\b(LC3_[1-4])\b", nested_error)
        if nested_match:
            return nested_match.group(1)
    for layer in ("lc3", "lc2", "lc1"):
        info = built.get(layer)
        if isinstance(info, dict) and info.get("status") not in ("ok", None):
            return layer.upper()
    error = str(built.get("_error") or "")
    match = re.search(r"\b(LC1|LC2|LC3)\b", error)
    return match.group(1) if match else "build"


def _persist_pipeline_status(
    state: _L1State,
    status: Dict[str, Any],
) -> None:
    """Persist one deterministic L1 execution outcome for the L0 gate.

    Scientific review and numerical execution are deliberately separate: LD
    may support an honest failure report, but L0 must still know that the
    requested calculation did not complete.  Keep a per-call sidecar for
    interrupted/debug consumers and mirror the same row into working memory
    for normal same-run aggregation.
    """

    payload = {
        "call": state.idx,
        "call_dir": _rel_to_session(state.call_dir),
        "purpose": state.purpose,
        **dict(status),
    }
    state.pipeline_status = dict(status)
    try:
        atomic_write_json(
            Path(state.call_dir) / "pipeline_status.json",
            payload,
        )
    except Exception:  # pragma: no cover - status still reaches memory
        log.warning(
            "L1[%d] could not persist pipeline_status.json",
            state.idx,
            exc_info=state.debug,
        )
    _wm_append("l1_pipeline_runs", payload)
    _stat_incr(
        "run",
        "ok" if str(status.get("status") or "").lower() == "ok" else "failed",
    )


def make_run_pipeline(
    state: _L1State,
    *,
    run_pipeline_func: Callable[..., Dict[str, Any]],
    estimation_tool_description_path: Path,
) -> Callable[..., str]:
    """Create the build-and-solve tool with its solver dependency injected."""

    def run_analysis_pipeline(notes: str = "") -> str:
        """Build and solve the system described by this call's purpose/tasks.

        Runs the full LC1→LC2→LC3 card-building chain and the numeric
        solver in one shot. Never raises: a build/solve failure is
        returned as ``{"status": "failed", "error": ...}`` so you can
        report it honestly. On success, the status is followed by the full,
        untruncated text of every solver-written ``*_verdict.md`` artifact.
        This verdict text is evidence already supplied to your context and
        does not require a separate read-tool call.

        Args:
            notes: Optional one-line refinement recorded in the audit
                trail. Does not change the chemistry (fixed by the brief).

        Returns:
            Status plus complete deterministic verdict text. Raw topology
            JSON is never embedded in this automatic result.
        """

        if state.ran_ok and state.pipeline_status is not None:
            return _render_pipeline_result(
                state,
                state.pipeline_status,
                already_ran=True,
            )

        if notes:
            log.info(
                "L1[%d] run_analysis_pipeline notes=%s",
                state.idx,
                notes[:200],
            )

        started = time.time()
        try:
            if state.estimate_missing_equilibria:
                built = run_pipeline_func(
                    state.purpose,
                    state.tasks_text,
                    output_dir=state.call_dir,
                    run_solver=True,
                    debug=state.debug,
                    estimate_missing_equilibria=True,
                )
            elif state.forward_explicit_estimation_disable:
                built = run_pipeline_func(
                    state.purpose,
                    state.tasks_text,
                    output_dir=state.call_dir,
                    run_solver=True,
                    debug=state.debug,
                    estimate_missing_equilibria=False,
                )
            else:
                built = run_pipeline_func(
                    state.purpose,
                    state.tasks_text,
                    output_dir=state.call_dir,
                    run_solver=True,
                    debug=state.debug,
                )
        except Exception as exc:  # pragma: no cover - pipeline guards internally
            elapsed = time.time() - started
            status = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "stage": "pipeline_exception",
                "elapsed_s": round(elapsed, 1),
            }
            _persist_pipeline_status(state, status)
            log.error(
                "L1[%d] pipeline raised: %s",
                state.idx,
                exc,
                exc_info=state.debug,
            )
            return json.dumps(status, indent=2, default=str)

        elapsed = time.time() - started
        build_status = (built or {}).get("status")
        solver = (built or {}).get("solver") or {}

        if build_status != "ok" or not solver:
            status = {
                "status": "failed",
                "error": (
                    (built or {}).get("_error")
                    or "card build failed before the solver ran"
                ),
                "stage": _failed_stage(built),
                "elapsed_s": round(elapsed, 1),
            }
            _persist_pipeline_status(state, status)
            return json.dumps(status, indent=2, default=str)

        solver_dir = Path(state.call_dir) / "solver"
        state.solver_dir = solver_dir
        output_paths = [
            Path(path) for path in (solver.get("output_paths") or [])
        ]
        relative_files = [_rel_to_session(path) for path in output_paths]
        state.default_verdicts = _collect_default_verdicts(output_paths)
        free_energy_card_value = (built or {}).get("free_energy_card_path")
        if not free_energy_card_value:
            free_energy_card_value = ((built or {}).get("lc2") or {}).get(
                "final_card_path"
            )
        state.default_reference_constants = (
            _build_reference_constants_artifact(
                state,
                Path(str(free_energy_card_value)),
            )
            if free_energy_card_value
            else None
        )

        status = {
            "status": "ok",
            "error": None,
            "sweep_method": solver.get("sweep_method", ""),
            "output_dir": _rel_to_session(solver_dir),
            "n_output_files": len(output_paths),
            "output_files": relative_files,
            "elapsed_s": round(elapsed, 1),
        }
        missing_pairs = (
            ((built or {}).get("lc1") or {}).get("coverage") or {}
        ).get("missing_pairs") or []
        if missing_pairs:
            status["database_coverage_gaps"] = {
                "missing_metal_ligand_pairs": [
                    f"{pair[0]} x {pair[1]}" for pair in missing_pairs
                ],
                "note": (
                    "SRD-46 holds no complexes for these pairs, so they are "
                    "absent from the model by construction. Report their "
                    "absence as missing data, never as a computed result."
                ),
            }
        if state.estimate_missing_equilibria:
            calc_path_value = (built or {}).get("calc_input_card_path")
            state.calc_input_card_path = (
                Path(calc_path_value) if calc_path_value else None
            )
            state.model_coverage = _build_model_coverage(
                built or {}, call_dir=state.call_dir
            )
            state.topology_summary = _build_topology_summary(
                state.solver_dir, call_dir=state.call_dir
            )
            status["model_coverage"] = state.model_coverage
            status["topology_summary"] = state.topology_summary
            lc1 = (built or {}).get("lc1") or {}
            lc1_3 = lc1.get("lc1_3") or {}
            lc2 = (built or {}).get("lc2") or {}
            lc2_1 = lc2.get("lc2_1") or {}
            support_path = lc1_3.get("support_eq_map_path")
            candidate_count = int(lc2_1.get("support_candidate_count") or 0)
            selected_count = int(
                lc2_1.get("selected_support_node_count") or 0
            )
            materialized_count = int(
                lc2_1.get("materialized_estimated_entry_count") or 0
            )
            estimated_stability_constants = (
                list(lc1_3.get("estimated_stability_constants") or [])
                if support_path
                else []
            )
            lc1_3_status = str(lc1_3.get("status") or "unknown")
            search_complete_value = lc1_3.get("estimation_search_complete")
            estimation_search_complete = (
                search_complete_value
                if isinstance(search_complete_value, bool)
                else lc1_3_status not in {
                    "reference_only", "failed", "unknown",
                }
            )
            interpretation_guard = (
                "The enabled estimation search completed for every required "
                "scope."
                if estimation_search_complete
                else (
                    "The enabled estimation search was incomplete and all "
                    "estimated support was withheld. The reference-only "
                    "solver result must not be described as an ordinary "
                    "no-estimation finding or as evidence that the missing "
                    "chemical pairs have no relevant equilibria."
                )
            )
            status["estimated_equilibrium_enrichment"] = {
                "status": lc1_3_status,
                "estimation_search_complete": estimation_search_complete,
                "estimation_search_status": (
                    "complete" if estimation_search_complete else "incomplete"
                ),
                "reference_only_reason": lc1_3.get("reference_only_reason"),
                "failure_summary": lc1_3.get("failure_summary"),
                "interpretation_guard": interpretation_guard,
                "source": (
                    lc1_3.get("source") or "SRD46 query estimated values"
                ),
                "estimates_generated": bool(support_path),
                "support_candidate_count": candidate_count,
                "selected_support_node_count": selected_count,
                "materialized_estimated_entry_count": materialized_count,
                "estimated_values_used": materialized_count > 0,
                "estimated_stability_constants": estimated_stability_constants,
                "support_eq_map_path": (
                    _rel_to_session(Path(support_path))
                    if support_path else None
                ),
                "manifest_path": (
                    _rel_to_session(Path(lc1_3["manifest_path"]))
                    if lc1_3.get("manifest_path") else None
                ),
            }
        state.ran_ok = True
        _persist_pipeline_status(state, status)
        return _render_pipeline_result(state, status)

    if state.estimate_missing_equilibria:
        run_analysis_pipeline.__doc__ = (
            (run_analysis_pipeline.__doc__ or "").rstrip()
            + "\n\n"
            + estimation_tool_description_path.read_text(
                encoding="utf-8"
            ).strip()
        )

    return run_analysis_pipeline


__all__ = ["make_run_pipeline"]
