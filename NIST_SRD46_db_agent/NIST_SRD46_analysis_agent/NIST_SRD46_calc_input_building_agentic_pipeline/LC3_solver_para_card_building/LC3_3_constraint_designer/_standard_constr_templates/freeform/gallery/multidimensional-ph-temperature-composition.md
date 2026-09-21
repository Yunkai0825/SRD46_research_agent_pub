---
example_id: multidimensional-ph-temperature-composition
stage: constraints
registry_revision: 1
title: Three-dimensional pH-temperature-composition field
summary: Three independent axes drive pH, temperature, and one total while another total remains coupled.
---

# L3_3 slice

```python
axes = ["pH_axis", "temperature_axis", "metal_tot_axis"]
lets = {}
binds = [
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda a:a["pH_axis"]},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda a:a["temperature_axis"]},
  {"id":"M", "op":"==", "lhs":lambda s:s.total["<metal-id>"],
   "rhs":lambda a:a["metal_tot_axis"]},
  {"id":"L_ratio", "op":"==", "lhs":lambda s:s.total["<ligand-id>"],
   "rhs":lambda s:2.0 * s.total["<metal-id>"]},
]
```

Submit `expected_K=4`. Replace the illustrative ratio and ids. The three axes
must match the DOF declared by L3_1.
