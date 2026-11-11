"""
srd46_db_registry — agent-agnostic catalog of all SRD46 SQLite databases.
==========================================================================
Central registry of every SQLite database used by the SRD46 search tools.

Four databases
--------------
1. **Cards DB** — metal/ligand entities, stability constant measurements,
   species definitions, and beta-definition metadata (158 MB).
2. **Equilibrium Maps DB** — pre-computed equilibrium networks, collections,
   and network nodes/edges (28 MB).
3. **Literature DB** — full citation catalog with VLM→literature linkage (44 MB).
4. **Fingerprints DB** — MACCS-166 + Morgan-2048 fingerprints for ligand
   similarity search.

Usage::

    from general_db_query_engine.srd46_db_registry import (
        SRD46_DATABASES,   # dict[str, SRD46DatabaseEntry]
        db_path,           # key → absolute path
    )
"""

from .srd46_db_registry import (
    SRD46DatabaseEntry,
    SRD46_DATABASES,
    db_path,
    cards_db_path,
    equilibrium_db_path,
    literature_db_path,
    fingerprints_db_path,
)

__all__ = [
    "SRD46DatabaseEntry",
    "SRD46_DATABASES",
    "db_path",
    "cards_db_path",
    "equilibrium_db_path",
    "literature_db_path",
    "fingerprints_db_path",
]
