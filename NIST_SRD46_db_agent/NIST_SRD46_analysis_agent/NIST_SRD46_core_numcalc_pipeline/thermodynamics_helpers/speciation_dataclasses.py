"""
speciation_dataclasses.py — Shared data classes and constants.
==============================================================

Defines the data structures used across the speciation pipeline:
``Species``, ``Equilibrium``, ``PointResult``, ``SpeciationCurve``,
``SpeciesType`` enum, and numerical constants.

Parsers, builders, and solvers live in dedicated modules under
``speciation_io_modules/`` and ``solver_modules/``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ── constants ────────────────────────────────────────────────────
LOG10 = math.log(10)
MIN_LOG = -99.0
MAX_LOG = 5.0
Kw_LOG  = -14.0          # log10(Kw) at 25 °C


# ══════════════════════════════════════════════════════════════════
#  Data classes
# ══════════════════════════════════════════════════════════════════

class SpeciesType(Enum):
    METAL             = "metal"
    LIGAND            = "ligand"
    PROTONATED_LIGAND = "protonated_ligand"
    COMPLEX           = "complex"
    PROTON            = "proton"
    HYDROXIDE         = "hydroxide"


@dataclass
class Species:
    id:      str
    label:   str               # display formula  e.g. "CuL₂"
    stype:   SpeciesType
    charge:  int   = 0
    phase:   str   = "aqueous" # "aqueous", "solid", or "gas"
    metal_idx:  int = 0        # 1-based real-metal index (0 = none / proton)
    ligand_idx: int = 0        # 1-based real-ligand index (0 = none)
    stoich: Dict[str, int] = field(default_factory=dict)  # e.g. {"M1":1, "L2":2, "H":-1}
    stoich_hlx: Optional[List[Tuple[str, int]]] = None  # grouped HxLy stoich, display-only
    mu0_free_kJ:      Optional[float] = None   # μ°_free  (kJ/mol) — set by free-energy solver
    mu0_canonical_kJ:  Optional[float] = None   # μ°_canon (kJ/mol) — set by free-energy solver


@dataclass
class Equilibrium:
    """log K for the formation reaction  Σ n_i·Comp_i  ⇌  Product."""
    id:      str
    label:   str
    log_k:   float
    species_id: str = ""       # product species id
    stoich: Dict[str, int] = field(default_factory=dict)  # e.g. {"M1":1, "L2":2, "H":-1}


@dataclass
class PointResult:
    pH:        float
    conc:      Dict[str, float] = field(default_factory=dict)   # mol/L
    log_conc:  Dict[str, float] = field(default_factory=dict)
    frac_M:    Dict[str, float] = field(default_factory=dict)   # fraction of total metal
    frac_L:    Dict[str, float] = field(default_factory=dict)   # fraction of total ligand
    converged: bool = True
    iters:     int  = 0
    residual:  float = 0.0
    # Multi-component: {component_id: {species_id: fraction}}
    frac_metals:  Dict[str, Dict[str, float]] = field(default_factory=dict)
    frac_ligands: Dict[str, Dict[str, float]] = field(default_factory=dict)
    solid_amounts: Dict[str, float] = field(default_factory=dict)   # mol/L precipitated
    ionic_strength_used: float = 0.0
    calculated_ionic_strength: float = 0.0
    charge_imbalance: float = 0.0
    inert_cation_conc: float = 0.0
    inert_anion_conc: float = 0.0


@dataclass
class SpeciationCurve:
    system_name: str
    pH_values:   List[float]            = field(default_factory=list)
    results:     List[PointResult]      = field(default_factory=list)
    species:     Dict[str, Species]     = field(default_factory=dict)
    equilibria:  List[Equilibrium]      = field(default_factory=list)
    total_M:     float = 0.0
    total_L:     float = 0.0
    temperature: float = 25.0
    ionic_str:   float = 0.0
    ionic_mode:  str = "fixed"
    target_ionic_str: float = 0.0
    # Multi-component fields
    total_metals:  Dict[str, float] = field(default_factory=dict)   # {"M0": 0.001, ...}
    total_ligands: Dict[str, float] = field(default_factory=dict)   # {"L0": 0.01, ...}
    metal_names:   Dict[str, str]   = field(default_factory=dict)   # {"M0": "Fe2+", ...}
    ligand_names:  Dict[str, str]   = field(default_factory=dict)   # {"L0": "glycine", ...}
    # Provenance — what actually entered the solver (optional)
    input_json:    Optional[dict]   = None
    run_params:    Optional[dict]   = None
    # Per-sample physical-input provenance for machine-facing tables.  These
    # values come from the compiled constraints evaluated at the matching
    # sweep coordinate; they are not solver defaults.
    state_provenance: List[Dict[str, Any]] = field(default_factory=list)
    method:        str              = "free_energy"  # "free_energy" or "equilibrium_const"

    # convenience ---
    def series(self, sp_id: str, kind: str = "frac_M") -> List[float]:
        """Return a list of values for *sp_id* across all pH points."""
        out: List[float] = []
        for r in self.results:
            store = getattr(r, kind, r.frac_M)
            out.append(store.get(sp_id, 0.0))
        return out

    def series_multi(self, sp_id: str, component_id: str) -> List[float]:
        """Return fraction values for *sp_id* in a specific metal/ligand balance."""
        out: List[float] = []
        for r in self.results:
            d = r.frac_metals.get(component_id,
                    r.frac_ligands.get(component_id, {}))
            out.append(d.get(sp_id, 0.0))
        return out

    @property
    def is_multi(self) -> bool:
        """True if this is a multi-component system."""
        return bool(self.total_metals)

    def n_converged(self) -> int:
        return sum(1 for r in self.results if r.converged)
