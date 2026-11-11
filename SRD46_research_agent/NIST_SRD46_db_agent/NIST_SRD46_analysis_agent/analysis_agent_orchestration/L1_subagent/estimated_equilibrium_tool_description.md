Enabled estimation runs additionally return an
`estimated_equilibrium_enrichment` object (search state, materialization
counts, `estimated_stability_constants` rows with each session estimate's
value, uncertainty, conditions, and validated justification) plus
deterministic `model_coverage` and `topology_summary`. The enabled-run
briefing in the system instructions defines how to read them; its hard rules
(session estimates vs measured entries, fail-closed incomplete search,
omitted-ligand limits) apply to this status object.
