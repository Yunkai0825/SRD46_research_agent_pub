"""
Time-budget reminder hook for the ReAct loop.
==============================================
Tracks effective agent time against configurable thresholds and injects
progressive ``[TIME REMINDER …]`` messages into conversation memory.

The configured value is a *reminder scale*, not a deadline. Crossing it
must never stop a ReAct loop, suppress a requested tool call, or force a
tool-free final response. Completion remains governed by the agent's
explicit terminal contract and maximum-turn setting.

Usage::

    from ...general_context_hooks.time_budget_reminder_hooks import TimeBudgetTracker

    tracker = TimeBudgetTracker(timeout=1000,
                                thresholds=[0.65, 0.85, 0.95],
                                max_warnings=3)

    # Inside each iteration:
    tracker.check_and_inject_warnings(elapsed, memory)

    # Continue normally. Reminder thresholds never terminate the loop.
"""

from __future__ import annotations

import logging
from typing import List

log = logging.getLogger("time-budget")

class TimeBudgetTracker:
    """Stateful tracker for effective-time reminders in one agent turn."""

    def __init__(
        self,
        timeout: float,
        thresholds: list[float],
        max_warnings: int,
    ) -> None:
        self._timeout = timeout
        self._thresholds = thresholds
        self._max_warnings = max_warnings
        self._warnings_fired = 0
        # Wall-clock seconds spent inside tool calls the caller has
        # explicitly asked to EXCLUDE from the turn budget (e.g. a
        # long-running deterministic pipeline tool). Credited via
        # :meth:`credit` and subtracted from every elapsed comparison so
        # that only the agent's own reasoning/LLM time counts against the
        # deadline.
        self._excluded = 0.0

    # ── read-only state ──────────────────────────────────────

    @property
    def warnings_fired(self) -> int:
        return self._warnings_fired

    @property
    def all_warnings_fired(self) -> bool:
        """Whether every configured reminder has been emitted.

        This is telemetry only. Callers must not use it as a completion or
        tool-execution gate.
        """
        return self._warnings_fired >= self._max_warnings

    @property
    def excluded(self) -> float:
        """Total seconds credited back to the budget so far."""
        return self._excluded

    # ── budget crediting ─────────────────────────────────────

    def credit(self, seconds: float) -> float:
        """Exclude *seconds* of tool time from the turn budget.

        Returns the new cumulative excluded total. Negative / non-finite
        inputs are ignored so a misbehaving tool clock can never *extend*
        the deadline backwards.
        """
        try:
            s = float(seconds)
        except (TypeError, ValueError):
            return self._excluded
        if s > 0.0:
            self._excluded += s
            log.info("Time budget: credited %.1fs (excluded total %.1fs)",
                     s, self._excluded)
        return self._excluded

    # ── core behaviour ───────────────────────────────────────

    def check_and_inject_warnings(
        self,
        elapsed: float,
        memory: List[dict],
    ) -> int:
        """Append any newly-exceeded time-warning messages to *memory*.

        Uses a while-loop so that if a single long tool call spans
        multiple thresholds (e.g. 0 %→90 %), ALL exceeded warnings
        fire in the same iteration rather than one-per-turn.

        Returns the number of new warnings injected.
        """
        effective = max(0.0, elapsed - self._excluded)
        count = 0
        while self._warnings_fired < self._max_warnings:
            threshold = self._thresholds[self._warnings_fired]
            if effective > self._timeout * threshold:
                pct = int(threshold * 100)
                warning = (
                    f"[TIME REMINDER {self._warnings_fired + 1}/"
                    f"{self._max_warnings}] "
                    f"{pct}% of the effective-time reminder scale reached "
                    f"({effective:.0f}s / {self._timeout}s). "
                    "Plan the remaining turns carefully; this reminder does "
                    "not prevent further tool use or force completion."
                )
                memory.append({"role": "user", "content": warning})
                self._warnings_fired += 1
                count += 1
                log.warning(warning)
            else:
                break
        return count

    def is_hard_stop(self, elapsed: float) -> bool:
        """Compatibility shim: effective-time reminders never hard-stop.

        Kept temporarily for hook catalogs compiled against the former
        interface. New code must not call this method.
        """
        return False

    @staticmethod
    def make_final_warning_message() -> str:
        """Return a non-terminal compatibility reminder."""
        return (
            "[TIME REMINDER] The effective-time reminder scale has been "
            "reached. Continue only with useful work and complete the "
            "required terminal contract when ready; tool use remains allowed."
        )
