"""
activity_model.py
=================
Davies equation, ionic-strength calculator, and Gibbs-framework
activity-correction helpers for the Pourbaix diagram solver.

All activity-related calculations live here:

* ``davies_log_gamma``       – fundamental Davies equation
* ``compute_ionic_strength``  – I = 0.5 Σ cᵢ zᵢ²
* ``gibbs_per_species_correction``  – per-species logβ correction
* ``dissolution_activity_correction`` – dissolution logK correction
* ``recompute_activity_at_I``        – recompute all apparent arrays at new I
"""

from __future__ import annotations

import math
import numpy as np
from typing import List

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from solver_settings import DAVIES_A


# --------------------------------------------------------------------------
#  Davies equation
# --------------------------------------------------------------------------

def davies_log_gamma(charge: int, ionic_strength: float,
                     A: float = DAVIES_A) -> float:
    """
    Davies equation for the activity coefficient of an ion.

    log₁₀ γ = -A z² [ √I / (1 + √I) - 0.3 I ]

    Parameters
    ----------
    charge : formal charge of the ion
    ionic_strength : I (mol/L)
    A : Debye-Hückel constant (default 0.5085 at 25 °C)

    Returns
    -------
    log₁₀ γ
    """
    if ionic_strength <= 0.0 or charge == 0:
        return 0.0
    sq = math.sqrt(ionic_strength)
    return -A * charge * charge * (sq / (1.0 + sq) - 0.3 * ionic_strength)


def compute_ionic_strength(concentrations: np.ndarray,
                           charges: np.ndarray) -> float:
    """I = 0.5 Σ cᵢ zᵢ²."""
    return 0.5 * float(np.sum(concentrations * charges * charges))


# --------------------------------------------------------------------------
#  Gibbs free energy helpers
# --------------------------------------------------------------------------

def gibbs_per_species_correction(
    species_charge: int,
    p_vec: list,
    q_vec: list,
    r_val: float,
    basis_elem_charges: List[int],
    basis_lig_charges: List[int],
    ionic_strength: float,
) -> float:
    """Per-species Davies activity correction for apparent logβ.

    Returns *correction* such that
        app_logβ = logβ_thermo − correction

    where  correction = logγ(product) − Σ logγ(reactants).

    Sign convention matches the speciation free-energy solver.
    """
    if ionic_strength <= 0.0:
        return 0.0
    lg_prod = davies_log_gamma(species_charge, ionic_strength)
    lg_react = 0.0
    for j, p in enumerate(p_vec):
        if p != 0.0 and j < len(basis_elem_charges):
            lg_react += p * davies_log_gamma(basis_elem_charges[j], ionic_strength)
    for ell, q in enumerate(q_vec):
        if q != 0.0 and ell < len(basis_lig_charges):
            lg_react += q * davies_log_gamma(basis_lig_charges[ell], ionic_strength)
    if r_val != 0.0:
        lg_react += r_val * davies_log_gamma(1, ionic_strength)  # H⁺
    return lg_prod - lg_react


def dissolution_activity_correction(
    p_vec: list,
    q_vec: list,
    r_val: float,
    basis_elem_charges: List[int],
    basis_lig_charges: List[int],
    ionic_strength: float,
) -> float:
    """Activity correction for dissolution log_K_diss_eff.

    For dissolution  Solid → Σ νᵢ · (aq products),
    the apparent dissolution constant includes the product activities:
        log_K_diss_eff_app = log_K_diss_eff_thermo + Σ νᵢ·logγ(product_i)

    This correction is ADDED to log_K_diss_eff.
    """
    if ionic_strength <= 0.0:
        return 0.0
    corr = 0.0
    for j, p in enumerate(p_vec):
        if p != 0.0 and j < len(basis_elem_charges):
            corr += p * davies_log_gamma(basis_elem_charges[j], ionic_strength)
    for ell, q in enumerate(q_vec):
        if q != 0.0 and ell < len(basis_lig_charges):
            corr += q * davies_log_gamma(basis_lig_charges[ell], ionic_strength)
    if r_val != 0.0:
        corr += r_val * davies_log_gamma(1, ionic_strength)  # H⁺
    return corr


# --------------------------------------------------------------------------
#  Gibbs recompute at new ionic strength  (used by auto-I iteration)
# --------------------------------------------------------------------------

def recompute_activity_at_I(built, ionic_strength: float):
    """Recompute apparent logβ and solid-formation logK at *I*.

    ``BuiltSystem`` stores the redox-aligned thermodynamic constants and the
    Davies charge-balance coefficients used to derive their apparent values.
    Recomputing from those arrays avoids both stale card-era ``app_log_beta``
    values and loss of the valence-alignment offset during auto-I iteration.

    Parameters
    ----------
    built : BuiltSystem
    ionic_strength : new ionic strength (mol/L)

    Returns
    -------
    log_beta_app : np.ndarray (N_aq,)
    diss_logK_app : np.ndarray (N_diss,)
    """
    if (isinstance(ionic_strength, bool)
            or not math.isfinite(float(ionic_strength))
            or float(ionic_strength) < 0.0):
        raise ValueError(
            f"ionic strength must be a finite number >= 0, got {ionic_strength!r}")
    I = float(ionic_strength)

    model = getattr(built, "activity_model", "Not defined")
    if model == "debye_huckel":
        raise ValueError(
            "activity_model='debye_huckel' is not implemented; "
            "declare 'ideal' or 'davies'")
    if model not in {"ideal", "davies"}:
        raise ValueError(
            "activity_model is 'Not defined' or unsupported on the built "
            "system; declare 'ideal' or 'davies'")

    log_beta_app = np.asarray(built.log_beta_thermo, dtype=float).copy()
    diss_logK_app = np.asarray(built.log_K_diss_thermo, dtype=float).copy()
    if model == "ideal" or I == 0.0:
        return log_beta_app, diss_logK_app

    aq_delta_z2 = np.asarray(built.aq_activity_delta_z2, dtype=float)
    diss_delta_z2 = np.asarray(built.diss_activity_delta_z2, dtype=float)
    if aq_delta_z2.shape != log_beta_app.shape:
        raise ValueError("aqueous activity-correction arrays are inconsistent")
    if diss_delta_z2.shape != diss_logK_app.shape:
        raise ValueError("dissolution activity-correction arrays are inconsistent")

    # Davies log(gamma_z) is z^2 times the monovalent value.  The stored
    # delta-z^2 coefficient is product minus formation-reactant charge square,
    # so apparent logK = aligned thermodynamic logK - delta(log gamma).
    log_gamma_z1 = davies_log_gamma(1, I)
    log_beta_app -= log_gamma_z1 * aq_delta_z2
    diss_logK_app -= log_gamma_z1 * diss_delta_z2
    return log_beta_app, diss_logK_app
