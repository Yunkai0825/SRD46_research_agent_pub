"""
Single entry point for the analysis-agent context hooks.

Mirrors the layout of ``NIST_SRD46_query_agent.query_agent_context_hooks
.hook_catalog`` but in much-reduced form because the analysis agent's
control flow is the hardcoded Python pipeline, not a chat loop. The L0
deterministic implementation reads working memory through this hook
catalog; a future LLM-driven L0 will additionally use the compactor /
tracking / verdict hooks at engine-anchor sites.

Public surface
--------------
- :class:`AnalysisWorkingMemory` — JSON-backed scratch dict per session.
- :class:`AnalysisHistoryRecorder` — append-only ``run_history.jsonl``.
- :class:`AnalysisStatsRecorder` — per-phase counter dump.
- :func:`run_verdict`, :func:`save_final_context` — post-run review.
- :func:`compact_tool_result`, :func:`compact_phase_artifact` — stubs.
"""

from __future__ import annotations

from .memory_hooks import AnalysisWorkingMemory, DEFAULT_MEMORY_FILENAME
from .tracking_hooks import AnalysisHistoryRecorder, AnalysisStatsRecorder
from .verdict_hooks import run_verdict, save_final_context
from .compactor_hooks import compact_tool_result, compact_phase_artifact

# Self-contained engine hook collection for the LLM-driven L0/L1 ReAct
# loops. Replaces the former cross-agent import from the query agent's
# ``query_agent_context_hooks.hook_catalog`` — see ``engine_agent_hooks``.
from .engine_agent_hooks import (
    AnalysisAgentHooks,
    build_agent_hooks,
    analysis_history_recorder,
    analysis_stats_recorder,
    analysis_reasoning_tracker,
)

__all__ = [
    "AnalysisWorkingMemory",
    "DEFAULT_MEMORY_FILENAME",
    "AnalysisHistoryRecorder",
    "AnalysisStatsRecorder",
    "run_verdict",
    "save_final_context",
    "compact_tool_result",
    "compact_phase_artifact",
    # Engine hooks (LLM-driven L0/L1)
    "AnalysisAgentHooks",
    "build_agent_hooks",
    "analysis_history_recorder",
    "analysis_stats_recorder",
    "analysis_reasoning_tracker",
]
