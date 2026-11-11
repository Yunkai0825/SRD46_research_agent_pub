"""
System-level catalog builder.

``build_system_catalog()`` returns an overview of all stability data
for one or more metal–ligand pairs, grouped by beta-definition, with
equilibrium-network summaries.

Typical use: an agent has resolved metal_id and ligand_id (or
beta_definition_id) and needs to see *how much* data exists before
drilling into individual VLM cards.
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from ._db_connection import get_cards_db, get_equilibrium_db
from ._normalization_helpers.id_prefixer import (
    prefix_ids_in_rows,
    prefix_id_value,
    unprefix_id,
)

log = logging.getLogger("SRD46")

_PAIR_LIMIT = 20          # max metal–ligand pairs per call
_VLM_ID_LIMIT = 200       # max vlm_ids listed per pair


# ── helpers ──────────────────────────────────────────────────────────

def _rows_to_dicts(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def _to_int(val: Any) -> int:
    """Accept prefixed string or plain int → int."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    return unprefix_id(val)


def _try_parse_json(raw):
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return _json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


# ── resolve pairs ────────────────────────────────────────────────────

def _resolve_pairs(
    metal_id: int | None,
    ligand_id: int | None,
    beta_definition_id: int | None,
    conn,
) -> list[dict]:
    """Return a list of ``{metal_id, ligand_id, metal_name, ligand_name}``."""

    if beta_definition_id is not None:
        rows = _rows_to_dicts(conn.execute(
            "SELECT DISTINCT c.metal_id, c.ligand_id, "
            "       c.metal_name_SRD AS metal_name, "
            "       c.ligand_name_SRD AS ligand_name "
            "FROM   ligandmetal_card c "
            "WHERE  c.beta_definition_id = ? "
            "LIMIT  ?",
            (beta_definition_id, _PAIR_LIMIT),
        ))
        return rows

    if metal_id is not None and ligand_id is not None:
        rows = _rows_to_dicts(conn.execute(
            "SELECT DISTINCT c.metal_id, c.ligand_id, "
            "       c.metal_name_SRD AS metal_name, "
            "       c.ligand_name_SRD AS ligand_name "
            "FROM   ligandmetal_card c "
            "WHERE  c.metal_id = ? AND c.ligand_id = ? "
            "LIMIT  1",
            (metal_id, ligand_id),
        ))
        return rows

    if metal_id is not None:
        rows = _rows_to_dicts(conn.execute(
            "SELECT DISTINCT c.metal_id, c.ligand_id, "
            "       c.metal_name_SRD AS metal_name, "
            "       c.ligand_name_SRD AS ligand_name "
            "FROM   ligandmetal_card c "
            "WHERE  c.metal_id = ? "
            "GROUP BY c.ligand_id "
            "ORDER BY COUNT(*) DESC "
            "LIMIT  ?",
            (metal_id, _PAIR_LIMIT),
        ))
        return rows

    if ligand_id is not None:
        rows = _rows_to_dicts(conn.execute(
            "SELECT DISTINCT c.metal_id, c.ligand_id, "
            "       c.metal_name_SRD AS metal_name, "
            "       c.ligand_name_SRD AS ligand_name "
            "FROM   ligandmetal_card c "
            "WHERE  c.ligand_id = ? "
            "GROUP BY c.metal_id "
            "ORDER BY COUNT(*) DESC "
            "LIMIT  ?",
            (ligand_id, _PAIR_LIMIT),
        ))
        return rows

    return []


# ── per-pair catalog ─────────────────────────────────────────────────

def _catalog_pair(metal_id: int, ligand_id: int, conn) -> dict:
    """Build the catalog dict for one metal–ligand pair."""

    # Species catalog grouped by beta_definition
    species_rows = _rows_to_dicts(conn.execute(
        "SELECT c.beta_definition_id, c.beta_definition_name, "
        "       s.equation_str, "
        "       COUNT(*) AS n_entries "
        "FROM   ligandmetal_card c "
        "JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
        "WHERE  c.metal_id = ? AND c.ligand_id = ? "
        "GROUP BY c.beta_definition_id "
        "ORDER BY c.beta_definition_id",
        (metal_id, ligand_id),
    ))
    # equation_str may differ across rows within same beta_def; take any
    for row in species_rows:
        row.pop("equation_str", None)  # we'll re-fetch a representative below

    # Get one representative equation_str per beta_definition
    eq_map: dict[int, str] = {}
    eq_rows = _rows_to_dicts(conn.execute(
        "SELECT c.beta_definition_id, s.equation_str "
        "FROM   ligandmetal_card c "
        "JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
        "WHERE  c.metal_id = ? AND c.ligand_id = ? "
        "  AND  s.equation_str IS NOT NULL "
        "GROUP BY c.beta_definition_id",
        (metal_id, ligand_id),
    ))
    for r in eq_rows:
        eq_map[r["beta_definition_id"]] = r["equation_str"]

    # Get one representative equation_tree_json per beta_definition for phase info
    tree_rows = _rows_to_dicts(conn.execute(
        "SELECT c.beta_definition_id, s.equation_tree_json "
        "FROM   ligandmetal_card c "
        "JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
        "WHERE  c.metal_id = ? AND c.ligand_id = ? "
        "  AND  s.equation_tree_json IS NOT NULL "
        "GROUP BY c.beta_definition_id",
        (metal_id, ligand_id),
    ))

    import json as _json
    phase_map: dict[int, str] = {}
    for r in tree_rows:
        try:
            tree = _json.loads(r["equation_tree_json"])
            parts = []
            for side in ("numerator", "denominator"):
                for sp in tree.get(side, []):
                    name = sp.get("species", "?")
                    phase = sp.get("phase", "")
                    parts.append(f"{name}({phase})" if phase else name)
            phase_map[r["beta_definition_id"]] = ", ".join(parts)
        except Exception:
            pass

    for row in species_rows:
        row["equation_str"] = eq_map.get(row["beta_definition_id"], None)
        row["phases"] = phase_map.get(row["beta_definition_id"], None)

    # Totals
    totals = conn.execute(
        "SELECT COUNT(*) AS total_entries, "
        "       COUNT(DISTINCT c.beta_definition_id) AS n_unique_species "
        "FROM   ligandmetal_card c "
        "JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
        "WHERE  c.metal_id = ? AND c.ligand_id = ?",
        (metal_id, ligand_id),
    ).fetchone()

    # VLM IDs
    vlm_rows = conn.execute(
        "SELECT DISTINCT c.complex_system_id AS vlm_id "
        "FROM   ligandmetal_card c "
        "WHERE  c.metal_id = ? AND c.ligand_id = ? "
        "ORDER BY c.complex_system_id "
        "LIMIT  ?",
        (metal_id, ligand_id, _VLM_ID_LIMIT),
    ).fetchall()
    vlm_ids = [r["vlm_id"] for r in vlm_rows]

    total_vlm = conn.execute(
        "SELECT COUNT(DISTINCT c.complex_system_id) AS n "
        "FROM   ligandmetal_card c "
        "WHERE  c.metal_id = ? AND c.ligand_id = ?",
        (metal_id, ligand_id),
    ).fetchone()["n"]

    beta_def_ids = [r["beta_definition_id"] for r in species_rows]

    prefix_ids_in_rows(species_rows)

    return {
        "species_catalog": species_rows,
        "total_stability_entries": totals["total_entries"],
        "n_unique_species": totals["n_unique_species"],
        "total_vlm_count": total_vlm,
        "vlm_ids": [prefix_id_value("vlm_id", v) for v in vlm_ids],
        "beta_definition_ids": [
            prefix_id_value("beta_definition_id", b) for b in beta_def_ids
        ],
    }


# ── equilibrium maps from eq DB ─────────────────────────────────────

def _eq_maps_for_pair(metal_id: int, ligand_id: int) -> list[dict]:
    """Fetch equilibrium map summaries for a metal–ligand pair."""
    sql = """
        SELECT c.collection_id,
               c.metal_id,        c.ligand_id,
               c.metal_name,      c.ligand_name,
               c.total_entries,    c.total_networks,
               n.network_db_id   AS network_id,
               n.node_count,      n.edge_count,
               m.condition_temp_min  AS temp_min,
               m.condition_temp_max  AS temp_max,
               m.condition_ionic_min AS ionic_min,
               m.condition_ionic_max AS ionic_max
        FROM   eq_map_collection c
        JOIN   eq_map m  ON m.collection_id = c.collection_id
        JOIN   eq_network n ON n.map_id = m.map_id
        WHERE  c.metal_id = ? AND c.ligand_id = ?
        ORDER  BY n.network_db_id
    """
    with get_equilibrium_db() as conn:
        rows = _rows_to_dicts(conn.execute(sql, (metal_id, ligand_id)))
    prefix_ids_in_rows(rows)
    return rows


# ═══════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════

def build_system_catalog(
    *,
    metal_id: int | str | None = None,
    ligand_id: int | str | None = None,
    beta_definition_id: int | str | None = None,
) -> dict:
    """
    Build an overview catalog for one or more metal–ligand systems.

    Supply **at least one** of the three parameters.  Accepts both
    raw integers and prefixed strings (``"metal_41"``, ``"ligand_5760"``,
    ``"beta_def_812"``).

    Parameters
    ----------
    metal_id : int or str, optional
        Filter by metal.  If only metal_id is given, returns the top
        pairs (up to 20) ranked by measurement count.
    ligand_id : int or str, optional
        Filter by ligand.  If only ligand_id is given, returns the top
        pairs ranked by measurement count.
    beta_definition_id : int or str, optional
        Filter by beta-definition.  Resolves to the metal–ligand pair(s)
        that share this definition.

    Returns
    -------
    dict
        ``{"pairs": [...], "summary": {...}}``.

        Each pair contains:

        - ``metal_id``, ``ligand_id``, ``metal_name``, ``ligand_name``
        - ``species_catalog``: one entry per beta_definition with
          ``beta_definition_id``, ``beta_definition_name``,
          ``equation_str``, ``n_entries``
        - ``total_stability_entries``, ``n_unique_species``,
          ``total_vlm_count``
        - ``vlm_ids``: prefixed list (up to 200)
        - ``beta_definition_ids``: prefixed list
        - ``equilibrium_maps``: network summaries from the eq DB

        ``summary`` aggregates: ``n_metals``, ``n_ligands``, ``n_pairs``,
        ``total_species``.

    Examples
    --------
    Ni + Ammonia system::

        build_system_catalog(metal_id="metal_112", ligand_id="ligand_10103")

    Everything with beta_def_812::

        build_system_catalog(beta_definition_id="beta_def_812")

    All ligand partners for Cu²⁺::

        build_system_catalog(metal_id=41)
    """
    m_id = _to_int(metal_id)
    l_id = _to_int(ligand_id)
    b_id = _to_int(beta_definition_id)

    if m_id is None and l_id is None and b_id is None:
        return {"error": "Provide at least one of metal_id, ligand_id, or beta_definition_id."}

    with get_cards_db() as conn:
        raw_pairs = _resolve_pairs(m_id, l_id, b_id, conn)

        if not raw_pairs:
            return {
                "pairs": [],
                "summary": {
                    "n_metals": 0, "n_ligands": 0,
                    "n_pairs": 0, "total_species": 0,
                },
            }

        # Fetch definition_HxL for each unique ligand in one pass
        unique_lids = list({p["ligand_id"] for p in raw_pairs})
        hxl_map: dict[int, str | None] = {}
        if unique_lids:
            ph = ",".join("?" for _ in unique_lids)
            for r in conn.execute(
                f"SELECT ligand_id, definition_HxL FROM ligand_card "
                f"WHERE ligand_id IN ({ph})", unique_lids,
            ):
                hxl_map[r["ligand_id"]] = r["definition_HxL"]

        pairs_out = []
        for p in raw_pairs:
            pair_mid = p["metal_id"]
            pair_lid = p["ligand_id"]

            catalog = _catalog_pair(pair_mid, pair_lid, conn)
            eq_maps = _eq_maps_for_pair(pair_mid, pair_lid)

            pairs_out.append({
                "metal_id": prefix_id_value("metal_id", pair_mid),
                "ligand_id": prefix_id_value("ligand_id", pair_lid),
                "metal_name": p["metal_name"],
                "ligand_name": p["ligand_name"],
                "definition_HxL": hxl_map.get(pair_lid),
                **catalog,
                "equilibrium_maps": eq_maps,
            })

    summary = {
        "n_metals": len({p["metal_id"] for p in pairs_out}),
        "n_ligands": len({p["ligand_id"] for p in pairs_out}),
        "n_pairs": len(pairs_out),
        "total_species": sum(p["n_unique_species"] for p in pairs_out),
    }

    return {"pairs": pairs_out, "summary": summary}
