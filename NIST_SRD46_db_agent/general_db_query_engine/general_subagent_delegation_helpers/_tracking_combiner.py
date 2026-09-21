"""
Subagent tracking-MD combiner
==============================
Parses markdown tables from subagent ``reference_stats.md``,
``run_history.md`` and ``reasoning_tokens_stripped.md``, adds a
**Source** column to every data row, and writes/updates a combined
file in the parent agent's session directory.

Used by any agent that delegates to subagents and wants unified
tracking output.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

STATS_FILE = "reference_stats.md"
HISTORY_FILE = "run_history.md"
REASONING_FILE = "reasoning_tokens_stripped.md"
COMBINED_PREFIX = "subagents_combined_"


# ═══════════════════════════════════════════════════════════════
#  Generic markdown table parser / combiner
# ═══════════════════════════════════════════════════════════════

_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:]*-")


def _parse_number(cell: str) -> Optional[float]:
    """Extract a numeric value from a markdown table cell.

    Handles bold (``**1,234**``), commas, tilde prefix, trailing 's'
    and '%' suffixes.
    """
    s = cell.strip().strip("*").strip("~").replace(",", "").rstrip("%").rstrip("s").strip()
    if not s or s in ("—", "-", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _split_row(line: str) -> List[str]:
    """Split a ``| a | b | c |`` line into ['a','b','c']."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [c.strip() for c in stripped.split("|")]


def _is_total_row(cells: List[str]) -> bool:
    return any("TOTAL" in c.upper() for c in cells[:3])


def _extract_tables(content: str) -> List[dict]:
    """Return all markdown tables with their section context.

    Each dict:
      section  – the ``##`` / ``###`` heading above the table
      header   – list of column names
      rows     – list of data-row cell lists
      totals   – list of TOTAL-row cell lists
    """
    lines = content.splitlines()
    tables: List[dict] = []
    current_section = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            current_section = stripped
        # Table start: row with pipes, next line is separator
        if (
            "|" in stripped
            and stripped.startswith("|")
            and i + 1 < len(lines)
            and _TABLE_SEP_RE.match(lines[i + 1])
        ):
            header = _split_row(stripped)
            data_rows: List[List[str]] = []
            total_rows: List[List[str]] = []
            j = i + 2
            while j < len(lines):
                rline = lines[j].strip()
                if not rline.startswith("|"):
                    break
                cells = _split_row(rline)
                if _is_total_row(cells):
                    total_rows.append(cells)
                else:
                    data_rows.append(cells)
                j += 1
            tables.append(
                {
                    "section": current_section,
                    "header": header,
                    "rows": data_rows,
                    "totals": total_rows,
                }
            )
            i = j
            continue
        i += 1
    return tables


def _recompute_total(header: List[str], rows: List[List[str]]) -> List[str]:
    """Build a TOTAL row by summing numeric columns."""
    n = len(header)
    total = [""] * n
    total[0] = "**TOTAL**"
    for ci in range(1, n):
        vals: List[float] = []
        for row in rows:
            if ci < len(row):
                v = _parse_number(row[ci])
                if v is not None:
                    vals.append(v)
        if vals:
            s = sum(vals)
            if all(v == int(v) for v in vals):
                total[ci] = f"**{int(s):,}**"
            else:
                total[ci] = f"**{s:,.1f}**"
    return total


def _render_table(
    header: List[str],
    rows: List[List[str]],
    totals: Optional[List[List[str]]] = None,
) -> str:
    """Render a markdown table from components."""
    n = len(header)

    def _pad(cells: List[str]) -> str:
        padded = [(cells[i] if i < len(cells) else "") for i in range(n)]
        return "| " + " | ".join(padded) + " |"

    out = [_pad(header)]
    seps: List[str] = []
    for ci in range(n):
        num_count = sum(1 for r in rows if ci < len(r) and _parse_number(r[ci]) is not None)
        seps.append("---:" if num_count > len(rows) * 0.4 else "---")
    out.append("| " + " | ".join(seps) + " |")
    for row in rows:
        out.append(_pad(row))
    if totals:
        for t in totals:
            out.append(_pad(t))
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════
#  Combiners per tracking file
# ═══════════════════════════════════════════════════════════════


def _combine_stats(main_dir: Path, subagent_dir: Path, source: str) -> None:
    """Parse subagent ``reference_stats.md`` tables, tag with *source*,
    and write / update the combined file."""
    src_path = subagent_dir / STATS_FILE
    if not src_path.exists():
        return
    content = src_path.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return

    new_tables = _extract_tables(content)
    if not new_tables:
        return

    # Add Source column to every new table
    for t in new_tables:
        t["header"].append("Source")
        for row in t["rows"]:
            row.append(source)
        for row in t["totals"]:
            row.append("")

    dest = main_dir / f"{COMBINED_PREFIX}{STATS_FILE}"

    if dest.exists():
        existing = dest.read_text(encoding="utf-8", errors="replace")
        existing_tables = _extract_tables(existing)
        section_map: Dict[str, dict] = {}
        for t in existing_tables:
            section_map[t["section"]] = t
        for nt in new_tables:
            key = nt["section"]
            if key in section_map:
                et = section_map[key]
                et["rows"].extend(nt["rows"])
                et["totals"] = [_recompute_total(et["header"], et["rows"])]
            else:
                section_map[key] = nt
                nt["totals"] = [_recompute_total(nt["header"], nt["rows"])]
        combined_tables = list(section_map.values())
    else:
        combined_tables = new_tables
        for t in combined_tables:
            if t["totals"]:
                t["totals"] = [_recompute_total(t["header"], t["rows"])]

    parts = ["# Combined Subagent Stats\n"]
    for t in combined_tables:
        parts.append("")
        parts.append(t["section"])
        parts.append("")
        parts.append(_render_table(t["header"], t["rows"], t["totals"]))
        parts.append("")

    dest.write_text("\n".join(parts), encoding="utf-8")


def _combine_history(main_dir: Path, subagent_dir: Path, source: str) -> None:
    """Tag step headers with *source* and accumulate into the combined
    history file."""
    src_path = subagent_dir / HISTORY_FILE
    if not src_path.exists():
        return
    content = src_path.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return

    tagged = re.sub(
        r"(### Step \d+)",
        rf"\1 [{source}]",
        content,
    )

    tables = _extract_tables(tagged)
    for t in tables:
        if "Source" not in t["header"]:
            t["header"].append("Source")
            for row in t["rows"]:
                row.append(source)
            for row in t["totals"]:
                row.append("")

    dest = main_dir / f"{COMBINED_PREFIX}{HISTORY_FILE}"
    separator = f"\n\n---\n\n## Subagent: {source}\n\n"

    if dest.exists():
        existing = dest.read_text(encoding="utf-8", errors="replace")
        combined = existing + separator + tagged
    else:
        combined = "# Combined Subagent History\n" + separator + tagged

    dest.write_text(combined, encoding="utf-8")


def _combine_reasoning(main_dir: Path, subagent_dir: Path, source: str) -> None:
    """Tag turn headers with *source* and accumulate into the combined
    reasoning file."""
    src_path = subagent_dir / REASONING_FILE
    if not src_path.exists():
        return
    content = src_path.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return

    tagged = re.sub(
        r"(## Turn \d+)",
        rf"\1 [{source}]",
        content,
    )

    dest = main_dir / f"{COMBINED_PREFIX}{REASONING_FILE}"
    separator = f"\n\n---\n\n## Subagent: {source}\n\n"

    if dest.exists():
        existing = dest.read_text(encoding="utf-8", errors="replace")
        combined = existing + separator + tagged
    else:
        combined = "# Combined Subagent Reasoning\n" + separator + tagged

    dest.write_text(combined, encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
#  Public entry point
# ═══════════════════════════════════════════════════════════════


def merge_subagent_tracking(
    main_dir: Path,
    subagent_dir: Path | str | None,
    agent_type: str,
    label: str = "",
) -> None:
    """Merge one subagent's tracking files into the parent session.

    Parameters
    ----------
    main_dir : Path
        The parent agent's session directory.
    subagent_dir : Path | str | None
        The subagent's session / output directory.
    agent_type : str
        ``"query"`` or ``"analysis"``.
    label : str
        Human-friendly source tag (e.g. first 60 chars of question).
    """
    if not subagent_dir:
        return
    subagent_dir = Path(subagent_dir)
    if not subagent_dir.exists():
        return

    source = label or f"{agent_type}_{subagent_dir.name}"

    for fn, combiner in [
        (STATS_FILE, _combine_stats),
        (HISTORY_FILE, _combine_history),
        (REASONING_FILE, _combine_reasoning),
    ]:
        try:
            combiner(main_dir, subagent_dir, source)
        except Exception as exc:
            log.debug("Failed to combine %s from %s: %s", fn, subagent_dir, exc)
