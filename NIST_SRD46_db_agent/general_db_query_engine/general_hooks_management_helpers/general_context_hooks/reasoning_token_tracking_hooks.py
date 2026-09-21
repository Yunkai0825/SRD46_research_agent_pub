"""
Real-time reasoning token tracker — ``reasoning_token_tracking_hooks.py``
=========================================================================
Thread-local, singleton-based tracker that captures every
``<reasoning>…</reasoning>`` block emitted by the LLM and writes them
incrementally to ``reasoning_tokens_stripped.md`` in the session folder.

The hook fires **immediately after the Argo response is received** —
before tool-call extraction, compaction, or any other processing — so it
captures the raw reasoning tokens exactly as the model produced them.

Like the other tracking hooks, this module is 100% harmless: it never
modifies the conversation context, working memory, or tool results.  It
only writes to disk.

Thread isolation
~~~~~~~~~~~~~~~~
Each thread gets its own ``_RunState`` via ``threading.local()``, so
parallel test workers never clobber each other's data or output files.

Usage::

    from ...general_context_hooks.reasoning_token_tracking_hooks import (
        reasoning_tracker,
    )

    reasoning_tracker.start_run(agent="main-agent",
                                out_path=".../reasoning_tokens_stripped.md")
    # Called from react_loop immediately after client.call():
    reasoning_tracker.log_reasoning_from_response(iteration=1, response=raw_llm)
    reasoning_tracker.flush()
    reasoning_tracker.reset()
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from ...general_text_context_marker_catalog import MARKERS

REASONING_BLOCK_RE = MARKERS.reasoning_re

log = logging.getLogger("reasoning-tracker")

# Also capture <thought> blocks (used by tool subagent compactors)
_THOUGHT_BLOCK_RE = re.compile(r"<thought>(.*?)</thought>", re.DOTALL)


# ═══════════════════════════════════════════════════════════════
#  Data container
# ═══════════════════════════════════════════════════════════════

@dataclass
class _ReasoningEntry:
    """One captured reasoning block."""
    iteration: int
    timestamp: str
    text: str
    char_count: int
    source: str = ""  # e.g. "", "compaction-guidance", "subagent/search_blocks"


# ═══════════════════════════════════════════════════════════════
#  Thread-local run state
# ═══════════════════════════════════════════════════════════════

@dataclass
class _RunState:
    """Per-thread state container for one recording session."""
    agent: str = ""
    out_path: Optional[Path] = None
    started_at: Optional[dt.datetime] = None
    entries: List[_ReasoningEntry] = field(default_factory=list)
    total_reasoning_chars: int = 0
    final_status: str = ""


# ═══════════════════════════════════════════════════════════════
#  ReasoningTokenTracker — singleton with thread-local state
# ═══════════════════════════════════════════════════════════════

class ReasoningTokenTracker:
    """Captures ``<reasoning>`` blocks from raw LLM responses.

    Designed to be called from ``react_loop.py`` immediately after
    ``client.call()`` — before any other processing.
    """

    def __init__(self):
        self._local = threading.local()

    # ── Internal: get/create the current thread's state ────

    def _state(self) -> _RunState:
        s = getattr(self._local, "state", None)
        if s is None:
            s = _RunState()
            self._local.state = s
        return s

    # ── Lifecycle ──────────────────────────────────────────────

    def start_run(self, agent: str, out_path: str | Path) -> None:
        """Begin a new recording session (resets state for this thread)."""
        s = _RunState(
            agent=agent,
            out_path=Path(out_path),
            started_at=dt.datetime.now(),
        )
        self._local.state = s
        # Write initial header immediately
        self._auto_flush()
        log.debug("Reasoning tracker started for %s → %s", agent, out_path)

    def reset(self) -> None:
        """Clear all accumulated state for this thread."""
        self._local.state = _RunState()

    def set_final_status(self, status: str) -> None:
        """Set final run status (OK / TIMEOUT / ERROR)."""
        self._state().final_status = status

    # ── Core logging hook ──────────────────────────────────────

    def log_reasoning_from_response(
        self,
        iteration: int,
        response: str,
        *,
        source: str = "",
    ) -> None:
        """Extract and log all ``<reasoning>`` and ``<thought>`` blocks.

        Called from ``react_loop.py`` immediately after ``client.call()``,
        before tool-call parsing or any other processing.  Also used
        for compactor / guidance LLM calls via the *source* label.
        """
        # Extract both <reasoning> and <thought> blocks
        matches = REASONING_BLOCK_RE.findall(response)
        thought_matches = _THOUGHT_BLOCK_RE.findall(response)
        all_matches = matches + thought_matches
        if not all_matches:
            return

        ts = dt.datetime.now().strftime("%H:%M:%S")
        s = self._state()
        for text in all_matches:
            char_count = len(text)
            entry = _ReasoningEntry(
                iteration=iteration,
                timestamp=ts,
                text=text,
                char_count=char_count,
                source=source,
            )
            s.entries.append(entry)
            s.total_reasoning_chars += char_count

        self._auto_flush()

    def log_compactor_reasoning(
        self,
        source: str,
        response: str,
    ) -> None:
        """Capture reasoning from compactor / subagent LLM responses.

        Convenience wrapper that uses ``iteration=0`` and the given
        *source* label (e.g. ``"subagent/search_blocks"``,
        ``"interactive-compact/select"``).
        """
        self.log_reasoning_from_response(0, response, source=source)

    def make_reasoning_hook(self) -> Callable[[str, str], None]:
        """Return a ``(source, response) -> None`` callback for compactors."""
        return self.log_compactor_reasoning

    # ── Rendering ──────────────────────────────────────────────

    def _auto_flush(self) -> None:
        """Write to disk if an output path is configured."""
        s = self._state()
        if s.out_path:
            try:
                self.flush()
            except Exception as e:
                log.error("Auto-flush failed: %s", e, exc_info=True)

    def flush(self, path: Optional[str | Path] = None) -> None:
        """Write the full reasoning log to disk (atomic write)."""
        s = self._state()
        out = Path(path) if path else s.out_path
        if not out:
            return
        md = self._render_markdown()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")

    def _render_markdown(self) -> str:
        """Build the complete reasoning tokens markdown."""
        s = self._state()
        lines: List[str] = []

        # Header
        ts = s.started_at.strftime("%Y-%m-%d %H:%M:%S") if s.started_at else "?"
        lines.append(f"# Reasoning Tokens Stripped — {s.agent}")
        lines.append(f"")
        lines.append(f"**Started:** {ts}")
        lines.append(f"**Total reasoning blocks:** {len(s.entries)}")
        lines.append(f"**Total reasoning chars:** {s.total_reasoning_chars:,}")
        if s.final_status:
            lines.append(f"**Final status:** {s.final_status}")
        lines.append("")
        lines.append("---")
        lines.append("")

        if not s.entries:
            lines.append("*No reasoning tokens captured yet.*")
            return "\n".join(lines) + "\n"

        # Each reasoning block
        for i, entry in enumerate(s.entries, 1):
            src_label = f" ({entry.source})" if entry.source else ""
            lines.append(
                f"## Turn {entry.iteration}{src_label} — block {i} "
                f"({entry.char_count:,} chars) [{entry.timestamp}]"
            )
            lines.append("")
            lines.append(entry.text)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Footer summary
        lines.append(f"## Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total blocks | {len(s.entries)} |")
        lines.append(f"| Total chars | {s.total_reasoning_chars:,} |")

        # Per-turn breakdown
        turn_map: dict[int, int] = {}
        for entry in s.entries:
            turn_map[entry.iteration] = (
                turn_map.get(entry.iteration, 0) + entry.char_count
            )
        if turn_map:
            lines.append(f"| Turns with reasoning | {len(turn_map)} |")
            avg = s.total_reasoning_chars // max(len(turn_map), 1)
            lines.append(f"| Avg chars/turn | {avg:,} |")
        lines.append("")

        return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════
#  Module-level singleton
# ═══════════════════════════════════════════════════════════════

reasoning_tracker = ReasoningTokenTracker()

# Thread-local "active" reasoning tracker — set by
# `set_active_reasoning_tracker()` during start_tracking so that
# any code needing the current agent's tracker can retrieve it.
_active_ref = threading.local()


def set_active_reasoning_tracker(tracker: ReasoningTokenTracker) -> None:
    """Designate *tracker* as the active reasoning tracker for this thread."""
    _active_ref.tracker = tracker


def get_active_reasoning_tracker() -> ReasoningTokenTracker:
    """Return the active reasoning tracker (agent-specific or base fallback)."""
    return getattr(_active_ref, "tracker", None) or reasoning_tracker


def clear_active_reasoning_tracker() -> None:
    """Remove the thread-local active reasoning tracker reference."""
    _active_ref.tracker = None
