"""
Result extractor for subagent delegation.
==========================================
Extracts a standardised ``dict`` from a ``RunResult``-like object
returned by any agent's public API.
"""
from __future__ import annotations

from typing import Any, Dict


def extract_run_result(
    result: object,
    agent_type: str,
    question: str = "",
    session_dir: Any = None,
    *,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Extract a flat result dict from a RunResult-like object.

    Parameters
    ----------
    result : object
        The object returned by ``ThermoML_*_run()``.
    agent_type : str
        ``"query"`` or ``"analysis"``.
    question : str
        The original question (stored as ``_question``).
    session_dir : Path | str | None
        The subagent session directory.
    extra : dict, optional
        Additional keys to merge into the result dict (e.g. entity
        summaries, verdict).

    Returns
    -------
    dict
        Standard keys: ``answer``, ``iterations``, ``elapsed_seconds``,
        ``tool_count``, ``timed_out``, ``agent``, ``_question``,
        ``_session_dir``, plus any agent-specific extras.
    """
    out: Dict[str, Any] = {
        "answer": getattr(result, "answer", str(result)),
        "iterations": getattr(result, "iterations", 0),
        "elapsed_seconds": getattr(result, "elapsed_seconds", 0.0),
        "tool_count": len(getattr(result, "tool_history", [])),
        "timed_out": getattr(result, "timed_out", False),
        "agent": agent_type,
        "_question": question,
        "_session_dir": str(session_dir) if session_dir else None,
    }
    if extra:
        out.update(extra)
    return out
