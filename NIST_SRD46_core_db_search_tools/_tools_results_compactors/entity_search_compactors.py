"""
Markdown compactors for ``search_metals()`` and ``search_ligands()`` entity search results.

* ``search_metals()`` returns a ``list[dict]``.
* ``search_ligands()`` returns a ``dict`` with keys
  ``results``, ``total_sql_matches``, ``excluded_by_groups``, ``limit``.
  (A plain ``list[dict]`` is still accepted for backward compatibility.)

Usage::

    from ._tools_results_compactors.entity_search_compactors import (
        compact_search_metals,
        compact_search_ligands,
    )
    md = compact_search_metals(search_metals(name="copper"))
    md = compact_search_ligands(search_ligands(name="glycine"))
"""
from __future__ import annotations

from typing import Any

from ._compactor_helpers import speciation_context_hint


# ── tiny helpers ─────────────────────────────────────────────────────

def _cell(val: Any, max_len: int = 80) -> str:
    """Stringify a value for a markdown table cell, truncating if needed."""
    if val is None or str(val).strip() == "":
        return "***"
    s = str(val)
    if len(s) <= max_len:
        return s
    import re
    m = re.search(r' \([^)]+\)$', s)
    if m:
        suffix = m.group()
        prefix = s[:m.start()]
        avail = max_len - len(suffix) - 1
        if avail > 0:
            return prefix[:avail] + "…" + suffix
    return s[: max_len - 1] + "…"


def _compact_brackets(brackets: list[dict] | None) -> str:
    """Format pKa brackets as ``(-inf, H2L, 2, HL, 8.18, L, +inf)``."""
    if not brackets:
        return "***"
    # Each bracket has bracket_label like "(-inf, 2.33)" and HxL_form like "H2L".
    # We interleave: lo, HxL, hi, HxL, hi, ... but shared boundaries collapse.
    parts: list[str] = []
    for i, b in enumerate(brackets):
        label = b.get("bracket_label", "")
        hxl = b.get("HxL_form", "?")
        # Parse lo,hi from bracket_label "(lo, hi)"
        inner = label.strip().strip("()")
        lo_hi = [x.strip() for x in inner.split(",", 1)] if inner else ["?", "?"]
        lo = lo_hi[0] if len(lo_hi) > 0 else "?"
        hi = lo_hi[1] if len(lo_hi) > 1 else "?"
        if i == 0:
            parts.append(lo)
        parts.append(hxl)
        parts.append(hi)
    est = any(b.get("is_estimated") for b in brackets)
    result = "(" + ", ".join(parts) + ")"
    if est:
        result += " *est*"
    return result


def _format_totn(prefix: str, count: Any) -> str:
    return f"{prefix}_totN_{count if count is not None else 0}"


# ═════════════════════════════════════════════════════════════════
#  search_metals compactor
# ═════════════════════════════════════════════════════════════════

def compact_search_metals(data: list[dict] | dict) -> str:
    """Convert a ``search_metals()`` result list to compact markdown.

    Parameters
    ----------
    data : list[dict] or dict
        Return value of ``search_metals()``, or the dict wrapper
        ``{"results": [...], "n_results": N}`` produced by ``wrap_tool()``.

    Returns
    -------
    str
        Markdown text.
    """
    # wrap_tool() wraps list results as {"results": [...], "n_results": N}
    if isinstance(data, dict):
        data = data.get("results", data)
    if not isinstance(data, list):
        return f"**search_metals:** unexpected data type {type(data).__name__}\n"

    if not data:
        return "## search_metals\n\n*(no results)*\n" + speciation_context_hint()

    lines = [
        f"## search_metals — {len(data)} result(s)",
        "",
        "| metal_id | metal_name | symbol | charge | simple_ion | smiles | inchi | beta_def_count | ligand_count | vlm_count |",
        "|----------|------------|--------|--------|------------|--------|-------|----------------|--------------|-----------|",
    ]
    for row in data:
        mid = row.get("metal_id", "?")
        name = _cell(row.get("metal_name", "?"), 40)
        sym = row.get("symbol", "")
        chg = row.get("charge", "?")
        simple = "✓" if row.get("is_simple_ion") else ""
        smiles = row.get("smiles", "") or "***"
        inchi = _cell(row.get("inchi", ""), 40)
        bdc = _format_totn("beta", row.get("beta_def_count", 0))
        lc = _format_totn("ligand", row.get("ligand_count", 0))
        vc = _format_totn("vlm", row.get("vlm_count", 0))
        lines.append(f"| {mid} | {name} | {sym} | {chg} | {simple} | {smiles} | {inchi} | {bdc} | {lc} | {vc} |")

    lines.append("")
    return "\n".join(lines) + "\n" + speciation_context_hint()


# ═════════════════════════════════════════════════════════════════
#  Functional-group statistics helper
# ═════════════════════════════════════════════════════════════════

def _functional_group_stats(smiles_list: list[str], title: str = "all SQL matches") -> list[str]:
    """Scan SMILES against the functional group catalog.

    Parameters
    ----------
    smiles_list : list[str]
        Raw SMILES strings (typically all SQL matches, not just shown rows).
    title : str
        Label for the header (e.g. "all SQL matches", "all ligand partners").

    Returns markdown lines for a summary table of matched groups,
    or an empty list if RDKit is unavailable or no SMILES are present.
    """
    if not smiles_list:
        return []

    try:
        from rdkit import Chem
        from .._normalization_helpers.functional_group_catalog import (
            FUNCTIONAL_GROUP_CATALOG,
        )
    except ImportError:
        return []

    # Parse molecules once
    mols = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is not None:
            mols.append(mol)

    if not mols:
        return []

    # Compile SMARTS and count matches
    counts: list[tuple[str, int]] = []
    for name, smarts in FUNCTIONAL_GROUP_CATALOG.items():
        pat = Chem.MolFromSmarts(smarts)
        if pat is None:
            continue
        n = sum(1 for mol in mols if mol.HasSubstructMatch(pat))
        if n > 0:
            counts.append((name, n))

    if not counts:
        return []

    # Sort by count descending
    counts.sort(key=lambda x: (-x[1], x[0]))

    n_total = len(mols)
    lines = [
        f"### Functional groups across {title} ({n_total} parseable SMILES)",
        "",
        "| group | count | % |",
        "|-------|-------|---|",
    ]
    for name, n in counts:
        pct = round(100 * n / n_total)
        lines.append(f"| {name} | {n} | {pct}% |")
    lines.append("")
    return lines


# ═════════════════════════════════════════════════════════════════
#  search_ligands compactor
# ═════════════════════════════════════════════════════════════════

def compact_search_ligands(data: dict | list[dict]) -> str:
    """Convert a ``search_ligands()`` result to compact markdown.

    Parameters
    ----------
    data : dict or list[dict]
        * **dict** (preferred): ``{"results": [...], "total_sql_matches": N,
          "excluded_by_groups": M, "limit": L}``
        * **list[dict]** (legacy): treated as results only.

    Returns
    -------
    str
        Markdown text with optional stats header.
    """
    # ── normalise input ──────────────────────────────────────────────
    if isinstance(data, dict):
        results = data.get("results", [])
        total = data.get("total_sql_matches", len(results))
        excluded = data.get("excluded_by_groups", 0)
        limit = data.get("limit")
    elif isinstance(data, list):
        results = data
        total = len(data)
        excluded = 0
        limit = None
    else:
        return f"**search_ligands:** unexpected data type {type(data).__name__}\n"

    if not results:
        return "## search_ligands\n\n*(no results)*\n" + speciation_context_hint()

    # ── header + stats line ─────────────────────────────────────────
    lines = [f"## search_ligands — {len(results)} result(s)"]

    parts = [f"{total} SQL matches"]
    if excluded:
        parts.append(f"{excluded} excluded by group filter")
    parts.append(f"showing {len(results)}")
    if limit is not None:
        parts.append(f"limit {limit}")
    lines.append("")
    lines.append("**stats:** " + " · ".join(parts))

    # ── table ────────────────────────────────────────────────────────
    lines += [
        "",
        "| ligand_id | ligand_name | HxL_def | ligand_class | vlm_count | smiles | pka_brackets |",
        "|-----------|-------------|---------|--------------|-----------|--------|--------------|",
    ]
    for row in results:
        lid = row.get("ligand_id", "?")
        name = _cell(row.get("ligand_name", "?"), 50)
        hxl = row.get("ligand_HxL_definition", "") or "***"
        lclass = _cell(row.get("ligand_class", ""), 25)
        vlm = row.get("vlm_count", "***")
        smiles_raw = row.get("smiles", "")
        smiles = f"`{smiles_raw}`" if smiles_raw else "***"
        pka_str = _compact_brackets(row.get("pka_brackets"))
        lines.append(f"| {lid} | {name} | {hxl} | {lclass} | {vlm} | {smiles} | {pka_str} |")

    lines.append("")

    # ── functional group statistics (over ALL SQL matches) ───────────
    all_smiles = data.get("all_smiles", []) if isinstance(data, dict) else []
    if not all_smiles:
        all_smiles = [r.get("smiles") for r in results if r.get("smiles")]
    fg_lines = _functional_group_stats(all_smiles)
    if fg_lines:
        lines.extend(fg_lines)

    return "\n".join(lines) + "\n" + speciation_context_hint()
