# `analysis_agent_argo_engine/`

Tier-tagged Argo LLM client for the analysis agent. A thin subclass of
the shared engine's `ArgoClient` whose factory methods bind each agent
tier to its own model, token budget and `_tier` tag — enabling
per-layer cost/latency attribution in Argo logs.

## Public surface (`argo_client.py`)

| Factory | Tier tag | Model (config key) | Used by |
|---------|----------|--------------------|---------|
| `SRD46AnalysisClient.for_l0()` | `L0-analysis` | `MODEL` | L0 orchestrator |
| `SRD46AnalysisClient.for_l1()` | `L1-phase` | `L1_MODEL` | L1 sub-agent |
| `SRD46AnalysisClient.for_lc1_1()` | `LC1_1-id-align` | `LC1_1_MODEL` | LC1_1 ID-alignment agent |
| `SRD46AnalysisClient.for_lc1_2()` | `LC1_2-eqmap-validator` | `LC1_2_MODEL` | LC1_2 eq-map validator |
| `SRD46AnalysisClient.for_l2()` | `L2-monitor` | `L2_MODEL` | L2 monitors |
| `SRD46AnalysisClient.for_ld()` | `LD-validator` | `VERDICT_MODEL` | LD validator |

All model names / budgets come from
`SRD46_analysis_argo_config.SRD46AnalysisAgentConfig`; transport,
retry and timeout behaviour are inherited unchanged from the shared
`ArgoClient`.

For deterministic record/replay of `client.call(...)` see
`analysis_agent_toolbox/agent_cassette.py`.
