---
example_id: nernst-coupled-ph-path
stage: sweep_design
registry_revision: 1
title: Nernst-coupled pH path
summary: Range the sole physical pH coordinate; the potential formula remains in the L3_3 card.
---

# L3_4 slice

This grid mirrors the validated Cu-glycine regression only as a structural
example. Choose the window and density for the current task.

```text
axes_json = [
  {"name":"pH", "min":0.0, "max":14.0, "n_points":30}
]
grid_refine_json = {"mode":"none"}
```

Do not add `E_V` as a second row: it is derived from pH by L3_3.
