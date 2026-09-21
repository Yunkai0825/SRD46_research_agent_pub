"""Gap-only entity enrichment for ``execute_srd46_sql`` results.

Resolves entity-ID columns (``metal_id`` / ``ligand_id`` /
``beta_definition_id``) into chemistry context (canonical name, charge,
HxL form, SMILES, pKa brackets, beta equation_str) but ONLY for fields
that the agent's SELECT did NOT already include. If every canonical
field for an entity type is already in the result columns, the
enrichment block for that type is omitted entirely.

**Why vlm_id is intentionally NOT enriched here:** ``vlm_id`` (=
``complex_system_id``) is the row-level identifier of the cards /
stability_measured table the agent is already SELECTing FROM — it is
not a foreign key to a separate canonical table. Every per-row field
(``equation_str``, ``constant_value``, ``temperature_c``,
``ionic_strength_mol_l``, the literal published equation, etc.) lives
on the same row the agent already has access to, so the right fix for
a vlm-bearing SELECT that omits these columns is to add them to the
SELECT (or call ``inspect_card('vlm_<id>')``), not to auto-JOIN. By
contrast ``metal_id`` / ``ligand_id`` / ``beta_definition_id`` are
FK columns that point OUT to canonical entity tables (metal_card,
ligand_card + ligand_pka_bracket, distinct beta_definition rows), so a
bounded enrichment per unique ID adds chemistry context the SELECT
cannot otherwise carry.

This is best-effort: any DB exception → returns ``{}`` (the SQL result
itself is never blocked by an enrichment failure).
"""
from __future__ import annotations

import logging
from typing import Any

from .._db_connection import get_cards_db

log = logging.getLogger("SRD46")

_MAX_UNIQUE_PER_TYPE = 25
_PREFIX = {"metal_id": "metal_", "ligand_id": "ligand_", "beta_definition_id": "beta_def_"}


def _strip_prefix(value: Any, prefix: str) -> int | None:
    """``"metal_61"`` → ``61``; tolerate raw ints; return None on failure."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s.startswith(prefix):
        s = s[len(prefix):]
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _collect_unique_ids(rows: list[dict], col: str, prefix: str) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for r in rows:
        if col not in r:
            continue
        rid = _strip_prefix(r.get(col), prefix)
        if rid is None or rid in seen:
            continue
        seen.add(rid)
        ordered.append(rid)
        if len(ordered) >= _MAX_UNIQUE_PER_TYPE:
            break
    return ordered


def _enrich_metal(conn, ids: list[int], present_cols: set[str]) -> dict | None:
    """Return ``{"fields": [...], "rows": [...]}`` or None to skip block."""
    # Per-field skip: if all canonical fields are already in SELECT, skip.
    candidate_fields = ["metal_name_SRD", "symbol_pure", "charge"]
    fields = [f for f in candidate_fields if f not in present_cols]
    if not fields:
        return None
    placeholders = ",".join("?" * len(ids))
    select_cols = ", ".join(["metal_id"] + fields)
    sql = (
        f"SELECT {select_cols} FROM metal_card "
        f"WHERE metal_id IN ({placeholders}) ORDER BY metal_id"
    )
    raw = conn.execute(sql, ids).fetchall()
    return {
        "fields": fields,
        "rows": [{"metal_id": f"metal_{r['metal_id']}",
                  **{f: r[f] for f in fields}} for r in raw],
    }


def _format_brackets(brackets: list[dict]) -> str:
    """Same condensed format used by entity_search compactor."""
    if not brackets:
        return "***"
    parts: list[str] = []
    for i, b in enumerate(brackets):
        label = (b.get("bracket_label") or "").strip().strip("()")
        lo_hi = [x.strip() for x in label.split(",", 1)] if label else ["?", "?"]
        lo = lo_hi[0] if len(lo_hi) > 0 else "?"
        hi = lo_hi[1] if len(lo_hi) > 1 else "?"
        if i == 0:
            parts.append(lo)
        parts.append(b.get("HxL_form", "?"))
        parts.append(hi)
    return "(" + ", ".join(parts) + ")"


def _enrich_ligand(conn, ids: list[int], present_cols: set[str]) -> dict | None:
    candidate_fields = ["ligand_name_SRD", "definition_HxL", "ligand_SMILES"]
    fields = [f for f in candidate_fields if f not in present_cols]
    # pka_brackets has no flat-SELECT equivalent in the agent's query → always render.
    render_pka = True

    if not fields and not render_pka:
        return None

    placeholders = ",".join("?" * len(ids))
    cols_to_select = ["ligand_id"] + fields
    select_cols = ", ".join(cols_to_select)
    sql = (
        f"SELECT {select_cols} FROM ligand_card "
        f"WHERE ligand_id IN ({placeholders}) ORDER BY ligand_id"
    )
    raw = conn.execute(sql, ids).fetchall()
    base = {r["ligand_id"]: {f: r[f] for f in fields} for r in raw}

    brackets_by_lid: dict[int, list[dict]] = {}
    if render_pka:
        br_sql = (
            f"SELECT ligand_id, HxL_form, bracket_label, is_estimated "
            f"FROM   ligand_pka_bracket "
            f"WHERE  ligand_id IN ({placeholders}) AND is_estimated = 0 "
            f"ORDER BY ligand_id, bracket_id"
        )
        for br in conn.execute(br_sql, ids).fetchall():
            brackets_by_lid.setdefault(br["ligand_id"], []).append(dict(br))

    rendered_rows = []
    for lid in ids:
        row = {"ligand_id": f"ligand_{lid}"}
        for f in fields:
            row[f] = base.get(lid, {}).get(f)
        if render_pka:
            row["pka_brackets"] = _format_brackets(brackets_by_lid.get(lid, []))
        rendered_rows.append(row)

    out_fields = list(fields)
    if render_pka:
        out_fields.append("pka_brackets")

    return {"fields": out_fields, "rows": rendered_rows}


def _enrich_beta(conn, ids: list[int], present_cols: set[str]) -> dict | None:
    if "equation_str" in present_cols:
        return None
    placeholders = ",".join("?" * len(ids))
    # Representative equation_str per beta_definition_id (mirrors
    # system_catalog.py L146-158).
    sql = (
        f"SELECT c.beta_definition_id, MIN(s.equation_str) AS equation_str "
        f"FROM   ligandmetal_card c "
        f"JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id "
        f"WHERE  c.beta_definition_id IN ({placeholders}) "
        f"  AND  s.equation_str IS NOT NULL "
        f"GROUP BY c.beta_definition_id "
        f"ORDER BY c.beta_definition_id"
    )
    raw = conn.execute(sql, ids).fetchall()
    eq_by_id = {r["beta_definition_id"]: r["equation_str"] for r in raw}
    return {
        "fields": ["equation_str"],
        "rows": [{"beta_definition_id": f"beta_def_{bid}",
                  "equation_str": eq_by_id.get(bid, "***")} for bid in ids],
    }


def enrich_entities(rows: list[dict], columns: list[str]) -> dict[str, dict]:
    """Resolve entity-ID columns to missing-only chemistry context.

    Parameters
    ----------
    rows : list[dict]
        The result rows from ``execute_srd46_sql`` (post id-prefixing).
    columns : list[str]
        The SELECT-list column names actually present in the result.

    Returns
    -------
    dict
        ``{entity_type: {"fields": [...], "rows": [...]}, ...}`` for each
        entity type whose ID column appears in ``columns`` AND has at
        least one missing canonical field. Empty dict on no matches or
        on any DB failure.
    """
    if not rows or not columns:
        return {}
    present_cols = set(columns)
    out: dict[str, dict] = {}

    try:
        with get_cards_db() as conn:
            if "metal_id" in present_cols:
                ids = _collect_unique_ids(rows, "metal_id", _PREFIX["metal_id"])
                if ids:
                    block = _enrich_metal(conn, ids, present_cols)
                    if block:
                        out["metal_id"] = block

            if "ligand_id" in present_cols:
                ids = _collect_unique_ids(rows, "ligand_id", _PREFIX["ligand_id"])
                if ids:
                    block = _enrich_ligand(conn, ids, present_cols)
                    if block:
                        out["ligand_id"] = block

            if "beta_definition_id" in present_cols:
                ids = _collect_unique_ids(rows, "beta_definition_id",
                                          _PREFIX["beta_definition_id"])
                if ids:
                    block = _enrich_beta(conn, ids, present_cols)
                    if block:
                        out["beta_definition_id"] = block
    except Exception as exc:  # best-effort
        log.warning("execute_srd46_sql entity enrichment failed: %s", exc)
        return {}

    return out
