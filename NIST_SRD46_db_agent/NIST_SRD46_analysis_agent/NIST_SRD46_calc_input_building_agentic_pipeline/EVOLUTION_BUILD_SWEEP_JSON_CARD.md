# Evolution — Calc-Input Card Through LC3

How the single evolving `calc_input_card.json` is built stage by stage
inside `LC3_solver_para_card_building/` (schema:
`SCHEMA_SWEEP_JSON_CARD.md`). Every stage **rewrites the same card**,
appending its own block; per-call artefacts land under
`L3_<n>_call_NN/`.

> **Support warning:** the advanced worked example below is an aspirational
> front-end DSL example, not a successful end-to-end production run. Species
> ratios/fractions and species-on-RHS couplings do not pass the native core;
> species pins are disabled, and inequalities are not enforced by
> `compile_spec`. Use simple Tier-1 intensive/total equalities for current
> production cards.

| Stage | Module | Adds to the card | Key per-call artefacts |
|-------|--------|------------------|------------------------|
| LC3_1 — method decider | `LC3_1_method_decider/` | `sweep_method` + `_meta.dof` | `calc_input_card.json`, `report.md` |
| LC3_2 — initial-condition designer | `LC3_2_initial_condition_designer/` | initial conditions (`sweep_constraints.initial_condition`) **and** the modelling-settings sidecar (`activity_model`, `solids`, `redox_mode`, `ionic_strength_mode`, optional `freeform_vars`) | `initial_condition_card.py`, `initial_conditions.json`, `initial_conditions_brief.md`, `variable_catalog.txt` |
| LC3_3 — constraint designer | `LC3_3_constraint_designer/` | `constraint_spec` (compiled `lc3_2.v1` residual spec; settings **inherited** from LC3_2) | `sweep_card.lc3_2.json`, `constraints_payload.json`, `expanded_bindings.json`, `card_snapshot.md` |
| LC3_4 — sweep designer (optional, auto-discovered) | `LC3_4_sweep_designer/` | `sweep_axes` (`{name, min, max, n_points}` per axis) + `grid_refine` | `sweep_axes.json`, `report.md` |
| final | `LC3_solver_para_card_orchestrator.py` | — | `LC3/calc_input_card.json` + `summary/LC3_summary.json` |

Invariants:

- The modelling regime is **decided once, at LC3_2**, and inherited by
  LC3_3 — the constraint algebra must stay consistent with whatever
  LC3_2 recorded.
- Variable names always come from the authoritative variable catalog
  (`NIST_SRD46_normalizer_helpers/constr_card_normalizer/constr_variable_catalog.py`)
  built from the solver's own `FreeEnergyReport`; the LLM never invents
  ids.
- LC3_4 is conditionally loaded (`_OPTIONAL_STAGES` in the orchestrator):
  if the module or its `run_l3_4()` is missing, the stage is skipped and
  recorded in `stages_skipped`.

See `LC3_solver_para_card_building/README.md` for the full flow diagram
and the orchestrator return dict.

---

## Worked example — aspirational advanced grammar, not currently runnable

System: **Cu + Fe (both redox-active) × glycine + citrate**, freeform
sweep with very unusual constraints — a ligand-competition composition
axis, a redox-poise axis, a cross-metal total tie, glycine-buffered pH
and auto ionic strength. This is the same case whose final JSON and
constraint-card pseudocode are shown in `SCHEMA_SWEEP_JSON_CARD.md`;
here is how the card accretes through the four stages.

### Step 0 — inputs

The validated LC2 card (`LC2/free_energy_card.md`) and the LC1 system
catalog. Before the catalog is folded into the calc-input card,
`system_catalog_normalizer.prune_system_catalog_to_report` drops any
phantom valences LC1 enumerated but the LC2 card never realised (e.g.
`Cu$+3`) — otherwise the solver-side
`validate_catalog_against_report` would reject the card. The brief:
*"map Cu/Fe partitioning between glycine and citrate as a function of
the ligand ratio and the Fe redox poise, with pH held by the glycine
buffer."*

### Step 1 — LC3_1 method decider

Neither pH nor E_V is a swept axis (pH is buffered, redox is poised via
a concentration ratio), so `pH_sweep` / `pourbaix_sweep` are the wrong
shapes. LC3_1 commits `sweep_method = "freeform_sweep"` and
`_meta.dof = 2` (ligand ratio + Fe poise). The card is born with just
`{sweep_method, _meta}` → `L3_1_call_01/calc_input_card.json` +
`report.md`.

### Step 2 — LC3_2 initial-condition designer

Authors the known/assumed state **and** the modelling-settings sidecar
everything downstream inherits:

- initial conditions: `[Fe]_total = 10 mM`; combined ligand budget
  `[L1]+[L2]_total = 50 mM` (the split is deliberately *not* fixed —
  that is what the ratio axis sweeps). `[Cu]_total` is also left open:
  it will be **slaved** to `[Fe]_total` by an LC3_3 coupled bind.
- settings sidecar: `activity_model = "davies"`, `solids = "include"`,
  `redox_mode = "freeform"` (no E_V axis — poise enters through lnconc
  ratios), `ionic_strength_mode = "auto"`.

Artefacts: `initial_condition_card.py`, `initial_conditions.json`,
`initial_conditions_brief.md`, and `variable_catalog.txt` — the
authoritative id namespace built from the LC2 card's own
`FreeEnergyReport` via `build_variable_catalog`, so `Cu$+2`,
`ligand_5760`, `[H].[L1].[z+0]`, … are the only legal tokens.

### Step 3 — LC3_3 constraint designer

Authors the residual card (the pseudocode block in
`SCHEMA_SWEEP_JSON_CARD.md`): two axis-consuming `==` binds
(`lig_ratio_sweep`, `fe_poise_sweep`), fixed binds (`T`,
`lig_sum_fixed`, `fe_total`), coupled binds (`cu_fe_tie`,
`cu_poise_fixed`), the nonlinear `gly_buffer` bind pinning the glycine
zwitterion fraction at 0.5, and the `ionic_cap` inequality guard
(closes no DOF).

The intended design uses a two-stage gate. At present, the front-end compile
may accept this grammar, but the native solver gate rejects the species-based
parts:

1. **compile** — `constr_normalizer.normalize_card_source` self-heals
   LLM surface slips (handle spellings, `np.*` functions, `=` vs `==`),
   then `compile_card` resolves every id against the variable catalog
   (did-you-mean on miss), checks the `lets` DAG is acyclic, verifies
   **DOF count == K** (2 axes ⇒ exactly 2 axis binds; 7 `==` binds total
   close all 7 free DOFs after the inequality is excluded), runs the
   numeric Jacobian-rank independence check at a feasible sample (this
   is what catches, e.g., `cu_fe_tie` accidentally restating
   `fe_total`), and enforces `log`/`sqrt`/division domain guards →
   `lc3_2.v1` spec;
2. **solver gate** — `constraint_compiler.compile_spec` re-compiles the
   spec natively against the real `SystemCatalog`. It currently supports only
   the narrower Tier-1 subset described in the warning above; it does not prove
   this advanced example runnable.

Any failure is fed back as located `{"line", "msg"}` issues. For a current
production run, the agent must remove the unsupported species-based and
inequality forms and reduce the card to the Tier-1 subset; the advanced card
shown here is not accepted as written. An accepted, reduced spec is appended as
`constraint_spec`, and `sweep_constraints` records the human-readable role
names.

Artefacts: `sweep_card.lc3_2.json`, `constraints_payload.json`,
`expanded_bindings.json`, `variable_catalog.txt`, `card_snapshot.md`,
`l3_3_tool_calls.md`, `report.md`.

### Step 4 — LC3_4 sweep designer

Declares the grid for the two axes the card left open:
`lig_ratio_axis ∈ [0.1, 10], n=25` (log-spaced competition window) and
`fe_poise_axis ∈ [−6.9, 6.9], n=31` (ln-ratio ≈ ±3 decades), plus
`grid_refine = {factor: 2, n_layers: 1}`. Written into the same card as
`sweep_axes` → `L3_4_call_01/sweep_axes.json` + `report.md`. (If this
module were absent, the orchestrator would skip it via
`_OPTIONAL_STAGES` and the solver would fall back to
`DEFAULT_AXES_BY_METHOD`.)

### Step 5 — final

In the target design, the orchestrator would copy this evolved card to
`LC3/calc_input_card.json` and drive the 25×31 grid. That final step does not
occur for this advanced example today because LC3_3's native gate rejects its
species-based constraints. A reduced Tier-1 card can be copied and run through
the normal `load_calc_input → CalcInput → run_calculation` path.

*(Simple contrast: "speciation of Cu–glycine vs pH" needs only
LC3_1 (`pH_sweep`, dof=1) → LC3_2 (totals + davies/auto) → LC3_3
(pH-axis bind + totals binds) → LC3_4 (`pH ∈ [0,14]`), with no coupled
or nonlinear binds at all.)*
