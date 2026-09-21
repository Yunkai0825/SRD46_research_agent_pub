# NIST SRD-46 Core Calc Tools — API & Settings Reference

Complete reference for every public input, keyword, default value, and
internal hyperparameter exposed by the calculator.

> **Known support boundary:** native `constraint_spec` and
> `constraint_settings` exist, but individual-species starting guesses do not.
> Exact species pins are partial/default-disabled, and
> `constraint_settings.species_pins = "allowed"` reaches the unfinished
> `_principal_component_map`. The public result schema also lacks released
> totals.

This document is exhaustive: it covers

1. The single public entry point `run_calculation` and its signature.
2. The two input objects it consumes (card source + calc-modes JSON).
3. The full `CalcInput` schema (every field, every nested dataclass).
4. Per-method sweep parameters, including how `CalcInput` axes are
   translated into low-level handler kwargs.
5. The dispatcher (`run_sweep`) signature and accepted aliases.
6. All module-level settings constants for every sweep method.
7. The result dict returned to the caller.

For an architectural overview (how the modules wire together) see
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Top-Level API

### `SRD46_numcalculator_api.run_calculation`

```python
def run_calculation(
    card_source: Union[str, pathlib.Path, dict, FreeEnergyReport],
    calc_input:  Union[str, pathlib.Path, dict, CalcInput],
    *,
    output_dir:  Optional[Union[str, pathlib.Path]] = None,
    debug:       bool = False,
) -> Dict[str, Any]
```

| Arg          | Type                                                                                             | Default | Meaning |
|--------------|--------------------------------------------------------------------------------------------------|---------|---------|
| `card_source`| `str` / `Path` / `dict` / `FreeEnergyReport`                                                     | —       | Free-energy card (see §2). Resolved by `input_entry_points.card_input.resolve_card_source`. |
| `calc_input` | `str` / `Path` / `dict` / `CalcInput`                                                            | —       | Calc-modes JSON or in-memory dict (see §3). Path/str/dict are parsed by `load_calc_input`. |
| `output_dir` | `str` / `Path` / `None`                                                                          | `None`  | Output root. Precedence: this arg > `calc_input.output_dir` > `None`. Created if missing. |
| `debug`      | `bool`                                                                                           | `False` | Verbose progress + per-step timestamped log file in `output_dir`. |

The function performs only **input adaptation**: it normalises both
inputs, applies environment / concentration overrides to the report,
then forwards to `sweep_pipelines._sweep_input_entry_point.run_sweep`.

The other public exports are:

| Symbol                     | Purpose |
|----------------------------|---------|
| `load_calc_input(source)`  | Parse a calc-modes JSON file or dict into a `CalcInput` dataclass. |
| `resolve_card_source(...)` | Turn any card-source form into a `FreeEnergyReport`. |
| `CalcInput`                | The calc-modes dataclass (schema in §3). |
| `SUPPORTED_SWEEP_METHODS`  | Tuple of canonical sweep-method strings (§3.1). |

---

## 2. Card Source

`resolve_card_source(source, *, temperature_K=None) → FreeEnergyReport`

Accepted forms (in priority order):

| Form                                              | Behaviour |
|---------------------------------------------------|-----------|
| `FreeEnergyReport`                                | Returned unchanged. |
| `dict`                                            | Treated as an equilibrium-network spec; passed to `compute_free_energy_network(spec, temperature_K=...)`. |
| `str` / `Path` ending in `.md`                    | Parsed with `parse_free_energy_card_md`. |
| `str` / `Path` directory                          | Searched for the first matching file in `_CARD_FILE_PRIORITY` (see below) and parsed as `.md`. |
| `str` / `Path` with any other extension (e.g. `.json`) | Treated as an equilibrium-network spec path; passed to `compute_free_energy_network(path, temperature_K=...)`. |

Card lookup priority inside a directory:

```python
_CARD_FILE_PRIORITY = (
    "free_energy_card_enriched.md",
    "free_energy_card.md",
    "free_energy_card_with_include.md",
)
```

If none match, the first `*.md` file in the directory is used. If
nothing is found, `FileNotFoundError` is raised.

The `temperature_K` argument is forwarded only to
`compute_free_energy_network` (the JSON / dict / spec path); MD card
parsing reads temperature from the card itself.

---

## 3. Calc-Modes Input (`CalcInput`)

The full JSON schema, defined in
[`numcalc_input_cards_reader/calc_json_input_reader.py`](numcalc_input_cards_reader/calc_json_input_reader.py).
All keys are optional unless marked **required**.

```jsonc
{
  "sweep_method": "pH_sweep" | "pourbaix_sweep"
                | "titration_sweep",                     // REQUIRED

  "sweep_axes": [
    {"name": "pH",  "min": 0.0,  "max": 14.0, "n_points": 71},
    {"name": "E_V", "min": -1.0, "max":  1.5, "n_points": 30},
    {"name": "a_w", "min": 0.7,  "max":  1.0, "n_points":  3}  // optional — upgrades pourbaix_sweep to 3-D
  ],

  "ionic_strength": {"mode": "fixed", "value": 0.1},

  "temperature_C": 25.0,
  // — or — "temperature_K": 298.15

  "concentrations": {
    "total_metals":  {"M1": 1.0e-3, "Cu+2": 1.0e-3},
    "total_ligands": {"L1": 1.0e-2}
  },

  "grid_refine":  {"mode": "boundary", "factor": 2, "n_layers": 1},

  "use_activity":   true,
  "include_solids": true,

  "output_dir": null,
  "_notes": "free text — preserved in extras"
}
```

Unknown top-level keys (other than those starting with `_`) are kept
under `CalcInput.extras` for downstream consumers.

### 3.1 `sweep_method` (required)

```python
SUPPORTED_SWEEP_METHODS = (
    "pH_sweep",
    "pourbaix_sweep",
    "titration_sweep",
)
```

Recognised axes per method (advisory, extras allowed). ``pourbaix_sweep``
is the unified N-D handler: include only ``pH`` and ``E_V`` for the
standard 2-D Pourbaix; add ``a_w`` to upgrade to a 3-D sweep.

```python
_RECOGNISED_AXES = {
    "pH_sweep":        ("pH",),
    "pourbaix_sweep":  ("pH", "E_V", "a_w"),
    "titration_sweep": ("V_added_mL",),
}
```

### 3.2 `sweep_axes` — `List[SweepAxis]`

```python
@dataclass
class SweepAxis:
    name:     str       # one of: "pH" | "E_V" | "a_w" | "V_added_mL"
    min:      float
    max:      float     # must be > min
    n_points: int = 71  # must be ≥ 2
```

JSON shorthand also accepted:

```jsonc
{"name": "pH", "range": [0.0, 14.0], "n": 71}   // range = [min,max], n = n_points
```

If a method-required axis is missing, `axis_or_default(name)` falls
back to `DEFAULT_AXES_BY_METHOD`:

| Method            | Default axes                                                                                  |
|-------------------|-----------------------------------------------------------------------------------------------|
| `pH_sweep`        | `pH ∈ [0, 14], n=71`                                                                          |
| `pourbaix_sweep`  | `pH ∈ [0, 14], n=30` · `E_V ∈ [-1.0, 1.5], n=30` (declare an `a_w` axis to upgrade to 3-D)   |
| `titration_sweep` | `V_added_mL ∈ [0, 50], n=100`                                                                 |

### 3.3 `ionic_strength` — `IonicStrengthSpec`

```python
@dataclass
class IonicStrengthSpec:
    mode:  str   = "fixed"   # "fixed" | "auto" | "none"
    value: float = 0.1       # mol/L (used for "fixed")
```

| `mode`   | Behaviour |
|----------|-----------|
| `"fixed"`| Use `value` (mol/L) throughout the sweep. |
| `"auto"` | Iterate ionic strength self-consistently against the speciation (Davies activity loop, max `MAX_OUTER_IONIC=12` iterations, tolerance `IONIC_TOL=1e-6`). |
| `"none"` | Disable activity corrections (`γ ≡ 1`); sets report `I=0` and `ionic_mode="fixed"`. Also forces `use_activity=False` in the sweep params even if user requested `true`. |

### 3.4 `temperature_C` / `temperature_K`

| Field           | Type             | Default | Notes |
|-----------------|------------------|---------|-------|
| `temperature_C` | `float` / `null` | `None`  | If non-null, override report temperature. |
| `temperature_K` | `float` / `null` | `None`  | Read only when `temperature_C` is absent; converted to °C internally. |

### 3.5 `concentrations`

```jsonc
"concentrations": {
  "total_metals":  {"<id_or_name>": <mol/L>, ...},
  "total_ligands": {"<id_or_name>": <mol/L>, ...}
}
```

Keys are matched first against canonical `metal_ids`/`ligand_ids`,
then against `metal_names`/`ligand_names` (with whitespace stripped).
Unmatched keys are stored verbatim — useful for declaring totals for
species not yet in the report.

### 3.6 `grid_refine` — `GridRefineSpec`

```python
@dataclass
class GridRefineSpec:
    mode:     str             # "none" | "boundary"
    factor:   Optional[int]   # omitted for none; >= 2 for boundary
    n_layers: int             # internal 0 for none; >= 1 for boundary
```

The block is required for every calculation card.  Disabled refinement is
declared as `{"mode":"none"}` with no unused numeric values.  Two- and
three-dimensional boundary refinement is declared as
`{"mode":"boundary","factor":R,"n_layers":L}`, where `R ≥ 2` and
`L ≥ 1`.  Missing, partial, or contradictory declarations are rejected.

### 3.7 `use_activity` / `include_solids`

| Field            | Type   | Default | Effect |
|------------------|--------|---------|--------|
| `use_activity`   | `bool` | `true`  | Toggle Davies activity corrections. Forced `False` when `ionic_strength.mode == "none"`. |
| `include_solids` | `bool` | `true`  | Include dissolution reactions in the active-set solver. Used by `pH_sweep`; the Pourbaix solver always considers solids. |

### 3.8 `output_dir`

Optional string path. Overridden by the `output_dir=` kwarg on
`run_calculation` if both are given.

### 3.9 Validation

`CalcInput.validate()` returns a list of human-readable issues. Fatal
issues raise `ValueError` from `load_calc_input`; advisory issues
(non-standard axis names) are printed but allowed.

Checks performed:

- `sweep_method` ∈ `SUPPORTED_SWEEP_METHODS`
- No duplicate axis names
- Each axis has `n_points ≥ 2` and `max > min`

> Nernst E° calculations (with their own `nernst_couple` spec) have
> been migrated out of this package to
> [`NIST_SRD46_post_calc_tools/nernst_simple/`](../NIST_SRD46_post_calc_tools/nernst_simple/).

---

## 4. Per-Method Sweep Parameters

`_build_sweep_params(calc)` translates `CalcInput` into the kwargs
forwarded to each handler. Common model kwargs are:

```python
{
  "use_activity":   bool,   # calc.use_activity AND not none-mode
  "include_solids": bool,   # calc.include_solids
}
```

`refine_factor` and `n_layers` are forwarded only to the Pourbaix and
freeform handlers.  Disabled mode becomes `refine_factor=None,
n_layers=0`; boundary mode forwards the two declared integers.

### 4.1 `pH_sweep` → `pH_sweep.run_pH_sweep`

| Handler kwarg | Source                    | Default          |
|---------------|---------------------------|------------------|
| `pH_range`    | `axis("pH").as_range()`   | `(0.0, 14.0)`    |
| `n_points`    | `axis("pH").n_points`     | `71`             |
| Plus the two common model kwargs above.                              |

`run_pH_sweep` signature:

```python
def run_pH_sweep(
    source,
    total_metals:  Optional[List[float]] = None,   # back-compat; canonical totals live on the report
    total_ligands: Optional[List[float]] = None,
    *,
    pH_range:        Tuple[float, float] = (0.0, 14.0),
    n_points:        int  = DEFAULT_N_POINTS,      # 141
    output_dir:      Optional[str]   = None,
    temperature_K:   Optional[float] = None,
    ionic_strength:  Optional[float] = None,
    include_solids:  bool = True,   # API parity; SolidManager always considers solids
    use_activity:    bool = True,   # API parity; auto-I gated by report.ionic_mode
    debug:           bool = False,
    prefix:          Optional[str]  = None,
    compiled_constraints: Optional[Any] = None,
)
```

### 4.2 `pourbaix_sweep` (unified N-D handler)

`pourbaix_sweep` is the **single** Pourbaix entry point; it dispatches
to `_run_pourbaix`, which forwards to `pourbaix_sweep.run_pourbaix_sweep`.
The dimensionality of the resulting sweep equals the number of axes
forwarded — declare an `a_w` axis to upgrade a 2-D pH x E sweep to 3-D.

| Handler kwarg | Source                                           | Default                |
|---------------|--------------------------------------------------|------------------------|
| `pH_range`    | `axis("pH").as_range()`                          | `(0.0, 14.0)` (always present) |
| `E_range`     | `axis("E_V").as_range()`                         | `(-1.0, 1.5)` (always present) |
| `aw_range`    | `axis("a_w").as_range()`                         | omitted unless an `a_w` axis is declared (→ 2-D); declare it to upgrade to 3-D |
| `n_pH`        | `axis("pH").n_points`                            | `30`                   |
| `n_E`         | `axis("E_V").n_points`                           | `30`                   |
| `n_aw`        | `axis("a_w").n_points`                           | inherited from declared axis (typical: `3`); omitted for 2-D |
| `refine_factor` | explicit boundary factor, or `None` in mode `none` | no default             |
| `n_layers`      | explicit boundary layers, or `0` in mode `none`    | no default             |
| Plus the two common model kwargs above.                                                                                  |

`run_pourbaix_sweep` signature (the unified N-D entry):

```python
def run_pourbaix_sweep(
    source, *,
    # ND-aware (preferred):
    axes:          Optional[List[GridAxis]] = None,
    # Legacy scalar kwargs (used when axes is None):
    pH_range:      Optional[Tuple[float,float]] = PH_RANGE,      # (0.0, 14.0)
    E_range:       Optional[Tuple[float,float]] = E_RANGE_V,     # (-1.0, 1.5)
    aw_range:      Optional[Tuple[float,float]] = None,
    n_pH:          Optional[int] = COARSE_N_PH,                  # 500
    n_E:           Optional[int] = COARSE_N_E,                   # 500
    n_aw:          Optional[int] = None,
    # Common pipeline parameters:
    output_dir:    Optional[str]   = None,
    temperature_K: Optional[float] = None,
    ionic_strength:Optional[float] = None,
    refine_factor: Optional[int], # None disabled; otherwise >= 2
    n_layers:      int,           # 0 disabled; otherwise >= 1
    debug:         bool = DEBUG,                                 # True
    compiled_constraints: Optional[Any] = None,
)
```

Setting any of `pH_range`/`E_range`/`aw_range` (and the matching `n_*`)
to `None` omits that axis. Pass `axes=[GridAxis(...), ...]` for
explicit ND control.

### 4.3 `titration_sweep` → `titration_sweep.run_titration_sweep`

Implemented as a 1-D added-volume sweep with a dilution model, solved
through the **freeform** pipeline (no bespoke solver code). The handler
receives the single `V_added_mL` axis plus:

| Handler kwarg       | Default | Meaning                                  |
|---------------------|---------|-------------------------------------------|
| `volume_initial_mL` | `50.0`  | Initial solution volume V0 (mL).          |
| `titrant_conc`      | `0.1`   | Titrant stock concentration (mol/L).      |
| `fixed_pH`          | `7.0`   | pH at which speciation is evaluated.      |

Per-cell totals are emitted as formula bindings against the volume axis
(`f(V) = V0/(V0+V)`; analyte totals dilute, the titrant total grows) and
compiled with the standard constraint compiler. Note: speciation is
evaluated at a **fixed pH** — a true free-pH titration curve requires a
charge-balance solver mode that is not yet available.

---

## 5. Dispatcher (`run_sweep`)

Lower-level entry point used by `run_calculation`:

```python
def run_sweep(
    source: Union[str, pathlib.Path, dict, FreeEnergyReport],
    sweep_type: str = "pourbaix",
    *,
    output_dir:     Optional[str]   = None,
    temperature_K:  Optional[float] = None,
    ionic_strength: Optional[float] = None,
    debug:          bool = False,
    **sweep_params,
) -> Dict[str, Any]
```

### 5.1 Accepted `sweep_type` aliases

| Alias                                              | Handler                |
|----------------------------------------------------|------------------------|
| `pH` · `ph` · `pH_sweep`                           | `_run_pH`              |
| `pourbaix` · `pourbaix_sweep`                      | `_run_pourbaix` (single N-D handler) |
| `freeform` · `freeform_sweep`                      | `_run_freeform`        |
| `titration` · `titration_sweep`                    | `_run_titration_sweep` |

Unknown `sweep_type` raises `ValueError` with the list of accepted aliases.

---

## 6. Module-Level Settings (Hyperparameters)

These are compile-time defaults inside each sweep package. `CalcInput`
fields override only the subset listed in §4; the remainder (timeouts,
retry counts, output cosmetics) are tuned at the source level.

### 6.1 `sweep_pipelines/pourbaix_sweep/pourbaix_sweep_settings.py`

```python
# Grid
PH_RANGE        = (0.0, 14.0)     # default pH domain
E_RANGE_V       = (-1.0, 1.5)     # default E domain (V vs SHE)
AW_RANGE        = (0.7, 1.0)      # default a_w domain (3-D only)
COARSE_N_PH     = 500             # default n_pH if not overridden
COARSE_N_E      = 500             # default n_E
COARSE_N_AW     = 3               # default n_aw (3-D)
# Solver
POINT_TIMEOUT_S = 5.0             # max seconds per Newton solve

# Output
OUTPUT_DPI      = 200             # PNG resolution
OUTPUT_FORMAT   = "png"
RDP_ENVELOPE_N  = 6               # boundary-polyline envelope sampling

# Debug
DEBUG           = True            # default verbose mode
```

| Constant         | Overridable via `CalcInput`?                  |
|------------------|-----------------------------------------------|
| `PH_RANGE`       | yes — `sweep_axes[name="pH"].min/max`         |
| `E_RANGE_V`      | yes — `sweep_axes[name="E_V"].min/max`        |
| `AW_RANGE`       | yes — `sweep_axes[name="a_w"].min/max`        |
| `COARSE_N_PH`    | yes — `sweep_axes[name="pH"].n_points`        |
| `COARSE_N_E`     | yes — `sweep_axes[name="E_V"].n_points`       |
| `COARSE_N_AW`    | yes — `sweep_axes[name="a_w"].n_points`       |
| `POINT_TIMEOUT_S`| **no** (edit settings file)                   |
| `OUTPUT_DPI`     | **no** (edit settings file)                   |
| `OUTPUT_FORMAT`  | **no** (edit settings file)                   |
| `RDP_ENVELOPE_N` | **no** (edit settings file)                   |
| `DEBUG`          | yes — `debug=True` on `run_calculation`       |

### 6.2 `sweep_pipelines/pH_sweep/pH_sweep_settings.py`

```python
DEFAULT_PH_MIN   = 0.0
DEFAULT_PH_MAX   = 14.0
DEFAULT_N_POINTS = 141

MAX_RETRY_SWEEPS = 3       # retries for non-converged segments

# Auto ionic-strength loop (when ionic_strength.mode == "auto")
MAX_OUTER_IONIC  = 12
IONIC_TOL        = 1.0e-6
```

| Constant            | Overridable via `CalcInput`?                                     |
|---------------------|------------------------------------------------------------------|
| `DEFAULT_PH_MIN`    | yes — axis `pH`                                                  |
| `DEFAULT_PH_MAX`    | yes — axis `pH`                                                  |
| `DEFAULT_N_POINTS`  | yes — axis `pH`                                                  |
| `MAX_RETRY_SWEEPS`  | **no** (settings constant; not consumed by the unified pipeline) |
| `MAX_OUTER_IONIC`   | **no** (engaged when `ionic_strength.mode == "auto"`)            |
| `IONIC_TOL`         | **no** (paired with `MAX_OUTER_IONIC`)                           |

### 6.3 `sweep_pipelines/titration_sweep/`

No settings module — registry metadata only (`SWEEP_PARAMS` defaults:
`volume_initial_mL=50.0`, `titrant_conc=0.1`, `fixed_pH=7.0`).

---

## 7. Result Dict

`run_calculation` always returns a `dict` with at least:

```python
{
  "report":        FreeEnergyReport,    # always present
  "sweep_method":  str,                 # echoes calc.sweep_method
  "calc_input":    CalcInput,           # the parsed CalcInput object
  "output_dir":    str | None,          # resolved output directory
  "output_paths":  list[str],           # all files written
}
```

Method-specific extras:

| Method                              | Extra keys |
|-------------------------------------|------------|
| `pH_sweep`                          | `results: List[GibbsPointResult]`, optionally `speciation_curve` if `speciation_curve` was in `extras` |
| `pourbaix_sweep`                    | `built: BuiltPourbaixSystem`, `grid: NDGrid`, `all_boundaries: Dict[elem → BoundaryCells]` (1-D ~ N-D — dimensionality follows the declared axes) |
| `titration_sweep`                   | (raises `NotImplementedError`) |

---

## 8. Output File Naming

For Pourbaix sweeps, written under `output_dir`:

| Pattern                                      | When               |
|----------------------------------------------|--------------------|
| `pourbaix_map_<safe_name>_<elem>.csv`        | 2-D, coarse and refined label maps |
| `pourbaix_<safe_name>_<elem>.png`            | 2-D diagram PNG    |
| `topology_<safe_name>_<elem>.json`           | 2-D compacted topology |
| `topology_3d_<safe_name>_<elem>.json`        | 3-D compacted topology |
| `pourbaix_3d_topology_<safe_name>_<elem>.png`| 3-D topology PNG   |
| `topology_<ndim>d_<safe_name>_<elem>.json`   | 1-D and ndim ≥ 4 fallback |
| `topo_csv_<safe_name>_<elem>/`               | Raw topology features CSVs |
| `speciation_<safe_name>_<elem>__<bdry>.csv`  | Speciation along boundaries (2-D) |
| `speciation_plot_<safe_name>_<elem>.png`     | Speciation plot (2-D) |
| `_snapshots/snap_01_coarse_<elem>.png`       | Pre-refinement snapshot (2-D, debug only) |
| `_snapshots/snap_02_topology_<elem>.png`     | Post-extraction snapshot (2-D, debug only) |
| `sweep_log.txt`                              | Per-step timestamped log (debug only) |
| `<original_card_filename>`                   | Verbatim copy of the input card for provenance |

`<safe_name>` is `built.system_name` with spaces and hyphens replaced
by underscores, truncated to 30 characters for 3-D outputs.

---

## 9. Cross-Reference

| Source file                                                                                                  | What it defines |
|--------------------------------------------------------------------------------------------------------------|-----------------|
| [`SRD46_numcalculator_api.py`](SRD46_numcalculator_api.py)                                                   | `run_calculation`, `_build_sweep_params`, `_apply_*_overrides` |
| [`numcalc_input_cards_reader/calc_json_input_reader.py`](numcalc_input_cards_reader/calc_json_input_reader.py)                                       | `CalcInput`, `SweepAxis`, `IonicStrengthSpec`, `GridRefineSpec`, `load_calc_input`, `SUPPORTED_SWEEP_METHODS`, `_RECOGNISED_AXES`, `DEFAULT_AXES_BY_METHOD` |
| [`numcalc_input_cards_reader/card_md_input_reader.py`](numcalc_input_cards_reader/card_md_input_reader.py)                                       | `resolve_card_source`, `_CARD_FILE_PRIORITY` |
| [`sweep_pipelines/_sweep_input_entry_point/sweep_dispatcher.py`](sweep_pipelines/_sweep_input_entry_point/sweep_dispatcher.py) | `run_sweep`, `parse_source`, `build_solver_chain`, all `_run_*` handlers |
| [`sweep_pipelines/pourbaix_sweep/pourbaix_sweep_main.py`](sweep_pipelines/pourbaix_sweep/pourbaix_sweep_main.py) | Unified N-D `run_pourbaix_sweep` |
| [`sweep_pipelines/pourbaix_sweep/pourbaix_sweep_settings.py`](sweep_pipelines/pourbaix_sweep/pourbaix_sweep_settings.py) | Pourbaix defaults |
| [`sweep_pipelines/pH_sweep/pH_sweep_main.py`](sweep_pipelines/pH_sweep/pH_sweep_main.py)                     | `run_pH_sweep` |
| [`sweep_pipelines/pH_sweep/pH_sweep_settings.py`](sweep_pipelines/pH_sweep/pH_sweep_settings.py)             | pH sweep defaults |
