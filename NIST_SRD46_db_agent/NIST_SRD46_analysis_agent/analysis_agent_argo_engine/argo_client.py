"""
Argo client — SRD-46 analysis agent subclass.
=============================================
Mirrors :class:`NIST_SRD46_query_agent.query_agent_argo_engine.argo_client.SRD46QueryClient`
with tier-tagged factories (L0 / L1 / L2). Each tier is logged on every
Argo call for per-layer latency / token attribution.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...general_db_query_engine.general_argo_engine_helpers._argo_engine_entry_point import ArgoClient
from ..SRD46_analysis_argo_config import AGENT_CONFIG as cfg


@dataclass
class SRD46AnalysisClient(ArgoClient):
    """SRD-46 analysis agent ArgoClient with tier-based factory methods."""

    @classmethod
    def for_l0(cls) -> "SRD46AnalysisClient":
        return cls(model=cfg.MODEL, max_tokens=cfg.MAX_TOKENS, _tier="L0-analysis")

    @classmethod
    def for_l1(cls) -> "SRD46AnalysisClient":
        return cls(model=cfg.L1_MODEL, max_tokens=cfg.MAX_TOKENS, _tier="L1-phase")

    @classmethod
    def for_lc1_1(cls) -> "SRD46AnalysisClient":
        """LC1_1 — calc-input building, ID-alignment sub-agent."""
        return cls(model=cfg.LC1_1_MODEL,
                   max_tokens=cfg.LC1_1_MAX_TOKENS,
                   _tier="LC1_1-id-align")

    @classmethod
    def for_lc1_2(cls) -> "SRD46AnalysisClient":
        """LC1_2 — calc-input building, eq-map node validator sub-agent."""
        return cls(model=cfg.LC1_2_MODEL,
                   max_tokens=cfg.LC1_2_MAX_TOKENS,
                   _tier="LC1_2-eqmap-validator")

    @classmethod
    def for_l2(cls) -> "SRD46AnalysisClient":
        return cls(model=cfg.L2_MODEL, max_tokens=cfg.L2_MAX_TOKENS, _tier="L2-monitor")

    @classmethod
    def for_ld(cls) -> "SRD46AnalysisClient":
        """LD validator — reviews the L1 analysis against solver outputs."""
        return cls(model=cfg.VERDICT_MODEL,
                   max_tokens=cfg.VERDICT_MAX_TOKENS,
                   _tier="LD-validator")
