---
name: predominance-map-design
description: Generate the L3_4 numeric coarse-grid and explicit boundary-refinement payload for standard Eh-pH Pourbaix calculations.
---

# L3_4 template: predominance-map sweep design

Use this template only to prepare
`finalize_sweep_grid(axes_json, grid_refine_json)`. Generate one `axes_json`
row for each axis already declared by L3_3, and one explicit
`grid_refine_json` decision. Do not restate constraints, totals, settings, or
coupling formulas in this stage.

For every row, use the physical `name` supplied by the SWEEP AXES table rather
than the L3_3 card-axis alias. Declare:

- the inclusive numeric `min` and `max`;
- integer `n_points >= 2`; and
- no additional fields.

Choose each axis window from the requested independent coordinates and the
applicable model domain. Choose the coarse point counts to capture anticipated
transitions while respecting the product of all per-axis counts. Boundary
refinement is a separate decision: its factor and layer count must both be
explicit, and its additional solve cost grows with dimension. Every value
must be a task value or documented design decision; do not import an unstated
route default.

Use the standalone `freeform-sweep-design` skill for generalized coordinate
systems such as concentration-pH or temperature-composition fields.

Submit `axes_json` in this shape:

```json
[
  {"name": "<first physical axis>", "min": "<explicit lower bound>",
   "max": "<explicit upper bound>", "n_points": "<explicit integer>"},
  {"name": "<second physical axis>", "min": "<explicit lower bound>",
   "max": "<explicit upper bound>", "n_points": "<explicit integer>"}
]
```

Replace every placeholder with a numeric declaration except `name`, which
must match the supplied physical-axis name exactly. The number of rows must
equal the declared DOF and the row order should follow the SWEEP AXES table.

Submit one explicit refinement payload:

```json
{"mode":"none"}
```

or, for boundary refinement:

```json
{"mode":"boundary", "factor":"<explicit integer>",
 "n_layers":"<explicit integer>"}
```

Boundary refinement can act only on transitions detected on the coarse grid;
it cannot compensate for a coarse grid that entirely misses a narrow domain.
For boundary mode, replace both placeholders and account for the increased
solve count. Do not omit the mode, factor, or layer count.
