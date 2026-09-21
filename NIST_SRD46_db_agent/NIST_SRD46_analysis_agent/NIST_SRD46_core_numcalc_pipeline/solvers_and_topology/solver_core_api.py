"""
solver_core_api.py
==================
Data classes shared across the entire speciation / Pourbaix solver pipeline.

All solver-ready containers live here so every downstream module
operates on the same well-defined types.

Renamed from ``pourbaix_core.py`` — generalised to cover pH-only
speciation sweeps, pH x E Pourbaix diagrams, and future multi-axis
sweeps.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


# ---------------------------------------------------------------------------
#  Species description (element-basis)
# ---------------------------------------------------------------------------

@dataclass
class SolverSpecies:
    """One chemical species in the element basis.

    After the system builder processes the raw equilibria through
    redox + Kw substitution, every aqueous species is characterised by:
        log[species] = log_beta_eff
                       + stoich_metals · x_metals + stoich_ligands · x_ligands
                       + stoich_H · log[H+]       + stoich_e · pe
    where x = vector of log[free basis ions].
    """
    id:              str           # "Fe2+", "FeCit-", "Fe(OH)3(s)", ...
    label:           str           # display-friendly label
    phase:           str           # "aqueous" | "dissolution"
    charge:          int           # formal charge
    log_beta_eff:    float         # effective formation constant in element basis
    stoich_metals:   List[int]     # stoich coeffs for each element-basis free ion
    stoich_ligands:  List[int]     # stoich coeffs for each ligand-basis free species
    stoich_H:        int           # net H+ coefficient
    stoich_e:        int           # net e- coefficient
    nu_elements:     List[int]     # atoms of each element in this species
    nu_ligands:      List[int]     # atoms of each ligand in this species
    # For solids, nu_* gives mass-balance footprint per mol precipitated


# ---------------------------------------------------------------------------
#  Dissolution equilibrium (for SI computation)
# ---------------------------------------------------------------------------

@dataclass
class SolverEquilibrium:
    """One dissolution equilibrium in the element basis."""
    id:              str
    solid_species_id: str
    solid_label:     str           # human-readable solid name
    log_K_diss_eff:  float         # dissolution constant in element basis
    stoich_metals:   List[int]     # coefficients for basis free ions
    stoich_ligands:  List[int]     # coefficients for basis ligands
    stoich_H:        int           # H+ coefficient
    stoich_e:        int           # e- coefficient
    nu_elements:     List[int]     # mass-balance contribution per mol solid
    nu_ligands:      List[int]


# ---------------------------------------------------------------------------
#  Point result
# ---------------------------------------------------------------------------

@dataclass
class SolverPointResult:
    """Solution at a single (pH, E) grid point."""
    pH:                 float
    E_V:                float
    pe:                 float
    converged:          bool
    iterations:         int
    residual:           float
    # Aqueous speciation
    x:                  np.ndarray          # log10[free basis species] vector
    log_conc:           Dict[str, float]    # species_id -> log10[conc]
    conc:               Dict[str, float]    # species_id -> conc (mol/L)
    frac_element:       Dict[str, Dict[str, float]]  # element -> {species: fraction}
    frac_ligand:        Dict[str, Dict[str, float]]  # ligand  -> {species: fraction}
    # Solid phase
    active_solid_ids:   List[str]           # solid ids in active set
    solid_amounts:      Dict[str, float]    # solid_id -> n_s (mol/L)
    saturation_indices: Dict[str, float]    # solid_id -> SI
    # Labelling (assigned by labeler later)
    label_aq:           Optional[Dict[str, str]]  = None  # element -> predominant aq species id
    label_solids:       Optional[FrozenSet[str]]  = None  # set of active solid ids
    label:              Optional[Tuple]            = None  # composite label


# ---------------------------------------------------------------------------
#  Grid result
# ---------------------------------------------------------------------------

@dataclass
class SolverGridResult:
    """Full 2D grid of solved points."""
    pH_values:          np.ndarray          # shape (N_pH,)
    E_values:           np.ndarray          # shape (N_E,)
    points:             np.ndarray          # shape (N_E, N_pH) object array of SolverPointResult
    labels:             Optional[np.ndarray] = None  # shape (N_E, N_pH) int (label index)
    label_catalog:      Optional[Dict[int, Tuple]] = None  # label_index -> composite
    converged_mask:     Optional[np.ndarray] = None  # shape (N_E, N_pH) boolean
    # For per-element mode:
    labels_per_element: Optional[Dict[str, np.ndarray]] = None  # element -> (N_E, N_pH) int
    label_catalog_per_element: Optional[Dict[str, Dict[int, str]]] = None
