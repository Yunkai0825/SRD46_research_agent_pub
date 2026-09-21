"""
free_energy_network_calc_helper.py â€” Standard chemical potentials from equilibrium networks.
============================================================================================

Computes per-species standard chemical potentials (Î¼Â°) and per-reaction
standard Gibbs free energies (Î”GÂ°) from the logK network in a speciation
JSON input file.

Stoichiometry model
-------------------
Each species carries a **stoich** dictionary mapping component keys to
integer stoichiometric coefficients:

    {"M1": p1, "M2": p2, ..., "L1": q1, "L2": q2, ..., "H": r}

- ``M0`` â€” always Hâº (pH-controlled, not mass-balanced)
- ``L0`` â€” always OHâ» (derived from Kw, not mass-balanced)
- ``Mi`` â€” real metal *i* (1-indexed, matching ``parsed.metal_ids``)
- ``Lj`` â€” real ligand *j* (1-indexed, matching ``parsed.ligand_ids``)
- ``H``  â€” net proton count (negative â†’ hydroxide contribution)

This replaces the old (p, q, r, metal_idx, ligand_idx) tuple and
generalises to multi-metal or multi-ligand species.

Reference states
----------------
- **Metals** (including Hâº): free aquo ion â†’ Î¼Â° = 0
- **Ligands**: canonical protonated form Hâ‚“L â†’ Î¼Â° = 0
- **OHâ»**: derived from water self-dissociation (Kw)

Solid / dissolution species
---------------------------
Species with ``phase == "dissolution"`` are included in the report.
Their chemical potentials are computed identically (Î¼Â° = âˆ’2.303 RT logÎ²).
The Gibbs minimiser uses their saturation index and mass-balance
contribution when precipitation occurs.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.canonical_standard_state_rulebook import (
    CanonicalRuleBook,
    build_canonical_references,
    compute_canonical_mu,
    check_protonation_consistency,
)

# â”€â”€ physical constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
R_kJ = 8.314e-3               # kJ molâ»Â¹ Kâ»Â¹
LN10 = math.log(10)           # 2.302585â€¦


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Data classes
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@dataclass
class SpeciesEnergy:
    """Standard chemical potential for one species.

    ``stoich`` maps component keys to stoichiometric coefficients:
        {"M0": 2, "L1": 1, "H": -1}  â†’  Mâ‚€Â²Lâ‚(OH)

    ``species_id`` is a component-based ID generated from stoich,
    e.g. ``M0.L0(2)`` for Cu(glyc)â‚‚.  The original parser ID is
    kept in ``original_id`` for cross-referencing.
    """
    species_id:    str                  # component-based ID (M0.L0(2), etc.)
    original_id:   str                  # parser species_id for traceability
    label:         str
    stoich:        Dict[str, int]       # component_key â†’ count
    charge:        int
    phase:         str                  # "aqueous" or "dissolution"
    log_beta:      float                # cumulative formation constant (thermodynamic)
    app_log_beta:  float                # apparent logÎ² (activity-corrected)
    mu0_free:      float                # Î¼Â° kJ/mol  (free-component ref)
    mu0_canonical: float                # Î¼Â° kJ/mol  (canonical Hâ‚“L ref)
    mu_aligned:    float = 0.0          # Î¼Â° kJ/mol  (valence-aligned: ref-metal + canonical-ligand)
    stoich_hlx:    Optional[List[Tuple[str, int]]] = None  # grouped HxLy stoich, display-only
    include:       bool = True           # included in calculation?
    additional_notes: str = ""           # user annotations
    vlm_id:        str = ""              # NIST SRD-46 VLM record that provided log_beta


@dataclass
class ReactionEnergy:
    """Standard Gibbs free energy for one cumulative formation reaction."""
    eq_id:        str
    label:        str
    species_id:   str                   # component-based ID
    original_sp_id: str                 # parser species_id
    log_beta:     float
    delta_G0:     float                 # Î”GÂ° = âˆ’2.303 RT logÎ²  (kJ/mol)
    delta_G0_can: float                 # Î”GÂ° in canonical ref   (kJ/mol)
    include:      bool = True            # included in calculation?
    additional_notes: str = ""          # user annotations


@dataclass
class ComponentMeta:
    """Metadata for one component (metal or ligand)."""
    internal_id:   str           # M0, L0, â€¦
    name:          str           # Cu2+, glycine, â€¦
    comp_type:     str           # "metal" or "ligand"
    charge:        int
    total:         float | str   # numeric or literal "Not defined"
    db_source:     str           # e.g. "NIST SRD-46"
    db_id:         str           # e.g. "metal_68", "ligand_9058"
    smiles:        str = ""
    inchi:         str = ""
    canonical_HOL: Optional[Dict[str, int]] = None   # {H, O, L}


@dataclass
class EquilibriumMeta:
    """Metadata for one raw equilibrium from the input card."""
    equation_str:     str
    log_K:            float
    constant_type:    str
    T_source_C:       float
    I_source_M:       float
    db_source:        str        # "NIST SRD-46"
    db_id:            str        # "vlm_173034"
    include:          bool
    metal_system:     List[str]  # ["Cu2+"]
    ligand_system:    List[str]  # ["glycine"]
    additional_notes: str = ""   # optional notes from card builder
    rhs_species_raw: str = ""    # raw parser species ID on the RHS (links to SpeciesEnergy.original_id)
    ref_eq_net_ids: List[int] = field(default_factory=list)  # SRD-46 network IDs for this block


@dataclass
class SolventMeta:
    """Metadata for one solvent (e.g. water).

    For future multi-solvent support (S0=Water, S1=DMF, â€¦).
    Each solvent may declare self-dissociation equilibrium.
    """
    internal_id:           str = "S0"
    name:                  str = "Water"
    formula:               str = "H2O"
    db_id:                 str = "solvent_1"
    self_dissociation:     bool = True
    dissociation_species:  List[str] = field(default_factory=lambda: ["M0", "L0"])
    dissociation_reaction: str = "H2O ⇌ H⁺ + OH⁻"
    pK:                    float = 14.0
    K_log10:               float = -14.0


@dataclass
class ValenceGroupEntry:
    """One metal species in a valence-alignment group."""
    internal_id: str          # M1, M2
    name:        str          # Fe2+, Fe3+
    charge:      int          # +2, +3
    is_reference: bool        # True â†’ Î¼Â° â‰¡ 0 for this oxidation state


@dataclass
class ValenceGroup:
    """Same-element metals grouped by oxidation state.

    The reference entry is the one whose charge is closest to 0
    (prefer +1 over âˆ’1, then +2 over âˆ’2, â€¦).  The Pourbaix builder
    uses this table to set up the basis/derived-redox map.
    """
    element:      str                       # "Fe"
    entries:      List[ValenceGroupEntry]    # all metal IDs for this element
    reference_id: str                       # internal_id of the reference state
    n_valences:   int                       # len(entries)


@dataclass
class RedoxCouple:
    """Half-reaction linking two oxidation states of the same element.

    Convention:  oxidised + n eâ»  â‡Œ  reduced,  logK = nÂ·EÂ°/(2.303RT/F).
    """
    couple_id:      str        # e.g. "Fe3+/Fe2+"
    element:        str        # "Fe"
    oxidized_id:    str        # "M2"  (higher charge)
    oxidized_name:  str        # "Fe3+"
    reduced_id:     str        # "M1"  (lower charge)
    reduced_name:   str        # "Fe2+"
    n_electrons:    int        # 1
    E0_V_SHE:      float       # standard reduction potential vs SHE
    logK:           float       # equilibrium constant for the half-reaction
    delta_G0_kJ:   float       # Î”GÂ° = âˆ’2.303RT Ã— logK  (kJ/mol)
    half_reaction:  str        # "Fe3+ + eâ» â†’ Fe2+"
    source:         str = ""   # data provenance


@dataclass
class LigandMicroValence:
    """Per-atom oxidation-state summary for one organic ligand.

    Computed from SMILES via electronegativity-based assignment (RDKit).
    Only atoms whose oxidation state may change in redox reactions
    (C, N, S, P, â€¦) are considered "dynamic".
    """
    ligand_id:      str                  # "L1"
    ligand_name:    str                  # "citrate"
    smiles:         str                  # input SMILES
    atom_os_summary: Dict[str, List[int]]  # element â†’ list of OS per atom
    # e.g. {"C": [+3, +3, 0, +1, 0, +3], "O": [-2, -2, -2, -2, -2, -2, -2]}
    dynamic_atoms:  List[str]             # atoms with >1 distinct OS in the mol


@dataclass
class FreeEnergyReport:
    """Complete free-energy analysis of an equilibrium network."""
    temperature_K:   float
    temperature_C:   float
    RT:              float              # RÂ·T   (kJ/mol)
    factor:          float              # 2.303Â·RÂ·T  (kJ/mol)
    Kw_log:          float
    species:         List[SpeciesEnergy]
    reactions:       List[ReactionEnergy]
    canonical_info:  Dict[int, dict]    # lig_idx â†’ {name, canonical_H, log_beta_HxL}
    rulebook:        Optional[CanonicalRuleBook]   # full rule book object
    metal_ids:       List[str]          # ["M1", "M2", ...]  (M0=H+ reserved)
    ligand_ids:      List[str]          # ["L1", "L2", ...]  (L0=OH- reserved)
    metal_names:     List[str]          # ["Cu2+", "Fe2+", ...]
    ligand_names:    List[str]          # ["glycine", "citrate", ...]
    total_metals:    Dict[str, float | str]  # calculation card must define
    total_ligands:   Dict[str, float | str]  # calculation card must define
    ionic_strength:  float | str        # mol/L or undeclared-card sentinel
    ionic_mode:      str = "Not defined"  # calc card must declare fixed/auto/none
    metal_charges:   Dict[str, int] = field(default_factory=dict)   # M0 â†’ charge
    ligand_charges:  Dict[str, int] = field(default_factory=dict)  # L0 â†’ charge
    consistency_ok:  bool = True
    inconsistencies: List[str] = field(default_factory=list)
    component_meta:  List[ComponentMeta] = field(default_factory=list)
    equilibrium_meta: List[EquilibriumMeta] = field(default_factory=list)
    excluded_species: List[str] = field(default_factory=list)
    solvents:        List['SolventMeta'] = field(default_factory=list)
    notes:           List[str] = field(default_factory=list)
    valence_groups:  List['ValenceGroup'] = field(default_factory=list)
    redox_couples:   List['RedoxCouple'] = field(default_factory=list)
    valence_offsets: Dict[str, float] = field(default_factory=dict)
    ligand_micro_valences: List['LigandMicroValence'] = field(default_factory=list)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Helpers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _build_stoich(sp) -> Dict[str, int]:
    """Return a copy of the species stoichiometry dict.

    The parser populates ``sp.stoich`` with the complete component-key â†’
    coefficient mapping (e.g. ``{"M1": 1, "L2": 2, "H": -1}``).
    We return a copy so callers can modify it safely.
    """
    return dict(sp.stoich)


def _stoich_str(stoich: Dict[str, int]) -> str:
    """Compact display string for a stoich dict, e.g. 'Cu$+2:+1 L1:+1 H:-1'."""
    if not stoich:
        return "â€”"
    parts = []
    for k in sorted(stoich, key=lambda k: (2 if k == "H" else 1 if k.startswith("L") else 0, k)):
        parts.append(f"{k}:{stoich[k]:+d}")
    return " ".join(parts)


def _make_comp_id(
    stoich: Dict[str, int],
    charge: int,
    phase: str = "aqueous",
    stoich_hlx: Optional[List[Tuple[str, int]]] = None,
) -> str:
    """Generate a component-based species ID from stoichiometry.

    When *stoich_hlx* is provided, the ID preserves HxLy grouped
    sub-units (e.g. ``Cu$+2(2).H-1L2.L2.z+0``).  Otherwise the flat
    *stoich* dict is used.

    Convention
    ----------
    - Components in order: metals â†’ ligands â†’ H/OH, dot-separated.
    - Count shown in parentheses when > 1:  ``M0(2)``, ``L1(3)``.
    - Negative H rendered as OH:  ``OH``, ``OH2``, ``OH3``, â€¦
    - Charge appended as ``.z{sign}{n}``:  ``.z+2``, ``.z-1``, ``.z0``.
    - Dissolution species: ``(s)`` suffix (before collision bracket).
    - Collisions: ``[1]``, ``[2]`` suffix (logÎ² descending).
    """
    if stoich_hlx:
        return _make_comp_id_from_hlx(stoich_hlx, charge, phase)
    if not stoich:
        return "(empty)"
    parts: List[str] = []
    # Metal keys: anything that isn't "H" and doesn't start with "L"
    metal_keys = sorted(k for k in stoich if k != "H" and not k.startswith("L"))
    for key in metal_keys:
        c = stoich[key]
        parts.append(key if c == 1 else f"{key}({c})")
    # Ligand keys
    ligand_keys = sorted(k for k in stoich if k.startswith("L"))
    for key in ligand_keys:
        c = stoich[key]
        parts.append(key if c == 1 else f"{key}({c})")
    h = stoich.get("H", 0)
    if h > 0:
        parts.append("H" if h == 1 else f"H{h}")
    elif h < 0:
        oh = -h
        parts.append("OH" if oh == 1 else f"OH{oh}")
    base = ".".join(parts)
    # Charge
    base += f".z{charge:+d}"
    if phase == "dissolution":
        base += "(s)"
    return base


def _make_comp_id_from_hlx(
    stoich_hlx: List[Tuple[str, int]], charge: int, phase: str,
) -> str:
    """Build species ID from HxLy grouped stoichiometry."""
    parts: List[str] = []
    for key, count in stoich_hlx:
        if key in ("OH", "H"):
            parts.append(key if count == 1 else f"{key}{count}")
        elif count == 1:
            parts.append(key)
        else:
            parts.append(f"{key}({count})")
    base = ".".join(parts)
    base += f".z{charge:+d}"
    if phase == "dissolution":
        base += "(s)"
    return base


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Main computation
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def compute_free_energy_network(
    source: Union[str, Path, dict],
    *,
    temperature_K: Optional[float] = None,
) -> FreeEnergyReport:
    """Compute standard chemical potentials for every species in a network.

    Parameters
    ----------
    source : path to a speciation JSON file, or the parsed dict itself.
    temperature_K : override the reference temperature (Kelvin).

    Returns
    -------
    FreeEnergyReport
    """
    # â”€â”€ 1. Load raw JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if isinstance(source, dict):
        raw = source
    else:
        source = Path(source)
        with open(source, encoding="utf-8") as fh:
            raw = json.load(fh)

    # â”€â”€ 2. Parse with the existing parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    import sys
    _proj = str(Path(__file__).resolve().parents[2])
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    _calc_pipeline = str(
        Path(__file__).resolve().parents[3]
        / "NIST_SRD46_calc_input_building_agentic_pipeline"
    )
    # The LC2 helper package lives beyond the traditional 260-character
    # Windows path limit in this repository.  Importlib can traverse it when
    # its search root uses the extended-length prefix, just as the card I/O
    # helpers do for session artefacts.  Keep non-Windows import semantics
    # unchanged.
    if sys.platform == "win32" and not _calc_pipeline.startswith("\\\\?\\"):
        if _calc_pipeline.startswith("\\\\"):
            _calc_pipeline = "\\\\?\\UNC\\" + _calc_pipeline[2:]
        else:
            _calc_pipeline = "\\\\?\\" + _calc_pipeline
    if _calc_pipeline not in sys.path:
        sys.path.insert(0, _calc_pipeline)
    from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.json_cards_builder_helpers.speciation_json_input_parser import (
        parse_speciation_json,
    )
    from thermodynamics_helpers.speciation_dataclasses import Kw_LOG
    from thermodynamics_helpers.electrolyte_activity_models.solution_models_activity_coeff import (
        davies_log_gamma,
    )

    parsed = parse_speciation_json(raw)

    # â”€â”€ 2b. VLM-ID map: parser sp_id â†’ VLM record ID â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # The parser populates vlm_map while processing each equilibrium,
    # keyed on its own internal sp_id (e.g. "M1_L1_p1q1H2") which
    # matches what compute_free_energy_network uses for all lookups.
    # (The previous approach keyed on the raw JSON RHS token, which
    #  never matched the parser sp_id and always returned "".)
    _species_to_vlm: Dict[str, str] = parsed.vlm_map

    # â”€â”€ 3. Canonical-HOL metadata from the raw JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    canonical_H_map: Dict[str, int] = {}        # ligand_name â†’ H count
    ligand_name_to_idx: Dict[str, int] = {}
    for comp_name, comp in raw["components"].items():
        if comp.get("type") == "ligand" and "ligand_canonical_HOL" in comp:
            canonical_H_map[comp_name] = comp["ligand_canonical_HOL"]["H"]
    # ligand_name_to_idx must use the same numeric index as stoich keys
    # (L1, L2, â€¦) so the canonical rulebook matches correctly.
    _lig_names = parsed.ligand_names
    if isinstance(_lig_names, dict):
        for tag in parsed.ligand_ids:
            ligand_name_to_idx[_lig_names[tag]] = int(tag[1:])
    else:
        for li, tag in enumerate(parsed.ligand_ids):
            ligand_name_to_idx[_lig_names[li]] = int(tag[1:])

    # â”€â”€ 4. Reference temperature â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    temps: List[float] = []
    eq_sections = raw.get("equations", {})
    for sec_key in ("metal_ligand_system_aqueous_only",
                     "metal_ligand_system_dissociation_only"):
        for block in eq_sections.get(sec_key, []):
            for eq_entry in block.get("equilibria", []):
                if eq_entry.get("include_calculation", True):
                    temps.append(eq_entry.get("data_source_temperature", 25.0))

    if temperature_K is not None:
        T = temperature_K
    elif temps:
        mode_C = Counter(temps).most_common(1)[0][0]
        T = mode_C + 273.15
    else:
        T = 298.15

    T_C = T - 273.15
    RT  = R_kJ * T
    fac = LN10 * RT              # 2.303 R T

    notes: List[str] = []
    notes.append(f"Reference temperature: {T_C:.1f} Â°C  ({T:.2f} K)")
    unique_temps = sorted(set(temps))
    if len(unique_temps) > 1:
        notes.append(f"Network temperatures: {unique_temps} Â°C")
        notes.append(f"Selected mode: {T_C:.1f} Â°C")

    # â”€â”€ 5. species_id â†’ cumulative logÎ² â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    log_beta: Dict[str, float] = {}
    for eq in parsed.equilibria:
        log_beta[eq.species_id] = eq.log_k
    for sp_id in parsed.species:
        log_beta.setdefault(sp_id, 0.0)

    # â”€â”€ 6. Build canonical rule book â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    rulebook = build_canonical_references(
        canonical_H_map=canonical_H_map,
        ligand_name_to_idx=ligand_name_to_idx,
        parsed_species=parsed.species,
        parsed_equilibria=parsed.equilibria,
        temperature_K=T,
        species_vlm_map=_species_to_vlm,
    )
    notes.extend(rulebook.notes)

    # Legacy-compatible canonical_info dict (for backward compat)
    canonical_info: Dict[int, dict] = {}
    for lig_idx, ref in rulebook.refs.items():
        canonical_info[lig_idx] = dict(
            name=ref.ligand_name,
            canonical_H=ref.resolved_H,
            log_beta_HxL=ref.log_beta_HxL,
            strategy=ref.strategy,
        )

    # â”€â”€ 7. Î¼Â° for every species (using M_i / L_j stoich) â”€â”€â”€â”€â”€â”€â”€â”€
    io_str = parsed.ionic_strength
    _metal_charges: Dict[str, int] = {}
    _ligand_charges: Dict[str, int] = {}
    for mid in parsed.metal_ids:
        _sp = parsed.species.get(mid)
        _metal_charges[mid] = _sp.charge if _sp else 0
    for lid in parsed.ligand_ids:
        _sp = parsed.species.get(lid)
        _ligand_charges[lid] = _sp.charge if _sp else 0

    species_energies: List[SpeciesEnergy] = []
    for sp_id, sp in parsed.species.items():
        lb = log_beta.get(sp_id, 0.0)
        mu0_f = -fac * lb

        stoich = _build_stoich(sp)

        # Activity correction (Davies equation)
        lg_prod = davies_log_gamma(sp.charge, io_str)
        lg_react = 0.0
        for key, count in stoich.items():
            if key == "H":
                lg_react += count * davies_log_gamma(1, io_str)
            elif key.startswith("L"):
                lg_react += count * davies_log_gamma(
                    _ligand_charges.get(key, 0), io_str)
            else:  # metal key (M1, Cu$+2, etc.)
                lg_react += count * davies_log_gamma(
                    _metal_charges.get(key, 0), io_str)
        app_lb = lb - (lg_prod - lg_react)

        # Canonical shift via rule book (RULE 5)
        mu0_c = compute_canonical_mu(mu0_f, stoich, rulebook)

        species_energies.append(SpeciesEnergy(
            species_id=sp_id,       # placeholder â€” overwritten below
            original_id=sp_id,
            label=sp.label,
            stoich=stoich,
            charge=sp.charge,
            phase=sp.phase,
            log_beta=lb,
            app_log_beta=app_lb,
            mu0_free=mu0_f,
            mu0_canonical=mu0_c,
            mu_aligned=mu0_c,   # no valence alignment in single-network path
            stoich_hlx=sp.stoich_hlx,
            vlm_id=_species_to_vlm.get(sp_id, ""),
        ))

    # â”€â”€ 8. Reaction energies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    reactions: List[ReactionEnergy] = []
    for eq in parsed.equilibria:
        sp = parsed.species.get(eq.species_id)
        sp_stoich = _build_stoich(sp) if sp else {}
        shift = 0.0
        for key, count in sp_stoich.items():
            if key.startswith("L"):
                lig_idx = int(key[1:])
                ref = rulebook.refs.get(lig_idx)
                if ref is not None:
                    shift += count * ref.mu_shift_kJ
        reactions.append(ReactionEnergy(
            eq_id=eq.id,
            label=eq.label,
            species_id=eq.species_id,   # placeholder â€” overwritten below
            original_sp_id=eq.species_id,
            log_beta=eq.log_k,
            delta_G0=-fac * eq.log_k,
            delta_G0_can=-fac * eq.log_k + shift,
        ))

    # â”€â”€ 8b. Generate component-based IDs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _base_ids: Dict[str, List[str]] = {}
    for se in species_energies:
        base = _make_comp_id(se.stoich, se.charge, se.phase, stoich_hlx=se.stoich_hlx)
        _base_ids.setdefault(base, []).append(se.original_id)

    _sp_lookup = {se.original_id: se for se in species_energies}
    _id_map: Dict[str, str] = {}
    for base, orig_ids in _base_ids.items():
        if len(orig_ids) == 1:
            _id_map[orig_ids[0]] = base
        else:
            ranked = sorted(orig_ids, key=lambda oid: -_sp_lookup[oid].log_beta)
            for rank, oid in enumerate(ranked, 1):
                _id_map[oid] = f"{base}[{rank}]"

    for se in species_energies:
        se.species_id = _id_map[se.original_id]
    for rx in reactions:
        rx.species_id = _id_map.get(rx.original_sp_id, rx.original_sp_id)

    # â”€â”€ 9. Consistency checks (via rule book) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    inconsistencies, extra_notes = check_protonation_consistency(
        parsed.species, parsed.equilibria, rulebook,
    )
    notes.extend(extra_notes)

    mu_OH = fac * (-Kw_LOG)
    notes.append(f"OHâ» derived Î¼Â° from Kw (={Kw_LOG}): {mu_OH:+.2f} kJ/mol")

    consistency_ok = len(inconsistencies) == 0

    # â”€â”€ 10. Extract metadata from raw JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    component_meta = _extract_component_meta(raw, parsed)
    equilibrium_meta = _extract_equilibrium_meta(raw)

    # â”€â”€ 10b. Detect valence groups (same-element, different charge) â”€â”€
    valence_groups = _detect_valence_groups(component_meta)

    # â”€â”€ 10c. Build redox couples from input JSON (if present) â”€â”€â”€â”€
    redox_couples = _extract_redox_couples(raw, component_meta, fac)

    # â”€â”€ 10d. Ligand micro-valence via RDKit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ligand_micro_valences = _compute_ligand_micro_valences(component_meta)

    _mn = parsed.metal_names
    _ln = parsed.ligand_names

    report = FreeEnergyReport(
        temperature_K=T,
        temperature_C=T_C,
        RT=RT,
        factor=fac,
        Kw_log=Kw_LOG,
        species=species_energies,
        reactions=reactions,
        canonical_info=canonical_info,
        rulebook=rulebook,
        metal_ids=list(parsed.metal_ids),
        ligand_ids=list(parsed.ligand_ids),
        metal_names=([_mn[t] for t in parsed.metal_ids]
                     if isinstance(_mn, dict) else list(_mn)),
        ligand_names=([_ln[t] for t in parsed.ligand_ids]
                      if isinstance(_ln, dict) else list(_ln)),
        total_metals=dict(parsed.total_metals),
        total_ligands=dict(parsed.total_ligands),
        ionic_strength=io_str,
        ionic_mode=parsed.ionic_mode,
        metal_charges=dict(_metal_charges),
        ligand_charges=dict(_ligand_charges),
        consistency_ok=consistency_ok,
        inconsistencies=inconsistencies,
        component_meta=component_meta,
        equilibrium_meta=equilibrium_meta,
        solvents=[SolventMeta(
            internal_id="S0",
            name="Water",
            formula="H2O",
            db_id="solvent_1",
            self_dissociation=True,
            dissociation_species=["M0", "L0"],
            dissociation_reaction="H2O ⇌ H⁺ + OH⁻",
            pK=-Kw_LOG,
            K_log10=Kw_LOG,
        )],
        notes=notes,
        valence_groups=valence_groups,
        redox_couples=redox_couples,
        ligand_micro_valences=ligand_micro_valences,
    )

    # â”€â”€ 11. Remap M1/M2 metal IDs to Element$+charge format â”€â”€â”€â”€â”€
    _remap_to_element_ids(report)

    return report


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Remap M-indexed metal IDs to Element$+charge format
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _remap_to_element_ids(report: FreeEnergyReport) -> None:
    """Remap generic M1/M2 metal IDs to Element$+charge format in-place.

    Transforms the report so that all metal references use self-describing
    IDs like ``Cu$+2``, ``Zn$+2`` instead of ``M1``, ``M2``.
    The ``original_id`` fields on species and reactions are preserved
    to maintain traceability back to the parser output.
    """
    # Build mapping from M1 â†’ Cu$+2 etc. (M0 = H+ is never remapped)
    id_map: Dict[str, str] = {}
    for cm in report.component_meta:
        if cm.comp_type != "metal" or cm.internal_id == "M0":
            continue
        elem = _element_from_name(cm.name)
        new_id = f"{elem}${cm.charge:+d}"
        id_map[cm.internal_id] = new_id

    if not id_map:
        return

    # 1. Remap component_meta internal_ids
    for cm in report.component_meta:
        if cm.internal_id in id_map:
            cm.internal_id = id_map[cm.internal_id]

    # 2. Remap metal_ids list
    report.metal_ids = [id_map.get(mid, mid) for mid in report.metal_ids]

    # 3. Remap total_metals, metal_charges dicts
    report.total_metals = {id_map.get(k, k): v
                           for k, v in report.total_metals.items()}
    report.metal_charges = {id_map.get(k, k): v
                            for k, v in report.metal_charges.items()}

    # 4. Remap species stoich keys and stoich_hlx metal keys
    for se in report.species:
        se.stoich = {id_map.get(k, k): v for k, v in se.stoich.items()}
        if se.stoich_hlx:
            se.stoich_hlx = [
                (id_map.get(key, key), count)
                for key, count in se.stoich_hlx
            ]

    # Regenerate component-based IDs (with collision disambiguation)
    _base_ids: Dict[str, List[str]] = {}
    for se in report.species:
        base = _make_comp_id(se.stoich, se.charge, se.phase, stoich_hlx=se.stoich_hlx)
        _base_ids.setdefault(base, []).append(se.original_id)

    _sp_lookup = {se.original_id: se for se in report.species}
    for base, orig_ids in _base_ids.items():
        if len(orig_ids) == 1:
            _sp_lookup[orig_ids[0]].species_id = base
        else:
            ranked = sorted(orig_ids,
                            key=lambda oid: -_sp_lookup[oid].log_beta)
            for rank, oid in enumerate(ranked, 1):
                _sp_lookup[oid].species_id = f"{base}[{rank}]"

    # 5. Remap reaction species_id (match via original_sp_id)
    sp_orig_to_new = {se.original_id: se.species_id
                      for se in report.species}
    for rx in report.reactions:
        rx.species_id = sp_orig_to_new.get(rx.original_sp_id,
                                           rx.species_id)

    # 6. Remap valence_groups entries
    for vg in report.valence_groups:
        for entry in vg.entries:
            if entry.internal_id in id_map:
                entry.internal_id = id_map[entry.internal_id]
        vg.reference_id = id_map.get(vg.reference_id, vg.reference_id)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Update activity corrections at a new ionic strength
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def update_report_ionic_strength(
    report: FreeEnergyReport,
    new_I: float,
) -> None:
    """Recalculate ``app_log_beta`` for every species at *new_I* (in-place).

    Called by the Gibbs solver's auto-ionic-strength loop to self-
    consistently update the Davies corrections after each iteration.
    """
    from electrolyte_activity_models.solution_models_activity_coeff import (
        davies_log_gamma,
    )
    report.ionic_strength = new_I
    for se in report.species:
        lg_prod = davies_log_gamma(se.charge, new_I)
        lg_react = 0.0
        for key, count in se.stoich.items():
            if key == "H":
                lg_react += count * davies_log_gamma(1, new_I)
            elif key.startswith("L"):
                lg_react += count * davies_log_gamma(
                    report.ligand_charges.get(key, 0), new_I)
            else:  # metal key (M1, Cu$+2, etc.)
                lg_react += count * davies_log_gamma(
                    report.metal_charges.get(key, 0), new_I)
        se.app_log_beta = se.log_beta - (lg_prod - lg_react)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  pH-dependent effective chemical potentials
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def mu_eff_at_pH(
    report: FreeEnergyReport,
    pH: float,
    *,
    reference: str = "canonical",
) -> List[Tuple[str, str, float]]:
    """Effective Î¼Â° at a given pH, absorbing the Hâº chemical potential.

    Î¼Â°_eff(i, pH)  =  Î¼Â°(i) + r_i Ã— 2.303 RT Ã— pH

    Parameters
    ----------
    report : FreeEnergyReport
    pH     : solution pH
    reference : ``"canonical"`` or ``"free"``

    Returns
    -------
    list of (species_id, label, mu_eff) sorted ascending (most stable first).
    """
    fac = report.factor
    out: List[Tuple[str, str, float]] = []
    for se in report.species:
        mu0 = se.mu0_canonical if reference == "canonical" else se.mu0_free
        r = se.stoich.get("H", 0)
        mu_eff = mu0 + r * fac * pH
        out.append((se.species_id, se.label, mu_eff))
    out.sort(key=lambda t: t[2])
    return out


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Text report formatter
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def format_report(report: FreeEnergyReport, *, include_pH: Optional[float] = None) -> str:
    """Return a human-readable text report."""
    lines: List[str] = []
    w = lines.append

    w("=" * 76)
    w("  EQUILIBRIUM NETWORK â€” FREE-ENERGY ANALYSIS")
    w("=" * 76)
    for n in report.notes:
        w(f"  {n}")
    w(f"  2.303 RT = {report.factor:.4f} kJ/mol")
    w("")

    # â”€â”€ Component legend â”€â”€
    w("â”€â”€â”€ Components â”€â”€â”€")
    for i, mn in enumerate(report.metal_names):
        mid = report.metal_ids[i]
        t = report.total_metals.get(mid, "Not defined")
        t_text = f"{t:.4g}" if isinstance(t, (int, float)) else str(t)
        w(f"  {mid}: {mn:<14s} T = {t_text} M")
    for j, ln in enumerate(report.ligand_names):
        lid = report.ligand_ids[j]
        t = report.total_ligands.get(lid, "Not defined")
        t_text = f"{t:.4g}" if isinstance(t, (int, float)) else str(t)
        w(f"  {lid}: {ln:<14s} T = {t_text} M")
    w(f"   H: Hâº  (pH-controlled)")
    w("")

    # â”€â”€ Canonical reference info â”€â”€
    w("â”€â”€â”€ Ligand canonical references â”€â”€â”€")
    for lig_idx in sorted(report.canonical_info):
        ci = report.canonical_info[lig_idx]
        lb = ci["log_beta_HxL"]
        mu_shift = report.factor * lb
        w(f"  L{lig_idx}: {ci['name']:>12s}  â†’  H{ci['canonical_H']}L  "
          f"(logÎ² = {lb:+.3f},  Î¼Â° shift = {mu_shift:+.2f} kJ/mol)")
    w("")

    # â”€â”€ Species table â”€â”€ sorted by canonical Î¼Â°
    sorted_sp = sorted(report.species, key=lambda s: s.mu0_canonical)
    w("â”€â”€â”€ Species standard chemical potentials â”€â”€â”€")
    w(f"  {'ID':<30s} {'Label':<26s} {'logÎ²':>8s}  "
      f"{'Î¼Â°_free':>10s}  {'Î¼Â°_canon':>10s}  {'Stoichiometry':<24s}")
    w("  " + "â”€" * 112)
    for se in sorted_sp:
        st = _stoich_str(se.stoich)
        w(f"  {se.species_id:<30s} {se.label:<26s} {se.log_beta:>8.3f}  "
          f"{se.mu0_free:>+10.2f}  {se.mu0_canonical:>+10.2f}  "
          f"{st:<24s}")
    w("")

    # â”€â”€ Reaction table â”€â”€
    w("â”€â”€â”€ Cumulative formation reactions (Î”GÂ°) â”€â”€â”€")
    w(f"  {'Eq ID':<32s} {'Label':<26s} {'logÎ²':>8s}  "
      f"{'Î”GÂ°_free':>10s}  {'Î”GÂ°_canon':>10s}")
    w("  " + "â”€" * 92)
    for rx in sorted(report.reactions, key=lambda r: r.delta_G0):
        w(f"  {rx.eq_id:<32s} {rx.label:<26s} {rx.log_beta:>8.3f}  "
          f"{rx.delta_G0:>+10.2f}  {rx.delta_G0_can:>+10.2f}")
    w("")

    # â”€â”€ pH-effective table â”€â”€
    if include_pH is not None:
        eff = mu_eff_at_pH(report, include_pH)
        w(f"â”€â”€â”€ Î¼Â°_eff at pH {include_pH:.1f} (canonical ref, most stable first) â”€â”€â”€")
        w(f"  {'ID':<30s} {'Label':<26s}  {'Î¼Â°_eff':>10s}")
        w("  " + "â”€" * 70)
        for sp_id, lbl, mue in eff:
            w(f"  {sp_id:<30s} {lbl:<26s}  {mue:>+10.2f}")
        w("")

    # â”€â”€ Consistency â”€â”€
    if report.inconsistencies:
        w("â”€â”€â”€ CONSISTENCY WARNINGS â”€â”€â”€")
        for msg in report.inconsistencies:
            w(f"  âš  {msg}")
    else:
        w("â”€â”€â”€ Consistency: OK (no ladder violations detected) â”€â”€â”€")
    w("")

    return "\n".join(lines)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Metadata extractors (from raw JSON)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _extract_component_meta(raw: dict, parsed) -> List[ComponentMeta]:
    """Extract reference metadata for every component.

    M0 = H+ (always), L0 = OH- (always).
    Real metals start at M1, real ligands at L1.
    """
    meta: List[ComponentMeta] = []
    components = raw.get("components", {})

    h_info = None
    oh_info = None
    real_metals = []
    real_ligands = []
    for name, info in components.items():
        if name == "H+":
            h_info = info
            continue
        elif name == "OH-":
            oh_info = info
            continue
        if info["type"] == "metal":
            real_metals.append((info["spec_id"], name, info))
        elif info["type"] == "ligand":
            real_ligands.append((info["spec_id"], name, info))
    real_metals.sort(key=lambda x: x[0])
    real_ligands.sort(key=lambda x: x[0])

    # M0 = H+ (always first metal entry)
    if h_info:
        ref = h_info.get("reference", {})
        meta.append(ComponentMeta(
            internal_id="M0",
            name="H+",
            comp_type="metal",
            charge=h_info.get("charge", 1),
            total=0.0,
            db_source=ref.get("source", ""),
            db_id=ref.get("source_database_ID", ""),
        ))

    # Real metals: M1, M2, â€¦
    for i, (token, name, info) in enumerate(real_metals):
        ref = info.get("reference", {})
        meta.append(ComponentMeta(
            internal_id=f"M{i + 1}",
            name=name,
            comp_type="metal",
            charge=info.get("charge", 0),
            total=_component_total_for_metadata(info, name),
            db_source=ref.get("source", ""),
            db_id=ref.get("source_database_ID", ""),
            smiles=ref.get("smiles", ""),
            inchi=ref.get("inchi", ""),
        ))

    # L0 = OH- (always first ligand entry)
    if oh_info:
        ref = oh_info.get("reference", {})
        meta.append(ComponentMeta(
            internal_id="L0",
            name="OH-",
            comp_type="ligand",
            charge=oh_info.get("charge", -1),
            total=0.0,
            db_source=ref.get("source", ""),
            db_id=ref.get("source_database_ID", ""),
        ))

    # Real ligands: L1, L2, â€¦
    for j, (token, name, info) in enumerate(real_ligands):
        ref = info.get("reference", {})
        meta.append(ComponentMeta(
            internal_id=f"L{j + 1}",
            name=name,
            comp_type="ligand",
            charge=info.get("charge", 0),
            total=_component_total_for_metadata(info, name),
            db_source=ref.get("source", ""),
            db_id=ref.get("source_database_ID", ""),
            smiles=ref.get("smiles", ""),
            inchi=ref.get("inchi", ""),
            canonical_HOL=info.get("ligand_canonical_HOL"),
        ))

    return meta


def _component_total_for_metadata(info: dict, name: str) -> float | str:
    """Read a reference-card total without manufacturing a numeric value."""
    value = info.get("total", "Not defined")
    if value == "Not defined":
        return "Not defined"
    if isinstance(value, bool):
        raise ValueError(f"component {name!r} total must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"component {name!r} total must be numeric or exactly "
            f"'Not defined', got {value!r}") from exc


def _build_spec_id_name_map(raw: dict) -> Dict[str, str]:
    """Build a spec_id â†’ human-readable name map from the components section.

    Used to substitute internal spec_ids (e.g. ``<M_2>``) with display
    names (e.g. ``Ca2+``) in equation strings for the validation section.
    """
    spec_map: Dict[str, str] = {}
    for comp_name, comp in raw.get("components", {}).items():
        sid = comp.get("spec_id", "")
        if sid:
            spec_map[sid] = comp_name
    return spec_map


def _humanize_equation(eq_str: str, spec_map: Dict[str, str]) -> str:
    """Replace only grammar-delimited spec_ids with component names.

    Bare substring replacement corrupted chemical literals: the proton
    spec_id ``H`` changed ``H2O`` into ``H+2O`` and could also rewrite the H
    inside hydroxide text.  Equation-builder component tokens are delimited
    by angle brackets, so solvent/formula literals must be left untouched.
    """
    return re.sub(
        r"<([^<>]+)>",
        lambda match: f"<{spec_map.get(match.group(1), match.group(1))}>",
        eq_str,
    )


def _extract_equilibrium_meta(raw: dict) -> List[EquilibriumMeta]:
    """Extract reference metadata for every raw equilibrium."""
    spec_map = _build_spec_id_name_map(raw)
    meta: List[EquilibriumMeta] = []
    eq_sections = raw.get("equations", {})
    for sec_key in ("metal_ligand_system_aqueous_only",
                     "metal_ligand_system_dissociation_only"):
        for block in eq_sections.get(sec_key, []):
            mls = block.get("metal_ligand_system", {})
            metal_names = [m[1] for m in mls.get("metal", [])]
            ligand_names = [l_[1] for l_ in mls.get("ligand", [])]
            net_ids = [int(n) for n in block.get("selected_network_ids", [])]
            for eq_entry in block.get("equilibria", []):
                ref = eq_entry.get("reference", {})
                rhs_list = eq_entry.get("RHS", [])
                rhs_sp_raw = rhs_list[0].get("species", "") if rhs_list else ""
                raw_eq_str = eq_entry.get("equation_str", "")
                human_eq_str = _humanize_equation(raw_eq_str, spec_map)
                meta.append(EquilibriumMeta(
                    equation_str=human_eq_str,
                    log_K=eq_entry.get("log_K", 0.0),
                    constant_type=eq_entry.get("constant_type", ""),
                    T_source_C=eq_entry.get("data_source_temperature", 25.0),
                    I_source_M=eq_entry.get("data_source_ionic_strength", 0.0),
                    db_source=ref.get("source", ""),
                    db_id=ref.get("source_database_ID", ""),
                    include=eq_entry.get("include_calculation", True),
                    metal_system=metal_names,
                    ligand_system=ligand_names,
                    rhs_species_raw=rhs_sp_raw,
                    ref_eq_net_ids=net_ids,
                ))
    return meta


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Valence-group detection (same element, different charge)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

import re as _re

_ELEMENT_RE = _re.compile(r"^([A-Z][a-z]?)")      # extract element symbol


def _element_from_name(metal_name: str) -> str:
    """Extract the element symbol from a metal ion name.

    Handles both raw ('Fe3+' â†’ 'Fe') and bracket-wrapped ('[Cu]2+' â†’ 'Cu').
    """
    name = metal_name.strip()
    if name.startswith("["):
        m = _re.match(r'\[([A-Za-z]+)\]', name)
        if m:
            return m.group(1)
    m = _ELEMENT_RE.match(name)
    return m.group(1) if m else name


def _reference_sort_key(charge: int) -> Tuple[int, int]:
    """Sort key so that charge closest to 0 comes first.

    Priority: 0 â†’ +1 â†’ âˆ’1 â†’ +2 â†’ âˆ’2 â†’ â€¦
    Within the same |charge|, positive wins over negative.
    """
    return (abs(charge), -charge)


def _detect_valence_groups(component_meta: List[ComponentMeta]) -> List[ValenceGroup]:
    """Group real metals by element and pick the reference oxidation state."""
    elem_map: Dict[str, List[ComponentMeta]] = {}
    for cm in component_meta:
        if cm.comp_type != "metal" or cm.internal_id == "M0":
            continue
        elem = _element_from_name(cm.name)
        elem_map.setdefault(elem, []).append(cm)

    groups: List[ValenceGroup] = []
    for elem, cms in sorted(elem_map.items()):
        sorted_cms = sorted(cms, key=lambda c: _reference_sort_key(c.charge))
        ref_cm = sorted_cms[0]
        entries = [
            ValenceGroupEntry(
                internal_id=cm.internal_id,
                name=cm.name,
                charge=cm.charge,
                is_reference=(cm.internal_id == ref_cm.internal_id),
            )
            for cm in sorted_cms
        ]
        groups.append(ValenceGroup(
            element=elem,
            entries=entries,
            reference_id=ref_cm.internal_id,
            n_valences=len(entries),
        ))
    return groups


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Redox couple extraction from raw JSON
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_F_C_MOL = 96485.3329          # Faraday constant C/mol


def _extract_redox_couples(
    raw: dict,
    component_meta: List[ComponentMeta],
    factor_2303RT: float,
) -> List[RedoxCouple]:
    """Extract explicit redox half-reactions from the input JSON.

    Looks for equilibria that contain ``"n_electrons"`` or electron
    species ``<E>`` on LHS/RHS.  If none are present (pure speciation
    input), returns an empty list.
    """
    couples: List[RedoxCouple] = []
    # Build token â†’ ComponentMeta lookup
    cm_by_name = {cm.name: cm for cm in component_meta}

    # Build spec_id â†’ component name lookup from raw JSON
    spec_to_name: Dict[str, str] = {}
    for cname, cinfo in raw.get("components", {}).items():
        sid = cinfo.get("spec_id", "")
        spec_to_name[sid] = cname

    eq_sections = raw.get("equations", {})
    for sec_key in ("metal_ligand_system_aqueous_only",
                     "metal_ligand_system_dissociation_only"):
        for block in eq_sections.get(sec_key, []):
            for eq_entry in block.get("equilibria", []):
                n_e = eq_entry.get("n_electrons")
                if not n_e:
                    continue
                E0 = eq_entry.get("E0_V_vs_SHE", 0.0)
                logK = eq_entry.get("log_K", 0.0)
                eq_str = eq_entry.get("equation_str", "")

                # Identify the oxidised and reduced species from LHS/RHS
                lhs = eq_entry.get("LHS", [])
                rhs = eq_entry.get("RHS", [])
                oxidized_tok = reduced_tok = None
                for side_items, label in [(lhs, "LHS"), (rhs, "RHS")]:
                    for item in side_items:
                        sp = item.get("species", "")
                        if sp == "<E>":
                            continue
                        name = spec_to_name.get(sp, sp)
                        cm = cm_by_name.get(name)
                        if cm and cm.comp_type == "metal" and cm.internal_id != "M0":
                            if label == "LHS":
                                oxidized_tok = cm
                            else:
                                reduced_tok = cm
                if not oxidized_tok or not reduced_tok:
                    continue
                # Ensure higher charge is "oxidized"
                if oxidized_tok.charge < reduced_tok.charge:
                    oxidized_tok, reduced_tok = reduced_tok, oxidized_tok

                elem = _element_from_name(oxidized_tok.name)
                delta_G0 = -factor_2303RT * logK
                half_rxn = f"{oxidized_tok.name} + {n_e}eâ» â†’ {reduced_tok.name}"

                ref = eq_entry.get("reference", {})
                source = ref.get("source", "")

                couples.append(RedoxCouple(
                    couple_id=f"{oxidized_tok.name}/{reduced_tok.name}",
                    element=elem,
                    oxidized_id=oxidized_tok.internal_id,
                    oxidized_name=oxidized_tok.name,
                    reduced_id=reduced_tok.internal_id,
                    reduced_name=reduced_tok.name,
                    n_electrons=n_e,
                    E0_V_SHE=E0 if E0 else logK * factor_2303RT / (_F_C_MOL / 1000.0),
                    logK=logK,
                    delta_G0_kJ=delta_G0,
                    half_reaction=half_rxn,
                    source=source,
                ))
    return couples


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Ligand micro-valence computation
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _compute_ligand_micro_valences(
    component_meta: List[ComponentMeta],
) -> List[LigandMicroValence]:
    """Compute per-atom oxidation-state summaries for organic ligands."""
    try:
        from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.micro_valence_calculator import (
            summarise_oxidation_states,
        )
    except ImportError:
        return []

    results: List[LigandMicroValence] = []
    for cm in component_meta:
        if cm.comp_type != "ligand" or cm.internal_id == "L0":
            continue
        if not cm.smiles:
            continue
        out = summarise_oxidation_states(cm.smiles)
        if out is None:
            continue
        atom_os, dynamic = out
        results.append(LigandMicroValence(
            ligand_id=cm.internal_id,
            ligand_name=cm.name,
            smiles=cm.smiles,
            atom_os_summary=atom_os,
            dynamic_atoms=dynamic,
        ))
    return results
