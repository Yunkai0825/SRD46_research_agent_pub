---
example_id: concentration-ph-fixed-ratio-map
stage: constraints
registry_revision: 1
title: Concentration-pH field with a fixed total ratio
summary: Two axes drive pH and one total; a third total follows by a supported total-to-total formula.
---

# L3_3 slice

```python
axes = ["pH_axis", "metal_tot_axis"]
lets = {}
binds = [
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda a:a["pH_axis"]},
  {"id":"M_axis", "op":"==", "lhs":lambda s:s.total["<metal-id>"],
   "rhs":lambda a:a["metal_tot_axis"]},
  {"id":"L_ratio", "op":"==", "lhs":lambda s:s.total["<ligand-id>"],
   "rhs":lambda s:2.0 * s.total["<metal-id>"]},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda s:298.15},
]
```

Submit `expected_K=4`. Replace `2.0`, the temperature, and both ids from the
task; the ratio bind is derived and does not create a third axis.
