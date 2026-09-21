---
example_id: two-inventory-axis-map
stage: sweep_design
registry_revision: 1
title: Two-total inventory map at fixed pH and potential
summary: Range the identifier-safe parent-metal and ligand total coordinates as a two-dimensional composition field.
---

# L3_4 slice

```text
axes_json = [
  {"name":"Cu", "min":1.0e-5, "max":1.0e-3, "n_points":21},
  {"name":"ligand_5760", "min":1.0e-4, "max":1.0e-1, "n_points":25}
]
grid_refine_json = {"mode":"boundary", "factor":2, "n_layers":1}
```

All bounds, counts, and refinement settings are illustrative. Use the two
physical names reported by the SWEEP AXES table.
