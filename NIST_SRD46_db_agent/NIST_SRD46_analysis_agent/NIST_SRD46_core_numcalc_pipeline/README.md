# NIST SRD-46 Core Numerical-Calculation Pipeline

Unified calculation engine for aqueous speciation and electrochemical
equilibrium analysis built on top of the NIST SRD-46 thermodynamic
database. Given a metal–ligand system, it produces:

- **pH speciation curves** — species fractions and concentrations vs pH.
- **Pourbaix diagrams** — 1-D / 2-D (E–pH) / 3-D (E–pH–a_w) predominance
  maps with full topology (regions, boundaries, junctions).
- **Freeform N-D sweeps** — any axis configuration (e.g. Nernst-line
  scans, composition sweeps over `[M]_total`/`[L]_total`).
- **CSV / JSON / PNG exports** — for downstream analysis and archival.

All sweep methods are accessed through a **single public entry point**:

```python
from SRD46_numcalculator_api import run_calculation, load_calc_input
```

which dispatches via the unified sweep dispatcher.

---

## 1. Quick start

```python
from SRD46_numcalculator_api import run_calculation, load_calc_input

calc = load_calc_input("_DEBUG_input/_sweep_parameter_calc_input/"
                       "pourbaix_sweep_example.json")

result = run_calculation(
    card_source="_outputs_user/<bucket>/<DB>/<Agent>/Diagnostics/test_01_Cu_glycine_merged",
    calc_input=calc,
    output_dir="_outputs_user/<bucket>/<DB>/<Agent>/Diagnostics/my_run",
    debug=True,
)

report     = result["report"]         # FreeEnergyReport
grid       = result.get("grid")       # NDGrid (for 2-D / 3-D)
out_paths  = result["output_paths"]
```

The same call covers all supported sweep methods — the dispatcher
selects the per-method handler based on `calc.sweep_method`.

---

## 2. Two inputs, one entry point

`run_calculation` takes **two distinct inputs** which never overlap:

| Input             | What it carries                                                                                  | Where it lives                                              |
|-------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| **Card source**   | The thermodynamic system (species, μ°, logβ, components, redox couples, total concentrations).   | [numcalc_input_cards_reader/](numcalc_input_cards_reader/)  |
| **Calc-modes**    | What sweep to run (method, axes, ionic strength, grid refine, constraints, overrides).           | [numcalc_input_cards_reader/](numcalc_input_cards_reader/)  |

Both are resolved inside `run_calculation`; everything below the API
is driven by these two pieces of data.

---

## 3. Supported sweep methods

| `sweep_method`     | Recognised axes                            | Status        |
|--------------------|--------------------------------------------|---------------|
| `pH_sweep`         | `pH`                                       | ✅ Full       |
| `pourbaix_sweep`   | `pH`, `E_V` (optional `a_w` → 3-D)         | ✅ Full       |
| `freeform_sweep`   | any user-declared scalar or composition    | ✅ Full       |
| `titration_sweep`  | `V_added_mL`                               | ✅ Full (fixed-pH dilution model via freeform) |

Defaults per method live in
[numcalc_input_cards_reader/calc_json_input_reader.py](numcalc_input_cards_reader/calc_json_input_reader.py)
(`DEFAULT_AXES_BY_METHOD`).

> Nernst E° calculations live in `NIST_SRD46_post_calc_tools/nernst_simple/`
> and are no longer dispatchable through `run_calculation`.

---

## 4. Calc-modes JSON (excerpt)

```jsonc
{
  "sweep_method":  "pourbaix_sweep",
  "sweep_axes": [
    {"name": "pH",  "min": 0.0,  "max": 14.0, "n_points": 30},
    {"name": "E_V", "min": -1.0, "max":  1.5, "n_points": 30}
  ],
  "ionic_strength": {"mode": "fixed", "value": 0.1},
  "temperature_C":  25.0,
  "system_catalog": {
    "chemical_system": {
      "metals":  [{"name": "Cu", "element": "Cu", "internal_id": "Cu$+2"}],
      "ligands": [{"name": "Glycine", "db_id": "ligand_5760"}]
    }
  },
  "sweep_constraints": {
    "pH_constr":             "pH_axis",
    "redox_constr":          "E_V_axis",
    "ionic_strength_constr": "ionic_strength_fixed",
    "[Cu]_constr":           "[Cu]_tot_fixed",
    "initial_condition":     {"[Cu]_total": [1.0, "mM"]}
  },
  "grid_refine": {"mode": "boundary", "factor": 2, "n_layers": 1}
}
```

Complete reference:
[numcalc_input_cards_reader/calc_json_input_reader.py](numcalc_input_cards_reader/calc_json_input_reader.py)
and [API_AND_SETTINGS.md](API_AND_SETTINGS.md).

---

## 5. Top-level layout

```
NIST_SRD46_core_numcalc_pipeline/
├── SRD46_numcalculator_api.py     ← public entry: run_calculation()
├── ARCHITECTURE.md                ← module-by-module map + I/O diagram
├── API_AND_SETTINGS.md            ← complete API + settings reference
├── README.md                      ← this file
│
├── numcalc_input_cards_reader/    ← card source + calc-modes JSON
├── thermodynamics_helpers/        ← FreeEnergyReport + canonical μ° + activity
├── solvers_and_topology/          ← point/grid solvers + topology mapper
├── sweep_pipelines/               ← per-method sweep handlers + dispatcher + output
│
├── _DEBUG_input/                  ← test fixtures
├── _outputs_user/<bucket>/<DB>/<Agent>/Diagnostics/                 ← test outputs (and built cards)
└── _DEBUG_script/                 ← smoke tests & probes
```

---

## 6. Smoke tests

```powershell
cd NIST_SRD46_core_numcalc_pipeline
python _DEBUG_script\_run_pourbaix.py 04   # 2-D Pourbaix, Fe+Cu+glycine+citrate
python _DEBUG_script\_run_pourbaix.py 03   # 3-D Pourbaix (pH × E_V × a_w)
```

---

## 7. Architecture

For a deep dive into every module — directory layout, key dataclasses,
data flow through the five-stage pipeline, and the unified sweep
dispatcher — see [ARCHITECTURE.md](ARCHITECTURE.md).

For per-folder responsibilities, see the README in each subfolder.
