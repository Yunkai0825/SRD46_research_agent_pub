"""
dedup_check.py — Stoichiometric deduplication check across databases.
=====================================================================
Groups all species (card + atlas) by their core M(i)/L(j)/H stoichiometry,
separated into three phase sections: aqueous/dissolved, solid, gas.

Two species share a "core identity" when their stoichiometric vectors
(M1, M2, ..., L1, L2, ..., H) are identical or integer multiples of
each other.  The GCD of all non-zero coefficients normalizes each
vector to its minimal form.

This module generates a ``deduplication_check.md`` that lists every
species under its core identity group, making it easy to spot duplicate
or conflicting entries from different data sources (SRD-46, Pourbaix
atlas).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import reduce
from math import gcd
from typing import Dict, List, Optional, Tuple

from ..db_pourbaix_atlas.atlas_data import AtlasSpecies, _SYMBOL_TO_NAME
from .reference_alignment import (
    AlignedAtlasSpecies,
    AlignedCardSpecies,
    ElementReference,
    parse_atlas_formula,
    compute_decomposition,
    _parse_stoich,
    parse_card_section5,
    _normalize_atlas_name,
    allocate_metal_oxidation_counts,
)

log = logging.getLogger("DedupCheck")


# ======================================================================
#  Data containers
# ======================================================================

@dataclass
class UnifiedSpecies:
    """A species from either source in a common representation."""
    name: str               # display label
    source: str             # "Atlas" or "SRD-46"
    phase: str              # "aqueous", "solid", "gas"
    charge: int
    mu_aligned_kJ: float
    raw_stoich: Dict[str, int]       # {M1: 1, H: -2, ...}
    core_stoich: Dict[str, int]      # GCD-normalised
    multiplier: int                  # raw / core
    elements: Tuple[str, ...] = field(default_factory=tuple)
    extra: Dict[str, str] = field(default_factory=dict)  # metadata


@dataclass
class CoreGroup:
    """A group of species sharing the same core stoichiometry."""
    core_key: Tuple               # sorted tuple of (comp, count) pairs
    core_label: str               # human-readable, e.g. "M2:1 H:-1"
    phase: str
    species: List[UnifiedSpecies] = field(default_factory=list)

    @property
    def is_multi_source(self) -> bool:
        sources = {s.source for s in self.species}
        return len(sources) > 1

    @property
    def count(self) -> int:
        return len(self.species)


# ======================================================================
#  Stoichiometry helpers
# ======================================================================

def _normalise_stoich(stoich: Dict[str, int]) -> Tuple[Dict[str, int], int]:
    """Normalise stoich dict by GCD. Returns (normalised, multiplier)."""
    vals = [abs(v) for v in stoich.values() if v != 0]
    if not vals:
        return dict(stoich), 1
    g = reduce(gcd, vals)
    return {k: v // g for k, v in stoich.items()}, g


def _stoich_to_key(stoich: Dict[str, int]) -> Tuple:
    """Convert stoich dict to a hashable sorted tuple."""
    return tuple(sorted(
        (k, v) for k, v in stoich.items() if v != 0
    ))


def _stoich_to_label(stoich: Dict[str, int]) -> str:
    """Human-readable label, e.g. 'Fe$1:1 H:-1'."""
    parts = []
    # Order: metals/element IDs first, then L* (sorted), then H
    keys = sorted(stoich.keys(), key=lambda k: (
        1 if k.startswith("L") else 2 if k == "H" else 0,
        k,
    ))
    for k in keys:
        v = stoich[k]
        if v != 0:
            parts.append(f"{k}:{v:+d}" if v < 0 else f"{k}:{v}")
        # skip zero values
    return " ".join(parts) if parts else "(empty)"


def _phase_bucket(phase: str) -> str:
    """Map phase strings to 'aqueous', 'solid', or 'gas'."""
    p = phase.lower().strip()
    if p in ("dissolved", "aqueous"):
        return "aqueous"
    if p in ("solid", "dissolution", "liquid"):
        return "solid"
    if p in ("gaseous", "gas"):
        return "gas"
    return p


# ======================================================================
#  Atlas → M(i) mapping
# ======================================================================

def _map_atlas_to_card_stoich(
    asp: AlignedAtlasSpecies,
    valence_table: List[dict],
    metal_info: Dict[str, dict],
    references: Dict[str, ElementReference],
) -> Optional[Dict[str, int]]:
    """Map an atlas species to card M(i)/H stoichiometry.

    Atlas species have element + oxidation_state; the valence table
    tells us which M(i) that corresponds to.

    Mixed-valence rows, including rounded average-valence labels, are
    allocated by charge balance.  If an ambiguous oxidation-state label
    cannot be allocated uniquely, all metal atoms are represented on the
    element's canonical reference state rather than being dropped from the
    composition.
    """
    el = asp.element

    # Build reverse map: (element, ox_state_int) → internal_id
    ox_to_mid: Dict[Tuple[str, int], str] = {}
    for row in valence_table:
        ox_int = int(str(row["charge"]).replace("+", ""))
        ox_to_mid[(row["element"], ox_int)] = row["internal_id"]

    stoich: Dict[str, int] = {}
    allocations = allocate_metal_oxidation_counts(
        asp.oxidation_state,
        asp.n_metal,
        asp.H_net,
        asp.charge,
        central_element=el,
        available_states=sorted(
            ox for element, ox in ox_to_mid if element == el
        ),
    )
    if allocations is not None:
        for ox_num, count in allocations.items():
            if count == 0:
                continue
            mid = ox_to_mid.get((el, ox_num), f"{el}${ox_num:+d}")
            stoich[mid] = stoich.get(mid, 0) + count
    elif asp.n_metal:
        # Never discard a mixed/fractional-valence phase merely because its
        # Atlas oxidation-state cell cannot be allocated uniquely.  Express
        # it on the canonical element reference; H_net and the aligned energy
        # still retain useful identity information without truncating the
        # oxidation-state label.
        ref = references.get(el)
        if ref is None:
            log.warning(
                "Atlas species %s has unresolved oxidation states %r and no "
                "element reference; preserving the element token",
                asp.species, asp.oxidation_state,
            )
            mid = el
        else:
            ref_ox = ref.oxidation_state
            mid = ox_to_mid.get((el, ref_ox), f"{el}${ref_ox:+d}")
            log.warning(
                "Atlas species %s has unresolved oxidation states %r; "
                "representing all %d %s atoms on reference state %+d",
                asp.species, asp.oxidation_state, asp.n_metal, el, ref_ox,
            )
        stoich[mid] = asp.n_metal
    if asp.H_net != 0:
        stoich["H"] = asp.H_net

    return stoich


# ======================================================================
#  Build unified species list
# ======================================================================

def build_unified_species(
    atlas_aligned_by_el: Dict[str, List[AlignedAtlasSpecies]],
    card_aligned: List[AlignedCardSpecies],
    valence_table: List[dict],
    metal_info: Dict[str, dict],
    references: Dict[str, ElementReference],
) -> List[UnifiedSpecies]:
    """Build a single list of UnifiedSpecies from both sources."""
    unified: List[UnifiedSpecies] = []

    # --- Atlas species ---
    for el_sym, species_list in atlas_aligned_by_el.items():
        for asp in species_list:
            raw = _map_atlas_to_card_stoich(
                asp, valence_table, metal_info, references,
            )
            if raw is None:
                raw = {}

            core, mult = _normalise_stoich(raw)
            phase = _phase_bucket(asp.phase)

            unified.append(UnifiedSpecies(
                name=_normalize_atlas_name(asp.species, asp.charge),
                source="Atlas",
                phase=phase,
                charge=asp.charge,
                mu_aligned_kJ=asp.mu0_aligned_kJ,
                raw_stoich=raw,
                core_stoich=core,
                multiplier=mult,
                elements=(el_sym,),
                extra={
                    "element": el_sym,
                    "ox_state": asp.oxidation_state,
                    "mu_abs_kJ": f"{asp.mu0_abs_kJ:+.3f}",
                    "atlas_name": asp.name[:60] if asp.name else "",
                    "n_e": str(asp.n_electrons),
                },
            ))

    # --- Card species ---
    for csp in card_aligned:
        raw: Dict[str, int] = {}
        for mid, count in csp.metal_stoich.items():
            raw[mid] = count
        for lid, count in csp.ligand_stoich.items():
            raw[lid] = count
        if csp.H_net != 0:
            raw["H"] = csp.H_net

        core, mult = _normalise_stoich(raw)
        phase = _phase_bucket(csp.phase)

        unified.append(UnifiedSpecies(
            name=csp.label,
            source=csp.source or "SRD-46",
            phase=phase,
            charge=csp.charge,
            mu_aligned_kJ=csp.mu0_aligned_kJ,
            raw_stoich=raw,
            core_stoich=core,
            multiplier=mult,
            elements=tuple(sorted({
                str(metal_info[mid]["element"])
                for mid in csp.metal_stoich
                if mid in metal_info and metal_info[mid].get("element")
            })),
            extra={
                "species_id": csp.species_id,
                "mu_canon_kJ": f"{csp.mu0_canon_kJ:+.4f}",
                "stoich_str": csp.stoich_str,
                "n_e": str(csp.n_electrons),
                "source_record_id": csp.source_record_id,
                "additional_notes": csp.additional_notes,
            },
        ))

    return unified


# ======================================================================
#  Grouping
# ======================================================================

def group_by_core(
    unified: List[UnifiedSpecies],
) -> Dict[str, List[CoreGroup]]:
    """Group species by phase bucket, then by core stoichiometry.

    Returns {"aqueous": [...], "solid": [...], "gas": [...]}
    """
    # Accumulate into (phase, core_key) -> list
    buckets: Dict[Tuple[str, Tuple], List[UnifiedSpecies]] = {}
    for sp in unified:
        key = (sp.phase, _stoich_to_key(sp.core_stoich))
        buckets.setdefault(key, []).append(sp)

    result: Dict[str, List[CoreGroup]] = {
        "aqueous": [],
        "solid": [],
        "gas": [],
    }

    for (phase, core_key), species in buckets.items():
        core_dict = dict(core_key)
        group = CoreGroup(
            core_key=core_key,
            core_label=_stoich_to_label(core_dict),
            phase=phase,
            species=sorted(species, key=lambda s: s.mu_aligned_kJ),
        )
        if phase in result:
            result[phase].append(group)

    # Sort each phase section by core_label for stable output
    for phase in result:
        result[phase].sort(key=lambda g: g.core_label)

    return result

# ======================================================================
#  Top-level API
# ======================================================================

def run_dedup_check(
    card_text: str,
    atlas_aligned_by_el: Dict[str, List[AlignedAtlasSpecies]],
    card_aligned: List[AlignedCardSpecies],
    valence_table: List[dict],
    metal_info: Dict[str, dict],
    references: Dict[str, ElementReference],
    system_name: str = "System",
) -> Tuple[str, dict]:
    """Run deduplication check and generate markdown.

    Returns (markdown_str, summary_dict).
    """
    unified = build_unified_species(
        atlas_aligned_by_el, card_aligned,
        valence_table, metal_info, references,
    )

    grouped = group_by_core(unified)

    from .species_dedup_report_writer import generate_dedup_markdown
    md = generate_dedup_markdown(
        system_name, grouped, references, valence_table, metal_info,
    )

    # Build summary
    total = len(unified)
    total_groups = sum(len(gs) for gs in grouped.values())
    multi_member = sum(
        1 for gs in grouped.values() for g in gs if g.count > 1
    )
    cross_source = sum(
        1 for gs in grouped.values() for g in gs if g.is_multi_source
    )

    return md, {
        "system": system_name,
        "total_species": total,
        "core_groups": total_groups,
        "multi_member_groups": multi_member,
        "cross_source_groups": cross_source,
        "by_phase": {
            phase: {"groups": len(gs), "species": sum(g.count for g in gs)}
            for phase, gs in grouped.items()
        },
    }
