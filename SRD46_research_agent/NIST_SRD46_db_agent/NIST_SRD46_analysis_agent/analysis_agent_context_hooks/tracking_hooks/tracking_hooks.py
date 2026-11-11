"""
Tracking hooks — history + stats + verdict-trace recorders.
============================================================

The pipeline driver writes per-phase summaries into ``manifest.json``;
these hooks add a finer-grained, append-only record of every L1 worker
call, every LD verdict, and every retry. Used by the eval pipeline to
reconstruct what the agent did.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("Analysis.Tracking")


@dataclass
class AnalysisHistoryRecorder:
    """Append-only ``run_history.jsonl`` per session."""

    session_dir: Path
    filename: str = "run_history.jsonl"

    def __post_init__(self):
        self.session_dir = Path(self.session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.session_dir / self.filename

    def log(self, event_type: str, **payload: Any) -> None:
        rec = {
            "ts": time.time(),
            "event": event_type,
            **payload,
        }
        try:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
        except Exception as exc:                    # pragma: no cover
            log.warning("history log failed: %s", exc)

    # Convenience shorthands matching the query agent's API style.
    def log_phase_start(self, phase_id: str) -> None:
        self.log("phase_start", phase_id=phase_id)

    def log_phase_end(self, phase_id: str, status: str, ld_verdict: str,
                      retries: int, elapsed_s: float) -> None:
        self.log("phase_end", phase_id=phase_id, status=status,
                 ld_verdict=ld_verdict, retries=retries, elapsed_s=elapsed_s)

    def log_checkpoint(self, checkpoint_id: str, summary: str = "") -> None:
        self.log("checkpoint", checkpoint_id=checkpoint_id, summary=summary)

    def log_tool_call(self, tool_name: str, purpose: str,
                      tasks: str, **extra: Any) -> None:
        self.log("tool_call", tool_name=tool_name, purpose=purpose,
                 tasks=tasks, **extra)


@dataclass
class AnalysisStatsRecorder:
    """In-memory per-phase counters, flushed to ``run_stats.json`` on save()."""

    session_dir: Path
    filename: str = "run_stats.json"
    _counters: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def __post_init__(self):
        self.session_dir = Path(self.session_dir)
        self.path = self.session_dir / self.filename

    def incr(self, phase_id: str, key: str, n: int = 1) -> None:
        self._counters.setdefault(phase_id, {})
        self._counters[phase_id][key] = self._counters[phase_id].get(key, 0) + n

    def save(self) -> None:
        self.path.write_text(json.dumps(self._counters, indent=2), encoding="utf-8")

    def as_dict(self) -> Dict[str, Dict[str, int]]:
        return {k: dict(v) for k, v in self._counters.items()}


__all__ = ["AnalysisHistoryRecorder", "AnalysisStatsRecorder"]
