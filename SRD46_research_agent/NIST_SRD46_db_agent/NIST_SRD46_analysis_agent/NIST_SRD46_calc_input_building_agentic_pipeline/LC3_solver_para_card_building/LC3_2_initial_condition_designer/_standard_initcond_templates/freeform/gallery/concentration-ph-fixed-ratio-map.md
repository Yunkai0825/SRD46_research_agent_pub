---
example_id: concentration-ph-fixed-ratio-map
stage: initial_conditions
registry_revision: 1
title: Concentration-pH field with a fixed total ratio
summary: Sweep pH and one analytical total while deriving a second total from a constant ratio.
---

# L3_2 slice

Use for a two-coordinate field whose independent coordinates are pH and one
component total. The second total is not another axis.

```text
card_source:
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":<task K>, "basis":"known"},
]

activity_model = "<explicit>"
solids = "<include-or-exclude>"
redox_mode = "excluded"
ionic_strength_mode = "auto"
deferred_json = [
  {"handle":"s.pH", "role":"swept", "note":"first coordinate"},
  {"handle":"s.total[\"<metal-id>\"]", "role":"swept",
   "note":"second coordinate"},
  {"handle":"s.total[\"<ligand-id>\"]", "role":"derived",
   "note":"fixed ligand-to-metal total ratio"}
]
```

Record the task-stated ratio in `notes`; do not invent it as a default.
