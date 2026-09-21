"""
built_system_from_dGreport.py
===============
Bridge between ``FreeEnergyReport`` (thermodynamic network) and the
numpy arrays consumed by the Newton-Raphson point solver.

``BuiltSystem`` is the solver-ready container.
``build_from_free_energy_report()`` is the main entry point.

The same array layout supports pH-only speciation and Pourbaix sweeps, but
the electron dimension is controlled by the explicitly declared
``include_redox`` setting.  With redox excluded, oxidation-state components
are independent, electron stoichiometries are zero, and no potential
coordinate is present.
"""
from __future__ import annotations

import math
import re
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
#  Physical constants — sourced from the TD entry point
# ---------------------------------------------------------------------------
from support_TD_helpers.TD_constants_entry_point import (
    LN10, F_CONST, NERNST_FACTOR, R_CONST,
)

R_kJ = R_CONST * 1e-3    # kJ mol⁻¹ K⁻¹


# ---------------------------------------------------------------------------
#  Proxy types for old SolidManager interface
# ---------------------------------------------------------------------------
class DissolutionProxy:
    """Mimics ``SolverEquilibrium`` attributes needed by SolidManager."""
    __slots__ = ("id", "log_K_diss_eff",
                 "stoich_metals", "stoich_ligands", "stoich_H", "stoich_e",
                 "nu_elements", "nu_ligands", "solid_label",
                 "solid_species_id")

    def __init__(self, logK, stoich_pq_row, stoich_H, stoich_e,
                 nu_row, n_metals, label, solid_id=""):
        self.id = solid_id or label
        self.solid_species_id = solid_id or label
        self.log_K_diss_eff = logK
        self.stoich_metals = list(stoich_pq_row[:n_metals])
        self.stoich_ligands = list(stoich_pq_row[n_metals:])
        self.stoich_H = stoich_H
        self.stoich_e = stoich_e
        self.nu_elements = list(nu_row[:n_metals])
        self.nu_ligands = list(nu_row[n_metals:])
        self.solid_label = label


class SpeciesProxy:
    """Mimics ``SolverSpecies`` for SolidManager/labeller debug output."""
    __slots__ = ("id", "label", "charge")

    def __init__(self, sid, label, charge=0):
        self.id = sid
        self.label = label
        self.charge = charge


# ---------------------------------------------------------------------------
#  Built system container
# ---------------------------------------------------------------------------
@dataclass
class BuiltSystem:
    """Solver-ready numpy arrays for the Newton-Raphson equilibrium solver.

    Constructed from a ``FreeEnergyReport`` via
    ``build_from_free_energy_report()``.
    """
    system_name:        str
    temperature_C:      float
    ionic_strength:     float
    ionic_mode:         str              # "fixed" or "auto"
    activity_model:     str              # "ideal" or "davies"
    include_solids:     bool

    # Basis bookkeeping
    n_basis:            int
    basis_labels:       List[str]        # human-readable names
    basis_tokens:       List[str]        # internal IDs (M1, M2, L1, …)
    basis_charges:      List[int]

    element_names:      List[str]        # e.g. ["Cu", "Fe"]
    ligand_names:       List[str]        # e.g. ["glycine"]
    element_totals:     List[float]
    ligand_totals:      List[float]
    principal_elements: List[str]        # elements for Pourbaix labelling

    # Derived redox: token → (basis_token, logK_redox, n_e_sign)
    derived_redox:      Dict[str, Tuple[str, float, int]]

    # Species metadata (parallel to numpy arrays)
    species_labels:     List[str]
    species_ids:        List[str]
    species_charges:    np.ndarray       # (N_aq,)
    species_phases:     List[str]

    # Core solver arrays ---------------------------------------------------
    log_beta_eff:       np.ndarray       # (N_aq,)  apparent logβ
    stoich_pq:          np.ndarray       # (N_aq, N_basis) element+ligand stoich
    stoich_r:           np.ndarray       # (N_aq,)  H⁺ stoichiometry
    stoich_s:           np.ndarray       # (N_aq,)  e⁻ stoichiometry
    nu_matrix:          np.ndarray       # (N_basis, N_aq) mass-balance
    C_total:            np.ndarray       # (N_basis,) total concentrations

    # Redox-aligned thermodynamic constants and Davies charge coefficients.
    # These, rather than card-era apparent constants, are the source of truth
    # for both fixed-I construction and auto-I recomputation.
    log_beta_thermo:    np.ndarray       # (N_aq,)
    aq_activity_delta_z2: np.ndarray     # (N_aq,)

    # Dissolution equilibria -----------------------------------------------
    n_diss:             int
    diss_labels:        List[str]
    diss_logK:          np.ndarray       # (N_diss,)
    log_K_diss_thermo:  np.ndarray       # (N_diss,)
    diss_activity_delta_z2: np.ndarray   # (N_diss,)
    diss_stoich_pq:     np.ndarray       # (N_diss, N_basis)
    diss_r:             np.ndarray       # (N_diss,)
    diss_s:             np.ndarray       # (N_diss,)
    diss_nu:            np.ndarray       # (N_diss, N_basis)

    # Mapping helpers for output / labelling
    spec_id_to_name:    Dict[str, str]
    element_to_ids:     Dict[str, List[str]]  # elem → [M1, M3]
    calculation_species_by_principal_element: Dict[
        str, Dict[str, List[str]]
    ] = field(default_factory=dict)
    water_stability:    dict = field(default_factory=lambda: {
        "e0_h2": 0.0, "e0_o2": 1.229,
    })

    # ---- convenience accessors (labeler / SolidManager interface) ----

    @property
    def n_metals(self) -> int:
        return len(self.element_names)

    @property
    def aqueous_species(self) -> List[SpeciesProxy]:
        """Return proxy list matching the ``SolverSpecies`` interface."""
        return [
            SpeciesProxy(sid, lbl, int(ch))
            for sid, lbl, ch in zip(
                self.species_ids, self.species_labels, self.species_charges)
        ]

    @property
    def dissolution_eqs(self) -> List[DissolutionProxy]:
        """Return proxy list matching the ``SolverEquilibrium`` interface."""
        n_m = self.n_metals
        proxies = []
        for i in range(self.n_diss):
            proxies.append(DissolutionProxy(
                logK=float(self.diss_logK[i]),
                stoich_pq_row=self.diss_stoich_pq[i],
                stoich_H=float(self.diss_r[i]),
                stoich_e=float(self.diss_s[i]),
                nu_row=self.diss_nu[i],
                n_metals=n_m,
                label=self.diss_labels[i],
                solid_id=self.diss_labels[i],
            ))
        return proxies

    @property
    def nu_elem_matrix(self) -> np.ndarray:
        """Element-only rows of nu_matrix (n_metals × N_aq)."""
        return self.nu_matrix[:self.n_metals]


# ---------------------------------------------------------------------------
#  Card-sourced species attributes (phase + formal oxidation state)
# ---------------------------------------------------------------------------
def principal_element_card_maps(built: "BuiltSystem") -> Dict[str, Dict[str, Any]]:
    """Phase and formal-oxidation-state maps keyed by species label.

    Returns ``{"phase": {label: "solid"|"aqueous"},
    "oxidation_state": {label: int|None}}``.  The oxidation state is the
    principal element's formal value, reconstructed only from the card's basis
    charges and electron stoichiometry:

        ox = (Σ basis_charge·metal_count − electron_stoich) / metal_count

    It resolves to ``None`` — never guessed — when the value is non-integer
    (mixed valence), when two principal metals share one species, or when the
    species carries none of the principal element.
    """
    basis_tokens = list(getattr(built, "basis_tokens", None) or [])
    basis_charges = list(getattr(built, "basis_charges", None) or [])
    element_to_ids = dict(getattr(built, "element_to_ids", None) or {})
    principal = list(getattr(built, "principal_elements", None) or [])
    token_index = {tok: idx for idx, tok in enumerate(basis_tokens)}

    elem_cols: Dict[str, List[int]] = {}
    for elem in principal:
        cols = [
            token_index[tok]
            for tok in element_to_ids.get(elem, [])
            if tok in token_index
        ]
        if cols:
            elem_cols[elem] = cols

    def _oxidation_state(stoich_row: Any, s_value: Any) -> Optional[int]:
        try:
            present: List[Tuple[List[int], float]] = []
            for cols in elem_cols.values():
                metal_count = sum(float(stoich_row[col]) for col in cols)
                if metal_count > 1e-9:
                    present.append((cols, metal_count))
            if len(present) != 1:
                return None
            cols, metal_count = present[0]
            charge_sum = sum(
                float(basis_charges[col]) * float(stoich_row[col]) for col in cols
            )
            raw = (charge_sum - float(s_value)) / metal_count
        except (IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
            return None
        if not math.isfinite(raw):
            return None
        if abs(raw - round(raw)) > 1e-6:
            return None
        return int(round(raw))

    phase_map: Dict[str, str] = {}
    oxidation_map: Dict[str, Optional[int]] = {}

    species_labels = list(getattr(built, "species_labels", None) or [])
    species_phases = list(getattr(built, "species_phases", None) or [])
    stoich_pq = getattr(built, "stoich_pq", None)
    stoich_s = getattr(built, "stoich_s", None)
    for idx, label in enumerate(species_labels):
        phase = species_phases[idx] if idx < len(species_phases) else "aqueous"
        is_solid = str(phase) in ("solid", "dissolution")
        phase_map.setdefault(label, "solid" if is_solid else "aqueous")
        if (
            stoich_pq is not None
            and stoich_s is not None
            and idx < len(stoich_pq)
            and label not in oxidation_map
        ):
            oxidation_map[label] = _oxidation_state(stoich_pq[idx], stoich_s[idx])

    diss_labels = list(getattr(built, "diss_labels", None) or [])
    diss_stoich_pq = getattr(built, "diss_stoich_pq", None)
    diss_s = getattr(built, "diss_s", None)
    for idx, label in enumerate(diss_labels):
        phase_map[label] = "solid"
        if (
            diss_stoich_pq is not None
            and diss_s is not None
            and idx < len(diss_stoich_pq)
        ):
            oxidation_map[label] = _oxidation_state(diss_stoich_pq[idx], diss_s[idx])

    return {"phase": phase_map, "oxidation_state": oxidation_map}


# ---------------------------------------------------------------------------
#  Builder
# ---------------------------------------------------------------------------
def build_from_free_energy_report(
    report,
    *,
    ionic_strength: Optional[float] = None,
    system_name: str = "",
) -> BuiltSystem:
    """Convert a ``FreeEnergyReport`` into solver-ready numpy arrays.

    Parameters
    ----------
    report : FreeEnergyReport
        The thermodynamic network (from ``compute_free_energy_network``
        or from the MD-card reader).
    ionic_strength : float, optional
        Override ionic strength (default: use report value).
    system_name : str
        Optional system name for output labels.

    Returns
    -------
    BuiltSystem
    """
    def _required_finite(value, label: str, *, positive: bool = False) -> float:
        if value == "Not defined" or value is None or isinstance(value, bool):
            raise ValueError(f"{label} is 'Not defined'; declare it explicitly")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be numeric, got {value!r}") from exc
        if not np.isfinite(number) or (number <= 0 if positive else number < 0):
            relation = "> 0" if positive else ">= 0"
            raise ValueError(f"{label} must be finite and {relation}, got {value!r}")
        return number

    report_I = getattr(report, "ionic_strength", "Not defined")
    I_eff = _required_finite(
        ionic_strength if ionic_strength is not None else report_I,
        "ionic strength",
    )
    T_C_raw = getattr(report, "temperature_C", "Not defined")
    if T_C_raw == "Not defined" or T_C_raw is None or isinstance(T_C_raw, bool):
        raise ValueError("temperature_C is 'Not defined'; declare it explicitly")
    try:
        T_C = float(T_C_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"temperature_C must be numeric, got {T_C_raw!r}") from exc
    if not np.isfinite(T_C):
        raise ValueError(f"temperature_C must be finite, got {T_C_raw!r}")
    T_K = _required_finite(
        getattr(report, "temperature_K", "Not defined"),
        "temperature_K", positive=True,
    )
    ionic_mode = getattr(report, "ionic_mode", "Not defined")
    if ionic_mode not in {"fixed", "auto"}:
        raise ValueError(
            "ionic_mode is 'Not defined' or unsupported on the solver report; "
            "declare fixed or auto explicitly")
    factor_kJ = LN10 * R_kJ * T_K

    # ``include_redox`` controls whether multi-valence metals are aggregated
    # into one element basis (True, classical Pourbaix) or kept as
    # independent components (False, redox-excluded).  Every explicitly
    # declared valence is retained, including a valence whose current
    # analytical total is zero: a dynamic sweep may make that same total
    # positive at a later grid coordinate.
    include_redox_raw = getattr(report, "include_redox", "Not defined")
    if not isinstance(include_redox_raw, bool):
        raise ValueError(
            "redox mode is 'Not defined' on the solver report; declare "
            "redox_mode explicitly before building the numerical system")
    include_redox = include_redox_raw

    activity_model = getattr(report, "activity_model", "Not defined")
    if activity_model == "debye_huckel":
        raise ValueError(
            "activity_model='debye_huckel' is not implemented; "
            "declare 'ideal' or 'davies'")
    if activity_model not in {"ideal", "davies"}:
        raise ValueError(
            "activity_model is 'Not defined' or unsupported on the solver "
            "report; declare 'ideal' or 'davies'")
    include_solids_raw = getattr(report, "include_solids", "Not defined")
    if not isinstance(include_solids_raw, bool):
        raise ValueError(
            "solids mode is 'Not defined' on the solver report; declare "
            "solids='include' or solids='exclude' explicitly")
    include_solids = include_solids_raw

    # ------------------------------------------------------------------
    # 1. Build redox map FIRST (needed for basis reduction)
    # ------------------------------------------------------------------
    all_metal_ids = list(report.metal_ids)      # ["M1", "M2", ...]
    ligand_ids = list(report.ligand_ids)         # ["L1", "L2", ...]

    derived_redox: Dict[str, Tuple[str, float, int]] = {}
    element_to_ids: Dict[str, List[str]] = {}

    # Map each metal to its element group
    vg_map: Dict[str, str] = {}  # internal_id -> element
    ref_ids_set: set = set()     # reference metal ids
    for vg in report.valence_groups:
        ids = [e.internal_id for e in vg.entries]
        element_to_ids[vg.element] = ids
        ref_ids_set.add(vg.reference_id)
        for e in vg.entries:
            vg_map[e.internal_id] = vg.element

    if include_redox:
        for rc in report.redox_couples:
            derived_redox[rc.oxidized_id] = (rc.reduced_id, rc.logK, -rc.n_electrons)

        # Derive redox map from valence_groups when no explicit redox_couples
        # are available (e.g. when parsing MD cards instead of raw JSON).
        if not derived_redox and report.valence_groups:
            for vg in report.valence_groups:
                ref_entry = next(
                    (e for e in vg.entries if e.internal_id == vg.reference_id),
                    None,
                )
                if ref_entry is None:
                    continue
                ref_charge = ref_entry.charge
                for e in vg.entries:
                    if e.internal_id != vg.reference_id:
                        n_e_sign = -(e.charge - ref_charge)
                        derived_redox[e.internal_id] = (
                            vg.reference_id, 0.0, n_e_sign,
                        )

    # ------------------------------------------------------------------
    # 2. Collapse multi-valence metals into one element basis
    # ------------------------------------------------------------------
    # In the Pourbaix formulation, each ELEMENT gets one basis slot.
    # Only the reference oxidation state is a basis species; derived
    # oxidation states are expressed via the Nernst equation (stoich_s).
    #
    # For single-valence metals (no valence group), the metal IS the
    # element basis directly.

    derived_metal_set = set(derived_redox.keys())

    # Identify unique elements and their reference metal tokens
    # Order: reference metals first (one per element), then any
    # metals that aren't part of a valence group.
    basis_metal_ids: List[str] = []     # one per unique element
    basis_metal_names: List[str] = []
    basis_metal_charges: List[int] = []
    basis_metal_totals: List[float] = []
    element_names: List[str] = []

    # metal_id -> element basis index (for mapping species stoich)
    mid_to_elem_idx: Dict[str, int] = {}

    all_metal_names = list(report.metal_names) if report.metal_names else all_metal_ids[:]
    mid_to_name = dict(zip(all_metal_ids, all_metal_names))

    def _required_total(mapping, key: str, kind: str) -> float:
        value = mapping.get(key, "Not defined")
        if value == "Not defined" or isinstance(value, bool):
            raise ValueError(
                f"{kind} total {key!r} is 'Not defined'; the calculation "
                "card must declare it before solver construction")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{kind} total {key!r} must be numeric") from exc
        if not np.isfinite(number) or number < 0:
            raise ValueError(
                f"{kind} total {key!r} must be finite and >= 0")
        return number

    def _required_charge(mapping, key: str, kind: str) -> int:
        if key not in mapping:
            raise ValueError(
                f"{kind} charge {key!r} is 'Not defined'; no solver "
                "charge defaults are permitted")
        return int(mapping[key])

    if include_redox:
        # Process valence groups first: one basis slot per element
        seen_elements: set = set()
        for vg in report.valence_groups:
            elem_name = vg.element
            if elem_name in seen_elements:
                continue
            seen_elements.add(elem_name)

            ref_id = vg.reference_id
            ref_entry = next(e for e in vg.entries if e.internal_id == ref_id)
            elem_idx = len(basis_metal_ids)

            basis_metal_ids.append(ref_id)
            basis_metal_names.append(mid_to_name.get(ref_id, ref_id))
            basis_metal_charges.append(ref_entry.charge)
            # Total for this element: sum totals of ALL valence states
            elem_total = sum(
                _required_total(report.total_metals, e.internal_id, "metal")
                for e in vg.entries
            )
            if elem_total <= 0:
                raise ValueError(
                    f"metal element {elem_name!r} has explicitly declared "
                    "zero total; remove it from the system catalog or declare "
                    "a positive total")
            basis_metal_totals.append(elem_total)
            element_names.append(elem_name)

            # Map ALL metals in this group to the same element index
            for e in vg.entries:
                mid_to_elem_idx[e.internal_id] = elem_idx

        # Add metals NOT in any valence group (single-valence elements)
        for mid in all_metal_ids:
            if mid not in mid_to_elem_idx:
                elem_idx = len(basis_metal_ids)
                mid_to_elem_idx[mid] = elem_idx
                basis_metal_ids.append(mid)
                basis_metal_names.append(mid_to_name.get(mid, mid))
                basis_metal_charges.append(
                    _required_charge(report.metal_charges, mid, "metal"))
                basis_metal_totals.append(
                    _required_total(report.total_metals, mid, "metal"))
                clean = mid_to_name.get(mid, mid).rstrip("+-0123456789").rstrip()
                element_names.append(clean if clean else mid)
    else:
        # ── include_redox=False: each declared metal valence is its own
        # independent component.  No element-level aggregation is performed.
        # Retain zero-total valences so a per-cell dynamic total can move from
        # zero to positive without changing the solver basis mid-sweep.
        # ``_required_total`` still rejects every undeclared valence.
        # Physical-element grouping is deliberately *not* discarded here.
        # It is output/label metadata, independent of the solver basis.  For
        # example Fe$+2 and Fe$+3 remain two mass-balance rows while both map
        # to the single physical output element ``Fe``.
        # Use canonical ordering: same order as report.metal_ids.
        for mid in all_metal_ids:
            total = _required_total(report.total_metals, mid, "metal")
            elem_idx = len(basis_metal_ids)
            mid_to_elem_idx[mid] = elem_idx
            basis_metal_ids.append(mid)
            basis_metal_names.append(mid_to_name.get(mid, mid))
            # Charge: prefer report.metal_charges; fall back to valence-group entry.
            charge = report.metal_charges.get(mid)
            if charge is None:
                for vg in report.valence_groups:
                    for e in vg.entries:
                        if e.internal_id == mid:
                            charge = e.charge
                            break
                    if charge is not None:
                        break
            if charge is None:
                raise ValueError(
                    f"metal charge {mid!r} is 'Not defined'; no solver "
                    "charge defaults are permitted")
            basis_metal_charges.append(int(charge))
            basis_metal_totals.append(float(total))
            # Component-axis names remain distinct so constraints and the
            # numerical solver can address each independently.
            element_names.append(mid)

    n_elements = len(basis_metal_ids)
    n_ligands = len(ligand_ids)
    n_basis = n_elements + n_ligands

    # Totals and charges
    ligand_totals = [
        _required_total(report.total_ligands, lid, "ligand")
        for lid in ligand_ids
    ]
    zero_metals = [mid for mid, total in zip(basis_metal_ids, basis_metal_totals)
                   if total <= 0]
    if include_redox and zero_metals:
        raise ValueError(
            "metal totals must be positive for catalogued metals; remove "
            f"zero-total metals or declare positive totals: {zero_metals}")
    zero_ligands = [lid for lid, total in zip(ligand_ids, ligand_totals)
                    if total <= 0]
    if zero_ligands:
        raise ValueError(
            "ligand totals must be positive for catalogued ligands; remove "
            f"zero-total ligands or declare positive totals: {zero_ligands}")
    C_total = np.array(basis_metal_totals + ligand_totals, dtype=np.float64)

    ligand_charges = [
        _required_charge(report.ligand_charges, lid, "ligand")
        for lid in ligand_ids
    ]
    basis_charges = list(basis_metal_charges) + ligand_charges

    # Names and tokens
    ligand_names = list(report.ligand_names) if report.ligand_names else ligand_ids[:]
    basis_labels = list(basis_metal_names) + ligand_names
    basis_tokens = list(basis_metal_ids) + ligand_ids

    if include_redox:
        # One solver row already represents each physical element.
        principal_elements = list(dict.fromkeys(element_names))
        for i, mid in enumerate(basis_metal_ids):
            element_to_ids.setdefault(element_names[i], [mid])
    else:
        # Redox-excluded solver rows are oxidation-state components, whereas
        # artifacts are grouped by physical chemical element.  Valence-group
        # metadata is authoritative; the display-name fallback covers the
        # ordinary single-valence case where no group was needed upstream.
        physical_element_to_ids: Dict[str, List[str]] = {}
        for mid in all_metal_ids:
            physical_name = vg_map.get(mid)
            if not physical_name:
                display_name = str(mid_to_name.get(mid, mid)).strip()
                match = re.match(r"^([A-Z][a-z]?)", display_name)
                if match:
                    physical_name = match.group(1)
                else:
                    clean = display_name.rstrip(
                        "+-0123456789"
                    ).rstrip()
                    physical_name = clean if clean else mid
            physical_element_to_ids.setdefault(physical_name, []).append(mid)
        element_to_ids = physical_element_to_ids
        principal_elements = list(physical_element_to_ids)

    # Preserve a compact audit of the final card selection before excluded
    # rows are filtered out of the numerical arrays.  Physical-element
    # membership comes from ``element_to_ids`` rather than formula/name
    # parsing, so mixed-valence species such as Fe3O4 remain one Fe entry and
    # a genuinely heterometallic species is reported under each element it
    # contains.  Repeated source rows with the same displayed label collapse
    # to one entry; actual solver inclusion wins over an excluded duplicate.
    calculation_species_by_principal_element: Dict[
        str, Dict[str, List[str]]
    ] = {}
    for element in principal_elements:
        metal_ids = set(element_to_ids.get(element, []))
        order: List[str] = []
        included_by_label: Dict[str, bool] = {}
        for species in report.species:
            stoich = species.stoich or {}
            if not any(stoich.get(metal_id, 0) != 0 for metal_id in metal_ids):
                continue
            label = str(species.label or species.species_id).strip()
            if not label:
                continue
            phase = str(species.phase or "").strip().lower()
            is_solver_included = bool(species.include) and (
                phase == "aqueous"
                or (phase in ("dissolution", "solid") and include_solids)
            )
            if label not in included_by_label:
                order.append(label)
                included_by_label[label] = is_solver_included
            else:
                included_by_label[label] = (
                    included_by_label[label] or is_solver_included
                )
        calculation_species_by_principal_element[element] = {
            "included": [
                label for label in order if included_by_label[label]
            ],
            "excluded": [
                label for label in order if not included_by_label[label]
            ],
        }

    # ------------------------------------------------------------------
    # 3. Build species arrays from SpeciesEnergy entries
    # ------------------------------------------------------------------
    # For each species, stoich_pq maps metal tokens to the element basis
    # index via mid_to_elem_idx.  Derived metals contribute to the SAME
    # element row as their reference, plus an electron term via stoich_s.

    aqueous = [s for s in report.species if s.phase == "aqueous" and s.include]
    # The card writer groups phase in ("dissolution", "solid") as one solid
    # section and the reader accepts both, so the solver must too — otherwise a
    # species that arrives as "solid" (e.g. an Atlas-merged oxide) is silently
    # dropped from the diagram.
    dissolution = (
        [s for s in report.species
         if s.phase in ("dissolution", "solid") and s.include]
        if include_solids else []
    )

    N_aq = len(aqueous)
    N_diss = len(dissolution)

    log_beta_eff = np.zeros(N_aq, dtype=np.float64)
    log_beta_thermo = np.zeros(N_aq, dtype=np.float64)
    aq_activity_delta_z2 = np.zeros(N_aq, dtype=np.float64)
    stoich_pq = np.zeros((N_aq, n_basis), dtype=np.float64)
    stoich_r = np.zeros(N_aq, dtype=np.float64)
    stoich_s = np.zeros(N_aq, dtype=np.float64)
    nu_matrix = np.zeros((n_basis, N_aq), dtype=np.float64)
    charges_arr = np.zeros(N_aq, dtype=np.float64)

    sp_labels: List[str] = []
    sp_ids: List[str] = []
    sp_phases: List[str] = []
    spec_id_to_name: Dict[str, str] = {}

    for i, sp in enumerate(aqueous):
        sp_labels.append(sp.label)
        sp_ids.append(sp.species_id)
        sp_phases.append(sp.phase)
        spec_id_to_name[sp.species_id] = sp.label

        if include_redox:
            # Valence alignment expresses every oxidation state in the
            # shared element/electron reference frame.
            valence_cost = sp.mu_aligned - sp.mu0_canonical
            log_beta_thermo[i] = sp.log_beta - valence_cost / factor_kJ
        else:
            # Redox-excluded components are independent.  Each valence uses
            # its own zero reference, so no inter-valence alignment offset
            # or electron coordinate belongs in its formation constant.
            log_beta_thermo[i] = sp.log_beta
        log_beta_eff[i] = log_beta_thermo[i]
        charges_arr[i] = sp.charge

        stoich = sp.stoich or {}
        reactant_z2 = 0.0
        for token, count in stoich.items():
            if token == "H":
                charge = 1
            elif token in report.ligand_charges:
                charge = _required_charge(report.ligand_charges, token, "ligand")
            elif token in report.metal_charges:
                charge = _required_charge(report.metal_charges, token, "metal")
            else:
                # Non-component bookkeeping tokens carry no independently
                # modelled activity coefficient in the current formulation.
                continue
            reactant_z2 += float(count) * float(charge * charge)
        aq_activity_delta_z2[i] = float(sp.charge * sp.charge) - reactant_z2

        # Metal stoichiometry: map each metal_id to its element basis index
        for mid in all_metal_ids:
            coeff = stoich.get(mid, 0)
            if coeff == 0:
                continue
            j = mid_to_elem_idx[mid]
            stoich_pq[i, j] += coeff
            nu_matrix[j, i] += coeff

        # Ligand stoichiometry
        for j, lid in enumerate(ligand_ids):
            coeff = stoich.get(lid, 0)
            stoich_pq[i, n_elements + j] = coeff
            nu_matrix[n_elements + j, i] = coeff

        # H+ stoichiometry
        stoich_r[i] = stoich.get("H", 0)

        # Electron stoichiometry from redox couples
        s_total = 0.0
        for mid_key, count in stoich.items():
            if mid_key in derived_redox:
                _, _, n_e_sign = derived_redox[mid_key]
                s_total += count * n_e_sign
        stoich_s[i] = s_total

    # ------------------------------------------------------------------
    # 4. Dissolution arrays
    # ------------------------------------------------------------------
    diss_labels: List[str] = []
    diss_logK = np.zeros(N_diss, dtype=np.float64)
    diss_logK_thermo = np.zeros(N_diss, dtype=np.float64)
    diss_activity_delta_z2 = np.zeros(N_diss, dtype=np.float64)
    diss_stoich_pq = np.zeros((N_diss, n_basis), dtype=np.float64)
    diss_r = np.zeros(N_diss, dtype=np.float64)
    diss_s = np.zeros(N_diss, dtype=np.float64)
    diss_nu = np.zeros((N_diss, n_basis), dtype=np.float64)

    for i, sp in enumerate(dissolution):
        diss_labels.append(sp.label)
        if include_redox:
            valence_cost = sp.mu_aligned - sp.mu0_canonical
            diss_logK_thermo[i] = sp.log_beta - valence_cost / factor_kJ
        else:
            diss_logK_thermo[i] = sp.log_beta
        diss_logK[i] = diss_logK_thermo[i]
        stoich = sp.stoich or {}
        reactant_z2 = 0.0
        for token, count in stoich.items():
            if token == "H":
                charge = 1
            elif token in report.ligand_charges:
                charge = _required_charge(report.ligand_charges, token, "ligand")
            elif token in report.metal_charges:
                charge = _required_charge(report.metal_charges, token, "metal")
            else:
                continue
            reactant_z2 += float(count) * float(charge * charge)
        diss_activity_delta_z2[i] = (
            float(sp.charge * sp.charge) - reactant_z2)

        for mid in all_metal_ids:
            coeff = stoich.get(mid, 0)
            if coeff == 0:
                continue
            j = mid_to_elem_idx[mid]
            diss_stoich_pq[i, j] += coeff
            diss_nu[i, j] += coeff
        for j, lid in enumerate(ligand_ids):
            coeff = stoich.get(lid, 0)
            diss_stoich_pq[i, n_elements + j] = coeff
            diss_nu[i, n_elements + j] = coeff
        diss_r[i] = stoich.get("H", 0)

        s_total = 0.0
        for mid_key, count in stoich.items():
            if mid_key in derived_redox:
                _, _, n_e_sign = derived_redox[mid_key]
                s_total += count * n_e_sign
        diss_s[i] = s_total

    # ------------------------------------------------------------------
    # 5. Assemble result
    # ------------------------------------------------------------------
    if not system_name:
        parts = list(dict.fromkeys(element_names)) + ligand_names
        system_name = " + ".join(parts) if parts else "System"

    built = BuiltSystem(
        system_name=system_name,
        temperature_C=T_C,
        ionic_strength=I_eff,
        ionic_mode=ionic_mode,
        activity_model=activity_model,
        include_solids=include_solids,
        n_basis=n_basis,
        basis_labels=basis_labels,
        basis_tokens=basis_tokens,
        basis_charges=basis_charges,
        element_names=element_names,
        ligand_names=ligand_names,
        element_totals=basis_metal_totals,
        ligand_totals=ligand_totals,
        principal_elements=principal_elements,
        derived_redox=derived_redox,
        species_labels=sp_labels,
        species_ids=sp_ids,
        species_charges=charges_arr,
        species_phases=sp_phases,
        log_beta_eff=log_beta_eff,
        stoich_pq=stoich_pq,
        stoich_r=stoich_r,
        stoich_s=stoich_s,
        nu_matrix=nu_matrix,
        C_total=C_total,
        log_beta_thermo=log_beta_thermo,
        aq_activity_delta_z2=aq_activity_delta_z2,
        n_diss=N_diss,
        diss_labels=diss_labels,
        diss_logK=diss_logK,
        log_K_diss_thermo=diss_logK_thermo,
        diss_activity_delta_z2=diss_activity_delta_z2,
        diss_stoich_pq=diss_stoich_pq,
        diss_r=diss_r,
        diss_s=diss_s,
        diss_nu=diss_nu,
        spec_id_to_name=spec_id_to_name,
        element_to_ids=element_to_ids,
        calculation_species_by_principal_element=(
            calculation_species_by_principal_element
        ),
    )
    from support_TD_helpers.activity_model_entry_point import (
        recompute_activity_at_I,
    )
    log_beta_eff, diss_logK_eff = recompute_activity_at_I(built, I_eff)
    np.copyto(built.log_beta_eff, log_beta_eff)
    np.copyto(built.diss_logK, diss_logK_eff)
    return built
