---
name: freeform-sweep-design
description: Generate the L3_3 axes, lets, and equality binds for supported freeform paths, coupled totals, slaved intensives, and generalized fields.
---

# L3_3 template: freeform constraints

Use this skill only to prepare
`compile_constraint_card(card_source, expected_K)`. The prompt includes the
gallery note inherited from L3_2. When examples would help, inspect the
corresponding stage-local entry or alternatives. You may recommend one opened
example with `select_freeform_example`, but submission does not require a
recommendation and `best_example` may be null. This stage's inspected examples
and optional recommendation are appended to the notes for L3_4.

The gallery tools expose canonical registry IDs only. Cross-stage misaligned
or solve-invalid entries are quarantined before this agent can list or read
them.

`card_source` must contain exactly the top-level names `axes`, `lets`, and
`binds`. Give every independent coordinate one axis. Promote every fixed L3_2
pin to a constant bind and close every L3_2 deferral with its exact `swept` or
`derived` role. A derived relation does not add an independent axis. Set
`expected_K` to the number of equality entries in `binds`.

The production constraint path supports intensives and analytical component
totals on the left-hand side, direct axis ties, constants, and supported
arithmetic formulas over axes, intensives, and totals. Keep the equations
dimensionally consistent and full rank. Species concentrations, fractions,
or ratios cannot appear on the right-hand side, and an exact dependent-species
pin must not be disguised as a total bind.

Prefer an identifier-safe parent-element or ligand total as a concentration
axis. A punctuation-bearing oxidation-state token such as `Fe$+3` is valid as
a fixed total handle but is not currently safe as the runtime formula token
for a freeform axis.

Encode redox exactly as L3_2 declared it: `excluded` has no `E_V` equation and
needs a full-rank oxidation-state inventory; `fixed` binds `E_V` to a literal;
`freeform` slaves `E_V` to a supported formula; `solve` leaves `E_V` free and
uses exactly one state-subtotal target. Do not choose axis ranges, point
counts, or refinement settings here.
