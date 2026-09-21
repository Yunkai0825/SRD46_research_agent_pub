# `NIST_SRD46_post_calc_tools/`

Post-calculation tools that consume solver outputs (speciation curves,
reports) to derive secondary quantities. These are **not** dispatchable
through `run_calculation` — they run after (or instead of) a sweep.

## `nernst_simple/` — Nernst E vs pH

Simple Nernst potential calculation for a redox couple, optionally
corrected with speciation fractions from a prior pH sweep.

| File | Purpose |
|------|---------|
| `nernst_simple_main.py` | `sweep_fn(...)` + registry metadata (`SWEEP_ID = "nernst_simple"`, `SWEEP_DESCRIPTION`, `SWEEP_PARAMS`). |
| `nernst_simple_export.py` | CSV/plot export for the resulting `NernstCurve`. |

```python
def sweep_fn(
    *, couple=None,
    metal: str = "", oxidised: str = "", reduced: str = "",
    speciation_curve=None,                  # optional prior pH-sweep curve
    total_metal: float = 1e-3,              # mol/L
    pH_range: Tuple[float, float] = (0.0, 14.0),
    n_points: int = 141,
    temperature: float = 25.0,              # °C
    activity_red: float = 1.0,
    mode: str = "auto",
    output_dir: Optional[str] = None,
    debug: bool = False,
) -> (NernstCurve, output_paths)
```

> Note: Nernst E° calculations were moved here from the core pipeline
> and are no longer dispatchable through `run_calculation` (see the
> core-pipeline README).

## `species_solver_simple/`

Reserved namespace — currently empty / not implemented.
