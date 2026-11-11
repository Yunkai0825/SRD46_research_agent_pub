"""
Entity search — resolve metal and ligand names to cards.

Public functions:
  * ``search_metals()``  — query ``metal_card``
  * ``search_ligands()`` — query ``ligand_card`` (with pKa brackets + InChI/SMILES fallback)
"""

import logging
import sqlite3
from typing import Optional

from ._db_connection import get_cards_db
from ._normalization_helpers.metal_resolution import (
    _expand_metal_name,
    _normalize_metal_query,
    _extract_symbol_charge_query,
)
from ._normalization_helpers.ligand_resolution import (
    _resolve_ligand_identifiers,
)
from ._normalization_helpers.id_prefixer import prefix_ids_in_rows
from ._normalization_helpers.functional_group_catalog import filter_by_groups

log = logging.getLogger("SRD46")


# ── Shared utility ───────────────────────────────────────────────────

def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    """Convert sqlite3.Row results into plain dicts."""
    return [dict(row) for row in cursor.fetchall()]


# =====================================================================
#  Metal search
# =====================================================================

def search_metals(
    name: Optional[str] = None,
    symbol: Optional[str] = None,
    metal_id: Optional[int] = None,
    smiles: Optional[str] = None,
    inchi: Optional[str] = None,
    limit: int = 50,
    exclude: Optional[str] = None,
) -> list[dict]:
    """
    Search the metal_card table.

    Parameters
    ----------
    name : str, optional    -- partial match against metal name (e.g. 'Cu', 'Iron')
    symbol : str, optional  -- partial match against symbol (e.g. 'Cu2+')
    metal_id : int, optional -- exact metal_id
    smiles : str, optional  -- partial or exact SMILES string (e.g. '[Cu+2]')
    inchi : str, optional   -- partial or exact InChI string
    limit : int -- max rows returned (default 50)
    exclude : str, optional -- comma-separated metal_ids to exclude

    Returns dicts with keys: metal_id, metal_name, symbol, charge,
        is_simple_ion, smiles, inchi
    """
    clauses, params = [], []

    if metal_id is not None:
        clauses.append("metal_id = ?")
        params.append(metal_id)
    if name:
        terms = _expand_metal_name(name)
        or_parts = []
        for t in terms:
            or_parts.append("metal_name_SRD LIKE ?")
            params.append(f"%{t}%")
            or_parts.append("symbol_pure LIKE ?")
            params.append(f"%{t}%")
        clauses.append(f"({' OR '.join(or_parts)})")
    if symbol:
        base_symbol, charge_number = _extract_symbol_charge_query(symbol)
        or_parts = []
        if base_symbol:
            if charge_number is not None:
                or_parts.append("(symbol_pure LIKE ? AND charge = ?)")
                params.extend([f"%{base_symbol}%", charge_number])
                or_parts.append("metal_name_SRD LIKE ?")
                params.append(f"%{base_symbol}^[{charge_number}+]%")
            else:
                or_parts.append("symbol_pure LIKE ?")
                params.append(f"%{base_symbol}%")
                or_parts.append("metal_name_SRD LIKE ?")
                params.append(f"%{base_symbol}%")
        if or_parts:
            clauses.append(f"({' OR '.join(or_parts)})")
    if smiles:
        clauses.append("SMILES LIKE ?")
        params.append(f"%{smiles}%")
    if inchi:
        clauses.append("InChi LIKE ?")
        params.append(f"%{inchi}%")
    if exclude:
        try:
            excl_ids = [int(x.strip()) for x in exclude.split(",") if x.strip()]
        except ValueError:
            excl_ids = []
        if excl_ids:
            placeholders_ex = ",".join("?" * len(excl_ids))
            clauses.append(f"metal_id NOT IN ({placeholders_ex})")
            params.extend(excl_ids)

    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
        SELECT metal_id,
               metal_name_SRD  AS metal_name,
               symbol_pure     AS symbol,
               charge,
               is_simple_ion,
               SMILES          AS smiles,
               InChi           AS inchi
        FROM   metal_card
        WHERE  {where}
        LIMIT  ?
    """
    params.append(limit)

    with get_cards_db() as conn:
        rows = _rows_to_dicts(conn.execute(sql, params))

        # -- Attach data-richness counts per metal -------------------------
        if rows:
            mid_list = [r["metal_id"] for r in rows]
            placeholders = ",".join("?" * len(mid_list))
            rich_sql = (
                f"SELECT metal_id, "
                f"       COUNT(DISTINCT beta_definition_id) AS beta_def_count, "
                f"       COUNT(DISTINCT ligand_id)          AS ligand_count, "
                f"       COUNT(DISTINCT complex_system_id)  AS vlm_count "
                f"FROM   ligandmetal_card "
                f"WHERE  metal_id IN ({placeholders}) "
                f"GROUP BY metal_id"
            )
            rich_rows = conn.execute(rich_sql, mid_list).fetchall()
            rich_map = {r["metal_id"]: dict(r) for r in rich_rows}
            for row in rows:
                rm = rich_map.get(row["metal_id"], {})
                row["beta_def_count"] = rm.get("beta_def_count", 0)
                row["ligand_count"] = rm.get("ligand_count", 0)
                row["vlm_count"] = rm.get("vlm_count", 0)

    return prefix_ids_in_rows(rows)


# =====================================================================
#  Ligand search
# =====================================================================

def _search_ligands_core(clauses, params, limit, conn):
    """Core ligand SQL query."""
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
        SELECT ligand_id,
               ligand_name_SRD      AS ligand_name,
               definition_HxL       AS ligand_HxL_definition,
               figure_definition    AS ligand_figure_definition,
               formula,
               ligand_class_name    AS ligand_class,
               synonym_iupac_name   AS iupac_name,
               synonym_common_name  AS common_name,
               ligand_SMILES        AS smiles,
               ligand_InChi         AS inchi
        FROM   ligand_card
        WHERE  {where}
        LIMIT  ?
    """
    return _rows_to_dicts(conn.execute(sql, params + [limit]))


def _count_ligands(clauses, params, conn) -> int:
    """COUNT(*) for the same WHERE used by _search_ligands_core."""
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT COUNT(*) AS n FROM ligand_card WHERE {where}"
    return conn.execute(sql, params).fetchone()["n"]


def _fetch_all_smiles(clauses, params, conn) -> list[str]:
    """Fetch ligand_SMILES for ALL rows matching the WHERE clause (no LIMIT)."""
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT ligand_SMILES FROM ligand_card WHERE {where} AND ligand_SMILES IS NOT NULL AND ligand_SMILES != ''"
    return [row["ligand_SMILES"] for row in conn.execute(sql, params)]


def search_ligands(
    name: Optional[str] = None,
    formula: Optional[str] = None,
    ligand_class: Optional[str] = None,
    ligand_id: Optional[int] = None,
    smiles: Optional[str] = None,
    inchi: Optional[str] = None,
    limit: int = 50,
    exclude: Optional[str] = None,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> dict:
    """
    Search the ligand_card table.

    Parameters
    ----------
    name : str, optional      -- partial match on ligand name
    formula : str, optional   -- partial match on chemical formula
    ligand_class : str, optional -- partial match on ligand class
    ligand_id : int, optional -- exact ligand_id
    smiles : str, optional    -- partial or exact SMILES string
    inchi : str, optional     -- partial or exact InChI string
    limit : int -- max rows (default 50)
    exclude : str, optional   -- comma-separated ligand_ids to exclude
    include_groups : list[str], optional
        Functional-group names (from ``list_functional_groups()``) or raw
        SMARTS patterns.  A ligand is kept only if it contains **all** of
        these substructures.
    exclude_groups : list[str], optional
        Functional-group names or raw SMARTS.  A ligand is excluded if it
        contains **any** of these substructures.

    Returns
    -------
    dict
        ``{"results": [...], "total_sql_matches": N,
           "excluded_by_groups": M, "limit": L}``

        Each result dict has keys: ligand_id, ligand_name, formula,
        ligand_class, iupac_name, common_name, smiles, inchi,
        pka_brackets.

    Notes
    -----
    Fallback: if a name-only search returns 0 rows, the function resolves
    the name via PubChemPy → InChI (canonical) → SMILES (backup) and
    retries the search automatically.
    """
    clauses, params = [], []
    if ligand_id is not None:
        clauses.append("ligand_id = ?")
        params.append(ligand_id)
    if name:
        clauses.append("ligand_name_SRD LIKE ?")
        params.append(f"%{name}%")
    if formula:
        clauses.append("formula LIKE ?")
        params.append(f"%{formula}%")
    if ligand_class:
        clauses.append("ligand_class_name LIKE ?")
        params.append(f"%{ligand_class}%")
    if smiles:
        clauses.append("ligand_SMILES LIKE ?")
        params.append(f"%{smiles}%")
    if inchi:
        clauses.append("ligand_InChi LIKE ?")
        params.append(f"%{inchi}%")
    if exclude:
        try:
            excl_ids = [int(x.strip()) for x in exclude.split(",") if x.strip()]
        except ValueError:
            excl_ids = []
        if excl_ids:
            placeholders_ex = ",".join("?" * len(excl_ids))
            clauses.append(f"ligand_id NOT IN ({placeholders_ex})")
            params.extend(excl_ids)

    # Decide whether functional-group filtering applies
    apply_group_filter = bool(include_groups or exclude_groups)

    with get_cards_db() as conn:
        total_sql = _count_ligands(clauses, params, conn)

        # When group-filtering is active, fetch all SQL matches (filtering
        # is substructure-based and cannot be predicted from SQL alone).
        fetch_limit = total_sql if apply_group_filter else limit
        rows = _search_ligands_core(clauses, params, fetch_limit, conn)

        # -- Fallback: name-only search returned 0 → try InChI / SMILES --
        if not rows and name and not (formula or smiles or inchi or ligand_id):
            ids = _resolve_ligand_identifiers(name)
            if ids["inchi"]:
                log.info("   -> fallback: searching ligand_InChi for '%s'", ids["inchi"][:50])
                fb_clauses = ["ligand_InChi LIKE ?"]
                fb_params = [f"%{ids['inchi']}%"]
                total_sql = _count_ligands(fb_clauses, fb_params, conn)
                fetch_limit = total_sql if apply_group_filter else limit
                rows = _search_ligands_core(fb_clauses, fb_params, fetch_limit, conn)
            if not rows and ids["smiles"]:
                log.info("   -> fallback: searching ligand_SMILES for '%s'", ids["smiles"][:50])
                fb_clauses = ["ligand_SMILES LIKE ?"]
                fb_params = [f"%{ids['smiles']}%"]
                total_sql = _count_ligands(fb_clauses, fb_params, conn)
                fetch_limit = total_sql if apply_group_filter else limit
                rows = _search_ligands_core(fb_clauses, fb_params, fetch_limit, conn)

        # -- Functional-group filtering --------------------------------
        excluded_count = 0
        if apply_group_filter and rows:
            rows, excluded_count = filter_by_groups(
                rows, include=include_groups, exclude=exclude_groups
            )
            rows = rows[:limit]
        else:
            rows = rows[:limit]

        # -- Attach pKa brackets for each ligand -------------------------
        if rows:
            lid_list = [r["ligand_id"] for r in rows]
            placeholders = ",".join("?" * len(lid_list))
            bracket_sql = (
                f"SELECT ligand_id, state_id, charge, formula, "
                f"       HxL_form, bracket_label, is_estimated "
                f"FROM   ligand_pka_bracket "
                f"WHERE  ligand_id IN ({placeholders}) "
                f"  AND  is_estimated = 0 "
                f"ORDER BY ligand_id, bracket_id"
            )
            bracket_rows = _rows_to_dicts(conn.execute(bracket_sql, lid_list))
            brackets_by_lid: dict[int, list[dict]] = {}
            for br in bracket_rows:
                lid = br.pop("ligand_id")
                brackets_by_lid.setdefault(lid, []).append(br)
            for row in rows:
                row["pka_brackets"] = brackets_by_lid.get(row["ligand_id"], [])

            # -- Attach VLM entry count per ligand ----------------------------
            vlm_sql = (
                f"SELECT ligand_id, COUNT(DISTINCT complex_system_id) AS vlm_count "
                f"FROM   ligandmetal_card "
                f"WHERE  ligand_id IN ({placeholders}) "
                f"GROUP BY ligand_id"
            )
            vlm_rows = conn.execute(vlm_sql, lid_list).fetchall()
            vlm_map = {r["ligand_id"]: r["vlm_count"] for r in vlm_rows}
            for row in rows:
                row["vlm_count"] = vlm_map.get(row["ligand_id"], 0)

        prefix_ids_in_rows(rows)

        # -- Collect ALL SMILES from the full SQL match set ---------------
        all_smiles = _fetch_all_smiles(clauses, params, conn)

    return {
        "results": rows,
        "total_sql_matches": total_sql,
        "excluded_by_groups": excluded_count,
        "limit": limit,
        "all_smiles": all_smiles,
    }
