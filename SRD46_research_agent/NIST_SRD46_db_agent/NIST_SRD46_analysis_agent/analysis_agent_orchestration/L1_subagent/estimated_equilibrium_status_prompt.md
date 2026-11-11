## Enabled query-estimated equilibrium status

This run enabled the missing-equilibrium enrichment branch. The
`run_analysis_pipeline` status additionally carries an
`estimated_equilibrium_enrichment` object plus deterministic `model_coverage`
and `topology_summary` objects — the only provenance sources for estimated
values.

Available in `estimated_equilibrium_enrichment`:

- Search state: `status`, `estimation_search_complete`, and (when incomplete)
  `reference_only_reason`, `failure_summary`, `interpretation_guard`.
- Materialization: `estimates_generated` means candidates were published;
  `materialized_estimated_entry_count` / `estimated_values_used` say whether
  any actually entered the free-energy cards — use these, plus the
  candidate/selected counts, when reporting what was used vs excluded.
- `estimated_stability_constants`: one row per session estimate — metal/ligand
  ids and names, `beta_definition_id`, `constant_type`, `log10_K`,
  `uncertainty_log10`, `temperature_C`, `ionic_strength_M`,
  `equation_python`, the validated `estimation_method` justification,
  `evidence_vlm_ids`, and a session-local `session_vlm_id`. Use
  `estimation_method` when judging how much weight an estimate can carry.
- Artifacts: `source`, `support_eq_map_path`, `manifest_path`.

`model_coverage` compares requested vs modeled ligands in the final
calculation card (`complete`, `omitted_requested_ligands`, card path,
`warning`). `topology_summary` is parsed from each complete
`topo_regions.csv`; use its `n_regions`/`regions` rows rather than truncated
file previews, and open the supplied card/topology paths for more context.

Hard rules:

- Estimated constants are session estimates: quote them with their
  uncertainty and label them per `source`, never as measured SRD46 entries; a
  `session_vlm_id` is not a measured SRD46 record and must not be cited as
  one.
- If `estimation_search_complete=false`, all estimated support was withheld
  (fail-closed); a zero materialized count is then not evidence that no
  relevant equilibrium exists.
- An omitted requested ligand was not modeled: its absence from solver output
  is not evidence of weak binding, negligible complexation, or no effect.

The committed L1 `record_analysis` prose is the report handed to the
orchestrator (same contract as a reference-only run). A deterministic
"Estimated-value provenance" appendix is attached to it automatically — do
not restate the enrichment payload verbatim, and never contradict it.
