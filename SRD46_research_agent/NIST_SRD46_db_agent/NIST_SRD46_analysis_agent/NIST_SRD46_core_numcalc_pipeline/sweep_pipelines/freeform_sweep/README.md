# `sweep_pipelines/freeform_sweep/`

Catch-all **N-D sweep** for any axis configuration that does not fit
the canonical `pH_sweep` (strict 1-D pH) or `pourbaix_sweep`
(2-D pH × E_V, optionally 3-D with `a_w`) shapes.

## Typical use cases

- 1-D scan along a non-physical-axis equation
  (e.g. a Nernst line `E_V = -0.059 * pH`: declare `pH` as axis with
  `E_V_freeform` + `custom_freeform` mapping).
- Sweeps over user-declared scalars in `freeform_vars_define`.
- Sweeps with composite `[X]_constr` plus stoichiometric
  `custom_freeform` chains.
- Sweeps with total-concentration axes
  (`[<metal>]_tot_axis`, `[<ligand>]_tot_axis`).

## Files

| File                          | Purpose                                                              |
|-------------------------------|----------------------------------------------------------------------|
| `freeform_sweep_main.py`      | `run_freeform_sweep(...)` — coerce axes, drive `NDGridSolver`.       |
| `freeform_sweep_export.py`    | Wide-CSV writer + topology JSON emitter; registry `sweep_fn`.        |
| `freeform_sweep_settings.py`  | Non-refinement sweep constants.                                    |
| `_paths.py`                   | Re-exports `long_path` / `safe_mkdir` for windows-safe writes.       |

## Pipeline

```
FreeEnergyReport + axes (arbitrary)
  → build_solver_chain                (shared with all sweeps)
  → NDGridSolver.solve                (dim-agnostic)
  → extract_topology_nd → compact_topology_nd
  → export_topology_json + wide CSV per principal element
```

The solver / grid / labeller / topology stages are *identical* to
those used by the Pourbaix sweep — only the axes are arbitrary and
the output is axis-agnostic.

Boundary refinement is always explicit.  Pass `n_layers=0` and
`refine_factor=None` for an unrefined sweep, or pass `n_layers>=1` and
`refine_factor>=2` for a 2-D/3-D refined sweep.  There is no independent
`coarse_only` control and no refinement default.

## Output artefacts

| File                                          | Purpose                                  |
|-----------------------------------------------|------------------------------------------|
| `freeform_<system>_<element>.csv`             | Wide CSV: one row per grid point, columns = axes + per-species fractions / log-c. |
| `freeform_topology_<system>_<element>.json`   | `features_0d`, `features_1d`, `regions`. |

Always invoked through `sweep_method_registry_api`; never import this
package directly.
