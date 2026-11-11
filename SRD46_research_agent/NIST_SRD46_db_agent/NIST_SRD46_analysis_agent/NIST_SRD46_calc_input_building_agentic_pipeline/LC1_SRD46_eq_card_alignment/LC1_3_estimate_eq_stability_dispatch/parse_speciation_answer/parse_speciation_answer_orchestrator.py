"""Coordinate parser drafts, chemistry follow-ups, and atomic gate commits."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers import (
    ArgoAccessRevokedError,
    ArgoTransportError,
)

from ..dispatch_srd46_query.clarification_renderer import render_host_budget_note
from ..dispatch_srd46_query.query_clarification_coordinator import (
    QueryClarificationFailure,
    run_query_clarification,
    run_query_continuation,
)
from ..runtime_support.artifacts import (
    _io_path,
    logical_path,
    mkdir,
    read_text,
    sha256_text,
    write_json,
    write_text,
)
from ..runtime_support.runtime_models import (
    LC13Settings,
    ParserRunner,
    QueryRunner,
    QuerySession,
    QueryTurn,
)
from .answer_integrity import suspect_truncation
from .candidate_schema import ParseResult, ParserAction, ParserCycleResult
from .evidence_call_index import (
    build_evidence_call_index,
    session_tool_histories,
    ungrounded_ids_for_followup,
)
from .held_digest import build_held_digest
from .parser_agent import PARSER_SYSTEM_PROMPT, run_parser_agent
from .parser_gate_service import (
    _UNGROUNDED_ANCHOR_FOLLOWUP_BUDGET,
    ParserGateService,
)
from .parser_working_state import ParserWorkingState
from .srd46_catalog import Catalog


_CALL_DIR_RE = re.compile(r"L1_call_\d+")


def _bound_answer_path(session: QuerySession, answer: str) -> str:
    """Session-relative path of the ``answer.md`` holding *answer*, or "".

    The parser binds to the latest accepted turn (the reporting turn when
    there is one, else the exploration answer, or a continuation); the file
    is found by content under the query's artifact directory.  Relative to
    the session root (the parent of the ``L1_call_NN`` folder) so L0/L1 can
    open it with ``read_session_file``; the full path when no call folder
    is on the way.
    """

    root = session.artifact_dir
    directories = [root / "01_dispatch_srd46_query"]
    followups = root / "query_agent_followups"
    if _io_path(followups).is_dir():
        directories.extend(
            followups / p.name
            for p in sorted(_io_path(followups).glob("followup_*"))
        )
    wanted = answer.replace("\r\n", "\n").strip()
    hit: Path | None = None
    for directory in directories:
        path = directory / "answer.md"
        if not _io_path(path).is_file():
            continue
        text = read_text(path, encoding="utf-8").replace("\r\n", "\n").strip()
        if text and text == wanted:
            hit = path
    if hit is None:
        return ""
    logical = logical_path(hit)
    for parent in logical.parents:
        if _CALL_DIR_RE.fullmatch(parent.name):
            return logical.relative_to(parent.parent).as_posix()
    return logical.as_posix()


def _host_budget_note(
    settings: LC13Settings,
    *,
    kind: str,
    same_kind_used: int,
    host_turns_used: int,
    time_used_s: float,
) -> str:
    """The remaining-follow-ups note for the host turn about to be sent.

    ``same_kind_used`` and ``host_turns_used`` already count that turn.  Empty
    unless the pair's follow-up stage is close to a limit (the rule lives in
    ``clarification_renderer.render_host_budget_note``); the coordinator
    appends a non-empty note after the prompt and records it.
    """

    limit = (
        settings.query_clarification_retries
        if kind == "clarification"
        else settings.query_continuation_retries
    )
    ceiling = int(getattr(settings, "query_host_turn_ceiling", 0) or 0)
    return render_host_budget_note(
        kind=kind,
        remaining_same_kind=int(limit) - int(same_kind_used),
        remaining_any_kind=(ceiling - int(host_turns_used)) if ceiling else None,
        time_used_s=float(time_used_s),
        time_budget_s=float(settings.query_clarification_total_timeout_s),
    )


def _continuation_trigger(turn: QueryTurn | None, answer: str) -> dict[str, Any] | None:
    """Why the host should ask the QueryAgent to resume ``answer``, or None.

    The Argo usage record decides where it exists: ``output_truncated`` True
    triggers; False silences the tail heuristic (the model stopped on its
    own).  Without a record only a high-confidence tail heuristic triggers.
    """

    budget = getattr(turn, "output_budget", None) if turn is not None else None
    verdict = budget.get("output_truncated") if isinstance(budget, dict) else None
    if verdict is True:
        return {
            "source": "argo_usage",
            "reason": (
                f"the output limit of {budget.get('max_tokens')} tokens was "
                f"reached, completion_tokens={budget.get('completion_tokens')}"
            ),
            "output_budget": dict(budget),
        }
    if verdict is False:
        return None
    flag = suspect_truncation(answer)
    if flag is not None and flag.get("confidence") == "high":
        return {
            "source": "tail_heuristic",
            "reason": "its last line looks cut off: " + "; ".join(flag["signals"]),
            "truncation_suspected": flag,
        }
    return None


def _host_turn_ceiling_block(
    settings: LC13Settings,
    *,
    host_turns_used: int,
    transcript_chars: int,
    next_kind: str,
) -> dict[str, Any] | None:
    """Why the host must not send the next turn to the QueryAgent, or None.

    Two pre-declared ceilings per query are checked before every clarification
    and every continuation: the total number of
    host turns (clarifications plus continuations, attempts counted) and the
    size of the assistant-answer transcript the parser reads.  0 disables a
    ceiling.  The record names the ceiling, the count or size reached and the
    kind of turn refused; it goes to the audit and, when a clarification is
    refused, to the failure.
    """

    turn_ceiling = max(0, int(getattr(settings, "query_host_turn_ceiling", 0) or 0))
    char_ceiling = max(0, int(getattr(settings, "query_transcript_char_ceiling", 0) or 0))
    if turn_ceiling and host_turns_used >= turn_ceiling:
        return {
            "ceiling": "host_turns",
            "limit": turn_ceiling,
            "reached": int(host_turns_used),
            "refused": str(next_kind),
            "reason": (
                f"host-turn ceiling reached: {host_turns_used} of {turn_ceiling} "
                "QueryAgent turns (clarifications plus continuations) already "
                f"used, so a {next_kind} was refused"
            ),
        }
    if char_ceiling and transcript_chars >= char_ceiling:
        return {
            "ceiling": "transcript_chars",
            "limit": char_ceiling,
            "reached": int(transcript_chars),
            "refused": str(next_kind),
            "reason": (
                f"transcript ceiling reached: the assistant-answer transcript is "
                f"{transcript_chars} characters against a ceiling of {char_ceiling}, "
                f"so a {next_kind} was refused"
            ),
        }
    return None


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
    ceiling_stop: dict[str, Any] | None = None,
    transport_failure: bool = False,
) -> dict[str, Any]:
    return {
        "query_id": session.query_id,
        "failure_kind": action.value,
        "error": reason,
        # True when the pair ended because the Argo gateway stopped answering
        # (the transport streak ran out), not because of a parser outcome.
        "transport_failure": bool(transport_failure),
        "missing_topics": list(missing_topics),
        "parser_cycles": parser_cycles,
        "query_clarification_rounds": clarification_rounds,
        # The ceiling that ended the pair, when one did.
        "query_ceiling_stop": dict(ceiling_stop) if ceiling_stop else None,
        "repair_action": "reference_only",
    }


_FEEDBACK_ISSUE_LIMIT = 10
_FEEDBACK_MESSAGE_LIMIT = 600
_FEEDBACK_DETAILS_LIMIT = 700
_FEEDBACK_DETAILS_RENDERED_KEYS = {
    "unresolved_species", "suggested_resolution", "suggested_species_mapping",
    "closest_candidates", "retry_options", "parsed_signature",
    "species_mapping_applied", "canonical_species_hint",
    "canonical_species_vocabulary_size",
    # Traceability feedback (nearest answer lines for an untraceable span,
    # answer rows the grammar already reads): rendered explicitly below so
    # they survive truncation of the message.
    "untraceable", "excerpt_head", "nearest_transcript_lines",
    "untraceable_excerpts", "readable_reaction_rows",
}


def _render_nearest_lines(rows: Any) -> str:
    return "; ".join(
        f"{str(row.get('row'))[:120]!r} ({row.get('similarity')})"
        for row in list(rows or [])[:3]
        if isinstance(row, Mapping)
    )


def _render_issue_details(details: Mapping[str, Any]) -> str:
    """One compact line of a gate issue's structured details for feedback.

    The message of a topology or token finding is long; the next cycle's
    parser must still see which species failed, which canonical reading the
    host proposes, and which retry routes exist even after the message is
    truncated, so those travel here in a fixed order.
    """

    if not details:
        return ""
    segments: list[str] = []
    if details.get("untraceable"):
        segments.append(
            "span is not the answer's text: "
            + str(details.get("excerpt_head") or "")[:80].__repr__()
        )
        nearest = _render_nearest_lines(details.get("nearest_transcript_lines"))
        if nearest:
            segments.append("nearest answer lines: " + nearest)
    untraceable_excerpts = details.get("untraceable_excerpts")
    if isinstance(untraceable_excerpts, Mapping):
        for label, row in list(untraceable_excerpts.items())[:4]:
            if not isinstance(row, Mapping):
                continue
            segment = f"{label} not in answer: {str(row.get('excerpt_head') or '')[:60]!r}"
            nearest = _render_nearest_lines(row.get("nearest_transcript_lines"))
            if nearest:
                segment += " -> nearest: " + nearest
            segments.append(segment)
    readable = details.get("readable_reaction_rows")
    if readable:
        segments.append(
            "answer rows the grammar reads: " + "; ".join(
                f"turn {row.get('turn')} {str(row.get('row'))[:100]!r} -> "
                f"beta_def_{row.get('beta_definition_id')}"
                for row in list(readable)[:3]
                if isinstance(row, Mapping)
            )
        )
    unresolved = details.get("unresolved_species")
    if unresolved:
        segments.append("unresolved species: " + ", ".join(map(str, unresolved)))
    suggested = details.get("suggested_resolution")
    mapping = details.get("suggested_species_mapping")
    if suggested and mapping:
        segments.append(
            f"implicit-solvent reading: beta_def_{suggested.get('beta_definition_id')} "
            f"`{suggested.get('equation_python')}` via topology_species_mapping "
            + json.dumps(mapping, ensure_ascii=False)
        )
    candidates = details.get("closest_candidates")
    if candidates:
        segments.append(
            "closest: " + "; ".join(
                f"beta_def_{row.get('beta_definition_id')} `{row.get('equation_python')}`"
                for row in list(candidates)[:3]
            )
        )
    for key, value in details.items():
        if key in _FEEDBACK_DETAILS_RENDERED_KEYS or value in (None, "", [], {}):
            continue
        if isinstance(value, (str, int, float, bool)):
            segments.append(f"{key}={value}")
        else:
            segments.append(f"{key}={json.dumps(value, ensure_ascii=False, default=str)}")
    retry = details.get("retry_options")
    if retry:
        segments.append("retry via: " + ", ".join(map(str, retry)))
    text = " | ".join(segments)
    if len(text) > _FEEDBACK_DETAILS_LIMIT:
        text = text[:_FEEDBACK_DETAILS_LIMIT] + " [truncated]"
    return text


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
        rendered = _render_issue_details(getattr(issue, "details", None) or {})
        if rendered:
            lines.append(f"    details: {rendered}")
    hidden = len(last_failed.issues) - _FEEDBACK_ISSUE_LIMIT
    if hidden > 0:
        lines.append(f"- (+{hidden} more issues; re-run the gates for the rest)")
    return "\n".join(lines)


def _evidence_followup_context(
    *,
    session: QuerySession,
    state: ParserWorkingState,
    service: ParserGateService,
    topics: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """The call index and the ungrounded ids for a ``supporting_evidence`` ask.

    Empty for every other topic, so those prompts are unchanged.
    """

    if "supporting_evidence" not in {str(topic) for topic in topics}:
        return [], []
    index = build_evidence_call_index(
        session.evidence_authorization or {}, session_tool_histories(session),
    )
    ungrounded = ungrounded_ids_for_followup(
        state, unauthorized=service.prose_cited_unauthorized_ids(),
    )
    return index, ungrounded


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
    followup_query_runner: QueryRunner | None = None,
) -> ParseResult:
    """Drive each pair to commit, a bounded chemistry follow-up, or failure.

    ``followup_query_runner`` serves the host's turns in the same conversation
    (clarifications and continuations); it is the dispatch runner with the
    runtime's fresh-plan gate off.  Without one, ``query_runner`` serves them.
    """

    del parser_validation_prior_attempts  # Accepted and ignored.
    followup_runner = (
        followup_query_runner if followup_query_runner is not None else query_runner
    )
    followup_runner_label = "followup" if followup_query_runner is not None else "dispatch"
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
            initial_output_budget=getattr(session.dispatch_turn, "output_budget", None),
        )
        # The host's reporting turn, when accepted, follows the
        # exploration answer in the transcript.  Where the report restates
        # an equilibrium for the same metal ion at the same conditions the
        # parser binds to it (answer_precedence_rule); the host only indexes
        # the rows (latest_statements) and reports disagreements
        # (other_value_statements) - it never decides which row governs.
        # Without a report (not run, failed, empty) the parser reads the
        # exploration answer alone.
        report = getattr(session, "reporting_turn", None)
        report_answer = str(getattr(report, "answer", "") or "")
        report_included = report is not None and bool(report_answer.strip())
        if report_included:
            state.add_answer_turn(
                answer=report_answer,
                evidence_snapshot=dict(session.evidence_authorization or {}),
                prompt_sha256=str(
                    getattr(session, "reporting_prompt_sha256", None) or ""
                ),
                kind="reporting",
                output_budget=getattr(report, "output_budget", None),
            )
            latest_turn, latest_answer = report, report_answer
        else:
            latest_turn, latest_answer = session.dispatch_turn, initial_answer
        service = ParserGateService(
            state=state,
            base_eq_map_card=base_card,
            session_id=session_id,
            artifact_dir=artifact_dir,
            catalog=catalog,
            # Never ask for a follow-up the retry limit below would refuse.
            ungrounded_anchor_followup_budget=min(
                _UNGROUNDED_ANCHOR_FOLLOWUP_BUDGET,
                max(0, int(settings.query_clarification_retries)),
            ),
            # Host ceilings tell the parser when a follow-up cannot be served.
            host_turn_ceiling=int(getattr(settings, "query_host_turn_ceiling", 0) or 0),
            transcript_char_ceiling=int(
                getattr(settings, "query_transcript_char_ceiling", 0) or 0
            ),
        )
        workspaces[session.query_id] = state

        parser_cycles = 0
        parser_revisions = 0
        # Consecutive cycles the Argo gateway never answered; they are not
        # parser corrections and have their own budget and wait.
        transport_streak = 0
        transport_exhausted = False
        transport_stops: list[dict[str, Any]] = []
        clarification_rounds = 0
        clarification_elapsed_s = 0.0
        continuation_rounds = 0
        continuation_log: list[dict[str, Any]] = []
        # Every host turn refused by a ceiling, and the transcript size
        # before every host turn that was sent.
        ceiling_stops: list[dict[str, Any]] = []
        host_turn_sizes: list[dict[str, Any]] = []

        def resume_cut_answer(turn: QueryTurn | None, answer: str) -> None:
            """Host repair: ask the same conversation to finish a cut answer.

            Runs before the parser first reads the transcript and after every
            accepted follow-up.  Bounded by ``query_continuation_retries`` and
            the shared clarification time budget.  A failed or skipped
            continuation is recorded and the parser proceeds on the cut
            transcript, where missing chemistry surfaces as a follow-up topic.
            """

            nonlocal continuation_rounds, clarification_elapsed_s
            latest_turn, latest_answer = turn, answer
            while True:
                trigger = _continuation_trigger(latest_turn, latest_answer)
                if trigger is None:
                    return
                entry: dict[str, Any] = {
                    "answer_turn": len(state.answer_turns),
                    "source": trigger["source"],
                    "reason": trigger["reason"],
                }
                continuation_log.append(entry)
                if followup_runner is None:
                    entry["outcome"] = "skipped: no QueryAgent runner is available"
                    return
                block = _host_turn_ceiling_block(
                    settings,
                    host_turns_used=clarification_rounds + continuation_rounds,
                    transcript_chars=len(state.transcript),
                    next_kind="continuation",
                )
                if block is not None:
                    # Advisory: the parser proceeds on the cut transcript.
                    entry["outcome"] = "skipped: " + block["reason"]
                    entry["ceiling"] = dict(block)
                    ceiling_stops.append({**block, "effect": "continuation skipped"})
                    return
                if continuation_rounds >= settings.query_continuation_retries:
                    entry["outcome"] = "skipped: continuation retry limit exhausted"
                    return
                remaining = (
                    settings.query_clarification_total_timeout_s
                    - clarification_elapsed_s
                )
                if remaining < 1.0:
                    entry["outcome"] = "skipped: QueryAgent time budget exhausted"
                    return
                continuation_rounds += 1
                budget_note = _host_budget_note(
                    settings, kind="continuation",
                    same_kind_used=continuation_rounds,
                    host_turns_used=clarification_rounds + continuation_rounds,
                    time_used_s=clarification_elapsed_s,
                )
                host_turn_sizes.append({
                    "host_turn": clarification_rounds + continuation_rounds,
                    "kind": "continuation",
                    "transcript_chars_before": len(state.transcript),
                })
                call_started = time.perf_counter()
                try:
                    continuation = run_query_continuation(
                        session=session,
                        settings=settings,
                        query_runner=followup_runner,
                        query_system_prompt=query_system_prompt,
                        timeout_s=remaining,
                        tail=latest_answer,
                        reason=trigger["reason"],
                        runner_label=followup_runner_label,
                        budget_note=budget_note or None,
                    )
                except QueryClarificationFailure as exc:
                    entry["outcome"] = f"failed: {exc.code}: {exc}"
                    return
                except Exception as exc:  # noqa: BLE001 - recorded, parser proceeds
                    entry["outcome"] = f"failed: {type(exc).__name__}: {exc}"
                    return
                finally:
                    clarification_elapsed_s += time.perf_counter() - call_started
                state.add_answer_turn(
                    answer=continuation.turn.answer,
                    evidence_snapshot=continuation.evidence_snapshot,
                    prompt_sha256=sha256_text(continuation.prompt),
                    kind="continuation",
                    output_budget=continuation.turn.output_budget,
                )
                entry["outcome"] = f"appended as answer turn {len(state.answer_turns)}"
                entry["artifact_dir"] = continuation.artifact_dir
                latest_turn, latest_answer = continuation.turn, continuation.turn.answer

        # The latest assistant turn is the one a continuation would resume:
        # the report when there is one, else the exploration answer.
        resume_cut_answer(latest_turn, latest_answer)
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
            except ArgoAccessRevokedError:
                # A revoked Argo allowance is not a cycle outcome: another
                # cycle would only repeat the blocked request.  Let it stop
                # the stage with the gateway's notice as the reason.
                raise
            except ArgoTransportError as exc:
                # The gateway never answered this cycle (outage, timeouts,
                # empty envelopes past the client's own retries): not a
                # parser outcome.  The drafts in ``state`` are kept, no
                # correction retry is spent, the pending feedback is sent
                # again, and the host waits longer than the client's own
                # back-off before the next cycle; a streak past the transport
                # budget fails the pair closed with its own reason.
                message = f"{type(exc).__name__}: {exc}"
                cycle = ParserCycleResult(
                    action=ParserAction.PARSER_REVISE, reason=message, error=message,
                )
                _persist_cycle(
                    artifact_dir=artifact_dir, index=parser_cycles, cycle=cycle,
                    state=state, feedback=feedback,
                )
                final_cycle = cycle
                transport_streak += 1
                stop: dict[str, Any] = {
                    "cycle": parser_cycles, "streak": transport_streak,
                    "error": str(exc), "waited_s": 0.0,
                }
                transport_stops.append(stop)
                if transport_streak > settings.parser_transport_retries:
                    final_cycle = ParserCycleResult(
                        action=ParserAction.PARSER_REVISE,
                        reason="parser transport retry limit exhausted: " + message,
                        error=message,
                    )
                    transport_exhausted = True
                    break
                wait_s = float(settings.parser_transport_wait_s) * transport_streak
                stop["waited_s"] = wait_s
                if wait_s > 0:
                    time.sleep(wait_s)
                continue
            except Exception as exc:
                cycle = ParserCycleResult(
                    action=ParserAction.PARSER_REVISE,
                    reason=f"{type(exc).__name__}: {exc}",
                    error=f"{type(exc).__name__}: {exc}",
                )
            transport_streak = 0
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
                    if followup_runner is None:
                        final_cycle = ParserCycleResult(
                            action=ParserAction.FATAL_HOST,
                            reason="no QueryAgent runner is available for clarification",
                            missing_topics=authorized_topics,
                        )
                        break
                    block = _host_turn_ceiling_block(
                        settings,
                        host_turns_used=clarification_rounds + continuation_rounds,
                        transcript_chars=len(state.transcript),
                        next_kind="clarification",
                    )
                    if block is not None:
                        # Fail closed, like an exhausted time budget: the pair
                        # goes reference_only with the ceiling recorded.
                        ceiling_stops.append({**block, "effect": "pair fails closed"})
                        final_cycle = ParserCycleResult(
                            action=ParserAction.REQUEST_FOLLOWUP,
                            reason="QueryAgent " + block["reason"],
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
                    budget_note = _host_budget_note(
                        settings, kind="clarification",
                        same_kind_used=clarification_rounds,
                        host_turns_used=clarification_rounds + continuation_rounds,
                        time_used_s=clarification_elapsed_s,
                    )
                    host_turn_sizes.append({
                        "host_turn": clarification_rounds + continuation_rounds,
                        "kind": "clarification",
                        "transcript_chars_before": len(state.transcript),
                    })
                    # For an evidence follow-up: the calls the agent already
                    # made and the ids no call returned, so it re-points or
                    # withdraws instead of searching again.
                    evidence_index, ungrounded_ids = _evidence_followup_context(
                        session=session, state=state, service=service,
                        topics=authorized_topics,
                    )
                    call_started = time.perf_counter()
                    try:
                        clarification = run_query_clarification(
                            session=session,
                            missing_topics=authorized_topics,
                            settings=settings,
                            query_runner=followup_runner,
                            query_system_prompt=query_system_prompt,
                            timeout_s=remaining,
                            # What the host already holds, in the agent's own
                            # words, so the addendum carries only the gap.
                            held_digest=build_held_digest(
                                state, missing_topics=authorized_topics,
                            ),
                            evidence_index=evidence_index,
                            ungrounded_ids=ungrounded_ids,
                            runner_label=followup_runner_label,
                            budget_note=budget_note or None,
                        )
                        state.add_answer_turn(
                            answer=clarification.turn.answer,
                            evidence_snapshot=clarification.evidence_snapshot,
                            prompt_sha256=sha256_text(clarification.prompt),
                            output_budget=clarification.turn.output_budget,
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
                    # A follow-up can hit the output cap too.
                    resume_cut_answer(clarification.turn, clarification.turn.answer)
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
            # Which answer file the committed values came from, for the
            # card's source cell.
            service.committed_query.answer_path = _bound_answer_path(
                session, latest_answer,
            )
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
                transport_failure=transport_exhausted,
                # Only a ceiling that ended the pair; a skipped continuation
                # is advisory and stays in the audit alone.
                ceiling_stop=next(
                    (
                        stop for stop in reversed(ceiling_stops)
                        if stop.get("effect") == "pair fails closed"
                    ),
                    None,
                ),
            )
            failures.append(failure)
            write_json(artifact_dir / "failure.json", failure)
        audit_by_query[session.query_id] = {
            "parser_cycles": parser_cycles,
            "parser_corrections": parser_revisions,
            # Cycles the Argo gateway never answered, with the host's wait
            # before the next one; they are not counted as corrections.
            "parser_transport_stops": transport_stops,
            "query_clarification_rounds": clarification_rounds,
            "query_clarification_elapsed_s": clarification_elapsed_s,
            "initial_answer_sha256": initial_digest,
            "initial_answer_immutable": (
                sha256_text(str(session.dispatch_turn.answer or "")) == initial_digest
            ),
            # Whether the host's reporting turn follows the
            # exploration answer in the transcript the parser read.
            "query_reporting_turn_included": bool(report_included),
            "final_transcript_sha256": state.transcript_sha256,
            "final_action": (
                None if final_cycle is None else final_cycle.action.value
            ),
            # Answer turns the Argo usage record shows stopped at the output
            # cap, the advisory tail heuristic, and the host continuations
            # that asked the QueryAgent to resume them.
            "answer_output_truncated": [
                row["turn"] for row in state.answer_turn_summaries()
                if row.get("output_truncated") is True
            ],
            "answer_truncation_suspected": [
                {
                    "turn": row["turn"],
                    "confidence": row["truncation_suspected"]["confidence"],
                    "signals": row["truncation_suspected"]["signals"],
                }
                for row in state.answer_turn_summaries()
                if row.get("truncation_suspected")
            ],
            "query_continuation_rounds": continuation_rounds,
            "query_continuations": continuation_log,
            # Host ceilings: what was declared, what was used, the transcript
            # size before each host turn, and every turn a ceiling refused.
            "query_host_turn_ceiling": int(
                getattr(settings, "query_host_turn_ceiling", 0) or 0
            ),
            "query_transcript_char_ceiling": int(
                getattr(settings, "query_transcript_char_ceiling", 0) or 0
            ),
            "query_host_turns_used": clarification_rounds + continuation_rounds,
            "query_host_turn_sizes": host_turn_sizes,
            "query_ceiling_stops": ceiling_stops,
            "final_transcript_chars": len(state.transcript),
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
