---
name: speciation-path-design
description: Generate the L3_4 numeric axis-grid and explicit refinement payload for standard pH-speciation and titration sweeps.
---

# L3_4 template: speciation/path sweep design

Use this template only to prepare
`finalize_sweep_grid(axes_json, grid_refine_json)`. Generate one `axes_json`
row for each axis already declared by L3_3, and one explicit
`grid_refine_json` decision. Do not restate constraints, totals, settings, or
path formulas in this stage.

For every row, use the physical `name` supplied by the SWEEP AXES table rather
than the L3_3 card-axis alias. Declare:

- the inclusive numeric `min` and `max`;
- integer `n_points >= 2`; and
- no additional fields.

Choose the window from the requested path and the applicable model domain.
Choose the point count from the narrowest anticipated transition that the
calculation must resolve and the available solve budget. Every value must be
an explicit task value or documented design decision; do not import an
unstated route default.

Use the standalone `freeform-sweep-design` skill for arbitrary physical axes
or coupled path geometry.

Submit `axes_json` in this shape:

```json
[
  {"name": "<physical axis name>",
   "min": "<explicit lower bound>",
   "max": "<explicit upper bound>",
   "n_points": "<explicit integer>"}
]
```

Replace every placeholder with a numeric declaration except `name`, which
must match the supplied physical-axis name exactly. The number of rows must
equal the declared DOF and the row order should follow the SWEEP AXES table.

Also submit one explicit refinement payload:

```json
{"mode":"none"}
```

or, only for a supported two- or three-dimensional boundary-refined design:

```json
{"mode":"boundary", "factor":"<explicit integer>",
 "n_layers":"<explicit integer>"}
```

For boundary mode, replace both placeholders and account for the increased
solve count. Do not omit the mode, factor, or layer count.
