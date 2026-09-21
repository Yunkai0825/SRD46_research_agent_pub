---
name: speciation-path-design
description: Generate the L3_2 literal initial-condition pins, modelling settings, and explicit deferrals for standard pH-speciation and titration sweeps.
---

# L3_2 template: speciation/path initial conditions

Use this template only to prepare the arguments passed to
`commit_initial_conditions`. Generate:

- `card_source`, containing exactly one top-level `inits` list of literal
  constant assignments;
- `notes`, documenting task-stated values and explicit assumptions;
- explicit `activity_model`, `solids`, `redox_mode`, and
  `ionic_strength_mode` settings;
- optional `freeform_vars_json` for named scalar constants;
- `deferred_json`, naming every catalog handle that L3_3 must sweep or
  derive.

Do not author constraint equations or numeric sweep grids in this stage.

First classify each physical quantity as swept, pointwise-derived,
equilibrium-solved, or fixed. Put only fixed literal values and the modelling
regime in the L3_2 submission. Do not pin the path coordinate, a quantity
derived from that coordinate, or a dependent equilibrium species.

Standard designs include:

- pH as the axis, with analytical metal and ligand totals fixed;
- titrant volume as the axis when the selected standard titration route
  exposes it; and
- redox excluded or explicitly fixed when the task requires it. Redox
  exclusion means no `E_V` equation; it does not mean `E_V = 0`.

Use the standalone `freeform-sweep-design` skill for concentration axes,
coupled totals, derived ratios, slaved potentials, or generalized paths.

Use only handles from the runtime variable catalog. A fixed-input structure
is:

```python
inits = [
  {"id": "T", "lhs": lambda s: s.temperature,
   "value": <explicit temperature in K>, "basis": "known",
   "note": "<task source>"},
  {"id": "M", "lhs": lambda s: s.total["<catalog metal id>"],
   "value": <explicit mol/L>, "basis": "known"},
  {"id": "L", "lhs": lambda s: s.total["<catalog ligand id>"],
   "value": <explicit mol/L>, "basis": "assumed",
   "note": "<rationale for the assumption>"},
]
```

Replace every angle-bracket placeholder before submission. `basis` must be
exactly `known` or `assumed`. Omit a total from `inits` only when L3_3 will
sweep or derive it. Declare that decision in `deferred_json`, for example:

```json
[{"handle":"s.total[\"<catalog id>\"]",
  "role":"swept",
  "note":"<axis rationale>"}]
```

L3_3 must close the same handle with the declared role. For fixed ionic
strength, pin its numeric value; for self-consistent ionic strength, select
the supported automatic mode and do not pin it.

An exact free-species or dependent-species concentration cannot currently be
submitted as an L3_2 pin. Report the limitation or redesign the intended
condition as a supported component-total declaration; never silently replace
a requested species concentration with a total.
