"""
SQL-WHERE pKa search — value-centric and ligand-centric views.

Temperature and ionic-strength screening is part of the SQL WHERE —
use ``p.temperature_c``, ``p.ionic_strength_mol_l``.
"""

import logging
from typing import Optional

from ._db_connection import get_cards_db
from ._normalization_helpers.id_prefixer import prefix_ids_in_rows, unprefix_id
from ._normalization_helpers.functional_group_catalog import filter_by_groups
from ._search_helpers import (
    parse_sql_where_query,
    validate_clause,
    HARD_LIMIT,
    expand_where_with_similar,
    get_similarity_score_map,
    execute_template,
    log,
)


_PKA_SELECT = """
    SELECT lc.ligand_id,
           lc.ligand_name_SRD         AS ligand_name,
           lc.definition_HxL          AS ligand_HxL_definition,
           lc.ligand_class_name,
           lc.formula,
           lc.ligand_SMILES           AS smiles,
           CAST(REPLACE(REPLACE(p.vlm_ids_json, '[', ''), ']', '') AS INTEGER)
                                      AS source_vlm_id,
           p.pka_id,
           p.pKa,
           p.pKa_type,
           p.temperature_c            AS temperature,
           p.ionic_strength_mol_l     AS ionic_strength,
           p.solvent_name             AS solvent,
           p.electrolyte              AS electrolyte,
           p.bracket_from_state       AS bracket_from,
           p.bracket_to_state         AS bracket_to,
           p.measurement_method       AS method,
           p.quality
    FROM   ligand_card lc
    JOIN   ligand_pka_measured p ON p.ligand_id = lc.ligand_id
"""


# ── shared pKa core ─────────────────────────────────────────────────

def _search_pka_core(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> list[dict]:
    """Shared logic for all pKa queries."""
    validate_clause(sql_where_query)
    where, order_by, limit = parse_sql_where_query(sql_where_query)

    effective_where = where
    similarity_scores: dict[int, float] = {}
    if ligand_similarity:
        similarity_scores = get_similarity_score_map(where)
        effective_where = expand_where_with_similar(where, "pka")

    apply_group_filter = bool(include_groups or exclude_groups)
    fetch_limit = str(HARD_LIMIT) if apply_group_filter else limit

    rows = execute_template(_PKA_SELECT, effective_where, order_by, fetch_limit, False)

    if not rows and not ligand_similarity:
        expanded = expand_where_with_similar(where, "pka")
        if expanded != where:
            rows = execute_template(_PKA_SELECT, expanded, order_by, fetch_limit, False)
            if rows:
                similarity_scores = get_similarity_score_map(where)
                log.info("   -> similarity fallback: %d rows via ligand expansion", len(rows))

    if apply_group_filter and rows:
        rows, excluded = filter_by_groups(
            rows, include=include_groups, exclude=exclude_groups,
            smiles_key="smiles",
        )
        if excluded:
            log.info("   -> group filter: kept %d, excluded %d", len(rows), excluded)
        if limit:
            rows = rows[:int(limit)]
    # else: SQL LIMIT (if any) was already applied

    for r in rows:
        raw_id = unprefix_id(r.get("ligand_id", ""))
        if raw_id in similarity_scores:
            r["similarity_score"] = round(similarity_scores[raw_id], 4)

    return prefix_ids_in_rows(rows)


def _enrich_pka_with_metal_counts(rows: list[dict]) -> None:
    """Add ``M_tot``, ``M_above``, ``M_below`` to each pKa row in-place."""
    ligand_ids = {unprefix_id(r.get("ligand_id", "")) for r in rows}
    ligand_ids.discard(None)
    if not ligand_ids:
        return
    placeholders = ",".join("?" * len(ligand_ids))
    ids = list(ligand_ids)

    with get_cards_db() as conn:
        tot_sql = (
            f"SELECT ligand_id, COUNT(DISTINCT metal_id) AS M_tot "
            f"FROM ligandmetal_card "
            f"WHERE ligand_id IN ({placeholders}) "
            f"GROUP BY ligand_id"
        )
        tot_counts = {
            row[0]: row[1]
            for row in conn.execute(tot_sql, ids).fetchall()
        }

        form_sql = (
            f"SELECT lm.ligand_id, je.value, COUNT(DISTINCT lm.metal_id) "
            f"FROM ligandmetal_stability_measured s "
            f"JOIN ligandmetal_card lm ON s.card_id = lm.card_id "
            f"CROSS JOIN json_each(s.HxL_involved_json) je "
            f"WHERE lm.ligand_id IN ({placeholders}) "
            f"  AND s.HxL_involved_json IS NOT NULL "
            f"  AND s.HxL_involved_json != '[]' "
            f"  AND s.HxL_involved_json != '' "
            f"GROUP BY lm.ligand_id, je.value"
        )
        form_counts: dict[tuple, int] = {}
        for row in conn.execute(form_sql, ids).fetchall():
            form_counts[(row[0], row[1])] = row[2]

    for r in rows:
        raw_id = unprefix_id(r.get("ligand_id", ""))
        r["M_tot"] = tot_counts.get(raw_id, 0)
        bfrom = r.get("bracket_from", "") or ""
        bto = r.get("bracket_to", "") or ""
        r["M_above"] = form_counts.get((raw_id, f"[{bfrom}]"), 0)
        r["M_below"] = form_counts.get((raw_id, f"[{bto}]"), 0)


# ── public API ───────────────────────────────────────────────────────

def search_pka_values(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> list[dict]:
    """Value-centric pKa search — results grouped by 0.5-unit pKa bands.

    Parameters
    ----------
    sql_where_query : str
        Full SQL WHERE fragment with optional trailing ``ORDER BY`` and
        ``LIMIT``; leading ``WHERE`` keyword optional. Filterable columns
        (use ``lc.`` or ``p.`` prefix):
        lc.ligand_id, lc.ligand_name_SRD, lc.ligand_class_name,
        p.pKa, p.pKa_type, p.temperature_c, p.ionic_strength_mol_l,
        p.solvent_name, p.electrolyte, p.quality.

        Examples:
          ``"lc.ligand_id IN (5760, 9058) ORDER BY p.pKa ASC"``
          ``"lc.ligand_class_name = 'amino acid' LIMIT 30"``

    ligand_similarity, include_groups, exclude_groups
        Same as ``search_stability``.
    """
    rows = _search_pka_core(sql_where_query, ligand_similarity,
                            include_groups, exclude_groups)
    _enrich_pka_with_metal_counts(rows)
    return rows


def search_pka_ligands(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> list[dict]:
    """Ligand-centric pKa search — results grouped by ligand with pKa ladder.

    Parameters are identical to ``search_pka_values``.
    """
    rows = _search_pka_core(sql_where_query, ligand_similarity,
                            include_groups, exclude_groups)
    _enrich_pka_with_metal_counts(rows)
    return rows
