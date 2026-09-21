"""
Database connection helpers for the four SRD-46 SQLite databases.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from workspace_setup import ensure_packaged_file

# Resolve the SRD-46 core-DB storage directory relative to this repo.
# This file: <workspace>/NIST_SRD46_core_db_search_tools/_db_connection.py
# Storage : <workspace>/NIST_SRD46_core_db_storage/
_DB_DIR = Path(__file__).absolute().parent.parent / "NIST_SRD46_core_db_storage"

CARDS_DB = _DB_DIR / "srd46_cards.db"
EQUILIBRIUM_DB = _DB_DIR / "srd46_equilibrium_maps.db"
LITERATURE_DB = _DB_DIR / "srd46_literature.db"
FINGERPRINT_DB = _DB_DIR / "srd46_ligand_fingerprints.db"


def _verify(path: Path) -> str:
    """Return the string path after verifying the file exists."""
    ensure_packaged_file(path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    return str(path)


@contextmanager
def get_cards_db():
    """Context manager for the primary cards database."""
    conn = sqlite3.connect(_verify(CARDS_DB))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_equilibrium_db():
    """Context manager for the equilibrium maps database."""
    conn = sqlite3.connect(_verify(EQUILIBRIUM_DB))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_literature_db():
    """Context manager for the full literature catalog database."""
    conn = sqlite3.connect(_verify(LITERATURE_DB))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def attach_all_dbs():
    """
    Open the cards database as the primary connection and ATTACH
    the equilibrium and literature databases for cross-DB queries.
    """
    conn = sqlite3.connect(_verify(CARDS_DB))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("ATTACH DATABASE ? AS eqdb", (_verify(EQUILIBRIUM_DB),))
        conn.execute("ATTACH DATABASE ? AS litdb", (_verify(LITERATURE_DB),))
        yield conn
    finally:
        conn.close()
