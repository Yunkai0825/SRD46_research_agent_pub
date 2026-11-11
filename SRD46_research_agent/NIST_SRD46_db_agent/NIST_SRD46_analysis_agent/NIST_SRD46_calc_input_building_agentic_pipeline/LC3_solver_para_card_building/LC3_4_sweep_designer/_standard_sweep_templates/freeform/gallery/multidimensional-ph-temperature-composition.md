---
example_id: multidimensional-ph-temperature-composition
stage: sweep_design
registry_revision: 1
title: Three-dimensional pH-temperature-composition field
summary: Range all three independent physical coordinates and account for their multiplicative solve cost.
---

# L3_4 slice

`Ca` is an illustrative identifier-safe parent-total name. Use the exact
three physical names from the SWEEP AXES table.

```text
axes_json = [
  {"name":"pH", "min":4.0, "max":12.0, "n_points":21},
  {"name":"temperature", "min":288.15, "max":328.15, "n_points":9},
  {"name":"Ca", "min":1.0e-6, "max":1.0e-3, "n_points":13}
]
grid_refine_json = {"mode":"boundary", "factor":2, "n_layers":1}
```

All numbers are illustrative. Check the product of point counts and the
additional boundary-refinement cost before submission.
