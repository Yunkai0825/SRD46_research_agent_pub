"""
Argo Engine — aggregated re-exports for the ReAct engine helpers.
===============================================================
This module is **not** imported directly.  The package ``__init__.py``
lazy-loads these symbols via ``__getattr__`` to avoid circular imports.

Preferred import path for consumers::

    from argo_engine_helpers import ArgoClient, agent_turn, ...

Modules aggregated:
  - engine_config       → EngineConfig, load_config, get_config
  - argo_client_caller  → ArgoClient
  - react_helpers       → AgentTurnResult, truncate_result, _normalize_args,
                           _PARAM_ALIASES
  - react_loop          → agent_turn
  - react_loop_async    → async_agent_turn
"""

from .engine_config import EngineConfig, load_config, get_config  # noqa: F401
from .argo_client_caller import (                    # noqa: F401
    ArgoClient,
    ArgoPromptTooLargeError,
)
from .engine_react_helpers.react_helpers import (   # noqa: F401
    AgentTurnResult,
    truncate_result,
    _normalize_args,
    _PARAM_ALIASES,
)
from .engine_react_helpers.react_loop import agent_turn                  # noqa: F401
from .engine_react_helpers.react_loop_async import async_agent_turn      # noqa: F401

__all__ = [
    "EngineConfig",
    "load_config",
    "get_config",
    "ArgoClient",
    "ArgoPromptTooLargeError",
    "AgentTurnResult",
    "agent_turn",
    "async_agent_turn",
    "truncate_result",
    "_normalize_args",
    "_PARAM_ALIASES",
]
