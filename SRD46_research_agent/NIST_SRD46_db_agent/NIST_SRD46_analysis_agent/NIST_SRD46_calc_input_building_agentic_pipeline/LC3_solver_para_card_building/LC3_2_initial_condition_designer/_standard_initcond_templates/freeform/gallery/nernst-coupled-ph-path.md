---
example_id: nernst-coupled-ph-path
stage: initial_conditions
registry_revision: 1
title: Nernst-coupled pH path
summary: Sweep pH while deriving potential from the same coordinate and holding analytical totals fixed.
---

# L3_2 slice

Use when pH is independent but `E_V` follows a declared line rather than
being fixed or independently swept. This pattern is based on the converged
Cu-glycine freeform regression card; adapt every id and value.

```text
card_source:
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":<task K>, "basis":"known"},
  {"id":"I", "lhs":lambda s:s.ionic_strength,
   "value":<task mol/L>, "basis":"known"},
  {"id":"M", "lhs":lambda s:s.total["<metal-id>"],
   "value":<task mol/L>, "basis":"known"},
  {"id":"L", "lhs":lambda s:s.total["<ligand-id>"],
   "value":<task mol/L>, "basis":"known"},
]

activity_model = "<explicit>"
solids = "<include-or-exclude>"
redox_mode = "freeform"
ionic_strength_mode = "fixed"
deferred_json = [
  {"handle":"s.pH", "role":"swept", "note":"independent path coordinate"},
  {"handle":"s.E_V", "role":"derived", "note":"potential follows the declared line"}
]
```

Do not pin `E_V` in `inits`.
