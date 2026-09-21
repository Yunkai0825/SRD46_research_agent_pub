# LC3_4 -- Sweep-Grid Designer (numeric axis ranges)

L3_4 is the **final** stage of the LC3 solver-parameter card-building
pipeline. The earlier stages each decided one thing:

- **L3_1** chose the solver role (`sweep_method`) and the number of sweep
  axes (`dof`);
- **L3_2** fixed the system's initial conditions;
- **L3_3** authored the **constraint card** -- the residual equations that
  pin every degree of freedom and declare *which* handles are swept (the
  `axes` block of the `lc3_2.v1` spec).

L3_4 attaches a numeric grid -- `min` / `max` / `n_points` -- to each swept
axis. It changes **nothing** about the constraints; it only gives every
axis the constraint card declared a range to scan. The LLM reads the L0
`purpose` / `tasks` plus a swept-axis table and emits one
`{name, min, max, n_points}` row per axis plus an explicit refinement design.

## Physical names vs. card handles

The constraint spec's `axes` block names axes with **card handles**
(e.g. `pH_axis`, `E_V_axis`). The numcalc solver consumes **physical**
names (`pH`, `E_V`, `a_w`, `V_added_mL`). L3_4 bridges the two: for every
swept axis it scans the spec's `binds` for the bind whose RHS references
that axis and reads the bound handle (`lhs.ref` / `lhs.id`), falling back
to suffix-stripping (`_tot_axis` / `_axis`). The LLM is shown a table
mapping `card-axis -> handle -> physical-name` so it declares the name the
solver recognises.

## Range declarations

`freeform_sweep` accepts any axis names. Every method requires explicit axis
bounds and resolution from the task or a documented agent assumption; L3_4
does not supply numeric range defaults.

## Inputs / outputs

`run_l3_4(*, purpose, tasks, calc_input_card_path, fixed_card_path,
system_catalog_path, output_dir)`

- `calc_input_card_path` -- the single evolving `calc_input_card.json`
  (carries `sweep_method`, `_meta.dof`, `system_catalog`,
  `constraint_spec`, `constraint_settings`). L3_4 appends `sweep_axes` and
  an explicit top-level `grid_refine` decision for either `none` or
  `boundary` mode.
- `fixed_card_path`, `system_catalog_path` -- accepted for
  orchestrator-call symmetry; not required (the evolving card already
  carries the system catalog + spec).

Per-call artefacts (`L3_4_call_NN/`): `calc_input_card.json` (the final
native calc-input the numcalc solver consumes), `input.json`,
`sweep_axes.json`, `l3_4_tool_calls.md`, `agent_response.md`, `report.md`.

`run_l3_4` returns `{status, output_dir, calc_input_path, sweep_axes,
grid_refine, refinement_design, n_cells, elapsed_s, report}`.

## Correctness gate

The emitted axes are merged with the L3_3 spec / settings / system catalog
into a **native calc-input** card:

```json
{
  "sweep_method": "...",
  "sweep_axes": [{"name": "...", "min": "<declared>",
                  "max": "<declared>", "n_points": "<declared>"}],
  "system_catalog": {...},
  "constraint_spec": {...lc3_2.v1 spec...},
  "constraint_settings": {...},
  "grid_refine": {"mode": "boundary", "factor": "<declared>",
                  "n_layers": "<declared>"}
}
```

and re-validated by the real solver loader
(`calc_json_input_reader.load_calc_input`). This re-parses the constraint
spec **and** checks every axis. Fatal failures (rejected card): duplicate
axis name, `n_points < 2`, `max <= min`. Advisory only (non-fatal): an axis
name that is not standard for the method -- so `freeform_sweep` axis names
never block. A committed card is guaranteed consumable by the numcalc
solver.

## Tool exposed to the agent

- `finalize_sweep_grid(axes_json, grid_refine_json)` -- submit the grid as a
  JSON list of `{name, min, max, n_points}` rows (one per swept axis, using
  physical names) plus `{"mode":"none"}` or a boundary design containing
  explicit `factor` and `n_layers`. The
  call assembles + gates the native calc-input; a successful call ends the
  run.

## Module map

- `l3_4_sweep_agent.py` -- the agent (`run_l3_4` /
  `configure_l3_4_session`).
- `L3_4_sweep_workflow.md` -- the agent prompt (grid-range authoring;
  explicit design rules + worked examples).
