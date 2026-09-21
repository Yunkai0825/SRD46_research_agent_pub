---
example_id: two-inventory-axis-map
stage: initial_conditions
registry_revision: 1
title: Two-total inventory map at fixed pH and potential
summary: Sweep independent parent-metal and ligand totals while holding pH, potential, temperature, and ionic strength fixed.
---

# L3_2 slice

Use for a genuinely non-Eh-pH two-dimensional composition map.

```text
card_source:
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":298.15, "basis":"known"},
  {"id":"pH", "lhs":lambda s:s.pH,
   "value":7.0, "basis":"known"},
  {"id":"E", "lhs":lambda s:s.E_V,
   "value":0.25, "basis":"known"},
  {"id":"I", "lhs":lambda s:s.ionic_strength,
   "value":0.1, "basis":"known"},
]

activity_model = "davies"
solids = "<include-or-exclude>"
redox_mode = "fixed"
ionic_strength_mode = "fixed"
deferred_json = [
  {"handle":"s.total[\"<parent-metal-id>\"]", "role":"swept",
   "note":"first independent inventory coordinate"},
  {"handle":"s.total[\"<ligand-id>\"]", "role":"swept",
   "note":"second independent inventory coordinate"}
]
```

The shown numbers are illustrative regression values, not defaults.
