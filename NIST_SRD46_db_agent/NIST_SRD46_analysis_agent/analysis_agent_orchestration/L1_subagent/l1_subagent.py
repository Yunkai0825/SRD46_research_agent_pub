"""L1 analysis-agent orchestration and public API.

The L0 orchestrator delegates one chemical-system brief to
:func:`dispatch_l1_pipeline`. One ReAct agent builds and solves the system,
receives complete deterministic ``*_verdict.md`` evidence by default, uses
narrow artifact-inspection tools when necessary, and commits a report for the
optional LD validation gate.

Implementation responsibilities are split across sibling modules:

* :mod:`l1_state` owns process/session and per-call state;
* :mod:`l1_artifacts` owns verdict delivery and evidence-reading tools;
* :mod:`l1_pipeline_tool` owns the idempotent build-and-solve tool;
* :mod:`l1_estimation_audit` owns deterministic enabled-run guards; and
* :mod:`l1_persistence` owns agent/tool transcripts and hard-stop recovery.

This facade intentionally retains the public entry points and the small set of
private compatibility names used by tests and runtime monkey-patchers.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ....general_db_query_engine.general_argo_engine_helpers import (
    AgentTurnResult,
    ArgoPromptTooLargeError,
    agent_turn,
)
from ....general_db_query_engine.general_checkpointing import (
    atomic_write_json,
    atomic_write_text,
    file_sha256,
)
from ....general_db_query_engine.general_subagent_skill_schema_and_parser import (
    parse_workflow,
)
from ....general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from ...analysis_agent_argo_engine.argo_client import SRD46AnalysisClient
from ...analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from ...NIST_SRD46_calc_input_building_agentic_pipeline.SRD46_calc_input_building_api import (
    run_pipeline,
)
from ...SRD46_analysis_argo_config import (
    AGENT_CONFIG as cfg,
    resolve_estimate_missing_equilibria,
)
# Compatibility imports keep the former monolithic module's diagnostic and
# test-facing private names available while their implementations live in the
# cohesive sibling modules below.
from .l1_artifacts import (
    _READ_DEFAULT_MAX_CHARS,
    _READ_HARD_MAX_CHARS,
    _VERDICT_FALLBACK_HEAD_CHARS,
    _VERDICT_FALLBACK_TAIL_CHARS,
    _api_error_fallback_text,
    _build_reference_constants_artifact,
    _collect_default_verdicts,
    _list_solver_files,
    _make_inspect_topology_feature,
    _make_inspect_verdict_section,
    _make_list_outputs,
    _make_read_output_file,
    _render_pipeline_result,
    _resolve_call_file,
    _verdict_sidecar_candidates,
    _walk_records_with_id,
)
from .l1_estimation_audit import (
    _build_model_coverage,
    _build_topology_summary,
    _chemical_system,
    _is_water_ligand,
    _ligand_descriptor,
    _make_append_analysis_chunk,
    _make_record_analysis,
    _name_keys,
    _persist_enabled_quality,
    _read_json_object,
    _same_ligand,
)
from .l1_method_skills import (
    infer_sweep_methods,
    render_method_briefing,
)
from .l1_persistence import (
    _recover_enabled_hard_stop_record_analysis as _recover_hard_stop_impl,
    _write_agent_response,
    _write_tool_history,
)
from .l1_pipeline_tool import (
    _failed_stage,
    make_run_pipeline as _make_run_pipeline_impl,
)
from .l1_state import (
    _L1State,
    _SESSION,
    _build_user_message,
    _clean_tasks,
    _per_call_dir,
    _rel_to_call,
    _rel_to_session,
    _stat_incr,
    _wm_append,
    configure_session as _configure_session,
)


log = logging.getLogger("Analysis.L1")

_HERE = Path(__file__).absolute().parent
_WORKFLOW_PATH = _HERE / "L1_subagent_workflow.md"
_ESTIMATION_STATUS_PROMPT_PATH = _HERE / "estimated_equilibrium_status_prompt.md"
_ESTIMATION_TOOL_DESCRIPTION_PATH = (
    _HERE / "estimated_equilibrium_tool_description.md"
)

_PIPELINE_TOOL = "run_analysis_pipeline"
_APPEND_REPORT_TOOL = "append_analysis_chunk"
_RECORD_TOOL = "record_analysis"

# Complete verdict text reaches Argo first; only an explicit prompt-size
# rejection may activate the deterministic fallback.
_L1_COMPACTION_TRIGGER_CHARS = 2_147_483_647


def configure_l1_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
) -> None:
    """Bind the per-session side-channel (called once by the L0 layer)."""

    _configure_session(
        session_dir=session_dir,
        history=history,
        stats=stats,
        working_memory=working_memory,
        debug=debug,
        estimate_missing_equilibria=estimate_missing_equilibria,
        resolved_estimation_default=resolve_estimate_missing_equilibria(),
    )


def _make_run_pipeline(state: _L1State) -> Callable[..., str]:
    """Resolve the patchable solver dependency at factory-call time."""

    return _make_run_pipeline_impl(
        state,
        run_pipeline_func=run_pipeline,
        estimation_tool_description_path=_ESTIMATION_TOOL_DESCRIPTION_PATH,
    )


def _recover_enabled_hard_stop_record_analysis(
    state: _L1State,
    result: AgentTurnResult,
) -> bool:
    """Compatibility facade for narrow terminal-tool recovery."""

    return _recover_hard_stop_impl(
        state,
        result,
        record_tool_name=_RECORD_TOOL,
        record_analysis_factory=_make_record_analysis,
    )


def _build_l1_system_prompt(state: _L1State) -> str:
    """Return the legacy prompt plus enabled-only and per-method blocks."""

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    if state.estimate_missing_equilibria:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n"
            + _ESTIMATION_STATUS_PROMPT_PATH.read_text(encoding="utf-8").strip()
        )
    inferred = infer_sweep_methods(f"{state.purpose}\n{state.tasks_text}")
    if len(inferred) == 1:
        briefing = render_method_briefing(inferred[0])
        if briefing is not None:
            system_prompt = system_prompt.rstrip() + "\n\n" + briefing
            if inferred[0] not in state.briefed_methods:
                state.briefed_methods.append(inferred[0])
    return system_prompt


def _run_l1_agent(
    state: _L1State,
    *,
    hint: str = "",
    attempt: int = 1,
    _allow_verdict_api_retry: bool = True,
) -> Optional[AgentTurnResult]:
    """Run one L1 ReAct turn without rerunning a successful solver call."""

    system_prompt = _build_l1_system_prompt(state)
    tools: Dict[str, Callable[..., str]] = {
        _PIPELINE_TOOL: _make_run_pipeline(state),
        "list_outputs": _make_list_outputs(state),
        "read_output_file": _make_read_output_file(state),
        "inspect_verdict_section": _make_inspect_verdict_section(state),
        "inspect_topology_feature": _make_inspect_topology_feature(state),
        _APPEND_REPORT_TOOL: _make_append_analysis_chunk(state),
        _RECORD_TOOL: _make_record_analysis(state),
    }
    system_prompt += "\n\n" + build_tool_instructions(tools)

    user_message = _build_user_message(state.purpose, state.tasks_text, hint=hint)
    client = SRD46AnalysisClient.for_l1()
    engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "",
        guidance_hooks=[],
    )

    result: Optional[AgentTurnResult] = None
    try:
        result = agent_turn(
            user_message,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=cfg.L1_MAX_ITERATIONS,
            timeout=cfg.L1_MAX_SECONDS,
            compaction_trigger_chars=_L1_COMPACTION_TRIGGER_CHARS,
            required_tools={_RECORD_TOOL},
            terminal_tools={_RECORD_TOOL},
            hooks=engine_agent_hooks.engine_hooks,
            is_subagent=True,
            untimed_tools={_PIPELINE_TOOL},
            uncompacted_tools={_PIPELINE_TOOL},
        )
    except ArgoPromptTooLargeError as exc:
        may_retry = (
            _allow_verdict_api_retry
            and state.ran_ok
            and bool(state.default_verdicts)
            and state.verdict_delivery_mode == "full"
            and not state.verdict_api_retry_used
            and not state.agent_committed_report
        )
        if may_retry:
            state.verdict_api_retry_used = True
            state.verdict_delivery_mode = "api_error_fallback"
            state.verdict_api_retry_error = str(exc)
            log.warning(
                "L1[%d] Argo rejected the full verdict prompt; starting one "
                "cached-pipeline retry with only the verdict delivery reduced: %s",
                state.idx,
                exc,
            )
            history = _SESSION.get("history")
            if history is not None:
                try:
                    history.log(
                        "L1_verdict_api_size_retry",
                        call=state.idx,
                        attempt=attempt,
                        status_code=exc.status_code,
                        full_verdict_chars=sum(
                            len(text) for _path, text in state.default_verdicts
                        ),
                    )
                except Exception:  # pragma: no cover
                    pass
            retry_note = (
                "  - Argo rejected the prior request specifically because the "
                "complete solver verdict made the prompt too large. Call "
                "run_analysis_pipeline once; it is cached and will not rerun "
                "the solver. Its verdict block is now the sole truncated "
                "artifact. Use inspect_verdict_section for any omitted section."
            )
            combined_hint = "\n".join(
                item for item in (hint.strip(), retry_note) if item
            )
            return _run_l1_agent(
                state,
                hint=combined_hint,
                attempt=attempt,
                _allow_verdict_api_retry=False,
            )
        log.error(
            "L1[%d] Argo prompt-size error was not eligible for a verdict "
            "fallback retry: %s",
            state.idx,
            exc,
            exc_info=state.debug,
        )
        return None
    except Exception as exc:  # pragma: no cover
        log.error(
            "L1[%d] agent_turn raised: %s",
            state.idx,
            exc,
            exc_info=state.debug,
        )
        return None

    if result is not None:
        _recover_enabled_hard_stop_record_analysis(state, result)
        _write_tool_history(state.call_dir, list(result.tool_history), attempt)
        _write_agent_response(state.call_dir, result, attempt)
    return result


def _validate_with_ld(
    state: _L1State,
    report: str,
    attempt: int,
) -> Optional[Dict[str, Any]]:
    """Run the optional LD validator; unavailable validation is a pass."""

    if not getattr(cfg, "LD_VALIDATOR_ENABLED", False):
        return None
    try:
        from ..LD_validator import validate as ld_validate
    except Exception as exc:  # pragma: no cover - LD is optional
        log.warning("L1[%d] LD validator unavailable: %s", state.idx, exc)
        return None
    try:
        if state.estimate_missing_equilibria:
            return ld_validate(
                purpose=state.purpose,
                tasks=state.tasks_text,
                report=report,
                call_dir=state.call_dir,
                solver_dir=state.solver_dir,
                attempt=attempt,
                debug=state.debug,
                estimation_enabled=True,
                enabled_run_facts={
                    "model_coverage": state.model_coverage,
                    "topology_summary": state.topology_summary,
                    "estimated_equilibrium_enrichment": (
                        (state.pipeline_status or {}).get(
                            "estimated_equilibrium_enrichment"
                        )
                    ),
                },
            )
        return ld_validate(
            purpose=state.purpose,
            tasks=state.tasks_text,
            report=report,
            call_dir=state.call_dir,
            solver_dir=state.solver_dir,
            attempt=attempt,
            debug=state.debug,
        )
    except Exception as exc:  # pragma: no cover
        log.warning("L1[%d] LD validator raised: %s", state.idx, exc)
        return None


def _append_validation_handoff(
    report: str,
    verdict: Optional[Dict[str, Any]],
) -> str:
    """Expose unresolved LD findings to the downstream L0 synthesizer."""

    if not isinstance(verdict, dict):
        return report
    status = str(verdict.get("verdict") or "inconclusive").strip().lower()
    hints = [str(item).strip() for item in (verdict.get("hints") or []) if str(item).strip()]
    if status == "supported" and not hints:
        return report
    heading = "## LD validation handoff"
    if heading in report:
        return report
    rows = [
        heading,
        "",
        f"- Verdict: `{status}`",
        "- Downstream status: these findings remain visible to synthesis; "
        "they are not silently converted into solver evidence.",
    ]
    if verdict.get("timed_out"):
        rows.append("- The LD review timed out before a complete terminal review.")
    if hints:
        rows.extend(["- Validator recommendations:", *[f"  - {hint}" for hint in hints]])
    else:
        rows.append("- No detailed validator recommendation was committed.")
    return report.rstrip() + "\n\n" + "\n".join(rows) + "\n"


def _missing_l1_terminal_commit_report() -> str:
    """Return the only report accepted when L1 missed its terminal commit.

    ``AgentTurnResult.answer`` is an engine-level hard-stop/diagnostic channel,
    not a durable scientific commit.  In particular, it may be cut off at the
    model output limit.  Never promote that text to ``l1_report.md``.
    """

    return (
        "## Doability\n"
        "Incomplete — the L1 analysis agent did not commit a report through "
        "the required `record_analysis` terminal tool.\n\n"
        "## Result\n"
        "No uncommitted or hard-stop answer text was accepted as scientific "
        "analysis. The deterministic solver artifacts, if present, remain "
        "available for inspection, but this L1 call must be retried before "
        "its interpretation can be validated or synthesized."
    )


def _persist_l1_report_status(
    state: _L1State,
    *,
    agent_turn_timed_out: bool,
) -> Dict[str, Any]:
    """Persist the terminal-report gate independently of the LD verdict."""

    committed = bool(state.agent_committed_report)
    report_path = state.call_dir / "l1_report.md"
    status: Dict[str, Any] = {
        "schema_version": "l1_report_status.v2",
        "call": state.idx,
        "call_dir": _rel_to_session(state.call_dir),
        "status": "complete" if committed else "incomplete",
        "l1_report_committed": committed,
        "agent_turn_timed_out": bool(agent_turn_timed_out),
        "reason": None if committed else "missing_l1_terminal_commit",
        "report_path": _rel_to_session(report_path),
        "report_sha256": (
            file_sha256(report_path) if committed and report_path.is_file()
            else None
        ),
    }
    try:
        atomic_write_json(
            state.call_dir / "l1_report_status.json",
            status,
        )
    except Exception:  # pragma: no cover - status still reaches working memory
        pass
    return status


def _load_completed_l1_report(call_dir: Path) -> Optional[str]:
    """Return a crash-safe prior terminal report for the exact call brief."""

    report_path = call_dir / "l1_report.md"
    report_status_path = call_dir / "l1_report_status.json"
    pipeline_status_path = call_dir / "pipeline_status.json"
    if not (
        report_path.is_file()
        and report_status_path.is_file()
        and pipeline_status_path.is_file()
    ):
        return None
    try:
        report_status = json.loads(
            report_status_path.read_text(encoding="utf-8")
        )
        pipeline_status = json.loads(
            pipeline_status_path.read_text(encoding="utf-8")
        )
    except Exception:
        return None
    if not isinstance(report_status, dict) or not isinstance(
        pipeline_status, dict
    ):
        return None
    if not bool(report_status.get("l1_report_committed")):
        return None
    if str(pipeline_status.get("status") or "").lower() != "ok":
        return None
    expected_report_sha256 = str(
        report_status.get("report_sha256") or ""
    )
    if expected_report_sha256 and file_sha256(report_path) != expected_report_sha256:
        return None
    text = report_path.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def dispatch_l1_pipeline(purpose: str, tasks: Any = None) -> str:
    """Build, solve, analyze, validate, and return one L1 system report."""

    purpose_clean = (purpose or "").strip()
    tasks_text = _clean_tasks(tasks)
    if not purpose_clean and not tasks_text:
        return (
            "## Doability\nNot doable — empty purpose and tasks.\n\n"
            "## Analysis\nThe L1 sub-agent received no chemical-system "
            "brief to act on."
        )

    call_dir = _per_call_dir(purpose_clean, tasks_text)
    idx = _SESSION["call_index"]

    completed_report = _load_completed_l1_report(call_dir)
    if completed_report is not None:
        history = _SESSION.get("history")
        if history is not None:
            try:
                history.log(
                    "L1_checkpoint_reused",
                    call=idx,
                    purpose=purpose_clean[:200],
                    report_path=_rel_to_session(call_dir / "l1_report.md"),
                )
            except Exception:  # pragma: no cover
                pass
        _stat_incr("run", "checkpoint_reused")
        log.info(
            "L1[%d] reused completed crash-safe report from %s",
            idx,
            call_dir,
        )
        return completed_report

    state = _L1State(
        purpose=purpose_clean,
        tasks_text=tasks_text,
        call_dir=call_dir,
        idx=idx,
        debug=bool(_SESSION["debug"]),
        estimate_missing_equilibria=bool(
            _SESSION["estimate_missing_equilibria"]
        ),
        forward_explicit_estimation_disable=bool(
            _SESSION["forward_explicit_estimation_disable"]
        ),
    )

    try:
        atomic_write_json(
            call_dir / "input.json",
            {"purpose": purpose_clean, "tasks": tasks_text},
        )
    except Exception:  # pragma: no cover
        pass

    history = _SESSION.get("history")
    if history is not None:
        try:
            history.log("L1_start", call=idx, purpose=purpose_clean[:200])
        except Exception:  # pragma: no cover
            pass

    started = time.time()
    result = _run_l1_agent(state, hint="", attempt=1)
    l1_agent_turn_timed_out = bool(
        result is not None and getattr(result, "timed_out", False)
    )
    if state.agent_committed_report and state.committed_report:
        report = state.committed_report
    else:
        # Fail closed.  The engine's final-answer channel is allowed to be a
        # partial hard-stop summary and therefore cannot substitute for the
        # required terminal tool, even when the numerical pipeline succeeded.
        report = _missing_l1_terminal_commit_report()
        state.committed_report = report
        state.last_ld_verdict = {
            "verdict": "inconclusive",
            "hints": [
                "LD validation was not run because L1 did not successfully "
                "commit `record_analysis`; retry the L1 interpretation."
            ],
            "timed_out": False,
            "agent_turn_timed_out": False,
            "committed": False,
            "reason": "missing_l1_terminal_commit",
        }

    retry_budget = int(getattr(cfg, "PHASE_RETRY_BUDGET", 0) or 0)
    attempt = 1
    while state.agent_committed_report and attempt <= retry_budget:
        verdict = _validate_with_ld(state, report, attempt)
        state.last_ld_verdict = verdict
        retry_verdicts = {"contradicted"}
        if state.estimate_missing_equilibria:
            retry_verdicts.add("inconclusive")
        if not verdict or verdict.get("verdict") not in retry_verdicts:
            break
        hints = verdict.get("hints") or []
        if hints:
            hint_text = "\n".join(f"  - {hint}" for hint in hints)
        elif verdict.get("verdict") == "inconclusive":
            hint_text = (
                "  - The validator did not commit a conclusive verdict. "
                "Use the structured model_coverage and topology_summary "
                "returned by the cached pipeline status."
            )
        else:
            hint_text = "  - The analysis is not supported by the solver outputs."
        log.info(
            "L1[%d] LD %s (attempt %d) — retrying with hints",
            idx,
            verdict.get("verdict"),
            attempt,
        )
        if history is not None:
            try:
                history.log(
                    "L1_ld_retry",
                    call=idx,
                    attempt=attempt,
                    hints=hints,
                )
            except Exception:  # pragma: no cover
                pass
        attempt += 1
        # The validator requested a replacement report.  Invalidate the prior
        # terminal commit before giving L1 another turn so a failed/truncated
        # revision cannot silently fall back to the previously rejected prose.
        # Draft chunks are likewise generation-local and must be rebuilt from
        # chunk 1 on a review retry.
        state.agent_committed_report = False
        state.committed_report = None
        state.artifacts = []
        state.analysis_draft_chunks.clear()
        state.analysis_draft_generation += 1
        # Persist invalidation before the new model call.  If the process dies
        # during that call, the earlier l1_analysis.json cannot be mistaken for
        # the still-current terminal report by the disk fallback gate.
        _persist_l1_report_status(
            state,
            agent_turn_timed_out=False,
        )
        result = _run_l1_agent(state, hint=hint_text, attempt=attempt)
        l1_agent_turn_timed_out = bool(
            l1_agent_turn_timed_out
            or (
                result is not None
                and getattr(result, "timed_out", False)
            )
        )
        if state.agent_committed_report and state.committed_report:
            report = state.committed_report
        else:
            report = _missing_l1_terminal_commit_report()
            state.committed_report = report
            state.last_ld_verdict = {
                "verdict": "inconclusive",
                "hints": [
                    "LD validation requested a revised report, but L1 did "
                    "not successfully commit that revision; retry the L1 "
                    "interpretation."
                ],
                "timed_out": False,
                "agent_turn_timed_out": False,
                "committed": False,
                "reason": "missing_l1_terminal_commit_after_ld_retry",
            }
            break

    report = _append_validation_handoff(report, state.last_ld_verdict)
    state.committed_report = report
    try:
        atomic_write_text(state.call_dir / "l1_report.md", report)
    except Exception:  # pragma: no cover
        pass
    report_status = _persist_l1_report_status(
        state,
        agent_turn_timed_out=l1_agent_turn_timed_out,
    )
    # Publish every L1 review outcome to the session working memory, including
    # the reference-only route.  L0 treats this in-memory record as primary
    # and can recover the same information from ``LD/verdict*.json`` if a
    # legacy call or interrupted bookkeeping step omitted it.
    review = dict(state.last_ld_verdict) if isinstance(
        state.last_ld_verdict, dict
    ) else {
        "verdict": "not_run",
        "hints": [],
        "timed_out": False,
        "committed": False,
    }
    _wm_append("l1_validation_reviews", {
        "call": idx,
        "call_dir": _rel_to_session(state.call_dir),
        "report_path": _rel_to_session(state.call_dir / "l1_report.md"),
        "validation_enabled": bool(
            getattr(cfg, "LD_VALIDATOR_ENABLED", False)
        ),
        **review,
        "l1_report_committed": report_status["l1_report_committed"],
        "l1_agent_turn_timed_out": report_status["agent_turn_timed_out"],
        "l1_report_reason": report_status["reason"],
    })
    if state.estimate_missing_equilibria:
        _persist_enabled_quality(state, report)

    elapsed = time.time() - started
    if history is not None:
        try:
            history.log(
                "L1_end",
                call=idx,
                elapsed_s=round(elapsed, 1),
                ran_ok=state.ran_ok,
                attempts=attempt,
            )
        except Exception:  # pragma: no cover
            pass

    return report


__all__ = ["configure_l1_session", "dispatch_l1_pipeline"]
