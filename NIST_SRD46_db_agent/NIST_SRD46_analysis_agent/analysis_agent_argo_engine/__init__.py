"""ArgoClient subclass + tier factories for the analysis agent.

Importing this module loads the analysis-agent ``EngineConfig`` into
the shared engine singleton so any subsequent ``agent_turn`` /
``ArgoClient`` use sees the analysis defaults.
"""
from ...general_db_query_engine.general_argo_engine_helpers.engine_config import load_config
from ..SRD46_analysis_argo_config import AGENT_CONFIG
load_config(AGENT_CONFIG)
from .argo_client import SRD46AnalysisClient

__all__ = ["SRD46AnalysisClient"]
