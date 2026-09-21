"""
Session Manager — directory structure & file catalog for analysis runs.
=======================================================================
Provides a thread-local session so that fitting tools can register
output files (CSVs, plots) without passing paths through every call chain.
Each thread gets its own independent session — safe for parallel test runs.

Usage from orchestrator.py:
    from ..memory_hooks import session_manager
    session_manager.init_session(cfg.OUTPUT_DIR, question)

Usage from fitting_tools.py:
    from ..memory_hooks.session_manager import get_session
    sess = get_session()
    if sess:
        csv_path = sess.data_path("fit_block_10.1234_B3.csv")
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("SESSION-MGR")

# ── Thread-local session storage ─────────────────────────────
# Each thread gets its own active session so parallel test workers
# never clobber each other's output directories or file catalogs.
_tls = threading.local()


class SessionManager:
    """Manages a single analysis-run output directory.

    Layout::
        _output/run_{ts}_{slug}/
            data/       ← CSVs (fit data, excess, baseline)
            plots/      ← PNGs (fit curves, residual plots)
            result.md
            history.md
    """

    def __init__(self, base_dir: Path, question: str):
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", question[:40]).strip("_").lower()
        self.session_dir = base_dir / f"run_{ts}_{slug}"
        self.data_dir = self.session_dir / "data"
        self.plots_dir = self.session_dir / "plots"
        self._catalog: List[Dict[str, str]] = []

    def ensure_dirs(self):
        """Create session directories on disk."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)

    # ── Path helpers ─────────────────────────────────────────

    def data_path(self, filename: str) -> Path:
        """Return a path inside data/ (creates dir if needed)."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / filename

    def plot_path(self, filename: str) -> Path:
        """Return a path inside plots/ (creates dir if needed)."""
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        return self.plots_dir / filename

    # ── File catalog ─────────────────────────────────────────

    def register_file(
        self,
        category: str,
        path: Path | str,
        description: str = "",
    ):
        """Register an output file in the session catalog (deduplicates by path)."""
        path_str = str(path)
        if any(e["path"] == path_str for e in self._catalog):
            return
        self._catalog.append({
            "category": category,
            "path": path_str,
            "description": description,
        })
        log.info("Registered %s: %s", category, path)

    def list_files(self) -> List[Dict[str, str]]:
        """Return all registered files grouped by category."""
        return list(self._catalog)

    def render_manifest(self, *, root_dir: str | None = None) -> str:
        """Render the file catalog as a markdown manifest.

        Parameters
        ----------
        root_dir : str, optional
            If provided, file paths are shown relative to this root.
        """
        if not self._catalog:
            return ""
        lines = ["## Session Output Files", ""]
        by_cat: Dict[str, list] = {}
        for entry in self._catalog:
            by_cat.setdefault(entry["category"], []).append(entry)
        for cat, files in by_cat.items():
            lines.append(f"### {cat}")
            for f in files:
                fpath = f["path"]
                if root_dir and fpath.startswith(root_dir):
                    fpath = "$ROOT/" + fpath[len(root_dir):].lstrip("\\/")
                desc = f" — {f['description']}" if f["description"] else ""
                lines.append(f"- `{fpath}`{desc}")
            lines.append("")
        return "\n".join(lines)


# ── Module-level API ─────────────────────────────────────────

def init_session(base_dir: Path, question: str) -> SessionManager:
    """Create and activate a new session.  Call once per run().

    Each thread gets an independent session so parallel workers never
    overwrite each other's output directories.
    """
    mgr = SessionManager(base_dir, question)
    mgr.ensure_dirs()
    _tls.session = mgr
    log.info("Session initialized: %s", mgr.session_dir)
    return mgr


def get_session() -> Optional[SessionManager]:
    """Return the active session for this thread, or None."""
    return getattr(_tls, "session", None)


def reopen_session(session_dir: Path) -> SessionManager:
    """Reopen an existing session directory for a continuation round.

    Unlike ``init_session`` this does NOT create a new timestamped
    subdirectory — it reuses *session_dir* as-is.
    """
    session_dir = Path(session_dir)
    mgr = object.__new__(SessionManager)
    mgr.session_dir = session_dir
    mgr.data_dir = session_dir / "data"
    mgr.plots_dir = session_dir / "plots"
    mgr._catalog = []
    mgr.ensure_dirs()
    _tls.session = mgr
    log.info("Session reopened: %s", session_dir)
    return mgr


def close_session():
    """Clear the active session for this thread."""
    _tls.session = None
