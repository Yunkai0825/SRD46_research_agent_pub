# `analysis_agent_toolbox/`

Tool surface shared by the analysis-agent LLM tiers: per-tier tool
catalogs, deterministic Python wrappers around the calc pipelines, and
passive transcript capture. Session continuation uses native first-principle reconstruction.

## Files

| File | Purpose |
|------|---------|
| `tool_catalog.py` | Tier-scoped tool catalogs — which tools each LLM tier may call. |
| `calc_wrappers.py` | Deterministic wrappers around card/calc entry points with a uniform contract. |
| `Argo_context_logging/` | Pipeline transcript capture (`_pipeline_transcript.py`); continuation uses the native first-principle reconstruction engine. |

## Tool catalogs (`tool_catalog.py`)

| Catalog (singleton) | Pipeline label | Registered tools |
|---------------------|----------------|------------------|
| `AnalysisL0Catalog` (`L0_CATALOG`) | `srd46-analysis-l0` | `parse_card`, `find_existing_cards`, `extract_topology` (read-only). |
| `AnalysisL1CardAssemblerCatalog` (`L1_CARD_ASSEMBLER_CATALOG`) | `srd46-analysis-l1-cards` | `find_existing_cards`, `build_or_load_ref_card`, `merge_ref_cards`, `enrich_card`, `parse_card`. |
| `AnalysisL1ConstraintBuilderCatalog` (`L1_CONSTRAINT_BUILDER_CATALOG`) | `srd46-analysis-l1-constraints` | `validate_calc_input`, `parse_card`. |
| `AnalysisL1CalcRunnerCatalog` (`L1_CALC_RUNNER_CATALOG`) | `srd46-analysis-l1-calc` | `run_calculation`, `extract_topology`. |
| `AnalysisL2InspectorCatalog` (`L2_INSPECTOR_CATALOG`) | `srd46-analysis-l2` | `parse_card`, `extract_topology` (read-only). |

## Wrapper contract (`calc_wrappers.py`)

- Every tool takes `purpose: str` and `tasks: str` as its first two
  keyword arguments; both must be non-empty or `CatalogContractError`
  is raised. `tasks` is always a **single prose string** (never a list).
- Every tool returns a uniform-shape dict consumable by LLMs and
  validators (status + payload + paths).
- Module bootstrap injects the calc roots into `sys.path` **without**
  `Path.resolve()` so Windows UNC / subst-drive paths stay short
  (MAX_PATH safety).

Wrapped entry points include `find_existing_cards`,
`wrap_build_pair_eq_map`, `wrap_render_pair_card`,
`wrap_merge_ref_cards`, `wrap_validate_calc_input`,
`wrap_run_calculation`, `wrap_extract_topology`.

## Session continuation

Use `SRD46_analysis_run` with the native first-principle reconstruction engine
and a verified source ledger. Requests, observations, runtime state and the
selected boundary must match. A transcript alone cannot resume an agent.
