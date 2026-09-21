from __future__ import annotations

import sqlite3
from pathlib import Path

from ..input_support_helpers.scan import REPO_ROOT
from workspace_setup import ensure_packaged_file

DB_NAMES = {
    "cards": "srd46_cards.db",
    "maps": "srd46_equilibrium_maps.db",
    "lit": "srd46_literature.db",
    "fp": "srd46_ligand_fingerprints.db",
}


def open_reference_connection(db_dir: str | Path | None = None) -> sqlite3.Connection:
    database_dir = Path(db_dir) if db_dir else REPO_ROOT / "NIST_SRD46_core_db_storage"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    for alias, filename in DB_NAMES.items():
        db_path = database_dir / filename
        ensure_packaged_file(db_path)
        if not db_path.exists():
            continue
        conn.execute(f"ATTACH DATABASE '{_sqlite_path(db_path)}' AS {alias}")
    return conn


def db_fingerprints(db_dir: str | Path | None = None) -> dict[str, dict[str, int | str]]:
    database_dir = Path(db_dir) if db_dir else REPO_ROOT / "NIST_SRD46_core_db_storage"
    fingerprints: dict[str, dict[str, int | str]] = {}
    for alias, filename in DB_NAMES.items():
        db_path = database_dir / filename
        ensure_packaged_file(db_path)
        if not db_path.exists():
            continue
        stat = db_path.stat()
        fingerprints[alias] = {
            "path": str(db_path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    return fingerprints


def _sqlite_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


__all__ = ["DB_NAMES", "db_fingerprints", "open_reference_connection"]
