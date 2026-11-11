# `nd_grid/grid_solver_sweep_retry_patching/`

Coarse-grid solve phases for `NDGridSolver`. Each phase is a
short-circuit retry strategy that attempts to converge any
grid cells left unsolved by the previous phase.

## Files

| File                       | Purpose                                                                                  |
|----------------------------|------------------------------------------------------------------------------------------|
| `solver_sweep_and_seed.py` | Phases 1–3: `default_seed` (grid centre), `bfs_fill` (BFS from converged seeds), `axis_sweeps` (per-axis dead-zone fill). |
| `solver_retry_helpers.py`  | Phases 4–5: `backscan_retry` (multi-pass backwards scan), `interpolation_retry` (averaged/blended neighbour guesses). |
| `solver_hole_patcher.py`   | Sub-grid hole patcher used by `boundary_refiner` to re-seed unconverged refined sub-cells. |

## Phase order (inside `NDGridSolver._solve_coarse_grid_nd`)

```
1. default_seed       → solve grid centre (or caller-supplied indices)
2. bfs_fill           → BFS flood-fill from every converged cell
3. axis_sweeps        → per-axis sweeps to fill dead zones
4. backscan_retry     → multi-pass reverse-direction retry
5. interpolation_retry→ interpolated initial guesses from neighbours
```

## I/O contract

- **Input:** mutable `NDGrid` (`PointResult` field per cell), the
  active `point_solve_fn`, retry budget.
- **Output:** in-place population of `grid.points[idx]` with
  `PointResult.converged = True` wherever possible. Returns a
  `dict` of phase-level statistics consumed by `NDGridSolver`
  for debug logging.
