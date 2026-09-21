---
example_id: conserved-moles-dilution-path
stage: constraints
registry_revision: 1
title: Conserved-moles dilution path
summary: One added-volume axis appears in formulas for two analytical totals while pH and temperature remain fixed.
---

# L3_3 slice

The constants are illustrative values chosen only to make the formula valid
Python. Replace them with task-stated moles and initial volume.

```python
axes = ["V_added_mL"]
lets = {}
binds = [
  {"id":"M_dilution", "op":"==", "lhs":lambda s:s.total["<metal-id>"],
   "rhs":lambda a:1.0e-4 / (0.100 + 1.0e-3 * a["V_added_mL"])},
  {"id":"L_dilution", "op":"==", "lhs":lambda s:s.total["<ligand-id>"],
   "rhs":lambda a:2.0e-4 / (0.100 + 1.0e-3 * a["V_added_mL"])},
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda s:7.0},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda s:298.15},
]
```

Submit `expected_K=4`. Keep liters, milliliters, moles, and mol/L
dimensionally consistent.
