# LC3_1 — Method Decider (Output / Calculation-Type Picker)

First stage of `LC3_solver_para_card_building`. An LLM agent chooses the
solver role and its dimensionality for the calculation; later LC3 stages
fill in everything else (axis ranges, constraints, initial conditions).

## What it does

Given:

- **`purpose` / `tasks`** — the L0/L1 intent for the calculation, and
- **the available output/calculation options** — auto-parsed from the
  solver registry (`sweep_pipelines.sweep_method_registry_api`), framed
  as abstract roles (speciation / predominance / freeform / titration),

the agent picks **exactly one** `sweep_method` (a registry id) and the
number of independent **degrees of freedom** (`dof`), bounded per method.

It builds **only** these fields. It does NOT build `sweep_axes`,
`sweep_constraints`, `system_catalog`, or initial conditions.

## Degrees of freedom

The DOF upper bound is auto-fetched from the solver's recognised-axis
table (`numcalc_input_cards_reader.calc_json_input_reader._RECOGNISED_AXES`):

| method            | allowed DOF |
|-------------------|-------------|
| `pH_sweep`        | 1           |
| `pourbaix_sweep`  | 1..3 (2 standard; 3 with a third axis e.g. `a_w`) |
| `titration_sweep` | 1           |
| `freeform_sweep`  | any (≥ 1)   |

The LLM picks `dof` from the purpose; `finalize_method` rejects values
outside the method's allowed range.

## Output

`calc_input_card.json` (the single evolving card the L3_2..L3_4 stages
grow in place):

```json
{ "sweep_method": "<registry id>",
  "_meta": { "dof": <int>, "stage": "LC3_1", "notes": "<rationale>" } }
```

## Public API

- `configure_l3_1_session(session_dir, history, stats, working_memory, debug)`
- `run_l3_1(purpose, tasks, fixed_card_path, output_dir) -> dict`
  returns `status`, `output_dir`, `sweep_method`, `dof`,
  `calc_input_card_path`, `elapsed_s`, `report`.

`fixed_card_path` is accepted for call-signature compatibility and
record-keeping only; this stage does not parse the card.

## Files

- `l3_1_method_agent.py` — deterministic wrapper + tool surface.
- `L3_1_method_workflow.md` — the agent system prompt (decision rules,
  DOF rules, the single `finalize_method` tool, worked examples).
