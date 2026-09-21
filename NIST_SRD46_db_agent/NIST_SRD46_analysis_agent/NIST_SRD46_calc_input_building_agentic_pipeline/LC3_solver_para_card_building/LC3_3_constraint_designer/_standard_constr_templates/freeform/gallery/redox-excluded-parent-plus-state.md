---
example_id: redox-excluded-parent-plus-state
stage: constraints
registry_revision: 1
title: Redox excluded with parent total plus one state subtotal
summary: A pH axis coexists with fixed parent and state inventories, and no potential equation is emitted.
---

# L3_3 slice

This structure follows the validated two-valence Fe end-to-end regression.

```python
axes = ["pH_axis"]
lets = {}
binds = [
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda a:a["pH_axis"]},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda s:298.15},
  {"id":"I", "op":"==", "lhs":lambda s:s.ionic_strength,
   "rhs":lambda s:0.0},
  {"id":"M_parent", "op":"==", "lhs":lambda s:s.total["<parent-metal-id>"],
   "rhs":lambda s:1.0e-3},
  {"id":"M_state", "op":"==", "lhs":lambda s:s.total["<one-state-id>"],
   "rhs":lambda s:4.0e-4},
]
```

Submit `expected_K=5`. Replace all values and ids. Do not add an `E_V` bind.
