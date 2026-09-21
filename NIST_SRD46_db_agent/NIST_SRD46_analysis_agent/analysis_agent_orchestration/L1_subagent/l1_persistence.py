"""Persistence helpers and narrow hard-stop recovery for the L1 runner."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from ....general_db_query_engine.general_argo_engine_helpers import AgentTurnResult

from .l1_state import _L1State


log = logging.getLogger("Analysis.L1")


def _write_tool_history(
    call_dir: Path,
    tool_history: List[Dict[str, Any]],
    attempt: int,
) -> None:
    rows = [
        f"# L1 Tool Calls (attempt {attempt})",
        "",
        "| # | iter | tool | args (excerpt) | result_chars | elapsed_s |",
        "|--:|----:|------|----------------|-------------:|----------:|",
    ]
    for index, call in enumerate(tool_history, start=1):
        arguments = call.get("arguments", {}) or {}
        try:
            excerpt = json.dumps(arguments)[:120].replace("|", "\\|")
        except Exception:
            excerpt = repr(arguments)[:120].replace("|", "\\|")
        rows.append(
            f"| {index} | {call.get('iteration', '')} | "
            f"{call.get('tool', '?')} | {excerpt} | "
            f"{call.get('result_chars', '')} | {call.get('elapsed_s', '')} |"
        )
    suffix = "" if attempt <= 1 else f"_retry{attempt - 1}"
    (call_dir / f"l1_tool_calls{suffix}.md").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def _write_agent_response(
    call_dir: Path,
    result: AgentTurnResult,
    attempt: int,
) -> None:
    suffix = "" if attempt <= 1 else f"_retry{attempt - 1}"
    try:
        (call_dir / f"agent_response{suffix}.md").write_text(
            "# L1 agent response\n\n"
            "## Final answer (text emitted by the agent)\n\n"
            f"{getattr(result, 'answer', '') or '_(empty)_'}\n\n"
            "## Final context\n\n"
            f"{getattr(result, 'final_context', '') or '_(empty)_'}\n",
            encoding="utf-8",
        )
    except Exception:  # pragma: no cover
        pass


def _recover_enabled_hard_stop_record_analysis(
    state: _L1State,
    result: AgentTurnResult,
    *,
    record_tool_name: str,
    record_analysis_factory: Callable[[_L1State], Callable[..., str]],
) -> bool:
    """Commit an exact terminal call emitted by the hard-stop summary turn."""

    if (
        not state.estimate_missing_equilibria
        or state.agent_committed_report
        or not bool(getattr(result, "timed_out", False))
    ):
        return False

    raw_answer = getattr(result, "answer", "")
    if not isinstance(raw_answer, str) or not raw_answer.strip():
        return False
    try:
        payload = json.loads(raw_answer.strip())
    except (TypeError, ValueError):
        return False

    if not isinstance(payload, dict) or set(payload) != {"name", "arguments"}:
        return False
    if payload.get("name") != record_tool_name:
        return False
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        return False
    allowed_arguments = {
        "analysis_markdown",
        "artifact_paths",
        "expected_chunks",
    }
    if not set(arguments).issubset(allowed_arguments):
        return False
    analysis_markdown = arguments.get("analysis_markdown", "")
    artifact_paths = arguments.get("artifact_paths", "")
    expected_chunks = arguments.get("expected_chunks", 0)
    if (
        not isinstance(analysis_markdown, str)
        or not isinstance(artifact_paths, str)
        or isinstance(expected_chunks, bool)
        or not isinstance(expected_chunks, int)
    ):
        return False

    started = time.time()
    receipt = record_analysis_factory(state)(
        analysis_markdown=analysis_markdown,
        artifact_paths=artifact_paths,
        expected_chunks=expected_chunks,
    )
    if not isinstance(receipt, str) or not receipt.startswith("OK"):
        return False

    result.tool_history.append({
        "iteration": int(getattr(result, "iterations", 0) or 0) + 1,
        "tool": record_tool_name,
        "args_keys": sorted(arguments),
        "arguments": dict(arguments),
        "result_chars": len(receipt),
        "result_full": receipt,
        "reasoning": "[recovered exact terminal call from hard-stop summary]",
        "elapsed_s": round(time.time() - started, 1),
        "hard_stop_terminal_recovery": True,
    })
    log.warning(
        "L1[%d] recovered exact %s terminal call from hard-stop summary",
        state.idx,
        record_tool_name,
    )
    return True


__all__ = [
    "_recover_enabled_hard_stop_record_analysis",
    "_write_agent_response",
    "_write_tool_history",
]
