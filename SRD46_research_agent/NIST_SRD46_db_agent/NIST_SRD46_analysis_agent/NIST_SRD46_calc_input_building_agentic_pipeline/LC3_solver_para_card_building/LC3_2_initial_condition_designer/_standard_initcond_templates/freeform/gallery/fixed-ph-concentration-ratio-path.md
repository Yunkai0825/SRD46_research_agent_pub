---
example_id: fixed-ph-concentration-ratio-path
stage: initial_conditions
registry_revision: 1
title: Fixed-pH concentration path with a coupled total ratio
summary: Sweep one identifier-safe parent total while pH and potential are fixed and a ligand total follows by a constant ratio.
---

# L3_2 slice

Use when concentration is the only independent coordinate. This structure was
exercised through the public Cu-glycine calculation path; adapt all ids and
values to the current task.

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
   "note":"only independent coordinate"},
  {"handle":"s.total[\"<ligand-id>\"]", "role":"derived",
   "note":"task-stated ligand-to-metal total ratio"}
]
```

The shown numbers are regression values, not route defaults.
