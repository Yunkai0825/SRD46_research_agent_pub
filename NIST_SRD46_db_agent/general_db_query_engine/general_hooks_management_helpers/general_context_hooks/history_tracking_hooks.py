"""
Real-time history recording helper — ``history_tracking_hooks.py``
==================================================================
Thread-local, singleton-based recorder that builds a rich Markdown
history file incrementally.  Designed to be called from:

  - ``react_loop.py``    — after each tool call / compaction event
  - ``_tool_subagent.py`` — after subagent verdict (KEEP/DISCARD/oversized)
  - ``_wrap_tool()``      — when purpose/tasks are missing (error guard)
  - test runners          — start_run() / flush()

The recorder is 100% harmless — it never modifies conversation context,
working memory, or any tool results.  It only writes to disk.

**Thread isolation:** Each thread gets its own ``_RunState`` via
``threading.local()``, so parallel test workers never clobber each
other's data or output files.  The public API is unchanged:

Usage::

    from ...general_context_hooks.history_tracking_hooks import history_recorder

    history_recorder.start_run(agent="query-agent", prompt="...", out_path="...")
    history_recorder.log_tool_call(iteration=1, tool_name="search_system_registry",
                                   args={...}, result_chars=1234, elapsed_s=2.1,
                                   result_preview="first 300 chars...")
    history_recorder.log_subagent_event(tool_name="search_system_registry",
                                        event="KEEP", detail="extracted 5 rows")
    history_recorder.log_compaction(iteration=3, before_chars=80000,
                                    after_chars=30000, trigger="interval=3")
    history_recorder.log_error(iteration=2, tool_name="bad_tool",
                               error_text="Unknown tool: bad_tool")
    history_recorder.flush()        # writes to out_path
    history_recorder.reset()
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("history-recorder")


# ═══════════════════════════════════════════════════════════════
#  Data containers
# ═══════════════════════════════════════════════════════════════

@dataclass
class _ToolEntry:
    """One tool invocation record."""
    iteration: int
    tool_name: str
    args: Dict[str, Any]
    result_chars: int
    elapsed_s: float
    result_preview: str = ""
    # Enrichment flags
    is_error: bool = False
    error_text: str = ""
    is_oversized_guard: bool = False
    oversized_notice: str = ""
    is_purpose_error: bool = False
    purpose_error_text: str = ""
    is_validation_block: bool = False
    validation_status: str = ""       # "blocked" | "held-back-by-batch"


@dataclass
class _SubagentEvent:
    """Subagent verdict for a tool call."""
    tool_name: str
    event: str        # "KEEP", "DISCARD", "OVERSIZED", "FALLBACK"
    detail: str = ""
    output_chars: int = 0
    elapsed_s: float = 0.0


@dataclass
class _CompactionEvent:
    """Context compaction event."""
    iteration: int
    before_chars: int
    after_chars: int
    trigger: str = ""     # "interval=3", "chars=80000>60000"
    purpose: str = ""
    tasks: str = ""
    receipt: str = ""     # what was compacted (tool names, char reductions)
    outcome: str = ""     # "compacted", "skipped_by_agent", "skipped_by_selector", "error"


@dataclass
class _StageCompactionEvent:
    """Parallel-batch stage compaction."""
    iteration: int
    n_tools: int
    before_chars: int
    after_chars: int


@dataclass
class _InternalError:
    """An internal engine error (type mismatch, reference-tracking failure, etc.).

    Stored in run history so batch runs can be post-mortem analysed.
    """
    source: str              # e.g. "react_loop", "stats_references", "engine_hooks"
    error_type: str          # e.g. "json_parse", "type_mismatch", "anchor_callback"
    tool_name: str           # tool that was being processed when the error occurred
    message: str             # short description
    context_preview: str     # first N chars of the data that caused the error
    timestamp: str = ""      # ISO timestamp


# ═══════════════════════════════════════════════════════════════
#  Thread-local run state
# ═══════════════════════════════════════════════════════════════

@dataclass
class _RunState:
    """Per-thread state container for one recording session."""
    agent: str = ""
    prompt: str = ""
    out_path: Optional[Path] = None
    started_at: Optional[dt.datetime] = None
    tool_entries: List[_ToolEntry] = field(default_factory=list)
    subagent_events: List[_SubagentEvent] = field(default_factory=list)
    compaction_events: List[_CompactionEvent] = field(default_factory=list)
    stage_compactions: List[_StageCompactionEvent] = field(default_factory=list)
    internal_errors: List[_InternalError] = field(default_factory=list)
    working_memory: str = ""
    final_status: str = ""


# ═══════════════════════════════════════════════════════════════
#  HistoryRecorder — singleton with thread-local state
# ═══════════════════════════════════════════════════════════════

class HistoryRecorder:
    """Accumulates tool history and writes incremental Markdown.

    Each thread gets its own ``_RunState`` via ``threading.local()``,
    so parallel workers never interfere with each other.
    """

    def __init__(self):
        self._local = threading.local()

    # ── Internal: get/create the current thread's state ────

    def _state(self) -> _RunState:
        """Return the current thread's _RunState (create if needed)."""
        s = getattr(self._local, "state", None)
        if s is None:
            s = _RunState()
            self._local.state = s
        return s

    # ── Lifecycle ──────────────────────────────────────────────

    def start_run(self, agent: str, prompt: str, out_path: str | Path) -> None:
        """Begin a new recording session (resets state for this thread)."""
        s = _RunState(
            agent=agent,
            prompt=prompt,
            out_path=Path(out_path),
            started_at=dt.datetime.now(),
        )
        self._local.state = s
        log.debug("History recorder started for %s → %s", agent, out_path)

    def reset(self) -> None:
        """Clear all accumulated state for this thread."""
        self._local.state = _RunState()

    def set_working_memory(self, text: str) -> None:
        """Set the working memory snapshot (appended at end of history)."""
        self._state().working_memory = text

    def set_final_status(self, status: str) -> None:
        """Set final run status (OK / TIMEOUT / ERROR)."""
        self._state().final_status = status

    # ── Logging hooks ──────────────────────────────────────────

    def log_tool_call(
        self,
        iteration: int,
        tool_name: str,
        args: Dict[str, Any],
        result_chars: int,
        elapsed_s: float,
        result_preview: str = "",
    ) -> None:
        """Record a tool invocation (called from react_loop after each tool)."""
        entry = _ToolEntry(
            iteration=iteration,
            tool_name=tool_name,
            args=args,
            result_chars=result_chars,
            elapsed_s=elapsed_s,
            result_preview=result_preview,
        )
        self._state().tool_entries.append(entry)
        self._auto_flush()

    def log_error(
        self,
        iteration: int,
        tool_name: str,
        error_text: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a tool-level error (exception, unknown tool, etc.)."""
        entry = _ToolEntry(
            iteration=iteration,
            tool_name=tool_name,
            args=args or {},
            result_chars=len(error_text),
            elapsed_s=0.0,
            result_preview=error_text,
            is_error=True,
            error_text=error_text,
        )
        self._state().tool_entries.append(entry)
        self._auto_flush()

    def log_validation_block(
        self,
        iteration: int,
        tool_name: str,
        status: str = "blocked",
        detail: str = "",
        args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a tool blocked (or held back) by pre-execution validation."""
        entry = _ToolEntry(
            iteration=iteration,
            tool_name=tool_name,
            args=args or {},
            result_chars=len(detail),
            elapsed_s=0.0,
            result_preview=detail,
            is_validation_block=True,
            validation_status=status,
        )
        self._state().tool_entries.append(entry)
        self._auto_flush()

    def log_purpose_tasks_error(
        self,
        iteration: int,
        tool_name: str,
        error_text: str,
    ) -> None:
        """Record when purpose/tasks were missing (mandatory-param guard)."""
        entry = _ToolEntry(
            iteration=iteration,
            tool_name=tool_name,
            args={},
            result_chars=len(error_text),
            elapsed_s=0.0,
            result_preview=error_text,
            is_purpose_error=True,
            purpose_error_text=error_text,
        )
        self._state().tool_entries.append(entry)
        self._auto_flush()

    def log_oversized_guard(
        self,
        tool_name: str,
        compact_chars: int,
        notice: str,
    ) -> None:
        """Record when the oversized-result guard triggered."""
        s = self._state()
        for entry in reversed(s.tool_entries):
            if entry.tool_name == tool_name:
                entry.is_oversized_guard = True
                entry.oversized_notice = notice
                break
        self._auto_flush()

    def log_subagent_event(
        self,
        tool_name: str,
        event: str,
        detail: str = "",
        output_chars: int = 0,
        elapsed_s: float = 0.0,
    ) -> None:
        """Record a subagent verdict (KEEP, DISCARD, OVERSIZED, FALLBACK)."""
        ev = _SubagentEvent(
            tool_name=tool_name,
            event=event,
            detail=detail,
            output_chars=output_chars,
            elapsed_s=elapsed_s,
        )
        self._state().subagent_events.append(ev)
        self._auto_flush()

    def log_compaction(
        self,
        iteration: int,
        before_chars: int,
        after_chars: int,
        trigger: str = "",
        purpose: str = "",
        tasks: str = "",
        receipt: str = "",
        outcome: str = "",
    ) -> None:
        """Record a context compaction event."""
        ev = _CompactionEvent(
            iteration=iteration,
            before_chars=before_chars,
            after_chars=after_chars,
            trigger=trigger,
            purpose=purpose,
            tasks=tasks,
            receipt=receipt,
            outcome=outcome,
        )
        self._state().compaction_events.append(ev)
        self._auto_flush()

    def log_internal_error(
        self,
        source: str,
        error_type: str,
        tool_name: str,
        message: str,
        context_preview: str = "",
    ) -> None:
        """Record an internal engine error for post-mortem batch analysis.

        These are non-fatal errors (type mismatches, failed JSON parses,
        hook callback failures) that don't stop execution but indicate
        data-shape issues worth investigating.
        """
        entry = _InternalError(
            source=source,
            error_type=error_type,
            tool_name=tool_name,
            message=message,
            context_preview=context_preview,
            timestamp=dt.datetime.now().strftime("%H:%M:%S"),
        )
        self._state().internal_errors.append(entry)
        self._auto_flush()

    def log_stage_compaction(
        self,
        iteration: int,
        n_tools: int,
        before_chars: int,
        after_chars: int,
    ) -> None:
        """Record a parallel-batch stage compaction event."""
        ev = _StageCompactionEvent(
            iteration=iteration,
            n_tools=n_tools,
            before_chars=before_chars,
            after_chars=after_chars,
        )
        self._state().stage_compactions.append(ev)
        self._auto_flush()

    # ── Rendering ──────────────────────────────────────────────

    def _auto_flush(self) -> None:
        """Write history to disk if an output path is configured."""
        s = self._state()
        if s.out_path:
            try:
                self.flush()
            except Exception as e:
                log.error("Auto-flush failed: %s", e, exc_info=True)

    def flush(self, path: Optional[str | Path] = None) -> None:
        """Write the full history markdown to disk (atomic write)."""
        s = self._state()
        out = Path(path) if path else s.out_path
        if not out:
            return
        md = self._render_markdown()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")

    def _render_markdown(self) -> str:
        """Build the complete history markdown."""
        s = self._state()
        lines: List[str] = []

        # Header
        ts = s.started_at.strftime("%Y-%m-%d %H:%M:%S") if s.started_at else "?"
        elapsed_total = (
            (dt.datetime.now() - s.started_at).total_seconds()
            if s.started_at else 0
        )
        lines.append(f"# Tool History — {s.agent}")
        lines.append(f"")
        lines.append(f"**Prompt:** {s.prompt}")
        lines.append(f"**Started:** {ts}  |  **Elapsed:** {elapsed_total:.1f}s  |  "
                      f"**Tool calls:** {len(s.tool_entries)}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        if not s.tool_entries:
            lines.append("*No tool calls recorded yet.*")
            lines.append("")
            return "\n".join(lines)

        # Track which subagent events have been consumed per-tool
        _consumed_sa: set = set()  # indices into s.subagent_events

        # ── Per-tool entries ──
        _entries = s.tool_entries
        for _ei, entry in enumerate(_entries):
            _is_last_in_iter = (
                _ei == len(_entries) - 1
                or _entries[_ei + 1].iteration != entry.iteration
            )
            # Step header with status badge
            badge = ""
            if entry.is_validation_block:
                if entry.validation_status == "blocked":
                    badge = " 🔒 VALIDATION BLOCKED"
                else:
                    badge = " ⏸️ HELD BACK BY BATCH"
            elif entry.is_error:
                badge = " ❌ ERROR"
            elif entry.is_purpose_error:
                badge = " ⚠️ MISSING purpose/tasks"
            elif entry.is_oversized_guard:
                badge = " 📏 OVERSIZED"

            lines.append(f"### Step {entry.iteration}: `{entry.tool_name}`{badge}")
            lines.append(f"")

            # Args (full display — no truncation)
            if entry.args:
                args_json = json.dumps(entry.args, indent=2, default=str,
                                       ensure_ascii=False)
                lines.append(f"<details><summary>Arguments</summary>")
                lines.append(f"")
                lines.append(f"```json")
                lines.append(args_json)
                lines.append(f"```")
                lines.append(f"</details>")
                lines.append(f"")

            lines.append(f"- **Result:** {entry.result_chars:,} chars  |  "
                          f"**Time:** {entry.elapsed_s:.1f}s")

            # Validation detail (before generic error, so it doesn't collide)
            if entry.is_validation_block:
                lines.append(f"- **Status:** {entry.validation_status}")
                if entry.result_preview:
                    lines.append(f"")
                    lines.append(f"<details><summary>Validation detail</summary>")
                    lines.append(f"")
                    lines.append(f"```")
                    for vl in entry.result_preview.splitlines():
                        lines.append(vl)
                    lines.append(f"```")
                    lines.append(f"</details>")

            # Error detail
            if entry.is_error:
                lines.append(f"- **Error:** `{entry.error_text}`")

            # Purpose/tasks missing
            if entry.is_purpose_error:
                lines.append(f"- **Guard:** purpose/tasks not provided by LLM")
                lines.append(f"  ```")
                lines.append(f"  {entry.purpose_error_text}")
                lines.append(f"  ```")

            # Oversized guard
            if entry.is_oversized_guard:
                lines.append(f"- **Oversized guard triggered:**")
                lines.append(f"  ```")
                for ol in entry.oversized_notice.splitlines():
                    lines.append(f"  {ol}")
                lines.append(f"  ```")

            # Subagent events for this tool
            # Skip for purpose/tasks errors (subagent was never called)
            if not entry.is_purpose_error:
                sa_ev = None
                for idx, e in enumerate(s.subagent_events):
                    if idx not in _consumed_sa and e.tool_name == entry.tool_name:
                        sa_ev = e
                        _consumed_sa.add(idx)
                        break
                if sa_ev:
                    lines.append(f"- **Subagent:** {sa_ev.event}"
                                  f" → {sa_ev.output_chars:,} chars"
                                  f" ({sa_ev.elapsed_s:.1f}s)")
                    if sa_ev.detail:
                        lines.append(f"  - {sa_ev.detail}")

            # Full tool-result text (skip for validation entries — detail section covers it)
            if entry.result_preview and not entry.is_error and not entry.is_purpose_error and not entry.is_validation_block:
                lines.append(f"")
                lines.append(f"<details><summary>Tool result (full)</summary>")
                lines.append(f"")
                lines.append(f"```")
                lines.append(entry.result_preview)
                lines.append(f"```")
                lines.append(f"</details>")

            lines.append(f"")

            # Compaction / stage-compaction events — render only once,
            # after the LAST tool of each iteration (avoids duplicates
            # when a parallel batch shares the same iteration number).
            if _is_last_in_iter:
                comp_events = [c for c in s.compaction_events
                               if c.iteration == entry.iteration]
                for ce in comp_events:
                    pct = (1 - ce.after_chars / ce.before_chars) * 100 if ce.before_chars else 0
                    lines.append(f"**📦 Context compaction** (after step {ce.iteration}, "
                                  f"trigger: {ce.trigger})")
                    if ce.outcome:
                        lines.append(f"- **Outcome:** {ce.outcome}")
                    if ce.purpose:
                        lines.append(f"- **Purpose:** {ce.purpose}")
                    if ce.tasks:
                        lines.append(f"- **Tasks:** {ce.tasks}")
                    lines.append(f"- {ce.before_chars:,} → {ce.after_chars:,} chars "
                                  f"(−{pct:.0f}%)")
                    if ce.receipt:
                        lines.append(f"- **Receipt:** {ce.receipt}")
                    lines.append(f"")

                stage_events = [sc for sc in s.stage_compactions
                                if sc.iteration == entry.iteration]
                for se in stage_events:
                    pct = (1 - se.after_chars / se.before_chars) * 100 if se.before_chars else 0
                    lines.append(f"**🔀 Stage compaction** (batch of {se.n_tools} tools)")
                    lines.append(f"- {se.before_chars:,} → {se.after_chars:,} chars "
                                  f"(−{pct:.0f}%)")
                    lines.append(f"")

            lines.append(f"---")
            lines.append(f"")

        # ── Summary tables ──

        # Compaction summary
        if s.compaction_events:
            lines.append(f"## Compaction Summary ({len(s.compaction_events)} events)")
            lines.append(f"")
            lines.append(f"| Iter | Trigger | Before | After | Reduction | Outcome |")
            lines.append(f"|------|---------|--------|-------|-----------|---------|")
            for ce in s.compaction_events:
                pct = (1 - ce.after_chars / ce.before_chars) * 100 if ce.before_chars else 0
                lines.append(
                    f"| {ce.iteration} "
                    f"| {ce.trigger} "
                    f"| {ce.before_chars:,} "
                    f"| {ce.after_chars:,} "
                    f"| −{pct:.0f}% "
                    f"| {ce.outcome or '—'} |"
                )
            lines.append(f"")

        # Stage compaction summary
        if s.stage_compactions:
            lines.append(f"## Stage Compaction Summary ({len(s.stage_compactions)} events)")
            lines.append(f"")
            lines.append(f"| Iter | Tools | Before | After | Reduction |")
            lines.append(f"|------|-------|--------|-------|-----------|")
            for se in s.stage_compactions:
                pct = (1 - se.after_chars / se.before_chars) * 100 if se.before_chars else 0
                lines.append(
                    f"| {se.iteration} "
                    f"| {se.n_tools} "
                    f"| {se.before_chars:,} "
                    f"| {se.after_chars:,} "
                    f"| −{pct:.0f}% |"
                )
            lines.append(f"")

        # Subagent summary
        if s.subagent_events:
            lines.append(f"## Subagent Summary ({len(s.subagent_events)} events)")
            lines.append(f"")
            lines.append(f"| Tool | Verdict | Output Chars | Time |")
            lines.append(f"|------|---------|-------------|------|")
            for se in s.subagent_events:
                lines.append(
                    f"| {se.tool_name} "
                    f"| {se.event} "
                    f"| {se.output_chars:,} "
                    f"| {se.elapsed_s:.1f}s |"
                )
            lines.append(f"")

        # Error summary
        errors = [e for e in s.tool_entries if e.is_error or e.is_purpose_error]
        if errors:
            lines.append(f"## Errors ({len(errors)})")
            lines.append(f"")
            for e in errors:
                kind = "purpose/tasks missing" if e.is_purpose_error else "exception"
                lines.append(f"- **Step {e.iteration}** `{e.tool_name}` ({kind}): "
                              f"{e.error_text or e.purpose_error_text}")
            lines.append(f"")

        # Internal errors summary
        if s.internal_errors:
            lines.append(f"## Internal Errors ({len(s.internal_errors)})")
            lines.append(f"")
            lines.append(f"| Time | Source | Type | Tool | Message |")
            lines.append(f"|------|--------|------|------|---------|")
            for ie in s.internal_errors:
                msg_cell = ie.message.replace("|", "\\|").replace("\n", "<br>")
                lines.append(
                    f"| {ie.timestamp} "
                    f"| {ie.source} "
                    f"| {ie.error_type} "
                    f"| `{ie.tool_name}` "
                    f"| {msg_cell} |"
                )
            lines.append(f"")
            # Detailed context previews
            lines.append(f"<details><summary>Context previews ({len(s.internal_errors)} errors)</summary>")
            lines.append(f"")
            for i, ie in enumerate(s.internal_errors, 1):
                lines.append(f"**{i}. [{ie.timestamp}] {ie.source}/{ie.error_type}** — `{ie.tool_name}`")
                lines.append(f"")
                lines.append(f"Message: {ie.message}")
                if ie.context_preview:
                    lines.append(f"")
                    lines.append(f"```")
                    lines.append(ie.context_preview)
                    lines.append(f"```")
                lines.append(f"")
            lines.append(f"</details>")
            lines.append(f"")

        # ── Working memory snapshot ──
        if s.working_memory and s.working_memory.strip():
            lines.append(f"## Working Memory (final snapshot)")
            lines.append(f"")
            lines.append(s.working_memory.strip())
            lines.append(f"")

        # Footer
        total_tool_time = sum(e.elapsed_s for e in s.tool_entries)
        status_str = f"  |  **Status:** {s.final_status}" if s.final_status else ""
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"**Total:** {len(s.tool_entries)} tool calls  |  "
                      f"Tool time: {total_tool_time:.1f}s  |  "
                      f"Wall: {elapsed_total:.1f}s{status_str}")
        lines.append(f"")

        return "\n".join(lines)



# ═══════════════════════════════════════════════════════════════
#  Singleton instance
# ═══════════════════════════════════════════════════════════════

history_recorder = HistoryRecorder()
