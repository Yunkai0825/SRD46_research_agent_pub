"""
SQL-WHERE equilibrium-network search.

``search_networks(sql_where_query, ...)`` queries
``eq_map_collection c ⨝ eq_map m ⨝ eq_network n ⨝ eq_node nd``.

The ``sql_where_query`` parameter accepts a full SQL WHERE fragment
with optional trailing ``ORDER BY`` and ``LIMIT``. Note: ``LIMIT``
applies to *distinct networks* (all node rows for matching networks
are returned).

Temperature and ionic-strength screening is part of the SQL WHERE —
use ``m.condition_temp_min``, ``m.condition_temp_max``,
``m.condition_ionic_min``, ``m.condition_ionic_max``.
"""

from typing import Optional

from ._normalization_helpers.id_prefixer import prefix_ids_in_rows
from ._search_helpers import (
    parse_sql_where_query,
    validate_clause,
    resolve_prefixed_ids,
    HARD_LIMIT,
    expand_where_with_similar,
    rows_to_dicts,
    log,
)
from ._db_connection import get_equilibrium_db, CARDS_DB


_NETWORK_SELECT = """
    SELECT n.network_db_id,
           c.metal_id            AS metal_id,
           c.ligand_id           AS ligand_id,
           c.metal_name          AS metal_name,
           c.ligand_name         AS ligand_name,
           lc.definition_HxL    AS ligand_HxL_definition,
           lc.ligand_SMILES     AS ligand_SMILES,
           n.node_count,
           n.edge_count,
           m.condition_temp_min  AS temp_min,
           m.condition_temp_max  AS temp_max,
           m.condition_ionic_min AS ionic_min,
           m.condition_ionic_max AS ionic_max,
           nd.node_db_id         AS node_id,
           nd.vlm_id             AS vlm_id,
           nd.beta_definition_id AS beta_definition_id,
           nd.beta_definition_name AS beta_definition_name,
           nd.equation_python    AS equation,
           nd.constant_type      AS constant_type,
           nd.constant_value     AS log_K
    FROM   eq_map_collection c
    JOIN   eq_map m  ON m.collection_id = c.collection_id
    JOIN   eq_network n ON n.map_id = m.map_id
    JOIN   eq_node nd ON nd.network_db_id = n.network_db_id
    LEFT JOIN cardsdb.ligand_card lc ON lc.ligand_id = c.ligand_id
"""


def _execute_network_query(
    where: str, order_by: str, net_limit: str,
) -> list[dict]:
    """Run network query, limiting by *distinct network_db_id* count.

    First fetches up to ``net_limit`` distinct network IDs that match the
    WHERE, then retrieves **all** rows (nodes) for those networks so no
    network is partially truncated. ``net_limit`` is a bare integer
    string; pass ``""`` to omit the LIMIT clause entirely.
    """
    # Step 1: get qualifying network IDs
    id_sql = (
        f"SELECT DISTINCT n.network_db_id "
        f"FROM eq_map_collection c "
        f"JOIN eq_map m ON m.collection_id = c.collection_id "
        f"JOIN eq_network n ON n.map_id = m.map_id "
        f"JOIN eq_node nd ON nd.network_db_id = n.network_db_id "
        f"LEFT JOIN cardsdb.ligand_card lc ON lc.ligand_id = c.ligand_id "
        f"WHERE {where}"
    )
    if net_limit:
        id_sql += f" LIMIT {net_limit}"

    with get_equilibrium_db() as conn:
        conn.execute("ATTACH DATABASE ? AS cardsdb", (str(CARDS_DB),))
        net_ids = [r[0] for r in conn.execute(id_sql).fetchall()]
        if not net_ids:
            return []

        # Step 2: fetch all rows for those networks
        placeholders = ",".join("?" * len(net_ids))
        full_sql = (
            f"{_NETWORK_SELECT} WHERE n.network_db_id IN ({placeholders})"
        )
        if order_by:
            full_sql += f" ORDER BY {order_by}"
        return rows_to_dicts(conn.execute(full_sql, net_ids))


def search_networks(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
) -> list[dict]:
    """
    SQL-WHERE search for equilibrium networks.

    Parameters
    ----------
    sql_where_query : str
        Full SQL WHERE fragment with optional trailing ``ORDER BY`` and
        ``LIMIT``; leading ``WHERE`` keyword optional. Filterable columns:
        c.metal_id, c.ligand_id, c.metal_name, c.ligand_name,
        n.node_count, n.edge_count, nd.vlm_id,
        nd.constant_type, nd.constant_value,
        m.condition_temp_min, m.condition_temp_max,
        m.condition_ionic_min, m.condition_ionic_max.

        ``LIMIT`` here applies to distinct networks; all rows (nodes)
        belonging to each qualifying network are returned regardless.

    ligand_similarity : bool
        Expand ligand filter to structurally similar ligands.

    Returns
    -------
    list[dict]
    """
    validate_clause(sql_where_query)
    where, order_by, limit = parse_sql_where_query(sql_where_query)
    where = resolve_prefixed_ids(where)

    effective_where = where
    if ligand_similarity:
        effective_where = expand_where_with_similar(where, "network")

    rows = _execute_network_query(effective_where, order_by, limit)

    if not rows and not ligand_similarity:
        expanded = expand_where_with_similar(where, "network")
        if expanded != where:
            rows = _execute_network_query(expanded, order_by, limit)
            if rows:
                log.info("   -> similarity fallback: %d rows via ligand expansion", len(rows))

    return prefix_ids_in_rows(rows)
