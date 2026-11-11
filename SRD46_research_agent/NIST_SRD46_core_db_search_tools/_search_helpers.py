"""
Shared helpers for SQL-WHERE search modules.

Provides WHERE-clause validation, ligand-similarity expansion,
templated query execution, and common constants.
"""

import logging
import re
from typing import Optional

from ._db_connection import get_cards_db, get_equilibrium_db, CARDS_DB
from ._normalization_helpers.id_prefixer import prefix_ids_in_rows, unprefix_id
from . import _sql_ast as _sa
from ._sql_ast import parse_sql_where_query  # re-export for search tools

log = logging.getLogger("SRD46")


# ── Agent-facing docstring snippet ───────────────────────────────────
#
# Reusable "what the WHERE clause auto-rewrites for you" block. Imported
# by the public search tools (search_stability / pka / networks) and the
# generic SQL/aggregate tools (execute_srd46_sql, db_count_records,
# db_distribution, db_ranked_pairs) so the agent sees the same
# explanation everywhere.
WHERE_NORMALIZATION_NOTES = """\
SQL-WHERE syntax & auto-normalization (the ``sql_where_query`` parameter)
-------------------------------------------------------------------------
* One string: optional leading ``WHERE``, **full** WHERE-fragment grammar. 
  Sub-SELECTs allowed (read-only validated; DDL/DML rejected at any depth).
* Prefer batched predicates (``ligand_id IN (a, b, c)``) over many
  single-ligand calls.
* Auto-normalizations that affect results:
        - Constant-type aliases fold to stored codes (``'log K'`` / ``'logK'`` → ``'K'``;
            ``'ΔH'`` / ``'delta H'`` → ``'H'``; ``'ΔS'`` / ``'delta S'`` → ``'S'``).
    - Metal-name equality widens to all aliases (``= 'copper(II)'`` →
      IN over ``copper(II)``, ``copper``, ``Cu2+``, ``Cu^[2+]``, ``Cu``).
    - Prefixed IDs accepted directly (``metal_41``, ``ligand_5760``).

Things to KNOW (silent footguns — NOT auto-handled)
----------------------------------------------------
* Ligand names are NOT PubChem-resolved in WHERE — use ``search_ligands(name=…)``
  first to get a ``ligand_id``. EXCEPTION: ``search_stability`` / ``search_pka_*`` /
  ``search_networks`` trigger a 0-row similarity fallback that DOES call PubChem.
* Similarity fallback is fuzzy: rows tagged with ``similarity_score``; a 0-row
  caused by a tight numeric/metal filter will NOT be a real answer — recheck.
* Branch-blind extraction: similarity uses the FIRST ``ligand_id=N`` /
  ``ligand_name='X'`` anywhere in the WHERE (incl. sub-SELECTs/OR branches);
  ``<>`` / ``NOT IN`` are NOT widened by similarity.
* SMILES canonicalization keeps stereo / salts / tautomers distinct.
* Result blow-up: similarity expands one ligand to top-K (default 10);
  combined with loose joins row count can ~10×. Sort by ``similarity_score``.
"""


# ── helpers ──────────────────────────────────────────────────────────

def rows_to_dicts(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


_BLOCKED_KEYWORDS = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
                     "CREATE", "REPLACE", "TRUNCATE"}


def _looks_like_full_sql(text: str) -> bool:
    head = text.lstrip().split(None, 1)[:1]
    return bool(head) and head[0].upper() in {"SELECT", "WITH", "PRAGMA"}


def resolve_prefixed_ids(clause: str) -> str:
    """Replace canonical prefixed IDs with raw integers in a SQL clause.

    ``"c.metal_id = metal_41"``  →  ``"c.metal_id = 41"``
    ``"c.beta_definition_id = beta_def_812"``  →  ``"c.beta_definition_id = 812"``

    Backed by an AST walk (sqlglot) so substrings inside string literals
    are never touched.
    """
    if not clause:
        return clause
    kind = "sql" if _looks_like_full_sql(clause) else "where"
    resolved = _sa.resolve_prefixed_ids(clause, kind=kind)
    if resolved != clause:
        log.debug("   -> resolved prefixed IDs: %s → %s", clause[:120], resolved[:120])
    return resolved


def validate_clause(clause: str, *, kind: str = "where") -> None:
    """Reject write keywords in WHERE / ORDER BY clauses.

    Read-only sub-SELECTs (``EXISTS (SELECT …)``, ``IN (SELECT …)``) are
    explicitly allowed; only DDL / DML node types are rejected.

    Parameters
    ----------
    kind : {"where", "order_by", "sql"}
        Tells the AST validator how to wrap the fragment before parsing.
        Order-by fragments like ``"s.constant_value DESC"`` MUST pass
        ``kind="order_by"`` — otherwise ``DESC`` is parsed as part of a
        WHERE expression and sqlglot raises a confusing parse error.
    """
    if not clause or not clause.strip():
        return
    # Tolerate a leading ``WHERE`` keyword the agent may emit when
    # treating the param like a real SQL WHERE prelude.
    stripped = re.sub(r"^\s*WHERE\s+", "", clause, count=1, flags=re.IGNORECASE)
    head = stripped.lstrip().split(None, 1)[:1]
    first = head[0].upper() if head else ""
    if first in _BLOCKED_KEYWORDS:
        raise ValueError(f"Write operations blocked: {first}")
    # If the caller didn't override `kind` and the fragment looks like a
    # full SELECT / WITH / PRAGMA, upgrade to kind="sql".
    if kind == "where" and first in {"SELECT", "WITH", "PRAGMA"}:
        kind = "sql"
    _sa.validate_read_only(stripped, kind=kind)


HARD_LIMIT = 200


# ── ligand-similarity helpers ────────────────────────────────────────

_LIGAND_ID_PREFIX = {
    "stability": "c",
    "network":   "c",
    "pka":       "lc",
}


def extract_ligand_from_where(where: str) -> dict:
    """Extract ligand_id or ligand_name from a WHERE clause."""
    return _sa.extract_ligand_from_where(where)


def expand_where_with_similar(where: str, entity_type: str, top_k: int = 10) -> str:
    """Widen a ``ligand_id = X`` filter to include structurally similar ligands.

    Returns the original *where* unchanged when no ligand criterion is found
    or no similar ligands exist.
    """
    from .similarity_search import search_similar_ligands

    info = extract_ligand_from_where(where)
    if not info:
        return where

    try:
        result = search_similar_ligands(
            ligand_id=info.get("ligand_id"),
            ligand_name=info.get("ligand_name"),
            top_k=top_k,
        )
    except Exception:
        return where

    similar_ids = [unprefix_id(s["ligand_id"]) for s in result.get("similar_ligands", [])]
    if not similar_ids:
        return where

    original_id = info.get("ligand_id")
    if original_id is None:
        ql_id = result.get("query_ligand", {}).get("ligand_id")
        if ql_id is not None:
            original_id = unprefix_id(ql_id)
    all_ids = ([original_id] if original_id else []) + similar_ids

    expanded, replaced = _sa.expand_ligand_id_with_similar(where, all_ids)
    if replaced:
        return expanded

    # WHERE used a name LIKE rather than ligand_id — append an OR clause
    id_csv = ",".join(str(i) for i in all_ids)
    prefix = _LIGAND_ID_PREFIX.get(entity_type, "c")
    return f"({where}) OR {prefix}.ligand_id IN ({id_csv})"


def get_similarity_score_map(where: str, top_k: int = 10) -> dict[int, float]:
    """Return ``ligand_id -> similarity_score`` for a ligand-centered query.

    The original query ligand is assigned a score of ``1.0`` so expanded
    result tables can show a consistent score column alongside similar hits.
    """
    from .similarity_search import search_similar_ligands

    info = extract_ligand_from_where(where)
    if not info:
        return {}

    try:
        result = search_similar_ligands(
            ligand_id=info.get("ligand_id"),
            ligand_name=info.get("ligand_name"),
            top_k=top_k,
        )
    except Exception:
        return {}

    score_map: dict[int, float] = {}
    original_id = info.get("ligand_id")
    if original_id is None:
        ql_id = result.get("query_ligand", {}).get("ligand_id")
        if ql_id is not None:
            original_id = unprefix_id(ql_id)
    if original_id is not None:
        score_map[int(original_id)] = 1.0

    for sim in result.get("similar_ligands", []):
        sid = unprefix_id(sim.get("ligand_id"))
        score = sim.get("similarity_score")
        if sid is not None and score is not None:
            score_map[int(sid)] = float(score)
    return score_map


def execute_template(
    template: str,
    where: str,
    order_by: str = "",
    limit: str = "",
    needs_eq_db: bool = False,
) -> list[dict]:
    """Build and execute a templated query.

    ``order_by`` and ``limit`` are bare strings (no leading keyword); pass
    ``""`` to omit either clause entirely.
    """
    where = _sa.normalize_chem_literals(where)
    where = _sa.expand_metal_name_literals(where)
    where = resolve_prefixed_ids(where)
    sql = f"{template} WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {limit}"
    if needs_eq_db:
        with get_equilibrium_db() as conn:
            conn.execute("ATTACH DATABASE ? AS cardsdb", (str(CARDS_DB),))
            return rows_to_dicts(conn.execute(sql))
    else:
        with get_cards_db() as conn:
            return rows_to_dicts(conn.execute(sql))
