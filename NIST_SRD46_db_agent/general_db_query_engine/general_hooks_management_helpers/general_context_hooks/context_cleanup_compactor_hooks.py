"""
Shared stage-compaction & context-cleanup helpers.
===================================================
Deterministic (non-LLM) compaction of parallel tool batches, tool-call
XML shortening, and adaptive trimming of old tool results.

All functions are **parameterised** — they receive budget / limit values
as arguments (no hard-coded config import).  Each agent provides a thin
wrapper that injects its own ``AGENT_CONFIG`` defaults.

Public API
----------
REASONING_BLOCK_RE           — compiled regex for ``<reasoning>…</reasoning>``
SUMMARY_BLOCK_RE             — compiled regex for ``<summary>…</summary>``
extract_note                 — first-N-chars preview from a tool result
compact_short_args           — one-line pretty-print of tool arguments
compact_tool_calls_for_memory — replace verbose ``<tool_call>`` XML
stage_compact_batch          — markdown table summarising a parallel batch
trim_old_tool_results        — truncate old entries in the memory list
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...general_text_context_marker_catalog import MARKERS

TAG_TOOL_CALL_OPEN = MARKERS.tool_call.open
TAG_TOOL_CALL_CLOSE = MARKERS.tool_call.close
TAG_TOOL_RESULT_OPEN = MARKERS.tool_result.open
TAG_WAIT = MARKERS.wait_tag
REASONING_BLOCK_RE = MARKERS.reasoning_re
SUMMARY_BLOCK_RE = MARKERS.summary_re


# ─── Helpers ─────────────────────────────────────────────────

def extract_note(text: str, max_chars: int = 200) -> str:
    """Extract the first meaningful sentences from a tool result."""
    lines = text.strip().split("\n")
    useful: list[str] = []
    n = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip markdown table separators
        if stripped.startswith("|") and set(stripped.replace("|", "").strip()) <= {"-"}:
            continue
        useful.append(stripped)
        n += len(stripped)
        if n >= max_chars:
            break
    note = " ".join(useful)
    if len(note) > max_chars:
        note = note[:max_chars].rsplit(" ", 1)[0] + "…"
    return note


def _format_arg_value(v: Any, max_chars: int) -> str:
    """Render a tool-arg value as a parseable Python literal.

    Strings → ``repr`` (quoted); ints/floats/bools/None → ``repr``;
    lists/dicts → ``repr`` (compact).  If the result exceeds
    ``max_chars`` we truncate inside the literal but preserve the
    closing quote so the compact form remains a syntactically valid
    string literal — important because the agent imitates this form
    on subsequent turns and our parser must be able to round-trip it.
    """
    sv = repr(v)
    if len(sv) <= max_chars:
        return sv
    # Truncate but keep balanced quotes for strings
    if isinstance(v, str):
        # repr(str) uses ' or " as outer; pick the same closing quote
        quote = sv[0]
        body = sv[1:-1]
        cut = max_chars - 3  # room for "…" + closing quote
        return f"{quote}{body[:cut]}…{quote}"
    return sv[: max_chars - 1] + "…"


def compact_short_args(raw_args: dict[str, Any], max_chars: int = 60) -> str:
    """Format tool arguments into a short string for summary tables.

    Output is a parseable ``k=v, k=v`` snippet (values use Python
    ``repr``), so ``ast.parse(name(...), mode="eval")`` round-trips
    cleanly.  ``purpose`` and ``tasks`` are dropped (verbose).
    """
    priority = [
        "compounds", "doi", "names", "compound", "property_hint",
        "block_number", "properties", "property_type",
    ]
    parts: list[str] = []
    for k in priority:
        if k in raw_args:
            parts.append(f"{k}={_format_arg_value(raw_args[k], max_chars=40)}")
    for k, v in raw_args.items():
        if k in priority or k in ("purpose", "tasks"):
            continue
        parts.append(f"{k}={_format_arg_value(v, max_chars=30)}")
    result = ", ".join(parts)
    if len(result) > max_chars:
        result = result[: max_chars - 1] + "…"
    return result


def compact_tool_calls_for_memory(
    executed_calls: list[dict],
    deferred_count: int = 0,
) -> str:
    """Build compact text replacing raw ``<tool_call>`` XML in memory.

    After tool calls are parsed and executed, the verbose JSON in
    ``<tool_call>`` blocks is dead weight.  Replace with a brief
    ``name(key_args)`` per call.
    """
    lines: list[str] = []
    for tc in executed_calls:
        name = tc.get("name", "?")
        short_args = compact_short_args(tc.get("arguments", {}), max_chars=80)
        lines.append(f"{TAG_TOOL_CALL_OPEN}{name}({short_args}){TAG_TOOL_CALL_CLOSE}")
    if deferred_count > 0:
        lines.append(f"{TAG_WAIT} ({deferred_count} deferred)")
    return "\n".join(lines)


def stage_compact_batch(
    tool_calls: list[dict],
    tool_results: list[str],
    *,
    note_chars: int = 200,
) -> str:
    """Compact a parallel batch of tool results into a summary table.

    Parameters
    ----------
    tool_calls : list[dict]
        Each dict has ``name`` and ``arguments`` keys.
    tool_results : list[str]
        Corresponding result text for each tool call.
    note_chars : int
        Max chars for the preview note column.

    Returns
    -------
    str  — markdown table summarising the batch.
    """
    n = len(tool_calls)
    lines = [
        f"**Parallel batch: {n} tools executed**\n",
        "| # | Tool | Args | Chars | Note |",
        "|---|------|------|------:|------|",
    ]
    for i, (tc, result_text) in enumerate(zip(tool_calls, tool_results), 1):
        name = tc.get("name", "?")
        args = compact_short_args(tc.get("arguments", {}))
        chars = len(result_text)
        note = extract_note(result_text, max_chars=note_chars)
        lines.append(f"| {i} | {name} | {args} | {chars} | {note} |")
    return "\n".join(lines) + "\n"


def trim_old_tool_results(
    memory: list[dict],
    *,
    keep_recent: int = 2,
    preview_chars: int = 800,
) -> None:
    """Compress old ``<tool_result>`` entries in the memory list.

    Preserves the most recent *keep_recent* tool_result entries intact.
    Older entries get their body truncated to a short preview plus a
    "trimmed" note.

    Parameters
    ----------
    memory : list[dict]
        Mutable list of ``{"role": …, "content": …}`` dicts.
    keep_recent : int
        Number of latest tool_result entries to leave untouched.
    preview_chars : int
        Characters to keep from old entries.
    """
    result_indices = [
        i for i, m in enumerate(memory)
        if m["role"] == "user" and TAG_TOOL_RESULT_OPEN in m["content"]
    ]
    if len(result_indices) <= keep_recent:
        return

    to_trim = result_indices[:-keep_recent]
    for idx in to_trim:
        content = memory[idx]["content"]
        if len(content) <= preview_chars + 100:
            continue
        preview = content[:preview_chars]
        omitted = len(content) - preview_chars
        memory[idx]["content"] = (
            f"{preview}\n\n... ({omitted:,} chars trimmed from earlier result) ..."
        )


# ═══════════════════════════════════════════════════════════════
#  Base dataclass — subclass in each agent's compactor_hooks/
# ═══════════════════════════════════════════════════════════════

@dataclass
class StageCompactor:
    """Deterministic compaction engine — one instance per agent.

    Subclass in ``<agent>_context_hooks/compactor_hooks/`` and
    override numeric fields to tune per agent.
    """

    stage_compact_budget: int = 8_000
    stage_note_chars: int = 200
    keep_recent: int = 2
    preview_chars: int = 800

    def extract_note(self, text: str, max_chars: int | None = None) -> str:
        return extract_note(text, max_chars=max_chars or self.stage_note_chars)

    def compact_short_args(self, raw_args: dict[str, Any], max_chars: int = 60) -> str:
        return compact_short_args(raw_args, max_chars=max_chars)

    def compact_tool_calls_for_memory(
        self, executed_calls: list[dict], deferred_count: int = 0,
    ) -> str:
        return compact_tool_calls_for_memory(executed_calls, deferred_count)

    def stage_compact_batch(
        self, tool_calls: list[dict], tool_results: list[str],
    ) -> str:
        return stage_compact_batch(
            tool_calls, tool_results, note_chars=self.stage_note_chars,
        )

    def trim_old_tool_results(self, memory: list[dict]) -> None:
        return trim_old_tool_results(
            memory,
            keep_recent=self.keep_recent,
            preview_chars=self.preview_chars,
        )
