"""
SQL-WHERE stability-constant search.

``search_stability(sql_where_query, ...)`` queries
``ligandmetal_card c ⨝ ligandmetal_stability_measured s``.

The ``sql_where_query`` parameter accepts a full SQL fragment: WHERE
predicate + optional trailing ``ORDER BY`` and ``LIMIT``. Temperature
and ionic-strength screening is part of the SQL WHERE clause — callers
can filter directly with ``s.temperature_c = 25`` or
``s.ionic_strength_mol_l BETWEEN 0.1 AND 1.0``.
"""

import json as _json
import logging
from typing import Optional

from ._db_connection import get_cards_db, get_equilibrium_db
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


_STABILITY_SELECT = """
    SELECT c.complex_system_id       AS vlm_id,
           c.metal_id,
           c.ligand_id,
           c.beta_definition_id,
           c.beta_definition_name,
           c.metal_name_SRD          AS metal_name,
           c.ligand_name_SRD         AS ligand_name,
           c.ligand_SMILES,
           c.ligand_HxL_definition_SRD AS ligand_HxL_definition,
           c.ligand_class_name,
           s.constant_type,
           s.constant_value          AS log_K,
           s.temperature_c           AS temperature,
           s.ionic_strength_mol_l    AS ionic_strength,
           s.equation_python         AS equation,
           s.reaction_type,
           s.solvent_name            AS solvent,
           s.electrolyte_composition AS electrolyte,
           s.LHS_species_json,
           s.RHS_species_json,
           s.equation_tree_json,
           s.equation_str,
           s.HxL_involved_json
    FROM   ligandmetal_card c
    JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
"""


def search_stability(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> list[dict]:
    """
    SQL-WHERE search for stability constants.

    Parameters
    ----------
    sql_where_query : str
        Full SQL WHERE fragment with optional trailing ``ORDER BY`` and
        ``LIMIT``. The leading ``WHERE`` keyword is optional. Default
        ``"1=1"`` (return everything, subject to ``LIMIT`` if supplied).
        Filterable columns (use ``c.`` or ``s.`` prefix):
        c.metal_id, c.ligand_id, c.beta_definition_id, c.metal_name_SRD,
        c.ligand_name_SRD, c.ligand_class_name,
        s.constant_type, s.constant_value, s.temperature_c,
        s.ionic_strength_mol_l, s.reaction_type, s.solvent_name,
        s.electrolyte_composition.

        Examples:
          ``"c.metal_id = 41 AND c.ligand_id IN (5760, 9058)"``
          ``"c.metal_id = 41 ORDER BY s.constant_value DESC LIMIT 20"``

    ligand_similarity : bool
        Expand ligand filter to structurally similar ligands.

    include_groups / exclude_groups : list[str], optional
        Functional-group names or raw SMARTS for substructure filtering.

    Returns
    -------
    list[dict]
        Stability rows with speciation columns.
    """
    validate_clause(sql_where_query)
    where, order_by, limit = parse_sql_where_query(sql_where_query)

    effective_where = where
    similarity_scores: dict[int, float] = {}
    if ligand_similarity:
        similarity_scores = get_similarity_score_map(where)
        effective_where = expand_where_with_similar(where, "stability")

    apply_group_filter = bool(include_groups or exclude_groups)
    # Over-fetch when group-filtering so post-filter slicing has rows to choose from.
    fetch_limit = str(HARD_LIMIT) if apply_group_filter else limit

    rows = execute_template(_STABILITY_SELECT, effective_where, order_by, fetch_limit, False)

    # Fallback: similarity expansion when the exact query returned nothing
    if not rows and not ligand_similarity:
        expanded = expand_where_with_similar(where, "stability")
        if expanded != where:
            rows = execute_template(_STABILITY_SELECT, expanded, order_by, fetch_limit, False)
            if rows:
                similarity_scores = get_similarity_score_map(where)
                log.info("   -> similarity fallback: %d rows via ligand expansion", len(rows))

    if apply_group_filter and rows:
        rows, excluded = filter_by_groups(
            rows, include=include_groups, exclude=exclude_groups,
            smiles_key="ligand_SMILES",
        )
        if excluded:
            log.info("   -> group filter: kept %d, excluded %d", len(rows), excluded)
        if limit:
            rows = rows[:int(limit)]
    # else: no group filter — LIMIT (if any) was already applied in SQL

    for row in rows:
        raw_ligand_id = unprefix_id(row.get("ligand_id", ""))
        if raw_ligand_id in similarity_scores:
            row["similarity_score"] = round(
                similarity_scores[raw_ligand_id], 4
            )

    if rows:
        _enrich_stability_with_hxl_pka(rows)
        _enrich_stability_with_ref_eq_map(rows)

    return prefix_ids_in_rows(rows)


# ── enrichment helpers ───────────────────────────────────────────────

def _enrich_stability_with_ref_eq_map(rows: list[dict]) -> None:
    """Attach the equilibrium map ID for each stability VLM row in-place."""
    vlm_ids: set[int] = set()
    for r in rows:
        raw = unprefix_id(r.get("vlm_id", ""))
        if raw is not None:
            vlm_ids.add(raw)
    if not vlm_ids:
        return

    placeholders = ",".join("?" * len(vlm_ids))
    sql = (
        f"SELECT nd.vlm_id, MIN(n.map_id) AS map_id "
        f"FROM   eq_node nd "
        f"JOIN   eq_network n ON n.network_db_id = nd.network_db_id "
        f"WHERE  nd.vlm_id IN ({placeholders}) "
        f"GROUP BY nd.vlm_id"
    )

    with get_equilibrium_db() as conn:
        map_by_vlm = {
            int(vlm_id): map_id
            for vlm_id, map_id in conn.execute(sql, list(vlm_ids)).fetchall()
            if map_id is not None
        }

    for r in rows:
        raw_vlm = unprefix_id(r.get("vlm_id", ""))
        r["map_id"] = map_by_vlm.get(raw_vlm)


def _enrich_stability_with_hxl_pka(rows: list[dict]) -> None:
    """Parse HxL_involved_json and attach pKa stability brackets."""

    def _parse_bracket_label(label: str) -> tuple[str, str]:
        inner = str(label or "").strip().strip("()")
        parts = [x.strip() for x in inner.split(",", 1)] if inner else ["?", "?"]
        lo = parts[0] if len(parts) > 0 else "?"
        hi = parts[1] if len(parts) > 1 else "?"
        return lo, hi

    def _format_segment(segment: list[dict]) -> str:
        first_lo, first_hi = _parse_bracket_label(segment[0].get("bracket_label", ""))
        parts: list[str] = [first_lo, segment[0].get("HxL_form", "?")]
        parts.append(first_hi)
        for bracket in segment[1:]:
            _, hi = _parse_bracket_label(bracket.get("bracket_label", ""))
            parts.append(bracket.get("HxL_form", "?"))
            parts.append(hi)
        return "(" + ", ".join(parts) + ")"

    ligand_ids: set[int] = set()
    for r in rows:
        raw = unprefix_id(r.get("ligand_id", ""))
        if raw is not None:
            ligand_ids.add(raw)
    if not ligand_ids:
        return

    placeholders = ",".join("?" * len(ligand_ids))
    ids = list(ligand_ids)
    bracket_sql = (
        f"SELECT ligand_id, bracket_id, HxL_form, bracket_label "
        f"FROM   ligand_pka_bracket "
        f"WHERE  ligand_id IN ({placeholders}) "
        f"  AND  is_estimated = 0 "
        f"ORDER BY ligand_id, bracket_id"
    )
    bracket_map: dict[int, list[dict]] = {}
    with get_cards_db() as conn:
        for row in conn.execute(bracket_sql, ids).fetchall():
            lid = row[0]
            bracket_map.setdefault(lid, []).append(
                {
                    "bracket_id": row[1],
                    "HxL_form": row[2] or "",
                    "bracket_label": row[3] or "",
                }
            )

    for r in rows:
        raw_json = r.get("HxL_involved_json")
        forms: list[str] = []
        if raw_json:
            try:
                parsed = _json.loads(raw_json)
                if isinstance(parsed, list):
                    forms = [str(f) for f in parsed]
            except (ValueError, TypeError):
                pass
        r["HxL_involved"] = "; ".join(forms) if forms else ""

        raw_lid = unprefix_id(r.get("ligand_id", ""))
        ligand_brackets = bracket_map.get(raw_lid, []) if raw_lid else []
        if not forms or not ligand_brackets:
            r["pKa_bracket_involved"] = ""
            continue

        wanted = {form.strip("[]") for form in forms}
        selected: list[tuple[int, dict]] = []
        for idx, bracket in enumerate(ligand_brackets):
            if bracket.get("HxL_form", "") in wanted:
                selected.append((idx, bracket))

        if not selected:
            r["pKa_bracket_involved"] = ""
            continue

        segments: list[list[dict]] = []
        current: list[dict] = [selected[0][1]]
        prev_idx = selected[0][0]
        for idx, bracket in selected[1:]:
            if idx == prev_idx + 1:
                current.append(bracket)
            else:
                segments.append(current)
                current = [bracket]
            prev_idx = idx
        segments.append(current)

        r["pKa_bracket_involved"] = "; ".join(_format_segment(seg) for seg in segments)
