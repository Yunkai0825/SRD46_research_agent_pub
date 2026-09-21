"""
canonical_standard_state_rulebook.py — Canonical chemical potential reference states.
=====================================================================================

Rule book for assigning canonical reference states to each component
in a speciation equilibrium network, and for computing μ° values in
the canonical basis.

Rules
-----
RULE 1 — Metal reference
    Every metal Mᵢ uses the free aquo ion as reference: μ°(Mᵢ) = 0.

RULE 2 — Proton reference
    H⁺ is the universal proton reference: μ°(H⁺) = 0.

RULE 3 — Hydroxide derived reference
    OH⁻ is derived from water self-dissociation:
        μ°(OH⁻) = 2.303 RT × |Kw_LOG|
    This is NOT an independent degree of freedom.

RULE 4 — Ligand canonical reference (HₓL form)
    Each ligand Lⱼ has a canonical protonated form HₓLⱼ declared
    in the input card (``ligand_canonical_HOL.H``).
    * If x = 0: free ligand is the reference, shift = 0.
    * If x > 0: μ° shift = 2.303 RT × logβ(HₓLⱼ), where logβ
      is the cumulative constant for forming HₓLⱼ from H⁺ + Lⱼ.

RULE 5 — Canonical μ° computation
    For any species with stoich {M0: p₀, …, L0: q₀, …, H: r}:
        μ°_free    = −2.303 RT × logβ
        μ°_canon   = μ°_free + Σⱼ qⱼ × 2.303 RT × logβ_can(Lⱼ)
    where the sum runs over all ligand keys present in the stoich.

Missing canonical form → hard error
------------------------------------
If the declared canonical HₓL is not found in the equilibrium map, a
``ValueError`` is raised.  Fallback strategies (EC-1 ladder reconstruction,
EC-2 free-ligand shift=0) are intentionally absent: they silently produce
incorrect μ°_canon values and are therefore considered legacy code that
cheats the algorithm.

To resolve a ``ValueError``:
  a) Add the missing H_x_L formation equilibrium to the input card, or
  b) Set ``ligand_canonical_HOL.H = 0`` in the component declaration when
     you genuinely want the free-ligand reference (shift = 0).

EC-3 — Hyperprotonation beyond canonical
    Species H_{x+n}L (n > 0) may have logβ that violates monotonicity
    beyond the canonical form.  This is expected and NOT an error.

EC-4 — Multi-metal species
    Species containing ≥ 2 distinct metals carry stoich keys for each.
    The canonical shift depends only on the ligand stoichiometry; the
    metal part uses the same μ°(Mᵢ) = 0 rule for each metal.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

R_kJ = 8.314e-3
LN10 = math.log(10)


# ══════════════════════════════════════════════════════════════════
#  Data classes
# ══════════════════════════════════════════════════════════════════

@dataclass
class CanonicalRef:
    """Canonical reference state for one ligand."""
    ligand_idx:     int           # 0-based ligand index
    ligand_name:    str
    canonical_H:    int           # declared proton count (from input card)
    resolved_H:     int           # actually used proton count (always == canonical_H)
    log_beta_HxL:   float         # cumulative logβ for the canonical form
    mu_shift_kJ:    float         # 2.303 RT × logβ_HxL  (kJ/mol)
    strategy:       str           # "exact" (only valid strategy; others raise ValueError)
    vlm_id:         str = ""      # NIST SRD-46 VLM record that provided log_beta_HxL
    warning:        Optional[str] = None


@dataclass
class CanonicalRuleBook:
    """Resolved canonical references for every ligand in the system."""
    refs:           Dict[int, CanonicalRef]   # lig_idx → CanonicalRef
    temperature_K:  float
    factor:         float                     # 2.303 RT  (kJ/mol)
    notes:          List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
#  Builder
# ══════════════════════════════════════════════════════════════════

def build_canonical_references(
    *,
    canonical_H_map: Dict[str, int],
    ligand_name_to_idx: Dict[str, int],
    parsed_species: dict,
    parsed_equilibria: list,
    temperature_K: float = 298.15,
    species_vlm_map: Dict[str, str] = None,
) -> CanonicalRuleBook:
    """Determine canonical reference states for every ligand.

    Parameters
    ----------
    canonical_H_map : {ligand_name: declared_H_count}
        From the input card ``ligand_canonical_HOL.H``.
    ligand_name_to_idx : {ligand_name: 0-based index}
    parsed_species : dict of Species objects (from parser)
    parsed_equilibria : list of Equilibrium objects (from parser)
    temperature_K : reference temperature in Kelvin
    species_vlm_map : {raw_species_id: vlm_id} — maps parser species IDs to
        their NIST SRD-46 VLM record IDs for provenance tracking.

    Returns
    -------
    CanonicalRuleBook
        Each ligand's ``CanonicalRef`` records:
        - ``strategy="exact"``  — declared canonical HₓL found (RULE 4b).
        - ``vlm_id``            — VLM record that provided the logβ, or "".

    Raises
    ------
    ValueError
        If the declared canonical H_x_L is not found in the equilibrium map.
        No fallback strategies are implemented; the error message tells the
        user exactly how to fix the input card.
    """
    if species_vlm_map is None:
        species_vlm_map = {}

    fac = LN10 * R_kJ * temperature_K
    refs: Dict[int, CanonicalRef] = {}
    notes: List[str] = []

    # Build species-level logβ lookup
    log_beta: Dict[str, float] = {}
    for eq in parsed_equilibria:
        log_beta[eq.species_id] = eq.log_k
    for sp_id in parsed_species:
        log_beta.setdefault(sp_id, 0.0)

    for lig_name, canon_H in canonical_H_map.items():
        lig_idx = ligand_name_to_idx.get(lig_name)
        if lig_idx is None:
            continue

        # RULE 4a: canonical_H = 0 → free ligand reference (shift = 0, no VLM needed)
        if canon_H == 0:
            refs[lig_idx] = CanonicalRef(
                ligand_idx=lig_idx,
                ligand_name=lig_name,
                canonical_H=0,
                resolved_H=0,
                log_beta_HxL=0.0,
                mu_shift_kJ=0.0,
                strategy="exact",
                vlm_id="",
            )
            continue

        # RULE 4b: Find HₓL in the equilibrium map.
        # Collect ALL pure protonation states for this ligand,
        # tracking sp_id so we can retrieve the VLM provenance.
        protonation_ladder: Dict[int, Tuple[float, str]] = {}  # h_count → (logβ, sp_id)
        lig_key = f"L{lig_idx}"
        for sp_id, sp in parsed_species.items():
            # Pure protonation: only Lⱼ and H, no metals
            has_metal = any(
                k != "H" and not k.startswith("L") and sp.stoich.get(k, 0) != 0
                for k in sp.stoich
            )
            q_val = sp.stoich.get(lig_key, 0)
            h_count = sp.stoich.get("H", 0)
            lig_match = (q_val == 1 and not has_metal and h_count > 0)
            if not lig_match:
                continue
            # Also confirm the species has the right ligand idx
            if sp.stoich:
                if sp.stoich.get(lig_key, 0) != 1:
                    continue
                # Check no other ligand keys
                other_lig = any(
                    k.startswith("L") and k != lig_key and sp.stoich.get(k, 0) != 0
                    for k in sp.stoich
                )
                if other_lig:
                    continue
            lb = log_beta.get(sp_id, 0.0)
            protonation_ladder[h_count] = (lb, sp_id)

        # Priority 1 — Exact match of declared canonical HₓL (RULE 4b)
        if canon_H in protonation_ladder:
            lb, canonical_sp_id = protonation_ladder[canon_H]
            vlm_id = species_vlm_map.get(canonical_sp_id, "")
            refs[lig_idx] = CanonicalRef(
                ligand_idx=lig_idx,
                ligand_name=lig_name,
                canonical_H=canon_H,
                resolved_H=canon_H,
                log_beta_HxL=lb,
                mu_shift_kJ=fac * lb,
                strategy="exact",
                vlm_id=vlm_id,
            )
            continue

        # No approximate reference substitution is chemically valid.  The
        # former EC-1/EC-2 branches were invoked when prerequisite
        # protonation rows were absent from a per-pair card or were skipped
        # by the old source-order parser.  Substituting the highest available
        # state (for example HL for declared H3L citrate) changes the energy
        # zero and makes species from different cards incomparable.
        available = ", ".join(
            f"H{h}L(logβ={value[0]:.6g})"
            for h, value in sorted(protonation_ladder.items())
        ) or "none"
        raise ValueError(
            f"Canonical H{canon_H}L reference for {lig_name!r} is missing; "
            f"available protonation states: {available}. The exact "
            "protonation equilibrium must be present and resolvable in the "
            "system card; canonical HxL-to-HyL fallback is forbidden."
        )

    return CanonicalRuleBook(
        refs=refs,
        temperature_K=temperature_K,
        factor=fac,
        notes=notes,
    )


# ══════════════════════════════════════════════════════════════════
#  Canonical μ° computation
# ══════════════════════════════════════════════════════════════════

def compute_canonical_mu(
    mu0_free: float,
    stoich: Dict[str, int],
    rulebook: CanonicalRuleBook,
) -> float:
    """Compute μ°_canon from μ°_free using the rule book.

    RULE 5:
        μ°_canon = μ°_free + Σⱼ qⱼ × shift(Lⱼ)
    where shift(Lⱼ) = 2.303 RT × logβ_can(Lⱼ).
    """
    shift = 0.0
    for key, count in stoich.items():
        if key.startswith("L"):
            lig_idx = int(key[1:])
            ref = rulebook.refs.get(lig_idx)
            if ref is not None:
                shift += count * ref.mu_shift_kJ
    return mu0_free + shift


def check_protonation_consistency(
    parsed_species: dict,
    parsed_equilibria: list,
    rulebook: CanonicalRuleBook,
) -> Tuple[List[str], List[str]]:
    """Check protonation ladder consistency for each ligand.

    Returns
    -------
    (inconsistencies, notes)
        inconsistencies: violations within the canonical range
        notes: expected hyperprotonation beyond canonical
    """
    log_beta: Dict[str, float] = {}
    for eq in parsed_equilibria:
        log_beta[eq.species_id] = eq.log_k

    inconsistencies: List[str] = []
    extra_notes: List[str] = []

    for lig_idx, ref in rulebook.refs.items():
        if ref.canonical_H < 2:
            continue
        lig_key = f"L{lig_idx}"
        ladder = []
        for sp_id, sp in parsed_species.items():
            has_metal = any(
                k.startswith("M") and sp.stoich.get(k, 0) != 0
                for k in sp.stoich
            )
            q_val = sp.stoich.get(lig_key, 0)
            h_count = sp.stoich.get("H", 0)
            if not has_metal and q_val == 1 and h_count > 0:
                lb = log_beta.get(sp_id, 0.0)
                ladder.append((h_count, lb))
        ladder.sort()
        for i in range(1, len(ladder)):
            if ladder[i][1] <= ladder[i - 1][1]:
                if ladder[i][0] <= ref.canonical_H:
                    # EC-3 does NOT apply — real violation
                    inconsistencies.append(
                        f"Protonation ladder violation for {ref.ligand_name}: "
                        f"logβ(H{ladder[i][0]}L)={ladder[i][1]:.3f} "
                        f"<= logβ(H{ladder[i - 1][0]}L)={ladder[i - 1][1]:.3f}"
                    )
                else:
                    # EC-3: hyperprotonation — expected
                    extra_notes.append(
                        f"Hyperprotonation beyond canonical for "
                        f"{ref.ligand_name}: logβ(H{ladder[i][0]}L)="
                        f"{ladder[i][1]:.3f} < logβ(H{ladder[i - 1][0]}L)="
                        f"{ladder[i - 1][1]:.3f} (expected)"
                    )

    return inconsistencies, extra_notes
