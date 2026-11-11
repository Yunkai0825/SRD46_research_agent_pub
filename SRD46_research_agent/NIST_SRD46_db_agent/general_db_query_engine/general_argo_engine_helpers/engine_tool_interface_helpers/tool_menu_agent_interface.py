"""
Tool-menu interactive hook — tool catalog & proxy for subagent tools.
=====================================================================
Wrap all the tools subagents have into several MCP subagents as a tool
catalog.  The main agent, if needed, can call this subagent_tool_menu
MCP tool to inspect the tools accessible to the subagents, and
optionally can send purpose+task instructions to run specific subagent
tools through this main agent MCP tool.  Since this is just a menu and
wrapper with tool_menu_hooks, all context token limit should be less
than 150 tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolMenuHook:
    """Base hook for tool-menu inspection — subclasses fill in agents.

    Each agent subclass should populate *tool_catalog* with the tools
    available to its subagents, and implement :meth:`inspect` and
    :meth:`dispatch` to expose them to the main agent.
    """

    agent_label: str = ""
    tool_catalog: Dict[str, Any] = field(default_factory=dict)

    def inspect(self) -> str:
        """Return a compact listing of available subagent tools."""
        if not self.tool_catalog:
            return "(no subagent tools registered)"
        lines = [f"## {self.agent_label} Tool Menu"]
        for name, meta in self.tool_catalog.items():
            desc = meta if isinstance(meta, str) else getattr(meta, "__doc__", "") or ""
            lines.append(f"- **{name}**: {desc[:120]}")
        return "\n".join(lines)

    def dispatch(self, tool_name: str, **kwargs) -> Any:
        """Invoke a subagent tool by name (override in subclass)."""
        raise NotImplementedError(
            f"{self.__class__.__name__}.dispatch() not implemented"
        )