# `sweep_pipelines/`

Driver layer above `solvers_and_topology/`. Every sweep method
(pH, Pourbaix N-D, titration, freeform) is a self-contained package
that:

1. Normalises user input (axes, constraints, initial conditions,
   ionic-strength mode, totals).
2. Builds a `point_solve_fn` and `BuiltSystem` via
   `_sweep_input_entry_point.build_solver_chain`.
3. Calls `NDGridSolver.solve(...)` with the right flags.
4. Assembles presentation artefacts (CSVs, plots, snapshots,
   topology JSON) from the returned `SolveResult`.

This layer **owns all output formatting**. `solvers_and_topology/`
returns raw numerical objects; everything user-facing is built here.

## Public surface

External code must go through the **sweep registry**, not
import sweep sub-packages directly:

| Function                                     | From                            | Purpose                                              |
|----------------------------------------------|---------------------------------|------------------------------------------------------|
| `get_sweep_method(name)`                     | `sweep_method_registry_api`     | Get the sweep callable.                              |
| `get_output_generator(name)`                 | `sweep_method_registry_api`     | Get the `generate_all_output` master orchestrator.   |
| `get_sweep_output_tools(name)`               | `sweep_method_registry_api`     | Get the dict of all export / plot callables.         |
| `list_sweep_methods()`                       | `sweep_method_registry_api`     | List `{id: description}` of registered sweeps.       |
| `DEFAULT_SWEEP_METHOD`                       | `sweep_method_registry_api`     | Default sweep id (`"pH_sweep"`).                     |
| `run_sweep(source, sweep_type, **kwargs)`    | `_sweep_input_entry_point`      | Lower-level single-call dispatcher.                  |

The registry enforces a uniform contract across sweep methods — see
the module docstring of
[sweep_method_registry_api.py](sweep_method_registry_api.py) for the
full per-sweep export list.

## Registered sweep methods

| Sweep id           | Handler module                          | Dim | Status        |
|--------------------|-----------------------------------------|-----|---------------|
| `pH_sweep`         | [pH_sweep/](pH_sweep/)                  | 1   | ✅ Full       |
| `pourbaix_sweep`   | [pourbaix_sweep/](pourbaix_sweep/)      | 1–N (1, 2, 3 wired) | ✅ Full |
| `freeform_sweep`   | [freeform_sweep/](freeform_sweep/)      | N   | ✅ Full       |
| `titration_sweep`  | [titration_sweep/](titration_sweep/)    | 1   | ✅ Full (fixed-pH dilution model via freeform) |

## Folder map

```
sweep_pipelines/
├── README.md                              ← this file
├── sweep_method_registry_api.py           ← THE public façade
├── _path_utils.py                         ← long_path() / safe_mkdir() (Windows long-path helpers)
│
├── _sweep_input_entry_point/              § input normalisation + dispatcher (shared)
│   ├── sweep_dispatcher.py                  routes a request to a sweep handler
│   ├── constraint_compiler.py               build/validate catalog · compile constraints
│   ├── sweep_constraints_expander.py        expand short-form / dict-shape constraints
│   └── initial_condition_normalizer.py      [V, unit] → canonical mol/L, etc.
│
├── pH_sweep/                              § 1-D pH speciation (full)
│   ├── pH_sweep_main.py
│   ├── pH_sweep_export.py
│   ├── pH_sweep_plot.py
│   └── pH_sweep_settings.py
│
├── pourbaix_sweep/                        § unified N-D Pourbaix sweep
│   ├── pourbaix_sweep_main.py               build axes; per-layer snapshot cb
│   ├── pourbaix_sweep_export.py             dim-aware emit_* orchestrators
│   └── pourbaix_sweep_settings.py
│
├── titration_sweep/                       § added-volume titration (dilution → freeform)
│   └── titration_sweep_main.py
│
├── freeform_sweep/                        § N-D catch-all sweep (arbitrary axes)
│   ├── freeform_sweep_main.py
│   ├── freeform_sweep_export.py
│   ├── freeform_sweep_settings.py
│   └── _paths.py                            re-exports long_path / safe_mkdir
│
└── _output_and_plotting/                  § shared output / plot helpers
    ├── _sweep_output_and_plotting_registry.py
    ├── _output_topology_compactor/          dense fine raster + RDP-compacted topology JSON
    │   ├── fine_label_map_assembler.py
    │   ├── compact_nd.py
    │   ├── simplifier_nd.py / simplifier_rdp.py
    │   ├── topology_csv_io.py
    │   └── topology_export.py
    ├── pourbaix_diagrams/                   csv_exporter · plotter (2-D) · plotter_3d_topology
    ├── speciation_curves/                   curve_builder · csv_exporter · plotter
    └── freeform_output/                     (reserved)
```

## Per-sweep flow

Every sweep handler follows the same three-step skeleton:

```python
# 1. build inputs
built  = build_built_system(report, ...)
axes   = [GridAxis("pH", pH_vals), GridAxis("E_V", E_vals)]
solve  = make_point_solve_fn(built, ...)

# 2. solve
nd     = NDGridSolver(solve, built.n_basis, built_system=built)
result = nd.solve(
    axes,
    label_elements=[...],
    refine=True,
    per_layer_callback=snapshot_cb,   # optional
)

# 3. assemble outputs from `result`
generate_all_output(result, output_dir, ...)
```

The dense fine label raster (Pourbaix CSV / PNG / per-layer snapshots)
is built **downstream** by
[fine_label_map_assembler.py](_output_and_plotting/_output_topology_compactor/fine_label_map_assembler.py).
The solver itself does not produce rasters.

## Windows long-path discipline

All file writes inside this package go through
[_path_utils.py](_path_utils.py):

| Helper            | When to use                                                                                                  |
|-------------------|--------------------------------------------------------------------------------------------------------------|
| `long_path(p)`    | Wrap every path passed to `open()`, `savefig()`, `shutil.copy2`.                                             |
| `safe_mkdir(p)`   | Always replace `Path.mkdir(parents=True, exist_ok=True)` with this — `pathlib` does NOT respect the `\\?\` prefix on Windows. |

Chemical-system names like `Cu + Fe + Glycine + Citric acid` produce
≥260-char output paths on UNC shares and crash unwrapped `open()` /
`mkdir()` calls. The wrap is a no-op on non-Windows hosts.

## Architecture rules

- **Registry-only public access.** External callers go through
  `sweep_method_registry_api`; never import a sweep sub-package
  directly.
- **No reverse imports.** Sweep packages may freely import from
  `solvers_and_topology/`; the reverse is forbidden.
- **Output stays here.** Every CSV / PNG / verdict / topology JSON is
  produced by a sweep package or by `_output_and_plotting/` — never
  by the solver layer.
- **Long-path safe.** Every `open()` and `Path.mkdir()` is wrapped.
