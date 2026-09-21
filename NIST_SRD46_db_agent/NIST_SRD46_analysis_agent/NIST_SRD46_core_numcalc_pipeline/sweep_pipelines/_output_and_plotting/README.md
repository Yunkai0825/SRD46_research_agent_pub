# `sweep_pipelines/_output_and_plotting/`

Shared output and plotting helpers for every sweep method. The solver
layer (`solvers_and_topology/`) is presentation-agnostic — every CSV,
PNG, snapshot, and topology JSON is produced here or from a sweep
package directly.

## Folder map

```
_output_and_plotting/
├── _sweep_output_and_plotting_registry.py   ← registry hook (sweep_id → output tools)
│
├── _output_topology_compactor/              § dense raster + RDP-compacted topology
│   ├── fine_label_map_assembler.py            compose dense raster from SolveResult
│   ├── compact_nd.py                          N-D region compaction (faces → edges → nodes)
│   ├── simplifier_nd.py / simplifier_rdp.py   curve simplification
│   ├── topology_csv_io.py                     features-CSV read/write
│   ├── topology_export.py                     topology JSON emitter
│   └── README.md                              (this subpackage has its own README)
│
├── pourbaix_diagrams/                       § Pourbaix renderers + CSV I/O
│   ├── csv_exporter.py                        16×16 / 64×64 label-map CSV
│   ├── plotter.py                             2-D PNG renderer (label-map overlay)
│   └── plotter_3d_topology.py                 3-D topology PNG renderer
│
├── speciation_curves/                       § pH-sweep curves
│   ├── curve_builder.py                       grid → SpeciationCurve
│   ├── csv_exporter.py                        full / envelope CSVs
│   ├── plotter.py                             fraction + log-c plots
│   └── speciation_output_compressor.py        DP-envelope sampling
│
└── freeform_output/                         § freeform-sweep output (placeholder)
```

## I/O contract

- **Input:** `SolveResult` (per-element `ElementResult` with coarse
  grid, refined boundary points, topology) — plus the originating
  `FreeEnergyReport` for species labels.
- **Output:** CSV / PNG / JSON files written to `output_dir`.

All file writes go through `sweep_pipelines._path_utils.long_path`
and `safe_mkdir` to remain safe on Windows long UNC paths.

## Architecture rules

- No solver imports from this folder; sweep handlers call these
  helpers explicitly.
- `_output_topology_compactor/` is the **only** place that builds the
  dense fine label raster — the solver layer never produces a raster.
- All registry-routed output tools live behind
  `_sweep_output_and_plotting_registry.py` so each sweep method
  exposes a uniform set of callables.
