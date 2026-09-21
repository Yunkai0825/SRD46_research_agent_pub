"""Markdown compactor for ``search_pka_ligands()`` results.

Ligand-centric view: one flat summary table with one row per ligand.

Columns
-------
``ligand_id``, ``ligand_name``, ``HxL_def``, ``formula``, ``smiles``,
``pH_ladder``, ``T°C_range``, ``I(M)_range``, ``similarity_score``.

The **pH ladder** encodes the full protonation sequence for the ligand:
``−∞; H₃L (M_tot_0); (pKa₁, VLM); H₂L⁻ (M_tot_5); … ; +∞``.
Each segment shows the dominant protonation form and how many metals
bind that form (``M_tot_N``).  pKa values are labelled with their
source VLM identifier.

Public API
----------
``compact_pka_ligands(rows)``
    Returns ``list[str]`` of markdown lines (no heading).
``compact_search_pka_ligands(data)``
    Returns a complete markdown string with ``## search_pka_ligands``
    heading and row count.
"""
from __future__ import annotations

from collections import OrderedDict

from ._compactor_helpers import _cell, _num, speciation_context_hint


def _format_ladder_state(state: str, count: object) -> str:
    state = state or "***"
    return f"{state} (M_tot_{count})"


def _table_cell(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _group_rows(rows: list[dict]) -> OrderedDict[tuple, list[dict]]:
    groups: OrderedDict[tuple, list[dict]] = OrderedDict()
    for row in rows:
        ligand_id = row.get("ligand_id", "?")
        ligand_name = row.get("ligand_name", "") or str(ligand_id)
        hxl_def = row.get("ligand_HxL_definition", "") or "***"
        formula = row.get("formula", "") or "***"
        smiles = row.get("smiles", "") or "***"
        groups.setdefault((ligand_id, ligand_name, hxl_def, formula, smiles), []).append(row)
    return groups


def _build_ladder(sorted_rows: list[dict]) -> str:
    has_per_form = sorted_rows[0].get("M_above") is not None
    if not has_per_form:
        return "***"

    ladder_parts = ["−∞"]
    first_to = sorted_rows[0].get("bracket_to", "") or "***"
    ladder_parts.append(_format_ladder_state(first_to, sorted_rows[0].get("M_below", 0)))

    for row in sorted_rows:
        pka_label = f"({_num(row.get('pKa'))}, {row.get('source_vlm_id', '')})"
        ladder_parts.append(pka_label)
        ladder_parts.append(
            _format_ladder_state(
                row.get("bracket_from", "") or "***",
                row.get("M_above", 0),
            )
        )

    ladder_parts.append("+∞")
    return "; ".join(str(part) for part in ladder_parts)


def _similarity_summary(sorted_rows: list[dict]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for row in sorted_rows:
        value = row.get("ligand_similarity_score")
        if value is None:
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        values.append(text)
    if not values:
        return "***"
    return "; ".join(values)


def _range_summary(rows: list[dict], field: str) -> str:
    values: list[float] = []
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not values:
        return "***"
    lo, hi = min(values), max(values)
    if lo == hi:
        return _num(lo)
    return f"{_num(lo)}~{_num(hi)}"


def compact_pka_ligands(rows: list[dict]) -> list[str]:
    """Render pKa ligands as the default flat summary table."""
    groups = _group_rows(rows)
    lines = [
        "| ligand_id | ligand_name | HxL_def | formula | smiles | pH_ladder | T°C_range | I(M)_range | similarity_score |",
        "|-----------|-------------|---------|---------|--------|-----------|-----------|------------|------------------|",
    ]

    for (ligand_id, ligand_name, hxl_def, formula, smiles), group_rows in groups.items():
        sorted_rows = sorted(group_rows, key=lambda row: float(row.get("pKa") or 0))
        ladder = _build_ladder(sorted_rows)
        temperature_range = _range_summary(sorted_rows, "temperature")
        ionic_range = _range_summary(sorted_rows, "ionic_strength")
        similarity = _similarity_summary(sorted_rows)
        lines.append(
            f"| {_table_cell(ligand_id)} | {_table_cell(_cell(ligand_name, 60))} | {_table_cell(hxl_def)} | {_table_cell(formula)} | {_table_cell(smiles)} | {_table_cell(ladder)} | {_table_cell(temperature_range)} | {_table_cell(ionic_range)} | {_table_cell(similarity)} |"
        )

    lines.append("")
    return lines


def compact_search_pka_ligands(data: list[dict] | dict) -> str:
    """Compact markdown for ``search_pka_ligands()`` results."""
    # wrap_tool() wraps list results as {"results": [...], "n_results": N}
    if isinstance(data, dict):
        data = data.get("results", data)
    if not isinstance(data, list):
        return f"**search_pka_ligands:** unexpected type {type(data).__name__}\n"
    if not data:
        return "## search_pka_ligands\n\n*(no results)*\n" + speciation_context_hint()
    n = len(data)
    lines = [f"## search_pka_ligands \u2014 {n} row(s)", ""]
    lines.extend(compact_pka_ligands(data))
    lines.append("")
    return "\n".join(lines) + "\n" + speciation_context_hint()
