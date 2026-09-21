---
example_id: conserved-moles-dilution-path
stage: sweep_design
registry_revision: 1
title: Conserved-moles dilution path
summary: Range only the added-volume coordinate used by both L3_3 dilution formulas.
---

# L3_4 slice

```text
axes_json = [
  {"name":"V_added_mL", "min":0.0, "max":100.0, "n_points":51}
]
grid_refine_json = {"mode":"none"}
```

Adapt the volume window and count to the titration protocol. Neither derived
analytical concentration receives a separate row.
