---
name: predominance-map-design
description: Generate the L3_2 literal initial-condition pins, modelling settings, and explicit deferrals for standard Eh-pH Pourbaix calculations.
---

# L3_2 template: predominance-map initial conditions

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

Identify the independent map coordinates first. Do not pin a coordinate
that L3_3 will sweep. Put only fixed thermodynamic/model settings and the
constant analytical inventories required at every coordinate in `inits`.

For the classical Eh-pH design, defer pH and `E_V`; fix temperature,
analytical totals, activity treatment, ionic-strength mode, and solid
inclusion. Use the standalone `freeform-sweep-design` skill for
concentration-pH, ratio, temperature, water-activity, or other generalized
coordinate systems.

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
exactly `known` or `assumed`. Omit an inventory from `inits` only when it is
an L3_3 axis or derived quantity, and list its exact handle in `deferred_json`
with role `swept` or `derived` and a non-empty rationale. L3_3 must close the
same handle with that role.

Redox exclusion changes the component basis; it is not an assignment
`E_V = 0`. Declare the required independent oxidation-state totals. An exact
dependent-species concentration cannot currently be submitted as an L3_2
pin; do not substitute a component total without saying so.
