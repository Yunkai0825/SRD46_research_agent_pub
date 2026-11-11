"""Generate tool-calling instructions for LLM system prompt injection.

The ReAct loop (``react_loop.agent_turn``) expects the LLM to emit tool
calls in the format:
    <tool_call>{"name": "tool_name", "arguments": {"p1": "v1"}}</tool_call>

This module builds the instruction block that tells the LLM:
  1. The exact format for tool calls
  2. A compact list of available tools with parameter info
3. Rules about one-tool-per-turn and result handling

Public API
----------
build_tool_instructions(tools: dict[str, Callable]) -> str
    Returns a formatted instruction string to prepend/append to the
    system prompt.
"""

from __future__ import annotations

import inspect
from typing import Callable, Dict

from ..general_text_context_marker_catalog import MARKERS


# Parameters that are internal plumbing — never shown to the LLM.
_INTERNAL_PARAMS = frozenset({"hooks", "agent_hooks", "engine_hooks"})


def _describe_tool(name: str, fn: Callable) -> str:
    """Build a one-line tool description from name + function signature."""
    sig = inspect.signature(fn)
    params = []
    for pname, p in sig.parameters.items():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if pname in _INTERNAL_PARAMS:
            continue
        if p.default is inspect.Parameter.empty:
            params.append(pname)
        else:
            params.append(f"{pname}={p.default!r}")
    param_str = ", ".join(params)

    doc = (fn.__doc__ or "").strip().split("\n")[0]  # first line only
    if doc:
        return f"- {name}({param_str}) — {doc}"
    return f"- {name}({param_str})"


def build_tool_instructions(tools: Dict[str, Callable]) -> str:
    """Build the full tool-calling instruction block for the system prompt.

    Parameters
    ----------
    tools : dict[str, Callable]
        Tool registry mapping names to callables (same as agent_turn tools).

    Returns
    -------
    str
        Instruction text to inject into the system prompt.
    """
    tool_lines = [_describe_tool(name, fn) for name, fn in sorted(tools.items())]
    tool_list = "\n".join(tool_lines)

    return f"""\
## Tool Calling

Format — one or more tool calls per turn:

{MARKERS.reasoning.open}
... internal reasoning (discarded each turn) ...
{MARKERS.reasoning.close}
{MARKERS.summary.open}
... 2-5 sentence conclusion (kept in memory, ≤600 chars) ...
{MARKERS.summary.close}
{MARKERS.tool_call.open}{{"name": "tool_a", "arguments": {{"p1": "v1"}}}}{MARKERS.tool_call.close}
{MARKERS.tool_call.open}{{"name": "tool_b", "arguments": {{"p2": 123}}}}{MARKERS.tool_call.close}
{MARKERS.wait_tag}

Final answer (no more tool calls):

{MARKERS.answer.open}
... complete answer — any length, markers stripped ...
{MARKERS.answer.close}

Rules:
- Batch independent tool calls in one turn — add multiple {MARKERS.tool_call.open}…{MARKERS.tool_call.close} blocks before {MARKERS.wait_tag}. All execute before the next turn.
- {MARKERS.tool_call.open} MUST come AFTER {MARKERS.summary.close} and BEFORE {MARKERS.wait_tag}. Arguments must be valid JSON.
- {MARKERS.answer.open} must NEVER mention internal mechanics (working memory, queries, memory keys, agent systems).
- If a tool returns an error, try a different approach or adjust parameters.

Available tools:
{tool_list}"""
