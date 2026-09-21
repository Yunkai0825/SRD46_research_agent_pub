## Enabled-run deterministic review facts

This validation concerns a run with query-estimated-equilibrium enrichment
enabled. The user message includes a `Deterministic enabled-run facts` JSON
object containing the final-card `model_coverage`, the complete parsed
`topology_summary`, and estimation provenance/counts.

Treat those structured facts as authoritative:

- If `model_coverage.complete=false`, every
  `omitted_requested_ligands` entry was not modeled. Contradict any report that
  calls it modeled or infers weak/no binding, negligible complexation, or no
  diagram effect from its absence.
- Region counts and names must match the full `topology_summary`, not a
  truncated file preview.
- Query-estimated values entered the model only when
  `estimated_equilibrium_enrichment.estimated_values_used=true` and its
  materialized count is positive.
- If `estimated_equilibrium_enrichment.estimation_search_complete=false`,
  contradict any report that describes the reference-only fallback as an
  ordinary `no_estimation` result or as evidence that no relevant equilibrium
  exists. The report must identify the incomplete search and its failure
  counts.
- An honest reduced-system report that names the omissions and refuses to draw
  conclusions about them is supported even though it cannot answer the full
  requested chemistry.

You may use these complete deterministic facts directly. Do not batch-read or
re-inspect them through a compaction tool. Always execute `commit_verdict`.
