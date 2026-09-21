"""general_agent_tool_catalog — class-based tool catalogs with two-stage compaction."""

from .tool_entry import ToolEntry
from .agent_tool_catalog import AgentToolCatalog
from .agent_tool_compactor_hooks_catalog import (
    CompactorEntry,
    CompactorCatalog,
    compacts,
    uses_compactors,
)
from .health_check_helper import run_health_check, CatalogHealthCheckError

__all__ = [
    "ToolEntry",
    "AgentToolCatalog",
    "CompactorEntry",
    "CompactorCatalog",
    "compacts",
    "uses_compactors",
    "run_health_check",
    "CatalogHealthCheckError",
]
