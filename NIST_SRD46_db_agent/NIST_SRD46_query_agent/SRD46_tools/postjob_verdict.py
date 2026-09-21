"""
Post-job verdict agent  (postjob_verdict.py)
=============================================
Independent review agent that evaluates the SRD-46 subagent's work
after ``agent_turn()`` completes.  Runs as a single Argo call using
the configured verdict model.

Returns a combined **Verdict + Explanation** block that can be
appended directly after the subagent's answer.
"""

import json
import logging
from typing import Dict, List, Optional

log = logging.getLogger("SRD46-UI")

# =============================================================
#  Verdict system prompt
# =============================================================

_VERDICT_SYSTEM = (
    "You are an independent verification agent reviewing an SRD-46 "
    "database subagent's output.  You receive the user question, "
    "tool-call trace, catalog/plan (if any), and the final answer.\n\n"
    "Produce exactly TWO sections:\n\n"
    "**Verdict** (1-2 sentences, do not list tool names):\n"
    "State whether there are gaps — did the subagent fully answer "
    "the user's question?\n\n"
    "**Explanation** (2-3 sentences): Plain-language scientific summary "
    "of what the retrieved data means in context of the user's question. "
    "Highlight key scientific findings, notable scientific patterns, "
    "or important scientific caveats a scientist would care about. "
    " Do NOT critique the subagent's workflow — focus on the science and the data.\n\n"
    "HARD LIMIT: entire response ≤ 100 words.  Use markdown."
)


# =============================================================
#  Helpers
# =============================================================

def _build_tool_trace(
    memory: List[Dict[str, str]],
    extract_tool_call,
    coerce_tool_calls=None,
    instrumented_history: Optional[List[dict]] = None,
) -> str:
    """Build a compact textual tool-call trace for the verdict prompt.

    If *instrumented_history* is provided (from ``run_tests.py``), it
    includes arguments and result statistics.  Otherwise falls back to
    extracting just tool names from *memory*.
    """
    if instrumented_history:
        parts = []
        for step in instrumented_history:
            args_str = ", ".join(
                f"{k}={v!r}" for k, v in step.get("arguments", {}).items()
            )
            stats = step.get("result_stats", {})
            stats_str = ""
            if stats:
                stats_str = " → " + ", ".join(
                    f"{k}={v}" for k, v in stats.items() if v
                )
            parts.append(
                f"  {step.get('iteration', '?')}. "
                f"{step.get('tool', '?')}({args_str})"
                f"  [{step.get('result_chars', 0)} chars{stats_str}]"
            )
        return "\n".join(parts)

    # Fallback: extract from memory
    names = []
    for turn in memory:
        if turn["role"] == "assistant":
            tc = extract_tool_call(turn["content"])
            calls = coerce_tool_calls(tc) if coerce_tool_calls else ([tc] if tc else [])
            for call in calls:
                if isinstance(call, dict):
                    names.append(call.get("name", "unknown"))
    return ", ".join(names) if names else "(none)"


def _extract_tagged_block(
    memory: List[Dict[str, str]],
    tag: str,
    max_chars: int,
) -> str:
    """Return the first user-turn content containing *tag*, trimmed."""
    for turn in memory:
        content = turn.get("content", "")
        if turn["role"] == "user" and tag in content:
            return content[:max_chars]
    return ""


# =============================================================
#  Public entry point
# =============================================================

def run_verdict_agent(
    user_question: str,
    memory: List[Dict[str, str]],
    final_answer: str,
    *,
    call_argo,
    extract_tool_call,
    verdict_model: str,
    tool_history: Optional[List[dict]] = None,
    coerce_tool_calls=None,
) -> str:
    """Independent verdict + explanation agent.

    Parameters
    ----------
    call_argo : callable
        ``call_argo(prompt, system, stop, model)`` from the Argo client module.
    extract_tool_call : callable
        Parses ``<tool_call>`` XML from assistant text.
    verdict_model : str
        Model name to use (e.g. ``"gpt52"``).
    tool_history : list[dict] or None
        Rich instrumented history from ``run_tests.py``.  When
        ``None``, tool names are extracted from *memory* instead.
    """
    trace = _build_tool_trace(memory, extract_tool_call, coerce_tool_calls, tool_history)
    catalog_text = _extract_tagged_block(memory, "[CATALOG]", 6000)
    plan_text    = _extract_tagged_block(memory, "[PLAN]", 4000)

    prompt = f"USER QUESTION:\n{user_question}\n\n"
    prompt += f"TOOL-CALL TRACE:\n{trace}\n\n"
    if catalog_text:
        prompt += f"SYSTEM CATALOG:\n{catalog_text}\n\n"
    if plan_text:
        prompt += f"SEARCH PLAN:\n{plan_text}\n\n"
    prompt += f"SUBAGENT FINAL ANSWER:\n{final_answer[:4000]}\n\n"
    prompt += "Give your **Verdict** and **Explanation**."

    try:
        result = call_argo(prompt, _VERDICT_SYSTEM, stop=[],
                           model=verdict_model)
        return result.strip()
    except Exception as e:
        log.warning("[V] Verdict agent failed: %s", e)
        return f"(Verdict unavailable: {e})"
