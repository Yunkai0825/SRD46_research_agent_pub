"""
Pourbaix Sweep Main — unified N-D Pourbaix diagram pipeline.
============================================================
Accepts a ``FreeEnergyReport`` (or source path), converts it to
solver-ready arrays via ``BuiltSystem``, and runs the
complete pipeline:
    coarse grid  →  label  →  boundary detect  →  refinement
    →  topology extraction  →  output emission

Uses the generalized N-D grid infrastructure (``nd_grid`` package),
so the same function handles 1-D (single axis), 2-D (E vs pH) and
3-D (E vs pH vs a_w) Pourbaix sweeps — and trivially extends to any
higher dimensionality should additional axes be added.

The grid solve / labeling / refinement / topology stages are all
dimension-agnostic.  Only the final output emission is dim-aware:

    ndim == 1   → topology JSON (minimal output)
    ndim == 2   → label-map CSV + topology JSON + speciation + 2-D PNG
    ndim == 3   → topology JSON + 3-D topology PNG
    ndim >= 4   → topology JSON only

Public API
----------
- ``run_pourbaix_sweep``  — canonical N-D entry point
"""
from __future__ import annotations

import datetime
import pathlib
import sys
import time
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple, Union

import numpy as np

from .pourbaix_sweep_settings import (
    POINT_TIMEOUT_S, DEBUG,
)
from sweep_pipelines._path_utils import long_path, safe_mkdir


# ── Timestamped logging to console + file ────────────────────
class SweepLogger:
    """Dual-output logger with ISO-8601 timestamps.

    Writes every message to both ``sys.stdout`` and an optional log
    file inside the output directory.
    """

    def __init__(self, log_path: Optional[pathlib.Path] = None):
        self._fh = None
        if log_path is not None:
            safe_mkdir(log_path.parent)
            self._fh = open(long_path(log_path), "a", encoding="utf-8")

    def log(self, msg: str, *, flush: bool = True) -> None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        # Write the durable file log FIRST so a console-encoding error
        # (e.g. a non-ASCII glyph on a cp1252 Windows console) can never
        # drop a log line.  The console print is best-effort.
        if self._fh is not None:
            self._fh.write(line + "\n")
            if flush:
                self._fh.flush()
        try:
            print(line, flush=flush)
        except UnicodeEncodeError:
            enc = getattr(sys.stdout, "encoding", "ascii") or "ascii"
            print(line.encode(enc, "replace").decode(enc), flush=flush)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


# ── N-D grid infrastructure ─────────────────────────────────
# NDGridSolver is THE single orchestrator of the grid + labelling
# + boundary refinement + topology pipeline.  This sweep driver
# only builds inputs and consumes the per-element result bundles.
from solvers_and_topology.nd_grid import (
    NDGridSolver, GridAxis, PointResult, NDGrid,
)


def _retain_full_speciation_record(result: PointResult) -> bool:
    """Return whether a point belongs in the diagnostic full-spec artifact.

    Converged points remain the normal numerical record.  A failed point is
    retained only when the solid-phase search produced actionable
    thermodynamic diagnostics: incomparable certified assemblages or an
    incomplete timeout.  The result remains ``converged=False``, so this
    persistence decision cannot promote it into labels or topology.
    """
    return bool(
        result.converged
        or result.thermodynamic_ambiguity_active_sets
        or result.phase_search_timed_out
    )


# ── Lazy imports from legacy solver chain ─────────────────────
def _get_solver_chain():
    """Import the solver classes (point solver + solid manager)."""
    from numerical_solvers.point_solver import PourbaixPointSolver
    from numerical_solvers.solid_manager import SolidManager
    return PourbaixPointSolver, SolidManager


def _get_free_energy():
    """Import FreeEnergyReport and the compute function."""
    from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
        compute_free_energy_network,
        FreeEnergyReport,
    )
    return compute_free_energy_network, FreeEnergyReport


# ── Proxy types for old SolidManager interface ───────────────
def _get_proxies():
    from _input_solver_helper.built_system_from_dGreport import DissolutionProxy, SpeciesProxy
    return DissolutionProxy, SpeciesProxy


# ── Solver chain construction from BuiltSystem ───────
def _build_solver_chain(built, *, debug=False):
    """Construct PourbaixPointSolver → SolidManager."""
    PourbaixPointSolver, SolidManager = _get_solver_chain()
    DissolutionProxy, SpeciesProxy = _get_proxies()

    pt_solver = PourbaixPointSolver(
        built.log_beta_eff, built.stoich_pq,
        built.stoich_r, built.stoich_s,
        built.nu_matrix, built.n_basis, debug=False,
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
            label=built.diss_labels[i] if i < len(built.diss_labels) else f"solid_{i}",
        ))

    sp_proxies = [
        SpeciesProxy(sid, lbl)
        for sid, lbl in zip(built.species_ids, built.species_labels)
    ]

    solid_mgr = SolidManager(
        pt_solver, diss_proxies, built.n_basis,
        sp_proxies, debug=False, built=built,
    )
    return pt_solver, solid_mgr


def _make_component_total_resolver(
    C_total,
    *,
    compiled_constraints=None,
    built=None,
    report=None,
) -> Tuple[Callable[..., np.ndarray], FrozenSet[int]]:
    """Return the solver's per-cell total resolver and varying slots.

    ``BuiltSystem.C_total`` is the pre-constraint baseline.  In redox-aware
    cards it can contain the sum of several oxidation-state defaults, while
    the compiled calculation constraint deliberately replaces that sum with
    one element-level total.  Keeping this resolution in one callable makes
    the numerical solver and output metadata consume the same value.

    The returned slot set identifies totals whose defining expression depends
    (directly or transitively) on a sweep axis.  Plotters must describe those
    totals as varying rather than displaying a misleading scalar.
    """
    base_C_total = np.asarray(C_total, dtype=float).copy()
    if compiled_constraints is None:
        def resolve_totals(coords, *, derived=None):
            return base_C_total.copy()

        return resolve_totals, frozenset()

    if built is None or report is None:
        raise ValueError(
            "constraint-aware total resolution requires built and report"
        )

    n_metals = len(built.element_names)
    catalog = compiled_constraints.catalog
    elem_to_idx = {name: i for i, name in enumerate(built.element_names)}
    basis_token_to_idx = {
        token: i for i, token in enumerate(built.basis_tokens[:n_metals])
    }
    totals_lookup: Dict[str, int] = {}
    element_lhs: set = set()
    include_redox = getattr(report, "include_redox", "Not defined")
    if not isinstance(include_redox, bool):
        raise ValueError("redox mode is 'Not defined' on the solver report")
    for m in catalog.chemical_system.metals:
        redox_ids = list(m.redox_states or [])
        if not include_redox and len(redox_ids) > 1:
            for rid in redox_ids:
                idx = basis_token_to_idx.get(rid, elem_to_idx.get(rid))
                if idx is not None:
                    totals_lookup[f"[{rid}]_total"] = idx
            continue
        idx = elem_to_idx.get(m.element)
        if idx is None and len(redox_ids) == 1:
            idx = basis_token_to_idx.get(redox_ids[0], elem_to_idx.get(redox_ids[0]))
        if idx is None:
            continue
        elem_lhs_key = f"[{m.element}]_total"
        totals_lookup[elem_lhs_key] = idx
        element_lhs.add(elem_lhs_key)
        if m.name != m.element:
            totals_lookup[f"[{m.name}]_total"] = idx
            element_lhs.add(f"[{m.name}]_total")
        for rid in redox_ids:
            totals_lookup[f"[{rid}]_total"] = idx
        if m.internal_id not in m.redox_states:
            totals_lookup[f"[{m.internal_id}]_total"] = idx

    l_ids = list(getattr(report, "ligand_ids", []) or [])
    lid_to_idx = {lid: n_metals + j for j, lid in enumerate(l_ids)}
    for ligand in catalog.chemical_system.ligands:
        idx = lid_to_idx.get(ligand.internal_id)
        if idx is None:
            continue
        totals_lookup[f"[{ligand.db_id}]_total"] = idx
        if ligand.internal_id and ligand.internal_id != ligand.db_id:
            totals_lookup[f"[{ligand.internal_id}]_total"] = idx

    # Propagate axis dependence through the compiler's topological order.
    # This is intentionally conservative: an expression such as ``0*pH``
    # is described as varying instead of being advertised as a fixed total.
    bindings_by_lhs = {
        binding[1]: binding for binding in compiled_constraints.bindings
    }
    axis_dependent_lhs = set(compiled_constraints.axis_names)
    for lhs in compiled_constraints.eval_order:
        binding = bindings_by_lhs.get(lhs)
        if binding is None:
            continue
        kind, _, _raw, _closure, free_identifiers = binding
        if (kind == "formula"
                and set(free_identifiers or ()) & axis_dependent_lhs):
            axis_dependent_lhs.add(lhs)

    # Mirror the resolver's precedence to identify which bindings actually
    # feed each component slot.  An element-level total supersedes all of its
    # redox-state totals; otherwise redox-state contributions are summed.
    source_lhs_by_slot: Dict[int, List[str]] = {}
    slot_has_element: Dict[int, bool] = {}
    for lhs, idx in totals_lookup.items():
        if lhs not in bindings_by_lhs:
            continue
        if lhs in element_lhs:
            source_lhs_by_slot[idx] = [lhs]
            slot_has_element[idx] = True
        elif not slot_has_element.get(idx):
            source_lhs_by_slot.setdefault(idx, []).append(lhs)
    axis_dependent_slots = frozenset(
        idx
        for idx, sources in source_lhs_by_slot.items()
        if any(lhs in axis_dependent_lhs for lhs in sources)
    )

    def resolve_totals(coords, *, derived=None):
        env = (compiled_constraints.apply(coords)
               if derived is None else derived)
        Cnew = base_C_total.copy()
        slot_value: Dict[int, float] = {}
        slot_has_element_value: Dict[int, bool] = {}
        for lhs, idx in totals_lookup.items():
            if lhs not in env:
                continue
            value = env[lhs]
            if (not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not np.isfinite(float(value))
                    or float(value) < 0):
                raise ValueError(
                    f"declared total {lhs} evaluated to invalid per-cell "
                    f"value {value!r} at coordinates {coords}")
            if lhs in element_lhs:
                slot_value[idx] = float(value)
                slot_has_element_value[idx] = True
            else:
                if slot_has_element_value.get(idx):
                    continue
                current = slot_value.get(idx)
                slot_value[idx] = (
                    float(value) if current is None
                    else current + float(value)
                )
        for idx, value in slot_value.items():
            Cnew[idx] = value
        return Cnew

    return resolve_totals, axis_dependent_slots


def _make_pourbaix_solve_fn(solid_mgr, C_total, timeout_s=POINT_TIMEOUT_S,
                            *, compiled_constraints=None, built=None,
                            report=None, total_resolver=None):
    """
    Create a ``(coords, x0) -> PointResult`` callable that wraps
    ``SolidManager.solve_point(pH, E_V, C_total, x0)``.

    When ``compiled_constraints`` is supplied, the wrapper resolves
    every catalog DOF per cell, derives ``pH`` / ``E_V`` (and ``a_w``
    handled upstream by the SolidManager via log-K shifts which are
    not yet rewired here for the pourbaix path), and recomputes
    ``C_total`` from ``[<elem>]_total`` / ``[<lig>]_total`` bindings.
    """
    include_redox = getattr(report, "include_redox", "Not defined")
    if include_redox is not True:
        raise ValueError(
            "Pourbaix sweeps require explicitly enabled redox and a declared "
            "E_V coordinate; redox-excluded systems must use a potential-free route")

    if total_resolver is None:
        total_resolver, _ = _make_component_total_resolver(
            C_total,
            compiled_constraints=compiled_constraints,
            built=built,
            report=report,
        )

    if compiled_constraints is None:
        def solve_fn(coords: Dict[str, float],
                     x0: Optional[np.ndarray]) -> PointResult:
            pH_raw = coords.get("pH")
            E_raw = coords.get("E_V")
            if pH_raw is None or E_raw is None:
                raise ValueError(
                    "Pourbaix cell coordinates pH and E_V must be explicitly declared")
            pH = float(pH_raw)
            E_V = float(E_raw)
            if not np.isfinite(pH) or not np.isfinite(E_V):
                raise ValueError(
                    f"Pourbaix coordinates must be finite, got {coords!r}")
            effective_totals = total_resolver(coords)
            return solid_mgr.solve_point(pH, E_V, effective_totals, x0,
                                         timeout_s=timeout_s)
        return solve_fn

    def solve_fn(coords: Dict[str, float],
                 x0: Optional[np.ndarray]) -> PointResult:
        derived = compiled_constraints.apply(coords)
        pH_raw = derived.get("pH", coords.get("pH"))
        E_raw = derived.get("E_V", coords.get("E_V"))
        if pH_raw is None or E_raw is None:
            raise ValueError(
                "Pourbaix pH or E_V is 'Not defined'; declare its axis or bind")
        pH = float(pH_raw)
        E_V = float(E_raw)
        if not np.isfinite(pH) or not np.isfinite(E_V):
            raise ValueError(
                f"Pourbaix coordinates must be finite, got pH={pH_raw!r}, "
                f"E_V={E_raw!r}")
        effective_totals = total_resolver(coords, derived=derived)
        return solid_mgr.solve_point(pH, E_V, effective_totals, x0,
                                     timeout_s=timeout_s)
    return solve_fn


# ==================================================================
#  PUBLIC API
# ==================================================================

def _build_axes_from_kwargs(
    pH_range: Optional[Tuple[float, float]],
    E_range: Optional[Tuple[float, float]],
    aw_range: Optional[Tuple[float, float]],
    n_pH: Optional[int],
    n_E: Optional[int],
    n_aw: Optional[int],
) -> List[GridAxis]:
    """Construct the axis list from the legacy 2-D / 3-D scalar kwargs.

    The returned list always uses the canonical Pourbaix order
    ``[E_V, pH, (a_w)]`` so that downstream output emitters can
    rely on a stable axis order.  Any axis whose ``range`` or ``n``
    is ``None`` is omitted.
    """
    axes: List[GridAxis] = []
    for name, axis_range, count in (
        ("E_V", E_range, n_E), ("pH", pH_range, n_pH),
        ("a_w", aw_range, n_aw),
    ):
        if (axis_range is None) != (count is None):
            raise ValueError(
                f"axis {name!r} is only partially declared; provide both "
                "range and resolution or omit both")
        if axis_range is None:
            continue
        try:
            lo, hi = float(axis_range[0]), float(axis_range[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError(f"axis {name!r} range must contain two numbers") from exc
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            raise ValueError(
                f"axis {name!r} range must be finite and increasing")
        if isinstance(count, bool) or int(count) < 2:
            raise ValueError(
                f"axis {name!r} resolution must be an integer >= 2")
    if E_range is not None and n_E is not None:
        axes.append(GridAxis(
            "E_V", np.linspace(E_range[0], E_range[1], n_E)))
    if pH_range is not None and n_pH is not None:
        axes.append(GridAxis(
            "pH", np.linspace(pH_range[0], pH_range[1], n_pH)))
    if aw_range is not None and n_aw is not None:
        axes.append(GridAxis(
            "a_w", np.linspace(aw_range[0], aw_range[1], n_aw)))
    if not axes:
        raise ValueError(
            "run_pourbaix_sweep: no axes specified — provide either "
            "an explicit `axes` list or at least one of "
            "(pH_range,n_pH) / (E_range,n_E) / (aw_range,n_aw)."
        )
    return axes


def _emit_per_element_output(
    grid, built, elem, boundaries,
    topo, refined_pts, x_cache, fine_label_map,
    *,
    axes: List[GridAxis],
    out_dir: pathlib.Path,
    safe_name: str,
    refine_factor_eff: int,
    solve_fn,
    effective_component_totals=None,
    debug: bool = False,
) -> List[str]:
    """Dim-aware per-element output emission.

    The grid solve / labeling / refinement / topology stages are all
    dimension-agnostic.  Only this final stage branches on ``len(axes)``.
    """
    ndim = len(axes)

    if ndim == 2:
        # Rich 2-D path: label-map CSV + topology JSON + speciation + PNG
        # Recover (pH_range, E_range, n_pH, n_E) from the axes.
        pH_axis = next((a for a in axes if a.name == "pH"), None)
        E_axis = next((a for a in axes if a.name == "E_V"), None)
        if pH_axis is None or E_axis is None:
            # Unusual 2-D axis combination — fall back to topology-only.
            from .pourbaix_sweep_export import emit_output_topology_only
            return emit_output_topology_only(
                grid, built, elem, topo, out_dir, safe_name, axes,
                fine_label_map=fine_label_map,
                debug=debug)
        pH_range = (float(pH_axis.values[0]), float(pH_axis.values[-1]))
        E_range = (float(E_axis.values[0]), float(E_axis.values[-1]))
        n_pH = len(pH_axis.values)
        n_E = len(E_axis.values)

        # With refinement disabled the coarse raster is itself the final
        # effective classified field.  The rich 2-D exporter intentionally
        # requires an explicit final map so neither topology nor verdict can
        # fall back to an unrelated upstream topology object.
        if fine_label_map is None:
            fine_label_map = (
                [axis.values for axis in grid.axes],
                grid.labels_per_element[elem],
                grid.label_catalog_per_element[elem],
            )

        from .pourbaix_sweep_export import emit_refined_output
        return emit_refined_output(
            grid, built, boundaries, elem,
            topo=topo, segments=None, grid_solver=None,
            out_dir=out_dir, safe_name=safe_name,
            pH_range=pH_range, E_range=E_range,
            n_pH=n_pH, n_E=n_E,
            refine_factor=refine_factor_eff,
            debug=debug,
            fine_label_map=fine_label_map,
            solve_fn=solve_fn,
            x_cache=x_cache,
            effective_component_totals=effective_component_totals,
        )

    if ndim == 3:
        from .pourbaix_sweep_export import emit_output_3d
        return emit_output_3d(
            grid, built, elem, topo,
            out_dir, safe_name, axes,
            fine_label_map=fine_label_map,
            debug=debug)

    # ndim == 1 or ndim >= 4 — minimal output
    from .pourbaix_sweep_export import emit_output_topology_only
    return emit_output_topology_only(
        grid, built, elem, topo, out_dir, safe_name, axes,
        fine_label_map=fine_label_map,
        debug=debug)


def run_pourbaix_sweep(
    source: Union[str, "pathlib.Path", dict, object],
    *,
    # ── New ND-aware path (preferred) ─────────────────────────
    axes: Optional[List[GridAxis]] = None,
    # ── Legacy scalar-kwarg path (used when `axes` is None) ───
    pH_range: Optional[Tuple[float, float]] = None,
    E_range: Optional[Tuple[float, float]] = None,
    aw_range: Optional[Tuple[float, float]] = None,
    n_pH: Optional[int] = None,
    n_E: Optional[int] = None,
    n_aw: Optional[int] = None,
    # ── Common pipeline parameters ────────────────────────────
    output_dir: Optional[str] = None,
    temperature_K: Optional[float] = None,
    ionic_strength: Optional[float] = None,
    refine_factor: Optional[int],
    n_layers: int,
    debug: bool = DEBUG,
    compiled_constraints: Optional[Any] = None,
):
    """
    Unified N-D Pourbaix diagram pipeline.

    The same function handles 1-D, 2-D (E vs pH) and 3-D
    (E vs pH vs a_w) sweeps — and trivially extends to higher
    dimensionality if additional axes are added.

    Parameters
    ----------
    source : str | Path | dict | FreeEnergyReport
        A JSON file path, dict, or pre-built ``FreeEnergyReport``.
    axes : list of GridAxis, optional
        Explicit N-D axis specification.  If given, the legacy scalar
        ``*_range`` / ``n_*`` kwargs are ignored.
    pH_range, E_range, aw_range : (min, max) tuples, optional
        Domain limits for the legacy scalar-kwarg path.  Pass ``None``
        for any axis you wish to omit (e.g. drop ``aw_range`` for a
        pure 2-D sweep, drop ``pH_range`` for a 1-D E-only sweep).
    n_pH, n_E, n_aw : int, optional
        Grid resolution per axis (legacy scalar-kwarg path).  Pass
        ``None`` to omit the corresponding axis.
    output_dir : str, optional
        Directory for output files.  Default: ``_output_pourbaix``.
    temperature_K : float, optional
        Override temperature (default: from report).
    ionic_strength : float, optional
        Override ionic strength (default: from report).
    refine_factor : int
        Per-axis sub-grid refinement factor.  Must be ``None`` when
        refinement is disabled and at least 2 otherwise.
    n_layers : int
        Explicit refinement switch: 0 disables refinement; values >=1
        enable boundary refinement for a 2-D or 3-D grid.
    debug : bool
        Print progress messages.

    Returns
    -------
    (grid, built, all_boundaries, output_paths)
    """
    compute_free_energy_network, FreeEnergyReport = _get_free_energy()

    t0 = time.time()
    from sweep_pipelines._sweep_input_entry_point.grid_refinement_contract import (
        normalize_grid_refinement,
    )
    n_layers, refine_factor = normalize_grid_refinement(
        n_layers=n_layers,
        factor=refine_factor,
        context="Pourbaix refinement",
    )

    # 1. Resolve axes
    if axes is None:
        axes = _build_axes_from_kwargs(
            pH_range, E_range, aw_range, n_pH, n_E, n_aw)
    ndim = len(axes)
    if n_layers >= 1 and ndim not in (2, 3):
        raise ValueError(
            "Pourbaix boundary refinement requires a 2-D or 3-D axis set; "
            "use n_layers=0 for an unrefined sweep"
        )

    # 2. Obtain FreeEnergyReport
    if isinstance(source, FreeEnergyReport):
        report = source
    else:
        report = compute_free_energy_network(source, temperature_K=temperature_K)

    # 3. Build solver-ready arrays
    from _input_solver_helper.built_system_from_dGreport import (
        build_from_free_energy_report, BuiltSystem,
    )
    built = build_from_free_energy_report(
        report,
        ionic_strength=ionic_strength,
        system_name="",
    )

    # 4. Setup output directory
    if output_dir is None:
        out_dir = pathlib.Path("_output_pourbaix")
    else:
        out_dir = pathlib.Path(output_dir)
    safe_mkdir(out_dir)

    # 4a. Initialise timestamped logger → console + log file
    log = SweepLogger(out_dir / "sweep_log.txt" if debug else None)

    # 4b. Copy input energy card to output directory for provenance
    import shutil
    if isinstance(source, (str, pathlib.Path)):
        src_path = pathlib.Path(source)
        if src_path.is_file():
            dst = out_dir / src_path.name
            shutil.copy2(long_path(src_path), long_path(dst))
            if debug:
                log.log(f"[step 4b] Copied input card -> {dst.name}")

    if debug:
        grid_shape = " x ".join(str(len(ax.values)) for ax in axes)
        axis_summary = ", ".join(
            f"{ax.name}=[{float(ax.values[0]):.2f},"
            f"{float(ax.values[-1]):.2f}]"
            for ax in axes
        )
        log.log(f"{'='*60}")
        log.log(f"  Pourbaix Diagram Sweep ({ndim}-D)")
        log.log(f"  System: {built.system_name}")
        log.log(f"  Grid:   {grid_shape}")
        log.log(f"  Axes:   {axis_summary}")
        log.log(f"  I:      {built.ionic_strength}")
        log.log(f"  T:      {built.temperature_C:.1f} °C")
        log.log(f"{'='*60}")

    # 5. Construct solver chain and N-D solve function
    _, solid_mgr = _build_solver_chain(built, debug=debug)
    total_resolver, axis_dependent_total_slots = (
        _make_component_total_resolver(
            built.C_total,
            compiled_constraints=compiled_constraints,
            built=built,
            report=report,
        )
    )
    _solve_fn_inner = _make_pourbaix_solve_fn(
        solid_mgr, built.C_total, timeout_s=POINT_TIMEOUT_S,
        compiled_constraints=compiled_constraints,
        built=built, report=report,
        total_resolver=total_resolver)

    # Figure metadata follows the same resolver as every numerical cell.
    # ``None`` entries are deliberately rendered as axis-dependent totals.
    # Legacy unconstrained callers retain the plotter's BuiltSystem fallback.
    effective_component_totals = None
    if compiled_constraints is not None:
        representative_coords = {
            axis.name: float(axis.values[0]) for axis in axes
        }
        resolved_totals = total_resolver(representative_coords)
        effective_component_totals = tuple(
            None if idx in axis_dependent_total_slots else float(value)
            for idx, value in enumerate(resolved_totals)
        )

    # Wrap solve_fn with a stage-tagged recorder.
    #   - coarse_records:  converged coarse-grid points plus nonconverged
    #                      thermodynamic ambiguity/timeout diagnostics.
    #   - refined_records: the corresponding retained sub-grid points from
    #                      step 8c (across all layers), dedup'd by quantised
    #                      coord so adjacent cells' shared edges collapse.
    # `_recorder_stage[0]` is flipped between "coarse" and "refined"
    # by the orchestration loop below.  Combined with the per-element
    # set `refined_coarse_keys` (coarse cells actually decomposed),
    # this lets the CSV emitter strip every coarse cell that was later
    # decomposed — guaranteeing the output has no overlap between the
    # coarse and refined sections.
    coarse_records: Dict[Tuple, PointResult] = {}
    refined_records: Dict[Tuple, PointResult] = {}
    refined_coarse_keys: set = set()
    _recorder_stage = ["coarse"]

    # The recorder stage flips to "refined" the FIRST TIME a coord
    # arrives that is NOT a coarse-grid vertex.  Coarse-grid coords
    # land EXACTLY on axis values; refined sub-grid coords land
    # between them.  This lets the wrapped solve_fn auto-segregate
    # coarse vs refined records without the sweep driver having to
    # peek into the solver pipeline.
    _coarse_vertex_sets: Dict[str, frozenset] = {
        ax.name: frozenset(round(float(v), 9) for v in ax.values)
        for ax in axes
    }
    _axis_domain_bounds: Dict[str, Tuple[float, float]] = {
        ax.name: tuple(float(value) for value in ax.range)
        for ax in axes
    }

    def solve_fn(coords: Dict[str, float],
                 x0: Optional[np.ndarray]) -> PointResult:
        if _recorder_stage[0] == "coarse":
            if any(
                round(float(v), 9) not in _coarse_vertex_sets.get(
                    k, frozenset())
                for k, v in coords.items()
            ):
                _recorder_stage[0] = "refined"
        res = _solve_fn_inner(coords, x0)
        # Endpoint-centred refinement cells can create a private numerical
        # support halo outside the requested sweep interval.  Those solves
        # may seed in-domain neighbours but must never enter persisted
        # machine-readable artifacts.
        inside_domain = all(
            lower - 1.0e-12 * max(1.0, abs(lower), abs(upper))
            <= float(coords.get(name, float("nan")))
            <= upper + 1.0e-12 * max(1.0, abs(lower), abs(upper))
            for name, (lower, upper) in _axis_domain_bounds.items()
        )
        if inside_domain and _retain_full_speciation_record(res):
            key = tuple(sorted(
                (k, round(float(v), 9)) for k, v in coords.items()
            ))
            if _recorder_stage[0] == "coarse":
                coarse_records[key] = res
            else:
                refined_records[key] = res
        return res

    # 6. Construct the N-D solver.  All grid-level pipeline work is
    #    invoked through the SINGLE public method ``NDGridSolver.solve``
    #    below; this driver never reaches into private stage methods.
    nd_solver = NDGridSolver(
        solve_fn, built.n_basis,
        built_system=built, debug=debug,
    )

    output_paths: List[str] = []
    all_boundaries: Dict[str, object] = {}
    safe_name = built.system_name.replace(" ", "_").replace("-", "_")

    # Snapshot directory (only used by 2-D rich emitter; safe to
    # create for any ndim).
    snap_dir = out_dir / "_snapshots"
    safe_mkdir(snap_dir)

    # Effective refinement factor for the final N-D label raster.
    _refinement_disabled = n_layers == 0
    _effective_refine_factor = (
        1 if _refinement_disabled else refine_factor ** n_layers
    )

    # Per-layer snapshot callback (2-D only): render an intermediate
    # Pourbaix PNG at each refinement layer using the same fine-grid
    # label tensor the solver hands back via the snapshot tuple.  No
    # solver back-references: the callback is a pure data sink.
    _snap_per_layer = (ndim == 2 and not _refinement_disabled)

    def _per_layer_callback(
        coarse_grid, element_name, boundaries,
        layer_idx, current_pts, xcache,
    ):
        if not _snap_per_layer:
            return
        try:
            from sweep_pipelines._output_and_plotting._output_topology_compactor.fine_label_map_assembler import (
                build_and_patch_fine_label_map,
            )
            from .pourbaix_sweep_export import (
                emit_refined_topology_snapshot,
            )
            eff = refine_factor ** layer_idx
            snapshot = build_and_patch_fine_label_map(
                coarse_grid, element_name,
                point_solve_fn=solve_fn,
                built_system=built,
                x_cache=xcache or {},
                refine_factor=eff,
                debug=False,
            )
            out_png = snap_dir / (
                f"snap_layer{layer_idx:02d}_eff{eff}x_{element_name}.png"
            )
            emit_refined_topology_snapshot(
                coarse_grid, boundaries, element_name, built,
                snapshot=snapshot,
                refine_factor_eff=eff,
                layer_idx=layer_idx,
                out_path=out_png,
                effective_component_totals=effective_component_totals,
                debug=False,
            )
            if debug:
                log.log(
                    f"[snapshot] Layer {layer_idx} (eff {eff}x) "
                    f"-> {out_png.name}"
                )
        except Exception as _exc:
            if debug:
                log.log(f"[snapshot] Layer {layer_idx} failed: {_exc}")

    # 6b. Run the entire grid pipeline through the SINGLE public solver
    #    entry point.  ``NDGridSolver.solve`` performs: coarse solve
    #    (BFS + retries + interpolation) -> per-element labelling ->
    #    boundary detection -> multi-layer refinement (with per-layer
    #    snapshot callback) -> topology extraction -> fine label map
    #    (compose + patch + vote).  No private methods are called by
    #    this driver.
    t6 = time.perf_counter()
    if debug:
        log.log(f"[step 6] Running full N-D solver pipeline ...")
    result = nd_solver.solve(
        axes,
        point_timeout_s=POINT_TIMEOUT_S,
        label_elements=list(built.principal_elements),
        refine=not _refinement_disabled,
        refine_factor=refine_factor,
        n_layers=n_layers,
        per_layer_callback=_per_layer_callback,
        checkpoint_dir=out_dir / "_checkpoints" / "nd_grid",
        checkpoint_identity={
            "sweep": "pourbaix",
            "system_name": built.system_name,
        },
    )
    grid = result.grid

    # Exclude exactly the coarse cells that the refiner actually
    # decomposed.  BoundaryCellND records are canonical transition facets
    # anchored on their lower-index side; deriving this set from those
    # anchors omitted the opposite incident cells.  ``refined_cells`` is
    # the authoritative, deduplicated record of all selected root cells
    # across every principal element.
    if not _refinement_disabled:
        for _cell_idx in (grid.refined_cells or {}):
            _coord = {
                axes[d].name: float(axes[d].values[_cell_idx[d]])
                for d in range(ndim)
            }
            _key = tuple(sorted(
                (k, round(float(v), 9)) for k, v in _coord.items()
            ))
            refined_coarse_keys.add(_key)

    if debug:
        n_conv = int(np.sum(grid.converged_mask))
        n_tot = int(np.prod(grid.shape))
        log.log(f"[step 6] Solver pipeline done "
                f"({n_conv}/{n_tot} coarse converged, "
                f"{time.perf_counter()-t6:.1f}s, "
                f"{len(result.per_element)} elements)")

    # 7. Per-element output emission (coarse PNG/CSV + refined PNG/CSV +
    #    topology JSON + speciation).  All data is already in
    #    ``result.per_element`` — no further solver calls here.
    for elem in built.principal_elements:
        er = result.per_element[elem]
        boundaries = er.boundaries
        all_boundaries[elem] = boundaries

        if debug:
            log.log(f"--- Outputs for principal element {elem} ---")

        # 7a. (2-D only) Coarse label-map + coarse PNG (pre-refinement view)
        if ndim == 2:
            from .pourbaix_sweep_export import emit_coarse_output
            pH_axis = next((a for a in axes if a.name == "pH"), None)
            E_axis = next((a for a in axes if a.name == "E_V"), None)
            if pH_axis is not None and E_axis is not None:
                _pH_range = (float(pH_axis.values[0]),
                             float(pH_axis.values[-1]))
                _E_range = (float(E_axis.values[0]),
                            float(E_axis.values[-1]))
                csv_path = out_dir / f"pourbaix_map_{safe_name}_{elem}.csv"
                img_path = out_dir / f"pourbaix_{safe_name}_{elem}.png"
                emit_coarse_output(
                    grid, built, boundaries, elem,
                    csv_path, img_path,
                    _pH_range, _E_range,
                    len(pH_axis.values), len(E_axis.values),
                    debug,
                    effective_component_totals=effective_component_totals,
                )
                output_paths.extend([str(csv_path), str(img_path)])

                # Snapshot: coarse grid with boundaries (pre-refinement view)
                try:
                    from .pourbaix_sweep_export import _get_topo_output_fns
                    _snap_fns = _get_topo_output_fns()
                    snap_coarse = snap_dir / f"snap_01_coarse_{elem}.png"
                    _snap_fns["plot_pourbaix"](
                        grid, built, str(snap_coarse),
                        principal_element=elem, boundary_cells=boundaries,
                        effective_component_totals=effective_component_totals,
                        debug=False)
                    if debug:
                        log.log(
                            f"[snapshot] Coarse grid -> {snap_coarse.name}"
                        )
                except Exception:
                    pass

        # 7b. Dim-aware refined output emission.  Reuse the exact final
        #     effective label raster that made ElementResult.topology.
        t7b = time.perf_counter()
        # Every refined output reconstructs topology from the same final
        # effective label raster.  This prevents 3-D and generic N-D
        # junctions from being carried forward from the coarse grid or an
        # earlier refinement layer.
        if _refinement_disabled:
            fine_label_map = None
        else:
            fine_label_map = er.effective_label_map
            if fine_label_map is None:
                raise RuntimeError(
                    "A refined NDGridSolver result must provide its final "
                    f"effective label map for element {elem!r}; refusing "
                    "to export the upstream coarse topology instead."
                )
        ref_paths = _emit_per_element_output(
            grid, built, elem, boundaries,
            er.topology, er.refined_points, er.x_cache,
            fine_label_map,
            axes=axes,
            out_dir=out_dir,
            safe_name=safe_name,
            refine_factor_eff=_effective_refine_factor,
            solve_fn=solve_fn,
            effective_component_totals=effective_component_totals,
            debug=debug,
        )
        output_paths.extend(ref_paths)
        if debug:
            log.log(f"[step 7b] Refined output done "
                    f"({time.perf_counter()-t7b:.1f}s, "
                    f"{len(ref_paths)} files)")

    # 8. Full speciation CSV — two sections, no overlap:
    #      [coarse_unrefined] coarse cells that were NOT decomposed
    #      [refined]          all sub-grid points from refinement
    #                         (final unified refined grid)
    #    Dim-agnostic: emitted for any ndim.
    try:
        from .pourbaix_sweep_export import emit_full_speciation_csv
        spec_csv = emit_full_speciation_csv(
            coarse_records, refined_records, refined_coarse_keys,
            built, axes,
            out_dir, safe_name, debug=debug,
        )
        if spec_csv is not None:
            output_paths.append(spec_csv)
            if debug:
                _excluded = (refined_coarse_keys | set(refined_records.keys())) \
                            & set(coarse_records.keys())
                _n_coarse_kept = len(coarse_records) - len(_excluded)
                log.log(f"[step 9] Full speciation CSV -> "
                        f"{pathlib.Path(spec_csv).name} "
                        f"({_n_coarse_kept} coarse + "
                        f"{len(refined_records)} refined points)")
    except Exception as exc:
        if debug:
            log.log(f"[step 9] Full speciation CSV failed: {exc}")

    elapsed = time.time() - t0
    if debug:
        log.log(f"{'='*60}")
        log.log(f"  Pipeline complete in {elapsed:.1f}s")
        log.log(f"  {len(output_paths)} output files")
        log.log(f"{'='*60}")
    log.close()

    return grid, built, all_boundaries, output_paths
