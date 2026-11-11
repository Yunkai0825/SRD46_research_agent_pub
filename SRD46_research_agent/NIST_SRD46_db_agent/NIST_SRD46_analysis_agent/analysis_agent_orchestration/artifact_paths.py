"""Canonical containment for agent-readable scientific artifacts."""
from __future__ import annotations

from pathlib import Path

from ...general_db_query_engine.general_first_principle_API_call_reconstruct.paths import (
    display_path, filesystem_path,
)


def resolve_under(path: str | Path, root: str | Path) -> tuple[Path, Path]:
    """Resolve links, require containment, and retain long-path-safe I/O.

    Windows may resolve a long target to extended UNC spelling while its
    shorter root retains ordinary UNC spelling. Normalize only that device
    prefix for comparison; chemical filenames and path components are intact.
    A target outside the resolved root raises ValueError.
    """
    target = filesystem_path(path).resolve()
    base = filesystem_path(root).resolve()
    relative = display_path(target).relative_to(display_path(base))
    return filesystem_path(target), relative
