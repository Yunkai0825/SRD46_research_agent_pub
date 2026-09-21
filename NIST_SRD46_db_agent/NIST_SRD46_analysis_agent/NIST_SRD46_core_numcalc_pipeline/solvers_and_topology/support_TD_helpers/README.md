# `solvers_and_topology/support_TD_helpers/`

The **only** gateway through which code inside `solvers_and_topology/`
reaches the thermodynamic helpers in `thermodynamics_helpers/`.

## Files

| File                              | Re-exports                                                                                  |
|-----------------------------------|---------------------------------------------------------------------------------------------|
| `activity_model_entry_point.py`   | Everything from `electrolyte_activity_models.activity_model`, plus explicit `compute_ionic_strength`, `recompute_activity_at_I`. |
| `TD_constants_entry_point.py`     | `R_CONST`, `F_CONST`, `NERNST_FACTOR`, `Kw_LOG`, `LN10`, `TEMPERATURE_C/K`.                 |

## Architecture rule

> No code inside `solvers_and_topology/` may import directly from
> `thermodynamics_helpers/`. Constants and activity-model functions
> must come through this module.

This keeps the solver layer pluggable against alternative
activity-coefficient backends and shields it from
`thermodynamics_helpers/` internals.
