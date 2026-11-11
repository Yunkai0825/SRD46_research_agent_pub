---
example_id: nernst-coupled-ph-path
stage: constraints
registry_revision: 1
title: Nernst-coupled pH path
summary: One pH axis directly drives pH and a supported formula derives potential from it.
---

# L3_3 slice

The numeric line below mirrors a validated Cu-glycine regression. Replace its
coefficient, totals, and ids from the current task.

```python
axes = ["pH_axis"]
lets = {}
binds = [
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda a:a["pH_axis"]},
  {"id":"E_line", "op":"==", "lhs":lambda s:s.E_V,
   "rhs":lambda a:-0.059 * a["pH_axis"]},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda s:298.15},
  {"id":"I", "op":"==", "lhs":lambda s:s.ionic_strength,
   "rhs":lambda s:0.1},
  {"id":"M", "op":"==", "lhs":lambda s:s.total["<metal-id>"],
   "rhs":lambda s:0.001},
  {"id":"L", "op":"==", "lhs":lambda s:s.total["<ligand-id>"],
   "rhs":lambda s:0.01},
]
```

Submit `expected_K=6`. The L3_2 `derived` deferral for `s.E_V` is closed by
`E_line`.
