"""
SQL-WHERE citation search.

``search_citations(sql_where_query)`` queries
``ref_vlm_literature_alt rv ⨝ ref_literature_alt la`` and returns
distinct citation rows, plus a representative VLM and the number of
linked VLM records.
"""

from ._normalization_helpers.id_prefixer import prefix_ids_in_rows
from ._search_helpers import (
    parse_sql_where_query,
    validate_clause,
    resolve_prefixed_ids,
    HARD_LIMIT,
)
from ._db_connection import get_cards_db


def search_citations(
    sql_where_query: str = "1=1",
) -> list[dict]:
    """
    SQL-WHERE search for literature citations.

    Parameters
    ----------
    sql_where_query : str
        Full SQL WHERE fragment with optional trailing ``ORDER BY`` and
        ``LIMIT``; leading ``WHERE`` keyword optional. Filterable columns:
        rv.vlm_id, la.shortcut, la.citation, la.literature_alt_id.

        Examples:
          ``"la.shortcut = '62Pc'"``
          ``"rv.vlm_id IN (93606, 93607) ORDER BY la.citation LIMIT 10"``

    Returns
    -------
    list[dict]
    """
    validate_clause(sql_where_query)
    where, order_by, limit = parse_sql_where_query(sql_where_query)
    where = resolve_prefixed_ids(where)

    sql = f"""
        SELECT MIN(rv.vlm_id)          AS example_vlm_id,
               COUNT(DISTINCT rv.vlm_id) AS vlm_count,
               la.literature_alt_id,
               la.shortcut,
               la.citation
        FROM   ref_vlm_literature_alt rv
        JOIN   ref_literature_alt la ON la.literature_alt_id = rv.literature_alt_id
        WHERE  {where}
        GROUP  BY la.literature_alt_id, la.shortcut, la.citation
    """
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {limit}"

    with get_cards_db() as conn:
        rows = [dict(row) for row in conn.execute(sql).fetchall()]
    return prefix_ids_in_rows(rows)
