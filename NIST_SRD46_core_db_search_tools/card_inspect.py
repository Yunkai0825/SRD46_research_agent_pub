"""
Deep card inspection.

``inspect_card(prefix_id)`` returns the **full card** for a metal, ligand,
or VLM measurement, including all speciation context, literature, and
equilibrium network membership.
"""

import json as _json
import logging

from ._db_connection import get_cards_db, attach_all_dbs
from ._normalization_helpers.id_prefixer import (
    prefix_ids_in_row,
    prefix_ids_in_rows,
    parse_prefixed_id,
)

log = logging.getLogger("SRD46")


# ── helpers ──────────────────────────────────────────────────────────

def _rows_to_dicts(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def _parse_prefix_id(prefix_id: str) -> tuple[str, int]:
    """Parse 'metal_41' → ('metal', 41), 'vlm_12345' → ('vlm', 12345)."""
    kind, num = parse_prefixed_id(prefix_id)
    if kind not in ("metal", "ligand", "vlm"):
        raise ValueError(
            f"Cannot inspect type '{kind}'. Must be metal, ligand, or vlm."
        )
    return kind, num


def _try_parse_json(raw):
    """Parse a JSON string to dict/list, or return raw value unchanged."""
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


# ── metal inspect ────────────────────────────────────────────────────

def _inspect_metal(metal_id: int) -> dict:
    """Full metal card + summary of ligand partners and measurement counts."""
    result: dict = {"prefix_id": f"metal_{metal_id}"}

    with get_cards_db() as conn:
        row = conn.execute(
            "SELECT * FROM metal_card WHERE metal_id = ?", (metal_id,)
        ).fetchone()
        if not row:
            return {"prefix_id": f"metal_{metal_id}", "error": "not found"}
        result["card"] = dict(row)
        prefix_ids_in_row(result["card"])

        partner_sql = """
            SELECT lc.ligand_id, lc.ligand_name_SRD AS ligand_name,
                   COUNT(*) AS n_measurements
            FROM   ligandmetal_card c
            JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
            JOIN   ligand_card lc ON lc.ligand_id = c.ligand_id
            WHERE  c.metal_id = ?
            GROUP BY lc.ligand_id
            ORDER BY n_measurements DESC
            LIMIT 5
        """
        result["ligand_partners"] = _rows_to_dicts(conn.execute(partner_sql, (metal_id,)))
        prefix_ids_in_rows(result["ligand_partners"])

        totals = conn.execute(
            "SELECT COUNT(DISTINCT c.ligand_id) AS total_ligand_partners, "
            "       COUNT(*) AS total_vlm_measurements "
            "FROM   ligandmetal_card c "
            "JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
            "WHERE  c.metal_id = ?",
            (metal_id,),
        ).fetchone()
        result["total_ligand_partners"] = totals["total_ligand_partners"]
        result["total_vlm_measurements"] = totals["total_vlm_measurements"]

    return result


# ── ligand inspect ───────────────────────────────────────────────────

def _inspect_ligand(ligand_id: int) -> dict:
    """Full ligand card + pKa values + metal partner summary."""
    result: dict = {"prefix_id": f"ligand_{ligand_id}"}

    with get_cards_db() as conn:
        row = conn.execute(
            "SELECT * FROM ligand_card WHERE ligand_id = ?", (ligand_id,)
        ).fetchone()
        if not row:
            return {"prefix_id": f"ligand_{ligand_id}", "error": "not found"}
        result["card"] = dict(row)
        prefix_ids_in_row(result["card"])

        pka_sql = """
            SELECT pka_id, pKa, pKa_type, temperature_c AS temperature,
                   ionic_strength_mol_l AS ionic_strength,
                   bracket_from_state AS bracket_from,
                   bracket_to_state AS bracket_to,
                   measurement_method AS method, quality,
                   source, solvent_name AS solvent,
                   electrolyte, vlm_ids_json, notes
            FROM   ligand_pka_measured
            WHERE  ligand_id = ?
            ORDER BY pKa
        """
        pka_rows = _rows_to_dicts(conn.execute(pka_sql, (ligand_id,)))
        for pk in pka_rows:
            raw_vlm = _try_parse_json(pk.pop("vlm_ids_json", None))
            if isinstance(raw_vlm, list) and raw_vlm:
                pk["source_vlm_id"] = raw_vlm[0]      # always single-element
            else:
                pk["source_vlm_id"] = None
        result["pka_values"] = pka_rows
        prefix_ids_in_rows(result["pka_values"])

        partner_sql = """
            SELECT mc.metal_id, mc.metal_name_SRD AS metal_name,
                   COUNT(*) AS n_measurements
            FROM   ligandmetal_card c
            JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
            JOIN   metal_card mc ON mc.metal_id = c.metal_id
            WHERE  c.ligand_id = ?
            GROUP BY mc.metal_id
            ORDER BY n_measurements DESC
            LIMIT 5
        """
        result["metal_partners"] = _rows_to_dicts(conn.execute(partner_sql, (ligand_id,)))
        prefix_ids_in_rows(result["metal_partners"])

        totals = conn.execute(
            "SELECT COUNT(DISTINCT c.metal_id) AS total_metal_partners, "
            "       COUNT(*) AS total_vlm_measurements "
            "FROM   ligandmetal_card c "
            "JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
            "WHERE  c.ligand_id = ?",
            (ligand_id,),
        ).fetchone()
        result["total_metal_partners"] = totals["total_metal_partners"]
        result["total_vlm_measurements"] = totals["total_vlm_measurements"]

    return result


# ── VLM inspect ──────────────────────────────────────────────────────

def _inspect_vlm(vlm_id: int) -> dict:
    """Full VLM measurement with speciation, citations, and network membership."""
    result: dict = {"prefix_id": f"vlm_{vlm_id}"}

    from .stability_search import _enrich_stability_with_hxl_pka

    sql_card = """
        SELECT c.card_id,
               c.complex_system_id     AS vlm_id,
               c.metal_id,
               c.ligand_id,
               c.beta_definition_id,
               c.beta_definition_name,
               c.complex_id,
               c.ligand_class_name,
               c.metal_name_SRD        AS metal_name,
               c.ligand_name_SRD       AS ligand_name,
               c.ligand_HxL_definition_SRD AS ligand_HxL_definition,
               c.metal_SMILES,
               c.metal_InChi,
               c.ligand_SMILES,
               c.ligand_InChi,
               s.stability_id,
               s.constant_type,
               s.constant_value        AS log_K,
               s.temperature_c         AS temperature,
               s.ionic_strength_mol_l  AS ionic_strength,
               s.solvent_name          AS solvent,
               s.electrolyte_composition AS electrolyte,
               s.equation_python       AS equation,
               s.equation_str,
               s.raw_definition,
               s.normalized_definition,
               s.reaction_type,
               s.element_conserved,
               s.equation_tree_json,
               s.LHS_species_json,
               s.RHS_species_json,
               s.HxL_involved_json,
               s.presence_flags_json,
               s.citations_json,
               s.error                 AS uncertainty,
               s.notes,
               s.audit_timestamp
        FROM   ligandmetal_card c
        JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
        WHERE  c.complex_system_id = ?
    """

    sql_network = """
        SELECT n.network_db_id  AS network_id,
               n.node_count,
               n.edge_count,
               nd.node_db_id   AS node_id,
               nd.is_duplicate
        FROM   eqdb.eq_node nd
        JOIN   eqdb.eq_network n ON n.network_db_id = nd.network_db_id
        WHERE  nd.vlm_id = ?
    """

    sql_citations = """
        SELECT la.literature_alt_id,
               la.shortcut,
               la.citation
        FROM   litdb.vlm_literature_sic sic
        JOIN   litdb.literature_alt la ON la.literature_alt_id = sic.literature_alt_id
        WHERE  sic.vlm_id = ?
    """

    with attach_all_dbs() as conn:
        row = conn.execute(sql_card, (vlm_id,)).fetchone()
        if not row:
            return {"prefix_id": f"vlm_{vlm_id}", "error": "not found"}

        card = dict(row)
        _enrich_stability_with_hxl_pka([card])
        # Parse JSON fields to dicts/lists
        for key in ("equation_tree_json", "LHS_species_json", "RHS_species_json",
                     "HxL_involved_json", "presence_flags_json", "citations_json"):
            card[key] = _try_parse_json(card.get(key))
        result["card"] = card
        prefix_ids_in_row(result["card"])

        result["networks"] = _rows_to_dicts(conn.execute(sql_network, (vlm_id,)))
        prefix_ids_in_rows(result["networks"])
        # Return ALL citations for the VLM (was previously limited to 5; the
        # standalone ``inspect_literature`` tool has been folded in here).
        result["citations"] = _rows_to_dicts(conn.execute(
            sql_citations + " ORDER BY la.shortcut", (vlm_id,)))
        prefix_ids_in_rows(result["citations"])
        result["total_citations"] = len(result["citations"])

    return result


# ── public API ───────────────────────────────────────────────────────

def inspect_card(prefix_id: str) -> dict:
    """
    Deep inspection of a single entity by its prefix_id.

    Parameters
    ----------
    prefix_id : str
        One of: ``metal_N``, ``ligand_N``, ``vlm_N``.
        Examples: ``"metal_41"``, ``"ligand_5760"``, ``"vlm_93606"``

    Returns
    -------
    dict
        The full card with all available data including speciation context,
        partner summaries, pKa values, citations, and network membership.
    """
    try:
        kind, num_id = _parse_prefix_id(prefix_id)
    except ValueError as e:
        return {"error": str(e)}

    if kind == "metal":
        return _inspect_metal(num_id)
    elif kind == "ligand":
        return _inspect_ligand(num_id)
    elif kind == "vlm":
        return _inspect_vlm(num_id)
    else:
        return {"error": f"Unknown prefix type: {kind}"}


# Literature-only inspection for query-agent clients.
def _inspect_literature(vlm_id: int) -> dict:
    """All citations for a single VLM measurement."""
    result: dict = {"prefix_id": f"vlm_{vlm_id}"}

    sql = """
        SELECT la.literature_alt_id, la.shortcut, la.citation
        FROM   litdb.vlm_literature_sic sic
        JOIN   litdb.literature_alt la ON la.literature_alt_id = sic.literature_alt_id
        WHERE  sic.vlm_id = ?
        ORDER  BY la.shortcut
    """

    with attach_all_dbs() as conn:
        rows = _rows_to_dicts(conn.execute(sql, (vlm_id,)))
        prefix_ids_in_rows(rows)
        result["citations"] = rows
        result["total_citations"] = len(rows)

    return result


def inspect_literature(prefix_id: str) -> dict:
    """
    Return all citations for a VLM measurement.

    Parameters
    ----------
    prefix_id : str
        A VLM prefix_id, e.g. ``"vlm_93847"``.

    Returns
    -------
    dict
        ``{"prefix_id": ..., "citations": [...], "total_citations": N}``
    """
    kind, num_id = parse_prefixed_id(prefix_id)
    if kind != "vlm":
        return {"error": f"inspect_literature requires a vlm prefix_id, got '{kind}'"}
    return _inspect_literature(num_id)
