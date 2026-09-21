# `sweep_pipelines/_output_and_plotting/pourbaix_diagrams/`

Renderers and CSV I/O for 2-D and 3-D Pourbaix diagrams.

## Files

| File                      | Purpose                                                                              |
|---------------------------|--------------------------------------------------------------------------------------|
| `csv_exporter.py`         | `export_pourbaix_csv` (write label-map) / `load_pourbaix_csv` (read back).           |
| `plotter.py`              | `plot_pourbaix(grid, built, output_path, **kwargs)` — 2-D PNG renderer (label-map overlay, optional topology curves, optional water lines). |
| `plotter_3d_topology.py`  | `plot_3d_topology(grid, topology, output_path, …)` — 3-D topology PNG renderer (regions as voxels, junctions as scatter, boundaries as wireframe). |

## I/O contract

- **Input:** labelled `NDGrid` + `BuiltSystem` (for species labels) +
  the principal-element name; optionally a topology JSON path for
  overlaying simplified feature curves.
- **Output:** PNG written to `output_path`. CSVs are written and
  read in CSV format `i, j[, k], label` with a header line.

All file paths are wrapped with `sweep_pipelines._path_utils.long_path`
before reaching `open()` / `savefig()` — required for the Windows long
UNC paths produced by long chemical-system names.
