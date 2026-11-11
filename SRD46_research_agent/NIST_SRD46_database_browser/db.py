"""
Database connection helpers for the SRD-46 browser.

All connections are **read-only** (``?mode=ro``).  Paths are resolved
relative to this file so the browser works regardless of cwd.
"""

import csv
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# ── path resolution ──────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_REQUIRED_DB_FILES = (
    "srd46_cards.db",
    "srd46_equilibrium_maps.db",
    "srd46_literature.db",
    "srd46_ligand_fingerprints.db",
)


def _resolve_srd46_db_dir() -> Path:
    """Resolve the SRD46 DB directory from known candidates.

    Resolution order:
    1) ``SRD46_DB_DIR`` environment variable (if set)
    2) ``NIST_SRD46_core_db_storage`` beside the browser package
    """
    candidates: list[Path] = []

    env_dir = os.environ.get("SRD46_DB_DIR")
    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    candidates.extend([
        _THIS_DIR.parent / "NIST_SRD46_core_db_storage",
    ])

    # Remove duplicates while preserving order.
    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for c in candidates:
        rc = c.resolve() if c.exists() else c
        if rc in seen:
            continue
        seen.add(rc)
        unique_candidates.append(c)

    for c in unique_candidates:
        if all((c / name).exists() for name in _REQUIRED_DB_FILES):
            return c

    # Partial fallback: accept folder with cards DB so browser can start,
    # while missing files still fail clearly when those routes are used.
    for c in unique_candidates:
        if (c / "srd46_cards.db").exists():
            return c

    searched = "\n  - " + "\n  - ".join(str(c) for c in unique_candidates)
    raise FileNotFoundError(
        "SRD46 database directory not found. Set SRD46_DB_DIR or place DB files in one of:\n"
        f"{searched}"
    )


_SRD46_DB_DIR = _resolve_srd46_db_dir()
_POURBAIX_DIR = (
    _THIS_DIR.parent / "Auxillary_dbs_storage" / "Pourbaix_atlas_database"
)
_POURBAIX_CSV = _POURBAIX_DIR / "_pourbaix_substances_all.csv"

CARDS_DB = _SRD46_DB_DIR / "srd46_cards.db"
EQUILIBRIUM_DB = _SRD46_DB_DIR / "srd46_equilibrium_maps.db"
LITERATURE_DB = _SRD46_DB_DIR / "srd46_literature.db"
FINGERPRINT_DB = _SRD46_DB_DIR / "srd46_ligand_fingerprints.db"


def _verify(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    text = str(path)
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return text


def _ro_connect(path: Path) -> sqlite3.Connection:
    uri = Path(_verify(path)).absolute().as_uri()
    if uri.startswith("file://") and not uri.startswith("file:///"):
        uri = "file:////" + uri[len("file://"):]
    uri += "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
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
        conn.execute("ATTACH DATABASE ? AS eqdb", (_verify(EQUILIBRIUM_DB),))
        conn.execute("ATTACH DATABASE ? AS litdb", (_verify(LITERATURE_DB),))
        yield conn
    finally:
        conn.close()


# ── helpers ──────────────────────────────────────────────────────────

def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


# ── Pourbaix Atlas ───────────────────────────────────────────────────
_POURBAIX_DATA: list[dict] | None = None


def get_pourbaix_data() -> list[dict]:
    global _POURBAIX_DATA
    if _POURBAIX_DATA is not None:
        return _POURBAIX_DATA
    # Optional dataset: if absent, expose an empty list so the browser
    # still works for the rest of the SRD-46 functionality.
    if not _POURBAIX_CSV.exists():
        _POURBAIX_DATA = []
        return _POURBAIX_DATA
    path = _verify(_POURBAIX_CSV)
    with open(path, newline="", encoding="utf-8") as f:
        _POURBAIX_DATA = list(csv.DictReader(f))
    return _POURBAIX_DATA


def get_pourbaix_md(element: str) -> str | None:
    """Read the Pourbaix .md file for a given element name."""
    for md in _POURBAIX_DIR.glob(f"*_{element}.md"):
        return md.read_text(encoding="utf-8")
    return None


def verify_all_paths() -> dict[str, bool]:
    return {
        "srd46_cards.db": CARDS_DB.exists(),
        "srd46_equilibrium_maps.db": EQUILIBRIUM_DB.exists(),
        "srd46_literature.db": LITERATURE_DB.exists(),
        "srd46_ligand_fingerprints.db": FINGERPRINT_DB.exists(),
        "pourbaix_substances_all.csv": _POURBAIX_CSV.exists(),
    }
