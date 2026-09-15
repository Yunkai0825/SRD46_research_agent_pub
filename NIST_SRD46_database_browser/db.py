"""
Database connection helpers for the SRD-46 browser.

All connections are **read-only** (``?mode=ro``).  Paths are resolved
relative to this file so the browser works regardless of cwd.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

# ── path resolution ──────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_REQUIRED_DB_FILES = (
    "srd46_cards.db",
    "srd46_equilibrium_maps.db",
    "srd46_literature.db",
    "srd46_ligand_fingerprints.db",
)


def _resolve_srd46_db_dir() -> Path:
    """Use an explicit database directory or the repository's core bundle."""
    env_dir = os.environ.get("SRD46_DB_DIR")
    directory = (Path(env_dir).expanduser().absolute() if env_dir
                 else _THIS_DIR.parent / "NIST_SRD46_core_db_storage")
    if not directory.is_dir():
        raise FileNotFoundError(
            f"SRD46 database directory not found: {directory}. "
            "Set SRD46_DB_DIR to a directory containing the four SQLite databases."
        )
    return directory


_SRD46_DB_DIR = _resolve_srd46_db_dir()
CARDS_DB = _SRD46_DB_DIR / "srd46_cards.db"
EQUILIBRIUM_DB = _SRD46_DB_DIR / "srd46_equilibrium_maps.db"
LITERATURE_DB = _SRD46_DB_DIR / "srd46_literature.db"
FINGERPRINT_DB = _SRD46_DB_DIR / "srd46_ligand_fingerprints.db"


def _verify(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    return str(path)


def _ro_uri(path: Path) -> str:
    """Encode reserved characters and keep UNC paths in SQLite's URI path."""
    _verify(path)
    value = path.absolute().as_posix()
    # SQLite rejects a remote URI authority; four slashes preserve a UNC path.
    prefix = "file://" if value.startswith("//") else "file:"
    return prefix + quote(value, safe="/:") + "?mode=ro"


def _ro_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(_ro_uri(path), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ── context managers ─────────────────────────────────────────────────

@contextmanager
def get_cards_db():
    conn = _ro_connect(CARDS_DB)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_equilibrium_db():
    conn = _ro_connect(EQUILIBRIUM_DB)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_literature_db():
    conn = _ro_connect(LITERATURE_DB)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_fingerprint_db():
    conn = _ro_connect(FINGERPRINT_DB)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def attach_all_dbs():
    """Cards as main + ATTACH equilibrium (eqdb) and literature (litdb)."""
    conn = _ro_connect(CARDS_DB)
    try:
        conn.execute("ATTACH DATABASE ? AS eqdb", (_ro_uri(EQUILIBRIUM_DB),))
        conn.execute("ATTACH DATABASE ? AS litdb", (_ro_uri(LITERATURE_DB),))
        yield conn
    finally:
        conn.close()


# ── helpers ──────────────────────────────────────────────────────────

def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def verify_all_paths() -> dict[str, bool]:
    return {
        "srd46_cards.db": CARDS_DB.exists(),
        "srd46_equilibrium_maps.db": EQUILIBRIUM_DB.exists(),
        "srd46_literature.db": LITERATURE_DB.exists(),
        "srd46_ligand_fingerprints.db": FINGERPRINT_DB.exists(),
    }
