# NIST SRD-46 Analysis Agent

LLM-orchestrated analysis agent that answers natural-language aqueous
chemistry questions (speciation, chelation, Pourbaix behaviour,
titration, redox) with **numeric calculations grounded in the NIST
SRD-46 database**. The LLM layers decide *what* to compute and write
the briefs; every number comes from the deterministic card-building +
solver pipelines.

Current limitation: catalog-visible individual-species values are not
numerical warm-start guesses, and exact species pins are not supported through
the production path.

## Public API

```python
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import SRD46_analysis_run

result = SRD46_analysis_run(
    "Pourbaix diagram of Cu in glycine",
    session_dir="./_run_001",
    debug=False,
)
result["answer"]       # final L0 prose answer (markdown)
result["session_dir"]  # where all artifacts live
# also: iterations, elapsed_s, tool_history, timed_out
```

Defined in `SRD46_analysis_api.py` — a thin synchronous wrapper around
the L0 orchestrator. Models, budgets and Argo endpoints live in
`SRD46_analysis_argo_config.py` (`SRD46AnalysisAgentConfig`; L0/LD
default model `claudeopus47`, per-tier token/turn budgets, context
compaction thresholds).

## Architecture

```text
user request
   │
   ▼
 L0 orchestrator (LLM)                analysis_agent_orchestration/L0_orchestrator/
   │   tools: dispatch_l1_pipeline · list_session_files · read_session_file
   │   one dispatch per chemical system
   ▼
 L1 sub-agent (LLM)                   analysis_agent_orchestration/L1_subagent/
   │   tools: run_analysis_pipeline · list_outputs · read_output_file
   │          record_analysis (terminal)
   ▼
 calc-input building (LC1→LC2→LC3)    NIST_SRD46_calc_input_building_agentic_pipeline/
   │   LC1 eq-card alignment → LC2 free-energy card → LC3 calc_input_card.json
   ▼
 numeric solver                       NIST_SRD46_core_numcalc_pipeline/
   │   run_calculation → pH / Pourbaix / freeform / titration sweeps
   ▼
 LD validator (LLM quality gate)      analysis_agent_orchestration/LD_validator/
       tools: list_outputs · read_output_file · commit_verdict
       verdict ∈ {supported, contradicted, inconclusive}; legacy runs retry
       "contradicted", while enabled-estimation runs also retry an
       inconclusive/no-commit review and fail closed in acceptance metadata
```

## Folder map

| Folder | Purpose |
|--------|---------|
| [analysis_agent_orchestration/](analysis_agent_orchestration/) | L0 / L1 / LD agent loops and their workflow prompts. |
| [analysis_agent_argo_engine/](analysis_agent_argo_engine/) | Tier-tagged Argo client factories (per-layer model + budget). |
| [analysis_agent_context_hooks/](analysis_agent_context_hooks/) | Session working memory, run history/stats recorders, verdict writer. |
| [analysis_agent_toolbox/](analysis_agent_toolbox/) | Tier tool catalogs, deterministic calc wrappers, LLM record/replay. |
| [NIST_SRD46_calc_input_building_agentic_pipeline/](NIST_SRD46_calc_input_building_agentic_pipeline/) | LC1→LC2→LC3: brief → solver-ready `calc_input_card.json`. |
| [NIST_SRD46_core_numcalc_pipeline/](NIST_SRD46_core_numcalc_pipeline/) | Deterministic solver/topology/export stack (`run_calculation`). |
| [NIST_SRD46_normalizer_helpers/](NIST_SRD46_normalizer_helpers/) | Shared chemical-name resolver + constraint-card catalog/normalizer. |
| [NIST_SRD46_post_calc_tools/](NIST_SRD46_post_calc_tools/) | Post-calculation tools (Nernst E vs pH; reserved extensions). |
| [_DEBUG_script/](_DEBUG_script/) | Batch prompt runner + smoke/inspection scripts. |
| `_DEBUG_input/` / `_outputs_user/<bucket>/<DB>/<Agent>/Diagnostics/` | Test prompt table and per-label session outputs. |

## Session artifacts (per `session_dir`)

| File | Writer | Content |
|------|--------|---------|
| `answer.md` | L0 | Final prose answer. |
| `run_history.md` / `run_history.jsonl` | L0 / tracking hooks | Per-event audit log. |
| `manifest.json` | L0 | Phase/dispatch manifest. |
| `run_stats.json` | stats hooks | Per-phase counters. |
| `working_memory.json` | memory hooks | Session scratch state. |
| `verdict.json` | verdict hooks / LD | Final pass/fail verdict + hints. |
| `L1_call_NN/` | L1 | Per-dispatch tree: `LC1/`, `LC2/`, `LC3/`, `solver/`, `LD/`, `l1_report.md`, `l1_analysis.json`; enabled runs also persist deterministic `l1_scientific_quality.json`. |
| `l0_agent_response.md` | L0 | Enabled-run raw model synthesis retained for audit; `answer.md` is assembled from guarded L1 final-card coverage, estimate materialization, and complete topology reports. |

## Debug / batch testing

```bash
python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch
# subset:  --only L2_2_FeCaMg_sequestrant_survey   layers: --layer L1 L2
```

See [_DEBUG_script/README.md](_DEBUG_script/README.md).
