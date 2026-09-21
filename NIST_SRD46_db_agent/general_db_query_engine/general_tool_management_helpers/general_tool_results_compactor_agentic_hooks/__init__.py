"""
Shared agentic subagent — tool-level ReAct KEEP/DISCARD compaction.
====================================================================
Both the query agent and analysis agent delegate tool result triage to
this lightweight LLM subagent.  Each agent provides its own
``client_factory`` and ``cfg`` object via thin wrappers.

Public API
----------
ToolResult              — carries raw dict + subagent text + discard flag
ToolResultCompactor     — base dataclass for agent-specific compaction
call_tool_subagent      — ReAct-style LLM subagent call (parametrised)
parse_subagent_response — extract (thought, action, output) from LLM text
"""

from ._search_tool_results_compact_subagent import (
    ToolResult,
    ToolResultCompactor,
    call_tool_subagent,
    parse_subagent_response,
)

__all__ = [
    "ToolResult",
    "ToolResultCompactor",
    "call_tool_subagent",
    "parse_subagent_response",
]
