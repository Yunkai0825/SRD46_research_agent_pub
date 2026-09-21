"""
Aggregate queries and raw SQL execution.

Provides counting, distribution, ranking, schema introspection, and
a capped read-only SQL gateway across all three SRD-46 databases.
"""

import logging
import re
from typing import Optional

from ._db_connection import (
    attach_all_dbs,
    get_cards_db,
    get_equilibrium_db,
    get_literature_db,
)
from ._normalization_helpers.id_prefixer import prefix_ids_in_rows
from ._search_helpers import resolve_prefixed_ids
from . import _sql_ast as _sa

log = logging.getLogger("SRD46")


def _rows_to_dicts(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


# ── safety ───────────────────────────────────────────────────────────

_BLOCKED_KEYWORDS = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
                     "CREATE", "REPLACE", "TRUNCATE"}


def _validate_read_only(sql: str) -> None:
    """Reject DDL/DML at any depth; allow read-only sub-SELECTs.

    Backed by a sqlglot AST walk so reserved keywords inside string literals
    (e.g. ``WHERE note = 'we will SELECT later'``) no longer false-trigger.
    """
    if not sql or not sql.strip():
        return
    head = sql.lstrip().split(None, 1)[:1]
    first = head[0].upper() if head else ""
    # Cheap up-front check for top-level DDL/DML — gives a clean error
    # message and avoids a confusing sqlglot parse failure on naked DROP etc.
    if first in _BLOCKED_KEYWORDS:
        raise ValueError(f"Write operations blocked: {first}")
    # Auto-detect: full SELECT/WITH/PRAGMA statement vs. WHERE-fragment used by
    # the count / distribution / ranked_pairs callers.
    kind = "sql" if first in {"SELECT", "WITH", "PRAGMA"} else "where"
    _sa.validate_read_only(sql, kind=kind)


# ── schema introspection ─────────────────────────────────────────────

_DB_PREFIXES = {
    "cards":       get_cards_db,
    "equilibrium": get_equilibrium_db,
    "literature":  get_literature_db,
}


def get_table_schema(table_name: str, database: str = "cards") -> list[dict]:
    """
    Return column information for *table_name*.

    Parameters
    ----------
    table_name : e.g. ``metal_card``, ``eq_node``, ``literature_alt``
    database   : ``"cards"`` | ``"equilibrium"`` | ``"literature"``

    Returns list of dicts: cid, name, type, notnull, pk
    """
    db_factory = _DB_PREFIXES.get(database)
    if db_factory is None:
        return [{"error": f"Unknown database '{database}'. "
                          f"Choose from: {', '.join(_DB_PREFIXES)}"}]
    with db_factory() as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not rows:
            tables = [
                r[0] for r in
                conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            return [{"error": f"Table '{table_name}' not found.",
                     "available_tables": tables}]
        return [{"cid": r[0], "name": r[1], "type": r[2],
                 "notnull": bool(r[3]), "pk": bool(r[5])} for r in rows]


# ── raw SQL execution ────────────────────────────────────────────────

# Head/tail row-window for execute_srd46_sql results.  When a query
# returns more than ``_HEAD_ROWS + _TAIL_ROWS`` rows we keep the first
# ``_HEAD_ROWS`` and the last ``_TAIL_ROWS`` and inject a single
# placeholder row in the middle that loudly announces how many rows
# were elided.  This is a UI/context shaping step, NOT a substitute for
# the agent using SQL ``LIMIT`` / ``ORDER BY`` to scope the query.
_HEAD_ROWS = 40
_TAIL_ROWS = 10
_ELIDED_ROW_MARKER = "<<<<< ROWS ELIDED >>>>>"

_TASK_DESCRIPTION_MIN_CHARS = 40
_COLUMN_LEGEND_MIN_CHARS_PER_ENTRY = 20


def execute_srd46_sql(
    sql_query: str,
    task_description: Optional[str] = None,
    column_legend: Optional[dict] = None,
    attach_equilibrium: bool = False,
    attach_literature: bool = False,
) -> dict:
    """
    ** Accepts full read-only SQL cross-database SRD-46 query commands. Advanced tool.**

    Most versatile, efficient, and powerful query path. Handle more complicated cross-db 
    composite queries than ``search_*`` tools (multi-table joins, self-joins, calcs, window functions, 
    custom aggregations, etc.).Best used once you are (1) already familiar with all the dbs, and (2) 
    acknowledging how those data values scientifically constrain each other in chemistry problems.

    Parameters
    ----------
    sql_query : str
        Read-only SQL (SELECT / WITH / PRAGMA only). DDL/DML rejected at
        any depth. Accept and autoresolve canonical entity prefixes before execution; 
        metal-name literals are also alias-expanded.
    task_description : str
        One short sentence stating the chemistry question this query
        answers. Keep it terse; Don't restate the SQL in prose.
    column_legend : dict[str, str]
        One entry per SELECT column (including aliases / computed
        expressions) explaining what the value is, where it came from,
        and (for computed cols) the formula. Rendered alongside the
        result so invented aliases can be traced back to their origin.
        Runtime enforces minimum lengths and full column coverage and
        returns a descriptive error if anything is missing.
    attach_equilibrium : bool
        If True, attach srd46_equilibrium_maps.db under prefix ``eqdb.``
    attach_literature : bool
        If True, attach srd46_literature.db under prefix ``litdb.``

    Returns
    -------
    dict with keys
        task_description : str
        column_legend    : dict[str, str]   (echoed; missing-column warnings appended as "_warnings")
        sql_query        : str  (post AST-rewrite -- what actually ran)
        row_count        : int
        columns          : list[str]
        rows             : list[dict]  (capped at 50)
    """
    # ---- task_description gate ----
    if not isinstance(task_description, str) or len(task_description.strip()) < _TASK_DESCRIPTION_MIN_CHARS:
        return {
            "error": (
                "execute_srd46_sql REQUIRES a `task_description` argument of "
                f"at least {_TASK_DESCRIPTION_MIN_CHARS} characters — ONE BRIEF "
                "SENTENCE stating the chemistry question this SQL answers. "
                "Be terse and to the point; do NOT restate the SQL in prose. "
                "GOOD: 'Fe(III)/Fe(II) ΔlogK selectivity per ligand at matched (T, I).' "
                "BAD : 'This query joins ligandmetal_stability_measured to itself on "
                "ligand_id and metal_id ...' (restates SQL). This text is preserved "
                "verbatim in the run history inside a <tool_context> block so the "
                "claim-grounding pipeline can audit the *intent* of the SQL."
            ),
            "task_description": task_description or "",
            "column_legend": column_legend or {},
            "sql_query": sql_query,
            "row_count": 0,
            "columns": [],
            "rows": [],
        }

    # ---- column_legend gate ----
    if not isinstance(column_legend, dict) or not column_legend:
        return {
            "error": (
                "execute_srd46_sql REQUIRES a `column_legend` argument: a dict "
                "mapping EVERY output column (including SELECT aliases like "
                "'logK_Fe3' and computed columns like 'delta_logK') to a "
                "chemistry-aware string. Each entry must cover ALL FOUR facets: "
                "(1) source table.column or, for computed cols, the explicit "
                "formula; (2) the filter/join that selects feeding rows "
                "(metal_id, ligand_id, constant_type, beta_definition_name, T/I "
                "window, pKa bracket); (3) physical/chemical meaning + units + "
                "the species / protonation / oxidation state involved (e.g. "
                "'logK for Fe^[3+] + L ⇌ [FeL] with L = fully deprotonated NTA'); "
                "(4) for computed cols: formula AND interpretation (sign "
                "convention, what 'positive' means, units). See the tool "
                "docstring for a worked Fe(III)/Fe(II) ΔlogK example."
            ),
            "task_description": task_description.strip(),
            "column_legend": column_legend or {},
            "sql_query": sql_query,
            "row_count": 0,
            "columns": [],
            "rows": [],
        }

    bad_legend_entries = [
        k for k, v in column_legend.items()
        if not isinstance(v, str) or len(v.strip()) < _COLUMN_LEGEND_MIN_CHARS_PER_ENTRY
    ]
    if bad_legend_entries:
        return {
            "error": (
                "execute_srd46_sql `column_legend` entries must each be a "
                f"non-empty string of at least {_COLUMN_LEGEND_MIN_CHARS_PER_ENTRY} "
                f"characters. Too-short / non-string entries: {bad_legend_entries}. "
                "Each entry must cover (1) source table.column or formula, "
                "(2) filter/join (metal_id, beta_definition_name, constant_type, "
                "T/I window, pKa bracket), (3) physical meaning + units + species "
                "or protonation state, and (4) for computed cols, formula AND "
                "interpretation (sign convention, what 'positive' means)."
            ),
            "task_description": task_description.strip(),
            "column_legend": column_legend,
            "sql_query": sql_query,
            "row_count": 0,
            "columns": [],
            "rows": [],
        }

    # ---- run query ----
    _validate_read_only(sql_query)
    normalized_sql = _sa.normalize_chem_literals(sql_query, kind="sql")
    normalized_sql = _sa.expand_metal_name_literals(normalized_sql, kind="sql")
    normalized_sql = resolve_prefixed_ids(normalized_sql)

    if attach_equilibrium or attach_literature:
        with attach_all_dbs() as conn:
            rows = _rows_to_dicts(conn.execute(normalized_sql))
    else:
        with get_cards_db() as conn:
            rows = _rows_to_dicts(conn.execute(normalized_sql))

    # Head/tail window: when too many rows come back, keep the first
    # ``_HEAD_ROWS`` and the last ``_TAIL_ROWS`` and slot a sentinel row
    # in between announcing how many were dropped.  Sentinel keys match
    # the result columns so the row stays valid in any downstream table
    # rendering.  The agent should use SQL ``LIMIT`` / ``ORDER BY`` /
    # aggregation to narrow the query rather than rely on this window.
    full_row_count = len(rows)
    elided_row_count = 0
    if full_row_count > _HEAD_ROWS + _TAIL_ROWS:
        elided_row_count = full_row_count - _HEAD_ROWS - _TAIL_ROWS
        head = rows[:_HEAD_ROWS]
        tail = rows[-_TAIL_ROWS:]
        col_keys = list(rows[0].keys())
        # Loud, count-bearing sentinel that survives any downstream
        # markdown / JSON renderer: the omitted-row count appears in
        # EVERY cell so it's visible regardless of which columns the
        # agent / compactor chooses to display.
        cell_marker = (
            f"{_ELIDED_ROW_MARKER} {elided_row_count} ROWS OMITTED "
            f"({full_row_count} total \u2014 kept first {_HEAD_ROWS} "
            f"+ last {_TAIL_ROWS}) {_ELIDED_ROW_MARKER}"
        )
        marker_row = {k: cell_marker for k in col_keys}
        rows = head + [marker_row] + tail
        log.info(
            "SQL returned %d rows \u2014 keeping first %d + last %d, "
            "%d rows elided in the middle",
            full_row_count, _HEAD_ROWS, _TAIL_ROWS, elided_row_count,
        )

    rows = prefix_ids_in_rows(rows)
    columns = list(rows[0].keys()) if rows else []

    # Soft-warn if legend doesn't cover every actual output column
    missing_in_legend = [c for c in columns if c not in column_legend]
    extra_in_legend = [k for k in column_legend if k not in columns] if columns else []
    warnings: list[str] = []
    if missing_in_legend:
        warnings.append(
            "column_legend is missing entries for these output columns: "
            f"{missing_in_legend}. Add them on the next call so claim-grounding "
            "can trace these values to their chemistry origin."
        )
    if extra_in_legend:
        warnings.append(
            "column_legend describes columns not present in the result: "
            f"{extra_in_legend}. Either the SELECT list changed, or the "
            "legend keys don't match the SELECT aliases."
        )

    out = {
        "task_description": task_description.strip(),
        "column_legend": column_legend,
        "sql_query": normalized_sql,
        "row_count": full_row_count,
        "columns": columns,
        "rows": rows,
    }
    if elided_row_count:
        out["rows_elided"] = elided_row_count
        out["rows_kept_head"] = _HEAD_ROWS
        out["rows_kept_tail"] = _TAIL_ROWS
        warnings.append(
            f"{elided_row_count} of {full_row_count} rows were elided in the "
            f"middle of the result (kept first {_HEAD_ROWS} + last {_TAIL_ROWS}). "
            "Use SQL LIMIT / ORDER BY / aggregation to scope the query if you "
            "need a different slice."
        )
    if warnings:
        out["_warnings"] = warnings
    return out


# ── counting ─────────────────────────────────────────────────────────

_ALLOWED_TABLES = {
    "metal_card", "ligand_card", "ligandmetal_card",
    "ligandmetal_stability_measured", "ligandmetal_stability_estimated",
    "ligand_pka_measured", "ligand_pka_bracket",
    "ref_literature_alt", "ref_vlm_literature_alt",
    "ref_author", "ref_vlm_author",
}


def db_count_records(
    table: str,
    where: Optional[str] = None,
) -> dict:
    """
    Count rows in a table, optionally filtered.

    Parameters
    ----------
    table : one of metal_card, ligand_card, ligandmetal_card, etc.
    where : SQL WHERE clause (without WHERE keyword).

    Returns {"table", "where", "count"}
    """
    if table not in _ALLOWED_TABLES:
        return {"error": f"Table '{table}' not allowed. Choose from: {sorted(_ALLOWED_TABLES)}"}

    sql = f"SELECT COUNT(*) AS cnt FROM {table}"
    if where:
        _validate_read_only(where)
        where = _sa.normalize_chem_literals(where)
        where = _sa.expand_metal_name_literals(where)
        where = resolve_prefixed_ids(where)
        sql += f" WHERE {where}"

    with get_cards_db() as conn:
        row = conn.execute(sql).fetchone()
    return {"table": table, "where": where or "(all)", "count": row["cnt"]}


# ── distribution ─────────────────────────────────────────────────────

def db_distribution(
    table: str,
    group_column: str,
    where: Optional[str] = None,
    limit: int = 25,
) -> dict:
    """
    Group-by distribution: counts per distinct value in a column.

    Returns {"table", "group_column", "total_rows", "groups": [{value, cnt, pct}]}
    """
    if table not in _ALLOWED_TABLES:
        return {"error": f"Table '{table}' not allowed."}

    if not all(c.isalnum() or c == '_' for c in group_column):
        return {"error": f"Invalid column name: '{group_column}'"}

    count_sql = f"SELECT COUNT(*) AS cnt FROM {table}"
    if where:
        _validate_read_only(where)
        where = _sa.normalize_chem_literals(where)
        where = _sa.expand_metal_name_literals(where)
        where = resolve_prefixed_ids(where)
        count_sql += f" WHERE {where}"

    group_sql = (
        f"SELECT {group_column} AS value, COUNT(*) AS cnt "
        f"FROM {table} "
    )
    if where:
        group_sql += f"WHERE {where} "
    group_sql += f"GROUP BY {group_column} ORDER BY cnt DESC LIMIT {int(limit)}"

    with get_cards_db() as conn:
        total = conn.execute(count_sql).fetchone()["cnt"]
        rows = _rows_to_dicts(conn.execute(group_sql))

    for r in rows:
        r["pct"] = round(100.0 * r["cnt"] / total, 2) if total else 0.0

    return {
        "table": table,
        "group_column": group_column,
        "total_rows": total,
        "groups": rows,
    }


# ── ranked pairs ─────────────────────────────────────────────────────

def db_ranked_pairs(
    rank_by: str = "ligands_per_metal",
    limit: int = 20,
    where: Optional[str] = None,
) -> dict:
    """
    Rank metals or ligands by partner count or measurement count.

    rank_by choices:
      - ``ligands_per_metal``
      - ``metals_per_ligand``
      - ``measurements_per_metal``
      - ``measurements_per_ligand``
      - ``pka_per_ligand``

    Returns {"rank_by", "results": [{metal_id|ligand_id, name, count}]}
    """
    _QUERIES = {
        "ligands_per_metal": (
            "SELECT lc.metal_id, mc.metal_name_SRD AS name, "
            "COUNT(DISTINCT lc.ligand_id) AS count "
            "FROM ligandmetal_card lc "
            "JOIN metal_card mc ON mc.metal_id = lc.metal_id "
            "{where} "
            "GROUP BY lc.metal_id ORDER BY count DESC LIMIT {limit}"
        ),
        "metals_per_ligand": (
            "SELECT lc.ligand_id, lc2.ligand_name_SRD AS name, "
            "COUNT(DISTINCT lc.metal_id) AS count "
            "FROM ligandmetal_card lc "
            "JOIN ligand_card lc2 ON lc2.ligand_id = lc.ligand_id "
            "{where} "
            "GROUP BY lc.ligand_id ORDER BY count DESC LIMIT {limit}"
        ),
        "measurements_per_metal": (
            "SELECT lc.metal_id, mc.metal_name_SRD AS name, "
            "COUNT(*) AS count "
            "FROM ligandmetal_stability_measured lsm "
            "JOIN ligandmetal_card lc ON lc.card_id = lsm.card_id "
            "JOIN metal_card mc ON mc.metal_id = lc.metal_id "
            "{where} "
            "GROUP BY lc.metal_id ORDER BY count DESC LIMIT {limit}"
        ),
        "measurements_per_ligand": (
            "SELECT lc.ligand_id, lc2.ligand_name_SRD AS name, "
            "COUNT(*) AS count "
            "FROM ligandmetal_stability_measured lsm "
            "JOIN ligandmetal_card lc ON lc.card_id = lsm.card_id "
            "JOIN ligand_card lc2 ON lc2.ligand_id = lc.ligand_id "
            "{where} "
            "GROUP BY lc.ligand_id ORDER BY count DESC LIMIT {limit}"
        ),
        "pka_per_ligand": (
            "SELECT p.ligand_id, lc.ligand_name_SRD AS name, "
            "COUNT(*) AS count "
            "FROM ligand_pka_measured p "
            "JOIN ligand_card lc ON lc.ligand_id = p.ligand_id "
            "{where} "
            "GROUP BY p.ligand_id ORDER BY count DESC LIMIT {limit}"
        ),
    }

    if rank_by not in _QUERIES:
        return {"error": f"Unknown rank_by='{rank_by}'. Choose from: {sorted(_QUERIES)}"}

    where_clause = ""
    if where:
        _validate_read_only(where)
        where = _sa.normalize_chem_literals(where)
        where = _sa.expand_metal_name_literals(where)
        where = resolve_prefixed_ids(where)
        where_clause = f"WHERE {where}"
    sql = _QUERIES[rank_by].format(where=where_clause, limit=int(limit))

    with get_cards_db() as conn:
        rows = _rows_to_dicts(conn.execute(sql))

    return {"rank_by": rank_by, "results": prefix_ids_in_rows(rows)}
