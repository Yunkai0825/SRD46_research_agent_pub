"""
curve_builder.py
================
Build a ``SpeciationCurve`` from a unified-pipeline 1-D ``NDGrid``.

Sits **downstream of** ``_output_topology_compactor``: the canonical
data flow for any 1-D speciation sweep is

    NDGridSolver â†’ NDGrid â†’ topology_nd â†’ compact_topology_nd
                  â†’ curve_builder â†’ SpeciationCurve â†’ CSV + plots

The same ``PointResult`` grid that produced the topology is folded
back into a ``SpeciationCurve`` so the speciation export pipeline
(``pH_sweep_export.generate_all_output``) can consume it.

Public API
----------
- ``build_speciation_curve_from_grid_1d``  â€” primary entry point.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.thermodynamics_helpers.speciation_dataclasses import (
    Equilibrium,
    PointResult as SpecPointResult,
    Species,
    SpeciationCurve,
    SpeciesType,
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _classify_species(stoich: Dict[str, int]) -> SpeciesType:
    """Heuristic mapping ``stoich`` -> ``SpeciesType`` enum."""
    has_metal = any(k.startswith("M") and k != "M0" for k in stoich)
    has_ligand = any(k.startswith("L") and k != "L0" for k in stoich)
    if has_metal and has_ligand:
        return SpeciesType.COMPLEX
    if has_metal:
        return SpeciesType.METAL
    if has_ligand:
        return SpeciesType.PROTONATED_LIGAND
    h = stoich.get("H", 0)
    if h > 0:
        return SpeciesType.PROTON
    return SpeciesType.HYDROXIDE


def _resolve_species_label(sp, stoich: Dict[str, int]) -> str:
    """Return a display label for a species, naming the solvent explicitly.

    The upstream card sometimes leaves the water self-ion product
    (neutral ``H``/``OH`` association) unresolved with a ``?`` / ``[?]``
    label, which then leaks into the CSV header, the verdict table and
    the plots. Detect that species structurally (no metal/ligand atoms,
    neutral, built only from solvent constituents — or simply an
    unresolved ``?`` with no stoichiometry) and name it ``H2O``.
    """
    label = getattr(sp, "label", None) or sp.species_id
    lbl = str(label).strip()
    keys = set(stoich or {})
    charge = int(getattr(sp, "charge", 0) or 0)
    solvent_only = bool(keys) and keys <= {"H", "OH", "O"} and charge == 0
    if solvent_only or (lbl in {"?", "[?]", ""} and not keys):
        return "H2O"
    return label


def _normalize_species_phase(phase: Any) -> str:
    """Translate free-energy-card phase names to curve semantics.

    The thermodynamic card calls a solid-forming equilibrium
    ``"dissolution"``.  ``SpeciationCurve`` and its plotters instead use
    ``"solid"`` for the resulting condensed species.  Keeping the card
    spelling here caused precipitated phases to appear in component
    fractions (which use ``solid_amounts`` directly) but disappear from the
    total/log-concentration representation (which filters on ``phase``).
    """

    normalized = str(phase or "aqueous").strip().lower()
    return "solid" if normalized == "dissolution" else normalized


def _build_species_dict(report) -> Dict[str, Species]:
    species: Dict[str, Species] = {}
    for sp in report.species:
        if not getattr(sp, "include", True):
            continue
        stoich = dict(getattr(sp, "stoich", {}) or {})
        species[sp.species_id] = Species(
            id=sp.species_id,
            label=_resolve_species_label(sp, stoich),
            stype=_classify_species(stoich),
            charge=getattr(sp, "charge", 0),
            phase=_normalize_species_phase(getattr(sp, "phase", "aqueous")),
            stoich=stoich,
            stoich_hlx=getattr(sp, "stoich_hlx", None),
            mu0_free_kJ=getattr(sp, "mu0_free", None),
            mu0_canonical_kJ=getattr(sp, "mu0_canonical", None),
        )
    return species


def _build_equilibria(report) -> List[Equilibrium]:
    eqs: List[Equilibrium] = []
    for rxn in getattr(report, "reactions", []):
        if not getattr(rxn, "include", True):
            continue
        eqs.append(Equilibrium(
            id=getattr(rxn, "eq_id", ""),
            label=getattr(rxn, "label", ""),
            log_k=float(getattr(rxn, "log_beta", 0.0)),
            species_id=getattr(rxn, "species_id", ""),
            stoich=dict(getattr(rxn, "stoich", {}) or {}),
        ))
    return eqs


def _compute_fractions(
    conc: Dict[str, float],
    species: Dict[str, Species],
    component_ids: List[str],
    component_totals: Dict[str, float],
    solid_amounts: Optional[Dict[str, float]] = None,
    component_members: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Dict[str, float]]:
    """Return ``{component_id: {species_id: fraction}}``.

    Fraction = (n_component_in_species * conc[species]) / total[component].

    ``component_members`` maps a public balance key to the stoichiometric
    tokens represented by that balance.  In a redox-enabled calculation the
    public key is the physical element (for example ``"Cu"``) and its
    members are all aligned oxidation-state tokens (for example
    ``["Cu$+1", "Cu$+2"]``).  With redox excluded every oxidation state
    remains an independent one-member component.

    Solids do not have an aqueous concentration, so they would silently
    drop out of the fraction display, making it look as if the component
    "vanished" once it precipitated.  To keep the speciation plot
    mass-conserving, every active solid contributes its precipitated
    share of the component total under the *same species id* as the
    aqueous species table uses (e.g. ``Fe2O3``, ``[Fe(OH)3](s)``).
    Real (aqueous) species + the solid entries sum to 1.0 at
    convergence and the plotter picks them up natively because solids
    are already members of ``curve.species``.
    """
    out: Dict[str, Dict[str, float]] = {}
    solid_amounts = solid_amounts or {}
    component_members = component_members or {
        cid: [cid] for cid in component_ids
    }
    # ``solid_amounts`` is keyed by the dissolution-equation id, which the
    # built-system layer sets to the species ``label`` (e.g. ``[Cu(OH)2](s)``),
    # NOT to ``species_id`` (e.g. ``[Cu$+2].[OH]2.[z+0]_(s)``).  The species
    # dict here is keyed by ``species_id``, so a naive ``species.get(sid)``
    # would silently miss every precipitated phase and zero out the solid
    # column in the fraction CSV / plot.  Build a labelâ†’species lookup so
    # we can resolve either key and always store the contribution under the
    # canonical ``species_id`` that the exporter iterates.
    species_by_label: Dict[str, Species] = {
        sp.label: sp for sp in species.values() if getattr(sp, "label", None)
    }
    resolved_solids: Dict[str, float] = {}
    for key, amount in solid_amounts.items():
        sp = species.get(key) or species_by_label.get(key)
        if sp is None:
            continue
        value = float(amount)
        if value <= 0.0:
            continue
        resolved_solids[sp.id] = resolved_solids.get(sp.id, 0.0) + value

    for cid in component_ids:
        total = float(component_totals.get(cid, 0.0))
        if total <= 0.0:
            out[cid] = {}
            continue
        members = list(dict.fromkeys(component_members.get(cid, [cid])))

        def _coefficient(sp: Species) -> float:
            return sum(float(sp.stoich.get(member, 0)) for member in members)

        d: Dict[str, float] = {}
        for sp_id, sp in species.items():
            # Solid amounts are injected into ``conc`` by ``_convert_point``
            # for concentration plots.  Fractions consume them only through
            # ``resolved_solids`` below so a condensed phase is counted once.
            if getattr(sp, "phase", "aqueous") == "solid":
                continue
            n = _coefficient(sp)
            if n == 0:
                continue
            c = float(conc.get(sp_id, 0.0))
            if c <= 0.0:
                continue
            d[sp_id] = (n * c) / total
        # Add precipitated solids using their real species id so the
        # plotter and CSV exporter (which both iterate curve.species)
        # display them without any special handling.
        for sid, n_solid in resolved_solids.items():
            sp = species.get(sid)
            if sp is None:
                continue
            n = _coefficient(sp)
            if n == 0 or n_solid <= 0.0:
                continue
            d[sp.id] = (n * float(n_solid)) / total
        out[cid] = d
    return out


def _metal_fraction_contract(
    report,
    built_system=None,
    *,
    include_redox: Optional[bool] = None,
) -> tuple[List[str], Dict[str, float], Dict[str, str], Dict[str, List[str]]]:
    """Return the public metal balances used by pH result artifacts.

    The numerical builder collapses aligned oxidation states into one basis
    row whenever redox is enabled.  The curve adapter must use that same
    physical balance: reporting fractions against the report-era per-state
    seed totals can give zero denominators or mutually incompatible Cu(I)
    and Cu(II) curves even though the solve conserved total Cu correctly.

    ``BuiltSystem`` metadata is authoritative in the production path.  The
    report-only branch retains a deterministic fallback for callers that
    construct curves directly, but follows the same valence-group contract.
    """
    report_ids = [str(mid) for mid in (getattr(report, "metal_ids", []) or [])]
    report_names = list(getattr(report, "metal_names", []) or [])
    report_totals = dict(getattr(report, "total_metals", {}) or {})
    if include_redox is None:
        include_redox = getattr(report, "include_redox", False) is True
    elif not isinstance(include_redox, bool):
        raise ValueError("include_redox must be an explicit boolean")

    if not include_redox:
        ids = report_ids
        totals = {mid: float(report_totals.get(mid, 0.0)) for mid in ids}
        names = {
            mid: str(report_names[i]) if i < len(report_names) else mid
            for i, mid in enumerate(ids)
        }
        return ids, totals, names, {mid: [mid] for mid in ids}

    if built_system is not None:
        ids = [
            str(element)
            for element in (getattr(built_system, "element_names", []) or [])
        ]
        raw_totals = list(getattr(built_system, "element_totals", []) or [])
        if len(ids) != len(raw_totals):
            raise ValueError(
                "redox-enabled pH result adapter received inconsistent "
                "BuiltSystem element_names/element_totals lengths"
            )
        totals = {cid: float(raw_totals[i]) for i, cid in enumerate(ids)}
        raw_members = dict(getattr(built_system, "element_to_ids", {}) or {})
        basis_tokens = list(getattr(built_system, "basis_tokens", []) or [])
        members: Dict[str, List[str]] = {}
        for i, cid in enumerate(ids):
            state_ids = [str(mid) for mid in (raw_members.get(cid, []) or [])]
            # Mixed systems can contain both a multi-valence group and a
            # single-valence element.  Older BuiltSystem maps omitted the
            # latter whenever any valence group existed; the basis token is
            # the unambiguous one-member fallback for that element row.
            if not state_ids and i < len(basis_tokens):
                state_ids = [str(basis_tokens[i])]
            members[cid] = list(dict.fromkeys(state_ids))
        return ids, totals, {cid: cid for cid in ids}, members

    # Direct-call fallback: aggregate each declared valence group, then keep
    # every ungrouped state as its own physical balance.
    ids: List[str] = []
    totals: Dict[str, float] = {}
    names: Dict[str, str] = {}
    members: Dict[str, List[str]] = {}
    grouped: set[str] = set()
    for group in (getattr(report, "valence_groups", []) or []):
        cid = str(getattr(group, "element", "") or "")
        state_ids = [
            str(entry.internal_id)
            for entry in (getattr(group, "entries", []) or [])
        ]
        if not cid or not state_ids:
            continue
        ids.append(cid)
        members[cid] = list(dict.fromkeys(state_ids))
        totals[cid] = sum(float(report_totals.get(mid, 0.0)) for mid in state_ids)
        names[cid] = cid
        grouped.update(state_ids)
    for i, mid in enumerate(report_ids):
        if mid in grouped:
            continue
        ids.append(mid)
        totals[mid] = float(report_totals.get(mid, 0.0))
        names[mid] = str(report_names[i]) if i < len(report_names) else mid
        members[mid] = [mid]
    return ids, totals, names, members


def _convert_point(
    pt,
    species: Dict[str, Species],
    metal_ids: List[str],
    ligand_ids: List[str],
    total_metals: Dict[str, float],
    total_ligands: Dict[str, float],
    pH: float,
    target_ionic_strength: float = 0.0,
    ionic_mode: str = "fixed",
    metal_component_members: Optional[Dict[str, List[str]]] = None,
) -> SpecPointResult:
    """Convert one unified ``PointResult`` -> ``speciation_dataclasses.PointResult``."""
    if pt is None or not getattr(pt, "converged", False):
        return SpecPointResult(
            pH=float(pH),
            converged=False,
            iters=int(getattr(pt, "iterations", 0)) if pt is not None else 0,
            residual=float(getattr(pt, "residual", 0.0)) if pt is not None else 0.0,
        )

    conc = dict(pt.conc)
    log_conc = dict(pt.log_conc)
    solid_amounts = dict(getattr(pt, "solid_amounts", {}) or {})

    # ``solid_amounts`` is keyed by dissolution-equation id, which equals
    # the species LABEL (e.g. ``[Cu(OH)2](s)``) â€” not the canonical
    # ``species_id`` (e.g. ``[Cu$+2].[OH]2.[z+0]_(s)``).  The aqueous
    # solver leaves ``conc``/``log_conc`` empty for every solid species,
    # so the CSV exporter and log-conc plotter (both iterate
    # ``curve.species.keys()`` and default missing entries to ``0.0``)
    # would render the solid as a flat line at ``log10 = 0`` (i.e. 1 M).
    # Populate ``conc``/``log_conc`` for every solid species using its
    # canonical ``species_id`` so downstream consumers see a real curve;
    # non-precipitated pH points get a very low floor that clips below
    # the plotter's ``min_log`` window.
    species_by_label: Dict[str, Species] = {
        sp.label: sp for sp in species.values() if getattr(sp, "label", None)
    }
    resolved_solids: Dict[str, float] = {}
    for k, n in solid_amounts.items():
        sp = species.get(k) or species_by_label.get(k)
        if sp is None:
            continue
        resolved_solids[sp.id] = resolved_solids.get(sp.id, 0.0) + float(n)
    _LOG_FLOOR = -50.0
    for sp in species.values():
        if getattr(sp, "phase", "aqueous") != "solid":
            continue
        n = resolved_solids.get(sp.id, 0.0)
        conc[sp.id] = n
        log_conc[sp.id] = math.log10(n) if n > 0.0 else _LOG_FLOOR

    frac_metals = _compute_fractions(
        conc, species, metal_ids, total_metals, solid_amounts,
        component_members=metal_component_members)
    frac_ligands = _compute_fractions(
        conc, species, ligand_ids, total_ligands, solid_amounts)

    # Single-component convenience copies (first metal / first ligand).
    frac_M = dict(frac_metals.get(metal_ids[0], {})) if metal_ids else {}
    frac_L = dict(frac_ligands.get(ligand_ids[0], {})) if ligand_ids else {}

    # Calculated ionic strength of the converged aqueous speciation:
    #   I = 0.5 * Σ c_i z_i²   (aqueous species only; solids excluded).
    # Use ``pt.conc`` (raw aqueous concentrations) rather than the local
    # ``conc`` copy, into which solid amounts were injected above for
    # plotting — those must NOT contribute to ionic strength.
    I_calc = 0.0
    for sid, c in pt.conc.items():
        sp = species.get(sid)
        if sp is None or getattr(sp, "phase", "aqueous") == "solid":
            continue
        z = int(getattr(sp, "charge", 0) or 0)
        if z == 0 or c <= 0.0:
            continue
        I_calc += c * z * z
    I_calc *= 0.5

    # Ionic strength actually used for activity coefficients: the fixed
    # target in "fixed" mode; in "auto" mode the per-point loop converges
    # to the solution's own ionic strength, i.e. ``I_calc``.
    I_used = (I_calc if str(ionic_mode).lower() == "auto"
              else float(target_ionic_strength))

    return SpecPointResult(
        pH=float(pH),
        conc=conc,
        log_conc=log_conc,
        frac_M=frac_M,
        frac_L=frac_L,
        converged=True,
        iters=int(pt.iterations),
        residual=float(pt.residual),
        frac_metals=frac_metals,
        frac_ligands=frac_ligands,
        solid_amounts=solid_amounts,
        ionic_strength_used=I_used,
        calculated_ionic_strength=I_calc,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Public API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_speciation_curve_from_grid_1d(
    report,
    grid,
    *,
    axis_name: str = "pH",
    system_name: Optional[str] = None,
    method: str = "free_energy",
    extras: Optional[Dict[str, Any]] = None,
    built_system=None,
    include_redox: Optional[bool] = None,
) -> SpeciationCurve:
    """Build a :class:`SpeciationCurve` from a 1-D ``NDGrid``.

    Parameters
    ----------
    report : FreeEnergyReport
        Source thermodynamic data (used for species, equilibria,
        component totals, names, temperature, ionic strength).
    grid : NDGrid
        Solved 1-D grid with one axis named *axis_name*.
    axis_name : str
        Name of the sweep axis (default ``"pH"``). For non-pH 1-D
        sweeps the values still occupy ``SpeciationCurve.pH_values``;
        callers can re-interpret them as needed.
    system_name : str, optional
        Override for ``SpeciationCurve.system_name``. Default: derived
        from ``report.metal_names`` and ``report.ligand_names``.
    method : str
        Provenance tag (``"free_energy"`` or ``"equilibrium_const"``).
    extras : dict, optional
        Additional provenance to stash on ``curve.run_params``.
    built_system : BuiltSystem, optional
        Solver bookkeeping used to expose redox-enabled metal fractions under
        physical parent-element keys and normalize them by the same element
        totals used in the numerical mass balance.
    include_redox : bool, optional
        Effective solver mode.  Production callers should pass the validated
        mode explicitly rather than relying on report attachment state.
    """
    if grid.ndim != 1:
        raise ValueError(
            f"build_speciation_curve_from_grid_1d: expected ndim=1, "
            f"got ndim={grid.ndim}"
        )
    if grid.axes[0].name != axis_name:
        raise ValueError(
            f"build_speciation_curve_from_grid_1d: axis[0].name="
            f"{grid.axes[0].name!r}, expected {axis_name!r}"
        )

    species = _build_species_dict(report)
    equilibria = _build_equilibria(report)

    (
        metal_ids,
        total_metals,
        metal_names,
        metal_component_members,
    ) = _metal_fraction_contract(
        report, built_system, include_redox=include_redox)
    ligand_ids = list(report.ligand_ids)
    total_ligands = dict(report.total_ligands)

    ligand_names = {
        lid: (report.ligand_names[i]
              if i < len(report.ligand_names) else lid)
        for i, lid in enumerate(ligand_ids)
    }

    target_ionic_strength = float(getattr(report, "ionic_strength", 0.0))
    ionic_mode = str(getattr(report, "ionic_mode", "fixed"))

    axis_values = grid.axes[0].values
    pH_values: List[float] = [float(v) for v in axis_values]
    results: List[SpecPointResult] = []
    for i in range(len(axis_values)):
        pt = grid.points[i]
        results.append(_convert_point(
            pt, species, metal_ids, ligand_ids,
            total_metals, total_ligands,
            pH=float(axis_values[i]),
            target_ionic_strength=target_ionic_strength,
            ionic_mode=ionic_mode,
            metal_component_members=metal_component_members,
        ))

    if system_name is None:
        sys_name = "-".join(
            list(report.metal_names) + list(report.ligand_names)
        ) or getattr(report, "system_name", "system")
    else:
        sys_name = system_name

    # Convenience scalars (single-component case).
    total_M = float(total_metals[metal_ids[0]]) if metal_ids else 0.0
    total_L = float(total_ligands[ligand_ids[0]]) if ligand_ids else 0.0

    curve = SpeciationCurve(
        system_name=sys_name,
        pH_values=pH_values,
        results=results,
        species=species,
        equilibria=equilibria,
        total_M=total_M,
        total_L=total_L,
        temperature=float(getattr(report, "temperature_C", 25.0)),
        ionic_str=float(getattr(report, "ionic_strength", 0.0)),
        ionic_mode=str(getattr(report, "ionic_mode", "fixed")),
        target_ionic_str=float(getattr(report, "ionic_strength", 0.0)),
        total_metals=total_metals,
        total_ligands=total_ligands,
        metal_names=metal_names,
        ligand_names=ligand_names,
        method=method,
    )

    if extras is not None:
        curve.run_params = dict(extras)

    return curve
