"""SRD46_card_merger.py
Merge multiple reference free-energy cards into one unified card.

Each ref card is a per-metal–ligand-pair MD card produced by
``ref_eq_SRD46_cards_builder``.  The merger:
  1. Parses each ref card via ``parse_free_energy_card_md``
  2. Unifies components (metals, ligands, solvents)
  3. Concatenates species tables
  4. Flags duplicate species (same stoichiometry from different cards)
  5. Generates a unified MD via ``generate_free_energy_card_md``

This is the **thin orchestrator** — all heavy logic lives in the
``SRD46_card_merger_helpers/`` sub-package.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Union

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_CALC_ROOT = _THIS.parents[2]                       # LC2_free_energy_card_building/
_PIPELINE_ROOT = _THIS.parents[3]                   # NIST_SRD46_calc_input_building_agentic_pipeline/
for _p in (_CALC_ROOT, _PIPELINE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
    FreeEnergyReport,
    ValenceGroup,
    RedoxCouple,
    LigandMicroValence,
    _detect_valence_groups,
)

# ── helper imports ─────────────────────────────────────────────
from .component_unifier import unify_components
from .species_concatenator import (
    concatenate_species,
    concatenate_eq_meta,
)
from card_management_helpers.free_energy_md_card_reader import (
    parse_free_energy_card_md,
)
from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_md_cards_builder.ref_eq_free_energy_md_card_generation import (
    generate_free_energy_card_md,
)


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def merge_ref_cards(
    ref_card_paths: List[Union[str, Path]],
    *,
    system_name: str = "",
) -> Tuple[str, FreeEnergyReport, List[dict]]:
    """Merge multiple reference cards into one unified free-energy card.

    Parameters
    ----------
    ref_card_paths : list of paths to ``.md`` reference cards
    system_name : label for the merged card header

    Returns
    -------
    (merged_md_text, merged_report, srd_srd_collisions) where the third
    element lists SRD-SRD duplicate groups kept in the card for LC2_3
    adjudication (empty when every shared dependency merged cleanly).
    """
    # ── Parse all ref cards ────────────────────────────────────
    reports: List[FreeEnergyReport] = []
    card_names: List[str] = []
    for p in ref_card_paths:
        p = Path(p)
        report = parse_free_energy_card_md(p)
        reports.append(report)
        card_names.append(p.stem)

    if not reports:
        raise ValueError("No reports to merge")

    # ── Unify components ───────────────────────────────────────
    (
        unified_meta,
        remaps,
        total_metals,
        total_ligands,
        metal_ids,
        ligand_ids,
        metal_names,
        ligand_names,
        metal_charges,
        ligand_charges,
    ) = unify_components(reports)

    # ── Concatenate species (merge all; drop only identical) ───
    provenances = [
        {
            "card": card_names[i],
            "T_C": r.temperature_C,
            "I_M": r.ionic_strength,
            "factor": r.factor,
        }
        for i, r in enumerate(reports)
    ]
    unique_species, srd_srd_collisions = concatenate_species(
        reports, remaps, provenances,
    )

    # ── Concatenate eq meta ────────────────────────────────────
    eq_meta = concatenate_eq_meta(reports)

    # ── Merge solvents (take first, all should be water) ──────
    solvents = reports[0].solvents if reports[0].solvents else []

    # ── Regenerate valence groups from unified components ───────
    # Individual ref_eq cards may each have only one metal per element,
    # but the unified component list contains all metals across all cards.
    # _detect_valence_groups groups by element and picks the reference state.
    valence_groups: List[ValenceGroup] = _detect_valence_groups(unified_meta)

    # ── Merge redox couples ───────────────────────────────────
    seen_couples: set = set()
    redox_couples: List[RedoxCouple] = []
    for report in reports:
        for rc in report.redox_couples:
            if rc.couple_id not in seen_couples:
                redox_couples.append(copy.deepcopy(rc))
                seen_couples.add(rc.couple_id)

    # ── Merge micro-valence ───────────────────────────────────
    seen_mv: set = set()
    micro_valences: List[LigandMicroValence] = []
    for report in reports:
        for mv in report.ligand_micro_valences:
            if mv.ligand_id not in seen_mv:
                micro_valences.append(copy.deepcopy(mv))
                seen_mv.add(mv.ligand_id)

    # ── Collect notes ─────────────────────────────────────────
    all_notes: List[str] = []
    for report in reports:
        all_notes.extend(report.notes)
    if srd_srd_collisions:
        all_notes.append(
            f"SRD-SRD duplicates kept for LC2_3 adjudication: "
            f"{len(srd_srd_collisions)} identity collision(s); see "
            "[srd-dup ...] markers in additional_notes."
        )

    # ── Merge canonical info & rulebook ────────────────────────
    canonical_info: Dict[int, dict] = {}
    merged_refs: Dict[int, object] = {}
    for i, report in enumerate(reports):
        remap = remaps[i]
        for old_idx, info in report.canonical_info.items():
            old_lid = f"L{old_idx}"
            new_lid = remap.get(old_lid, old_lid)
            new_idx = int(new_lid[1:]) if new_lid.startswith("L") else old_idx
            if new_idx not in canonical_info:
                canonical_info[new_idx] = info
        if report.rulebook:
            for old_idx, ref in report.rulebook.refs.items():
                old_lid = f"L{old_idx}"
                new_lid = remap.get(old_lid, old_lid)
                new_idx = int(new_lid[1:]) if new_lid.startswith("L") else old_idx
                if new_idx not in merged_refs:
                    new_ref = copy.deepcopy(ref)
                    new_ref.ligand_idx = new_idx
                    merged_refs[new_idx] = new_ref

    # ── Use first report's thermodynamic constants ────────────
    r0 = reports[0]

    # Build merged rulebook
    merged_rulebook = None
    if merged_refs:
        from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.canonical_standard_state_rulebook import CanonicalRuleBook
        merged_rulebook = CanonicalRuleBook(
            refs=merged_refs,
            temperature_K=r0.temperature_K,
            factor=r0.factor,
            notes=all_notes,
        )

    # ── Build merged report ────────────────────────────────────
    merged = FreeEnergyReport(
        temperature_K=r0.temperature_K,
        temperature_C=r0.temperature_C,
        RT=r0.RT,
        factor=r0.factor,
        Kw_log=r0.Kw_log,
        species=unique_species,
        reactions=[],
        canonical_info=canonical_info,
        rulebook=merged_rulebook,
        metal_ids=metal_ids,
        ligand_ids=ligand_ids,
        metal_names=metal_names,
        ligand_names=ligand_names,
        total_metals=total_metals,
        total_ligands=total_ligands,
        ionic_strength=r0.ionic_strength,
        ionic_mode=r0.ionic_mode,
        metal_charges=metal_charges,
        ligand_charges=ligand_charges,
        consistency_ok=all(r.consistency_ok for r in reports),
        inconsistencies=[inc for r in reports for inc in r.inconsistencies],
        component_meta=unified_meta,
        equilibrium_meta=eq_meta,
        excluded_species=[],
        solvents=solvents,
        notes=all_notes,
        valence_groups=valence_groups,
        redox_couples=redox_couples,
        ligand_micro_valences=micro_valences,
    )

    # ── Generate markdown ──────────────────────────────────────
    md_text = generate_free_energy_card_md(merged, system_name=system_name)

    return md_text, merged, srd_srd_collisions
