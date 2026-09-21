"""
pourbaix_merge.py — LLM-free Pourbaix-atlas merge.
=============================================================
Parses a free-energy MD card and merges in every Pourbaix-atlas species
for the card's elements, applying reference-state alignment but **no**
deduplication.  Every species from both SRD-46 and the Pourbaix atlas is
included by default; resolving duplicates is LC2_3's responsibility.

Public API
----------
    merge_card_hardcoded(card_text, system_name, *, elements=None)
        → (enriched_card_text, stats_dict)
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from .atlas_loader import atlas_species_for_element
from .atlas_data import _SYMBOL_TO_NAME

from .._md_card_merge_core.merge_helpers import (
    _parse_card_metals,
    _parse_card_valence_table,
    _element_from_metal_name,
    _build_metal_info,
    _parse_2303rt,
    _discover_atlas_only_ids,
    _compute_atlas_only_offsets,
    _build_atlas_metal_dicts,
    _precompute_enrichment_fields,
    _RE_POURBAIX_ID,
    SKIP_ELEMENTS,
    WATER_SPECIES_ELEMENTS,
)
from .._md_card_merge_core.reference_state_converter import compute_valence_offsets
from .._md_card_merge_core.reference_alignment import (
    select_element_references,
    align_atlas_species,
    align_card_species,
    allocate_metal_oxidation_counts,
    integral_oxidation_states,
    parse_card_section5,
    build_pourbaix_id_map,
    remap_to_pourbaix_ids,
    remap_card_species,
)
from .._md_card_merge_core.species_unifier import (
    build_unified_species,
    group_by_core,
    run_dedup_check,
    UnifiedSpecies,
)
from .._md_card_merge_core.enriched_card_writer import (
    EnrichedSpecies,
    build_enriched_card,
)

log = logging.getLogger("HardcodedMerge")


# ======================================================================
#  Convert grouped species → EnrichedSpecies (all included)
# ======================================================================

def _safe_float(s: str, default: float = 0.0) -> float:
    s = s.strip().lstrip("+")
    if not s or s in ("—", "–"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _augment_atlas_valence_inventory(
    atlas_aligned_by_el: Dict[str, list],
    valence_table: List[dict],
    metal_info: Dict[str, dict],
) -> Tuple[List[dict], Dict[str, dict]]:
    """Expose Atlas-required integral valences before species mapping.

    Atlas-only IDs used to be discovered only *after* unification.  At that
    point a state absent from the input card had already been rejected by the
    oxidation-state allocator and collapsed onto the canonical reference.
    Build a temporary mapping inventory first, using only integral states
    explicitly present somewhere in the Atlas data and allocations that pass
    the existing formula charge-balance checks.

    The returned table is for mapping/dedup only.  The caller retains the
    original card table for reference selection, offsets, totals, and the
    writer's base-valence count; the existing Atlas-only writer path adds the
    synthetic rows with zero analytical total.
    """
    effective_table = [dict(row) for row in valence_table]
    effective_info = {
        internal_id: dict(info)
        for internal_id, info in metal_info.items()
    }
    existing = {
        (str(row["element"]), int(row["charge"]))
        for row in valence_table
    }
    candidates: Dict[str, Set[int]] = {}
    for element, charge in existing:
        candidates.setdefault(element, set()).add(charge)

    # First pass: explicit integral labels establish real available states.
    # Fractional averages deliberately do not invent floor/ceil valences.
    for element, species_list in atlas_aligned_by_el.items():
        available = candidates.setdefault(element, set())
        for species in species_list:
            available.update(integral_oxidation_states(
                species.oxidation_state,
                central_element=element,
            ))

    required: Set[Tuple[str, int]] = set()
    for element, species_list in atlas_aligned_by_el.items():
        available = sorted(candidates.get(element, set()))
        for species in species_list:
            allocation = allocate_metal_oxidation_counts(
                species.oxidation_state,
                species.n_metal,
                species.H_net,
                species.charge,
                central_element=element,
                available_states=available,
            )
            if allocation is None:
                continue
            # A single integral Atlas label is otherwise accepted directly
            # by the allocator.  Before allowing it to expand the card's
            # component inventory, require the formula's formal O/H charge
            # balance to agree as well.  This prevents aggregate/peroxide
            # spellings from inventing impossible metal valences.
            if sum(
                state * count for state, count in allocation.items()
            ) != species.charge - species.H_net:
                continue
            required.update(
                (element, state)
                for state, count in allocation.items()
                if count and (element, state) not in existing
            )

    required_ids = {
        f"{element}${charge:+d}" for element, charge in required
    }
    for atlas_metal in _build_atlas_metal_dicts(required_ids):
        internal_id = atlas_metal["internal_id"]
        effective_table.append({
            "element": atlas_metal["element"],
            "internal_id": internal_id,
            "name": atlas_metal["name"],
            "charge": atlas_metal["charge"],
            "is_reference": False,
        })
        effective_info[internal_id] = {
            "element": atlas_metal["element"],
            "charge": atlas_metal["charge"],
            "name": atlas_metal["name"],
        }

    if required_ids:
        log.info(
            "[Hardcoded] Pre-seeded Atlas valences for mapping: %s",
            ", ".join(sorted(required_ids)),
        )
    return effective_table, effective_info


def _grouped_to_enriched(
    grouped: Dict[str, list],
) -> List[EnrichedSpecies]:
    """Convert all species in the grouped dict to EnrichedSpecies.

    Every species is included (no LLM dedup filtering).
    """
    enriched: List[EnrichedSpecies] = []
    for phase_key in ("aqueous", "solid", "gas"):
        for group in grouped.get(phase_key, []):
            # Mark duplicate groups (species from both SRD-46 and Atlas)
            dup_tag = ""
            if group.is_multi_source:
                dup_tag = f"[DUPLICATE GROUP: {group.core_label}]"

            for sp in group.species:
                notes_parts: list = []
                if dup_tag:
                    notes_parts.append(dup_tag)
                if sp.source == "Atlas":
                    notes_parts.append(f"Atlas: {sp.name}")
                elif sp.extra.get("additional_notes"):
                    notes_parts.append(sp.extra["additional_notes"])
                notes = " ".join(notes_parts)

                enriched.append(EnrichedSpecies(
                    species_id=sp.extra.get("species_id", ""),
                    original_id=sp.extra.get("original_id", ""),
                    label=sp.name,
                    charge=sp.charge,
                    phase=sp.extra.get("phase", phase_key),
                    log_beta=_safe_float(sp.extra.get("log_beta", "0")),
                    mu0_free_kJ=_safe_float(sp.extra.get("mu0_free_kJ", "0")),
                    mu0_canon_kJ=_safe_float(sp.extra.get("mu_canon_kJ", "0")),
                    stoich=sp.extra.get("stoich_str", ""),
                    include=True,
                    additional_notes=notes,
                    source=sp.source,
                    mu_aligned_kJ=sp.mu_aligned_kJ,
                ))
    return enriched


# ======================================================================
#  Main entry point
# ======================================================================

def merge_card_hardcoded(
    card_text: str,
    system_name: str,
    *,
    elements: Optional[List[str]] = None,
    dedup_instruction: Optional[Dict[str, object]] = None,
    merge_water_species_redox: bool = False,
) -> Tuple[str, dict]:
    """Run the full merge pipeline without LLM deduplication.

    Parameters
    ----------
    card_text : original speciation Markdown card
    system_name : e.g. "FeCitrate"
    elements : override elements to query from atlas.
               If None, auto-detected from card metals (skipping C, H, O).
    dedup_instruction : accepted for backward compatibility but **ignored**.
               LC2_2 performs no deduplication; every merged species is
               kept.  Filtering duplicates is LC2_3's responsibility.
    merge_water_species_redox : when False (default) the aqueous
               self-system elements (H, O) are excluded from the atlas
               redox merge — H⁺/OH⁻ are pure references and need no
               Pourbaix data. Set True to query the atlas for them too.

    Returns
    -------
    (enriched_card_text, stats_dict)
    """
    # ── 1. Parse card ─────────────────────────────────────────
    metals = _parse_card_metals(card_text)
    valence_table = _parse_card_valence_table(card_text)
    factor_2303RT = _parse_2303rt(card_text)

    if elements is None:
        skip = set(SKIP_ELEMENTS)
        if merge_water_species_redox:
            skip -= WATER_SPECIES_ELEMENTS
        elements = list(dict.fromkeys(
            _element_from_metal_name(m) for m in metals
        ))
        elements = [e for e in elements if e not in skip]

    log.info("[Hardcoded] system=%s, metals=%s, elements=%s",
             system_name, metals, elements)

    if not valence_table:
        log.warning("[Hardcoded] No valence table — returning original card.")
        return card_text, {"status": "no_valence", "system": system_name}

    # ── 2. Load atlas ─────────────────────────────────────────
    atlas_by_name: Dict[str, list] = {}
    all_atlas: list = []
    for el in elements:
        el_name = _SYMBOL_TO_NAME.get(el, el)
        species = atlas_species_for_element(el)
        if species:
            atlas_by_name[el_name] = species
            all_atlas.extend(species)
            log.info("[Hardcoded] Atlas [%s → %s]: %d species",
                     el, el_name, len(species))

    if not all_atlas:
        log.warning("[Hardcoded] No atlas data — returning original card.")
        return card_text, {"status": "no_atlas", "system": system_name,
                           "elements": elements}

    # ── 3. Offsets + Pourbaix IDs ─────────────────────────────
    valence_offsets = compute_valence_offsets(all_atlas, valence_table)
    metal_info = _build_metal_info(valence_table)
    id_map = build_pourbaix_id_map(valence_table)
    valence_table, valence_offsets, metal_info = remap_to_pourbaix_ids(
        valence_table, valence_offsets, metal_info, id_map,
    )

    # ── 4. Alignment ─────────────────────────────────────────
    references = select_element_references(atlas_by_name, valence_table)
    element_ref_charges = {
        sym: ref.oxidation_state for sym, ref in references.items()
    }
    atlas_aligned_by_el: Dict[str, list] = {}
    for sym, ref in references.items():
        el_name = ref.element_name
        species = atlas_by_name.get(el_name, [])
        aligned = align_atlas_species(species, ref)
        atlas_aligned_by_el[sym] = aligned

    effective_valence_table, effective_metal_info = (
        _augment_atlas_valence_inventory(
            atlas_aligned_by_el, valence_table, metal_info,
        )
    )

    card_species_orig = parse_card_section5(card_text)
    card_species = remap_card_species(card_species_orig, id_map)

    original_id_map: Dict[str, str] = {}
    for orig, remapped in zip(card_species_orig, card_species):
        original_id_map[remapped["species_id"]] = orig["species_id"]

    card_aligned = align_card_species(
        card_species, valence_offsets, metal_info, element_ref_charges,
    )

    # ── 5. Unify & group ─────────────────────────────────────
    unified = build_unified_species(
        atlas_aligned_by_el, card_aligned,
        effective_valence_table, effective_metal_info, references,
    )
    grouped = group_by_core(unified)

    # ── 5b. Deduplication check ──────────────────────────────
    dedup_md, dedup_stats = run_dedup_check(
        card_text=card_text,
        atlas_aligned_by_el=atlas_aligned_by_el,
        card_aligned=card_aligned,
        valence_table=effective_valence_table,
        metal_info=effective_metal_info,
        references=references,
        system_name=system_name,
    )

    # ── 6. Atlas-only offsets ─────────────────────────────────
    extra_ids = _discover_atlas_only_ids(grouped, valence_offsets)
    atlas_only_offsets = _compute_atlas_only_offsets(extra_ids, grouped)
    full_offsets = dict(valence_offsets)
    full_offsets.update(atlas_only_offsets)
    atlas_metals = _build_atlas_metal_dicts(extra_ids)

    # ── 6b. Pre-compute enrichment fields ─────────────────────
    card_by_id: Dict[str, dict] = {}
    for sp in card_species:
        card_by_id[sp["species_id"]] = sp

    _precompute_enrichment_fields(
        grouped, card_by_id, original_id_map,
        full_offsets, factor_2303RT,
    )

    # ── 7. No deduplication (LC2_2 is pure parse + merge) ─────
    # Resolving duplicate / overlapping species across SRD-46 and the
    # external DBs is LC2_3's responsibility. Every grouped species is
    # retained here.

    # ── 7b. Convert all kept species → EnrichedSpecies ────
    enriched_species = _grouped_to_enriched(grouped)

    n_srd = sum(1 for s in enriched_species if s.source == "SRD-46")
    n_atlas = sum(1 for s in enriched_species if s.source == "Atlas")
    log.info("[Hardcoded] All included: %d SRD-46, %d Atlas, %d total",
             n_srd, n_atlas, len(enriched_species))

    # ── 8. Build enriched card ────────────────────────────────
    n_valences = len(valence_table) + len(atlas_metals)

    enriched_card = build_enriched_card(
        card_text=card_text,
        id_map=id_map,
        enriched_species=enriched_species,
        atlas_metals=atlas_metals,
        atlas_offsets=atlas_only_offsets,
        valence_offsets=full_offsets,
        n_valences_total=n_valences,
    )

    stats = {
        "status": "ok",
        "system": system_name,
        "elements": elements,
        "n_srd46_species": n_srd,
        "n_atlas_species": n_atlas,
        "n_total_species": len(enriched_species),
        "n_atlas_only_metals": len(atlas_metals),
        "id_map": id_map,
        "dedup_md": dedup_md,
        "dedup_stats": dedup_stats,
        # Exposed so a downstream consumer (LC2_3) can enumerate the
        # core-stoichiometry groups. LC2_2 never mutates this; it only
        # reads species names / sources / mu values.
        "_grouped": grouped,
    }

    return enriched_card, stats
