# `sweep_pipelines/pH_sweep/`

1-D pH speciation sweep — fraction and log-concentration curves vs
pH for every species in a `FreeEnergyReport`.

## Files

| File                      | Purpose                                                                 |
|---------------------------|-------------------------------------------------------------------------|
| `pH_sweep_main.py`        | `run_pH_sweep(...)` — build axes, drive `NDGridSolver(ndim=1)`.         |
| `pH_sweep_export.py`      | CSV / envelope / verdict export; registry-facing `sweep_fn`.            |
| `pH_sweep_plot.py`        | Fraction, log-concentration, multi-component plots.                     |
| `pH_sweep_settings.py`    | Defaults (`DEFAULT_N_POINTS`, …).                                       |

## Pipeline

```
FreeEnergyReport
  → build_from_free_energy_report     (BuiltSystem)
  → SolidManager.solve_point          (Newton-Raphson + active-set + auto-I)
  → NDGridSolver(ndim=1).solve        (BFS continuation along pH)
  → label_grid_nd                     (per-element predominance)
  → extract_topology_nd               (0-D transitions on pH axis)
  → compact_topology_nd               (RDP-simplified features)
  → build_speciation_curve_from_grid_1d  (SpeciationCurve)
  → generate_all_output               (CSVs + envelopes + plots + verdict)
```

The same solver chain backs the Pourbaix sweep.  A redox-enabled pH-only
sweep requires an explicitly declared fixed `E_V`.  When redox is excluded,
`E_V` is absent: every oxidation state is an independent component with its
own zero reference and no inter-valence alignment.  This is not an `E_V = 0`
calculation.

## Public API

```python
def run_pH_sweep(
    source,                               # path / dict / FreeEnergyReport
    total_metals:  Optional[List[float]] = None,   # back-compat; canonical totals live on the report
    total_ligands: Optional[List[float]] = None,
    *,
    pH_range:        Optional[Tuple[float,float]] = None,
    n_points:        Optional[int] = None,
    output_dir:      Optional[str]   = None,
    temperature_K:   Optional[float] = None,
    ionic_strength:  Optional[float] = None,
    include_solids:  Optional[bool] = None,
    use_activity:    Optional[bool] = None,
    debug:           bool = False,
    prefix:          Optional[str]  = None,
    compiled_constraints: Optional[Any] = None,
    fixed_E_V:       Optional[float] = None,
) -> Dict[str, Any]
```

The axis bounds/count, solid inclusion, and activity model must already be
declared by the calculation card or supplied explicitly. `include_solids`
selects whether dissolution/solid equilibria are assembled, while
`use_activity=True` selects Davies corrections and `False` selects the ideal
model. A redox-enabled pH-only call must also supply `fixed_E_V`.

Returns `{report, built, grid, topologies, speciation_curve, output_paths, …}`.

## Output artefacts (`generate_all_output`)

All files share a `<prefix>` derived from the system name (override with
`prefix=`).

| File                                  | Purpose                                                         |
|---------------------------------------|------------------------------------------------------------------|
| `<prefix>_frac_metal.csv`              | Fraction-of-metal vs pH — merged across **all** metal components. |
| `<prefix>_frac_ligand.csv`             | Fraction-of-ligand vs pH — merged across **all** ligand components. |
| `<prefix>_log_conc.csv`                | log10[species] vs pH.                                            |
| `<prefix>_concentrations.csv`          | Molar concentrations vs pH.                                      |
| `<prefix>_state_metrics.csv`           | Calculated ionic strength + convergence per pH point.            |
| `<prefix>_envelope_<component>.csv`    | Sampled fraction envelope per metal/ligand component.            |
| `<prefix>_concentration_envelope.csv`  | Douglas–Peucker simplified concentration envelope.               |
| `<prefix>_frac_<component>.png`        | Per-component fraction diagram (multi-component systems).        |
| `<prefix>_frac_metal.png` / `_frac_ligand.png` | Fraction diagrams (single-component systems).            |
| `<prefix>_log_conc.png`                | log-c diagram.                                                   |
| `<prefix>_verdict.md`                  | Calculation-based verdict document.                              |
| `<prefix>_run_params.json`             | Run parameters snapshot.                                         |
| `<prefix>_input_speciation_card.json`  | Input card snapshot (when available).                            |
| `topology_<system>_<element>.json`     | Per-element 1-D topology (written by `pH_sweep_main`).           |

Multi-component note: the full-resolution `frac_metal.csv` /
`frac_ligand.csv` union the per-component maps
(`PointResult.frac_metals` / `frac_ligands`); the flat `frac_M` /
`frac_L` fields are first-component convenience copies only. Per-component
series are accessed via `SpeciationCurve.series_multi(sp_id, component_id)`.

Driven through the central registry — always invoke via
`sweep_method_registry_api`, never import this package directly.
