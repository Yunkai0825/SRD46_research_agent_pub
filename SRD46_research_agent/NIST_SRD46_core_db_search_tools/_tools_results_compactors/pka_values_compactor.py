"""
Markdown compactor for ``search_pka_values()`` results.

Value-centric pKa rendering: sorts all rows by pKa ascending, then
groups into 0.5-unit bands with section headings and flat tables.
Each row includes per-protonation-form metal binding counts and VLM source.

Columns
-------
* ``M_bind_totN_above`` = metals binding the ``bracket_from`` form
  (deprotonated, dominant at pH > pKa).
* ``M_bind_totN_below`` = metals binding the ``bracket_to`` form
  (protonated, dominant at pH < pKa).
* ``vlm_id`` = source VLM identifier for the pKa measurement.

Rendering tiers (threshold: ``_MAX_COMPACT_CHARS = 5 000`` chars)
-----------------------------------------------------------------
1. **Full** — every pKa row shown in its band table.
2. **Truncated** — each band is capped at ``_MAX_ROWS_PER_BAND = 5``
   rows with per-band statistics appended.

Public API
----------
``compact_pka_values(rows)``
    Returns ``list[str]`` of markdown lines (no heading).
``compact_search_pka_values(data)``
    Returns a complete markdown string with ``## search_pka_values``
    heading and row count.
"""
from __future__ import annotations

import math
from collections import Counter, OrderedDict

from ._compactor_helpers import _cell, _num, speciation_context_hint

_MAX_COMPACT_CHARS = 5000
_MAX_ROWS_PER_BAND = 5


def _format_m_tot(count: object) -> str:
    return f"M_tot_{count}"


def _band_key(pka: float) -> float:
    """Return the lower bound of the 0.5-unit band containing *pka*."""
    return math.floor(pka * 2) / 2


def _functional_group_stats_str(band_rows: list[dict]) -> str:
    """Compact functional-group presence counts across band entries."""
    smiles_list = [str(r.get("smiles") or "").strip() for r in band_rows if r.get("smiles")]
    if not smiles_list:
        return "***"

    try:
        from rdkit import Chem
        from .._normalization_helpers.functional_group_catalog import FUNCTIONAL_GROUP_CATALOG
    except ImportError:
        return "***"

    mols = []
    for smiles in smiles_list:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            mols.append(mol)
    if not mols:
        return "***"

    counts: list[tuple[str, int]] = []
    for name, smarts in FUNCTIONAL_GROUP_CATALOG.items():
        pattern = Chem.MolFromSmarts(smarts)
        if pattern is None:
            continue
        n = sum(1 for mol in mols if mol.HasSubstructMatch(pattern))
        if n > 0:
            counts.append((name, n))

    if not counts:
        return "***"

    counts.sort(key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{name}({n})" for name, n in counts)


# ── table helpers ──────────────────────────────────────────────────

def _table_header(has_similarity: bool) -> tuple[str, str]:
    if has_similarity:
        h = (
            "| vlm_id | ligand_id | ligand_name | HxL_def | smiles | pKa | T°C | I(M) "
            "| bracket_from→to | M_bind_totN_below | M_bind_totN_above | similarity_score |"
        )
        s = (
            "|--------|-----------|-------------|---------|--------|-----|-----|------"
            "|-----------------|-------------------|-------------------|------------------|"
        )
    else:
        h = (
            "| vlm_id | ligand_id | ligand_name | HxL_def | smiles | pKa | T°C | I(M) "
            "| bracket_from→to | M_bind_totN_below | M_bind_totN_above |"
        )
        s = (
            "|--------|-----------|-------------|---------|--------|-----|-----|------"
            "|-----------------|-------------------|-------------------|"
        )
    return h, s


def _render_row(r: dict, has_similarity: bool) -> str:
    vlm = r.get("source_vlm_id", "")
    lid = r.get("ligand_id", "?")
    name = _cell(r.get("ligand_name", ""), 35)
    hxl = r.get("ligand_HxL_definition", "") or "***"
    smiles = r.get("smiles", "") or "***"
    pka = _num(r.get("pKa"))
    temp = _num(r.get("temperature"))
    ionic = _num(r.get("ionic_strength"))
    bfrom = r.get("bracket_from", "") or "***"
    bto = r.get("bracket_to", "") or "***"
    bracket = f"{bfrom}→{bto}"
    m_above = r.get("M_above", "?")
    m_below = r.get("M_below", "?")
    if has_similarity:
        similarity = r.get("similarity_score")
        return (
            f"| {vlm} | {lid} | {name} | {hxl} | {smiles} | {pka} | {temp} | {ionic} "
            f"| {bracket} | {_format_m_tot(m_below)} | {_format_m_tot(m_above)} | {similarity} |"
        )
    return (
        f"| {vlm} | {lid} | {name} | {hxl} | {smiles} | {pka} | {temp} | {ionic} "
        f"| {bracket} | {_format_m_tot(m_below)} | {_format_m_tot(m_above)} |"
    )


# ── per-band stats (used in truncated mode) ───────────────────────

def _band_stats(band_rows: list[dict]) -> list[str]:
    """Compact stats table summarising *all* entries in a band."""
    n = len(band_rows)
    ligs = len({r.get("ligand_id") for r in band_rows})
    pkas = [float(r.get("pKa") or 0) for r in band_rows]
    temps = [float(r.get("temperature") or 0) for r in band_rows
             if r.get("temperature") is not None]
    ionics = [float(r.get("ionic_strength") or 0) for r in band_rows
              if r.get("ionic_strength") is not None]
    hxl_counts = Counter(r.get("ligand_HxL_definition", "?") for r in band_rows)
    hxl_str = ", ".join(f"{k}({v})" for k, v in hxl_counts.most_common())
    func_groups = _functional_group_stats_str(band_rows)

    lines = [
        "",
        f"**Band stats (all {n} entries):**",
        "",
        "| stat | value |",
        "|------|-------|",
        f"| entries | {n} |",
        f"| unique ligands | {ligs} |",
        f"| pKa range | {min(pkas):.2f} – {max(pkas):.2f} |",
    ]
    if temps:
        lines.append(f"| T°C range | {min(temps):g} – {max(temps):g} |")
    if ionics:
        lines.append(f"| I(M) range | {min(ionics):g} – {max(ionics):g} |")
    lines.append(f"| HxL forms | {hxl_str} |")
    lines.append(f"| functional groups | {func_groups} |")
    return lines


# ── band renderer ──────────────────────────────────────────────────

def _render_bands(
    bands: OrderedDict[float, list[dict]],
    has_similarity: bool,
    *,
    truncate: bool,
) -> list[str]:
    header, sep = _table_header(has_similarity)
    lines: list[str] = []
    for lo, band_rows in bands.items():
        hi = lo + 0.5
        lines.append(f"### pKa {lo:.1f}–{hi:.1f} ({len(band_rows)} entries)")
        lines.append("")

        show_rows = band_rows
        need_stats = truncate and len(band_rows) > _MAX_ROWS_PER_BAND
        if need_stats:
            show_rows = band_rows[:_MAX_ROWS_PER_BAND]

        lines.append(header)
        lines.append(sep)
        for r in show_rows:
            lines.append(_render_row(r, has_similarity))

        if need_stats:
            lines.extend(_band_stats(band_rows))

        lines.append("")
    return lines


# ── public entry point ─────────────────────────────────────────────

def compact_pka_values(rows: list[dict]) -> list[str]:
    """Band-grouped pKa rendering sorted by value.

    If the full output exceeds ``_MAX_COMPACT_CHARS``, a second stage
    limits each band to ``_MAX_ROWS_PER_BAND`` sample rows and appends
    a stats table covering **all** entries in that band.
    """
    sorted_rows = sorted(rows, key=lambda r: float(r.get("pKa") or 0))
    has_similarity = any(r.get("similarity_score") is not None for r in sorted_rows)

    bands: OrderedDict[float, list[dict]] = OrderedDict()
    for r in sorted_rows:
        pka = float(r.get("pKa") or 0)
        lo = _band_key(pka)
        bands.setdefault(lo, []).append(r)

    # First pass: full rendering
    lines = _render_bands(bands, has_similarity, truncate=False)
    if len("\n".join(lines)) <= _MAX_COMPACT_CHARS:
        return lines

    # Second pass: truncated with per-band stats
    return _render_bands(bands, has_similarity, truncate=True)


def compact_search_pka_values(data: list[dict] | dict) -> str:
    """Compact markdown for ``search_pka_values()`` results."""
    # wrap_tool() wraps list results as {"results": [...], "n_results": N}
    if isinstance(data, dict):
        data = data.get("results", data)
    if not isinstance(data, list):
        return f"**search_pka_values:** unexpected type {type(data).__name__}\n"
    if not data:
        return "## search_pka_values\n\n*(no results)*\n" + speciation_context_hint()
    n = len(data)
    lines = [f"## search_pka_values \u2014 {n} row(s)", ""]
    lines.extend(compact_pka_values(data))
    lines.append("")
    return "\n".join(lines) + "\n" + speciation_context_hint()
