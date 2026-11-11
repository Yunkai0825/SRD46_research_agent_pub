"""Hardcoded compactor for ``execute_srd46_sql``.

Renders raw-SQL results so that the agent's chemistry intent and the
per-column legend are preserved verbatim alongside the row table. Wraps
the agent-supplied ``task_description`` and ``column_legend`` in a
``<tool_context>`` ... ``</tool_context>`` block so the claim-grounding
pipeline can distinguish *agent reasoning about its own SQL* from *actual
SRD-46 data rows*.
"""
from __future__ import annotations

from typing import Any

from ._compactor_helpers import _cell, speciation_context_hint
from ._sql_entity_enricher import enrich_entities


def _compacts(*tool_names: str):
    def _decorator(fn):
        fn._compacts_tools = tool_names
        return fn
    return _decorator


def _fence(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text.rstrip()}\n```"


@_compacts("execute_srd46_sql")
def compact_execute_srd46_sql(data: Any) -> str:
    if not isinstance(data, dict):
        return f"**execute_srd46_sql:** unexpected data type {type(data).__name__}\n"

    if "error" in data:
        # The validation gates (missing task_description / column_legend) and
        # any DB error land here. Surface them prominently so the agent
        # corrects its next call.
        return (
            "## execute_srd46_sql — REJECTED\n\n"
            f"**Error:** {data['error']}\n"
        )

    task = (data.get("task_description") or "").strip()
    legend = data.get("column_legend") or {}
    sql = (data.get("sql_query") or "").strip()
    rows = data.get("rows") or []
    columns = data.get("columns") or (list(rows[0].keys()) if rows else [])
    row_count = data.get("row_count", len(rows))
    warnings = data.get("_warnings") or []

    out: list[str] = []
    out.append(f"## execute_srd46_sql — {row_count} row(s)")
    out.append("")

    # ── <tool_context> block: agent intent + per-column legend ──
    out.append("<tool_context>")
    out.append("**Task (agent-stated intent):**")
    out.append("")
    out.append(f"> {task}" if task else "> *(missing)*")
    out.append("")

    if legend:
        out.append("**Column legend (agent-stated chemistry origin of each column):**")
        out.append("")
        out.append("| column | meaning / source table+filter / species or (T, I) |")
        out.append("|--------|----------------------------------------------------|")
        # Render in the order the columns actually appear in the result
        # (so the legend lines up visually with the table below); fall back
        # to the legend's own iteration order if the result is empty.
        ordered = columns if columns else list(legend.keys())
        for col in ordered:
            meaning = legend.get(col)
            if meaning is None:
                out.append(f"| `{_cell(col)}` | *(no legend entry \u2014 see warning)* |")
            else:
                out.append(f"| `{_cell(col)}` | {_cell(str(meaning), max_len=300)} |")
        # Any legend entries that don't correspond to actual columns
        for k, v in legend.items():
            if k not in (columns or []):
                out.append(f"| `{_cell(k)}` *(not in result)* | {_cell(str(v), max_len=300)} |")
        out.append("")

    if warnings:
        out.append("**Validation warnings:**")
        for w in warnings:
            out.append(f"- {w}")
        out.append("")

    # ── Auto-enriched entities (gap-only) ──
    enrichment = enrich_entities(rows, columns) if rows else {}
    if enrichment:
        out.append("**Auto-enriched entities (filling in fields missing from the SELECT):**")
        out.append("")
        _entity_labels = {
            "metal_id": "metal_id → metal_card",
            "ligand_id": "ligand_id → ligand_card (+ ligand_pka_bracket)",
            "beta_definition_id": "beta_definition_id → representative equation_str",
        }
        for ent_type, block in enrichment.items():
            fields = block["fields"]
            ent_rows = block["rows"]
            id_col = ent_type
            out.append(f"*{_entity_labels.get(ent_type, ent_type)}*")
            out.append("")
            header_cols = [id_col] + fields
            out.append("| " + " | ".join(header_cols) + " |")
            out.append("|" + "|".join("-" * (len(c) + 2) for c in header_cols) + "|")
            for r in ent_rows:
                out.append("| " + " | ".join(_cell(r.get(c)) for c in header_cols) + " |")
            out.append("")

    out.append("**SQL executed (post AST-rewrite):**")
    out.append("")
    out.append(_fence(sql, "sql"))
    out.append("</tool_context>")
    out.append("")

    # ── Result table ──
    if not rows:
        out.append("*(0 rows returned)*")
        out.append("")
        out.append(speciation_context_hint())
        return "\n".join(out)

    # Hoist columns whose value is identical across every row into a
    # "Shared across all N rows" preamble, and drop them from the table
    # body. This compacts wide self-joins / fixed-(T,I) shortlists where
    # most metadata columns are constant. Only triggers when there are
    # >=2 rows AND at least one varying column (so we never collapse the
    # entire table away).
    constant_cols: list[str] = []
    varying_cols: list[str] = list(columns)
    if len(rows) >= 2 and len(columns) >= 2:
        const_candidates = []
        var_candidates = []
        for c in columns:
            first = rows[0].get(c)
            if all(r.get(c) == first for r in rows[1:]):
                const_candidates.append(c)
            else:
                var_candidates.append(c)
        if const_candidates and var_candidates:
            constant_cols = const_candidates
            varying_cols = var_candidates

    if constant_cols:
        out.append(f"**Shared across all {len(rows)} rows:**")
        out.append("")
        for c in constant_cols:
            out.append(f"- `{c}` = {_cell(rows[0].get(c))}")
        out.append("")

    header = "| " + " | ".join(varying_cols) + " |"
    sep = "|" + "|".join("-" * (len(c) + 2) for c in varying_cols) + "|"
    out.append(header)
    out.append(sep)
    for r in rows:
        out.append("| " + " | ".join(_cell(r.get(c)) for c in varying_cols) + " |")
    out.append("")
    out.append(speciation_context_hint())
    return "\n".join(out)
