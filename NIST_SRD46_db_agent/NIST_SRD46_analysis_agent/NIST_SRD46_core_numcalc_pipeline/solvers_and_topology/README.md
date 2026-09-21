# `solvers_and_topology/`

Numerical core of the pipeline. Owns everything from a single
point-solve up to a fully labelled N-D grid with extracted phase
topology. Sweep drivers in `sweep_pipelines/` build their inputs
and call into this layer; this layer never imports from
`sweep_pipelines/`.

## Public surface

The **only** entry points external code should use are:

| Symbol                                              | From                                                                                  | Purpose                                                              |
|-----------------------------------------------------|---------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| `NDGridSolver`                                      | `nd_grid` (re-exported at package root)                                               | Single container for the entire grid pipeline.                       |
| `NDGridSolver.solve()`                              | —                                                                                     | The **one** public method. Coarse grid + label + boundary + multi-layer refine + topology. |
| `SolveResult`, `ElementResult`                      | `nd_grid`                                                                             | Result bundles returned by `solve()`.                                |
| `GridAxis`, `NDGrid`, `PointResult`                 | `nd_grid`                                                                             | Data types passed in/out of `solve()`.                               |
| `BoundaryCellND`, `RefinedBoundaryPointND`, `TopologyND` | `nd_grid`                                                                       | Per-element artefacts inside `SolveResult`.                          |
| `solve_one_point(...)`, `make_point_solve_fn(...)`  | [numerical_solvers/point_solver.py](numerical_solvers/point_solver.py)                | Build a `point_solve_fn` callable for `NDGridSolver`.                |
| `build_from_free_energy_report(...)`                | [_input_solver_helper/](_input_solver_helper/)                                        | Build the `BuiltSystem` argument from a `FreeEnergyReport`.          |
| `extract_topology(...)`                             | [_output_topology_mapper/topology_dispatcher.py](_output_topology_mapper/topology_dispatcher.py) | Dimension-agnostic topology extraction (1-D / 2-D / 3-D).         |

Everything else is package-private.

## Folder map

```
solvers_and_topology/
├── solver_core_api.py            ← shared dataclasses (SolverSpecies, SolverEquilibrium, …)
├── solver_settings.py            ← global numerical tolerances / log clamps
├── __init__.py                   ← re-exports NDGridSolver + result types
│
├── numerical_solvers/            § single-point equilibrium solver
│   ├── point_solver.py             builds the point_solve_fn callable
│   ├── eq_numerical_methods.py     residual / Jacobian + Newton-with-trust-region
│   └── solid_manager.py            active-set switching + auto-I outer loop
│
├── support_TD_helpers/           § thermodynamic-helper entry points (the ONLY bridge)
│   ├── activity_model_entry_point.py    activity-model re-exports
│   └── TD_constants_entry_point.py      physical / thermodynamic constants
│
├── _input_solver_helper/         § turn a FreeEnergyReport into a BuiltSystem
│   └── built_system_from_dGreport.py
│
├── nd_grid/                      § the N-D grid pipeline
│   ├── grid_solver.py              NDGridSolver + solve() orchestrator
│   ├── data_types.py               GridAxis · NDGrid · PointResult · …
│   ├── settings.py                 grid-phase tolerances & retry limits
│   ├── grid_solver_sweep_retry_patching/
│   │   ├── solver_sweep_and_seed.py    phases 1-3 (seed · BFS · axis sweeps)
│   │   ├── solver_retry_helpers.py     phases 4-5 (back-scan · interpolation)
│   │   └── solver_hole_patcher.py      sub-grid hole patcher (used by refiner)
│   └── grid_dynamic_refiner/
│       ├── labeler.py                  per-element predominance labels
│       ├── boundary_detector.py        boundary cells per element
│       └── boundary_refiner.py         multi-layer cascaded refinement
│
└── _output_topology_mapper/      § turn refined boundaries into topology
    ├── topology_dispatcher.py      1-D / 2-D / 3-D dispatcher
    └── topology_nd/                regions · junctions · boundary chains
        ├── topology_nd.py
        ├── boundary_builder.py     contains the 2-D diagonal-artifact fix
        ├── junction_finder.py
        ├── region_builder.py
        └── geometry_utils.py
```

## Pipeline overview

`NDGridSolver.solve()` runs these stages in order:

1. **Coarse grid solve** (`_solve_coarse_grid_nd`) — 5 phases:
   1. Seed at grid centre (or caller-supplied indices).
   2. BFS flood-fill from converged seeds  → `solver_sweep_and_seed.bfs_fill`
   3. Axis sweeps to fill dead zones       → `solver_sweep_and_seed.axis_sweeps`
   4. Back-scan retry (multi-pass)         → `solver_retry_helpers.backscan_retry`
   5. Interpolation retry (averaged/blended neighbour guesses) → `solver_retry_helpers.interpolation_retry`
2. **Label** the coarse grid per principal element
   (`grid_dynamic_refiner/labeler.py`).
3. **For each requested element:**
   1. Boundary cell detection (`grid_dynamic_refiner/boundary_detector.py`).
   2. *(Optional)* Multi-layer cascaded boundary refinement with
      optional per-layer callback
      (`grid_dynamic_refiner/boundary_refiner.py`). Unconverged
      sub-cells are re-seeded via `solver_hole_patcher`.
   3. Topology extraction via the dim-dispatcher
      (`_output_topology_mapper/topology_dispatcher.py`).

`solve()` returns
`SolveResult(grid, per_element={name: ElementResult(...)})`.
Presentation artefacts (dense fine label rasters, CSV / PNG exports)
are **not** built here — they are assembled by callers from
`SolveResult` using the helpers in
`sweep_pipelines/_output_and_plotting/_output_topology_compactor/`.

## I/O contract

- **Input:** a callable `point_solve_fn(coords, x0) -> PointResult`
  (from `numerical_solvers/`), the `BuiltSystem` (from
  `_input_solver_helper/`), and a list of `GridAxis`.
- **Output:** `SolveResult` — no rasters, no CSVs, no plots.

## 2-D diagonal-artifact fix

`_output_topology_mapper/topology_nd/boundary_builder.py` contains the
collinearity-residual gate
(`residual ≤ 0.25 AND max_span ≤ min(spacing)`) that suppresses
the SVD-based junction relocation on near-degenerate 2-D fits —
the root-cause fix for the diagonal-spike artefact that historically
appeared in 2-D Pourbaix diagrams.

## Architecture rules

- **One public class, one public method.** All other classes and
  functions in `nd_grid/` are leading-underscore or live under
  package-private sub-folders.
- **No upward imports.** This package never imports from
  `sweep_pipelines/`. Sweep drivers configure behaviour through
  `solve()` keyword flags only.
- **Solver is presentation-agnostic.** Anything callers need for
  CSV / PNG / snapshot output is returned through `SolveResult`.
- **Thermodynamics through the gateway.** All activity / constants
  imports go through
  [support_TD_helpers/](support_TD_helpers/) — never directly from
  `thermodynamics_helpers/`.
