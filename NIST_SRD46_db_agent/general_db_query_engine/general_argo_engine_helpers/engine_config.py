"""
EngineConfig — shared configuration shape for the Argo ReAct engine.
===================================================================
Each agent defines its own dataclass subclass:

- ``ThermoML_query_argo_config.py``    → ``QueryAgentConfig(EngineConfig)``
- ``ThermoML_analysis_argo_config.py`` → ``AnalysisAgentConfig(EngineConfig)``

At startup the agent's ``argo_engine_subagent_helpers/__init__.py``
calls ``load_config(AGENT_CONFIG)`` to register the singleton.
Engine modules then read it at runtime via ``get_config()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class EngineConfig:
    """Configuration required by the shared Argo engine.

    No defaults — each agent subclass must define every value.
    These fields are consumed by the four core engine modules:
      - argo_client_caller.py  (ArgoClient factory methods)
      - react_loop.py          (synchronous agent_turn)
      - react_loop_async.py    (asynchronous async_agent_turn)
      - react_helpers.py       (truncation, compaction threshold)
    """

    # ── API connection ──────────────────────────────────────
    API_URL: str            # Argo REST chat endpoint; used by ArgoClient.call()
    API_USER: str           # Argo API username; sent in every request payload
    HEADERS: dict           # HTTP headers (Content-Type); passed to requests.post()

    # ── Model names ─────────────────────────────────────────
    MODEL: str              # Primary LLM for the L0 orchestrator and L1 workers
    VERDICT_MODEL: str      # LLM for post-job quality review; ArgoClient.for_verdict()
    PLANNER_MODEL: str      # LLM for strategy planning; ArgoClient.for_planner()

    # ── Generation parameters ───────────────────────────────
    TEMPERATURE: float      # Sampling temperature for the primary MODEL
    TOP_P: float            # Nucleus-sampling p (omitted for Claude models)
    MAX_TOKENS: int         # Max tokens per LLM response (primary calls)
    HTTP_TIMEOUT: int       # Seconds before requests.post() raises a timeout

    # ── Agent loop limits (L0) ──────────────────────────────
    MAX_TOOL_ITERATIONS: int  # Hard cap on tool-call iterations in react_loop.agent_turn()
    MAX_TURN_SECONDS: int     # Effective agent-time scale for reminder hooks only

    # ── L2 async limits ─────────────────────────────────────
    L2_MAX_ITERATIONS: int  # Iteration cap for async_agent_turn() (L2 leaf evaluators)
    L2_MAX_SECONDS: int     # Effective-time reminder scale for each async L2 call

    # ── Time warnings ───────────────────────────────────────
    WARN_THRESHOLDS: List[float]  # Fractions of the reminder scale
    MAX_WRAP_WARNINGS: int        # Number of progressive reminder levels
    MAX_EMPTY_WAITS: int          # Max consecutive empty LLM responses before abort

    # ── Tool result truncation ──────────────────────────────
    TOOL_RESULT_CHAR_LIMIT: int   # Char threshold; results longer than this are head+tail trimmed
    TOOL_RESULT_HEAD_CHARS: int   # Chars kept from the beginning of a truncated result
    TOOL_RESULT_TAIL_CHARS: int   # Chars kept from the end of a truncated result

    # ── Compaction ──────────────────────────────────────────
    COMPACTION_TRIGGER_CHARS: int  # Context size (chars) that triggers LLM-driven compaction
    SUMMARY_MAX_CHARS: int         # Target length for each compacted summary block
    GUIDANCE_MAX_TOKENS: int       # Token budget for the compaction-guidance LLM call

    # ── Verdict client ──────────────────────────────────────
    VERDICT_TEMPERATURE: float  # Temperature for the verdict LLM; low = deterministic review
    VERDICT_MAX_TOKENS: int     # Max tokens for the verdict response

    # ── Compactor client ────────────────────────────────────
    COMPACTOR_TEMPERATURE: float  # Temperature for the compaction sub-agent
    COMPACTOR_MAX_TOKENS: int     # Max tokens allowed for each compaction response

    # ── Planner client ──────────────────────────────────────
    PLANNER_TEMPERATURE: float  # Temperature for strategy-planning LLM calls
    PLANNER_MAX_TOKENS: int     # Max tokens for each planner response

    def is_claude_model(self, model_name: str) -> bool:
        """Return True for Claude/Opus models (require omitting top_p)."""
        return "claudeopus" in model_name.lower()


# ── Module-level singleton ──────────────────────────────────

_active_config: EngineConfig | None = None


def load_config(config: EngineConfig) -> None:
    """Set the active engine configuration.  Call once at agent startup."""
    global _active_config
    _active_config = config


def get_config() -> EngineConfig:
    """Return the active engine configuration.

    Raises ``RuntimeError`` if no agent has called ``load_config()`` yet.
    """
    if _active_config is None:
        raise RuntimeError(
            "Engine config not loaded. Call load_config() with your "
            "agent's EngineConfig before using the engine."
        )
    return _active_config
