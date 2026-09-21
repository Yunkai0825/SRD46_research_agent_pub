---
example_id: conserved-moles-dilution-path
stage: initial_conditions
registry_revision: 1
title: Conserved-moles dilution path
summary: Sweep added volume while deriving analytical concentrations from conserved moles and total volume.
---

# L3_2 slice

Use when the freeform coordinate is an externally defined added volume and
component concentrations change by dilution.

```text
card_source:
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":<task K>, "basis":"known"},
  {"id":"pH", "lhs":lambda s:s.pH,
   "value":<task pH>, "basis":"known"},
]

activity_model = "<explicit>"
solids = "<include-or-exclude>"
redox_mode = "excluded"
ionic_strength_mode = "auto"
deferred_json = [
  {"handle":"s.total[\"<metal-id>\"]", "role":"derived",
   "note":"conserved metal moles divided by pointwise volume"},
  {"handle":"s.total[\"<ligand-id>\"]", "role":"derived",
   "note":"conserved ligand moles divided by pointwise volume"}
]
```

Put the task-stated initial volume and moles in `notes`. The non-catalog axis
`V_added_mL` is declared by L3_3, not as an L3_2 pin.
