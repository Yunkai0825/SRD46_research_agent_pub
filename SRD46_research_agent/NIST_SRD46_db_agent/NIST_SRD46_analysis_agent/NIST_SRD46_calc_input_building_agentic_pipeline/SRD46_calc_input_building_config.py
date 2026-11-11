"""Calc-input-building pipeline — agents config wrapper.

Every layer in ``NIST_SRD46_calc_input_building_agentic_pipeline``
(``LC1_*``, ``LC2_*``, ``LC3_*``) draws its LLM knobs (model name,
token / iteration / time budgets) from the shared singleton
:data:`NIST_SRD46_analysis_agent.SRD46_analysis_argo_config.AGENT_CONFIG`.

This module is intentionally thin — it just re-exports that singleton
so each sub-layer can write::

    from SRD46_calc_input_building_config import AGENT_CONFIG as cfg
    client = SRD46AnalysisClient.for_lc1_1()
    max_iter = cfg.LC1_1_MAX_ITERATIONS

without having to reach two package levels up.
"""

from __future__ import annotations

try:
    # Preferred: relative import (works when imported as
    # ``NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.calc_input_building_agents_config``).
    from ..SRD46_analysis_argo_config import (  # type: ignore
        AGENT_CONFIG,
        SRD46AnalysisAgentConfig,
        resolve_estimate_missing_equilibria,
    )
except ImportError:
    # Fallback: absolute import (works when the pipeline directory is
    # on ``sys.path`` directly — used by the LC1_* sub-agents whose
    # bootstrap injects the analysis-agent root).
    from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.SRD46_analysis_argo_config import (  # type: ignore
        AGENT_CONFIG,
        SRD46AnalysisAgentConfig,
        resolve_estimate_missing_equilibria,
    )

__all__ = [
    "AGENT_CONFIG",
    "SRD46AnalysisAgentConfig",
    "resolve_estimate_missing_equilibria",
]
