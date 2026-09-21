"""
Working memory for the SRD-46 analysis agent.
=============================================

Single JSON-backed key/value store, persisted to ``working_memory.json``
inside the active session_dir. The L0 reasoner uses it to remember
between checkpoints (e.g. seed_system from C1 must still be visible to
C4 prose for citing the original user-asked subset).

Deliberately *much* smaller than the query agent's working memory
because the analysis agent's state lives primarily in
``PipelineState`` — this hook is for cross-checkpoint scratch space
that doesn't belong in the typed pipeline state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("Analysis.WorkingMemory")

DEFAULT_MEMORY_FILENAME = "working_memory.json"


class AnalysisWorkingMemory:
    """Tiny JSON-backed dict scoped to one analysis run."""

    def __init__(self, session_dir: str | Path,
                 filename: str = DEFAULT_MEMORY_FILENAME):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.session_dir / filename
        self._store: Dict[str, Any] = {}
        if self.path.exists():
            try:
                self._store = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:                # pragma: no cover
                log.warning("Could not load %s: %s", self.path, exc)
                self._store = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._flush()

    def update(self, **kwargs: Any) -> None:
        self._store.update(kwargs)
        self._flush()

    def append(self, key: str, value: Any) -> None:
        bucket = self._store.setdefault(key, [])
        if not isinstance(bucket, list):
            raise TypeError(f"working-memory key {key!r} is {type(bucket).__name__}, not list")
        bucket.append(value)
        self._flush()

    def render(self) -> str:
        """Render as a small markdown block (for re-injection into LLM prompts)."""
        if not self._store:
            return "_(working memory is empty)_"
        lines = ["## Working memory (analysis agent)"]
        for k, v in self._store.items():
            if isinstance(v, (dict, list)):
                v_str = json.dumps(v, indent=2)
                lines.append(f"### {k}")
                lines.append("```json")
                lines.append(v_str)
                lines.append("```")
            else:
                lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._store)

    def _flush(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self._store, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:                    # pragma: no cover
            log.warning("Could not flush %s: %s", self.path, exc)


__all__ = ["AnalysisWorkingMemory", "DEFAULT_MEMORY_FILENAME"]
