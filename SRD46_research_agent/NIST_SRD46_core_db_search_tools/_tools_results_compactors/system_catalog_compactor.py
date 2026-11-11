"""
Markdown compactor for ``build_system_catalog()`` results.

Converts the nested pairs/species/equilibrium structure into a compact
markdown report suitable for LLM agent consumption.

Usage::

    from ._tools_results_compactors.system_catalog_compactor import compact_system_catalog
    md = compact_system_catalog(build_system_catalog(metal_id=41, ligand_id=10103))
"""
from __future__ import annotations

from typing import Any


# ── tiny helpers ─────────────────────────────────────────────────────

def _cell(val: Any, max_len: int = 80) -> str:
    if val is None or str(val).strip() == "":
        return "***"
    s = str(val)
    if len(s) <= max_len:
        return s
    # Smart chunking: preserve trailing parenthetical like " (Glycine)"
    import re
    m = re.search(r' \([^)]+\)$', s)
    if m:
        suffix = m.group()
        prefix = s[:m.start()]
        avail = max_len - len(suffix) - 1
        if avail > 0:
            return prefix[:avail] + "…" + suffix
    return s[: max_len - 1] + "…"


def _clean_num(v) -> str:
    """Format a numeric value, rounding away floating-point noise."""
    if v is None:
        return "***"
    if isinstance(v, float):
        return f"{round(v, 4):g}"
    return str(v)


def _fmt_range(lo, hi, unit: str = "") -> str:
    if lo is None and hi is None:
        return "***"
    slo, shi = _clean_num(lo), _clean_num(hi)
    if slo == shi:
        return f"{slo}{unit}"
    return f"{slo}~{shi}{unit}"


# ═════════════════════════════════════════════════════════════════
#  Per-pair renderers (full & compact)
# ═════════════════════════════════════════════════════════════════

_COMPACT_THRESHOLD = 5000


def _render_pair_full(pair: dict) -> list[str]:
    """Render one metal–ligand pair in full (verbose) mode."""
    mid = pair.get("metal_id", "?")
    lid = pair.get("ligand_id", "?")
    mname = pair.get("metal_name", "?")
    lname = pair.get("ligand_name", "?")
    hxl = pair.get("definition_HxL") or "***"
    total_ent = pair.get("total_stability_entries", "?")
    n_sp = pair.get("n_unique_species", "?")
    total_vlm = pair.get("total_vlm_count", "?")

    lines: list[str] = []
    lines.append(f"### {mname} + {lname}")
    lines.append(f"**metal_id:** {mid} | **ligand_id:** {lid} | **ligand_def_HxL:** {hxl}  ")
    lines.append(
        f"**entries:** {total_ent} | **species:** {n_sp} | "
        f"**vlm_count:** {total_vlm}"
    )
    lines.append("")

    # ── Species catalog table ──
    species = pair.get("species_catalog", [])
    if species:
        lines.append("| beta_definition_id | beta_definition_name | equation_str | phases | n_entries |")
        lines.append("|--------------------|----------------------|--------------|--------|----------|")
        for sp in species:
            bdid = sp.get("beta_definition_id", "?")
            bdname = _cell(sp.get("beta_definition_name", ""), 40)
            eq = _cell(sp.get("equation_str", ""), 40)
            phases = _cell(sp.get("phases", ""), 80)
            n = sp.get("n_entries", "?")
            lines.append(f"| {bdid} | {bdname} | {eq} | {phases} | {n} |")
        lines.append("")

    # ── VLM IDs ──
    vlm_ids = pair.get("vlm_ids", [])
    if vlm_ids:
        if len(vlm_ids) <= 10:
            lines.append(f"**vlm_ids:** {', '.join(str(v) for v in vlm_ids)}")
        else:
            first = ', '.join(str(v) for v in vlm_ids[:5])
            last = ', '.join(str(v) for v in vlm_ids[-3:])
            lines.append(
                f"**vlm_ids:** {first}, … {last} "
                f"({len(vlm_ids)} listed"
                + (f" of {total_vlm}" if total_vlm != len(vlm_ids) else "")
                + ")"
            )
        lines.append("")

    # ── Equilibrium maps ──
    eq_maps = pair.get("equilibrium_maps", [])
    if eq_maps:
        lines.append(
            f"**equilibrium_maps:** {len(eq_maps)} preset reference network(s) "
            f"*(clustered around room temperature & low ionic strength)*"
        )
        lines.append("")
        lines.append("| network_id | nodes | edges | T range | I range |")
        lines.append("|------------|-------|-------|---------|---------|")
        for em in eq_maps:
            nid = em.get("network_id", "?")
            nc = em.get("node_count", "?")
            ec = em.get("edge_count", "?")
            t_range = _fmt_range(em.get("temp_min"), em.get("temp_max"), " °C")
            i_range = _fmt_range(em.get("ionic_min"), em.get("ionic_max"), " M")
            lines.append(f"| {nid} | {nc} | {ec} | {t_range} | {i_range} |")
        lines.append("")

    return lines


def _render_pair_compact(pair: dict) -> list[str]:
    """Render one metal–ligand pair in compact mode (>5 000 chars budget)."""
    mid = pair.get("metal_id", "?")
    lid = pair.get("ligand_id", "?")
    mname = pair.get("metal_name", "?")
    lname = pair.get("ligand_name", "?")
    hxl = pair.get("definition_HxL") or "***"
    total_ent = pair.get("total_stability_entries", "?")
    n_sp = pair.get("n_unique_species", "?")
    total_vlm = pair.get("total_vlm_count", "?")

    lines: list[str] = []
    lines.append(f"### {mname} + {lname}")
    lines.append(f"**metal_id:** {mid} | **ligand_id:** {lid} | **ligand_def_HxL:** {hxl}  ")
    lines.append(
        f"**entries:** {total_ent} | **species:** {n_sp} | "
        f"**vlm_count:** {total_vlm}"
    )
    lines.append("")

    # ── Species catalog (slim table) ──
    species = pair.get("species_catalog", [])
    if species:
        # Phase check: are all species fully aqueous?
        all_aqueous = all(
            "aqueous" in (sp.get("phases") or "")
            and not any(
                ph in (sp.get("phases") or "")
                for ph in ("solid", "gas", "liquid", "organic")
            )
            for sp in species
        )
        if all_aqueous:
            lines.append("*(all species aqueous)*")
        lines.append("| beta_def_id | equation_str | n |")
        lines.append("|-------------|--------------|---|")
        for sp in species:
            bdid = sp.get("beta_definition_id", "?")
            eq = _cell(sp.get("equation_str", ""), 45)
            n = sp.get("n_entries", "?")
            if not all_aqueous:
                phases = sp.get("phases", "") or ""
                # Show only non-aqueous phases
                non_aq = [
                    p.strip()
                    for p in phases.split(",")
                    if p.strip() and "aqueous" not in p
                ]
                if non_aq:
                    eq = f"{eq} | {', '.join(non_aq)}"
            lines.append(f"| {bdid} | {eq} | {n} |")
        lines.append("")

    # ── VLM IDs (count + range only) ──
    vlm_ids = pair.get("vlm_ids", [])
    if vlm_ids:
        if len(vlm_ids) <= 3:
            lines.append(f"**vlm_ids:** {', '.join(str(v) for v in vlm_ids)}")
        else:
            lines.append(
                f"**vlm_ids:** {len(vlm_ids)} ({vlm_ids[0]}…{vlm_ids[-1]})"
            )
        lines.append("")

    # ── Equilibrium maps (one-line summary) ──
    eq_maps = pair.get("equilibrium_maps", [])
    if eq_maps:
        t_mins = [em.get("temp_min") for em in eq_maps if em.get("temp_min") is not None]
        t_maxs = [em.get("temp_max") for em in eq_maps if em.get("temp_max") is not None]
        i_mins = [em.get("ionic_min") for em in eq_maps if em.get("ionic_min") is not None]
        i_maxs = [em.get("ionic_max") for em in eq_maps if em.get("ionic_max") is not None]
        max_nodes = max((em.get("node_count", 0) for em in eq_maps), default=0)
        max_edges = max((em.get("edge_count", 0) for em in eq_maps), default=0)

        t_range = _fmt_range(
            min(t_mins) if t_mins else None,
            max(t_maxs) if t_maxs else None,
            " °C",
        )
        i_range = _fmt_range(
            min(i_mins) if i_mins else None,
            max(i_maxs) if i_maxs else None,
            " M",
        )
        nids = [em.get("network_id", "?") for em in eq_maps]
        nids_str = ", ".join(str(n) for n in nids[:3])
        if len(nids) > 3:
            nids_str += f"…{nids[-1]}"

        lines.append(
            f"**eq_maps:** {len(eq_maps)} ref nets ({nids_str}) | "
            f"T: {t_range} | I: {i_range} | "
            f"max {max_nodes} nodes, {max_edges} edges"
        )
        lines.append("")

    return lines


# ═════════════════════════════════════════════════════════════════
#  Ultra-compact renderer (stage-2 compaction)
# ═════════════════════════════════════════════════════════════════

_ULTRA_COMPACT_THRESHOLD = 8000


def _build_equation_legend(pairs: list[dict]) -> list[str]:
    """Collect all unique (beta_def_id → equation_str) across pairs.

    Returns markdown lines for a legend table, sorted by numeric ID.
    Includes a note column for non-aqueous species.
    """
    legend: dict[str, str] = {}  # beta_def_id → equation_str
    phase_notes: dict[str, set] = {}  # beta_def_id → set of non-aqueous labels
    for pair in pairs:
        for sp in pair.get("species_catalog", []):
            bdid = sp.get("beta_definition_id", "?")
            eq = sp.get("equation_str") or "***"
            if bdid not in legend:
                legend[bdid] = eq
                phase_notes[bdid] = set()
            phases = sp.get("phases", "") or ""
            for ph in ("solid", "gas", "liquid", "organic"):
                if ph in phases:
                    phase_notes[bdid].add(ph)

    def _sort_key(item):
        try:
            return int(item[0].replace("beta_def_", ""))
        except (ValueError, AttributeError):
            return 0

    sorted_items = sorted(legend.items(), key=_sort_key)

    lines = ["### Equation legend", ""]
    lines.append("| beta_def_id | equation | note |")
    lines.append("|-------------|----------|------|")
    for bdid, eq in sorted_items:
        notes = phase_notes.get(bdid, set())
        note_str = ", ".join(sorted(notes)) if notes else ""
        lines.append(f"| {bdid} | {eq} | {note_str} |")
    lines.append("")
    return lines


def _eq_maps_summary(eq_maps: list[dict]) -> str:
    """One-line eq_maps summary for ultra-compact mode."""
    if not eq_maps:
        return ""
    t_mins = [em.get("temp_min") for em in eq_maps if em.get("temp_min") is not None]
    t_maxs = [em.get("temp_max") for em in eq_maps if em.get("temp_max") is not None]
    i_mins = [em.get("ionic_min") for em in eq_maps if em.get("ionic_min") is not None]
    i_maxs = [em.get("ionic_max") for em in eq_maps if em.get("ionic_max") is not None]
    max_nodes = max((em.get("node_count", 0) for em in eq_maps), default=0)
    max_edges = max((em.get("edge_count", 0) for em in eq_maps), default=0)

    t_range = _fmt_range(
        min(t_mins) if t_mins else None,
        max(t_maxs) if t_maxs else None,
        "°C",
    )
    i_range = _fmt_range(
        min(i_mins) if i_mins else None,
        max(i_maxs) if i_maxs else None,
        "M",
    )
    return (
        f"eq:{len(eq_maps)} nets T:{t_range} I:{i_range} "
        f"max {max_nodes}n/{max_edges}e"
    )


def _render_pair_ultra(pair: dict, idx: int) -> list[str]:
    """Render one pair as a numbered list item with sub-bullets.

    Main line: **N. Metal + Ligand** (ids) — ligand_def_HxL: X | entries, species, vlms (range)
    Sub-bullet 1: species tokens  beta_def_id(n) ...
    Sub-bullet 2: eq_maps summary
    """
    mid = pair.get("metal_id", "?")
    lid = pair.get("ligand_id", "?")
    mname = pair.get("metal_name", "?")
    lname = pair.get("ligand_name", "?")
    hxl = pair.get("definition_HxL") or "***"
    total_ent = pair.get("total_stability_entries", "?")
    n_sp = pair.get("n_unique_species", "?")
    total_vlm = pair.get("total_vlm_count", "?")

    vlm_ids = pair.get("vlm_ids", [])
    if len(vlm_ids) <= 3:
        vlm_str = ", ".join(str(v) for v in vlm_ids) if vlm_ids else "***"
    else:
        vlm_str = f"{vlm_ids[0]}…{vlm_ids[-1]}"

    # Main line
    line1 = (
        f"**{idx}. {mname} + {lname}** ({mid} + {lid}) — "
        f"ligand_def_HxL: {hxl} | {total_ent} ent, {n_sp} sp, "
        f"{total_vlm} vlms ({vlm_str})"
    )

    # Sub-bullet: species tokens using full prefixed IDs
    species = pair.get("species_catalog", [])
    sp_tokens = []
    for sp in species:
        bdid = sp.get("beta_definition_id", "?")
        n = sp.get("n_entries", "?")
        sp_tokens.append(f"{bdid}({n})")

    lines = [line1]
    lines.append(f"   - species: {' '.join(sp_tokens)}")

    # Sub-bullet: eq_maps summary
    eq_sum = _eq_maps_summary(pair.get("equilibrium_maps", []))
    if eq_sum:
        lines.append(f"   - {eq_sum}")

    return lines


# ═════════════════════════════════════════════════════════════════
#  Public compactor
# ═════════════════════════════════════════════════════════════════

def compact_system_catalog(data: dict) -> str:
    """Convert a ``build_system_catalog()`` result dict to compact markdown.

    Parameters
    ----------
    data : dict
        Return value of ``build_system_catalog()``.

    Returns
    -------
    str
        Markdown text.
    """
    if not isinstance(data, dict):
        return f"**build_system_catalog:** unexpected type {type(data).__name__}\n"

    if "error" in data:
        return f"## build_system_catalog\n\n**Error:** {data['error']}\n"

    pairs = data.get("pairs", [])
    summary = data.get("summary", {})

    if not pairs:
        return (
            "## build_system_catalog\n\n*(no pairs found)*\n\n"
            f"**summary:** {summary}\n"
        )

    header = (
        f"## build_system_catalog — "
        f"{summary.get('n_pairs', '?')} pair(s), "
        f"{summary.get('total_species', '?')} species"
    )

    # ── First pass: full render ──────────────────────────────────────
    full_lines = [header, ""]
    for i, pair in enumerate(pairs):
        full_lines.extend(_render_pair_full(pair))
        if i < len(pairs) - 1:
            full_lines += ["---", ""]

    full_md = "\n".join(full_lines) + "\n"
    if len(full_md) <= _COMPACT_THRESHOLD:
        return full_md

    # ── Second pass: compact render ──────────────────────────────────
    compact_lines = [header + " *(compact)*", ""]
    for i, pair in enumerate(pairs):
        compact_lines.extend(_render_pair_compact(pair))
        if i < len(pairs) - 1:
            compact_lines += ["---", ""]

    compact_md = "\n".join(compact_lines) + "\n"
    if len(compact_md) <= _ULTRA_COMPACT_THRESHOLD:
        return compact_md

    # ── Third pass: ultra-compact render ─────────────────────────────
    ultra_lines = [header + " *(ultra-compact)*", ""]
    ultra_lines.extend(_build_equation_legend(pairs))

    # Global aqueous note
    all_aqueous_global = all(
        "aqueous" in (sp.get("phases") or "")
        and not any(
            ph in (sp.get("phases") or "")
            for ph in ("solid", "gas", "liquid", "organic")
        )
        for pair in pairs
        for sp in pair.get("species_catalog", [])
    )
    if all_aqueous_global:
        ultra_lines.append("*(all species aqueous)*")
    else:
        ultra_lines.append("*(all species aqueous unless noted)*")
    ultra_lines.append("")

    for i, pair in enumerate(pairs):
        ultra_lines.extend(_render_pair_ultra(pair, i + 1))
    ultra_lines.append("")

    from ._compactor_helpers import speciation_context_hint
    return "\n".join(ultra_lines) + "\n" + speciation_context_hint()
