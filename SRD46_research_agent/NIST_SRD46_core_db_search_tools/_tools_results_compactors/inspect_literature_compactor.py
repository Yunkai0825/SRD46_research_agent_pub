"""Markdown compactor for ``inspect_literature()`` results.

Renders a markdown table of citations for a single VLM measurement.

Public API
----------
``compact_inspect_literature(data)``
    Returns a complete markdown string with heading and citation table.
"""
from __future__ import annotations

from ._compactor_helpers import _cell


def compact_inspect_literature(data: dict) -> str:
    """Compact markdown for ``inspect_literature()`` results."""
    if not isinstance(data, dict):
        return f"**inspect_literature:** unexpected data type {type(data).__name__}\n"
    if "error" in data:
        return f"**inspect_literature — error:** {data['error']}\n"

    prefix_id = data.get("prefix_id", "?")
    citations = data.get("citations", [])
    total = data.get("total_citations", len(citations))

    if not citations:
        return f"## inspect_literature — {prefix_id}\n\n*(no citations)*\n"

    lines = [f"## inspect_literature — {prefix_id} — {total} citation(s)", ""]
    lines.append("| lit_id | shortcut | citation |")
    lines.append("|--------|----------|----------|")
    for c in citations:
        lit = c.get("literature_alt_id", "?")
        sc = c.get("shortcut", "") or "***"
        cite = _cell(c.get("citation", ""), 80)
        lines.append(f"| {lit} | {sc} | {cite} |")
    lines.append("")
    return "\n".join(lines) + "\n"
