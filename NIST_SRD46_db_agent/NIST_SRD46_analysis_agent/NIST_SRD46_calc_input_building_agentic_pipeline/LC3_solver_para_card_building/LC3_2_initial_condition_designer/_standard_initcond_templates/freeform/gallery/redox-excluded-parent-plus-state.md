---
example_id: redox-excluded-parent-plus-state
stage: initial_conditions
registry_revision: 1
title: Redox excluded with parent total plus one state subtotal
summary: Fix a multivalent parent inventory and all but one oxidation-state subtotal while sweeping pH.
---

# L3_2 slice

Use when oxidation states are independent components and no redox potential
is modeled. This parent-plus-one-state pattern is covered by the Fe end-to-end
DOF regression.

```text
card_source:
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":<task K>, "basis":"known"},
  {"id":"I", "lhs":lambda s:s.ionic_strength,
   "value":<task mol/L>, "basis":"known"},
  {"id":"M_parent", "lhs":lambda s:s.total["<parent-metal-id>"],
   "value":<task mol/L>, "basis":"known"},
  {"id":"M_state", "lhs":lambda s:s.total["<one-state-id>"],
   "value":<task mol/L>, "basis":"known"},
]

activity_model = "<explicit>"
solids = "<include-or-exclude>"
redox_mode = "excluded"
ionic_strength_mode = "fixed"
deferred_json = [
  {"handle":"s.pH", "role":"swept", "note":"independent coordinate"}
]
```

For more than two oxidation states, fix the parent plus all but one state, or
all states, to obtain full rank. Do not set `E_V = 0`.
