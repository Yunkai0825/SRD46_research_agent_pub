# Schema — Agent-Piggybacked Constraint Spec (`lc3_2.v1`)

The **constraint spec** that LC3_3 appends ("piggybacks") onto the single
evolving `calc_input_card.json` under the `constraint_spec` key. It is the
compiled form of the agent-authored constraint card (a small Python module
with `axes` / `lets` / `binds` in lambda surface syntax) — **parsed with
`ast`, never executed**.

> **Syntax is broader than execution.** `compile_card` can represent species
> references, nonlinear expressions, and inequalities in the AST, but the
> production `compile_spec`/dispatcher does not implement all of them.

- **Producer**: `LC3_3_constraint_designer/_constraint_helpers/constr_code_card_compiler.compile_card(source, *, components, species, intensives=None, expected_K=None, charge_balance_enforced=False)`
  (`SCHEMA_VERSION = "lc3_2.v1"`). Pre-compile self-healing by
  `NIST_SRD46_normalizer_helpers/constr_card_normalizer/constr_normalizer.normalize_card_source`.
- **Gate**: re-compiled natively against the authoritative `SystemCatalog`
  by `sweep_pipelines/_sweep_input_entry_point/constraint_compiler.compile_spec`
  before the card is accepted.
- **Consumer**: the numcalc API lowers the native spec through
  `constraint_compiler.compile_spec` and forwards its Tier-1
  `compiled_constraints` object. `_constraint_helpers/constr_residual_eval.py`
  is an unconnected future/diagnostic residual kernel, not the production
  species-residual path.
- **Debug artefact**: `L3_3_call_NN/sweep_card.lc3_2.json`.

## Top-level spec layout

```jsonc
{
  "schema_version": "lc3_2.v1",
  "source_card":    "<card module name>",
  "axes":           ["pH", "..."],            // declared sweep axes
  "dof":            {"K": 3,                  // number of '==' residual binds
                     "charge_balance_enforced": false},
  "lets":           { /* named sub-expressions (acyclic DAG) */ },
  "binds":          [ /* residual bindings, each an AST node tree */ ]
}
```

## Residual AST node grammar

```jsonc
{"op":   "<sym>", "args": [<node>, ...]}                    // operator / function
{"ref":  "lnconc" | "conc" | "total" | "species", "id": "<token>"}
{"ref":  "temperature" | "ionic_strength" | "pH" | "E_V"}   // intensives
{"ref":  "let", "name": "<let name>"}
{"const": <number>}
{"axis": "<axis name>"}
```

- Whitelisted functions: `log` (= `ln`), `log10`, `exp`, `sqrt`, `abs`,
  `pow`, `sinh`, `cosh`, `tanh`.
- Binary operators: `+ - * / ** %`; comparison ops in binds: `==`, `<=`, `>=`.
- `s.E_V` is a **passthrough** redox handle (Strategy B): an `s.E_V` bind is
  intercepted and routed to the fixed-grid redox input path, never a
  residual row.

## Production execution subset

| AST form | Front-end parse | Native production execution |
| --- | --- | --- |
| Simple `pH`, `E_V`, temperature, ionic-strength equality | accepted | supported with the core's constant/axis restrictions |
| Simple component-total equality | accepted | supported for constants and Tier-1/freeform formulas; axis use requires a valid native axis-token mapping |
| `s.species` / species `s.conc` / `s.lnconc` on LHS | accepted | exact-pin scaffolding only; disabled in LC3 and manual opt-in reaches `NotImplementedError` |
| Species reference on RHS; ratios/fractions/cross-species `let` | accepted by the AST layer | rejected during native lowering |
| General nonlinear/state expression on LHS | accepted by parts of the front end | not a supported core LHS |
| `<=` / `>=` bind | accepted | omitted by native equality lowering; not enforced as a feasibility guard |

The variable catalog is an ID namespace, not a capability advertisement.

## Compile-time validation (all must pass)

1. ID resolution of every token against the authoritative variable catalog
   (did-you-mean suggestions on miss).
2. `lets` form an acyclic DAG.
3. DOF count: number of `==` binds equals `K` (`expected_K` when given).
4. Numeric Jacobian-rank independence at a feasible sample point.
5. Domain guards on `log` / `sqrt` / division.

Failures raise `CardCompileError` with located `{"line", "msg"}` issues that
are fed back to the agent for repair.

## Settings sidecar (travels next to the spec, not inside it)

Authored at **LC3_2** and inherited by LC3_3:
`activity_model` (`ideal`/`davies`; Debye-Hückel is not implemented), `solids`
(`include`/`exclude`), `redox_mode`
(`axis`/`fixed`/`freeform`/`solve`/`excluded`),
`ionic_strength_mode` (`fixed`/`auto`/`none`), optional
`freeform_vars`.

See `LC3_3_constraint_designer/readme.md` for the authoring workflow and
`../SCHEMA_SWEEP_JSON_CARD.md` for where the spec sits inside
`calc_input_card.json`.
