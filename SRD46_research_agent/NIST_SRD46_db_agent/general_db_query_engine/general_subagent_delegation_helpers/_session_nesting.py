"""
Session-nesting helper for subagent delegation.
================================================
Creates nested subdirectories inside a parent agent's active session
so that each subagent run's output (stats, history, reasoning) is
co-located with the parent's output.

The caller injects a ``get_session`` callable (from its own
hook_catalog) so this module never imports agent-specific code.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)


class SubagentSessionManager:
    """Thread-safe session-nesting manager.

    Parameters
    ----------
    get_session : callable
        Zero-arg callable that returns the parent agent's active
        ``SessionManager`` instance (or ``None``).  Typically
        ``hook_catalog.session_manager.get_session``.
    """

    def __init__(self, get_session: Callable[[], Optional[object]]) -> None:
        self._get_session = get_session
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()

    def _next_run_id(self, agent_type: str) -> int:
        with self._lock:
            self._counters[agent_type] = self._counters.get(agent_type, 0) + 1
            return self._counters[agent_type]

    def get_subagent_session_dir(self, agent_type: str) -> Optional[Path]:
        """Create and return a nested subfolder for *agent_type*.

        Layout::

            <parent_session_dir>/<agent_type>_runs/run_<N>/

        Returns ``None`` when no parent session is active.
        """
        try:
            sess = self._get_session()
            if sess and getattr(sess, "session_dir", None):
                run_id = self._next_run_id(agent_type)
                subdir = (
                    Path(sess.session_dir)
                    / f"{agent_type}_runs"
                    / f"run_{run_id}"
                )
                subdir.mkdir(parents=True, exist_ok=True)
                return subdir
        except Exception as exc:
            log.debug("Could not resolve parent session dir: %s", exc)
        return None

    def get_parent_session_dir(self) -> Optional[Path]:
        """Return the parent agent's session dir, or ``None``."""
        try:
            sess = self._get_session()
            if sess and getattr(sess, "session_dir", None):
                return Path(sess.session_dir)
        except Exception:
            pass
        return None
