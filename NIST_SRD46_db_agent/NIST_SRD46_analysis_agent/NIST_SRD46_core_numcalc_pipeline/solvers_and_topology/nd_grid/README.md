# `solvers_and_topology/nd_grid/`

N-dimensional grid pipeline. `NDGridSolver` is THE single container
that owns coarse-grid solve, labelling, boundary detection,
multi-layer refinement, and topology extraction. `NDGridSolver.solve()`
is the ONE public method.

## Folder map

```
nd_grid/
├── grid_solver.py                    ← NDGridSolver + SolveResult + ElementResult
├── effective_label_map.py            ← refinement tree → final resolved raster
├── effective_topology.py             ← final raster → facets/junctions/boundaries/regions
├── data_types.py                     ← GridAxis, NDGrid, PointResult,
│                                       BoundaryCellND, RefinedBoundaryPointND, TopologyND
├── settings.py                       ← POINT_TIMEOUT_S, REFINE_FACTOR, REFINE_LAYERS, BISECTION_TOL
│
├── grid_solver_sweep_retry_patching/ § coarse-grid solve phases 1-5
│   ├── solver_sweep_and_seed.py        seed + BFS flood-fill + axis sweeps
│   ├── solver_retry_helpers.py         back-scan retry + interpolation retry
│   └── solver_hole_patcher.py          sub-grid hole patcher (used by refiner)
│
└── grid_dynamic_refiner/             § labelling + boundary detection + refinement
    ├── labeler.py                      assign phase labels to coarse cells
    ├── boundary_detector.py            find canonical transition facets per element
    └── boundary_refiner.py             shared, vertex-incident cascaded refinement
```

## `NDGridSolver.solve()` pipeline

1. **Coarse grid solve** (`_solve_coarse_grid_nd`) — 5 phases:
   1. Seed at grid centre (or caller-supplied indices).
   2. BFS flood-fill from converged seeds.
   3. Axis sweeps to fill dead zones.
   4. Back-scan retry (multi-pass).
   5. Interpolation retry (averaged/blended neighbour guesses).
2. **Label** the coarse grid per principal element (`labeler.py`).
3. Detect one canonical transition facet per unequal adjacent pair for each
   requested element (`boundary_detector.py`).
4. *(Optional)* Refine the deduplicated union of **all cells touching any
   vertex** of all element facets once (`boundary_refiner.py`), labelling
   every solved sub-cell for every principal element. Unconverged sub-cells
   are re-seeded via `solver_hole_patcher`; callbacks are emitted per layer
   and element.
5. Preserve an explicitly named coarse diagnostic topology, assemble one
   final effective label field per element, and reconstruct all canonical
   facets, junctions, boundaries, and regions solely from that field.

## Public API

```python
solver = NDGridSolver(point_solve_fn, n_basis, built_system=built)
result = solver.solve(
    axes=[GridAxis("pH", pH_vals), GridAxis("E_V", E_vals)],
    label_elements=["Cu", "Fe"],
    refine=True,
    refine_factor=2,
    n_layers=2,
    per_layer_callback=snapshot_cb,   # optional
)
# result.grid                   → labelled NDGrid (coarse)
# result.per_element[name]      → ElementResult(topology=final,
#                                      coarse_topology=diagnostic,
#                                      effective_label_map=final field)
```

## I/O contract

- **Input:** a callable `point_solve_fn(coords, x0) -> PointResult`
  (from `numerical_solvers/point_solver.py`), plus the `BuiltSystem`
  for labeller context.
- **Output:** `SolveResult` — no CSVs or plots. A refined per-element result
  contains the final effective label raster and topology derived from it;
  output layers reuse that same field without rebuilding it.

## Architecture rules

- One public class, one public method. Everything else (modules in
  `grid_solver_sweep_retry_patching/`, `grid_dynamic_refiner/`,
  `data_types.py` internals) is package-private.
- No upward imports — `nd_grid/` never imports from
  `sweep_pipelines/`. Behaviour is configured exclusively through
  `solve()` keyword flags.
