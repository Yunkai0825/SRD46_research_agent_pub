## Enabled query-estimation reporting contract

For this run only, missing-equilibrium estimation is enabled. Each L1 result
may contain an authoritative `## Modeling coverage` section generated from the
resolved LC1 catalog and final LC3 calculation card.

- Preserve that coverage statement in the user-facing answer.
- If L1 says requested ligands were omitted or the system was reduced, never
  say those ligands were modeled and never infer weak binding, negligible
  complexation, or no diagram effect from their absence.
- Preserve the complete deterministic topology region count and labels from
  L1; do not replace them with a count inferred from a truncated preview.
- Distinguish `no_estimation`/zero materialized estimated entries from an
  estimate that actually entered the calculation.
- Also distinguish a complete `no_estimation` search from
  `estimation_search_complete=false`. The latter is an incomplete LC1_3 search
  whose all-or-reference-only fallback withheld every estimate. Preserve that
  limitation, its reason, and failure counts; never present it as evidence
  that no estimable equilibrium exists.
- A converged reduced-system solve is not a completed answer to the requested
  mixed-ligand chemistry. State the limitation prominently and report only the
  reduced-system result.
