---
example_id: two-inventory-axis-map
stage: constraints
registry_revision: 1
title: Two-total inventory map at fixed pH and potential
summary: Two independent total axes coexist with fixed pH, potential, temperature, and ionic strength.
---

# L3_3 slice

```python
axes = ["Cu_total_axis", "glycine_total_axis"]
lets = {}
binds = [
  {"id":"Cu_axis", "op":"==", "lhs":lambda s:s.total["Cu"],
   "rhs":lambda a:a["Cu_total_axis"]},
  {"id":"L_axis", "op":"==", "lhs":lambda s:s.total["ligand_5760"],
   "rhs":lambda a:a["glycine_total_axis"]},
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

Submit `expected_K=6`. Replace values and ids. Both totals are independent;
do not also impose a fixed ratio between them.
