# `analysis_agent_toolbox/`

Tool surface shared by the analysis-agent LLM tiers: per-tier tool
catalogs, deterministic Python wrappers around the calc pipelines, and
LLM record/replay support.

## Files

| File | Purpose |
|------|---------|
| `tool_catalog.py` | Tier-scoped tool catalogs — which tools each LLM tier may call. |
| `calc_wrappers.py` | Deterministic wrappers around card/calc entry points with a uniform contract. |
| `agent_cassette.py` | Record/replay of `ArgoClient.call(...)` for deterministic agent reruns. |
| `Argo_context_logging/` | Pipeline transcript capture (`_pipeline_transcript.py`) and replay (`_pipeline_replay.py`). |

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

## LLM record/replay (`agent_cassette.py`)

- `RecordingArgoClient` — wraps a live `SRD46AnalysisClient`; tapes one
  JSONL line per `.call()` (`system`, `prompt`, `stop`, `model`,
  `response`, `elapsed_s`, content hashes).
- `ReplayArgoClient` — serves recorded responses in order; raises
  `CassetteMismatchError` on hash divergence so tests pinpoint exactly
  what changed.

This makes full agent turns (hooks, tool dispatch, validation loops,
compaction) replayable **without calling Argo**.
