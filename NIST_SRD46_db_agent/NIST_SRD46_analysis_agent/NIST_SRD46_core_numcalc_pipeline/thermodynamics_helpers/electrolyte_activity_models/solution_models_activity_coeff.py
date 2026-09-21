"""
solution_models_activity_coeff.py â€” Activity-coefficient models.
=================================================================

Separated from the solver so that both the aqueous-only and
aqueous+solid builders can use the same activity calculations
without importing the solver itself.

Public API
----------
- ``davies_log_gamma``       â€” Davies equation for logâ‚â‚€(Î³)
- ``compute_apparent_logK``  â€” activity-corrected logK for one equilibrium
- ``compute_all_apparent_logK`` â€” batch version for a list of equilibria
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from thermodynamics_helpers.speciation_dataclasses import (
    Species, Equilibrium,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Davies equation  (valid for I < ~0.5 M)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def davies_log_gamma(
    charge: int,
    ionic_strength: float,
    A: float = 0.5085,
) -> float:
    """Compute logâ‚â‚€(Î³) for a single ion using the Davies equation.

    Parameters
    ----------
    charge : int
        Formal charge of the ion (0 â†’ Î³ = 1).
    ionic_strength : float
        Molar ionic strength (mol/L).
    A : float
        Debyeâ€“HÃ¼ckel parameter (default 0.5085 at 25 Â°C in water).

    Returns
    -------
    float  â€”  logâ‚â‚€(Î³)
    """
    if charge == 0 or ionic_strength <= 0:
        return 0.0
    sqI = math.sqrt(ionic_strength)
    return -A * charge**2 * (sqI / (1.0 + sqI) - 0.3 * ionic_strength)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Apparent logK (activity-corrected)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def compute_apparent_logK(
    eq: Equilibrium,
    species: Dict[str, Species],
    ionic_strength: float,
    metal_ids: List[str],
    ligand_ids: List[str],
) -> float:
    """Return log K_apparent = log K_thermo âˆ’ Î”log Î³ for one equilibrium.

    Î”log Î³ = log Î³(product) âˆ’ Î£(stoich Ã— log Î³(reactant))

    Reactants are the free metal, free ligand, and Hâº whose
    stoichiometric coefficients are (p, q, r) respectively.
    """
    sp = species.get(eq.species_id)
    if sp is None:
        return eq.log_k

    lg_prod = davies_log_gamma(sp.charge, ionic_strength)

    lg_react = 0.0
    mi = sp.metal_idx
    li = sp.ligand_idx
    n_metals = len(metal_ids)
    n_ligands = len(ligand_ids)

    if eq.p and 0 <= mi < n_metals:
        m_sp = species.get(metal_ids[mi])
        if m_sp:
            lg_react += eq.p * davies_log_gamma(m_sp.charge, ionic_strength)

    if eq.q and 0 <= li < n_ligands:
        l_sp = species.get(ligand_ids[li])
        if l_sp:
            lg_react += eq.q * davies_log_gamma(l_sp.charge, ionic_strength)

    if eq.r:
        lg_react += eq.r * davies_log_gamma(1, ionic_strength)   # Hâº

    return eq.log_k - (lg_prod - lg_react)


def compute_all_apparent_logK(
    equilibria: List[Equilibrium],
    species: Dict[str, Species],
    ionic_strength: float,
    metal_ids: List[str],
    ligand_ids: List[str],
) -> Dict[str, float]:
    """Return {eq.id: apparent_logK} for every equilibrium in the list."""
    return {
        eq.id: compute_apparent_logK(
            eq, species, ionic_strength, metal_ids, ligand_ids,
        )
        for eq in equilibria
    }


def describe_ionic_state(
    conc: Dict[str, float],
    species: Dict[str, Species],
) -> Dict[str, float]:
    """Estimate ionic strength and inert-ion balancing for one solution state.

    Non-aqueous species are excluded. Any remaining net charge is balanced using
    monovalent inert ions, which are then included in the ionic-strength total.
    """
    ionic_term = 0.0
    charge_imbalance = 0.0

    for species_id, amount in conc.items():
        if amount <= 0.0:
            continue
        if species_id == "H+":
            charge = 1
        elif species_id == "OH-":
            charge = -1
        else:
            sp = species.get(species_id)
            if sp is None or sp.phase not in ("aqueous", ""):
                continue
            charge = sp.charge
        charge_imbalance += charge * amount
        ionic_term += amount * (charge ** 2)

    inert_cation_conc = max(-charge_imbalance, 0.0)
    inert_anion_conc = max(charge_imbalance, 0.0)
    ionic_term += inert_cation_conc + inert_anion_conc

    return {
        "ionic_strength": 0.5 * ionic_term,
        "charge_imbalance": charge_imbalance,
        "inert_cation_conc": inert_cation_conc,
        "inert_anion_conc": inert_anion_conc,
    }
