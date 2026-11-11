"""Continue the same QueryAgent conversation for missing chemistry facts."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.query_artifacts import query_artifact_scope

from ..runtime_support.artifacts import (
    next_query_followup_directory, record_query_context, record_query_failure, record_query_turn,
    sha256_text, write_json, write_text,
)
from ..runtime_support.runtime_models import (
    LC13Settings,
    QueryRunner,
    QuerySession,
    QueryTurn,
    normalize_query_turn,
)
from .clarification_renderer import (
    render_query_clarification,
    render_query_continuation,
    render_query_reporting_followup,
)
from .evidence_receipts import build_evidence_receipt_snapshot


@dataclass(frozen=True)
class ClarificationResult:
    prompt: str
    turn: QueryTurn
    evidence_snapshot: dict[str, Any]
    artifact_dir: str
    elapsed_s: float
    call_timeout_s: float


class QueryClarificationFailure(RuntimeError):
    """A rejected clarification turn that must fail closed for this query."""

    def __init__(self, code: str, message: str, *, elapsed_s: float = 0.0) -> None:
        super().__init__(message)
        self.code = str(code)
        self.elapsed_s = float(elapsed_s)


def run_query_clarification(
    *,
    session: QuerySession,
    missing_topics: list[str],
    settings: LC13Settings,
    query_runner: QueryRunner,
    query_system_prompt: str,
    timeout_s: float,
    prompt_override: str | None = None,
    kind: str = "clarification",
    held_digest: list[dict[str, Any]] | None = None,
    evidence_index: Mapping[str, Any] | None = None,
    ungrounded_ids: Iterable[str] | None = None,
    runner_label: str = "dispatch",
    budget_note: str | None = None,
) -> ClarificationResult:
    """Continue the conversation with one bounded host prompt.

    The default prompt asks for the parser's missing chemistry topics;
    ``held_digest`` (rows from ``held_digest.build_held_digest``) tells the
    agent what the host already holds so it adds only what is missing.  For
    a ``supporting_evidence`` ask, ``evidence_index`` and ``ungrounded_ids``
    (from ``evidence_call_index``) list the calls already made and the ids
    no call returned, so the agent re-points or withdraws instead of
    searching again.  ``prompt_override`` with ``kind="continuation"`` reuses
    the same guarded path (deadline, memory identity, evidence refresh,
    artifacts) to ask the agent to resume an answer cut at the output cap.
    ``runner_label`` names the runner that serves the turn in the manifest
    (``"followup"``: the bound follow-up runner with the runtime's fresh-plan
    gate off; ``"dispatch"``: the dispatch runner).  ``kind="reporting"`` is
    the host's reporting turn (``run_query_reporting_followup``).
    ``budget_note`` (``clarification_renderer.render_host_budget_note``) is
    the remaining-follow-ups note the orchestrator computes when the pair's
    follow-up stage is close to a limit; it is appended after the prompt and
    recorded in the manifest, and an empty one changes nothing.
    """

    if session.dispatch_turn is None:
        raise ValueError("cannot clarify a query that was never dispatched")
    held_rows = [dict(row) for row in (held_digest or [])]
    index_payload = dict(evidence_index) if evidence_index else None
    cited_ids = [str(token) for token in (ungrounded_ids or []) if str(token).strip()]
    prompt = (
        render_query_clarification(
            missing_topics,
            held=held_rows,
            evidence_index=index_payload,
            ungrounded_ids=cited_ids,
        )
        if prompt_override is None
        else str(prompt_override)
    )
    note = str(budget_note or "").strip()
    if note:
        prompt = prompt.rstrip() + "\n\n" + note
    memory = session.memory
    call_timeout = min(float(settings.query_timeout_s), float(timeout_s))
    if not math.isfinite(call_timeout) or call_timeout < 1.0:
        raise QueryClarificationFailure(
            "budget_exhausted",
            "less than one second remains in the QueryAgent clarification budget",
        )
    index = len(session.followup_turns) + 1
    artifact_dir, attempt_index = next_query_followup_directory(session)
    write_text(artifact_dir / "user_prompt.md", prompt)
    write_text(artifact_dir / "system_prompt.md", query_system_prompt)

    def failure(code: str, message: str, elapsed: float) -> QueryClarificationFailure:
        record_query_failure(turn_dir=artifact_dir, code=code, message=message,
                             memory=memory, elapsed_s=elapsed)
        record_query_context(session)
        return QueryClarificationFailure(code, message, elapsed_s=elapsed)

    started = time.perf_counter()
    try:
        with query_artifact_scope(artifact_dir, user_prompt=prompt, system_prompt=query_system_prompt):
            turn = normalize_query_turn(query_runner(
                prompt,
                memory=memory,
                timeout=call_timeout,
                max_tool_iterations=settings.query_max_iterations,
            ))
    except TimeoutError as exc:
        elapsed = time.perf_counter() - started
        raise failure(
            "timeout", f"QueryAgent clarification timed out: {exc}",
            elapsed,
        ) from exc
    except Exception as exc:
        elapsed = time.perf_counter() - started
        raise failure(
            "runner_error",
            f"QueryAgent clarification failed: {type(exc).__name__}: {exc}",
            elapsed,
        ) from exc
    elapsed = time.perf_counter() - started
    # Persist every actual return, even when a later deadline/error gate rejects
    # it. Rejected turns remain artifacts; they never join parser evidence.
    record_query_turn(
        turn_dir=artifact_dir, user_prompt=prompt,
        system_prompt=query_system_prompt, turn=turn,
    )
    if elapsed > call_timeout:
        raise failure(
            "timeout",
            "QueryAgent clarification returned after its allowed deadline",
            elapsed,
        )
    if turn.timed_out:
        raise failure(
            "timeout",
            "QueryAgent clarification reported a timeout",
            elapsed,
        )
    if turn.error:
        raise failure(
            "agent_error",
            f"QueryAgent clarification reported an error: {turn.error}",
            elapsed,
        )
    if turn.memory is not memory:
        raise failure(
            "memory_replaced",
            f"{session.query_id}: QueryAgent replaced memory during follow-up",
            elapsed,
        )
    if not str(turn.answer or "").strip():
        raise failure(
            "empty_answer",
            "QueryAgent clarification answer is empty",
            elapsed,
        )
    session.followup_turns.append(turn)
    all_history = list(session.dispatch_turn.tool_history)
    for prior in session.followup_turns:
        all_history.extend(prior.tool_history)
    snapshot = build_evidence_receipt_snapshot(
        tool_history=all_history,
        scope=session.scope,
        authorization_context_id=session.query_id,
    )
    session.evidence_authorization = snapshot
    write_json(session.artifact_dir / "evidence_receipts.json", snapshot)
    write_json(artifact_dir / "clarification_manifest.json", {
        "query_id": session.query_id,
        "round": index,
        "attempt": attempt_index,
        "kind": str(kind),
        "runner": str(runner_label or "dispatch"),
        "missing_topics": list(missing_topics),
        "held_digest": held_rows,
        "evidence_index": index_payload,
        "ungrounded_ids": cited_ids,
        "host_budget_note": note or None,
        "output_budget": getattr(turn, "output_budget", None),
        "prompt_sha256": sha256_text(prompt),
        "answer_sha256": sha256_text(turn.answer),
        "same_memory_object": turn.memory is memory,
        "call_timeout_s": call_timeout,
        "elapsed_s": elapsed,
        "cumulative_tool_calls": len(all_history),
        "evidence_snapshot_sha256": snapshot.get("snapshot_sha256"),
    })
    record_query_context(session)
    return ClarificationResult(
        prompt=prompt,
        turn=turn,
        evidence_snapshot=snapshot,
        artifact_dir=str(artifact_dir),
        elapsed_s=elapsed,
        call_timeout_s=call_timeout,
    )


def run_query_continuation(
    *,
    session: QuerySession,
    settings: LC13Settings,
    query_runner: QueryRunner,
    query_system_prompt: str,
    timeout_s: float,
    tail: str,
    reason: str,
    runner_label: str = "dispatch",
    budget_note: str | None = None,
) -> ClarificationResult:
    """Ask the same conversation to resume an answer that stopped early.

    A host repair, not a chemistry question: it carries no missing topics and
    the orchestrator counts it against ``query_continuation_retries``, never
    against the clarification rounds.  The accepted turn joins the parser's
    transcript as the tail of the preceding answer.
    """

    return run_query_clarification(
        session=session,
        missing_topics=[],
        settings=settings,
        query_runner=query_runner,
        query_system_prompt=query_system_prompt,
        timeout_s=timeout_s,
        prompt_override=render_query_continuation(tail, reason=reason),
        kind="continuation",
        runner_label=runner_label,
        budget_note=budget_note,
    )


def run_query_reporting_followup(
    *,
    session: QuerySession,
    settings: LC13Settings,
    query_runner: QueryRunner,
    query_system_prompt: str,
    runner_label: str = "followup",
) -> ClarificationResult:
    """Ask the same conversation to restate its estimates in structured form.

    The second turn of every pair's conversation, sent by the host once the
    free exploration answer is in. The exploration turn carries chemistry
    only; every reporting requirement is a follow-up prompt. The agent
    keeps every tool and the turn gets the full query
    timeout.  It is recorded like any other host turn (``kind="reporting"``)
    and joins the parser's transcript after the exploration answer, where a
    later statement of an equilibrium governs.  The caller treats a failure
    as advisory: the parser then reads the exploration answer alone.
    """

    return run_query_clarification(
        session=session,
        missing_topics=[],
        settings=settings,
        query_runner=query_runner,
        query_system_prompt=query_system_prompt,
        timeout_s=float(settings.query_timeout_s),
        prompt_override=render_query_reporting_followup(),
        kind="reporting",
        runner_label=runner_label,
    )


__all__ = [
    "ClarificationResult",
    "QueryClarificationFailure",
    "run_query_clarification",
    "run_query_continuation",
    "run_query_reporting_followup",
]
