# `solvers_and_topology/numerical_solvers/`

Single-point equilibrium solver. Builds the
`point_solve_fn(coords, x0, *, warm_start=None) -> PointResult` callable consumed by
`NDGridSolver`.

## Neighbour state and recovery

The shared 1D/2D grid passes a copy of a converged neighbour's log-basis
concentrations, active solid IDs, precipitated amounts, and released totals
for pinned constraints. The target still supplies its own pH, potential,
analytical totals, constraints, and activity calculations. Failed, timed-out,
nonfinite, or incompatible-model donors are not accepted as full seeds.

`SolidManager` re-solves the donor assemblage at the target conditions before
the aqueous-root/alternative-assemblage search. Solids can appear or disappear.
The existing residual, saturation, positive-amount, tie, ambiguity and timeout
checks still decide acceptance. The aqueous root remains mandatory; a valid
warm solve does not override a failed root or an incomplete phase search.

The default aqueous-root/alternative-phase search allowance is 10 seconds.
Complete donor preparation has its own bounded allowance of the same size;
its elapsed time is excluded from the subsequent search deadline, including
when the donor attempt fails or times out. Both pinned and unpinned solves
use this policy. Interpolation retains its separate wall-clock allowance of
three point budgets (30 seconds by default). Newton iteration limits and
phase-acceptance criteria are independent of these time allowances.

Full states propagate through coarse BFS, axis sweeps, backscan, interpolation,
refinement, bisection and numerical hole recovery. Compatible blends carry
amounts and released totals; incompatible phase-set blends and elimination or
extrapolation guesses remain vector-only. Legacy two-argument callbacks still
receive a copied vector. Refinement caches keep their public ndarray entries
and retain full point states separately.

The grid checkpoint identity includes `full-phase-state/v2-separate-donor-budget`. Checkpoints from
another policy are rejected rather than silently treated as completed work
under this policy.

Unconverged speciation samples are exported as `nan` and plotted as gaps with grey interval shading.
They cannot imply solid dissolution, a phase edge, or a dominant-species
interval. Label/topology hole filling is separate from numerical convergence.

Pinned constraints use the augmented residual/Jacobian and carry released
component totals in the point's `_released_totals` mapping. The target's
`pin_plan` determines which totals apply; a donor never changes that plan.

## Files

| File                       | Purpose                                                                                  |
|----------------------------|------------------------------------------------------------------------------------------|
| `point_solver.py`          | `PourbaixPointSolver` — aqueous, expanded-solid and pin-aware Newton solves. |
| `eq_numerical_methods.py`  | Mass-balance residual + analytic Jacobian + Newton-with-trust-region.                    |
| `solid_manager.py`         | `SolidManager` — active-set switching for solid phases (SI ≥ 0 → activate, SI < 0 → deactivate). Also drives the auto-I outer loop. |

## Solver pipeline

1. Resolve target conditions and validate the optional complete neighbour seed.
2. Re-solve its active solids using its amounts and log-basis concentrations.
3. Solve the aqueous root and search alternative phase assemblages.
4. Apply complementarity, tie, ambiguity and timeout checks.
5. In auto-I mode, repeat at updated activity coefficients, forwarding each
   successful inner state to the next iteration.

## Public API

`build_solver_chain` in `sweep_pipelines/_sweep_input_entry_point/sweep_dispatcher.py`
constructs the native callable. `NDGridSolver` obtains complete copies using
`seed_from_point` and invokes it through `solve_seeded` in `nd_grid/warm_start.py`.
Direct callers may continue supplying `x0` alone.

## I/O contract

- **Input:** ordered model arrays and species, target coordinates and totals,
  optional log-basis vector or complete `warm_start`.
- **Output:** `PointResult` containing `x`, convergence and residual diagnostics,
  `active_solid_ids`, `solid_amounts`, concentrations, saturation indices,
  and model compatibility key. Optional released totals accompany pinned solves.
