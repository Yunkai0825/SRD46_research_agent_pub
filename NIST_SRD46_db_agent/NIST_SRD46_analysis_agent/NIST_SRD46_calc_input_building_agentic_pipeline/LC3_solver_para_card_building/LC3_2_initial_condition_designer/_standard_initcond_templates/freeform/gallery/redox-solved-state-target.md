---
example_id: redox-solved-state-target
stage: initial_conditions
registry_revision: 1
title: Potential solved from one oxidation-state subtotal
summary: Sweep pH while leaving potential free and using one state subtotal as the global redox closure.
---

# L3_2 slice

Use when `E_V` is an unknown to solve rather than an axis or imposed formula.
The parent-plus-one-state target is covered by the Fe end-to-end DOF
regression.

```text
card_source:
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":<task K>, "basis":"known"},
  {"id":"I", "lhs":lambda s:s.ionic_strength,
   "value":<task mol/L>, "basis":"known"},
  {"id":"M_parent", "lhs":lambda s:s.total["<parent-metal-id>"],
   "value":<task mol/L>, "basis":"known"},
  {"id":"M_target", "lhs":lambda s:s.total["<target-state-id>"],
   "value":<task mol/L>, "basis":"known"},
]

activity_model = "<explicit>"
solids = "<include-or-exclude>"
redox_mode = "solve"
ionic_strength_mode = "fixed"
deferred_json = [
  {"handle":"s.pH", "role":"swept", "note":"independent coordinate"}
]
```

Do not pin or defer `E_V`; `redox_mode="solve"` supplies that closure.
