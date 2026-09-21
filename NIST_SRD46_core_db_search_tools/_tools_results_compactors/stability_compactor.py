"""Markdown compactor for ``search_stability()`` results.

Rows are grouped by (metal_id, ligand_id) pair, then rendered at one of
three detail levels depending on total output length (threshold:
``_MAX_COMPACT_CHARS = 5 000`` chars):

1. **Full** — one subsection per metal-ligand pair with every
   measurement as its own table row (vlm_id, ref_eq_map, beta_def,
   type, value, T°C, I(M), equation, non-aqueous phases,
   HxL_involved, pKa_bracket_involved) and ligand similarity score when
   similarity expansion was used.
2. **Merged** — rows sharing the same equation + constant-type are
   collapsed into a single row showing value/T/I ranges and VLM counts,
   followed by per-section summary statistics.
3. **Global stats** — all per-section detail is replaced by one
   per-constant-type summary table across all metal-ligand pairs,
   followed by a similarity-ranked ligand table, all-metals and
   all-ligands aggregate tables, and functional-group statistics.
4. **Global stats (compact ligands)** — if the aggregate output is
   still oversized, the wide all-ligands aggregate table is replaced
   by a minimal ``ligand_id | ligand_name | n_vlm`` table (mirrors
   the inspect_metal partner-table layout).

Public API
----------
``compact_stability(rows)``
    Returns ``list[str]`` of markdown lines (no heading).
``compact_search_stability(data)``
    Returns a complete markdown string with ``## search_stability``
    heading and row count.
"""
from __future__ import annotations

import json
from collections import OrderedDict

from ._compactor_helpers import speciation_context_hint, _cell, _esc, _ctype, _num

_MAX_COMPACT_CHARS = 5000
_GLOBAL_STATS_MAX_ROWS_PER_TYPE = 25


def _extract_non_aqueous_phases(row: dict) -> str:
    phases: list[str] = []
    seen: set[str] = set()

    tree_json = row.get("equation_tree_json")
    if tree_json:
        try:
            tree = json.loads(tree_json)
        except (TypeError, ValueError):
            tree = None
        if isinstance(tree, dict):
            for side in ("numerator", "denominator"):
                for item in tree.get(side, []) or []:
                    phase = str(item.get("phase") or "").strip().lower()
                    if phase and phase != "aqueous" and phase not in seen:
                        seen.add(phase)
                        phases.append(phase)

    return "; ".join(phases)


# ── helpers ────────────────────────────────────────────────────────

def _group_rows(rows: list[dict]) -> OrderedDict[tuple, list[dict]]:
    groups: OrderedDict[tuple, list[dict]] = OrderedDict()
    for r in rows:
        metal_id = r.get("metal_id", "?")
        metal_name = r.get("metal_name", "") or metal_id
        lig_id = r.get("ligand_id", "?")
        lig_name = r.get("ligand_name", "") or lig_id
        groups.setdefault((metal_id, metal_name, lig_id, lig_name), []).append(r)
    return groups


def _range_str(values: list) -> str:
    """Compact range: single value if all equal, else lo~hi."""
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return "***"
    lo, hi = min(nums), max(nums)
    if lo == hi:
        return _num(lo)
    return f"{_num(lo)}~{_num(hi)}"


def _format_map_ids(map_ids: list[str]) -> str:
    unique_ids = sorted({str(map_id) for map_id in map_ids if map_id})
    if not unique_ids:
        return "***"
    if len(unique_ids) <= 3:
        return "; ".join(unique_ids)
    return f"{len(unique_ids)} diff ref_eq_map"


def _count_distinct(values: list[str]) -> str:
    distinct = {str(value) for value in values if value}
    if not distinct:
        return "0"
    return str(len(distinct))


def _format_ids(values: list[object]) -> str:
    """Preserve concrete canonical IDs in model-facing summaries."""

    distinct = sorted({str(value) for value in values if value})
    return "; ".join(distinct) if distinct else "***"


def _collect_phase_cell(rows: list[dict]) -> str:
    phases: list[str] = []
    seen_phases: set[str] = set()
    for row in rows:
        phase_str = _extract_non_aqueous_phases(row)
        if not phase_str:
            continue
        for part in [p.strip() for p in phase_str.split(";") if p.strip()]:
            if part not in seen_phases:
                seen_phases.add(part)
                phases.append(part)
    return _cell("; ".join(phases), 20) if phases else "***"


def _similarity_score_cell(rows: list[dict]) -> str:
    """Return one score or a score range, omitting absent score metadata."""

    scores = [
        row.get("similarity_score")
        for row in rows
        if row.get("similarity_score") is not None
    ]
    return _range_str(scores) if scores else ""


def _append_section_ligand_meta(lines: list[str], group_rows: list[dict]) -> None:
    first_row = group_rows[0] if group_rows else {}
    ligand_hxl_def = first_row.get("ligand_HxL_definition", "") or "***"
    ligand_smiles = first_row.get("ligand_SMILES", "") or "***"
    lines.append(
        f"ligand_HxL_def: {ligand_hxl_def} | ligand_SMILES: {ligand_smiles}"
    )
    lines.append("")


# ── full rendering (original) ─────────────────────────────────────

def _render_full(groups: OrderedDict[tuple, list[dict]]) -> list[str]:
    lines: list[str] = []
    for (mid, mname, lid, lname), group_rows in groups.items():
        metal_disp = _esc(mname)
        lig_disp = _cell(lname, 60)
        lines.append(
            f"### {metal_disp} + {lig_disp} — {len(group_rows)} measurement(s)"
        )
        lines.append(f"metal_id: {mid} | ligand_id: {lid}")
        _append_section_ligand_meta(lines, group_rows)
        lines.append(
            "| vlm_id | ref_eq_map | beta_def | type | value | T°C | I(M) | equation | non_aqueous_phases | HxL_involved | pKa_bracket_involved |"
        )
        lines.append(
            "|--------|------------|----------|------|-------|-----|------|----------|--------------------|--------------|-------------|"
        )
        for r in group_rows:
            vlm = r.get("vlm_id", "?")
            ref_eq_map = r.get("map_id") or "***"
            beta = r.get("beta_definition_id", "?")
            ctype = _ctype(r.get("constant_type"))
            logk = _num(r.get("log_K"))
            temp = _num(r.get("temperature"))
            ionic = _num(r.get("ionic_strength"))
            eq = _esc(r.get("equation_str", ""))
            non_aqueous = _cell(_extract_non_aqueous_phases(r), 20)
            hxl = r.get("HxL_involved", "") or ""
            pka_br = r.get("pKa_bracket_involved", "") or ""
            lines.append(
                f"| {vlm} | {ref_eq_map} | {beta} | {ctype} | {logk} | {temp} | {ionic} | {eq} | {non_aqueous} | {hxl} | {pka_br} |"
            )
        lines.append("")
    return lines


# ── merged rendering (equation+type collapsed) ────────────────────

def _render_merged(groups: OrderedDict[tuple, list[dict]]) -> list[str]:
    lines: list[str] = []
    for (mid, mname, lid, lname), group_rows in groups.items():
        metal_disp = _esc(mname)
        lig_disp = _cell(lname, 60)
        lines.append(
            f"### {metal_disp} + {lig_disp} — {len(group_rows)} measurement(s)"
        )
        lines.append(f"metal_id: {mid} | ligand_id: {lid}")
        _append_section_ligand_meta(lines, group_rows)
        lines.append(
            "| equation | type | vlm_counts | vlm_ids | ref_eq_map | value_range | T°C_range | I(M)_range | beta_defs | non_aqueous_phases | HxL_involved | pKa_bracket_involved |"
        )
        lines.append(
            "|----------|------|------------|---------|------------|-------------|-----------|------------|-----------|--------------------|--------------|-------------|"
        )

        # Group by (equation_str, constant_type)
        eq_type_groups: OrderedDict[tuple[str, str], list[dict]] = OrderedDict()
        for r in group_rows:
            eq = r.get("equation_str", "") or ""
            ctype = _ctype(r.get("constant_type"))
            eq_type_groups.setdefault((eq, ctype), []).append(r)

        for (eq, ctype), sub_rows in eq_type_groups.items():
            n = len(sub_rows)
            vlm_ids = _format_ids([r.get("vlm_id") for r in sub_rows])
            map_col = _format_map_ids([r.get("map_id") for r in sub_rows])
            val_range = _range_str([r.get("log_K") for r in sub_rows])
            t_range = _range_str([r.get("temperature") for r in sub_rows])
            i_range = _range_str([r.get("ionic_strength") for r in sub_rows])
            betas = sorted({str(r.get("beta_definition_id", "?")) for r in sub_rows})
            beta_str = "; ".join(betas)
            naq_str = _collect_phase_cell(sub_rows)
            # Use first row's HxL/pKa (same equation → same HxL)
            hxl = sub_rows[0].get("HxL_involved", "") or ""
            pka_br = sub_rows[0].get("pKa_bracket_involved", "") or ""
            lines.append(
                f"| {_esc(eq)} | {ctype} | {n} | {vlm_ids} | {map_col} | {val_range} | {t_range} | {i_range} | {beta_str} | {naq_str} | {hxl} | {pka_br} |"
            )

        lines.append("")
        lines.extend(_render_section_stats(group_rows))
        lines.append("")
    return lines


def _render_section_stats(group_rows: list[dict]) -> list[str]:
    lines: list[str] = []
    by_type: OrderedDict[str, list[dict]] = OrderedDict()
    for row in group_rows:
        ctype = _ctype(row.get("constant_type"))
        by_type.setdefault(ctype, []).append(row)

    lines.append("Summary stats")
    lines.append(
        "| type | vlm_counts | beta_counts | T°C_range | I(M)_range | non_aqueous_phases | ref_eq_map_counts |"
    )
    lines.append(
        "|------|------------|-------------|-----------|------------|--------------------|-------------------|"
    )
    for ctype, type_rows in by_type.items():
        vlm_counts = _count_distinct([r.get("vlm_id") for r in type_rows])
        beta_counts = _count_distinct([r.get("beta_definition_id") for r in type_rows])
        t_range = _range_str([r.get("temperature") for r in type_rows])
        i_range = _range_str([r.get("ionic_strength") for r in type_rows])
        phase_cell = _collect_phase_cell(type_rows)
        map_count = _count_distinct([r.get("map_id") for r in type_rows])
        lines.append(
            f"| {ctype} | {vlm_counts} | {beta_counts} | {t_range} | {i_range} | {phase_cell} | {map_count} |"
        )
    return lines


def _render_global_stats(
    groups: OrderedDict[tuple, list[dict]],
    *,
    compact_ligands: bool = False,
) -> list[str]:
    lines: list[str] = []
    type_groups: OrderedDict[str, list[tuple[tuple, list[dict]]]] = OrderedDict()

    for key, group_rows in groups.items():
        by_type: OrderedDict[str, list[dict]] = OrderedDict()
        for row in group_rows:
            ctype = _ctype(row.get("constant_type"))
            by_type.setdefault(ctype, []).append(row)
        for ctype, type_rows in by_type.items():
            type_groups.setdefault(ctype, []).append((key, type_rows))

    for ctype, entries in type_groups.items():
        entries = sorted(entries, key=lambda item: len(item[1]), reverse=True)
        total_pairs = len(entries)
        truncated = total_pairs > _GLOBAL_STATS_MAX_ROWS_PER_TYPE
        shown = entries[:_GLOBAL_STATS_MAX_ROWS_PER_TYPE] if truncated else entries
        header = f"### {ctype} \u2014 {total_pairs} metal-ligand pair(s)"
        if truncated:
            header += f" (top {_GLOBAL_STATS_MAX_ROWS_PER_TYPE} by vlm count)"
        lines.append(header)
        lines.append(
            "| metal_id | metal_name | ligand_id | ligand_name | ligand_HxL_def | ligand_SMILES | vlm_counts | vlm_ids | beta_counts | beta_def_ids | value_range | T\u00b0C_range | I(M)_range | non_aqueous_phases | ref_eq_map_counts |"
        )
        lines.append(
            "|----------|------------|-----------|-------------|----------------|---------------|------------|---------|-------------|--------------|-------------|-----------|------------|--------------------|-------------------|"
        )
        for (mid, mname, lid, lname), type_rows in shown:
            hxl_def = type_rows[0].get("ligand_HxL_definition", "") or "***"
            smiles = type_rows[0].get("ligand_SMILES", "") or "***"
            metal_name = _cell(mname, 20)
            ligand_name = _cell(lname, 28)
            vlm_counts = _count_distinct([r.get("vlm_id") for r in type_rows])
            vlm_ids = _format_ids([r.get("vlm_id") for r in type_rows])
            beta_counts = _count_distinct([r.get("beta_definition_id") for r in type_rows])
            beta_ids = _format_ids([
                r.get("beta_definition_id") for r in type_rows
            ])
            value_range = _range_str([r.get("log_K") for r in type_rows])
            t_range = _range_str([r.get("temperature") for r in type_rows])
            i_range = _range_str([r.get("ionic_strength") for r in type_rows])
            phase_cell = _collect_phase_cell(type_rows)
            map_count = _count_distinct([r.get("map_id") for r in type_rows])
            lines.append(
                f"| {mid} | {metal_name} | {lid} | {ligand_name} | {hxl_def} | {smiles} | {vlm_counts} | {vlm_ids} | {beta_counts} | {beta_ids} | {value_range} | {t_range} | {i_range} | {phase_cell} | {map_count} |"
            )
        if truncated:
            omitted = total_pairs - _GLOBAL_STATS_MAX_ROWS_PER_TYPE
            lines.append(f"... {omitted} more metal-ligand pair(s) omitted (see aggregate stats below)")
        lines.append("")

    # ── aggregate chemistry context across ALL searched rows ──
    all_rows: list[dict] = []
    for group_rows in groups.values():
        all_rows.extend(group_rows)
    lines.extend(_render_aggregate_metal_stats(all_rows))
    if compact_ligands:
        lines.extend(_render_compact_ligand_stats(all_rows))
    else:
        lines.extend(_render_aggregate_ligand_stats(all_rows))
    lines.extend(_render_aggregate_functional_groups(all_rows))
    return lines


def _ctype_breakdown(rows: list[dict]) -> str:
    """Return ``logK:120; ΔH:8`` style breakdown sorted by descending count."""
    counts: OrderedDict[str, int] = OrderedDict()
    for row in rows:
        ctype = _ctype(row.get("constant_type"))
        counts[ctype] = counts.get(ctype, 0) + 1
    if not counts:
        return "***"
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "; ".join(f"{name}:{n}" for name, n in items)


def _render_similarity_ligand_scores(rows: list[dict]) -> list[str]:
    """Preserve the similarity score assigned to every expanded ligand."""

    by_ligand: OrderedDict[tuple, list[dict]] = OrderedDict()
    for row in rows:
        if row.get("similarity_score") is None:
            continue
        key = (
            row.get("ligand_id", "?"),
            row.get("ligand_name", "") or row.get("ligand_id", "?"),
        )
        by_ligand.setdefault(key, []).append(row)
    if not by_ligand:
        return []

    def _rank(item: tuple[tuple, list[dict]]) -> float:
        scores = [
            row.get("similarity_score")
            for row in item[1]
            if row.get("similarity_score") is not None
        ]
        try:
            return max(float(score) for score in scores)
        except (TypeError, ValueError):
            return float("-inf")

    entries = sorted(by_ligand.items(), key=_rank, reverse=True)
    lines = [
        f"### Similarity-ranked ligands — {len(entries)} ligand(s)",
        "| ligand_id | ligand_name | similarity_score | n_metals | n_vlm |",
        "|-----------|-------------|------------------|----------|-------|",
    ]
    for (ligand_id, ligand_name), ligand_rows in entries:
        score = _similarity_score_cell(ligand_rows) or "***"
        n_metals = _count_distinct([
            row.get("metal_id") for row in ligand_rows
        ])
        n_vlm = _count_distinct([row.get("vlm_id") for row in ligand_rows])
        lines.append(
            f"| {ligand_id} | {_cell(ligand_name, 30)} | {score} | "
            f"{n_metals} | {n_vlm} |"
        )
    lines.append("")
    return lines


def _render_aggregate_metal_stats(rows: list[dict]) -> list[str]:
    """One table summarising every distinct metal across all matched rows."""
    if not rows:
        return []
    by_metal: OrderedDict[tuple, list[dict]] = OrderedDict()
    for r in rows:
        key = (r.get("metal_id", "?"), r.get("metal_name", "") or r.get("metal_id", "?"))
        by_metal.setdefault(key, []).append(r)
    total_metals = len(by_metal)
    entries = sorted(by_metal.items(), key=lambda kv: -len(kv[1]))
    lines = [
        f"### All-metals aggregate \u2014 {total_metals} distinct metal(s)",
        "| metal_id | metal_name | n_ligands | n_vlm | n_beta_def | type_breakdown | T\u00b0C_range | I(M)_range | non_aqueous_phases |",
        "|----------|------------|-----------|-------|------------|----------------|-----------|------------|--------------------|",
    ]
    for (mid, mname), m_rows in entries:
        n_lig = _count_distinct([r.get("ligand_id") for r in m_rows])
        n_vlm = _count_distinct([r.get("vlm_id") for r in m_rows])
        n_beta = _count_distinct([r.get("beta_definition_id") for r in m_rows])
        breakdown = _ctype_breakdown(m_rows)
        t_range = _range_str([r.get("temperature") for r in m_rows])
        i_range = _range_str([r.get("ionic_strength") for r in m_rows])
        phase_cell = _collect_phase_cell(m_rows)
        lines.append(
            f"| {mid} | {_cell(mname, 30)} | {n_lig} | {n_vlm} | {n_beta} | {breakdown} | {t_range} | {i_range} | {phase_cell} |"
        )
    lines.append("")
    return lines


def _render_aggregate_ligand_stats(rows: list[dict]) -> list[str]:
    """One table summarising every distinct ligand across all matched rows."""
    if not rows:
        return []
    by_ligand: OrderedDict[tuple, list[dict]] = OrderedDict()
    for r in rows:
        key = (r.get("ligand_id", "?"), r.get("ligand_name", "") or r.get("ligand_id", "?"))
        by_ligand.setdefault(key, []).append(r)
    total_ligands = len(by_ligand)
    entries = sorted(by_ligand.items(), key=lambda kv: -len(kv[1]))
    lines = [
        f"### All-ligands aggregate \u2014 {total_ligands} distinct ligand(s)",
        "| ligand_id | ligand_name | ligand_HxL_def | ligand_SMILES | n_metals | n_vlm | n_beta_def | type_breakdown | T\u00b0C_range | I(M)_range |",
        "|-----------|-------------|----------------|---------------|----------|-------|------------|----------------|-----------|------------|",
    ]
    for (lid, lname), l_rows in entries:
        hxl_def = l_rows[0].get("ligand_HxL_definition", "") or "***"
        smiles = l_rows[0].get("ligand_SMILES", "") or "***"
        n_metals = _count_distinct([r.get("metal_id") for r in l_rows])
        n_vlm = _count_distinct([r.get("vlm_id") for r in l_rows])
        n_beta = _count_distinct([r.get("beta_definition_id") for r in l_rows])
        breakdown = _ctype_breakdown(l_rows)
        t_range = _range_str([r.get("temperature") for r in l_rows])
        i_range = _range_str([r.get("ionic_strength") for r in l_rows])
        lines.append(
            f"| {lid} | {_cell(lname, 30)} | {hxl_def} | {smiles} | {n_metals} | {n_vlm} | {n_beta} | {breakdown} | {t_range} | {i_range} |"
        )
    lines.append("")
    return lines


def _render_compact_ligand_stats(rows: list[dict]) -> list[str]:
    """Functional-group-bucketed ligand stats (replaces per-ligand rows).

    Used when the all-ligands aggregate table is itself too large
    (search may match thousands of distinct ligands). Each row is one
    functional group; metrics are aggregated across all rows whose
    ligand SMILES matches that group's SMARTS pattern.

    Columns: functional_group | n_ligands | n_metals | n_vlm | n_beta_def
             | type_breakdown | T°C_range | I(M)_range
    Plus an "(unmatched)" bucket for ligands with no parseable / no
    catalog hit, and an "(all)" total row.
    """
    if not rows:
        return []
    # Index rows by ligand SMILES (one mol per distinct SMILES).
    rows_by_smiles: OrderedDict[str, list[dict]] = OrderedDict()
    for r in rows:
        smi = r.get("ligand_SMILES") or ""
        rows_by_smiles.setdefault(smi, []).append(r)

    try:
        from rdkit import Chem
        from .._normalization_helpers.functional_group_catalog import (
            FUNCTIONAL_GROUP_CATALOG,
        )
    except ImportError:
        return []

    # Parse molecules once per distinct SMILES.
    mol_by_smiles: dict[str, object] = {}
    for smi in rows_by_smiles:
        if not smi:
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol is not None:
            mol_by_smiles[smi] = mol

    # Bucket SMILES by functional group.
    group_smiles: OrderedDict[str, list[str]] = OrderedDict()
    matched_smiles: set[str] = set()
    for name, smarts in FUNCTIONAL_GROUP_CATALOG.items():
        pat = Chem.MolFromSmarts(smarts)
        if pat is None:
            continue
        hits = [smi for smi, mol in mol_by_smiles.items() if mol.HasSubstructMatch(pat)]
        if hits:
            group_smiles[name] = hits
            matched_smiles.update(hits)

    unmatched_smiles = [smi for smi in rows_by_smiles if smi not in matched_smiles]

    total_distinct_ligands = len({r.get("ligand_id") for r in rows if r.get("ligand_id")})

    def _bucket_stats(smiles_list: list[str]) -> tuple[str, str, str, str, str, str, str]:
        bucket_rows: list[dict] = []
        for smi in smiles_list:
            bucket_rows.extend(rows_by_smiles.get(smi, []))
        n_lig = _count_distinct([r.get("ligand_id") for r in bucket_rows])
        n_metals = _count_distinct([r.get("metal_id") for r in bucket_rows])
        n_vlm = _count_distinct([r.get("vlm_id") for r in bucket_rows])
        n_beta = _count_distinct([r.get("beta_definition_id") for r in bucket_rows])
        breakdown = _ctype_breakdown(bucket_rows)
        t_range = _range_str([r.get("temperature") for r in bucket_rows])
        i_range = _range_str([r.get("ionic_strength") for r in bucket_rows])
        return n_lig, n_metals, n_vlm, n_beta, breakdown, t_range, i_range

    lines = [
        f"### Ligand functional-group stats \u2014 {total_distinct_ligands} distinct ligand(s) bucketed",
        "(per-ligand table omitted; ligands grouped by SMARTS-matched functional group; one ligand may appear in multiple groups)",
        "| functional_group | n_ligands | n_metals | n_vlm | n_beta_def | type_breakdown | T\u00b0C_range | I(M)_range |",
        "|------------------|-----------|----------|-------|------------|----------------|-----------|------------|",
    ]
    # Sort buckets by ligand count desc.
    bucket_entries = sorted(
        group_smiles.items(),
        key=lambda kv: -len({r.get("ligand_id") for smi in kv[1] for r in rows_by_smiles.get(smi, [])}),
    )
    for name, smiles_list in bucket_entries:
        n_lig, n_metals, n_vlm, n_beta, breakdown, t_range, i_range = _bucket_stats(smiles_list)
        lines.append(
            f"| {name} | {n_lig} | {n_metals} | {n_vlm} | {n_beta} | {breakdown} | {t_range} | {i_range} |"
        )
    if unmatched_smiles:
        n_lig, n_metals, n_vlm, n_beta, breakdown, t_range, i_range = _bucket_stats(unmatched_smiles)
        lines.append(
            f"| (unmatched/unparseable) | {n_lig} | {n_metals} | {n_vlm} | {n_beta} | {breakdown} | {t_range} | {i_range} |"
        )
    lines.append("")
    return lines


def _render_aggregate_functional_groups(rows: list[dict]) -> list[str]:
    """Functional-group prevalence across distinct ligand SMILES in the matches."""
    if not rows:
        return []
    seen: set[str] = set()
    smiles_list: list[str] = []
    for r in rows:
        smi = r.get("ligand_SMILES")
        if smi and smi not in seen:
            seen.add(smi)
            smiles_list.append(smi)
    if not smiles_list:
        return []
    try:
        from .entity_search_compactors import _functional_group_stats
    except ImportError:
        return []
    return _functional_group_stats(smiles_list, title="all stability ligand matches")


# ── public entry point ─────────────────────────────────────────────

def compact_stability(rows: list[dict]) -> list[str]:
    """Group stability rows by (metal, ligand) pair, one table per pair.

    If the full output exceeds ``_MAX_COMPACT_CHARS``, rows sharing the
    same equation and measurement type are merged into a single row
    showing value/T/I ranges and vlm counts, followed by a summary table
    for that same metal-ligand section. If that output still exceeds the
    limit, replace the detailed sections with global per-type summary tables.
    """
    groups = _group_rows(rows)
    similarity_lines = _render_similarity_ligand_scores(rows)
    lines = similarity_lines + _render_full(groups)
    if len("\n".join(lines)) <= _MAX_COMPACT_CHARS:
        return lines
    lines = similarity_lines + _render_merged(groups)
    if len("\n".join(lines)) <= _MAX_COMPACT_CHARS:
        return lines
    lines = similarity_lines + _render_global_stats(groups)
    if len("\n".join(lines)) <= _MAX_COMPACT_CHARS:
        return lines
    return similarity_lines + _render_global_stats(
        groups, compact_ligands=True
    )


def compact_search_stability(data: list[dict] | dict) -> str:
    """Compact markdown for ``search_stability()`` results."""
    # wrap_tool() wraps list results as {"results": [...], "n_results": N}
    if isinstance(data, dict):
        data = data.get("results", data)
    if not isinstance(data, list):
        return f"**search_stability:** unexpected data type {type(data).__name__}\n"
    if not data:
        return "## search_stability\n\n*(no results)*\n" + speciation_context_hint()
    n = len(data)
    lines = [f"## search_stability \u2014 {n} row(s)", ""]
    lines.extend(compact_stability(data))
    lines.append("")
    return "\n".join(lines) + "\n" + speciation_context_hint()
