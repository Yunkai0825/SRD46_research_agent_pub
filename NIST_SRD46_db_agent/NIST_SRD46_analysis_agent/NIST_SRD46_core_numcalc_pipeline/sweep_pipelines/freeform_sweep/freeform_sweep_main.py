"""
freeform_sweep_main.py — Catch-all N-D sweep over arbitrary DOFs.
=================================================================

The freeform sweep is the unified handler for any sweep whose axes /
constraints do not match the canonical ``pH_sweep`` (strict 1-D pH)
or ``pourbaix_sweep`` (2-D pH x E_V, optionally 3-D with a_w) shapes.
Typical use cases:

    - 1-D scan along a non-physical-axis equation (e.g. a Nernst-line
      where ``E_V = -0.059 * pH``: declare pH as axis with
      ``E_V_freeform`` + ``custom_freeform`` mapping).
    - Sweeps over user-declared scalars in ``freeform_vars_define``.
    - Sweeps with composite ``[X]_constr={constr_1,…}`` plus
      stoichiometric ``custom_freeform`` chains.
    - Any combination of total-concentration axes
      (``[<metal>]_tot_axis``, ``[<ligand>]_tot_axis``).

The handler reuses the *same* solver + N-D grid + labeller pipeline
used by Pourbaix sweeps; the only difference is that the axes set is
arbitrary and the output is axis-agnostic (one wide CSV per principal
element plus a topology JSON).

Public API
----------
- ``run_freeform_sweep`` — canonical entry point.
"""
from __future__ import annotations

import pathlib
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from solvers_and_topology.nd_grid import GridAxis, NDGridSolver
from sweep_pipelines._output_and_plotting._output_topology_compactor.compact_nd import (
    compact_topology_nd,
)
from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_export import (
    export_topology_json,
)
from sweep_pipelines._output_and_plotting._output_topology_compactor.predominance_verdict import (
    export_predominance_verdict,
)
from sweep_pipelines._sweep_input_entry_point.sweep_dispatcher import (
    build_solver_chain,
    parse_source,
)
from sweep_pipelines._sweep_input_entry_point.grid_refinement_contract import (
    normalize_grid_refinement,
)

# ------------------------------------------------------------------
#  Axis-spec normalisation
# ------------------------------------------------------------------

def _coerce_axes(axes: Sequence[Any]) -> List[GridAxis]:
    """Convert each entry of *axes* to a :class:`GridAxis`.

    Accepts:
      - ``GridAxis``                      → passed through.
      - ``dict`` with explicit ``{name, min, max, n_points}``.
      - ``dict`` with ``{name, values}``.
    """
    out: List[GridAxis] = []
    for spec in axes:
        if isinstance(spec, GridAxis):
            out.append(spec); continue
        if not isinstance(spec, dict) or "name" not in spec:
            raise ValueError(
                f"freeform_sweep axis spec must be GridAxis or dict with "
                f"'name'; got {spec!r}")
        name = str(spec["name"])
        if "values" in spec:
            vals = np.asarray(spec["values"], dtype=np.float64)
        else:
            lo_raw = spec.get("min", spec.get("low", "Not defined"))
            hi_raw = spec.get("max", spec.get("high", "Not defined"))
            n_raw = spec.get("n_points", spec.get("n", "Not defined"))
            if "Not defined" in (lo_raw, hi_raw, n_raw):
                raise ValueError(
                    f"freeform axis {name!r} must declare min, max, and n_points")
            if any(isinstance(value, bool) for value in (lo_raw, hi_raw, n_raw)):
                raise ValueError(
                    f"freeform axis {name!r} numeric fields cannot be booleans")
            lo = float(lo_raw)
            hi = float(hi_raw)
            n = int(n_raw)
            if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo or n < 2:
                raise ValueError(
                    f"freeform axis {name!r} must have finite increasing "
                    "bounds and n_points >= 2")
            vals = np.linspace(lo, hi, n)
        if vals.ndim != 1 or len(vals) < 2 or not np.all(np.isfinite(vals)):
            raise ValueError(
                f"freeform axis {name!r} values must be a finite 1-D array "
                "with at least two points")
        out.append(GridAxis(name=name, values=vals,
                            display_label=str(spec.get("display_label", name))))
    if not out:
        raise ValueError("freeform_sweep requires at least one axis")
    return out


def _emit_freeform_predominance_verdict(
    *,
    topology,
    topology_path: pathlib.Path,
    axes: Sequence[GridAxis],
    final_label_map,
    built,
    metadata: Dict[str, Any],
) -> List[str]:
    """Export a verdict from the same final classified field as topology."""

    verdict_metadata = dict(metadata)
    components = list(getattr(built, "element_names", None) or [])
    components.extend(list(getattr(built, "ligand_names", None) or []))
    if components:
        verdict_metadata["components"] = components
    calculation_species = getattr(
        built, "calculation_species_by_principal_element", None
    )
    if calculation_species:
        verdict_metadata["calculation_species_by_principal_element"] = (
            calculation_species
        )
    if any(axis.name == "E_V" for axis in axes):
        verdict_metadata.setdefault("potential_reference", "SHE")

    artifacts = export_predominance_verdict(
        topology,
        topology_path,
        axes=list(axes),
        final_label_map=final_label_map,
        built_metadata=verdict_metadata,
        sweep_method="Freeform predominance",
    )
    return [str(artifacts["markdown_path"]), str(artifacts["json_path"])]


# ------------------------------------------------------------------
#  Public API
# ------------------------------------------------------------------

def run_freeform_sweep(
    source,
    *,
    axes: Sequence[Any],
    output_dir: Optional[Union[str, pathlib.Path]] = None,
    temperature_K: Optional[float] = None,
    ionic_strength: Optional[float] = None,
    refine_factor: Optional[int],
    n_layers: int,
    debug: bool = False,
    prefix: Optional[str] = None,
    compiled_constraints: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run an N-D freeform sweep through the unified solver pipeline.

    Parameters
    ----------
    source
        Card source — path, dict, or pre-built ``FreeEnergyReport``.
    axes
        Ordered list of axis specs (see ``_coerce_axes``).  Axis names
        may be any DOF that the compiled constraints can map (e.g.
        ``"pH"``, ``"E_V"``, ``"a_w"``, ``"[Cu]_total"``,
        ``"[ligand_5760]_total"``, user-declared scalars from
        ``freeform_vars_define``).
    output_dir
        If supplied, writes one wide CSV per principal element plus a
        topology JSON when available.
    ionic_strength, temperature_K
        Forwarded to source resolver / built system.
    refine_factor, n_layers
        Explicit boundary-refinement policy.  Set ``n_layers=0`` and
        ``refine_factor=None`` to disable refinement.  For a 2-D or 3-D
        refined sweep, set ``n_layers>=1`` and ``refine_factor>=2``.
    debug
        Verbose progress logging.
    prefix
        Filename prefix for output files. Default: derived from
        ``built.system_name``.
    compiled_constraints
        Compiled-constraint object produced upstream.  Always required
        for a true freeform run; if omitted the axis values flow
        through unchanged (pH / E_V / a_w only).

    Returns
    -------
    dict with keys:
        ``report``         — FreeEnergyReport
        ``built``          — BuiltSystem
        ``grid``           — NDGrid (any dimensionality)
        ``per_element``    — dict[element → ElementResult]  (may be {})
        ``topologies``     — dict[element → CompactTopologyND | None]
        ``output_paths``   — list[str]
    """
    t0 = time.time()

    axes_list = _coerce_axes(axes)
    n_layers, refine_factor = normalize_grid_refinement(
        n_layers=n_layers,
        factor=refine_factor,
        context="freeform refinement",
    )
    if n_layers >= 1 and len(axes_list) not in (2, 3):
        raise ValueError(
            "freeform boundary refinement requires a 2-D or 3-D axis set; "
            "use n_layers=0 for an unrefined sweep"
        )

    report = parse_source(source, temperature_K=temperature_K)

    built, unified_solve_fn = build_solver_chain(
        report,
        ionic_strength=ionic_strength,
        system_name=getattr(report, "system_name", "") or "",
        compiled_constraints=compiled_constraints,
    )

    axis_names = [ax.name for ax in axes_list]

    if debug:
        print(f"[freeform_sweep] System: {built.system_name}")
        print(f"[freeform_sweep] Basis : {built.n_basis} "
              f"(elements={built.element_names}, "
              f"ligands={list(report.ligand_ids)})")
        ax_desc = ", ".join(
            f"{ax.name}[{ax.n}]={ax.values[0]:.4g}->{ax.values[-1]:.4g}"
            for ax in axes_list
        )
        print(f"[freeform_sweep] Axes  : {ax_desc}")
        print(f"[freeform_sweep] I     : {built.ionic_strength} "
              f"(mode={getattr(report, 'ionic_mode', 'fixed')})")
        print(f"[freeform_sweep] constraints: "
              f"{'on' if compiled_constraints else 'off'}")

    nd_solver = NDGridSolver(
        unified_solve_fn, built.n_basis,
        built_system=built, debug=debug,
    )

    do_refine = n_layers >= 1
    result = nd_solver.solve(
        axes_list,
        refine=do_refine,
        refine_factor=refine_factor,
        n_layers=n_layers,
        checkpoint_dir=(
            pathlib.Path(output_dir) / "_checkpoints" / "nd_grid"
            if output_dir is not None else None
        ),
        checkpoint_identity={
            "sweep": "freeform",
            "system_name": built.system_name,
        },
    )
    grid = result.grid

    if debug:
        n_conv = int(np.sum(grid.converged_mask))
        n_total = int(np.prod(grid.shape))
        print(f"[freeform_sweep] Coarse solve: {n_conv}/{n_total} converged "
              f"({time.time() - t0:.1f}s)")

    # ── Output emission ─────────────────────────────────────────
    output_paths: List[str] = []
    out_path: Optional[pathlib.Path] = None
    if output_dir is not None:
        from ._paths import long_path as _long
        out_path = pathlib.Path(output_dir)
        import os as _os
        _os.makedirs(_long(out_path), exist_ok=True)

    safe_name = (built.system_name or "system").replace(" ", "_").replace("-", "_")
    emit_prefix = prefix if prefix is not None else safe_name

    topologies: Dict[str, Any] = {}
    per_element = result.per_element or {}

    if out_path is not None:
        from .freeform_sweep_export import (
            emit_cell_table_csv,
            emit_fraction_csvs,
            write_run_params_json,
        )

        # ── 1. axis-agnostic per-cell table (always) ──────────────
        cell_csv = emit_cell_table_csv(
            grid, built, out_path, prefix=emit_prefix, debug=debug,
        )
        output_paths.append(cell_csv)

        # ── 2. fraction CSVs per principal element (always) ───────
        frac_paths = emit_fraction_csvs(
            grid, built, out_path, prefix=emit_prefix, debug=debug,
        )
        output_paths.extend(frac_paths)

        # ── 3. run-params JSON ────────────────────────────────────
        params_path = write_run_params_json(
            built, axes_list, out_path, prefix=emit_prefix,
            ionic_strength=ionic_strength,
            extras={
                "axis_names": [ax.name for ax in axes_list],
                "axes_shape": list(grid.shape),
                "n_converged": int(np.sum(grid.converged_mask)),
                "constraints_active": bool(compiled_constraints is not None),
            },
        )
        output_paths.append(params_path)

        # ── 4. per-element topology JSON (when available) ─────────
        for elem, el_res in per_element.items():
            topo = el_res.topology
            verdict_payload = None
            try:
                if topo is not None and hasattr(topo, "boundaries") \
                        and topo.boundaries:
                    topo = compact_topology_nd(topo, csv_dir=None)
                if topo is not None:
                    topo_path = out_path / f"topology_{safe_name}_{elem}.json"
                    if el_res.effective_label_map is not None:
                        final_axis_values, final_labels, final_catalog = (
                            el_res.effective_label_map
                        )
                    else:
                        final_axis_values = [axis.values for axis in axes_list]
                        final_labels = grid.labels_per_element[elem]
                        final_catalog = grid.label_catalog_per_element[elem]
                    human_catalog = {
                        int(key): built.spec_id_to_name.get(value, value)
                        for key, value in dict(final_catalog or {}).items()
                    }
                    if hasattr(topo, "label_catalog"):
                        topo.label_catalog = dict(human_catalog)
                    effective_shape = (
                        list(final_labels.shape)
                    )
                    meta = {
                        "system_name": built.system_name,
                        "element":     elem,
                        "axes":        axis_names,
                        "axes_shape":  effective_shape,
                        "topology_resolution": (
                            "final_effective_grid"
                            if el_res.effective_label_map is not None
                            else "coarse_grid"
                        ),
                    }
                    export_topology_json(
                        topo, _long(topo_path), metadata=meta, debug=debug,
                    )
                    output_paths.append(str(topo_path))
                    verdict_payload = (
                        topo,
                        topo_path,
                        (final_axis_values, final_labels, human_catalog),
                        meta,
                    )
                topologies[elem] = topo
            except Exception as exc:
                if debug:
                    print(f"[freeform_sweep] Topology emit skipped for "
                          f"{elem}: {exc}")
                topologies[elem] = None
            if verdict_payload is not None:
                verdict_topology, verdict_path, verdict_map, verdict_meta = (
                    verdict_payload
                )
                # A missing mandatory LLM-facing verdict is a route failure,
                # not an optional plotting failure; let the error propagate.
                output_paths.extend(
                    _emit_freeform_predominance_verdict(
                        topology=verdict_topology,
                        topology_path=verdict_path,
                        axes=axes_list,
                        final_label_map=verdict_map,
                        built=built,
                        metadata=verdict_meta,
                    )
                )

        # ── 5. Optional 1-D plot (when ndim == 1) ─────────────────
        if grid.ndim == 1:
            try:
                from .freeform_sweep_export import emit_1d_fraction_plots
                plot_paths = emit_1d_fraction_plots(
                    grid, built, out_path, prefix=emit_prefix, debug=debug,
                )
                output_paths.extend(plot_paths)
            except Exception as exc:
                if debug:
                    print(f"[freeform_sweep] 1-D plot skipped: {exc}")

        # ── 6. Optional 2-D label heatmap (when ndim == 2) ────────
        if grid.ndim == 2:
            try:
                from .freeform_sweep_export import emit_2d_label_heatmaps
                heat_paths = emit_2d_label_heatmaps(
                    grid, built, out_path, prefix=emit_prefix, debug=debug,
                )
                output_paths.extend(heat_paths)
            except Exception as exc:
                if debug:
                    print(f"[freeform_sweep] 2-D heatmap skipped: {exc}")

    if debug:
        print(f"[freeform_sweep] Done in {time.time() - t0:.1f}s "
              f"({len(output_paths)} output files)")

    return {
        "report":       report,
        "built":        built,
        "grid":         grid,
        "per_element":  per_element,
        "topologies":   topologies,
        "output_paths": output_paths,
    }
