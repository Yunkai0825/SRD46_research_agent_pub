"""Markdown compactor for ``search_citations()`` results.

Renders a flat markdown table with columns:
``vlm_id``, ``lit_id``, ``shortcut``, ``citation`` (truncated to 80
chars).

Public API
----------
``compact_citation(rows)``
    Returns ``list[str]`` of markdown lines (no heading).
``compact_search_citations(data)``
    Returns a complete markdown string with ``## search_citations``
    heading and row count.
"""
from __future__ import annotations

from ._compactor_helpers import _cell, speciation_context_hint


def compact_citation(rows: list[dict]) -> list[str]:
    lines = [
        "| example_vlm_id | vlm_count | lit_id | shortcut | citation |",
        "|----------------|-----------|--------|----------|----------|",
    ]
    for r in rows:
        vlm = r.get("example_vlm_id", r.get("vlm_id", "?"))
        vlm_count = r.get("vlm_count", 1)
        lit = r.get("literature_alt_id", "?")
        sc = r.get("shortcut", "") or "***"
        cite = _cell(r.get("citation", ""), 80)
        lines.append(f"| {vlm} | {vlm_count} | {lit} | {sc} | {cite} |")
    return lines


def compact_search_citations(data: list[dict] | dict) -> str:
    """Compact markdown for ``search_citations()`` results."""
    # wrap_tool() wraps list results as {"results": [...], "n_results": N}
    if isinstance(data, dict):
        data = data.get("results", data)
    if not isinstance(data, list):
        return f"**search_citations:** unexpected data type {type(data).__name__}\n"
    if not data:
        return "## search_citations\n\n*(no results)*\n" + speciation_context_hint()
    n = len(data)
    lines = [f"## search_citations \u2014 {n} row(s)", ""]
    lines.extend(compact_citation(data))
    lines.append("")
    return "\n".join(lines) + "\n" + speciation_context_hint()
