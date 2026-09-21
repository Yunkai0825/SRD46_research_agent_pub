# `numcalc_input_cards_reader/`

Input adapters for the calc pipeline. Resolves the two distinct
input families that `SRD46_numcalculator_api.run_calculation`
consumes:

| Input family       | What it carries                                                              | Reader                            |
|--------------------|------------------------------------------------------------------------------|-----------------------------------|
| **Card source**    | Thermodynamic system (species, μ°, logβ, components, redox couples, totals) | `card_md_input_reader.py`         |
| **Calc-modes**     | What sweep to run (method, axes, ionic strength, constraints, …)            | `calc_json_input_reader.py`       |

These two inputs never overlap and are validated independently.

## Public surface (re-exported from `__init__.py`)

| Symbol                       | From                              | Purpose                                                                 |
|------------------------------|-----------------------------------|-------------------------------------------------------------------------|
| `resolve_card_source(src,…)` | `card_md_input_reader`            | Card source (path / dir / `.md` / `.json` / dict) → `FreeEnergyReport`. |
| `CalcInput`                  | `calc_json_input_reader`          | Calc-modes dataclass.                                                   |
| `SweepAxis`                  | `calc_json_input_reader`          | One axis (name, min, max, n_points).                                    |
| `IonicStrengthSpec`          | `calc_json_input_reader`          | `mode={fixed,auto,none}`, `value`.                                      |
| `GridRefineSpec`             | `calc_json_input_reader`          | `factor`, `n_layers`.                                                   |
| `load_calc_input(src)`       | `calc_json_input_reader`          | Parse JSON file / dict / `CalcInput` → `CalcInput` (validated).         |
| `dump_calc_input(calc,path)` | `calc_json_input_reader`          | Serialise `CalcInput` to JSON.                                          |
| `SUPPORTED_SWEEP_METHODS`    | `calc_json_input_reader`          | Tuple of legal `sweep_method` strings.                                  |
| `DEFAULT_AXES_BY_METHOD`     | `calc_json_input_reader`          | Per-method default axis specs.                                          |

## Card-source resolution

Priority for files inside a directory:

```
free_energy_card_numcalc.md
free_energy_card_enriched.md
free_energy_card.md
free_energy_card_with_include.md
*.md (first match)
```

`.json` / dict sources are passed to `compute_free_energy_network(...)`
to build the report from an equilibrium-network spec.

## Calc-modes (JSON v3 schema, dict-shape constraints)

```jsonc
{
  "sweep_method":  "pourbaix_sweep",
  "sweep_axes":    [{"name":"pH", "min":0, "max":14, "n_points":30},
                    {"name":"E_V","min":-1, "max":1.5, "n_points":30}],
  "ionic_strength":{"mode":"fixed","value":0.1},
  "temperature_C": 25.0,
  "system_catalog":{"chemical_system":{"metals":[…],"ligands":[…]}},
  "sweep_constraints":{
    "pH_constr":"pH_axis", "redox_constr":"E_V_axis",
    "[Cu]_constr":"[Cu]_tot_fixed",
    "initial_condition":{"[Cu]_total":[1.0,"mM"]}
  },
  "grid_refine":   {"mode":"boundary", "factor":2, "n_layers":1}
}
```

Full reference in [calc_json_input_reader.py](calc_json_input_reader.py).
Use `{"mode":"none"}` for an explicitly unrefined calculation.  Boundary
mode additionally requires integer `factor >= 2` and `n_layers >= 1`.
Missing and legacy default-dependent refinement blocks are rejected.

## Architecture rules

- Pure input layer — no solver or output dependencies.
- Validation: `CalcInput.validate()` returns a list of human-readable
  issues; `load_calc_input` raises `ValueError` on fatal issues.
- Card resolution never mutates the source; environment / concentration
  overrides happen later inside `SRD46_numcalculator_api`.
