---
name: freeform-sweep-design
description: Generate L3_2 fixed initial conditions, modelling settings, and deferrals for a freeform sweep whose axes or couplings do not fit a standard route.
---

# L3_2 template: freeform initial conditions

Use this skill only to prepare the arguments passed to
`commit_initial_conditions`. The `freeform_sweep` method routes here
automatically; `sweep_skill_id` need not classify the calculation as a
speciation path or predominance map.

When examples would help, use `list_freeform_examples` and open relevant
stage-local entries with `read_freeform_example`. You may recommend one
opened structural analogue with `select_freeform_example`, but neither
inspection nor recommendation is required for commit; `best_example` may be
null. Example identifiers and numbers are illustrative: use only runtime
catalog handles and values supported by the current task. Every inspected
example and any optional recommendation are recorded for L3_3; a recommended
example is listed first.

The gallery tools expose canonical registry IDs only. Entries that are absent
or inconsistent in another LC3 stage, or lack a passing solve check, are
quarantined and cannot be read or recommended.

Classify every physical quantity before writing the card:

- put fixed literal totals and intensives in the single top-level `inits`
  list;
- put each catalog handle that L3_3 will tie directly to an axis in
  `deferred_json` with role `swept`;
- put each catalog handle that L3_3 will calculate from an axis or another
  supported total in `deferred_json` with role `derived`;
- leave equilibrium-solved quantities unpinned only when the declared solver
  mode supplies their closure; and
- declare `activity_model`, `solids`, `redox_mode`, and
  `ionic_strength_mode` explicitly.

The current L3_3 surface has no syntax for inherited `freeform_vars_json`
names, so normally leave that object empty and place task-sourced numeric
literals directly in the later supported formula with provenance in `notes`.
Do not place an axis range, point count, constraint expression, or
dependent-species value in this stage. Exact species pins remain outside the
current production path; do not silently replace one with a component total.

The direct submission consists only of `card_source`, `notes`, the four model
settings, optional `freeform_vars_json`, `deferred_json`, and the optional
backward-compatible `sweep_skill_id` argument.
