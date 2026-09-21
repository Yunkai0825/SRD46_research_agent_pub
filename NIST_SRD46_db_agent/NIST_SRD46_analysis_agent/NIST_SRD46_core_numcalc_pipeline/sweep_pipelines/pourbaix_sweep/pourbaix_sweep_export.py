"""
pourbaix_sweep_export.py
========================
Output / export functions for the Pourbaix sweep (Layer 5).

Provides:
  - ``emit_coarse_output``   — write CSV + plot for the coarse grid
  - ``emit_refined_output``  — write CSV, topology JSON, speciation CSV/plot,
                                and refined diagram plot for one element
  - ``generate_all_output``  — registry-compatible master entry point

Sweep-registry metadata (SWEEP_ID, SWEEP_PARAMS, sweep_fn) also lives here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .pourbaix_sweep_main import run_pourbaix_sweep
from .pourbaix_sweep_settings import RDP_ENVELOPE_N, DEBUG
from sweep_pipelines._path_utils import long_path, safe_mkdir

# ── Registry metadata ─────────────────────────────────────────
SWEEP_ID = "pourbaix_sweep"
SWEEP_DESCRIPTION = (
    "Full 2D pH-E Pourbaix diagram: coarse grid → label → "
    "boundary detection → topology refinement → CSV + plot."
)
SWEEP_PARAMS = {
    "pH_range":      {"type": "tuple", "required": True,
                      "help": "pH domain (min, max)"},
    "E_range":       {"type": "tuple", "required": True,
                      "help": "E domain (min, max) in V vs SHE"},
    "n_pH":          {"type": "int",   "required": True,
                      "help": "Number of pH grid points"},
    "n_E":           {"type": "int",   "required": True,
                      "help": "Number of E grid points"},
    "refine_factor": {"type": "int|null", "required": True,
                      "help": "Null when disabled; otherwise >=2"},
    "n_layers":      {"type": "int", "required": True,
                      "help": "0 disables refinement; >=1 enables it"},
    "output_dir":    {"type": "str",   "default": None,
                      "help": "Output directory path"},
}

# ── Callable aliases for registry ─────────────────────────────
sweep_fn = run_pourbaix_sweep


# ==================================================================
#  Output helpers (extracted from pourbaix_sweep_main.py)
# ==================================================================

def _effective_totals_metadata(built, effective_component_totals):
    """Serialize constraint-resolved totals into machine-readable outputs."""
    if effective_component_totals is None:
        return {}
    names = list(built.element_names) + list(built.ligand_names)
    totals = list(effective_component_totals)
    if len(names) != len(totals):
        raise ValueError(
            "effective_component_totals must contain one value for "
            "each element and ligand"
        )
    values = ";".join(
        f"{name}={'varies' if value is None else format(float(value), '.16g')}"
        for name, value in zip(names, totals)
    )
    return {
        "component_totals_M": values,
        "component_totals_source": "compiled_constraints",
    }


def reconstruct_topology_from_fine_label_map(
    coarse_grid,
    fine_label_map,
    *,
    debug: bool = False,
):
    """Extract topology exclusively from a final effective label raster.

    ``fine_label_map`` is the ``(axis_values, labels, catalog)`` tuple
    returned by ``build_and_patch_fine_label_map``.  Rebuilding the labelled
    grid and its canonical transition facets here ensures that junctions,
    boundaries, and regions all describe this final layer rather than an
    upstream coarse grid or an earlier refinement layer.

    Returns ``(topology, fine_axes, effective_labels, raw_topology)``.
    ``effective_labels`` is the raster the fixed ``topology`` was extracted
    from: the input map with the topology fixer's marks applied (the
    deep-merged grid), so output metadata, the label CSV and the verdict
    describe the same field as the topology; ``raw_topology`` is the
    rule-free pre-fix extraction of the solver's raster, preserved for
    audit export.
    """
    from solvers_and_topology.nd_grid.effective_topology import (
        extract_effective_topology,
    )

    topology, fine_axes, labels_fine, _, raw_topology = (
        extract_effective_topology(
            coarse_grid,
            fine_label_map,
            debug=debug,
        )
    )
    return topology, fine_axes, labels_fine, raw_topology


def _get_topo_output_fns():
    """Lazy-import output-only topology functions."""
    from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_export import (
        export_topology_json,
    )
    from sweep_pipelines._output_and_plotting.pourbaix_diagrams.csv_exporter import (
        export_pourbaix_csv,
    )
    from sweep_pipelines._output_and_plotting.pourbaix_diagrams.plotter import (
        plot_pourbaix,
    )
    from sweep_pipelines._output_and_plotting._output_topology_compactor.predominance_verdict import (
        export_predominance_verdict,
    )
    fns = {
        "export_topology_json": export_topology_json,
        "export_predominance_verdict": export_predominance_verdict,
        "export_pourbaix_csv": export_pourbaix_csv,
        "plot_pourbaix": plot_pourbaix,
    }
    try:
        from sweep_pipelines._output_and_plotting.pourbaix_diagrams.speciation_along_boundary_export import (
            export_speciation_csv,
            plot_speciation_along_boundaries,
        )
        fns["export_speciation_csv"] = export_speciation_csv
        fns["plot_speciation_along_boundaries"] = plot_speciation_along_boundaries
    except ImportError:
        fns["export_speciation_csv"] = None
        fns["plot_speciation_along_boundaries"] = None
    return fns


def _pourbaix_verdict_axis_order(axes) -> Optional[List[str]]:
    """Use the reference report's pH, E order without relabelling data."""

    names = [str(axis.name) for axis in axes]
    if "pH" in names and "E_V" in names:
        return ["pH", "E_V"]
    return None


def _verdict_metadata(built, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich persisted export metadata with available system declarations."""

    result = dict(metadata)
    components = list(getattr(built, "element_names", None) or [])
    components.extend(list(getattr(built, "ligand_names", None) or []))
    if components:
        result["components"] = components
    totals = result.get("component_totals_M")
    if totals:
        result["constraints"] = [f"component totals (M): {totals}"]
    calculation_species = getattr(
        built, "calculation_species_by_principal_element", None
    )
    if calculation_species:
        result["calculation_species_by_principal_element"] = (
            calculation_species
        )
    # Card-sourced phase / formal-oxidation-state maps let the verdict group
    # regions, boundaries, and junctions without any geometric redox guess.
    try:
        from solvers_and_topology._input_solver_helper.built_system_from_dGreport import (
            principal_element_card_maps,
        )

        card_maps = principal_element_card_maps(built)
        if card_maps.get("phase"):
            result["species_phase_map"] = card_maps["phase"]
        if card_maps.get("oxidation_state"):
            result["species_oxidation_state_map"] = card_maps["oxidation_state"]
    except Exception as exc:
        # A resolver failure means this card shape is unsupported here; the
        # verdict must report it instead of silently dropping the grouping.
        result["species_card_maps_error"] = f"{type(exc).__name__}: {exc}"
    result.setdefault("potential_reference", "SHE")
    return result


def _emit_predominance_verdict(
    *,
    topology,
    topology_path: Path,
    axes,
    labels,
    label_catalog,
    built,
    metadata: Dict[str, Any],
    export_fn=None,
) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """Write the LLM-facing verdict from the same final field as topology.

    Returns ``(paths, report)`` so callers can reuse the verdict's canonical
    feature ids in sidecar exports.
    """

    if export_fn is None:
        from sweep_pipelines._output_and_plotting._output_topology_compactor.predominance_verdict import (
            export_predominance_verdict as export_fn,
        )
    artifacts = export_fn(
        topology,
        topology_path,
        axes=list(axes),
        final_label_map=(
            [axis.values for axis in axes],
            labels,
            dict(label_catalog or {}),
        ),
        built_metadata=_verdict_metadata(built, metadata),
        sweep_method="Pourbaix",
        display_axis_order=_pourbaix_verdict_axis_order(axes),
    )
    return (
        [str(artifacts["markdown_path"]), str(artifacts["json_path"])],
        artifacts.get("report"),
    )


def emit_coarse_output(
    grid, built, boundaries, elem,
    csv_path, out_img_path,
    pH_range, E_range, n_pH, n_E,
    debug=DEBUG,
    *,
    effective_component_totals=None,
):
    """Write coarse-grid CSV + plot image (no re-solve)."""
    fns = _get_topo_output_fns()
    labels = grid.labels_per_element[elem]
    catalog = dict(grid.label_catalog_per_element[elem])
    pH_vals = grid.pH_values
    E_vals = grid.E_values

    csv_meta = {
        "system_name": built.system_name,
        "element": elem,
        "n_pH_coarse": n_pH, "n_E_coarse": n_E,
        "n_pH_fine": len(pH_vals), "n_E_fine": len(E_vals),
        "pH_range": f"{pH_range[0]},{pH_range[1]}",
        "E_range": f"{E_range[0]},{E_range[1]}",
        "resolution": "coarse",
    }
    csv_meta.update(
        _effective_totals_metadata(built, effective_component_totals)
    )
    fns["export_pourbaix_csv"](
        pH_vals, E_vals, labels, catalog, str(csv_path),
        metadata=csv_meta,
        spec_id_to_name=built.spec_id_to_name,
        debug=debug,
    )
    fns["plot_pourbaix"](
        grid, built, str(out_img_path),
        principal_element=elem,
        boundary_cells=boundaries,
        effective_component_totals=effective_component_totals,
        debug=debug,
    )


def emit_refined_topology_snapshot(
    coarse_grid,
    boundaries,
    elem,
    built,
    *,
    snapshot,
    refine_factor_eff: int,
    layer_idx: int,
    out_path,
    effective_component_totals=None,
    debug: bool = False,
) -> Optional[str]:
    """Emit a per-layer Pourbaix snapshot from a pre-built fine label map.

    The ``snapshot`` argument is the
    ``(axes_fine_vals, labels_fine, map_catalog)`` triple produced by
    :meth:`NDGridSolver.solve` and handed to the sweep through the
    ``per_layer_callback`` hook.  This function never re-solves and
    never calls the solver itself; it only consumes the pre-built
    label tensor and renders topology + PNG.

    Returns the absolute path string of the produced PNG, or None on
    failure.
    """
    from sweep_pipelines._output_and_plotting._output_topology_compactor.compact_nd import (
        compact_topology_nd,
    )
    import numpy as _np
    from solvers_and_topology.nd_grid.data_types import (
        GridAxis as _GA, BoundaryCellND as _BC,
    )
    from solvers_and_topology._output_topology_mapper.topology_nd.topology_nd import (
        extract_topology_nd as _extract_topo,
    )

    fns = _get_topo_output_fns()

    if snapshot is None:
        if debug:
            print(f"[snapshot] No snapshot supplied at layer {layer_idx}; skip.")
        return None

    axes_fine_vals, labels_fine, map_catalog = snapshot
    iE = coarse_grid.axis_index("E_V")
    iPH = coarse_grid.axis_index("pH")
    E_fine = axes_fine_vals[iE]
    pH_fine = axes_fine_vals[iPH]
    E_domain = coarse_grid.axes[iE].range
    pH_domain = coarse_grid.axes[iPH].range
    if iE != 0:
        labels_fine = np.moveaxis(labels_fine, iE, 0)
        iPH = 1 - iE
    # 2. Vectorised boundary-cell detection on the fine grid
    _fine_axes = [
        _GA("E_V", E_fine, domain_range=E_domain),
        _GA("pH", pH_fine, domain_range=pH_domain),
    ]

    class _LabelGrid:
        def __init__(self, axes, labels, catalog):
            self.axes = axes
            self.labels = labels
            self.label_catalog = catalog or {}
            self.labels_per_element = None
            self.label_catalog_per_element = None
        @property
        def ndim(self):
            return len(self.axes)
        @property
        def shape(self):
            return tuple(len(ax.values) for ax in self.axes)

    _fine_grid = _LabelGrid(_fine_axes, labels_fine, map_catalog)

    _fine_bcells = []
    for _ad in range(len(_fine_axes)):
        _aname = _fine_axes[_ad].name
        slc_L = [slice(None)] * labels_fine.ndim
        slc_R = [slice(None)] * labels_fine.ndim
        slc_L[_ad] = slice(None, -1)
        slc_R[_ad] = slice(1, None)
        L_arr = labels_fine[tuple(slc_L)]
        R_arr = labels_fine[tuple(slc_R)]
        diff = (L_arr != R_arr) & (L_arr >= 0) & (R_arr >= 0)
        for idx in zip(*_np.where(diff)):
            _fine_bcells.append(_BC(
                index=tuple(idx), axis=_ad, axis_name=_aname,
                left_label=int(L_arr[idx]), right_label=int(R_arr[idx]),
                btype="unknown",
            ))

    # 3. Topology extraction + compaction (same pipeline as final output)
    topo = _extract_topo(_fine_grid, _fine_bcells,
                         refined_points=[], debug=debug)
    if hasattr(topo, "settings") and isinstance(topo.settings, dict):
        topo.settings["axis_spacing_coarse"] = {
            ax.name: float(_np.median(_np.diff(
                _np.asarray(ax.values, dtype=float))))
            for ax in coarse_grid.axes
            if getattr(ax, "values", None) is not None and len(ax.values) > 1
        }
    if hasattr(topo, "boundaries") and topo.boundaries:
        topo = compact_topology_nd(
            topo, rdp_epsilon=0.01, envelope_n=RDP_ENVELOPE_N,
            csv_dir=None,
        )
    if hasattr(topo, "label_catalog") and topo.label_catalog:
        topo.label_catalog = {
            int(k): built.spec_id_to_name.get(v, v)
            for k, v in topo.label_catalog.items()
        }

    # 4. Write fine label CSV alongside the PNG so the plotter can use
    #    it as the colour background (matches the final-output plot
    #    pathway, which passes ``csv_path``).
    out_path = Path(out_path)
    safe_mkdir(out_path.parent)
    snap_csv = out_path.with_suffix(".csv")
    csv_meta = {
        "system_name": built.system_name,
        "element": elem,
        "n_pH_fine": len(pH_fine), "n_E_fine": len(E_fine),
        "resolution": f"layer_{layer_idx}",
        "refine_factor_eff": refine_factor_eff,
    }
    csv_meta.update(
        _effective_totals_metadata(built, effective_component_totals)
    )
    try:
        fns["export_pourbaix_csv"](
            pH_fine, E_fine, labels_fine, map_catalog,
            str(snap_csv), metadata=csv_meta,
            spec_id_to_name=built.spec_id_to_name, debug=False,
        )
    except Exception:
        snap_csv = None

    plot_kwargs = dict(
        principal_element=elem,
        boundary_cells=boundaries,
        effective_component_totals=effective_component_totals,
        show_compact_controls=True,
        debug=False,
    )
    if snap_csv is not None:
        plot_kwargs["csv_path"] = str(snap_csv)
    if hasattr(topo, "features") and isinstance(
            getattr(topo, "features", None), dict):
        plot_kwargs["topology_map"] = topo
    elif hasattr(topo, "boundaries") and topo.boundaries:
        plot_kwargs["topology_map"] = topo

    try:
        fns["plot_pourbaix"](coarse_grid, built, str(out_path), **plot_kwargs)
    except Exception as _exc:
        if debug:
            print(f"[snapshot] plot_pourbaix failed at layer {layer_idx}: {_exc}")
        return None

    return str(out_path)


def emit_refined_output(
    grid, built, boundaries, elem,
    topo, segments, grid_solver,
    out_dir, safe_name,
    pH_range, E_range, n_pH, n_E,
    refine_factor,
    debug=DEBUG,
    *,
    fine_label_map=None,
    solve_fn=None,
    x_cache=None,
    effective_component_totals=None,
    export_raw_audit=False,
):
    """Write all refined outputs for one element: CSV, topology JSON,
    speciation along boundaries, and the refined diagram plot.

    Parameters
    ----------
    grid_solver       : legacy PourbaixGridSolver (deprecated, may be None)
    fine_label_map    : pre-built ``(axes_fine_vals, labels_fine,
                        map_catalog)`` triple from the solver's effective
                        label-map assembly.  REQUIRED for the rich 2-D output
                        path.
    solve_fn          : ``(coords, x0) -> PointResult`` callable used
                        only for speciation-along-boundary re-solves.
    topo              : pre-computed TopologyND or None
    export_raw_audit  : opt-in storage of the rule-free pre-fix topology
                        (``topology_raw_*.json``).  Audit-only: no
                        downstream output or verdict reads it, and it is
                        not written by default.

    Returns list of output file paths.
    """
    from sweep_pipelines._output_and_plotting._output_topology_compactor.compact_nd import (
        compact_topology_nd,
    )
    from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_csv_io import (
        export_features_csv,
    )
    from sweep_pipelines._output_and_plotting._output_topology_compactor.predominance_verdict import (
        verdict_feature_id_maps,
    )
    try:
        from sweep_pipelines._output_and_plotting.pourbaix_diagrams.speciation_along_boundary import (
            compute_speciation_along_boundaries,
        )
    except ImportError:
        compute_speciation_along_boundaries = None

    fns = _get_topo_output_fns()
    output_paths: List[str] = []

    # Fine label map: REQUIRED to be supplied pre-built by the caller from the
    # SolveResult bundle.
    if fine_label_map is None:
        raise ValueError(
            "emit_refined_output: fine_label_map must be supplied by "
            "the caller from ElementResult.effective_label_map."
        )
    axes_fine_vals, labels_fine, map_catalog = fine_label_map
    iE = grid.axis_index("E_V")
    iPH = grid.axis_index("pH")
    E_fine = axes_fine_vals[iE]
    pH_fine = axes_fine_vals[iPH]

    # ── Re-extract topology from the fine label map ──────────────
    # Shared effective-topology route: raw extraction, fixer analysis,
    # fixed extraction on the effective (deep-merged) label map.  The
    # returned labels ARE that effective map, and every artifact below
    # -- the label CSV, the plot background, the topology JSON and the
    # verdict report -- describes it, so the agent and the reviewer see
    # one consistent grid.  The solver's raster is recoverable from the
    # fixer's ``marks`` in the topology settings.
    topo, fine_axes, _effective_labels, topo_raw = (
        reconstruct_topology_from_fine_label_map(
            grid, fine_label_map, debug=debug,
        )
    )
    fix_report = (getattr(topo, "settings", None) or {}).get("topology_fix") or {}
    n_marks = len(fix_report.get("marks", []) or [])

    labels_for_csv = _effective_labels
    if iE != 0:
        labels_for_csv = __import__("numpy").moveaxis(
            labels_for_csv, iE, 0,
        )
    csv_path = out_dir / f"pourbaix_map_{safe_name}_{elem}.csv"
    csv_meta = {
        "system_name": built.system_name,
        "element": elem,
        "n_pH_coarse": n_pH, "n_E_coarse": n_E,
        "n_pH_fine": len(pH_fine), "n_E_fine": len(E_fine),
        "pH_range": f"{pH_range[0]},{pH_range[1]}",
        "E_range": f"{E_range[0]},{E_range[1]}",
        "label_source": (getattr(topo, "settings", None) or {}).get(
            "label_source", "solver_raster"),
        "fixer_marks": n_marks,
    }
    csv_meta.update(
        _effective_totals_metadata(built, effective_component_totals)
    )
    fns["export_pourbaix_csv"](
        pH_fine, E_fine, labels_for_csv, map_catalog,
        str(csv_path), metadata=csv_meta,
        spec_id_to_name=built.spec_id_to_name, debug=debug,
    )

    # Compact TopologyND → CompactTopologyND via dimension-stratified pipeline
    topo_precompact = None
    if hasattr(topo, "boundaries") and topo.boundaries:
        # Hold the full-geometry fixed topology; its feature CSVs are
        # written after the verdict so they can reuse its canonical ids.
        topo_precompact = topo
        # Bottom-up compaction
        topo = compact_topology_nd(
            topo, rdp_epsilon=0.01, envelope_n=RDP_ENVELOPE_N,
            csv_dir=None)

    if hasattr(topo, "label_catalog") and topo.label_catalog:
        topo.label_catalog = {
            int(k): built.spec_id_to_name.get(v, v)
            for k, v in topo.label_catalog.items()
        }

    # Export topology JSON (handles TopologyND and CompactTopologyND)
    topo_path = out_dir / f"topology_{safe_name}_{elem}.json"
    meta = {
        "system_name": built.system_name,
        "element": elem,
        # The legacy short keys now describe the topology being serialized;
        # retain the input-grid dimensions under explicit coarse keys.
        "n_pH": len(pH_fine), "n_E": len(E_fine),
        "n_pH_coarse": n_pH, "n_E_coarse": n_E,
        "n_pH_fine": len(pH_fine), "n_E_fine": len(E_fine),
        "pH_range": list(pH_range),
        "E_range": list(E_range),
        "grid_shape": [len(axis.values) for axis in fine_axes],
        "axis_values": {
            axis.name: axis.values.tolist() for axis in fine_axes
        },
    }
    meta.update(
        _effective_totals_metadata(built, effective_component_totals)
    )
    fns["export_topology_json"](topo, str(topo_path), metadata=meta, debug=debug)
    output_paths.append(str(topo_path))

    # Raw pre-fix topology: rule-free, uncompacted, strictly an audit
    # artifact.  No downstream output or verdict reads it, and it is only
    # stored on explicit request; when no fix applies the fixed export
    # above already carries the identical (renamed) solution.
    if export_raw_audit:
        if hasattr(topo_raw, "label_catalog") and topo_raw.label_catalog:
            topo_raw.label_catalog = {
                int(k): built.spec_id_to_name.get(v, v)
                for k, v in topo_raw.label_catalog.items()
            }
        raw_path = out_dir / f"topology_raw_{safe_name}_{elem}.json"
        fns["export_topology_json"](
            topo_raw, str(raw_path), metadata=meta, debug=debug,
        )
        output_paths.append(str(raw_path))
    verdict_paths, verdict_report = _emit_predominance_verdict(
        topology=topo,
        topology_path=topo_path,
        axes=fine_axes,
        labels=_effective_labels,
        label_catalog=(
            getattr(topo, "label_catalog", None) or map_catalog
        ),
        built=built,
        metadata=meta,
        export_fn=fns.get("export_predominance_verdict"),
    )

    # Feature CSVs come from the full-geometry fixed topology but are named
    # by the verdict's canonical prefixed ids, so every agent-facing
    # artifact identifies the same feature identically.
    if topo_precompact is not None:
        csv_topo_dir = out_dir / f"topo_csv_{safe_name}_{elem}"
        export_features_csv(
            topo_precompact, csv_topo_dir, prefix="topo",
            axis_names=(topo_precompact.settings or {}).get(
                "axis_names", []),
            verdict_ids=(
                verdict_feature_id_maps(verdict_report)
                if verdict_report else None
            ),
        )
    output_paths.extend(verdict_paths)

    # Speciation along boundaries
    # Resolve the solve_fn for speciation: prefer explicit solve_fn,
    # fall back to grid_solver.solid_manager.solve_point
    spec_solve_fn = None
    if solve_fn is not None:
        # Wrap (coords, x0) -> PointResult into legacy (pH, E, C, x0) -> result
        C_total = built.C_total
        def _legacy_spec_solve(pH, E_V, C, x0):
            return solve_fn({"pH": pH, "E_V": E_V}, x0)
        spec_solve_fn = _legacy_spec_solve
    elif grid_solver is not None:
        spec_solve_fn = grid_solver.solid_manager.solve_point

    if spec_solve_fn is not None and compute_speciation_along_boundaries is not None:
        spec_profiles = compute_speciation_along_boundaries(
            topo, spec_solve_fn, built,
            n_samples=50, debug=debug)
        if spec_profiles:
            if fns.get("export_speciation_csv") is not None:
                spec_paths = fns["export_speciation_csv"](
                    spec_profiles, str(out_dir),
                    prefix=f"speciation_{safe_name}_{elem}", debug=debug)
                output_paths.extend(spec_paths)
            if fns.get("plot_speciation_along_boundaries") is not None:
                spec_plot_path = out_dir / f"speciation_plot_{safe_name}_{elem}.png"
                plotted = fns["plot_speciation_along_boundaries"](
                    spec_profiles, topo, str(spec_plot_path), debug=debug)
                if plotted:
                    output_paths.append(str(spec_plot_path))

    # Refined plot (overwrites coarse)
    img_path = out_dir / f"pourbaix_{safe_name}_{elem}.png"
    plot_kwargs = dict(
        csv_path=str(csv_path),
        principal_element=elem,
        boundary_cells=boundaries,
        effective_component_totals=effective_component_totals,
        # The primary compact representation is displayed as literal
        # straight chords joining its selected raw boundary vertices.
        show_compact_controls=True,
        debug=debug,
    )
    # Pass topology data — CompactTopologyND or TopologyND
    if hasattr(topo, "features") and isinstance(getattr(topo, "features", None), dict):
        plot_kwargs["topology_map"] = topo
    elif hasattr(topo, "edges") and topo.edges:
        plot_kwargs["topology_map"] = topo
        plot_kwargs["boundary_segments"] = segments
        plot_kwargs["triple_points"] = getattr(topo, "nodes", None)
    elif hasattr(topo, "boundaries") and topo.boundaries:
        plot_kwargs["topology_map"] = topo
    fns["plot_pourbaix"](grid, built, str(img_path), **plot_kwargs)

    return output_paths


def generate_all_output(grid, built, all_boundaries, output_dir, **kwargs):
    """Alias that re-runs the pipeline output stages.

    Typically the sweep itself generates all output.  This function
    exists for registry compatibility — it's a no-op if the sweep
    was already run with ``output_dir``.
    """
    return output_dir


# ==================================================================
#  3-D output (compact topology JSON + 3-D topology plot)
# ==================================================================

def emit_output_3d(
    grid, built, elem, topo,
    out_dir: Path, safe_name: str,
    axes,
    *,
    fine_label_map=None,
    debug: bool = False,
) -> List[str]:
    """Emit topology JSON + 3-D topology PNG for a single element.

    Used for the ndim == 3 branch of the unified Pourbaix pipeline.
    """
    from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_export import (
        export_topology_json,
    )
    from sweep_pipelines._output_and_plotting._output_topology_compactor.compact_nd import (
        compact_topology_nd,
    )
    from sweep_pipelines._output_and_plotting.pourbaix_diagrams.plotter_3d_topology import (
        plot_3d_topology,
    )

    output_axes = list(axes)
    bulk_labels = grid.labels_per_element[elem]
    if fine_label_map is not None:
        topo, output_axes, bulk_labels, _ = (
            reconstruct_topology_from_fine_label_map(
                grid, fine_label_map, debug=debug,
            )
        )

    # Compact topology (simplify surfaces and curves)
    if hasattr(topo, "boundaries") and topo.boundaries:
        topo = compact_topology_nd(topo, rdp_epsilon=0.01)

    if hasattr(topo, "label_catalog") and topo.label_catalog:
        topo.label_catalog = {
            int(k): built.spec_id_to_name.get(v, v)
            for k, v in topo.label_catalog.items()
        }

    output_paths: List[str] = []
    topo_path = out_dir / f"topology_3d_{safe_name}_{elem}.json"
    meta = {
        "system_name": built.system_name,
        "element": elem,
        "ndim": 3,
        "axes": [ax.name for ax in output_axes],
        "grid_shape": [len(ax.values) for ax in output_axes],
        "bulk_field": {
            "axis_names": [ax.name for ax in output_axes],
            "axis_values": {
                ax.name: ax.values.tolist() for ax in output_axes
            },
            "axis_ranges": {
                ax.name: list(ax.range) for ax in output_axes
            },
            "labels": bulk_labels,
        },
    }
    export_topology_json(topo, str(topo_path), metadata=meta, debug=debug)
    output_paths.append(str(topo_path))
    verdict_paths, _ = _emit_predominance_verdict(
        topology=topo,
        topology_path=topo_path,
        axes=output_axes,
        labels=bulk_labels,
        label_catalog=(
            getattr(topo, "label_catalog", None)
            or getattr(grid, "label_catalog_per_element", {}).get(elem, {})
        ),
        built=built,
        metadata=meta,
    )
    output_paths.extend(verdict_paths)

    topo_png = out_dir / f"pourbaix_3d_topology_{safe_name}_{elem}.png"
    try:
        plot_3d_topology(topo_path, topo_png)
        output_paths.append(str(topo_png))
        if debug:
            print(f"[3D] Topology plot -> {topo_png.name}")
    except Exception as exc:
        if debug:
            print(f"[3D] Topology plot failed: {exc}")

    return output_paths


# ==================================================================
#  Generic ND output (topology JSON only, used for ndim == 1 or >= 4)
# ==================================================================

def emit_output_topology_only(
    grid, built, elem, topo,
    out_dir: Path, safe_name: str,
    axes,
    *,
    fine_label_map=None,
    debug: bool = False,
) -> List[str]:
    """Emit a topology JSON for arbitrary dimensionality.

    Fallback used for ndim == 1 and ndim >= 4, where dim-specific rich
    plotting is not implemented.
    """
    from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_export import (
        export_topology_json,
    )

    output_axes = list(axes)
    bulk_labels = grid.labels_per_element[elem]
    if fine_label_map is not None:
        topo, output_axes, bulk_labels, _ = (
            reconstruct_topology_from_fine_label_map(
                grid, fine_label_map, debug=debug,
            )
        )

    if hasattr(topo, "label_catalog") and topo.label_catalog:
        topo.label_catalog = {
            int(k): built.spec_id_to_name.get(v, v)
            for k, v in topo.label_catalog.items()
        }

    ndim = len(output_axes)
    topo_path = out_dir / f"topology_{ndim}d_{safe_name}_{elem}.json"
    meta = {
        "system_name": built.system_name,
        "element": elem,
        "ndim": ndim,
        "axes": [ax.name for ax in output_axes],
        "grid_shape": [len(ax.values) for ax in output_axes],
        "bulk_field": {
            "axis_names": [ax.name for ax in output_axes],
            "axis_values": {
                ax.name: ax.values.tolist() for ax in output_axes
            },
            "axis_ranges": {
                ax.name: list(ax.range) for ax in output_axes
            },
            "labels": bulk_labels,
        },
    }
    from sweep_pipelines._output_and_plotting._output_topology_compactor.topology_export import (
        export_topology_json,
    )
    export_topology_json(topo, str(topo_path), metadata=meta, debug=debug)
    output_paths = [str(topo_path)]
    verdict_paths, _ = _emit_predominance_verdict(
        topology=topo,
        topology_path=topo_path,
        axes=output_axes,
        labels=bulk_labels,
        label_catalog=(
            getattr(topo, "label_catalog", None)
            or getattr(grid, "label_catalog_per_element", {}).get(elem, {})
        ),
        built=built,
        metadata=meta,
    )
    output_paths.extend(verdict_paths)
    return output_paths


# ==================================================================
#  Full speciation CSV (physical points + phase-search diagnostics, no overlap)
# ==================================================================

def emit_full_speciation_csv(
    coarse_records: Dict[tuple, Any],
    refined_records: Dict[tuple, Any],
    refined_coarse_keys: set,
    built,
    axes,
    out_dir: Path,
    safe_name: str,
    *,
    debug: bool = False,
) -> Optional[str]:
    """Dump full speciation and retained phase-search diagnostics to one CSV.

    The CSV has two sections, each preceded by a ``# section: <name>``
    marker line, with **no overlap** between them:

    1. ``coarse_unrefined`` \u2014 coarse-grid points whose cell was *not*
       handed to the refiner (i.e. not a label-boundary cell for any
       principal element).  Rows normally contain converged speciation;
       explicitly flagged solid-phase ambiguity/timeout failures are also
       retained with ``converged=0`` for auditability.

    2. ``refined`` \u2014 every converged sub-grid point produced by
       refinement (across all layers), deduplicated by quantised
       coordinate so adjacent boundary cells' shared edges collapse to
       a single row.  This is the final unified refined grid.

    Coarse cells that *were* decomposed (``refined_coarse_keys``) are
    explicitly stripped from section 1, ensuring a decomposed coarse
    cell never appears alongside its own refined sub-cells.

    Both sections share one column schema: sweep axes, convergence
    diagnostics, full aqueous-species concentrations (mol/L), solid
    amounts (mol/L), raw saturation indices, reference-normalized formation
    affinities and driving energies, phase-search diagnostics, and
    per-element dominant-species labels.
    """
    import csv
    import json

    if not coarse_records and not refined_records:
        if debug:
            print("[full_spec] No physical or diagnostic points to write")
        return None

    # ── Strip coarse cells from section 1 if either:
    #   (a) the cell was explicitly handed to the refiner, OR
    #   (b) the cell's centre coord was re-solved at any point during
    #       refinement (e.g. because the 2-D fine label-map emitter
    #       re-solved that coordinate, or because an odd refine_factor
    #       sub-grid hit the centre exactly).
    # Either way the refined-section row supersedes the coarse one.
    refined_keyset = set(refined_records.keys())
    excluded_keys = refined_coarse_keys | refined_keyset
    coarse_kept = {
        k: v for k, v in coarse_records.items()
        if k not in excluded_keys
    }

    # ── Column inventory (union across both sections) ──
    all_pts = list(coarse_kept.values()) + list(refined_records.values())
    species_ids: List[str] = sorted({
        sid for pr in all_pts for sid in pr.conc.keys()
    })
    solid_ids: List[str] = sorted({
        sid for pr in all_pts for sid in pr.solid_amounts.keys()
    })
    si_ids: List[str] = sorted({
        sid for pr in all_pts for sid in pr.saturation_indices.keys()
    })
    thermo_ids: List[str] = sorted({
        sid
        for pr in all_pts
        for mapping in (
            getattr(pr, "saturation_reference_scales", {}),
            getattr(pr, "saturation_reference_frames", {}),
            getattr(pr, "normalized_formation_affinities", {}),
            getattr(
                pr,
                "formation_driving_energies_kJ_per_mol_reference",
                {},
            ),
        )
        for sid in mapping.keys()
    })
    elem_labels: List[str] = list(built.principal_elements)
    axis_names = [ax.name for ax in axes]
    spec_id_to_name = getattr(built, "spec_id_to_name", {}) or {}

    csv_path = out_dir / f"speciation_full_{safe_name}.csv"

    def _write_row(writer, key, pr):
        coord_d = dict(key)
        row: List[Any] = [
            f"{coord_d.get(a, ''):.9g}" if a in coord_d else ""
            for a in axis_names
        ]
        row += [int(bool(pr.converged)),
                int(getattr(pr, "iterations", 0)),
                f"{float(getattr(pr, 'residual', 0.0)):.6e}"]
        row += [f"{pr.conc.get(s, 0.0):.6e}" for s in species_ids]
        row += [f"{pr.solid_amounts.get(s, 0.0):.6e}" for s in solid_ids]
        row += [f"{pr.saturation_indices.get(s, 0.0):.6e}"
                if s in pr.saturation_indices else ""
                for s in si_ids]
        normalized = getattr(pr, "normalized_formation_affinities", {})
        driving_energy = getattr(
            pr, "formation_driving_energies_kJ_per_mol_reference", {}
        )
        row += [f"{normalized[s]:.6e}" if s in normalized else ""
                for s in thermo_ids]
        row += [f"{driving_energy[s]:.6e}" if s in driving_energy else ""
                for s in thermo_ids]
        row += [
            json.dumps(
                getattr(pr, "thermodynamic_tie_active_sets", []),
                separators=(",", ":"),
            ),
            json.dumps(
                getattr(pr, "thermodynamic_ambiguity_active_sets", []),
                separators=(",", ":"),
            ),
            int(bool(getattr(pr, "phase_search_timed_out", False))),
        ]
        label_per_elem = pr.label_per_element or {}
        row += [label_per_elem.get(e, "") for e in elem_labels]
        writer.writerow(row)

    with open(long_path(csv_path), "w", newline="", encoding="utf-8") as f:
        # ── Provenance header ──
        f.write("# speciation_full_v3\n")
        f.write(f"# system_name: {built.system_name}\n")
        f.write(f"# ndim: {len(axes)}\n")
        f.write(f"# axes: {','.join(axis_names)}\n")
        f.write(f"# n_coarse_unrefined: {len(coarse_kept)}\n")
        f.write(f"# n_refined: {len(refined_records)}\n")
        f.write(f"# n_coarse_excluded: "
                f"{len(excluded_keys & set(coarse_records.keys()))}\n")
        f.write(f"# n_aqueous_species: {len(species_ids)}\n")
        f.write(f"# n_solids: {len(solid_ids)}\n")
        f.write("# units: conc=mol/L, solid_amount=mol/L, "
                "SI=raw log10(IAP/Ksp) per written formula, "
                "SI_normalized=SI/reference_scale, "
                "dG_drive=-R*T*ln(10)*SI_normalized in "
                "kJ/mol primitive reference\n")
        reference_metadata = {}
        for sid in thermo_ids:
            scales = {
                float(pr.saturation_reference_scales[sid])
                for pr in all_pts
                if sid in getattr(pr, "saturation_reference_scales", {})
            }
            frames = {
                tuple(pr.saturation_reference_frames[sid])
                for pr in all_pts
                if sid in getattr(pr, "saturation_reference_frames", {})
            }
            if len(scales) > 1 or len(frames) > 1:
                raise ValueError(
                    f"inconsistent saturation reference metadata for {sid!r}"
                )
            reference_metadata[sid] = {
                "scale": next(iter(scales)) if scales else None,
                "frame": list(next(iter(frames))) if frames else None,
            }
        f.write(
            "# saturation_reference_json: "
            + json.dumps(reference_metadata, sort_keys=True,
                         separators=(",", ":"))
            + "\n"
        )
        f.write(
            "# saturation_reference_basis_json: "
            + json.dumps(
                list(getattr(built, "basis_tokens", [])),
                separators=(",", ":"),
            )
            + "\n"
        )
        f.write("# sections: coarse_unrefined, refined "
                "(no overlap; decomposed coarse cells excluded)\n")

        writer = csv.writer(f)

        # ── Header row (shared by both sections) ──
        header: List[str] = list(axis_names)
        header += ["converged", "iterations", "residual"]
        header += [f"conc[{spec_id_to_name.get(s, s)}]" for s in species_ids]
        header += [f"solid_amount[{s}]" for s in solid_ids]
        header += [f"SI[{s}]" for s in si_ids]
        header += [f"SI_normalized[{s}]" for s in thermo_ids]
        header += [
            f"dG_drive_kJ_per_mol_reference[{s}]" for s in thermo_ids
        ]
        header += [
            "thermodynamic_tie_active_sets",
            "thermodynamic_ambiguity_active_sets",
            "phase_search_timed_out",
        ]
        header += [f"label[{e}]" for e in elem_labels]
        writer.writerow(header)

        # ── Section 1: coarse_unrefined ──
        f.write(f"# section: coarse_unrefined  (rows={len(coarse_kept)})\n")
        for key in sorted(coarse_kept.keys()):
            _write_row(writer, key, coarse_kept[key])

        # ── Section 2: refined (final unified refined grid) ──
        f.write(f"# section: refined  (rows={len(refined_records)})\n")
        for key in sorted(refined_records.keys()):
            _write_row(writer, key, refined_records[key])

    if debug:
        n_excluded = len(excluded_keys & set(coarse_records.keys()))
        print(f"[full_spec] Saved {len(coarse_kept)} coarse + "
              f"{len(refined_records)} refined points "
              f"({n_excluded} coarse cells superseded by refinement) "
              f"-> {csv_path.name}")

    return str(csv_path)
