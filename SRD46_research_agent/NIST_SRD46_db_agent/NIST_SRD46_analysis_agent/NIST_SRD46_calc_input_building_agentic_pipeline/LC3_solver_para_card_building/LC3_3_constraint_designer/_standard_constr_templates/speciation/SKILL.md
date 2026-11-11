---
name: speciation-path-design
description: Generate the L3_3 axes, lets, and equality binds for standard pH-speciation and titration sweeps.
---

# L3_3 template: speciation/path constraints

Use this template only to prepare
`compile_constraint_card(card_source, expected_K)`. `card_source` must contain
exactly the top-level names `axes`, `lets`, and `binds`; `expected_K` is the
intended number of equality binds. Do not choose numeric axis ranges, point
counts, or refinement settings in this stage.

Build one algebraically closed path. Tie each independent coordinate to one
axis, promote the fixed L3_2 declarations to constant binds, and close every
L3_2 deferral with its declared `swept` or `derived` role. Every active total
or intensive must be fixed, tied to an axis, derived from another supported
quantity, or deliberately left to the supported equilibrium/redox closure.
Count independent equations rather than requiring one input for every catalog
name.

## Reusable card patterns

Strict pH speciation:

```python
axes = ["pH_axis"]
lets = {}
binds = [
  {"id": "pH", "op": "==", "lhs": lambda s: s.pH,
   "rhs": lambda a: a["pH_axis"]},
  # Add fixed or derived totals and supported intensives.
]
```

Replace every angle-bracket placeholder before submission. Preserve
dimensional consistency for a standard titration. Use the standalone
`freeform-sweep-design` skill and its gallery for concentration axes, coupled
totals, dilution formulas, or other nonstandard algebraic paths.

For excluded redox, bind a full-rank set of oxidation-state totals. A
dependent-species pin is unsupported and must not be encoded as an ordinary
component-total bind.

Submit the completed source and set `expected_K` to the number of `==` entries
in `binds`.
