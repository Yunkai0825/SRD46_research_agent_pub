# Canonical Schema — Calc-Input Card (`calc_input_card.json`)

**File name on disk**: `calc_input_card.json` (single evolving card under
`<output_dir>/LC3/`).
**Producer**: LC3 stages `LC3_1` (method + dof) → `LC3_2` (initial
conditions + modelling settings) → `LC3_3` (constraint spec, see
`LC3_solver_para_card_building/SCHEMA_AGENT_PIGGYBACKING_CONSTR.md`) →
`LC3_4` (sweep axes).
**Consumer**: `NIST_SRD46_core_numcalc_pipeline/numcalc_input_cards_reader/calc_json_input_reader.load_calc_input`
→ `CalcInput` → `SRD46_numcalculator_api.run_calculation`.

> This card carries **what sweep to run**. The thermodynamic system itself
> travels separately in the free-energy markdown card
> (`SCHEMA_FREE_ENERGY_CARD.md`); the two never overlap.

> **Runtime support boundary (2026-08-24):** the advanced species-ratio,
> species-fraction, cross-state RHS, and inequality examples below describe the
> front-end AST vocabulary, not an executable production contract. The native
> core currently supports a narrower Tier-1 subset: simple equality binds for
> intensives and component totals, plus formulas over Tier-1 values and axes
> that have a valid native axis-token mapping.
> Species references on the RHS are rejected; species LHS pins are disabled and
> manual opt-in reaches an unfinished API mapper; inequalities are not enforced
> by `compile_spec`.

---

## Top-level layout (advanced/aspirational example)

Example: **multi-metal (Cu + Fe, redox-active) × multi-ligand (glycine +
citrate) freeform sweep** with unusual constraints — one composition axis
(ligand competition ratio) and one redox axis, glycine-buffered pH, a
cross-metal total tie, and auto ionic strength:

```jsonc
{
  "sweep_method":  "freeform_sweep",          // one of SUPPORTED_SWEEP_METHODS
  "sweep_axes":    [{"name": "lig_ratio_axis", "min": 0.1,  "max": 10.0, "n_points": 25},
                    {"name": "fe_poise_axis",  "min": -6.9, "max": 6.9,  "n_points": 31}],
  "ionic_strength": {"mode": "auto"},          // fixed | auto | none
  "temperature_C": 25.0,
  "system_catalog": {"chemical_system": {
    "metals":  [{"element": "Cu", "redox_states": ["Cu$+2", "Cu$+1", "Cu$+0"]},
                {"element": "Fe", "redox_states": ["Fe$+3", "Fe$+2", "Fe$+0"]}],
    "ligands": [{"db_id": "ligand_5760", "name": "Glycine"},
                {"db_id": "ligand_9058", "name": "Citric acid"}]}},
  "sweep_constraints": {
    "lig_ratio_constr": "lig_ratio_axis",      // [gly]/[cit] swept
    "redox_constr":     "fe_poise_axis",       // ln([Fe3+]/[Fe2+]) swept
    "[Cu]_constr":      "[Fe]_tot_slaved",     // cross-metal tie
    "pH_constr":        "gly_buffered",        // pinned via zwitterion fraction
    "initial_condition": {"[Fe]_total":      [10.0, "mM"],
                          "[L1]+[L2]_total": [50.0, "mM"]}
  },
  "grid_refine":   {"factor": 2, "n_layers": 1},
  "constraint_spec": { /* piggybacked lc3_2.v1 residual spec — LC3_3, below */ },
  "_meta":         { "dof": 2 /* + stage audit fields */ }
}
```

## Field reference

| Field | Type | Authored by | Notes |
|-------|------|-------------|-------|
| `sweep_method` | str | LC3_1 | `pH_sweep` \| `pourbaix_sweep` \| `titration_sweep` \| `freeform_sweep`. |
| `_meta.dof` | int | LC3_1 | Number of sweep axes (degrees of freedom). |
| `system_catalog` | dict | LC1 (copied forward) | `chemical_system.metals/ligands` with canonical SRD-46 ids. |
| `sweep_constraints` | dict | LC3_2 (+ LC3_3 names) | Dict-shape constraint roles incl. `initial_condition` totals (`[value, unit]`). |
| `constraint_spec` | dict | LC3_3 | Compiled `lc3_2.v1` residual spec (see piggybacking schema doc). |
| `sweep_axes` | list | LC3_4 | One `{name, min, max, n_points}` per declared axis. |
| `ionic_strength` | dict | LC3_2 settings | `mode`: `fixed` (use `value`), `auto` (self-consistent I loop), `none` (ideal). |
| `temperature_C` | float | request env | Forwarded to the report resolver. |
| `grid_refine` | dict | LC3_4 / defaults | `factor` ≥ 1, `n_layers` ≥ 0 (`n_layers ≤ 0` ⇒ coarse-only). |

Validation lives in `CalcInput.validate()`; defaults per method in
`DEFAULT_AXES_BY_METHOD`. Legacy v1/v2 JSONs are auto-translated by a
shim inside `load_calc_input`.

---

## Pseudocode — the constraint card behind the example above

The `constraint_spec` block is compiled (never executed) from an
LC3_3-authored card. For the freeform case above—an illustration of the
front-end grammar, not a currently runnable production card—the surface card
looks like:

```python
# dof = 2  →  exactly 2 axes; every other DOF closed by one '==' bind
axes = ["lig_ratio_axis", "fe_poise_axis"]

lets = {
    # redox log-ratios (log space — smooth, no overflow)
    "cu_poise": lambda s: s.lnconc["Cu$+2"] - s.lnconc["Cu$+1"],
    "fe_poise": lambda s: s.lnconc["Fe$+3"] - s.lnconc["Fe$+2"],
    # ligand competition (real-space totals; ids from the variable catalog)
    "lig_ratio": lambda s: s.total["ligand_5760"] / s.total["ligand_9058"],
    "lig_sum":   lambda s: s.total["ligand_5760"] + s.total["ligand_9058"],
    # glycine zwitterion fraction (nonlinear pH proxy; species id from catalog)
    "gly_zwit":  lambda s: s.conc["[H].[L1].[z+0]"] / s.total["ligand_5760"],
}

binds = [
    # swept DOFs — one bind consumes each axis
    {"id": "lig_ratio_sweep", "op": "==",
     "lhs": lambda s: s.lig_ratio, "rhs": lambda a: a["lig_ratio_axis"]},
    {"id": "fe_poise_sweep",  "op": "==",
     "lhs": lambda s: s.fe_poise,  "rhs": lambda a: a["fe_poise_axis"]},

    # fixed DOFs
    {"id": "T",             "op": "==", "lhs": lambda s: s.temperature, "rhs": 298.15},
    {"id": "lig_sum_fixed", "op": "==", "lhs": lambda s: s.lig_sum,     "rhs": 0.05},
    {"id": "fe_total",      "op": "==",
     "lhs": lambda s: s.total["Fe"], "rhs": 0.01},           # element-level total

    # coupled DOFs (rhs over state — cross-metal tie, fixed Cu poise)
    {"id": "cu_fe_tie", "op": "==",
     "lhs": lambda s: s.total["Cu"],
     "rhs": lambda s: 0.5 * s.total["Fe"]},
    {"id": "cu_poise_fixed", "op": "==",
     "lhs": lambda s: s.cu_poise, "rhs": 4.605},             # [Cu2+]/[Cu+] = 100

    # nonlinear indirect pH control: glycine zwitterion fraction = 0.5
    {"id": "gly_buffer", "op": "==", "lhs": lambda s: s.gly_zwit, "rhs": 0.5},

    # feasibility guard (inequality — NOT a DOF)
    {"id": "ionic_cap", "op": "<=", "lhs": lambda s: s.ionic_strength, "rhs": 0.7},
]
```

Front-end rules this example is intended to exercise. Do not infer native
solver support from parser acceptance:

- `len(axes) == dof`, and exactly one `==` bind consumes each axis.
- Each lambda takes **one** parameter — `s` (state) or `a` (axes), never
  both; cross-references route through `lets` (acyclic DAG).
- Totals are constrained at **one** level per component: `s.total["Fe"]`
  (element) here — never element *and* valence totals together.
- All ids (`Cu$+2`, `ligand_5760`, `[H].[L1].[z+0]`, …) must appear in the
  LC3 variable catalog; the compiler rejects everything else with
  did-you-mean diagnostics, then checks DOF count == K, Jacobian-rank
  independence and `log`/`sqrt`/division domain guards.
- Inequalities (`<=`) are feasibility guards and do not close DOFs.

Full machine-readable reference:
`NIST_SRD46_core_numcalc_pipeline/numcalc_input_cards_reader/calc_json_input_reader.py`
and `NIST_SRD46_core_numcalc_pipeline/API_AND_SETTINGS.md` (§3).
