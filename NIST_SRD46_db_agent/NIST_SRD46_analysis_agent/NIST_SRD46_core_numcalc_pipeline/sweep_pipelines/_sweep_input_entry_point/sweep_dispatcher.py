"""
sweep_dispatcher.py
===================
Unified entry point for all sweep methods.

Provides:
  - ``parse_source``        — card path / dict / FreeEnergyReport → FreeEnergyReport
  - ``build_solver_chain``  — FreeEnergyReport → (BuiltSystem, solve_fn)
  - ``run_sweep``           — one-call dispatcher for pH / pourbaix sweeps

Every sweep method reuses the same solver construction path, ensuring
grid refinement and topology are always available.
"""
from __future__ import annotations

import pathlib
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

import numpy as np

if TYPE_CHECKING:
    from .constraint_compiler import CompiledConstraints


# ── Source parsing ──────────────────────────────────────────────

def parse_source(
    source: Union[str, pathlib.Path, dict, object],
    temperature_K: Optional[float] = None,
) -> "FreeEnergyReport":
    """
    Normalise *source* to a ``FreeEnergyReport``.

    Accepts a ``.md`` card path, a JSON path, a dict, or a pre-built report.
    """
    from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
        compute_free_energy_network,
        FreeEnergyReport,
    )

    if isinstance(source, FreeEnergyReport):
        return source

    if isinstance(source, (str, pathlib.Path)):
        p = pathlib.Path(source)
        if p.suffix == ".md":
            from free_energy_md_card_reader import parse_free_energy_card_md
            return parse_free_energy_card_md(p)
        return compute_free_energy_network(source, temperature_K=temperature_K)

    return compute_free_energy_network(source, temperature_K=temperature_K)


# ── Solver chain construction ──────────────────────────────────

def build_solver_chain(
    report: "FreeEnergyReport",
    *,
    ionic_strength: Optional[float] = None,
    system_name: str = "",
    compiled_constraints: Optional["CompiledConstraints"] = None,
) -> Tuple["BuiltSystem", Callable]:
    """
    Build a BuiltSystem and a Pourbaix-style ``solve_fn``
    ``(coords: dict, x0: ndarray|None) -> PointResult``
    from a ``FreeEnergyReport``.

    The returned ``solve_fn`` requires ``"pH"`` and optionally ``"a_w"``.
    It also requires ``"E_V"`` when redox is enabled; when redox is
    excluded the potential coordinate must be absent.

    When ``compiled_constraints`` is supplied, the wrapper additionally:

    * Resolves every explicitly declared catalog DOF for the cell.
    * Computes a per-cell ``C_total`` array from ``[<element>]_total`` /
      ``[<ligand_db_id>]_total`` / ``[<internal_id>]_total`` resolved
      values, replacing the BuiltSystem baseline.
    * Reads ``pH`` / ``E_V`` / ``a_w`` from the derived DOF dict if not
      already supplied in ``coords``.

    Without ``compiled_constraints``, coordinates must contain every active
    DOF explicitly and ``C_total`` is the already-declared BuiltSystem
    baseline; no physical input is synthesized.
    """
    from _input_solver_helper.built_system_from_dGreport import (
        build_from_free_energy_report,
        DissolutionProxy,
        SpeciesProxy,
    )
    from numerical_solvers.point_solver import PourbaixPointSolver
    from numerical_solvers.solid_manager import SolidManager
    from solvers_and_topology.nd_grid import PointResult

    built = build_from_free_energy_report(
        report,
        ionic_strength=ionic_strength,
        system_name=system_name,
    )

    pt_solver = PourbaixPointSolver(
        built.log_beta_eff, built.stoich_pq,
        built.stoich_r, built.stoich_s,
        built.nu_matrix, built.n_basis,
    )

    n_metals = len(built.element_names)
    diss_proxies = []
    for i in range(built.n_diss):
        diss_proxies.append(DissolutionProxy(
            logK=built.diss_logK[i],
            stoich_pq_row=built.diss_stoich_pq[i],
            stoich_H=built.diss_r[i],
            stoich_e=built.diss_s[i],
            nu_row=built.diss_nu[i],
            n_metals=n_metals,
            label=(built.diss_labels[i]
                   if i < len(built.diss_labels) else f"solid_{i}"),
        ))

    sp_proxies = [
        SpeciesProxy(sid, lbl)
        for sid, lbl in zip(built.species_ids, built.species_labels)
    ]

    solid_mgr = SolidManager(
        pt_solver, diss_proxies, built.n_basis,
        sp_proxies, built=built,
    )

    base_C_total = built.C_total.copy()
    base_log_beta = pt_solver.log_beta_eff.copy()
    base_diss_logK = (solid_mgr.diss_logK.copy()
                      if built.n_diss > 0 else np.array([]))
    stoich_w_aq = np.maximum(0.0, -built.stoich_r)
    stoich_w_diss = (np.maximum(0.0, -built.diss_r)
                     if built.n_diss > 0 else np.array([]))

    # ── Pre-build the totals-LHS → basis-index lookup table when
    #    constraints are supplied. The lookup covers the three forms:
    #      - "[<element>]_total"        → metal basis slot for that element
    #      - "[<internal_id>]_total"    → metal basis slot for that valence
    #                                     (mapped through the catalog's
    #                                     metal redox_states)
    #      - "[<ligand_db_id>]_total"   → ligand basis slot for that ligand
    catalog = (compiled_constraints.catalog
               if compiled_constraints is not None else None)
    totals_lookup: Dict[str, int] = {}
    element_lhs: set = set()
    if catalog is not None:
        elem_to_idx = {name: i for i, name in enumerate(built.element_names)}
        basis_token_to_idx = {
            token: i for i, token in enumerate(built.basis_tokens[:n_metals])
        }
        include_redox = getattr(report, "include_redox", "Not defined")
        if not isinstance(include_redox, bool):
            raise ValueError("redox mode is 'Not defined' on the solver report")
        for m in catalog.chemical_system.metals:
            redox_ids = list(m.redox_states or [])
            if not include_redox and len(redox_ids) > 1:
                # Each valence is an independent basis component.  Do not
                # route an element total to any one of them.
                for rid in redox_ids:
                    idx = basis_token_to_idx.get(rid, elem_to_idx.get(rid))
                    if idx is not None:
                        totals_lookup[f"[{rid}]_total"] = idx
                continue
            idx = elem_to_idx.get(m.element)
            if idx is None and len(redox_ids) == 1:
                idx = elem_to_idx.get(redox_ids[0])
            if idx is None:
                continue
            elem_key = f"[{m.element}]_total"
            totals_lookup[elem_key] = idx
            element_lhs.add(elem_key)
            if m.name != m.element:
                totals_lookup[f"[{m.name}]_total"] = idx
                element_lhs.add(f"[{m.name}]_total")
            if m.db_id:
                totals_lookup[f"[{m.db_id}]_total"] = idx
                element_lhs.add(f"[{m.db_id}]_total")
            for rid in redox_ids:
                totals_lookup[f"[{rid}]_total"] = idx
            if m.internal_id not in m.redox_states:
                totals_lookup[f"[{m.internal_id}]_total"] = idx
        l_ids = list(getattr(report, "ligand_ids", []) or [])
        lid_to_idx = {lid: n_metals + j for j, lid in enumerate(l_ids)}
        for L in catalog.chemical_system.ligands:
            idx = lid_to_idx.get(L.internal_id)
            if idx is None:
                continue
            totals_lookup[f"[{L.db_id}]_total"] = idx
            if L.internal_id and L.internal_id != L.db_id:
                totals_lookup[f"[{L.internal_id}]_total"] = idx

    # Resolve report-level species/component names to the numerical rows and
    # basis slots used by the augmented solver.  Compilation has already
    # guaranteed one distinct released component per pin.
    compiled_species_pins = (
        list(getattr(compiled_constraints, "species_pins", []) or [])
        if compiled_constraints is not None else [])
    if compiled_species_pins:
        species_rows: Dict[str, List[int]] = {}
        for row, species_id in enumerate(built.species_ids):
            species_rows.setdefault(str(species_id), []).append(row)
        released_indices: List[int] = []
        for pin in compiled_species_pins:
            rows = species_rows.get(str(pin.species_id), [])
            if len(rows) != 1:
                raise ValueError(
                    f"species pin {pin.species_id!r} resolves to "
                    f"{len(rows)} aqueous rows; exactly one is required")
            total_key = f"[{pin.released_component_token}]_total"
            component_idx = totals_lookup.get(total_key)
            if component_idx is None:
                raise ValueError(
                    f"released component {pin.released_component_token!r} "
                    "does not map to a numerical basis slot")
            if component_idx in released_indices:
                raise ValueError(
                    f"multiple species pins release basis slot "
                    f"{component_idx}; releases must be distinct")
            pin.aqueous_row = rows[0]
            pin.released_component = component_idx
            released_indices.append(component_idx)
        compiled_constraints.released_totals = released_indices

    # ── Phase-B (outer-Brent) plan ─────────────────────────────────
    # When the compiler emitted a redox-state sub-total pin and E_V is a
    # *free* scalar (not a sweep axis), each cell root-finds E_V so the
    # solved sub-total of the pinned oxidation state matches the per-cell
    # target.  Build the per-pin species masks once: a species carries
    # the metal in oxidation state ``redox_token`` when its (report)
    # stoichiometry has a non-zero coefficient for that internal id.
    phase_b_plan: List[Dict[str, Any]] = []
    _pb_pins = (list(getattr(compiled_constraints, "phase_b_pins", []))
                if compiled_constraints is not None else [])
    if _pb_pins:
        aq_stoich: Dict[str, Dict[str, float]] = {}
        diss_stoich: Dict[str, Dict[str, float]] = {}
        for s in (getattr(report, "species", []) or []):
            st = dict(getattr(s, "stoich", None) or {})
            if getattr(s, "phase", "aqueous") == "aqueous":
                aq_stoich[s.species_id] = st
            else:
                diss_stoich[s.species_id] = st
                lbl = getattr(s, "label", None)
                if lbl:
                    diss_stoich.setdefault(lbl, st)
        for pin in _pb_pins:
            rt = pin.redox_token
            aq_coeff = {sid: float(st[rt])
                        for sid, st in aq_stoich.items() if st.get(rt)}
            solid_coeff = {k: float(st[rt])
                           for k, st in diss_stoich.items() if st.get(rt)}
            phase_b_plan.append({
                "pin": pin,
                "aq": aq_coeff,
                "solid": solid_coeff,
                "elem_slot": totals_lookup.get(f"[{pin.element}]_total"),
            })

    def _resolve_per_cell(coords: Dict[str, float]
                          ) -> Tuple[float, Optional[float], Optional[float],
                                     np.ndarray, Dict[str, Any]]:
        """Apply constraints and return physical DOFs plus evaluated values."""
        if compiled_constraints is None:
            pH_raw = coords.get("pH")
            if pH_raw is None:
                raise ValueError(
                    "pH is 'Not defined' at this grid cell; declare an axis")
            pH = float(pH_raw)
            if not np.isfinite(pH):
                raise ValueError(f"pH evaluated to non-finite value {pH_raw!r}")
            include_redox = getattr(report, "include_redox", "Not defined")
            if not isinstance(include_redox, bool):
                raise ValueError("redox mode is 'Not defined' on the solver report")
            E_raw = coords.get("E_V")
            if include_redox:
                if E_raw is None:
                    raise ValueError(
                        "E_V is 'Not defined' while redox is enabled; "
                        "declare an axis or bind")
                E_V = float(E_raw)
                if not np.isfinite(E_V):
                    raise ValueError(
                        f"E_V evaluated to non-finite value {E_raw!r}")
            else:
                if E_raw is not None:
                    raise ValueError(
                        "E_V was supplied while redox is excluded; potential "
                        "must be absent rather than ignored")
                E_V = None
            a_w_raw = coords.get("a_w", None)
            a_w = None if a_w_raw is None else float(a_w_raw)
            if a_w is not None and (not np.isfinite(a_w) or a_w <= 0):
                raise ValueError(
                    f"a_w must evaluate to a finite value > 0, got {a_w_raw!r}")
            return pH, E_V, a_w, base_C_total, {}

        derived = compiled_constraints.apply(coords)
        # pH / E_V / a_w with per-cell precedence: explicit constraint,
        # then explicit coordinate.  Physical fallbacks are forbidden.
        pH_raw = derived.get("pH", coords.get("pH"))
        if pH_raw is None:
            raise ValueError(
                "pH is 'Not defined' at this grid cell; declare an axis or bind")
        pH = float(pH_raw)
        if not np.isfinite(pH):
            raise ValueError(f"pH evaluated to non-finite value {pH_raw!r}")
        include_redox = getattr(report, "include_redox", "Not defined")
        if not isinstance(include_redox, bool):
            raise ValueError("redox mode is 'Not defined' on the solver report")
        E_raw = derived.get("E_V", coords.get("E_V"))
        if include_redox:
            if E_raw is None:
                if phase_b_plan:
                    # Phase-B owns the one free electron-potential DOF and
                    # determines it from the compiled state-subtotal target.
                    E_V = None
                else:
                    raise ValueError(
                        "E_V is 'Not defined' while redox is enabled; "
                        "declare an axis/fixed/formula bind or redox='solve' "
                        "with one state-subtotal target")
            else:
                E_V = float(E_raw)
                if not np.isfinite(E_V):
                    raise ValueError(
                        f"E_V evaluated to non-finite value {E_raw!r}")
        else:
            # Potential is absent when valence components are independent.
            if E_raw is not None:
                raise ValueError(
                    "E_V was supplied while redox is excluded; potential "
                    "must be absent rather than ignored")
            E_V = None
        a_w_raw = derived.get("a_w", coords.get("a_w", None))
        a_w = None if a_w_raw is None else float(a_w_raw)
        if a_w is not None and (not np.isfinite(a_w) or a_w <= 0):
            raise ValueError(
                f"a_w must evaluate to a finite value > 0, got {a_w_raw!r}")

        # Build C_total from element/redox/ligand totals. Element-LHS
        # bindings (``[<element>]_total``) win over redox-resolved
        # entries pointing at the same slot; if no element binding is
        # given, redox-resolved entries are summed.
        Cnew = base_C_total.copy()
        slot_value: Dict[int, float] = {}
        slot_has_element: Dict[int, bool] = {}
        for lhs, idx in totals_lookup.items():
            if lhs not in derived:
                continue
            val = derived[lhs]
            if (not isinstance(val, (int, float))
                    or isinstance(val, bool)
                    or not np.isfinite(float(val))
                    or float(val) < 0):
                raise ValueError(
                    f"declared total {lhs} evaluated to invalid per-cell "
                    f"value {val!r} at coordinates {coords}")
            if lhs in element_lhs:
                slot_value[idx] = float(val)
                slot_has_element[idx] = True
            else:
                if slot_has_element.get(idx):
                    continue
                cur = slot_value.get(idx)
                slot_value[idx] = float(val) if cur is None else cur + float(val)
        for idx, v in slot_value.items():
            Cnew[idx] = v

        return pH, E_V, a_w, Cnew, derived

    def solve_fn(coords: Dict[str, float],
                 x0: Optional[np.ndarray]) -> PointResult:
        pH, E_V, a_w, C_total, derived = _resolve_per_cell(coords)
        if a_w is not None and a_w < 1.0:
            log_aw = np.log10(a_w)
            pt_solver.log_beta_eff[:] = base_log_beta + stoich_w_aq * log_aw
            if built.n_diss > 0:
                solid_mgr.diss_logK[:] = base_diss_logK + stoich_w_diss * log_aw
        else:
            pt_solver.log_beta_eff[:] = base_log_beta
            if built.n_diss > 0:
                solid_mgr.diss_logK[:] = base_diss_logK
        # Phase-B: root-find a free E_V so the pinned redox-state
        # sub-total is met.  Only active when a pin was emitted *and*
        # E_V is not itself a grid coordinate (standard Pourbaix sweeps
        # supply E_V in ``coords`` and are therefore untouched).
        if phase_b_plan and ("E_V" not in coords):
            plan = phase_b_plan[0]
            target = derived.get(plan["pin"].total_key)
            if isinstance(target, (int, float)):
                return _solve_phase_b(pH, C_total, x0, plan, float(target))
        pin_plan = (compiled_constraints.resolve_pins(derived)
                    if compiled_species_pins else None)
        return solid_mgr.solve_point(
            pH, E_V, C_total, x0=x0, pin_plan=pin_plan)

    def _redox_subtotal(res: PointResult, plan: Dict[str, Any]) -> float:
        """Solved total of the pinned oxidation state (aqueous + solid)."""
        tot = 0.0
        conc = res.conc or {}
        for sid, c in plan["aq"].items():
            tot += conc.get(sid, 0.0) * c
        solids = plan["solid"]
        if solids and res.solid_amounts:
            for k, amt in res.solid_amounts.items():
                c = solids.get(k)
                if c:
                    tot += amt * c
        return tot

    def _solve_phase_b(pH: float, C_total: np.ndarray,
                       x0: Optional[np.ndarray], plan: Dict[str, Any],
                       target: float) -> PointResult:
        """Bracket-and-bisect a free E_V so the redox sub-total == target."""
        from scipy.optimize import brentq

        last: Dict[str, PointResult] = {}

        def _at(E: float) -> Tuple[PointResult, float]:
            res = solid_mgr.solve_point(pH, E, C_total, x0=x0)
            last["res"] = res
            return res, _redox_subtotal(res, plan)

        def f(E: float) -> float:
            _, s = _at(E)
            return s - target

        E_lo, E_hi = -2.0, 2.5
        f_lo, f_hi = f(E_lo), f(E_hi)
        tries = 0
        while f_lo * f_hi > 0.0 and tries < 6:
            if abs(f_lo) <= abs(f_hi):
                E_lo -= 1.0
                f_lo = f(E_lo)
            else:
                E_hi += 1.0
                f_hi = f(E_hi)
            tries += 1

        if f_lo * f_hi > 0.0:
            # Target unreachable across the bracket: clamp to the closest
            # extreme and flag the cell as not satisfying the constraint.
            E_clamp = E_lo if abs(f_lo) < abs(f_hi) else E_hi
            res, _ = _at(E_clamp)
            try:
                res.converged = False
            except Exception:
                pass
            return res

        E_star = brentq(f, E_lo, E_hi, xtol=1e-5, rtol=8.9e-7, maxiter=100)
        res, _ = _at(E_star)
        return res

    return built, solve_fn


# ── Unified sweep dispatcher ──────────────────────────────────

def run_sweep(
    source: Union[str, pathlib.Path, dict, object],
    sweep_type: str = "pourbaix",
    *,
    output_dir: Optional[str] = None,
    temperature_K: Optional[float] = None,
    ionic_strength: Optional[float] = None,
    debug: bool = False,
    compiled_constraints: Optional["CompiledConstraints"] = None,
    **sweep_params,
) -> Dict[str, Any]:
    """
    Run a sweep end-to-end: parse source → build solver → sweep → output.

    Parameters
    ----------
    source : str | Path | dict | FreeEnergyReport
        Free energy card (.md), JSON path, dict, or pre-built report.
    sweep_type : str
        ``"pH"`` | ``"pourbaix"`` (i.e. ``"pourbaix_sweep"``).  The
        unified Pourbaix handler infers dimensionality (1-D ~ N-D) from
        the axes supplied in ``sweep_params``; declare an ``aw_range``
        to upgrade a 2-D pH x E sweep to 3-D.
    output_dir : str, optional
        Output directory (created if needed).
    temperature_K : float, optional
        Override temperature.
    ionic_strength : float, optional
        Override ionic strength.
    debug : bool
        Print progress messages.
    **sweep_params
        Additional parameters forwarded to the sweep function.

    Returns
    -------
    dict with keys depending on sweep_type:
      - ``"report"``          : FreeEnergyReport  (always)
      - ``"built"``           : BuiltSystem       (pourbaix)
      - ``"grid"``            : NDGrid            (pourbaix)
      - ``"results"``         : list              (pH)
      - ``"output_paths"``    : list of str       (always)
      - ``"all_boundaries"``  : dict              (pourbaix)
    """
    dispatch = {
        "pH":             _run_pH,
        "ph":             _run_pH,
        "pH_sweep":       _run_pH,
        "pourbaix":       _run_pourbaix,
        "pourbaix_sweep": _run_pourbaix,
        "titration":       _run_titration_sweep,
        "titration_sweep": _run_titration_sweep,
        "freeform":        _run_freeform,
        "freeform_sweep":  _run_freeform,
    }

    fn = dispatch.get(sweep_type)
    if fn is None:
        raise ValueError(
            f"Unknown sweep_type '{sweep_type}'. "
            f"Available: {sorted(dispatch.keys())}"
        )

    report = parse_source(source, temperature_K=temperature_K)

    # The top-level calculation adapter forwards these explicit card settings
    # for every route, including Pourbaix/freeform routes whose local function
    # signatures do not otherwise consume them.  Attach them before any route
    # builds its solver so solids exclusion and activity selection are uniform.
    if "include_solids" in sweep_params:
        include_solids = sweep_params["include_solids"]
        if not isinstance(include_solids, bool):
            raise ValueError("include_solids must be an explicitly declared boolean")
        report.include_solids = include_solids
    if "use_activity" in sweep_params:
        use_activity = sweep_params["use_activity"]
        if not isinstance(use_activity, bool):
            raise ValueError("use_activity must be an explicitly declared boolean")
        report.activity_model = "davies" if use_activity else "ideal"

    return fn(
        report,
        output_dir=output_dir,
        ionic_strength=ionic_strength,
        debug=debug,
        compiled_constraints=compiled_constraints,
        **sweep_params,
    )


# ── pH sweep ──────────────────────────────────────────────────

def _run_pH(
    report,
    *,
    output_dir: Optional[str] = None,
    ionic_strength: Optional[float] = None,
    debug: bool = False,
    compiled_constraints: Optional["CompiledConstraints"] = None,
    **params,
) -> Dict[str, Any]:
    """Dispatch to the unified 1-D pH sweep handler.

    ``run_pH_sweep`` now returns a dict with the same shape as
    ``_run_pourbaix`` (``report``, ``built``, ``grid``, ``topology``,
    ``speciation_curve``, ``output_paths``); plus a back-compat
    ``results`` alias resolved from ``speciation_curve.results`` for
    callers that still expect a list of point results.
    """
    from sweep_pipelines.pH_sweep.pH_sweep_main import run_pH_sweep

    total_metals = params.pop("total_metals", None)
    total_ligands = params.pop("total_ligands", None)
    # The report has already passed the strict declaration gate.
    if total_metals is None and report.metal_ids:
        total_metals = [report.total_metals[mid]
                        for mid in report.metal_ids]
    if total_ligands is None and report.ligand_ids:
        total_ligands = [report.total_ligands[lid]
                         for lid in report.ligand_ids]

    for required in ("pH_range", "n_points", "include_solids", "use_activity"):
        if required not in params:
            raise ValueError(
                f"pH_sweep physical/model input {required!r} is 'Not defined'")

    result = run_pH_sweep(
        report, total_metals, total_ligands,
        pH_range=params["pH_range"],
        n_points=params["n_points"],
        output_dir=output_dir,
        ionic_strength=ionic_strength,
        include_solids=params["include_solids"],
        use_activity=params["use_activity"],
        debug=debug,
        prefix=params.get("prefix"),
        compiled_constraints=compiled_constraints,
    )

    # Back-compat alias: legacy callers expect ``results`` as a list.
    curve = result.get("speciation_curve")
    if curve is not None:
        result.setdefault("results", curve.results)
    return result


# ── N-D Pourbaix sweep (1-D ~ 3-D, unified) ──────────────────

def _run_pourbaix(
    report,
    *,
    output_dir: Optional[str] = None,
    ionic_strength: Optional[float] = None,
    debug: bool = False,
    compiled_constraints: Optional["CompiledConstraints"] = None,
    **params,
) -> Dict[str, Any]:
    """Unified Pourbaix dispatcher entry point.

    Forwards to ``pourbaix_sweep.run_pourbaix_sweep`` which is N-D-aware.
    The grid dimensionality is implied by which axis-range / axis-N
    kwargs are present:

        * ``pH_range`` + ``n_pH``  → pH axis
        * ``E_range``  + ``n_E``   → E_V axis
        * ``aw_range`` + ``n_aw``  → a_w axis

    Any non-empty subset is accepted (1-D ~ 3-D today; trivially
    extends to higher dimensionality if more axes are added).  Passing
    just ``pH_range``/``E_range``/``n_pH``/``n_E`` reproduces the
    classical 2-D Pourbaix sweep; adding ``aw_range``/``n_aw`` upgrades
    it to 3-D.
    """
    from sweep_pipelines.pourbaix_sweep.pourbaix_sweep_main import run_pourbaix_sweep
    from sweep_pipelines._sweep_input_entry_point.grid_refinement_contract import (
        normalize_grid_refinement,
    )

    pH_range = params.get("pH_range")
    E_range  = params.get("E_range")
    aw_range = params.get("aw_range")
    n_pH = params.get("n_pH")
    n_E  = params.get("n_E")
    n_aw = params.get("n_aw")

    if pH_range is None and E_range is None and aw_range is None:
        raise ValueError(
            "Pourbaix sweep axes are 'Not defined'; declare every range "
            "and point count in the calculation card")
    if "coarse_only" in params:
        raise ValueError(
            "coarse_only is no longer accepted by the calculation dispatcher; "
            "declare n_layers=0 to disable refinement"
        )
    missing_refinement = [
        key for key in ("n_layers", "refine_factor") if key not in params
    ]
    if missing_refinement:
        raise ValueError(
            "Pourbaix refinement declaration is incomplete: missing "
            + ", ".join(missing_refinement)
        )
    n_layers, refine_factor = normalize_grid_refinement(
        n_layers=params["n_layers"],
        factor=params["refine_factor"],
        context="Pourbaix refinement",
    )

    grid, built, all_boundaries, output_paths = run_pourbaix_sweep(
        report,
        pH_range=pH_range, E_range=E_range, aw_range=aw_range,
        n_pH=n_pH, n_E=n_E, n_aw=n_aw,
        output_dir=output_dir,
        ionic_strength=ionic_strength,
        refine_factor=refine_factor,
        n_layers=n_layers,
        debug=debug,
        compiled_constraints=compiled_constraints,
    )

    return {
        "report": report,
        "built": built,
        "grid": grid,
        "all_boundaries": all_boundaries,
        "output_paths": output_paths,
    }


# ── N-D Pourbaix sweep — unified handler ────────────────────────
#
# As of the N-D Pourbaix unification, ``_run_pourbaix`` above handles
# 1-D ~ N-D sweeps in a single code path; the dimensionality is
# inferred from the axes supplied via ``sweep_params``.  The legacy
# ``_run_pourbaix_3d`` handler and the ``"pourbaix_2d"`` / ``"pourbaix_3d"``
# / ``"3d"`` aliases have been removed.
#
# Likewise ``_run_nernst_simple`` (single-couple Nernst E° sweep) has
# been migrated out of this package to
# ``NIST_SRD46_post_calc_tools/nernst_simple/`` and is no longer
# dispatchable here.


# ── Titration (volume sweep) ───────────────────────────────────

def _run_titration_sweep(
    report,
    *,
    output_dir: Optional[str] = None,
    ionic_strength: Optional[float] = None,
    debug: bool = False,
    compiled_constraints: Optional["CompiledConstraints"] = None,
    **params,
) -> Dict[str, Any]:
    """Dispatch to the titration (added-volume) sweep handler.

    ``params`` must include ``axes`` — a single added-volume axis spec
    ``{name, min, max, n_points}`` whose ``name`` identifies the titrant
    component.  Optional: ``volume_initial_mL``, ``titrant_conc``,
    ``fixed_pH``, ``prefix``.
    """
    from sweep_pipelines.titration_sweep.titration_sweep_main import (
        run_titration_sweep,
    )

    axes = params.pop("axes", None)
    if not axes:
        raise ValueError(
            "titration_sweep requires one 'axes' entry "
            "({name, min, max, n_points}) describing the added-volume range.")
    missing = [key for key in ("volume_initial_mL", "titrant_conc", "fixed_pH")
               if key not in params]
    if missing:
        raise ValueError(
            "titration physical inputs are 'Not defined': " + ", ".join(missing))

    return run_titration_sweep(
        report,
        axes=axes,
        output_dir=output_dir,
        ionic_strength=ionic_strength,
        volume_initial_mL=float(params["volume_initial_mL"]),
        titrant_conc=float(params["titrant_conc"]),
        fixed_pH=float(params["fixed_pH"]),
        debug=debug,
        prefix=params.get("prefix"),
        compiled_constraints=compiled_constraints,
    )



# ── Freeform (catch-all N-D) sweep ───────────────────────────────

def _run_freeform(
    report,
    *,
    output_dir: Optional[str] = None,
    ionic_strength: Optional[float] = None,
    debug: bool = False,
    compiled_constraints: Optional["CompiledConstraints"] = None,
    **params,
) -> Dict[str, Any]:
    """Dispatch to the generic N-D freeform sweep handler.

    ``params`` must include ``axes`` — a list of GridAxis or dicts
    ``{name, min, max, n_points}`` — plus the explicit ``n_layers`` and
    ``refine_factor`` refinement declaration.  ``prefix`` is optional.
    """
    from sweep_pipelines.freeform_sweep.freeform_sweep_main import (
        run_freeform_sweep,
    )

    axes = params.pop("axes", None)
    if not axes:
        raise ValueError(
            "freeform_sweep requires at least one entry in 'axes' "
            "(list of GridAxis or {name, min, max, n_points} dicts)."
        )
    if "coarse_only" in params:
        raise ValueError(
            "coarse_only has been removed from freeform_sweep; declare "
            "n_layers=0 and refine_factor=None to disable refinement"
        )
    missing_refinement = [
        key for key in ("n_layers", "refine_factor") if key not in params
    ]
    if missing_refinement:
        raise ValueError(
            "freeform refinement declaration is incomplete: missing "
            + ", ".join(missing_refinement)
        )

    return run_freeform_sweep(
        report,
        axes=axes,
        output_dir=output_dir,
        ionic_strength=ionic_strength,
        refine_factor=params["refine_factor"],
        n_layers=params["n_layers"],
        debug=debug,
        prefix=params.get("prefix"),
        compiled_constraints=compiled_constraints,
    )
