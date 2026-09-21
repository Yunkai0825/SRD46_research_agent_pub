"""neighbor_query.py — fetch full sibling list for an eq-map node.

A "neighbor" of an eq-map node is any DB row that measured the SAME
``(metal_id, ligand_id, beta_definition_id)`` triple — across ALL
temperatures and ionic strengths.  These are the rows the L2_1_1
validator and L3 fixer compare the chosen node against.

Two source tables are queried and merged:

* ``srd46_equilibrium_maps.eq_node`` — the table the new card builder
  ingests; one or more rows per (metal, ligand, beta_def) curated into
  per-network selections.  Rows tagged with ``constant_type``
  ('K' / 'H' / 'S'), ``constant_value``, ``temperature``,
  ``ionic_strength``, ``vlm_id``, ``network_db_id``,
  ``is_duplicate``, ``used_in_map``.

* ``srd46_cards.ligandmetal_stability_measured`` joined to
  ``ligandmetal_card`` — the alternate mirror used by the OLD pipeline.
  Same triple may appear here too; carries solvent + footnote info.
  ``ligandmetal_card.complex_system_id`` equals
  ``eq_node.vlm_id`` (== raw NIST ``verkn_ligand_metalID``).

Rows are de-duplicated by ``vlm_id`` after merging (eq_node row wins
when both tables carry the same vlm_id, since eq_node is what the
new pipeline actually consumes).
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── path bootstrap so the helper can run standalone ─────────────
_SRD46_ROOT = Path(__file__).absolute().parents[6]   # SRD46_research_agent/
if str(_SRD46_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRD46_ROOT))

from NIST_SRD46_core_db_search_tools._db_connection import (
    get_cards_db,
    get_equilibrium_db,
)

log = logging.getLogger("eqmap_validation.neighbor_query")


@dataclass
class NeighborRow:
    """One sibling measurement for a (metal, ligand, beta_def) triple."""
    vlm_id:            Optional[int]      # raw NIST verkn_ligand_metalID
    source_table:      str                 # "eq_node" | "ligandmetal_stability_measured" | "both"
    constant_type:     str                 # "K" | "H" | "S" | "*"
    constant_value:    float
    temperature_C:     Optional[float]
    ionic_strength_M:  Optional[float]
    equation_str:      str = ""           # e.g. "[M] + [L] <=> [ML]"
    network_db_id:     Optional[int] = None
    is_duplicate:      Optional[int] = None
    used_in_map:       Optional[int] = None
    solvent_name:      str = ""
    notes:             str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ════════════════════════════════════════════════════════════════════
#  eq_node fetch
# ════════════════════════════════════════════════════════════════════

def _fetch_from_eq_node(
    metal_id: int,
    ligand_id: int,
    beta_definition_id: int,
) -> List[NeighborRow]:
    """Pull every eq_node row for the (metal, ligand, beta_def) triple.

    eq_node is partitioned per network_db_id; we DELIBERATELY ignore
    the network filter so every measurement of this triple is returned
    regardless of which curated map it landed in.
    """
    sql = """
        SELECT vlm_id, network_db_id, constant_type, constant_value,
               temperature, ionic_strength,
               equation_python, is_duplicate, used_in_map
        FROM eq_node
        WHERE metal_id = ? AND ligand_id = ? AND beta_definition_id = ?
        ORDER BY vlm_id
    """
    out: List[NeighborRow] = []
    with get_equilibrium_db() as conn:
        rows = conn.execute(sql, (metal_id, ligand_id, beta_definition_id)).fetchall()
        for r in rows:
            try:
                val = float(r["constant_value"])
            except (TypeError, ValueError):
                continue
            out.append(NeighborRow(
                vlm_id=int(r["vlm_id"]) if r["vlm_id"] is not None else None,
                source_table="eq_node",
                constant_type=str(r["constant_type"] or "").strip() or "?",
                constant_value=val,
                temperature_C=_safe_float(r["temperature"]),
                ionic_strength_M=_safe_float(r["ionic_strength"]),
                equation_str=str(r["equation_python"] or ""),
                network_db_id=int(r["network_db_id"]) if r["network_db_id"] is not None else None,
                is_duplicate=int(r["is_duplicate"]) if r["is_duplicate"] is not None else None,
                used_in_map=int(r["used_in_map"]) if r["used_in_map"] is not None else None,
            ))
    return out


# ════════════════════════════════════════════════════════════════════
#  ligandmetal_stability_measured fetch
# ════════════════════════════════════════════════════════════════════

def _fetch_from_stability_measured(
    metal_id: int,
    ligand_id: int,
    beta_definition_id: int,
) -> List[NeighborRow]:
    """Pull every cards.db row for the same (metal, ligand, beta_def).

    Joined via ``ligandmetal_card``; the card's
    ``complex_system_id`` equals the raw ``verkn_ligand_metalID``
    (a.k.a. ``vlm_id`` in eq_node).
    """
    sql = """
        SELECT s.constant_type, s.constant_value,
               s.temperature_c, s.ionic_strength_mol_l,
               s.equation_str, s.solvent_name, s.notes,
               c.complex_system_id AS vlm_id
        FROM ligandmetal_stability_measured s
        JOIN ligandmetal_card c ON c.card_id = s.card_id
        WHERE c.metal_id = ?
          AND c.ligand_id = ?
          AND c.beta_definition_id = ?
        ORDER BY c.complex_system_id
    """
    out: List[NeighborRow] = []
    with get_cards_db() as conn:
        rows = conn.execute(sql, (metal_id, ligand_id, beta_definition_id)).fetchall()
        for r in rows:
            try:
                val = float(r["constant_value"])
            except (TypeError, ValueError):
                continue
            out.append(NeighborRow(
                vlm_id=int(r["vlm_id"]) if r["vlm_id"] is not None else None,
                source_table="ligandmetal_stability_measured",
                constant_type=str(r["constant_type"] or "").strip() or "?",
                constant_value=val,
                temperature_C=_safe_float(r["temperature_c"]),
                ionic_strength_M=_safe_float(r["ionic_strength_mol_l"]),
                equation_str=str(r["equation_str"] or ""),
                solvent_name=str(r["solvent_name"] or "").strip(),
                notes=str(r["notes"] or "").strip(),
            ))
    return out


# ════════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════════

def get_node_neighbors(
    metal_id: int,
    ligand_id: int,
    beta_definition_id: int,
) -> List[NeighborRow]:
    """Return every measurement for the (metal, ligand, beta_def) triple.

    Merges rows from both source tables; rows that share a ``vlm_id``
    are collapsed (eq_node copy wins on metadata; the
    stability_measured copy contributes solvent_name / notes /
    equation_str when they are richer).
    """
    eq_rows = _fetch_from_eq_node(metal_id, ligand_id, beta_definition_id)
    sm_rows = _fetch_from_stability_measured(metal_id, ligand_id, beta_definition_id)

    by_vlm: Dict[Optional[int], NeighborRow] = {}
    for row in eq_rows:
        by_vlm[row.vlm_id] = row
    for row in sm_rows:
        existing = by_vlm.get(row.vlm_id)
        if existing is None:
            by_vlm[row.vlm_id] = row
            continue
        # Enrich the eq_node row with solvent + notes from cards.db
        merged_notes = existing.notes or row.notes
        merged_solvent = existing.solvent_name or row.solvent_name
        merged_eq = existing.equation_str or row.equation_str
        existing.solvent_name = merged_solvent
        existing.notes = merged_notes
        existing.equation_str = merged_eq
        existing.source_table = "both"

    # Stable order: by vlm_id ascending; None last.
    def _sort_key(row: NeighborRow) -> Tuple[int, int]:
        v = row.vlm_id if row.vlm_id is not None else 10**18
        return (0, v)

    return sorted(by_vlm.values(), key=_sort_key)


# ════════════════════════════════════════════════════════════════════
#  Internals
# ════════════════════════════════════════════════════════════════════

def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
