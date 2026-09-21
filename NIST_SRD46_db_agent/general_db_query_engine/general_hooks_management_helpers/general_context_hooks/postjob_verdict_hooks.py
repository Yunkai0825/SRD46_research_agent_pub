"""
Post-job tracking hooks — verdict core + final context persistence.
===================================================================
Shared infrastructure called by both the query and analysis agents
after a run completes.

Public API
----------
build_tool_trace    — format a tool_history list into a compact text trace
run_verdict_core    — parametrised LLM verdict call (each agent provides
                      its own system prompt, client, and optional kwargs)
save_final_context  — write ``final_full_context.md`` to the output dir

Usage (thin wrappers in each agent)::

    from ...general_context_hooks.postjob_verdict_hooks import (
        run_verdict_core,
        save_final_context,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("postjob-hooks")


# ═══════════════════════════════════════════════════════════════════════════
#  Tool-trace builder
# ═══════════════════════════════════════════════════════════════════════════

def build_tool_trace(
    tool_history: list[dict[str, Any]],
    *,
    include_elapsed: bool = True,
) -> str:
    """Format *tool_history* into a compact, human-readable trace.

    Parameters
    ----------
    tool_history : list[dict]
        Each dict should have ``iteration``, ``tool``, ``args_keys``,
        ``result_chars``, and (optionally) ``elapsed_s``.
    include_elapsed : bool
        Append elapsed seconds to each line (default True).
    """
    lines: list[str] = []
    for entry in tool_history:
        iteration = entry.get("iteration", "?")
        tool = entry.get("tool", "?")
        args = ", ".join(entry.get("args_keys", []))
        chars = entry.get("result_chars", "?")
        line = f"  {iteration}. {tool}({args}) → {chars} chars"
        if include_elapsed:
            line += f", {entry.get('elapsed_s', '?')}s"
        lines.append(line)
    return "\n".join(lines) if lines else "(no tool calls)"


# ═══════════════════════════════════════════════════════════════════════════
#  Core verdict LLM call
# ═══════════════════════════════════════════════════════════════════════════

def run_verdict_core(
    user_question: str,
    final_answer: str,
    tool_history: list[dict[str, Any]],
    *,
    system_prompt: str,
    client,
    answer_char_limit: int | None = None,
    verdict_word_cap: int | None = None,
    include_elapsed: bool = True,
    call_kwargs: dict[str, Any] | None = None,
) -> str:
    """Run an independent verdict LLM call and return the review text.

    Parameters
    ----------
    user_question : str
        Original user question.
    final_answer : str
        Agent's final answer text.
    tool_history : list[dict]
        Tool call trace from ``AgentTurnResult.tool_history``.
    system_prompt : str
        Agent-specific verdict system prompt.
    client
        LLM caller (must expose ``.call(prompt, system, ...)``).
    answer_char_limit : int, optional
        If set, truncate *final_answer* to this many characters in the
        prompt sent to the verdict model.
    verdict_word_cap : int, optional
        If set, append a "≤N words" instruction to the user prompt.
    include_elapsed : bool
        Forward to :func:`build_tool_trace`.
    call_kwargs : dict, optional
        Extra keyword arguments forwarded to ``client.call()``.
    """
    trace = build_tool_trace(tool_history, include_elapsed=include_elapsed)

    answer_text = final_answer
    if answer_char_limit is not None:
        answer_text = final_answer[:answer_char_limit]

    prompt = (
        f"## User Question\n{user_question}\n\n"
        f"## Tool Call Trace\n{trace}\n\n"
        f"## Agent's Final Answer\n{answer_text}\n\n"
    )
    if verdict_word_cap is not None:
        prompt += f"Provide your independent verdict (≤{verdict_word_cap} words)."

    model_label = getattr(client, "model", "?")
    log.info("Running verdict agent (%s)…", model_label)
    try:
        kw = call_kwargs or {}
        result = client.call(prompt, system_prompt, **kw)
        log.info("Verdict: %d chars", len(result))
        return result.strip()
    except Exception as exc:
        log.warning("Verdict failed: %s", exc, exc_info=True)
        return f"(Verdict unavailable: {exc})"


# ═══════════════════════════════════════════════════════════════════════════
#  Final-context persistence
# ═══════════════════════════════════════════════════════════════════════════

def save_final_context(
    output_dir: str | Path,
    final_context: str,
    *,
    filename: str = "final_full_context.md",
) -> Path | None:
    """Persist the raw final LLM context to *output_dir*/*filename*.

    Parameters
    ----------
    output_dir : str or Path
        Session / run output directory.
    final_context : str
        Raw last-turn context captured from the ReAct loop
        (``AgentTurnResult.final_context``).
    filename : str
        Destination filename (default ``final_full_context.md``).

    Returns
    -------
    Path or None
        Written file path, or None if context was empty / write failed.
    """
    if not final_context or not final_context.strip():
        log.debug("No final context to save — skipping.")
        return None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / filename
    try:
        dest.write_text(final_context, encoding="utf-8")
        log.info("Final context saved → %s (%d chars)", dest, len(final_context))
        return dest
    except Exception as exc:
        log.warning("Failed to write final context: %s", exc, exc_info=True)
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  Base dataclass — subclass in each agent's verdict_hooks/
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VerdictRunner:
    """Post-job verdict engine — one instance per agent.

    Subclass in ``<agent>_context_hooks/verdict_hooks/`` and
    override *system_prompt* and numeric fields to customise
    verdict behaviour per agent.
    """

    system_prompt: str = ""
    verdict_word_cap: int | None = None
    answer_char_limit: int | None = None
    include_elapsed: bool = True
    call_kwargs: dict[str, Any] = field(default_factory=dict)

    def run_verdict(
        self,
        user_question: str,
        final_answer: str,
        tool_history: list[dict[str, Any]],
        *,
        client,
    ) -> str:
        return run_verdict_core(
            user_question, final_answer, tool_history,
            system_prompt=self.system_prompt,
            client=client,
            verdict_word_cap=self.verdict_word_cap,
            answer_char_limit=self.answer_char_limit,
            include_elapsed=self.include_elapsed,
            call_kwargs=self.call_kwargs or None,
        )
