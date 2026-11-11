---
example_id: fixed-ph-concentration-ratio-path
stage: constraints
registry_revision: 1
title: Fixed-pH concentration path with a coupled total ratio
summary: One parent-total axis drives concentration while pH and potential are fixed and ligand total is derived.
---

# L3_3 slice

This structure was exercised through the public Cu-glycine calculation path.
Replace values and catalog ids from the task.

```python
axes = ["Cu_total_axis"]
lets = {}
binds = [
  {"id":"Cu_axis", "op":"==", "lhs":lambda s:s.total["Cu"],
   "rhs":lambda a:a["Cu_total_axis"]},
  {"id":"L_ratio", "op":"==", "lhs":lambda s:s.total["ligand_5760"],
   "rhs":lambda s:10.0 * s.total["Cu"]},
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda s:7.0},
  {"id":"E", "op":"==", "lhs":lambda s:s.E_V,
   "rhs":lambda s:0.25},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda s:298.15},
  {"id":"I", "op":"==", "lhs":lambda s:s.ionic_strength,
   "rhs":lambda s:0.1},
]
```

Submit `expected_K=6`. Use an identifier-safe parent axis such as `Cu`, not
an oxidation-state id containing `$`.
