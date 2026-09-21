---
example_id: redox-excluded-parent-plus-state
stage: sweep_design
registry_revision: 1
title: Redox excluded with parent total plus one state subtotal
summary: Range pH only; fixed oxidation-state inventories and excluded potential add no grid coordinates.
---

# L3_4 slice

```text
axes_json = [
  {"name":"pH", "min":6.0, "max":8.0, "n_points":3}
]
grid_refine_json = {"mode":"none"}
```

This small grid mirrors the end-to-end regression shape. Select task-relevant
bounds and density. Do not add an `E_V` row.
