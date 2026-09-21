"""Context hooks for the analysis agent — see ``hook_catalog`` for the public surface."""
from .hook_catalog import (
    AnalysisWorkingMemory,
    DEFAULT_MEMORY_FILENAME,
    AnalysisHistoryRecorder,
    AnalysisStatsRecorder,
    run_verdict,
    save_final_context,
    compact_tool_result,
    compact_phase_artifact,
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
    "AnalysisAgentHooks",
    "build_agent_hooks",
    "analysis_history_recorder",
    "analysis_stats_recorder",
    "analysis_reasoning_tracker",
]
