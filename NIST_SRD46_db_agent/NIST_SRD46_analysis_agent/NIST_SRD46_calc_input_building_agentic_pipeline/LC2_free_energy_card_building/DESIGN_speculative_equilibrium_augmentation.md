# Superseded — Speculative Equilibrium Augmentation

**Status:** superseded; not implemented.

The original draft placed the estimated-entry compiler after LC2_1. That is too
late: LC2_1 has already converted the stability-constant network to cumulative
log beta values and free energies.

The replacement plan puts evidence acquisition in the sibling
`LC1_3_estimate_eq_stability_dispatch` package, interposed before LC1_2 system
review, and joins accepted supporting entries to the materialized equilibrium
network inside LC2_1, before `parse_ref_eq_json_card(...)`:

- [current LC1.3 estimation module](../LC1_SRD46_eq_card_alignment/LC1_3_estimate_eq_stability_dispatch/README.md)

The replacement also defines the default-false setting, false-path identity
contract, same-agent query ownership, isolated parser boundary, session artifact
layout, provenance label, pre-conversion validation, and rollout tests.
