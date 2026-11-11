---
example_id: multidimensional-ph-temperature-composition
stage: initial_conditions
registry_revision: 1
title: Three-dimensional pH-temperature-composition field
summary: Sweep pH, temperature, and one total while deriving a coupled second total.
---

# L3_2 slice

Use when no standard method exposes all three independent coordinates.

```text
card_source:
inits = []

activity_model = "<explicit>"
solids = "<include-or-exclude>"
redox_mode = "excluded"
ionic_strength_mode = "auto"
deferred_json = [
  {"handle":"s.pH", "role":"swept", "note":"first coordinate"},
  {"handle":"s.temperature", "role":"swept", "note":"second coordinate"},
  {"handle":"s.total[\"<metal-id>\"]", "role":"swept",
   "note":"third coordinate"},
  {"handle":"s.total[\"<ligand-id>\"]", "role":"derived",
   "note":"task-stated ratio to the swept metal total"}
]
```

State the coupling ratio and the intended temperature units in `notes`.
