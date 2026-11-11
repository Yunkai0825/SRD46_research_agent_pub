"""LC1_2 — Equilibrium-map *card* fetch helpers.

Given the LC1_1-resolved ``chemical_system`` block, this module
queries the SRD-46 equilibrium DB and emits a flat
``{"equilibrium_networks": [...]}`` JSON card listing every
``eq_network`` that exists for the requested ``(metal, ligand)``
pairs.

The card shape mirrors the hand-curated
``test_04_FeCu_glycine_citrate_card.json`` reference:

```jsonc
{
  "_notes": "Multi-metal multi-ligand: Cu2+, Cu+, Fe3+, Fe2+ ...",
  "equilibrium_networks": [
    {
      "eq_network":           "ref_eq_net_86",
      "node_count":           2,
      "temperature":          25.0,
      "ionic_strength":       0.1,
      "metal_id":             41,
      "metal_name":           "Cu^[2+]",
      "ligand_id":            5760,
      "ligand_SMILES":        "NCC(=O)O",
      "ligand_canonical_HxL": "HL",
      "_notes": "collection_id=33, Cu2+/Glycine (2 nodes)"
    }, ...
  ]
}
```

Pure DB lookup — no LLM, no curation. The LC1_2 sub-agent uses this
card as its seed and then runs the per-node screening / fixer loop on
top of it.

Public API
----------
``fetch_eqmap_card(chemical_system, *, expand_redox_states=True)``
    Top-level entry point. Returns the card dict.

``fetch_networks_for_pair(metal_id, ligand_id)``
    Lower-level helper: returns the list of network rows for a single
    ``(metal_id, ligand_id)`` collection pair.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ── path bootstrap (so this module is usable stand-alone) ──────────
_THIS = Path(__file__).absolute()
_SRD46_ROOT = _THIS.parents[5]   # SRD46_research_agent/
_sp = str(_SRD46_ROOT)
if _sp not in sys.path:
    sys.path.insert(0, _sp)

from NIST_SRD46_core_db_search_tools._db_connection import (  # noqa: E402
    CARDS_DB,
    get_equilibrium_db,
)

# Reuse the LC1_1 sibling-row helper so we can expand a single chosen
# charge state to every redox state present in the catalog.
from ..LC1_1_SRD46_eq_map_ID_alignment.id_enrichment_helpers import (  # noqa: E402
    sibling_metal_rows,
)

log = logging.getLogger("LC1_2.eqmap_fetch")


_METAL_ID_RE  = re.compile(r"^metal_(\d+)$")
_LIGAND_ID_RE = re.compile(r"^ligand_(\d+)$")

# Aqueous self-system species are treated as ordinary catalog entries here.
# H+ (a metal, metal_68) is enumerated via ``_extract_metal_ids`` so its
# ligand-protonation networks become validated eq-map nodes; OH- (a ligand,
# ligand_10076) is enumerated via ``_extract_ligand_ids`` so metal-hydroxide
# networks are validated here too. Neither needs special-casing.


# ════════════════════════════════════════════════════════════════════
#  ID extraction
# ════════════════════════════════════════════════════════════════════

def _to_int_id(value: Any, kind: str) -> Optional[int]:
    """``"metal_41"`` / ``41`` / ``"41"`` → ``41``; otherwise ``None``."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    pat = _METAL_ID_RE if kind == "metal" else _LIGAND_ID_RE
    m = pat.match(s)
    if m:
        return int(m.group(1))
    try:
        return int(s)
    except ValueError:
        return None


def _extract_metal_ids(
    chemical_system: Dict[str, Any],
) -> List[Tuple[int, str]]:
    """Return [(metal_id, display_name), ...] covering **all** valences.

    For every metal listed in the LC1_1 ``chemical_system``, every
    charge state of the same element that exists in SRD-46 is included
    via :func:`sibling_metal_rows` (Pourbaix-style coverage).
    Duplicates are removed; order follows first-seen.
    """
    out: List[Tuple[int, str]] = []
    seen: set[int] = set()

    for m in chemical_system.get("metals", []) or []:
        element = m.get("element") or m.get("name")

        # New schema: per-oxidation-state IDs live in redox_states, each
        # carrying its own internal_id + db_id.
        for rs in m.get("redox_states") or []:
            if not isinstance(rs, dict):
                continue
            rs_id = _to_int_id(rs.get("db_id"), "metal")
            if rs_id is None or rs_id in seen:
                continue
            out.append((rs_id, str(rs.get("internal_id") or element or rs_id)))
            seen.add(rs_id)

        # Legacy fallback: metal-level db_id (older catalogs).
        mid = _to_int_id(m.get("db_id"), "metal")
        if mid is not None and mid not in seen:
            out.append((mid, str(m.get("internal_id") or m.get("name") or mid)))
            seen.add(mid)

        # Supplemental sibling expansion (covers oxidation states absent
        # from the catalog).
        if not element:
            continue
        for row in sibling_metal_rows(str(element)):
            sib_id = _to_int_id(row.get("metal_id"), "metal")
            if sib_id is None or sib_id in seen:
                continue
            charge = row.get("charge")
            disp = (
                f"{element}{_signed(charge)}"
                if charge is not None else str(element)
            )
            out.append((sib_id, disp))
            seen.add(sib_id)
    return out


def _extract_ligand_ids(
    chemical_system: Dict[str, Any],
) -> List[Tuple[int, str]]:
    """Return [(ligand_id, display_name), ...] in first-seen order."""
    out: List[Tuple[int, str]] = []
    seen: set[int] = set()
    for l in chemical_system.get("ligands", []) or []:
        lid = _to_int_id(l.get("db_id"), "ligand")
        if lid is None:
            log.warning("Skipping ligand entry with no db_id: %r", l)
            continue
        if lid in seen:
            continue
        out.append((lid, str(l.get("name") or l.get("internal_id") or lid)))
        seen.add(lid)
    return out


def _signed(charge: Any) -> str:
    try:
        c = int(charge)
    except (TypeError, ValueError):
        return ""
    return f"+{c}" if c >= 0 else f"{c}"


# ════════════════════════════════════════════════════════════════════
#  Per-pair SQL fetch
# ════════════════════════════════════════════════════════════════════

# One row per eq_network for a given (metal_id, ligand_id) collection.
# Collapses node-level rows via aggregation so the result is flat.
_NETWORKS_FOR_PAIR_SQL = """
    SELECT n.network_db_id              AS network_db_id,
           c.collection_id              AS collection_id,
           c.metal_id                   AS metal_id,
           c.metal_name                 AS metal_name,
           c.ligand_id                  AS ligand_id,
           c.ligand_name                AS ligand_name,
           lc.definition_HxL            AS ligand_canonical_HxL,
           lc.ligand_SMILES             AS ligand_SMILES,
           n.node_count                 AS node_count,
           n.edge_count                 AS edge_count,
           (
               SELECT COUNT(*)
               FROM eq_node executable_node
               WHERE executable_node.network_db_id = n.network_db_id
                 AND executable_node.equation_python IS NOT NULL
                 AND TRIM(executable_node.equation_python) <> ''
                 AND TRIM(executable_node.equation_python) <> '*'
                 AND EXISTS (
                     SELECT 1
                     FROM eq_node_species executable_species
                     WHERE executable_species.node_db_id =
                           executable_node.node_db_id
                 )
                 AND NOT EXISTS (
                     SELECT 1
                     FROM eq_node_species missing_species
                     WHERE missing_species.node_db_id =
                           executable_node.node_db_id
                       AND INSTR(
                           executable_node.equation_python,
                           missing_species.species
                       ) = 0
                 )
           )                            AS solver_parseable_node_count,
           m.condition_temp_min         AS temp_min,
           m.condition_temp_max         AS temp_max,
           m.condition_ionic_min        AS ionic_min,
           m.condition_ionic_max        AS ionic_max
    FROM   eq_map_collection c
    JOIN   eq_map        m ON m.collection_id = c.collection_id
    JOIN   eq_network    n ON n.map_id        = m.map_id
    LEFT JOIN cardsdb.ligand_card lc ON lc.ligand_id = c.ligand_id
    WHERE  c.metal_id  = ?
      AND  c.ligand_id = ?
    ORDER BY n.network_db_id
"""


def _midpoint(lo: Any, hi: Any) -> Optional[float]:
    """Return the midpoint of (lo, hi); falls back to whichever is non-None."""
    try:
        if lo is not None and hi is not None:
            lo_f, hi_f = float(lo), float(hi)
            return round((lo_f + hi_f) / 2.0, 3)
        if lo is not None:
            return round(float(lo), 3)
        if hi is not None:
            return round(float(hi), 3)
    except (TypeError, ValueError):
        return None
    return None


def fetch_networks_for_pair(
    metal_id: int,
    ligand_id: int,
) -> List[Dict[str, Any]]:
    """Return one dict per ``eq_network`` for a ``(metal_id, ligand_id)`` pair.

    Returns ``[]`` when no collection exists for the pair.  Each dict
    carries the raw column values; the higher-level :func:`fetch_eqmap_card`
    reshapes them into the card schema.
    """
    out: List[Dict[str, Any]] = []
    with get_equilibrium_db() as conn:
        conn.execute("ATTACH DATABASE ? AS cardsdb", (str(CARDS_DB),))
        rows = conn.execute(_NETWORKS_FOR_PAIR_SQL,
                            (int(metal_id), int(ligand_id))).fetchall()
        for r in rows:
            out.append(dict(r))
    return out


# ════════════════════════════════════════════════════════════════════
#  Top-level card builder
# ════════════════════════════════════════════════════════════════════

def _short_metal(metal_name: str, charge_hint: str) -> str:
    """``"Cu^[2+]"`` → ``"Cu2+"``; otherwise echoes the input."""
    if not metal_name:
        return charge_hint or "?"
    cleaned = (
        metal_name.replace("^", "").replace("[", "").replace("]", "")
    )
    return cleaned or charge_hint or metal_name


def _network_card_row(
    raw: Dict[str, Any],
    ligand_display: str,
) -> Dict[str, Any]:
    """Shape one DB row into the eq_network card schema."""
    network_id_int = raw.get("network_db_id")
    network_id = (
        f"ref_eq_net_{network_id_int}" if network_id_int is not None else "?"
    )
    metal_id = raw.get("metal_id")
    ligand_id = raw.get("ligand_id")
    metal_name = raw.get("metal_name") or ""
    metal_short = _short_metal(metal_name, "")
    ligand_short = ligand_display or (raw.get("ligand_name") or "")
    node_count = raw.get("node_count")
    collection_id = raw.get("collection_id")

    notes_parts = [f"collection_id={collection_id}"] if collection_id is not None else []
    pair_tag = f"{metal_short}/{ligand_short}".strip("/")
    if pair_tag:
        notes_parts.append(pair_tag)
    if node_count is not None:
        notes_parts.append(f"{node_count} node(s)")
    excluded_non_solver = list(
        raw.get("_excluded_non_solver_network_ids") or []
    )
    if excluded_non_solver:
        excluded_tags = ", ".join(
            f"ref_eq_net_{network_id}"
            for network_id in excluded_non_solver
        )
        notes_parts.append(
            f"non-solver evidence excluded: {excluded_tags}"
        )
    notes = ", ".join(notes_parts)

    return {
        "eq_network":            network_id,
        "node_count":            int(node_count) if node_count is not None else 0,
        "temperature":           _midpoint(raw.get("temp_min"),  raw.get("temp_max")),
        "ionic_strength":        _midpoint(raw.get("ionic_min"), raw.get("ionic_max")),
        "metal_id":              int(metal_id) if metal_id is not None else None,
        "metal_name":            metal_name,
        "ligand_id":             int(ligand_id) if ligand_id is not None else None,
        "ligand_name":           raw.get("ligand_name") or ligand_display or "",
        "ligand_SMILES":         raw.get("ligand_SMILES") or "",
        "ligand_canonical_HxL":  raw.get("ligand_canonical_HxL") or "",
        "selection_provenance": {
            "solver_parseable_node_count": int(
                raw.get("solver_parseable_node_count") or 0
            ),
            "excluded_non_solver_eq_networks": [
                f"ref_eq_net_{network_id}"
                for network_id in excluded_non_solver
            ],
        },
        "_notes":                notes,
        # LC1_2 will populate this slot after the per-pair validator
        # runs. Stays as the empty default below when LC1_2 is
        # disabled or no patches are emitted.
        "patch_notes":           _empty_patch_notes(),
    }


def _empty_patch_notes() -> Dict[str, Any]:
    """Default ``patch_notes`` slot for an un-validated eq_network row."""
    return {
        "validated":          False,
        "validator_attempts": 0,
        "screen_summary":     None,
        "patches":            [],
        "error":              None,
    }


def _select_best_network(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick a single representative network for a (metal, ligand) pair.

    Selection rule:
      1. Require every network node to have an executable equation and a
         non-empty species mapping.  Rows such as SRD-46's ``equation='*'``
         entries remain evidence, but are not solver networks.
      2. Largest ``node_count`` (most complete executable topology).
      3. Tie-break: smallest ``network_db_id`` (stable / oldest).
    """
    if not rows:
        return None
    solver_rows = [row for row in rows if _network_is_solver_usable(row)]
    if not solver_rows:
        return None
    selected = max(
        solver_rows,
        key=lambda r: (
            int(r.get("node_count") or 0),
            -int(r.get("network_db_id") or 0),
        ),
    )
    excluded_ids = sorted(
        int(row["network_db_id"])
        for row in rows
        if not _network_is_solver_usable(row)
        and row.get("network_db_id") is not None
    )
    if not excluded_ids:
        return selected
    return {
        **selected,
        "_excluded_non_solver_network_ids": excluded_ids,
    }


def _network_is_solver_usable(row: Dict[str, Any]) -> bool:
    node_count = int(row.get("node_count") or 0)
    parseable_count = int(row.get("solver_parseable_node_count") or 0)
    return node_count > 0 and parseable_count == node_count


def fetch_eqmap_card(
    chemical_system: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the LC1_2 seed card from an LC1_1 chemical-system block.

    For every metal listed by LC1_1, **every charge state of the same
    element present in SRD-46** is queried (Pourbaix-style coverage).
    For every ``(metal_id, ligand_id)`` pair, exactly **one**
    executable ``eq_network`` is kept — the one with the largest
    ``node_count`` (ties broken by smallest ``network_db_id``). Networks
    whose equations/species cannot be materialized are retained in SRD-46
    as evidence but are never emitted as solver networks.

    Parameters
    ----------
    chemical_system:
        The ``system_catalog.chemical_system`` dict produced by LC1_1.
        Either the inner ``chemical_system`` block or the full
        ``{"system_catalog": {"chemical_system": ...}}`` envelope is
        accepted.

    Returns
    -------
    dict
        ``{"_notes": str, "equilibrium_networks": [...]}``
    """
    # Accept either the envelope or the inner block.
    cs = chemical_system
    if "system_catalog" in cs and isinstance(cs["system_catalog"], dict):
        cs = cs["system_catalog"].get("chemical_system", {}) or {}
    elif "chemical_system" in cs and isinstance(cs["chemical_system"], dict):
        cs = cs["chemical_system"]

    metals  = _extract_metal_ids(cs)
    ligands = _extract_ligand_ids(cs)

    network_rows: List[Dict[str, Any]] = []
    pairs_with_data = 0

    for mid, _m_disp in metals:
        for lid, l_disp in ligands:
            best = _select_best_network(fetch_networks_for_pair(mid, lid))
            if best is None:
                continue
            pairs_with_data += 1
            network_rows.append(_network_card_row(best, l_disp))

    # Header summary
    n_metals  = len({mid for mid, _ in metals})
    n_ligands = len(ligands)
    summary = (
        f"{n_metals} metal(s) × {n_ligands} ligand(s) → "
        f"{pairs_with_data} pair(s) with eq_map data "
        f"({len(network_rows)} eq_network(s), one per pair)."
    )

    return {
        "_notes":               summary,
        "equilibrium_networks": network_rows,
    }


__all__ = [
    "fetch_eqmap_card",
    "fetch_networks_for_pair",
    "empty_patch_notes",
]


def empty_patch_notes() -> Dict[str, Any]:
    """Public alias of :func:`_empty_patch_notes`."""
    return _empty_patch_notes()
