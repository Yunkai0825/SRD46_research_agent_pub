"""argo_engine_helpers — sub-modules for the ReAct agentic loop engine.

EngineConfig / load_config / get_config are imported eagerly (lightweight).
Everything else is lazy-loaded on first access to avoid circular imports
when agent config modules subclass EngineConfig.
"""

from .engine_config import EngineConfig, load_config, get_config  # noqa: F401
from .engine_hooks_anchors import (  # noqa: F401
    AnchorPoint,
    AnchorCollection,
    AgentAnchorCollection,
    HookBinding,
    EngineHooks,
    AgentHookCollection,
    EMPTY_HOOKS,
    AGENT_START_TRACKING,
    AGENT_FINALIZE_TRACKING,
    AGENT_RECORD_REFERENCES,
    AGENT_SAVE_FINAL_CONTEXT,
    AGENT_RUN_VERDICT,
    define_anchor,
    define_anchor_collection,
    bind_hook,
    build_agent_lifecycle_bindings,
    compile_hooks,
    anchor,
)

_LAZY_NAMES = {
    "ArgoClient",
    "ArgoPromptTooLargeError",
    "AgentTurnResult",
    "agent_turn",
    "async_agent_turn",
    "truncate_result",
    "_normalize_args",
    "_PARAM_ALIASES",
}


def __getattr__(name: str):
    if name in _LAZY_NAMES:
        from . import _argo_engine_entry_point as _ep
        val = getattr(_ep, name)
        globals()[name] = val  # cache for subsequent access
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "EngineConfig",
    "load_config",
    "get_config",
    "AnchorPoint",
    "AnchorCollection",
    "AgentAnchorCollection",
    "HookBinding",
    "EngineHooks",
    "AgentHookCollection",
    "EMPTY_HOOKS",
    "AGENT_START_TRACKING",
    "AGENT_FINALIZE_TRACKING",
    "AGENT_RECORD_REFERENCES",
    "AGENT_SAVE_FINAL_CONTEXT",
    "AGENT_RUN_VERDICT",
    "define_anchor",
    "define_anchor_collection",
    "bind_hook",
    "build_agent_lifecycle_bindings",
    "compile_hooks",
    "anchor",
    *_LAZY_NAMES,
]
