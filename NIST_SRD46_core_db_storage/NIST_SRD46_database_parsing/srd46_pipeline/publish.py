"""Atomic hand-over of freshly built SQLite files to their final paths."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def finalize_sqlite(path: Path) -> None:
    """Make the file self-contained (WAL checkpointed, no -wal/-shm side files)."""
    con = sqlite3.connect(str(path))
    try:
        con.execute("PRAGMA journal_mode=DELETE")
        con.commit()
    finally:
        con.close()


def publish(tmp: Path, final: Path) -> None:
    """temp file -> final path in one rename; stale side files of the old DB are removed first."""
    final.parent.mkdir(parents=True, exist_ok=True)
    for side in (final.with_name(final.name + "-wal"), final.with_name(final.name + "-shm"),
                 final.with_name(final.name + "-journal")):
        if side.exists():
            side.unlink()
    os.replace(tmp, final)


def temp_path(final: Path) -> Path:
    tmp = final.with_name(final.name + ".tmp")
    for p in (tmp, tmp.with_name(tmp.name + "-wal"), tmp.with_name(tmp.name + "-shm"), tmp.with_name(tmp.name + "-journal")):
        if p.exists():
            p.unlink()
    return tmp
