# `sweep_pipelines/titration_sweep/`

1-D **titration sweep** — incremental addition of a titrant to a
fixed-volume solution, tracking speciation vs the added volume
`V_added_mL`, with dilution of all pre-loaded totals. Solved through
the **same** unified solver / N-D grid / export pipeline as the
freeform sweep; the only titration-specific logic is the construction
of the per-cell totals.

## Files

| File                      | Purpose                                                        |
|---------------------------|----------------------------------------------------------------|
| `titration_sweep_main.py` | `run_titration_sweep(...)` — dilution model → freeform sweep.  |

## Dilution model

```
f(V)             = V0 / (V0 + V)          # dilution factor
[analyte]_tot(V) = [analyte]_0 * f(V)     # every pre-loaded total dilutes
[titrant]_tot(V) = C_titrant * V / (V0 + V)
```

These relations are emitted as *formula bindings* against the
`V_added_mL` axis and compiled with the standard constraint compiler,
so the freeform solver drives them per cell — no bespoke solver code.

## Public API

```python
def run_titration_sweep(
    report,                                   # resolved FreeEnergyReport
    *,
    axes:              Optional[Sequence[Any]] = None,  # single {name,min,max,n_points} added-volume axis
    output_dir:        Optional[str]   = None,
    ionic_strength:    Optional[float] = None,
    temperature_K:     Optional[float] = None,
    volume_initial_mL: float = 50.0,          # V0
    titrant_conc:      float = 0.1,           # titrant stock (mol/L)
    fixed_pH:          float = 7.0,           # pH at which speciation is evaluated
    debug:             bool  = False,
    prefix:            Optional[str] = None,
    compiled_constraints: Optional[Any] = None,  # read for analyte totals + catalog
) -> Dict[str, Any]
```

Returns the freeform-sweep result bundle
(`{report, built, grid, per_element, topologies, output_paths}`).

## Status / limitations

- ✅ Solver: implemented (delegates to `freeform_sweep` with formula
  bindings).
- ✅ Export / plotting: inherited from the freeform output layer.
- ⚠️ Speciation is evaluated at a **fixed pH** (default 7). A true
  free-pH titration (pH solved from proton/charge balance as titrant is
  added) requires a charge-balance solver mode that is not yet
  available.
- The titrant identity is taken from the declared axis name (the LC3
  card names the axis after the titrant component id, e.g.
  `ligand_10076` for hydroxide). If it does not resolve to a catalog
  component, the sweep still runs as a pure dilution scan.

Driven through the central registry — always invoke via
`sweep_method_registry_api`, never import this package directly.
