"""Shared plumbing for the two LC2_3 dedup LLM pathways.

Both the per-group pathway (:mod:`group_agent`) and the singleton-batch
pathway (:mod:`singleton_agent`) need the same Argo client, engine hooks,
tool-instruction renderer and a small fence stripper.  They live here so
each pathway module stays focused on its prompt + tool surface.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path as _Path
from typing import Any, Tuple

# ── path bootstrap: import LC2's external deps (shared LLM engine, query
#    agent context hooks, analysis config) as bare top-level packages
#    WITHOUT pulling in the heavy NIST_SRD46_analysis_agent package
#    __init__ chain. ───────────────────────────────────────────────
_THIS = _Path(__file__).absolute()
_ANALYSIS_ROOT = _THIS.parents[4]   # NIST_SRD46_analysis_agent/
_DB_AGENT_ROOT = _THIS.parents[5]   # NIST_SRD46_db_agent/
_SRD46_ROOT    = _THIS.parents[6]   # SRD46_research_agent/
for _p in (_ANALYSIS_ROOT, _DB_AGENT_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
    AgentTurnResult,
)
from general_db_query_engine.general_argo_engine_helpers.engine_config import (
    load_config as _load_engine_config,
)
from general_db_query_engine.general_argo_engine_helpers._argo_engine_entry_point import (
    ArgoClient as _ArgoClient,
)
from general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from SRD46_analysis_argo_config import AGENT_CONFIG as cfg
from ...agent_context_artifacts import (
    write_agent_context_bundle,
)

# LC2 builds its LLM client from the SHARED engine ArgoClient + the analysis
# config directly, rather than importing analysis_agent_argo_engine (whose
# package __init__ drags in the full analysis-agent stack).  Loading the
# config here mirrors that package's import-time side effect.
_load_engine_config(cfg)

__all__ = [
    "agent_turn",
    "AgentTurnResult",
    "build_tool_instructions",
    "cfg",
    "strip_fence",
    "build_client_and_hooks",
    "write_subagent_context",
]


def strip_fence(raw: str) -> str:
    """Remove a leading/trailing ```` ```json ```` fence if present."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw


def write_subagent_context(
    out_dir: Any,
    stage_label: str,
    result: Any,
    *,
    tool_prefix: str,
    stage_id: str = "LC2_agent",
    role: str = "subagent",
    phase: str = "agent_turn",
    system_prompt: str = "",
    user_message: str = "",
    tools: Any = None,
    required_tools: Any = (),
    memory: Any = (),
    error: str | None = None,
    metadata: Any = None,
) -> None:
    """Persist one LC2 agent's exact input context and lossless result.

    ``tool_prefix`` is retained for call compatibility; the context bundle has
    canonical filenames and a machine-readable manifest. All I/O is best-effort
    so an audit-write failure cannot change a chemistry decision.
    """
    try:
        write_agent_context_bundle(
            out_dir,
            stage_id=stage_id,
            stage_label=stage_label,
            role=role,
            phase=phase,
            system_prompt=system_prompt,
            user_message=user_message,
            tools=dict(tools or {}),
            required_tools=list(required_tools or ()),
            memory=list(memory or ()),
            result=result,
            error=error,
            metadata={"legacy_tool_prefix": tool_prefix, **dict(metadata or {})},
            runtime={
                "engine": (
                    "general_db_query_engine.general_argo_engine_helpers."
                    "agent_turn"
                ),
                "argo_api_user": cfg.API_USER,
                "model": cfg.L1_MODEL,
                "tier": "L1-phase",
                "temperature": cfg.TEMPERATURE,
                "top_p": cfg.TOP_P,
                "max_tokens": cfg.MAX_TOKENS,
                "max_tool_iterations": cfg.MAX_TOOL_ITERATIONS,
                "turn_timeout_seconds": cfg.MAX_TURN_SECONDS,
                "keep_recent_results": cfg.KEEP_RECENT_RESULTS,
                "trimmed_preview_chars": cfg.TRIMMED_PREVIEW_CHARS,
                "guidance_max_tokens": cfg.GUIDANCE_MAX_TOKENS,
                "http_timeout_seconds": cfg.HTTP_TIMEOUT,
            },
        )
    except Exception:                                # pragma: no cover
        # Best-effort: an audit-write failure must never change a chemistry
        # decision — but it MUST be visible.  A silently dropped bundle
        # previously made the LC2_3 context audit fail the whole phase
        # closed (2026-09-05: MAX_PATH manifest losses looked like agent
        # turns that never happened).
        logging.getLogger(__name__).warning(
            "LC2 agent context bundle write failed for %s (%s)",
            out_dir, stage_label, exc_info=True,
        )


def build_client_and_hooks() -> Tuple[Any, Any]:
    """Build a fresh L1 Argo client + engine hooks for one subagent run."""
    client = _ArgoClient(
        model=cfg.L1_MODEL, max_tokens=cfg.MAX_TOKENS, _tier="L1-phase",
    )
    hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "", guidance_hooks=[],
    ).engine_hooks
    return client, hooks
