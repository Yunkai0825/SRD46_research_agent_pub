# `_output_topology_compactor/`

Dimension-agnostic topology compaction and serialisation. Turns the raw
`TopologyND` produced by `solvers_and_topology/_output_topology_mapper`
into a compact, plot/export-ready form, and assembles the dense fine
label raster used by the 2-D Pourbaix renderers.

## Files & public surface

| File | Main public functions | Purpose |
|------|------------------------|---------|
| `compact_nd.py` | `compact_topology_nd(source, settings=…, rdp_epsilon=…, envelope_n=…, csv_dir=…, csv_prefix=…)` | Compact a `TopologyND` (or a CSV dir) into a `CompactTopologyND` via bottom-up, dimension-by-dimension feature simplification. |
| | `compact_from_csv(csv_dir, csv_prefix, …)` | Convenience wrapper for CSV-sourced topology. |
| `fine_label_map_assembler.py` | `assemble_fine_label_map_from_grid(grid, refine_factor, …)`, `build_and_patch_fine_label_map(...)` | Build a dense fine label raster from the coarse grid + refined sub-cell layers (compose + patch + vote). |
| `simplifier_nd.py` | `simplify_curve(curve, rdp_epsilon, …)`, `subsample_curve(curve, n_points)`, `simplify_surface(surface, …)`, `simplify_manifold_k(manifold, k, …)` | k-D manifold simplification (1-D boundaries, 2-D surfaces, generic k-D). |
| `simplifier_rdp.py` | `rdp_simplify(points, epsilon)` | Classical Ramer–Douglas–Peucker polyline simplification. |
| `topology_csv_io.py` | `export_features_csv(topo, output_dir, csv_prefix, axis_names)`, `load_features_csv(csv_dir, csv_prefix)`, `classify_features_by_dim(topo, axis_names)` | Round-trip topology features to/from per-dimension CSV files. |
| `topology_export.py` | `export_topology_json(topo, output_path, metadata=…, debug=…)` | Serialise `TopologyND` / `CompactTopologyND` to JSON (ND format, plus legacy 2-D/3-D keys). |

## I/O contract

- **Input:** `TopologyND` from the topology mapper (or its CSV dump),
  optionally an `NDGrid` for the fine-raster assembler.
- **Output:** `CompactTopologyND`, `topology_*.json`,
  `topo_csv_*/features_*.csv`, dense label rasters for renderers.

## Architecture rules

- Pure output-side helper: no solver calls, no LLM, no global state.
- Consumed by the sweep export layers (`pH_sweep`, `pourbaix_sweep`,
  `freeform_sweep`); never import sweep packages from here.
