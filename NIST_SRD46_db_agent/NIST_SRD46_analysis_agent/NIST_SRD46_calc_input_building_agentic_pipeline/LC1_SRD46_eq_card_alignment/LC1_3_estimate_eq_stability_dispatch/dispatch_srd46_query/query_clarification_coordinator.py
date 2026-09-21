"""Continue the same QueryAgent conversation for missing chemistry facts."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from ..runtime_support.artifacts import record_query_turn, sha256_text, write_json
from ..runtime_support.runtime_models import (
    LC13Settings,
    QueryRunner,
    QuerySession,
    QueryTurn,
    normalize_query_turn,
)
from .clarification_renderer import render_query_clarification
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
) -> ClarificationResult:
    if session.dispatch_turn is None:
        raise ValueError("cannot clarify a query that was never dispatched")
    prompt = render_query_clarification(missing_topics)
    memory = session.memory
    call_timeout = min(float(settings.query_timeout_s), float(timeout_s))
    if not math.isfinite(call_timeout) or call_timeout < 1.0:
        raise QueryClarificationFailure(
            "budget_exhausted",
            "less than one second remains in the QueryAgent clarification budget",
        )
    started = time.perf_counter()
    try:
        turn = normalize_query_turn(query_runner(
            prompt,
            memory=memory,
            timeout=call_timeout,
            max_tool_iterations=settings.query_max_iterations,
        ))
    except TimeoutError as exc:
        elapsed = time.perf_counter() - started
        raise QueryClarificationFailure(
            "timeout", f"QueryAgent clarification timed out: {exc}",
            elapsed_s=elapsed,
        ) from exc
    except Exception as exc:
        elapsed = time.perf_counter() - started
        raise QueryClarificationFailure(
            "runner_error",
            f"QueryAgent clarification failed: {type(exc).__name__}: {exc}",
            elapsed_s=elapsed,
        ) from exc
    elapsed = time.perf_counter() - started
    if elapsed > call_timeout:
        raise QueryClarificationFailure(
            "timeout",
            "QueryAgent clarification returned after its allowed deadline",
            elapsed_s=elapsed,
        )
    if turn.timed_out:
        raise QueryClarificationFailure(
            "timeout",
            "QueryAgent clarification reported a timeout",
            elapsed_s=elapsed,
        )
    if turn.error:
        raise QueryClarificationFailure(
            "agent_error",
            f"QueryAgent clarification reported an error: {turn.error}",
            elapsed_s=elapsed,
        )
    if turn.memory is not memory:
        raise QueryClarificationFailure(
            "memory_replaced",
            f"{session.query_id}: QueryAgent replaced memory during follow-up",
            elapsed_s=elapsed,
        )
    if not str(turn.answer or "").strip():
        raise QueryClarificationFailure(
            "empty_answer",
            "QueryAgent clarification answer is empty",
            elapsed_s=elapsed,
        )
    session.followup_turns.append(turn)
    index = len(session.followup_turns)
    artifact_dir = session.artifact_dir / "query_agent_followups" / f"followup_{index:02d}"
    record_query_turn(
        turn_dir=artifact_dir,
        user_prompt=prompt,
        system_prompt=query_system_prompt,
        turn=turn,
    )
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
        "missing_topics": list(missing_topics),
        "prompt_sha256": sha256_text(prompt),
        "answer_sha256": sha256_text(turn.answer),
        "same_memory_object": turn.memory is memory,
        "call_timeout_s": call_timeout,
        "elapsed_s": elapsed,
        "cumulative_tool_calls": len(all_history),
        "evidence_snapshot_sha256": snapshot.get("snapshot_sha256"),
    })
    return ClarificationResult(
        prompt=prompt,
        turn=turn,
        evidence_snapshot=snapshot,
        artifact_dir=str(artifact_dir),
        elapsed_s=elapsed,
        call_timeout_s=call_timeout,
    )


__all__ = [
    "ClarificationResult",
    "QueryClarificationFailure",
    "run_query_clarification",
]
