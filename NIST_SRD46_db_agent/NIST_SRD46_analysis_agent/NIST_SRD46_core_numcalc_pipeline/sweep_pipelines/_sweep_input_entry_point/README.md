# `sweep_pipelines/_sweep_input_entry_point/`

Shared input-normalisation and dispatch layer for every sweep
method. This is where the `SRD46_numcalculator_api.run_calculation`
top-level call lands before it is routed to a specific handler.

> `constraint_compiler.py` contains partial `SpeciesPin` scaffolding, but this
> entry layer does not resolve pin indices or forward a `pin_plan` through the
> production sweep handlers.

## Files

| File                              | Purpose                                                                                          |
|-----------------------------------|--------------------------------------------------------------------------------------------------|
| `sweep_dispatcher.py`             | `run_sweep(source, sweep_type, **kwargs)` — single dispatch entry; aliases & handler table.      |
| `constraint_compiler.py`          | Build / validate / compile the system catalog and `sweep_constraints` into a `CompiledConstraints` object consumed by the handlers. |
| `sweep_constraints_expander.py`   | Expand short-form / dict-shape constraints into the canonical full form.                         |
| `initial_condition_normalizer.py` | Normalise `initial_condition` entries (e.g. `[1.0, "mM"] → 1e-3 mol/L`).                         |

## Dispatch table

```
sweep_type aliases                       → handler
─────────────────────────────────────────────────────────────────
pH | ph | pH_sweep                       → pH_sweep.run_pH_sweep
pourbaix | pourbaix_sweep                → pourbaix_sweep.run_pourbaix_sweep (N-D)
titration | titration_sweep              → titration_sweep.run_titration_sweep (stub)
freeform | freeform_sweep                → freeform_sweep.run_freeform_sweep
```

Unknown `sweep_type` raises `ValueError` listing accepted aliases.

## Public API

```python
def run_sweep(
    source,                  # FreeEnergyReport / path / dict
    sweep_type:    str = "pourbaix",
    *,
    output_dir:    Optional[str]   = None,
    temperature_K: Optional[float] = None,
    ionic_strength:Optional[float] = None,
    debug:         bool = False,
    compiled_constraints = None,
    **sweep_params,
) -> Dict[str, Any]
```

Helpers also exported:

| Function                                       | Purpose                                              |
|------------------------------------------------|------------------------------------------------------|
| `parse_source(src, temperature_K)`             | Accepts `FreeEnergyReport`, path, dict; returns report. |
| `build_solver_chain(report, …)`                | Common solver-chain construction (BuiltSystem + PointSolver). |
| `build_default_catalog(report)`                | Default system catalog from a report.                |
| `merge_catalog_overrides(default, user)`       | Merge user catalog on top.                           |
| `validate_catalog_against_report(cat, report)` | Cross-check IDs / names against the report.          |
| `compile_constraints(cat, axes, constraints)`  | Compile dict-shape constraints into solver kwargs.   |

## Architecture rules

- Sweep handlers must not duplicate constraint logic — call
  `compile_constraints` once at the top-level and forward the compiled
  object down.
- This module never owns output formatting; everything renders inside
  the per-method packages or `_output_and_plotting/`.
