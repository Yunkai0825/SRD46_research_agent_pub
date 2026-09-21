"""Markdown compactors for aggregate / statistical query tools.

Covers three SQL-aggregate tools that return summary statistics rather
than individual rows:

``compact_db_count_records(data)``
    Renders record-count results (e.g. total metals, ligands, VLMs).
``compact_db_distribution(data)``
    Renders frequency-distribution tables (e.g. measurements per metal).
``compact_db_ranked_pairs(data)``
    Renders ranked metal-ligand pair tables.
``compact_get_table_schema(data)``
    Renders raw SQLite table schema information.
"""
from __future__ import annotations

from typing import Any

from ._compactor_helpers import speciation_context_hint


def _compacts(*tool_names: str):
    def _decorator(fn):
        fn._compacts_tools = tool_names
        return fn
    return _decorator


def _cell(val: Any, max_len: int = 80) -> str:
    if val is None or str(val).strip() == "":
        return "***"
    s = str(val)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


@_compacts("db_count_records")
def compact_db_count_records(data: dict) -> str:
    if not isinstance(data, dict):
        return f"**db_count_records:** unexpected data type {type(data).__name__}\n"
    if "error" in data:
        return f"**db_count_records:** Error - {data['error']}\n"

    lines = [
        "## db_count_records",
        "",
        "| table | where | count |",
        "|-------|-------|-------|",
        f"| {_cell(data.get('table'))} | {_cell(data.get('where'))} | {_cell(data.get('count'))} |",
        "",
    ]
    return "\n".join(lines) + speciation_context_hint()


@_compacts("db_distribution")
def compact_db_distribution(data: dict) -> str:
    if not isinstance(data, dict):
        return f"**db_distribution:** unexpected data type {type(data).__name__}\n"
    if "error" in data:
        return f"**db_distribution:** Error - {data['error']}\n"

    groups = data.get("groups", []) or []
    lines = [
        f"## db_distribution - {_cell(data.get('table'))} by {_cell(data.get('group_column'))}",
        "",
        f"**total_rows:** {_cell(data.get('total_rows'))}",
        "",
        "| value | count | pct |",
        "|-------|-------|-----|",
    ]
    for row in groups:
        lines.append(
            f"| {_cell(row.get('value'))} | {_cell(row.get('cnt'))} | {_cell(row.get('pct'))}% |"
        )
    lines.append("")
    return "\n".join(lines) + speciation_context_hint()


@_compacts("db_ranked_pairs")
def compact_db_ranked_pairs(data: dict) -> str:
    if not isinstance(data, dict):
        return f"**db_ranked_pairs:** unexpected data type {type(data).__name__}\n"
    if "error" in data:
        return f"**db_ranked_pairs:** Error - {data['error']}\n"

    rows = data.get("results", []) or []
    id_col = "id"
    if rows:
        for key in rows[0].keys():
            if key.endswith("_id"):
                id_col = key
                break

    lines = [
        f"## db_ranked_pairs - {_cell(data.get('rank_by'))}",
        "",
        f"| {id_col} | name | count |",
        f"|{'-' * (len(id_col) + 2)}|------|-------|",
    ]
    for row in rows:
        lines.append(
            f"| {_cell(row.get(id_col))} | {_cell(row.get('name'), 60)} | {_cell(row.get('count'))} |"
        )
    lines.append("")
    return "\n".join(lines) + speciation_context_hint()


@_compacts("get_table_schema")
def compact_get_table_schema(data: list[dict] | dict) -> str:
    rows = data if isinstance(data, list) else data.get("results", data)

    if rows and isinstance(rows, list) and isinstance(rows[0], dict) and "error" in rows[0]:
        err = rows[0]
        tables = err.get("available_tables", [])
        suffix = f"\nAvailable tables: {', '.join(tables)}" if tables else ""
        return f"**get_table_schema:** Error - {err['error']}{suffix}\n"

    if not rows:
        return "## get_table_schema\n\n*(0 columns)*\n"

    lines = [
        f"## get_table_schema - {len(rows)} column(s)",
        "",
        "| cid | name | type | notnull | pk |",
        "|-----|------|------|---------|----|",
    ]
    for row in rows:
        lines.append(
            f"| {_cell(row.get('cid'))} | {_cell(row.get('name'))} | {_cell(row.get('type'))} | {_cell(row.get('notnull'))} | {_cell(row.get('pk'))} |"
        )
    lines.append("")
    return "\n".join(lines)