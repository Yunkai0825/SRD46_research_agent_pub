---
name: freeform-sweep-design
description: Generate the L3_4 numeric grid and explicit refinement decision for arbitrary physical axes already declared by a freeform constraint card.
---

# L3_4 template: freeform sweep grid

Use this skill only to prepare
`finalize_sweep_grid(axes_json, grid_refine_json)`. The prompt includes the
gallery notes inherited from L3_2 and L3_3. When examples would help, inspect
the same stage-local entry or alternatives. You may recommend one opened
example with `select_freeform_example`, but finalization does not require a
recommendation and `best_example` may be null. The final card records every
example this stage opened and its optional recommendation.

The gallery tools expose canonical registry IDs only. Cross-stage misaligned
or solve-invalid entries are quarantined before this agent can list or read
them.

Create one `axes_json` row for each L3_3 axis, in the supplied SWEEP AXES table
order. Use the table's physical `name`, not the symbolic card alias, and
declare an inclusive numeric `min`, numeric `max`, and integer
`n_points >= 2`. The grid interface is a uniformly sampled numeric range; if
the scientific design needs a transformed coordinate, that coordinate must
already have been defined as an L3_3 axis rather than implied here.

For a total-concentration axis, use the exact identifier-safe physical name
reported by the table. Do not turn a punctuation-bearing oxidation-state id
into a new axis name at this stage.

Choose ranges from the requested physical domain and point counts from the
narrowest transition that must be resolved, while accounting for the product
of all axis counts. Every number must be a task value or documented design
decision, never an unstated route default.

Submit `grid_refine_json` explicitly as `{"mode":"none"}` or, only for a
supported two- or three-dimensional boundary-refined field, as
`{"mode":"boundary","factor":<integer>,"n_layers":<integer>}`. Do not
restate or change L3_3 constraints in this stage.
