"""The host's reporting turn after the free exploration answer.

The SRD-46 QueryAgent's exploration turn carries chemistry only, and every
reporting requirement reaches it afterwards as a follow-up prompt in the same
conversation. This stage sends that one prompt to every dispatched conversation.
It never touches the exploration turn, the agent keeps every tool for it, and a
failure is advisory: the parser then reads the exploration answer alone.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..runtime_support.artifacts import mkdir, sha256_text, write_json
from ..runtime_support.runtime_models import LC13Settings, QueryRunner, QuerySession
from .clarification_renderer import render_query_reporting_followup
from .query_clarification_coordinator import (
    QueryClarificationFailure,
    run_query_reporting_followup,
)

MANIFEST_NAME = "02b_reporting_followup_manifest.json"


@dataclass
class ReportingFollowupResult:
    sessions: list[QuerySession]
    manifest_path: str
    runner: str
    prompt_sha256: str
    turns: list[dict[str, Any]] = field(default_factory=list)

    def _count(self, status: str) -> int:
        return sum(1 for row in self.turns if row.get("status") == status)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": "reporting_followup",
            "manifest_path": self.manifest_path,
            "runner": self.runner,
            "prompt_sha256": self.prompt_sha256,
            "n_sessions": len(self.sessions),
            "n_accepted": self._count("accepted"),
            "n_failed": self._count("failed"),
            "n_skipped": self._count("skipped"),
            "turns": [dict(row) for row in self.turns],
        }


def run_reporting_followup(
    *,
    sessions: list[QuerySession],
    output_dir: str | Path,
    settings: LC13Settings,
    query_runner: QueryRunner | None,
    query_system_prompt: str,
    runner_label: str = "followup",
) -> ReportingFollowupResult:
    """Send the reporting prompt to every dispatched conversation, once.

    ``query_runner`` should be the follow-up runner (the runtime's fresh-plan
    gate off, so the restatement is accepted as the addendum it is); the
    caller names it in ``runner_label``.  An accepted turn is stored on the
    session (``reporting_turn``, ``reporting_prompt_sha256``) for the parser,
    which reads it after the exploration answer.  A failed, errored, empty or
    late turn is recorded in the pair's follow-up artifacts and here, and the
    session keeps ``reporting_turn=None``.
    """

    root = Path(output_dir)
    mkdir(root, parents=True, exist_ok=True)
    prompt_sha256 = sha256_text(render_query_reporting_followup())
    rows: list[dict[str, Any]] = []
    for session in sessions:
        row: dict[str, Any] = {"query_id": session.query_id}
        if session.dispatch_turn is None:
            row.update(status="skipped", reason="no accepted exploration turn")
        elif query_runner is None:
            row.update(status="skipped", reason="no QueryAgent runner is available")
        else:
            started = time.perf_counter()
            try:
                result = run_query_reporting_followup(
                    session=session,
                    settings=settings,
                    query_runner=query_runner,
                    query_system_prompt=query_system_prompt,
                    runner_label=runner_label,
                )
            except QueryClarificationFailure as exc:
                row.update(
                    status="failed", code=exc.code, reason=str(exc),
                    elapsed_s=float(exc.elapsed_s or (time.perf_counter() - started)),
                )
            except Exception as exc:  # noqa: BLE001 - advisory stage, recorded
                row.update(
                    status="failed", code="runner_error",
                    reason=f"{type(exc).__name__}: {exc}",
                    elapsed_s=time.perf_counter() - started,
                )
            else:
                session.reporting_turn = result.turn
                session.reporting_prompt_sha256 = sha256_text(result.prompt)
                row.update(
                    status="accepted",
                    artifact_dir=result.artifact_dir,
                    elapsed_s=result.elapsed_s,
                    call_timeout_s=result.call_timeout_s,
                    answer_chars=len(result.turn.answer),
                    answer_sha256=sha256_text(result.turn.answer),
                    output_budget=result.turn.output_budget,
                    tool_calls=len(result.turn.tool_history),
                    evidence_snapshot_sha256=result.evidence_snapshot.get("snapshot_sha256"),
                )
        rows.append(row)
    outcome = ReportingFollowupResult(
        sessions=list(sessions),
        manifest_path=str(root / MANIFEST_NAME),
        runner=str(runner_label),
        prompt_sha256=prompt_sha256,
        turns=rows,
    )
    manifest = {
        **outcome.as_dict(),
        "contract": (
            "One host prompt per conversation after the exploration answer, "
            "asking for the structured restatement of the estimates; the "
            "exploration turn is never changed; a failed reporting turn is "
            "advisory and the parser reads the exploration answer alone."
        ),
        "call_timeout_s": float(settings.query_timeout_s),
    }
    write_json(root / MANIFEST_NAME, manifest)
    return outcome


__all__ = [
    "MANIFEST_NAME",
    "ReportingFollowupResult",
    "run_reporting_followup",
]
