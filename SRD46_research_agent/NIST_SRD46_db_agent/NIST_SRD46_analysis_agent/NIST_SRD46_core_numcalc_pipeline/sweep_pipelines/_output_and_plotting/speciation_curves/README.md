# `sweep_pipelines/_output_and_plotting/speciation_curves/`

CSV exporters and plotters for pH-sweep speciation curves
(fraction and log-concentration vs pH).

## Files

| File                                 | Purpose                                                                  |
|--------------------------------------|--------------------------------------------------------------------------|
| `curve_builder.py`                   | `build_speciation_curve_from_grid_1d(grid)` — `NDGrid` → `SpeciationCurve` dataclass. |
| `csv_exporter.py`                    | Full-resolution CSV + envelope CSV writers, envelope reader.             |
| `plotter.py`                         | `plot_fraction`, `plot_log_conc`, `plot_multi_fraction` — matplotlib renderers. |
| `speciation_output_compressor.py`    | Douglas–Peucker sampling for compact envelopes.                          |

## I/O contract

- **Input:** 1-D labelled `NDGrid` (pH axis) + originating
  `FreeEnergyReport` for species labels and component totals.
- **Output (CSV, via `export_speciation_csv` — `<prefix>_` optional):**
  - `frac_metal.csv` — fraction-of-metal vs pH, merged across **all**
    metal components.
  - `frac_ligand.csv` — fraction-of-ligand vs pH, merged across **all**
    ligand components.
  - `log_conc.csv` — log10[species] vs pH.
  - `concentrations.csv` — molar concentrations vs pH.
  - `state_metrics.csv` — calculated ionic strength, convergence and
    charge balance per pH point.
- **Output (PNG, via `plotter.py`):** per-component fraction diagrams
  (`series_multi`), single-component fraction diagrams, log-c diagram.

## Multi-component & ionic-strength data model

`curve_builder._convert_point` produces one
`PointResult` (from `thermodynamics_helpers/speciation_dataclasses.py`)
per pH grid point:

- `frac_metals` / `frac_ligands` — **full** per-component fraction maps
  `{component_id: {species_id: fraction}}`; this is the authoritative
  source for multi-metal / multi-ligand systems.
- `frac_M` / `frac_L` — flat first-component convenience copies only.
  CSV exporters union the per-component maps instead of reading these.
- `ionic_strength_used` / `calculated_ionic_strength` — per-point ionic
  strength: `I = ½ Σ c_i z_i²` over aqueous species; `used` equals the
  calculated value in `ionic_mode="auto"`, else the fixed target.

`SpeciationCurve` carries `total_metals` / `total_ligands` /
`metal_names` / `ligand_names` and exposes:

- `series(sp_id, kind)` — flat first-component series (legacy).
- `series_multi(sp_id, component_id)` — per-component fraction series;
  use this for all multi-component plots/exports.
- `is_multi` — `True` when more than one metal/ligand component exists.

All file paths are wrapped with `sweep_pipelines._path_utils.long_path`
and `safe_mkdir` before reaching `open()` / `savefig()`.
