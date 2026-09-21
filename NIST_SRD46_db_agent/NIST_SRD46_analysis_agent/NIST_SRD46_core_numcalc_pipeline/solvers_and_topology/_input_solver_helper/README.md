# `solvers_and_topology/_input_solver_helper/`

Bridge between `FreeEnergyReport` (thermodynamic network) and the
numpy-array container (`BuiltSystem`) consumed by the Newton-Raphson
point solver.

## Files

| File                              | Purpose                                                                            |
|-----------------------------------|------------------------------------------------------------------------------------|
| `built_system_from_dGreport.py`   | `build_from_free_energy_report(report, …)` — main entry point; `BuiltSystem` dataclass. |

## What `BuiltSystem` carries

- `log_beta_eff`, `stoich_pq`, `stoich_r`, `stoich_s`,
  `nu_matrix` — solver-ready arrays in the element basis.
- `C_total` — total metal + ligand concentrations.
- Dissolution arrays — per-solid `log_K_diss_eff`, stoichiometry,
  mass-balance footprints (via `DissolutionProxy`).
- Derived redox tokens — empty when no `RedoxCouple` exists in the
  report.
- Water stability lines (for Pourbaix plot overlays).
- Bookkeeping: basis labels, metal / ligand names, species labels.

## Key insight

The same `BuiltSystem` layout backs pH-only and Pourbaix sweeps. A
redox-enabled pH-only sweep uses an explicitly fixed `E_V`. When redox is
excluded, every declared oxidation state is retained as an independent
zero-reference component, all electron stoichiometries are zero, and no
potential coordinate is present. This is not an `E_V = 0` calculation.

## I/O contract

- **Input:** `FreeEnergyReport` from `thermodynamics_helpers/`.
- **Output:** `BuiltSystem` (immutable numpy-array container).

This module is the **only** writer of `BuiltSystem`. Solver,
labeller, and plot code only ever read from it.
