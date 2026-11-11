"""Markdown compactor for ``0_preplan_decision`` results.

Preserves the actual metals, ligands, l0_needed lists and notes
so the agent knows exactly what to search and which L0 tools to call.
"""
from __future__ import annotations


def compact_preplan_decision(data: dict) -> str:
    if not isinstance(data, dict):
        return f"## 0_preplan_decision\n\n*(unexpected data type)*\n"

    task_type = data.get("task_type", "unknown")
    metals = data.get("metals", [])
    ligands = data.get("ligands", [])
    l0_needed = data.get("l0_needed", [])
    notes = data.get("notes", "")

    metals_str = ", ".join(str(m) for m in metals) if metals else "(none)"
    ligands_str = ", ".join(str(l) for l in ligands) if ligands else "(none)"
    l0_str = ", ".join(str(t) for t in l0_needed) if l0_needed else "(none — skip to planner)"

    lines = [
        "## Pre-Plan Decision",
        "",
        f"- **Task type:** {task_type}",
        f"- **Metals to search:** {metals_str}",
        f"- **Ligands to search:** {ligands_str}",
        f"- **L0 tools needed:** {l0_str}",
    ]
    if notes:
        lines.append(f"- **Notes:** {notes}")
    lines.append("")
    return "\n".join(lines) + "\n"
