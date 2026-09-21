"""
pH_sweep_main.py - Unified 1-D pH speciation sweep.
====================================================

Runs a 1-D pH sweep on top of the **same** solver/topology stack used
by the N-D Pourbaix sweep:

    FreeEnergyReport
        -> build_from_free_energy_report  (BuiltSystem)
        -> PourbaixPointSolver + SolidManager  (Newton-Raphson + active-set)
        -> NDGridSolver(ndim=1)                (BFS continuation)
        -> label_grid_nd
        -> extract_topology_nd                 (0-D transitions on pH axis)
        -> compact_topology_nd                 (RDP-simplified features)
        -> build_speciation_curve_from_grid_1d (SpeciationCurve)
        -> generate_all_output                 (CSV + plots + verdict)

The legacy ``gibbs_solve_at_pH`` / ``GibbsPointResult`` / pH-only
auto-I helper have been removed: ``SolidManager.solve_point`` already
performs Newton-Raphson on the same mass-balance residual *and*
handles the auto-I outer loop when the report's ``ionic_mode`` is
``"auto"``.

Public API
----------
- ``run_pH_sweep`` - canonical entry point.
"""
from __future__ import annotations

import pathlib
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from solvers_and_topology.nd_grid import (
    GridAxis,
    NDGridSolver,
    PointResult,
)
from sweep_pipelines._output_and_plotting._output_topology_compactor.compact_nd import (
    compact_topology_nd,
)
from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_export import (
    export_topology_json,
)
from sweep_pipelines._output_and_plotting.speciation_curves.curve_builder import (
    build_speciation_curve_from_grid_1d,
)
from sweep_pipelines._sweep_input_entry_point.sweep_dispatcher import (
    build_solver_chain,
    parse_source,
)

from .pH_sweep_settings import DEFAULT_N_POINTS


# ------------------------------------------------------------------
#  1-D pH solve_fn adapter
# ------------------------------------------------------------------

def _make_pH_only_solve_fn(
    unified_solve_fn,
    *,
    include_redox: bool,
    fixed_E_V: Optional[float] = None,
):
    """
    Wrap the unified ``(coords, x0) -> PointResult`` callable so that
    callers supplying only a ``pH`` coordinate get the explicitly declared
    fixed potential.  When redox is explicitly excluded, the potential is
    absent and the wrapped coordinates are passed through without ``E_V``.

    A redox-enabled pH-only sweep must declare ``fixed_E_V``; silently
    selecting 0 V is a physical-input default and is forbidden.
    """
    if not isinstance(include_redox, bool):
        raise ValueError(
            "redox mode is 'Not defined'; declare redox_mode explicitly")

    if include_redox:
        if (fixed_E_V is None or isinstance(fixed_E_V, bool)):
            raise ValueError(
                "E_V is 'Not defined' for a redox-enabled pH sweep; "
                "declare fixed_E_V or supply a compiled E_V binding")
        try:
            electron_reference = float(fixed_E_V)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"fixed_E_V must be a finite number, got {fixed_E_V!r}") from exc
        if not np.isfinite(electron_reference):
            raise ValueError(
                f"fixed_E_V must be a finite number, got {fixed_E_V!r}")
    else:
        if fixed_E_V is not None:
            raise ValueError(
                "fixed_E_V must be absent when redox is excluded")
        electron_reference = None

    def solve_fn(coords: Dict[str, float],
                 x0: Optional[np.ndarray]) -> PointResult:
        merged = dict(coords)
        if electron_reference is not None:
            merged["E_V"] = electron_reference
        return unified_solve_fn(merged, x0)
    return solve_fn


def _pH_output_provenance(
    grid,
    *,
    compiled_constraints: Optional[Any],
    include_redox: bool,
    fixed_E_V: Optional[float],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Derive serialized pH-sweep inputs from their numerical source.

    Compiled constraints, when present, are the source of truth for the
    redox policy and analytical totals.  The potential exported for each row
    is also checked against the coordinate returned by the point solver.  A
    fixed-potential calculation therefore cannot be serialized as an
    apparently potential-free sweep, and no potential is invented for an
    excluded-redox calculation.
    """
    by_lhs: Dict[str, Any] = {}
    if compiled_constraints is not None:
        by_lhs = {
            binding[1]: binding
            for binding in (compiled_constraints.bindings or [])
        }

    redox_binding = by_lhs.get("redox")
    compiled_redox = (
        str(redox_binding[2]) if redox_binding is not None else None
    )
    e_binding = by_lhs.get("E_V")
    if compiled_redox == "exclude":
        redox_mode = "excluded"
    elif getattr(compiled_constraints, "phase_b_pins", None):
        redox_mode = "solve"
    elif e_binding is not None:
        redox_mode = "fixed" if e_binding[0] == "scalar" else "freeform"
    elif (compiled_constraints is not None
          and "E_V" in set(compiled_constraints.axis_names or ())):
        redox_mode = "axis"
    elif include_redox and fixed_E_V is not None:
        # Direct callers must pass this value explicitly.
        redox_mode = "fixed"
    elif include_redox:
        redox_mode = "solve"
    else:
        redox_mode = "excluded"

    inventory = getattr(compiled_constraints, "variable_inventory", None)
    groups = {
        "parent_element_totals": tuple(
            getattr(inventory, "parent_element_totals", ()) or ()),
        "redox_state_subtotals": tuple(
            getattr(inventory, "redox_state_subtotals", ()) or ()),
        "component_totals": tuple(
            getattr(inventory, "component_totals", ()) or ()),
    }
    params: Dict[str, Any] = {"redox_mode": redox_mode}
    total_keys: List[str] = []
    for group_name, keys in groups.items():
        values: Dict[str, Any] = {}
        for key in keys:
            binding = by_lhs.get(key)
            if binding is None:
                continue
            kind, _lhs, raw, _closure, _free = binding
            if kind == "scalar":
                values[key] = float(raw)
            else:
                # Preserve the declared expression.  Its evaluated values
                # are recorded separately in state_provenance below.
                values[key] = str(raw)
            total_keys.append(key)
        if values:
            params[group_name] = values

    state_rows: List[Dict[str, Any]] = []
    actual_e_values: List[float] = []
    for i, axis_value in enumerate(grid.axes[0].values):
        coords = {grid.axes[0].name: float(axis_value)}
        derived = (
            compiled_constraints.apply(coords)
            if compiled_constraints is not None else {}
        )
        point = grid.points[i]
        point_e = getattr(point, "E_V", None) if point is not None else None
        expected_e = derived.get("E_V", fixed_E_V)
        if point_e is not None:
            point_e = float(point_e)
            if not np.isfinite(point_e):
                raise RuntimeError(
                    f"solver returned non-finite E_V={point_e!r} at pH "
                    f"{float(axis_value):.12g}")
            actual_e_values.append(point_e)
        if expected_e is not None:
            expected_e = float(expected_e)
            if point_e is not None and not np.isclose(
                    point_e, expected_e, rtol=0.0, atol=1.0e-12):
                raise RuntimeError(
                    "declared E_V disagrees with the solver coordinate at "
                    f"pH {float(axis_value):.12g}: declared={expected_e!r}, "
                    f"solved={point_e!r}")

        row: Dict[str, Any] = {
            "E_V": point_e if point_e is not None else expected_e,
            "redox_mode": redox_mode,
        }
        for key in total_keys:
            if key in derived:
                row[key] = derived[key]
        state_rows.append(row)

    if redox_mode == "excluded":
        if actual_e_values:
            raise RuntimeError(
                "redox-excluded pH sweep returned an E_V coordinate")
    elif redox_mode == "fixed":
        if e_binding is not None:
            declared_e = float(e_binding[2])
        elif fixed_E_V is not None:
            declared_e = float(fixed_E_V)
        else:
            raise RuntimeError(
                "fixed-potential pH sweep has no explicit E_V source")
        if not actual_e_values:
            raise RuntimeError(
                "fixed-potential pH sweep returned no E_V coordinates")
        if not all(np.isclose(value, declared_e, rtol=0.0, atol=1.0e-12)
                   for value in actual_e_values):
            raise RuntimeError(
                "fixed E_V was not preserved across the pH sweep")
        params["fixed_E_V"] = declared_e
    elif actual_e_values:
        params["E_V_range"] = [
            float(min(actual_e_values)), float(max(actual_e_values)),
        ]

    return params, state_rows


# ------------------------------------------------------------------
#  Public API
# ------------------------------------------------------------------

def run_pH_sweep(
    source,
    total_metals: Optional[List[float]] = None,
    total_ligands: Optional[List[float]] = None,
    *,
    pH_range: Optional[Tuple[float, float]] = None,
    n_points: Optional[int] = None,
    output_dir: Optional[Union[str, pathlib.Path]] = None,
    temperature_K: Optional[float] = None,
    ionic_strength: Optional[float] = None,
    include_solids: Optional[bool] = None,
    use_activity: Optional[bool] = None,
    debug: bool = False,
    prefix: Optional[str] = None,
    compiled_constraints: Optional[Any] = None,
    fixed_E_V: Optional[float] = None,
) -> Dict[str, Any]:
    """Run a 1-D pH speciation sweep through the unified pipeline.

    Parameters
    ----------
    source : str | pathlib.Path | dict | FreeEnergyReport
        Card source. Resolved by ``parse_source``.
    total_metals, total_ligands : list of float, optional
        Per-component total concentrations.  When omitted, the totals
        already attached to the report (typically populated by the
        top-level API) are used.  Provided for back-compat with direct
        callers; in the unified pipeline the canonical place to set
        totals is on the report itself (via the ``concentrations``
        section of the calc-input JSON).
    pH_range : (float, float)
        Sweep domain.
    n_points : int
        Number of grid points along the pH axis.
    output_dir : str | Path, optional
        If supplied, all output files (speciation CSVs, plots,
        topology JSON) are written here.
    temperature_K, ionic_strength : float, optional
        Overrides forwarded to the source resolver / system builder.
    include_solids, use_activity : bool
        Explicit model selections. ``include_solids`` controls whether
        dissolution/solid equilibria are assembled. ``use_activity`` selects
        Davies activity corrections when true and the ideal model when false;
        auto-I iteration is additionally engaged when
        ``report.ionic_mode == "auto"``.
    debug : bool
        Verbose progress logging.
    prefix : str, optional
        Filename prefix for output files. Default: derived from
        ``built.system_name``.
    fixed_E_V : float, optional
        Explicit fixed potential for a redox-enabled pH-only sweep when no
        compiled constraints are supplied.  Redox-enabled callers must
        provide this value; no potential default is assumed.

    Returns
    -------
    dict with keys:
        ``report``           - FreeEnergyReport
        ``built``            - BuiltSystem
        ``grid``             - NDGrid (1-D)
        ``topology``         - CompactTopologyND (or TopologyND when no
                                boundaries exist; None on extraction failure)
        ``speciation_curve`` - SpeciationCurve
        ``output_paths``     - list[str]
    """
    t0 = time.time()

    missing = [
        name for name, value in (
            ("pH_range", pH_range), ("n_points", n_points),
            ("include_solids", include_solids),
            ("use_activity", use_activity),
        ) if value is None
    ]
    if missing:
        raise ValueError(
            "pH_sweep physical/model input(s) are 'Not defined': "
            f"{missing}; declare them explicitly")
    if not isinstance(include_solids, bool) or not isinstance(use_activity, bool):
        raise ValueError("include_solids and use_activity must be explicit booleans")
    try:
        pH_lo, pH_hi = (float(pH_range[0]), float(pH_range[1]))
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("pH_range must contain two finite numbers") from exc
    if not np.isfinite(pH_lo) or not np.isfinite(pH_hi) or pH_hi <= pH_lo:
        raise ValueError(f"pH_range must be finite and increasing, got {pH_range!r}")
    if isinstance(n_points, bool) or int(n_points) < 2:
        raise ValueError(f"n_points must be an explicit integer >= 2, got {n_points!r}")
    pH_range = (pH_lo, pH_hi)
    n_points = int(n_points)

    # 1. Resolve the report
    report = parse_source(source, temperature_K=temperature_K)
    # Direct callers declare these settings as function arguments; attach
    # them to the report before the shared builder enforces the model contract.
    report.include_solids = include_solids
    report.activity_model = "davies" if use_activity else "ideal"
    include_redox = getattr(report, "include_redox", "Not defined")
    if not isinstance(include_redox, bool):
        raise ValueError(
            "redox mode is 'Not defined' on the solver report; declare "
            "redox_mode explicitly before running the pH sweep")

    # Apply caller-supplied totals onto the report so the BuiltSystem
    # (which reads ``report.total_metals``/``total_ligands``) sees them.
    if total_metals is not None:
        for mid, val in zip(report.metal_ids, total_metals):
            report.total_metals[mid] = float(val)
    if total_ligands is not None:
        for lid, val in zip(report.ligand_ids, total_ligands):
            report.total_ligands[lid] = float(val)

    # 2. Build BuiltSystem + unified solve_fn
    built, unified_solve_fn = build_solver_chain(
        report,
        ionic_strength=ionic_strength,
        system_name=getattr(report, "system_name", "") or "",
        compiled_constraints=compiled_constraints,
    )
    # When constraints are supplied they inject E_V (and a_w), so the
    # wrapper must not overwrite the declared binding.  Without compiled
    # constraints, redox-enabled pH sweeps require an explicit fixed E_V;
    # redox-excluded systems have no potential coordinate.
    if compiled_constraints is None:
        solve_fn = _make_pH_only_solve_fn(
            unified_solve_fn,
            include_redox=include_redox,
            fixed_E_V=fixed_E_V,
        )
    else:
        solve_fn = unified_solve_fn

    if debug:
        print(f"[pH_sweep] System: {built.system_name}")
        print(f"[pH_sweep] Basis : {built.n_basis} "
              f"(elements={built.element_names}, "
              f"ligands={list(report.ligand_ids)})")
        print(f"[pH_sweep] pH    : {pH_range[0]:.2f} -> "
              f"{pH_range[1]:.2f} ({n_points} points)")
        print(f"[pH_sweep] I     : {built.ionic_strength}  "
              f"(mode={getattr(report, 'ionic_mode', 'fixed')})")

    # 3. Solve 1-D grid via the single public method NDGridSolver.solve.
    #    pH sweeps only need labelled coarse grid + topology —
    #    no boundary refinement and no fine label map.
    pH_vals = np.linspace(pH_range[0], pH_range[1], int(n_points))
    axes = [GridAxis("pH", pH_vals)]
    nd_solver = NDGridSolver(
        solve_fn, built.n_basis, built_system=built, debug=debug,
    )
    result = nd_solver.solve(
        axes,
        refine=False,
        checkpoint_dir=(
            pathlib.Path(output_dir) / "_checkpoints" / "nd_grid"
            if output_dir is not None else None
        ),
        checkpoint_identity={
            "sweep": "pH",
            "system_name": built.system_name,
        },
    )
    grid = result.grid
    if debug:
        n_conv = int(np.sum(grid.converged_mask))
        print(f"[pH_sweep] Coarse solve: {n_conv}/{n_points} converged "
              f"({time.time() - t0:.1f}s)")

    # 4. Extract + compact topology
    output_paths: List[str] = []
    out_path: Optional[pathlib.Path] = None
    if output_dir is not None:
        out_path = pathlib.Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

    # Use the first principal element for 1-D topology (the labels we
    # care about for pH-only speciation are element-keyed).  When no
    # principal element exists we still emit the speciation curve below.
    topology = None
    safe_name = (built.system_name or "system").replace(
        " ", "_").replace("-", "_")

    if built.principal_elements:
        elem = built.principal_elements[0]
        try:
            topology = result.per_element[elem].topology
            if hasattr(topology, "boundaries") and topology.boundaries:
                topology = compact_topology_nd(topology, csv_dir=None)
            if out_path is not None and topology is not None:
                topo_path = out_path / f"topology_{safe_name}_{elem}.json"
                meta = {
                    "system_name": built.system_name,
                    "element": elem,
                    "n_pH": int(n_points),
                    "pH_range": list(pH_range),
                }
                export_topology_json(
                    topology, str(topo_path),
                    metadata=meta, debug=debug,
                )
                output_paths.append(str(topo_path))
        except Exception as exc:
            if debug:
                print(f"[pH_sweep] Topology extraction skipped: {exc}")
            topology = None

    provenance, state_provenance = _pH_output_provenance(
        grid,
        compiled_constraints=compiled_constraints,
        include_redox=include_redox,
        fixed_E_V=fixed_E_V,
    )

    # 6. Build SpeciationCurve from the grid (downstream of compactor)
    curve = build_speciation_curve_from_grid_1d(
        report, grid,
        axis_name="pH",
        system_name=built.system_name or None,
        method="free_energy",
        extras={
            "pH_range":  list(pH_range),
            "n_points":  int(n_points),
            "ionic_mode": getattr(report, "ionic_mode", "fixed"),
            "include_redox": include_redox,
            **provenance,
        },
        built_system=built,
        include_redox=include_redox,
    )
    curve.state_provenance = state_provenance

    # 7. Output emission
    if out_path is not None:
        from .pH_sweep_export import generate_all_output
        emit_prefix = prefix if prefix is not None else safe_name
        out_paths = generate_all_output(
            curve, out_path, prefix=emit_prefix,
        )
        if isinstance(out_paths, dict):
            output_paths.extend(out_paths.values())
        elif out_paths:
            output_paths.append(out_paths)

    if debug:
        print(f"[pH_sweep] Done in {time.time() - t0:.1f}s "
              f"({len(output_paths)} output files)")

    return {
        "report":            report,
        "built":             built,
        "grid":              grid,
        "topology":          topology,
        "speciation_curve":  curve,
        "output_paths":      output_paths,
    }
