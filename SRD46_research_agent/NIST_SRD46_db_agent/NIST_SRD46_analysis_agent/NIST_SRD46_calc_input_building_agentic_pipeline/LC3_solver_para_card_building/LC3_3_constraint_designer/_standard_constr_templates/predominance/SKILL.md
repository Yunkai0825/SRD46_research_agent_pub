---
name: predominance-map-design
description: Generate the L3_3 axes, lets, and equality binds for standard Eh-pH Pourbaix calculations.
---

# L3_3 template: predominance-map constraints

Use this template only to prepare
`compile_constraint_card(card_source, expected_K)`. `card_source` must contain
exactly the top-level names `axes`, `lets`, and `binds`; `expected_K` is the
intended number of equality binds. Do not choose numeric axis ranges, point
counts, or refinement settings in this stage.

Give each independent coordinate one axis and one tie equation. Promote the
fixed L3_2 declarations to constant binds, and close every L3_2 deferral with
its declared `swept` or `derived` role. All remaining active totals and
intensives must be fixed or closed by a supported equilibrium/redox rule.

Classical Eh-pH card (`pourbaix_sweep`):

```python
axes = ["pH_axis", "E_V_axis"]
lets = {}
binds = [
  {"id": "pH", "op": "==", "lhs": lambda s: s.pH,
   "rhs": lambda a: a["pH_axis"]},
  {"id": "E", "op": "==", "lhs": lambda s: s.E_V,
   "rhs": lambda a: a["E_V_axis"]},
  # Add fixed or derived totals and supported intensives.
]
```

Use the standalone `freeform-sweep-design` skill and its gallery for
concentration-pH fields, ratio coordinates, slaved redox paths, temperature
maps, or any other generalized geometry. A dependent-species contour remains
unsupported and must not be encoded as an axis or exact pin.

Submit the completed source and set `expected_K` to the number of `==` entries
in `binds`.
