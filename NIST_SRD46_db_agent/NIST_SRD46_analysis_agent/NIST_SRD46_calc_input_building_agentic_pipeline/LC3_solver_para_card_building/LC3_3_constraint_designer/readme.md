# LC3_3 -- Constraint-Card Designer (residual-equation DSL)

L3_3 authors the system's **constraint card** -- a small Python module
(`axes` / `lets` / `binds`, lambda surface syntax) that pins every degree
of freedom of the solver with a residual equation. The card is **parsed
with `ast`, never executed**: its expressions reference solver *unknowns*
(`s.lnconc["Fe$+2"]`, `s.pH`, ...) that only exist mid-solve, so they are
symbolic residuals, not values.

The solver role (`sweep_method`) and the number of sweep axes (`dof`) are
inherited from L3_1. L3_3 chooses the constraint *structure* only; it does
**not** choose axis grid ranges / point counts (LC3_4's job).

> **Current runtime subset:** catalog-visible species handles are accepted by
> the front-end grammar but are not executable end to end. Individual-species
> LHS equalities are disabled exact pins; species ratios/fractions and
> species-on-RHS expressions are rejected by native lowering; inequalities are
> not enforced. Use Tier-1 intensive and component-total equalities in
> production.

## Variable catalog (no more guessing names)

To stop the LLM inventing variable names, L3_3 hands it an **authoritative
variable catalog** built from the solver's own `FreeEnergyReport` (resolved
from the L2 card via `resolve_card_source`) -- the same source the numcalc
solver consumes. The catalog mirrors the card namespace exactly:

```
s.E_V                  # electron / redox handle
s.pH                   # proton handle
s.temperature
s.ionic_strength
s.total["<id>"]        # element / valence / ligand totals
s.species["<id>"]      # one dependent aqueous / solid / gas species
s.conc["<id>"] / s.lnconc["<id>"]
```

It is grouped as requested: electron (`s.E_V`) / proton (`s.pH`)
intensives, then per ligand `{total, member species}`, then per metal
element `{element total, per valence {valence total, member species}}`.
Total ids come at three levels -- element symbol (`Cu`), valence token
(`Cu$+2`), ligand db_id (`ligand_5760`) -- and species ids are the report's
own `species_id` tokens (all phases: aqueous, solid, gas). Built by
`NIST_SRD46_normalizer_helpers.constr_card_normalizer.constr_variable_catalog.build_variable_catalog(report,
system_catalog)`, which also returns the flat `components` / `species` id
sets passed to the card compiler.

## Inputs / outputs

`run_l3_3(*, purpose, tasks, calc_input_card_path, system_catalog_path,
fixed_card_path, output_dir, initial_conditions_text="",
constraint_settings=None)`

- `calc_input_card_path` -- the single evolving `calc_input_card.json`
  (provides `sweep_method`, `_meta.dof`, and the `system_catalog` /
  `constraint_settings` authored by L3_2). L3_3 appends `constraint_spec`
  and rewrites the same card.
- `system_catalog_path` -- the L1/L2 system-catalog file (e.g. LC1's
  `lc1_sweep_input.json`); a bare `system_catalog` dict or a wrapper are
  both accepted. Used only for metal display-name overrides; token ids
  always come from the report.
- `fixed_card_path` -- the final L2 free-energy markdown card; resolved to
  a `FreeEnergyReport` to build the variable catalog.

Per-call artefacts (`L3_3_call_NN/`): `sweep_card.lc3_2.json` (the residual
spec, debug only), `calc_input_card.json` (the evolving card with
`constraint_spec` appended), `variable_catalog.txt`,
`expanded_bindings.json`, `constraints_payload.json`, `card_snapshot.md`,
`input.json`, `l3_3_tool_calls.md`, `report.md`.

`run_l3_3` returns `{status, output_dir, calc_input_card_path, spec_path,
settings_path, spec, settings, expand_ok, n_bindings, elapsed_s, report}`.

### Settings sidecar

The card models residuals only; the non-residual context travels in a
settings sidecar (also the `compile_constraint_card` tool arguments):
`activity_model` (`ideal`/`davies`; Debye-Hückel is not implemented), `solids`
(`include`/`exclude`), `redox_mode`
(`axis`/`fixed`/`freeform`/`solve`/`excluded`; `solve` releases E_V against
exactly one global state-subtotal target),
`ionic_strength_mode`
(`fixed`/`auto`/`axis`/`freeform`), optional `freeform_vars`.

## Correctness gate (two stages, both must pass)

A card is accepted only when:

1. **compile** -- `_constraint_helpers.constr_code_card_compiler.compile_card(
   source, components, species, expected_K)` first runs
   `constr_normalizer.normalize_card_source`
   to self-heal the surface details the LLM hallucinates (handle
   spellings, oxidation-state tokens, `np.*` functions, `"="` ops, axis
   attribute access) -- a no-op on an already-canonical card, line
   numbers preserved -- then parses the card, resolves every id against
   the authoritative catalog (did-you-mean on miss), checks DOF==K and
   Jacobian-rank independence, and enforces domain guards -> `lc3_2.v1`
   spec;
2. **solver gate** -- `constraint_compiler.compile_spec(catalog, axes,
   spec, settings)` compiles the spec natively against the real
   authoritative `SystemCatalog` (it lowers the Tier-1 binds and runs
   `compile_constraints` internally -- no intermediate bindings list).

On any failure the structured issue is fed back to the agent for repair.

## Tools exposed to the agent

- `inspect_card_section(section)` -- slice a section of the L2 card.
- `compile_constraint_card(card_source, activity_model, solids, redox_mode,
  ionic_strength_mode, freeform_vars_json, expected_K)` -- submit the final
  card; compiled + solver-gated; a successful call ends the run.

## Module map

- `l3_3_constraint_agent.py` -- the agent (`run_l3_3` /
  `configure_l3_3_session`).
- `NIST_SRD46_normalizer_helpers/constr_card_normalizer/constr_variable_catalog.py`
  *(shared, hosted at the analysis-agent level)* -- builds the variable catalog
  from the report.
- `_constraint_helpers/constr_code_card_compiler.py` -- card -> `lc3_2.v1`
  spec (parse, allowlist, semantic validate).
- `NIST_SRD46_normalizer_helpers/constr_card_normalizer/constr_normalizer.py`
  *(shared)* -- pre-compile self-healer for LLM-hallucinated surface details
  (handle spellings, oxidation-state tokens, `np.*` functions, op strings);
  conservative and line-preserving.
- `_constraint_helpers/constr_residual_eval.py` -- solver-facing
  residual/Jacobian kernel (augmented-Newton; future solver phases).
- `L3_3_constraint_workflow.md` -- the agent prompt (DSL authoring).
- `_Future_plan_full_freeform/` -- the design notes the DSL is based on.
