"""Coordinate parser drafts, chemistry follow-ups, and atomic gate commits."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..dispatch_srd46_query.query_clarification_coordinator import (
    QueryClarificationFailure,
    run_query_clarification,
)
from ..runtime_support.artifacts import mkdir, sha256_text, write_json, write_text
from ..runtime_support.runtime_models import (
    LC13Settings,
    ParserRunner,
    QueryRunner,
    QuerySession,
)
from .candidate_schema import ParseResult, ParserAction, ParserCycleResult
from .parser_agent import PARSER_SYSTEM_PROMPT, run_parser_agent
from .parser_gate_service import ParserGateService
from .parser_working_state import ParserWorkingState
from .srd46_catalog import Catalog


def _normalize_cycle(value: Any) -> ParserCycleResult:
    if isinstance(value, ParserCycleResult):
        return value
    if not isinstance(value, dict):
        raise TypeError("parser runner must return ParserCycleResult or dict")
    return ParserCycleResult(
        action=ParserAction(str(value.get("action") or "parser_revise")),
        reason=str(value.get("reason") or ""),
        missing_topics=[str(item) for item in value.get("missing_topics", [])],
        tool_history=list(value.get("tool_history") or []),
        agent_answer=str(value.get("agent_answer") or ""),
        final_context=str(value.get("final_context") or ""),
        elapsed_s=float(value.get("elapsed_s") or 0.0),
        error=value.get("error"),
    )


def _persist_cycle(
    *, artifact_dir: Path, index: int, cycle: ParserCycleResult,
    state: ParserWorkingState, feedback: str | None,
) -> None:
    cycle_dir = artifact_dir / "parser_cycles" / f"cycle_{index:02d}"
    mkdir(cycle_dir, parents=True, exist_ok=True)
    write_text(cycle_dir / "agent_answer.md", cycle.agent_answer, encoding="utf-8")
    write_text(cycle_dir / "final_context.md", cycle.final_context, encoding="utf-8")
    if feedback:
        write_text(cycle_dir / "parser_feedback.md", feedback, encoding="utf-8")
    write_json(cycle_dir / "tool_history.json", cycle.tool_history)
    write_json(cycle_dir / "outcome.json", cycle.as_dict())
    write_json(cycle_dir / "workspace.json", state.as_dict())


def _failure(
    *, session: QuerySession, action: ParserAction, reason: str,
    missing_topics: list[str], parser_cycles: int, clarification_rounds: int,
) -> dict[str, Any]:
    return {
        "query_id": session.query_id,
        "failure_kind": action.value,
        "error": reason,
        "missing_topics": list(missing_topics),
        "parser_cycles": parser_cycles,
        "query_clarification_rounds": clarification_rounds,
        "repair_action": "reference_only",
    }


_FEEDBACK_ISSUE_LIMIT = 10
_FEEDBACK_MESSAGE_LIMIT = 600


def _revise_feedback(state: ParserWorkingState, reason: str) -> str:
    """Carry gate findings across the cycle boundary a fresh agent cannot re-read."""

    lines = [
        "Correct parser-owned extraction or draft fields using the existing "
        "assistant answers and the host findings below. Do not add new "
        "chemical facts. Previous cycle: " + reason,
        "",
    ]
    if state.drafts:
        roster = ", ".join(
            f"{draft.draft_id}={draft.status}/"
            f"{state.annotation_liveness(draft.draft_id)}"
            for draft in state.drafts.values()
        )
        lines.append(
            f"Workspace at cycle end (revision {state.revision}): {roster}. "
            "Drafts and annotations persist across cycles: inspect_drafts, "
            "patch what is wrong, then run_network_gate; after it passes, "
            "annotate any unannotated or stale draft before commit."
        )
    else:
        lines.append(
            f"Workspace at cycle end (revision {state.revision}): no drafts "
            "exist yet."
        )
    last_failed = next(
        (report for report in reversed(state.gate_reports) if not report.passed),
        None,
    )
    if last_failed is None:
        return "\n".join(lines)
    header = (
        f"Last failed gate report (gate={last_failed.gate}, "
        f"revision {last_failed.state_revision}"
    )
    if last_failed.state_revision != state.revision:
        header += "; the workspace changed after this report"
    lines.append(header + "):")
    for issue in last_failed.issues[:_FEEDBACK_ISSUE_LIMIT]:
        message = issue.message
        if len(message) > _FEEDBACK_MESSAGE_LIMIT:
            message = message[:_FEEDBACK_MESSAGE_LIMIT] + " [truncated]"
        target = f"[{issue.draft_id}] " if issue.draft_id else ""
        lines.append(f"- {target}{issue.code} ({issue.owner.value}): {message}")
    hidden = len(last_failed.issues) - _FEEDBACK_ISSUE_LIMIT
    if hidden > 0:
        lines.append(f"- (+{hidden} more issues; re-run the gates for the rest)")
    return "\n".join(lines)


def run_parse_speciation_answer(
    *,
    sessions: list[QuerySession],
    output_dir: str | Path,
    settings: LC13Settings,
    base_eq_map_card: dict[str, Any] | None = None,
    session_id: str = "parser-gate-session",
    query_runner: QueryRunner | None = None,
    query_system_prompt: str = "",
    parser_runner: ParserRunner | None = None,
    catalog: Catalog | None = None,
    parser_validation_prior_attempts: dict[str, int] | None = None,
) -> ParseResult:
    """Drive each pair to commit, a bounded chemistry follow-up, or failure."""

    del parser_validation_prior_attempts  # old continuation accounting is retired
    root = Path(output_dir)
    parser_root = root / "parser_agents"
    mkdir(parser_root, parents=True, exist_ok=True)
    base_card = dict(base_eq_map_card or {"equilibrium_networks": []})
    runner = run_parser_agent if parser_runner is None else parser_runner
    parsed_queries = []
    failures: list[dict[str, Any]] = []
    workspaces: dict[str, ParserWorkingState] = {}
    source_transcripts: dict[str, str] = {}
    audit_by_query: dict[str, Any] = {}

    for session in sessions:
        if session.dispatch_turn is None:
            failures.append(_failure(
                session=session,
                action=ParserAction.FATAL_HOST,
                reason="query session has no initial QueryAgent turn",
                missing_topics=[],
                parser_cycles=0,
                clarification_rounds=0,
            ))
            continue
        artifact_dir = parser_root / session.query_id
        mkdir(artifact_dir, parents=True, exist_ok=True)
        initial_answer = str(session.dispatch_turn.answer or "")
        initial_digest = sha256_text(initial_answer)
        state = ParserWorkingState.create(
            query_id=session.query_id,
            scope=session.scope,
            request_T_C=float(session.request_T_C),
            request_I_M=float(session.request_I_M),
            base_eq_map_card=base_card,
            initial_answer=initial_answer,
            evidence_snapshot=dict(session.evidence_authorization or {}),
        )
        service = ParserGateService(
            state=state,
            base_eq_map_card=base_card,
            session_id=session_id,
            artifact_dir=artifact_dir,
            catalog=catalog,
        )
        workspaces[session.query_id] = state
        write_text(
            artifact_dir / "query_agent_transcript.md",
            state.transcript,
            encoding="utf-8",
        )
        write_text(
            artifact_dir / "parser_system_prompt.md",
            PARSER_SYSTEM_PROMPT,
            encoding="utf-8",
        )

        parser_cycles = 0
        parser_revisions = 0
        clarification_rounds = 0
        clarification_elapsed_s = 0.0
        feedback: str | None = None
        final_cycle: ParserCycleResult | None = None
        while True:
            parser_cycles += 1
            try:
                cycle = _normalize_cycle(runner(
                    service=service,
                    settings=settings,
                    artifact_dir=artifact_dir,
                    feedback=feedback,
                ))
            except Exception as exc:
                cycle = ParserCycleResult(
                    action=ParserAction.PARSER_REVISE,
                    reason=f"{type(exc).__name__}: {exc}",
                    error=f"{type(exc).__name__}: {exc}",
                )
            _persist_cycle(
                artifact_dir=artifact_dir,
                index=parser_cycles,
                cycle=cycle,
                state=state,
                feedback=feedback,
            )
            final_cycle = cycle
            feedback = None

            if cycle.action in {ParserAction.COMMIT, ParserAction.NO_ESTIMATE}:
                if service.committed_query is None:
                    cycle = ParserCycleResult(
                        action=ParserAction.FATAL_HOST,
                        reason=(
                            "parser reported a terminal commit without a "
                            "gate-owned committed query"
                        ),
                    )
                    final_cycle = cycle
                    break
                parsed_queries.append(service.committed_query)
                break

            if cycle.action is ParserAction.REQUEST_FOLLOWUP:
                authorized_topics = service.query_agent_followup_topics()
                asserted_topics = sorted({
                    str(value).strip() for value in cycle.missing_topics
                    if str(value).strip()
                })
                if not authorized_topics or asserted_topics != authorized_topics:
                    cycle = ParserCycleResult(
                        action=ParserAction.PARSER_REVISE,
                        reason=(
                            "parser requested a QueryAgent follow-up not authorized "
                            "by an active QueryAgent-source-bound gate receipt"
                        ),
                    )
                    final_cycle = cycle
                else:
                    if query_runner is None:
                        final_cycle = ParserCycleResult(
                            action=ParserAction.FATAL_HOST,
                            reason="no QueryAgent runner is available for clarification",
                            missing_topics=authorized_topics,
                        )
                        break
                    if clarification_rounds >= settings.query_clarification_retries:
                        final_cycle = ParserCycleResult(
                            action=ParserAction.REQUEST_FOLLOWUP,
                            reason="QueryAgent clarification retry limit exhausted",
                            missing_topics=authorized_topics,
                        )
                        break
                    remaining = (
                        settings.query_clarification_total_timeout_s
                        - clarification_elapsed_s
                    )
                    if remaining < 1.0:
                        final_cycle = ParserCycleResult(
                            action=ParserAction.REQUEST_FOLLOWUP,
                            reason="QueryAgent clarification time budget exhausted",
                            missing_topics=authorized_topics,
                        )
                        break
                    clarification_rounds += 1
                    call_started = time.perf_counter()
                    try:
                        clarification = run_query_clarification(
                            session=session,
                            missing_topics=authorized_topics,
                            settings=settings,
                            query_runner=query_runner,
                            query_system_prompt=query_system_prompt,
                            timeout_s=remaining,
                        )
                        state.add_answer_turn(
                            answer=clarification.turn.answer,
                            evidence_snapshot=clarification.evidence_snapshot,
                            prompt_sha256=sha256_text(clarification.prompt),
                        )
                    except QueryClarificationFailure as exc:
                        final_cycle = ParserCycleResult(
                            action=ParserAction.FATAL_HOST,
                            reason=f"QueryAgent clarification {exc.code}: {exc}",
                            missing_topics=authorized_topics,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        break
                    except Exception as exc:
                        final_cycle = ParserCycleResult(
                            action=ParserAction.FATAL_HOST,
                            reason=(
                                "QueryAgent clarification coordination failed: "
                                f"{type(exc).__name__}: {exc}"
                            ),
                            missing_topics=authorized_topics,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        break
                    finally:
                        clarification_elapsed_s += time.perf_counter() - call_started
                    write_text(
                        artifact_dir / "query_agent_transcript.md",
                        state.transcript,
                        encoding="utf-8",
                    )
                    parser_revisions = 0
                    feedback = (
                        "A same-conversation QueryAgent chemistry addendum is now "
                        "available. Recheck the retained drafts against the expanded "
                        "assistant-answer transcript."
                    )
                    continue

            if cycle.action is ParserAction.REQUEST_FOLLOWUP:
                # Every authorized request either continued or terminated above.
                final_cycle = ParserCycleResult(
                    action=ParserAction.FATAL_HOST,
                    reason="internal clarification routing error",
                )
                break

            if cycle.action is ParserAction.PARSER_REVISE:
                if parser_revisions >= settings.parser_validation_retries:
                    final_cycle = ParserCycleResult(
                        action=ParserAction.PARSER_REVISE,
                        reason="parser correction retry limit exhausted: " + cycle.reason,
                    )
                    break
                parser_revisions += 1
                feedback = _revise_feedback(state, cycle.reason)
                continue

            break

        if sha256_text(str(session.dispatch_turn.answer or "")) != initial_digest:
            final_cycle = ParserCycleResult(
                action=ParserAction.FATAL_HOST,
                reason="initial QueryAgent answer changed during parser coordination",
            )
            service.committed_query = None
            parsed_queries[:] = [
                item for item in parsed_queries if item.query_id != session.query_id
            ]
        source_transcripts[session.query_id] = state.transcript
        write_json(artifact_dir / "workspace.json", state.as_dict())
        if service.committed_query is not None:
            write_json(
                artifact_dir / "committed_guess_set.json",
                service.committed_query.parsed_speciation,
            )
        else:
            assert final_cycle is not None
            failure = _failure(
                session=session,
                action=final_cycle.action,
                reason=final_cycle.reason or final_cycle.error or "parser gate failed",
                missing_topics=final_cycle.missing_topics,
                parser_cycles=parser_cycles,
                clarification_rounds=clarification_rounds,
            )
            failures.append(failure)
            write_json(artifact_dir / "failure.json", failure)
        audit_by_query[session.query_id] = {
            "parser_cycles": parser_cycles,
            "parser_corrections": parser_revisions,
            "query_clarification_rounds": clarification_rounds,
            "query_clarification_elapsed_s": clarification_elapsed_s,
            "initial_answer_sha256": initial_digest,
            "initial_answer_immutable": (
                sha256_text(str(session.dispatch_turn.answer or "")) == initial_digest
            ),
            "final_transcript_sha256": state.transcript_sha256,
            "final_action": (
                None if final_cycle is None else final_cycle.action.value
            ),
        }

    manifest = {
        "stage": "parse_speciation_answer",
        "implementation": "revisioned tool parser plus deterministic entry/network gates",
        "n_parsed": len(parsed_queries),
        "n_failed": len(failures),
        "failures": failures,
        "queries": audit_by_query,
    }
    manifest_path = root / "03_parse_speciation_answer_manifest.json"
    write_json(manifest_path, manifest)
    return ParseResult(
        parsed_queries=parsed_queries,
        failures=failures,
        manifest_path=str(manifest_path),
        workspaces=workspaces,
        source_transcripts=source_transcripts,
        repair_audit={"queries": audit_by_query},
    )


__all__ = ["ParseResult", "run_parse_speciation_answer"]
