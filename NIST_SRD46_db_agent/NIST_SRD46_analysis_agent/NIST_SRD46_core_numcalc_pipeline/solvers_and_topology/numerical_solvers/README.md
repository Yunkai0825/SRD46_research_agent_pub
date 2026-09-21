# `solvers_and_topology/numerical_solvers/`

Single-point equilibrium solver. Builds the
`point_solve_fn(coords, x0) -> PointResult` callable consumed by
`NDGridSolver`.

The low-level package includes `augmented_residual_jacobian`,
`solve_augmented`, and pin-aware `SolidManager` branches. Their standalone toy
test passes, but the production API/dispatcher does not currently resolve or
supply a valid `pin_plan`, and released totals are not part of the public
result.

## Files

| File                       | Purpose                                                                                  |
|----------------------------|------------------------------------------------------------------------------------------|
| `point_solver.py`          | `solve_one_point(built, coords, x0, …)` and `make_point_solve_fn(built, …)` — top-level entry. |
| `eq_numerical_methods.py`  | Mass-balance residual + analytic Jacobian + Newton-with-trust-region.                    |
| `solid_manager.py`         | `SolidManager` — active-set switching for solid phases (SI ≥ 0 → activate, SI < 0 → deactivate). Also drives the auto-I outer loop. |

## Solver pipeline

```
coords = {pH, E_V, [a_w, T_K, …]}            (axis values)
x0     = log[free basis ions]              (warm-start vector)
   │
   ▼
SolidManager.solve_point(coords, x0)
   ├─ Newton on f(x) = sum stoich_i · 10^{log_beta_eff,i + …} − C_total
   ├─ check SI of every dissolution equilibrium
   ├─ flip active set if SI sign disagrees with current state
   └─ if report.ionic_mode == "auto": iterate I (Davies, max 12 iter)
   ▼
PointResult(x, residuals, converged, active_solids, …)
```

## Public API

```python
from solvers_and_topology.numerical_solvers.point_solver import (
    make_point_solve_fn, solve_one_point,
)

solve_fn = make_point_solve_fn(
    built_system,
    use_activity=True,
    include_solids=True,
    timeout_s=5.0,
)
result = solve_fn({"pH": 7.0, "E_V": 0.2}, x0=None)
```

## I/O contract

- **Input:** `BuiltSystem` (numpy arrays), axis-coordinate dict,
  optional warm-start vector.
- **Output:** `PointResult` — `x` (log basis), `converged`,
  `active_solids` (frozenset of ids), per-species log-concentrations,
  ionic strength, residual norm, wall time, error message.
