"""
SRD46 DB Registry — dataclass-based catalog of all SRD46 SQLite databases.
===========================================================================
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from workspace_setup import ensure_packaged_file


# ═══════════════════════════════════════════════════════════════
#  Path root (resolved once at import time)
# ═══════════════════════════════════════════════════════════════

_HERE = os.path.dirname(os.path.abspath(__file__))
# srd46_db_registry/ → general_db_query_engine/ → NIST_SRD46_db_agent/ → <workspace>/
_WORKSPACE = os.path.normpath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))
_DB_DIR = os.path.join(_WORKSPACE, "NIST_SRD46_core_db_storage")


# ═══════════════════════════════════════════════════════════════
#  Dataclass
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SRD46DatabaseEntry:
    """One SRD46 SQLite database."""

    key: str
    """Short identifier: CARDS, EQUILIBRIUM, LITERATURE, FINGERPRINTS."""

    filename: str
    """Filename within NIST_SRD46_core_db/."""

    description: str
    """One-line purpose."""

    tables: int
    """Approximate table count (for documentation)."""


# ═══════════════════════════════════════════════════════════════
#  Database entries
# ═══════════════════════════════════════════════════════════════

_DB_ENTRIES: List[SRD46DatabaseEntry] = [
    SRD46DatabaseEntry(
        key="CARDS",
        filename="srd46_cards.db",
        description=(
            "Primary database: metals, ligands, species, beta-definitions, "
            "stability constants, pKa values, complex systems."
        ),
        tables=16,
    ),
    SRD46DatabaseEntry(
        key="EQUILIBRIUM",
        filename="srd46_equilibrium_maps.db",
        description=(
            "Pre-computed equilibrium networks: collections, networks, "
            "nodes, edges with full species connectivity."
        ),
        tables=12,
    ),
    SRD46DatabaseEntry(
        key="LITERATURE",
        filename="srd46_literature.db",
        description=(
            "Full citation catalog: literature entries, shortcuts, "
            "VLM→literature linkage across all measurements."
        ),
        tables=8,
    ),
    SRD46DatabaseEntry(
        key="FINGERPRINTS",
        filename="srd46_ligand_fingerprints.db",
        description=(
            "MACCS-166 and Morgan-2048 fingerprints for ligand "
            "structural similarity search."
        ),
        tables=3,
    ),
]

SRD46_DATABASES: Dict[str, SRD46DatabaseEntry] = {e.key: e for e in _DB_ENTRIES}
"""All 4 SRD46 SQLite databases keyed by short name."""


# ═══════════════════════════════════════════════════════════════
#  Path helpers
# ═══════════════════════════════════════════════════════════════

def db_path(key: str) -> str:
    """Absolute path to an SRD46 database.

    *key* is an ``SRD46_DATABASES`` key (e.g. ``"CARDS"``) or a filename.
    """
    entry = SRD46_DATABASES.get(key)
    fn = entry.filename if entry else key
    path = os.path.join(_DB_DIR, fn)
    ensure_packaged_file(path)
    return path


def cards_db_path() -> str:
    """Absolute path to the primary cards database."""
    return db_path("CARDS")


def equilibrium_db_path() -> str:
    """Absolute path to the equilibrium maps database."""
    return db_path("EQUILIBRIUM")


def literature_db_path() -> str:
    """Absolute path to the literature catalog database."""
    return db_path("LITERATURE")


def fingerprints_db_path() -> str:
    """Absolute path to the ligand fingerprints database."""
    return db_path("FINGERPRINTS")
