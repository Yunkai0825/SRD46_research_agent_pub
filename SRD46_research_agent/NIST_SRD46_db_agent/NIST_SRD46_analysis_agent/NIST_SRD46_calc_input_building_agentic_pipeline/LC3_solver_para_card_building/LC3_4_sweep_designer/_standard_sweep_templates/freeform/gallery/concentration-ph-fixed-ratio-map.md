---
example_id: concentration-ph-fixed-ratio-map
stage: sweep_design
registry_revision: 1
title: Concentration-pH field with a fixed total ratio
summary: Range pH and the one independently swept parent total; the coupled total has no grid row.
---

# L3_4 slice

`Ca` is an illustrative identifier-safe parent-total name. Use the exact
physical name from the SWEEP AXES table.

```text
axes_json = [
  {"name":"pH", "min":4.0, "max":12.0, "n_points":41},
  {"name":"Ca", "min":1.0e-6, "max":1.0e-3, "n_points":31}
]
grid_refine_json = {"mode":"boundary", "factor":2, "n_layers":1}
```

The displayed bounds, counts, and refinement settings are examples, not
defaults. The derived ligand total receives no row.
