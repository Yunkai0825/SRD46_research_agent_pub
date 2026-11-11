from __future__ import annotations

import re
from typing import Dict, List

from .reference_alignment import ElementReference
from .species_unifier import CoreGroup, _stoich_to_label

# Baseline source used as the alignment reference for misalignment
# deltas.  Grouping itself is source-agnostic (core stoichiometry +
# phase only); the baseline only decides which row deltas are measured
# *against*, so the column is comparable across groups.
_DEFAULT_BASELINE_SOURCE = "SRD-46"

# Regex to parse component IDs like "Fe$+3", "Cu$-1", "Cu$+0"
_RE_POURBAIX_ID = re.compile(r'^([A-Z][a-z]*)\$([+-]\d+)$')


# ======================================================================
#  Misalignment helper
# ======================================================================

def _compute_misalignment(
    group: CoreGroup, baseline_source: str = _DEFAULT_BASELINE_SOURCE,
) -> List[str]:
    """Per-species misalignment string relative to the baseline source.

    Returns a list parallel to group.species with values:
      "ref"      — baseline-source species chosen as reference (mult=1 preferred)
      "+3.456"   — signed delta in kJ/mol (per formula unit) vs reference
      "—"        — single-source group or no baseline-source reference available
    """
    n = len(group.species)
    if not group.is_multi_source:
        return ["—"] * n

    # Pick baseline-source reference: prefer mult=1, else smallest mult
    ref_sp = None
    ref_idx = -1
    for i, sp in enumerate(group.species):
        if sp.source == baseline_source and sp.multiplier == 1:
            ref_sp, ref_idx = sp, i
            break
    if ref_sp is None:
        for i, sp in enumerate(group.species):
            if sp.source == baseline_source:
                ref_sp, ref_idx = sp, i
                break
    if ref_sp is None:
        return ["—"] * n

    ref_mu = ref_sp.mu_aligned_kJ / ref_sp.multiplier
    result: List[str] = []
    for i, sp in enumerate(group.species):
        if i == ref_idx:
            result.append("ref")
        else:
            delta = sp.mu_aligned_kJ / sp.multiplier - ref_mu
            result.append(f"{delta:+.3f}")
    return result


# ======================================================================
#  Markdown generation
# ======================================================================

def generate_dedup_markdown(
    system_name: str,
    grouped: Dict[str, List[CoreGroup]],
    references: Dict[str, ElementReference],
    valence_table: List[dict],
    metal_info: Dict[str, dict],
    baseline_source: str = _DEFAULT_BASELINE_SOURCE,
) -> str:
    """Generate deduplication_check.md content.

    Duplicate grouping is purely by core stoichiometry + phase and is
    therefore source-agnostic: the data source never influences which
    species are clustered together.  ``baseline_source`` only selects
    which source's row is used as the 0-reference for the
    ``misalignment_kJ`` column.
    """
    lines: List[str] = []

    # Sources actually present, so the header is not hard-wired to any
    # particular pair of databases.
    sources_present = sorted({
        sp.source for gs in grouped.values() for g in gs for sp in g.species
    })
    src_phrase = ", ".join(f"**{s}**" for s in sources_present) or "all sources"

    lines.append(f"# Deduplication Check: {system_name}")
    lines.append("")
    lines.append(f"Species from {src_phrase} grouped by core stoichiometry "
                 "and phase (source does not affect grouping).")
    lines.append(f"Baseline source for misalignment deltas: **{baseline_source}**.")
    lines.append("Integer multiples (e.g. Fe2(OH)2 = 2×FeOH) are "
                 "normalised to the same core group.")
    lines.append("")

    # Summary of metal → Pourbaix ID mapping
    lines.append("### Component Mapping")
    lines.append("")
    lines.append("| pourbaix_id | original_id | name | element | charge |")
    lines.append("|-------------|-------------|------|---------|--------|")

    # Start with SRD-46 valence table entries
    known_ids = set()
    for row in valence_table:
        pid = row['internal_id']
        known_ids.add(pid)
        lines.append(
            f"| {pid} | {row.get('original_id', pid)} | {row['name']} | "
            f"{row['element']} | {row['charge']} |"
        )

    # Collect unmapped element IDs from all core groups (Atlas-only ox states)
    extra_ids: Dict[str, tuple] = {}          # pid → (element, charge_int)
    for gs in grouped.values():
        for g in gs:
            for sp in g.species:
                for comp_id in sp.raw_stoich:
                    if comp_id in known_ids or comp_id in extra_ids:
                        continue
                    m = _RE_POURBAIX_ID.match(comp_id)
                    if m:
                        extra_ids[comp_id] = (m.group(1), int(m.group(2)))

    # Sort extra IDs by (element, charge) and append
    for pid in sorted(extra_ids, key=lambda p: extra_ids[p]):
        el, chg = extra_ids[pid]
        lines.append(
            f"| {pid} | Atlas | {el} (ox {chg:+d}) | {el} | {chg:+d} |"
        )

    lines.append("")

    # Global statistics
    total = sum(len(g.species) for gs in grouped.values() for g in gs)
    total_groups = sum(len(gs) for gs in grouped.values())
    multi_source = sum(
        1 for gs in grouped.values() for g in gs if g.is_multi_source
    )
    multi_member = sum(
        1 for gs in grouped.values() for g in gs if g.count > 1
    )
    lines.append(f"**Total species**: {total} | "
                 f"**Core groups**: {total_groups} | "
                 f"**Multi-member groups**: {multi_member} | "
                 f"**Cross-source groups**: {multi_source}")
    lines.append("")

    # Phase sections
    section_titles = {
        "aqueous": "Aqueous / Dissolved Species",
        "solid": "Solid / Dissolution Species",
        "gas": "Gas Species",
    }

    OVW_HEADER = (
        "| # | core | species | source | charge | mult "
        "| mu_aligned_kJ | n_e | misalignment_kJ | notes |"
    )
    OVW_SEP = (
        "|---|------|---------|--------|--------|------"
        "|---------------|-----|-----------------|-------|"
    )

    section_num = 1
    for phase_key in ("aqueous", "solid", "gas"):
        groups = grouped.get(phase_key, [])
        lines.append(f"## {section_num}. {section_titles[phase_key]}")
        lines.append("")

        if not groups:
            lines.append("*(No species in this section.)*")
            lines.append("")
            section_num += 1
            continue

        n_species = sum(g.count for g in groups)
        lines.append(f"{len(groups)} core groups, {n_species} total species.")
        lines.append("")

        # --- Overview table (all species merged) ---
        lines.append(OVW_HEADER)
        lines.append(OVW_SEP)
        row_num = 0
        for group in groups:
            misalign = _compute_misalignment(group, baseline_source)
            for si, sp in enumerate(group.species):
                row_num += 1
                n_e = sp.extra.get("n_e", "")
                notes = (sp.extra.get("additional_notes") or "").replace("|", "/")
                lines.append(
                    f"| {row_num} "
                    f"| `{group.core_label}` "
                    f"| {sp.name} "
                    f"| {sp.source} "
                    f"| {sp.charge:+d} "
                    f"| {sp.multiplier}x "
                    f"| {sp.mu_aligned_kJ:+.3f} "
                    f"| {n_e} "
                    f"| {misalign[si]} "
                    f"| {notes or '—'} |"
                )
        lines.append("")

        # --- Detailed subsections for multi-member groups only ---
        multi_groups = [g for g in groups if g.count > 1]
        if multi_groups:
            lines.append("### Duplicated Groups")
            lines.append("")

            for gi, group in enumerate(multi_groups, 1):
                # Group header tag
                if group.is_multi_source:
                    dup_tag = " **[CROSS-SOURCE]**"
                else:
                    sources = sorted({s.source for s in group.species})
                    dup_tag = f" **[{group.count}× {sources[0]}]**"

                lines.append(
                    f"#### {section_num}.{gi}  Core: "
                    f"`{group.core_label}`{dup_tag}"
                )
                lines.append("")

                # Species table
                lines.append(
                    "| # | name | source | charge | mult | "
                    "mu_aligned_kJ | n_e | extra |"
                )
                lines.append(
                    "|---|------|--------|--------|------|"
                    "---------------|-----|-------|"
                )

                for si, sp in enumerate(group.species, 1):
                    extra_parts = []
                    if sp.extra.get("ox_state"):
                        extra_parts.append(f"ox={sp.extra['ox_state']}")
                    if sp.extra.get("atlas_name"):
                        extra_parts.append(sp.extra["atlas_name"][:40])
                    if sp.extra.get("species_id"):
                        extra_parts.append(
                            f"id={sp.extra['species_id']}"
                        )
                    if sp.extra.get("mu_abs_kJ"):
                        extra_parts.append(
                            f"DGf={sp.extra['mu_abs_kJ']}"
                        )
                    if sp.extra.get("mu_canon_kJ"):
                        extra_parts.append(
                            f"mu_canon={sp.extra['mu_canon_kJ']}"
                        )
                    if sp.extra.get("additional_notes"):
                        extra_parts.append(
                            str(sp.extra["additional_notes"]).replace("|", "/")
                        )
                    extra_str = "; ".join(extra_parts) if extra_parts else ""

                    lines.append(
                        f"| {si} | {sp.name} | {sp.source} | "
                        f"{sp.charge:+d} | {sp.multiplier}x | "
                        f"{sp.mu_aligned_kJ:+.3f} | "
                        f"{sp.extra.get('n_e', '')} | "
                        f"{extra_str} |"
                    )

                # Delta notes for cross-source groups
                if group.is_multi_source:
                    # Find baseline-source reference
                    ref_sp = None
                    for sp in group.species:
                        if sp.source == baseline_source and sp.multiplier == 1:
                            ref_sp = sp
                            break
                    if ref_sp:
                        ref_mu = ref_sp.mu_aligned_kJ
                        for sp in group.species:
                            if sp is ref_sp:
                                continue
                            sp_mu = sp.mu_aligned_kJ / sp.multiplier
                            delta = abs(sp_mu - ref_mu)
                            lines.append("")
                            lines.append(
                                f"> Δ({sp.name} vs {ref_sp.name})"
                                f" = {delta:.3f} kJ/mol"
                            )

                lines.append("")

        section_num += 1

    return "\n".join(lines)
