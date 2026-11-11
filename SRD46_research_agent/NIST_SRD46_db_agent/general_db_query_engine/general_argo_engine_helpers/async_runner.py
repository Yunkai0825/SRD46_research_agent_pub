"""Async execution engine for workflow-driven agents.

Reads parsed workflow definitions and executes phases sequentially,
with optional ``asyncio.gather()`` fan-out within a single phase when
``parallel_dispatch`` is specified.

The runner is LLM-backend agnostic — it receives a *tool executor*
callback that the outer harness must supply.  This callback maps a
tool name + arguments to a result string (or dict).

Public API
----------
run_workflow(parsed, tool_executor, *, context) -> list[PhaseResult]
    Execute all phases of a parsed workflow, returning per-phase results.

run_phase(phase, tool_executor, *, context) -> PhaseResult
    Execute a single phase (sequential or parallel).

fan_out(items, call_fn, *, max_concurrent=8) -> list
    Low-level parallel dispatcher using asyncio.gather + Semaphore.

ToolExecutor protocol
---------------------
The ``tool_executor`` callback must have the signature::

    async def tool_executor(tool_name: str, **kwargs) -> str | dict

It is called for every tool invocation.  For LLM-based subagents the
harness would wrap the LLM call; for Python tools it would call them
directly.

If the tool executor is synchronous, wrap it with
``sync_tool_executor_adapter(fn)`` which returns an async version.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Sequence


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ToolExecutor = Callable[..., Awaitable[str | dict]]
"""async (tool_name, **kwargs) -> str | dict"""


@dataclass
class PhaseResult:
    """Result of executing one workflow phase."""

    phase_number: int
    phase_name: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)
    parallel: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Low-level parallel dispatcher
# ---------------------------------------------------------------------------

async def fan_out(
    items: Sequence[Any],
    call_fn: Callable[[Any], Awaitable[Any]],
    *,
    max_concurrent: int = 8,
) -> list[Any]:
    """Execute *call_fn* for each item in *items* concurrently.

    Parameters
    ----------
    items : sequence
        The items to iterate over (e.g. a list of block dicts).
    call_fn : async callable
        Called once per item: ``await call_fn(item) -> result``.
    max_concurrent : int
        Maximum number of concurrent tasks (``asyncio.Semaphore`` cap).

    Returns
    -------
    list — one result per item, in the same order as *items*.
    """
    if not items:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _guarded(item: Any) -> Any:
        async with semaphore:
            return await call_fn(item)

    return list(await asyncio.gather(*(_guarded(it) for it in items)))


# ---------------------------------------------------------------------------
# Phase execution
# ---------------------------------------------------------------------------

async def run_phase(
    phase: dict[str, Any],
    tool_executor: ToolExecutor,
    *,
    context: dict[str, Any],
) -> PhaseResult:
    """Execute a single workflow phase.

    If the phase has a ``parallel_dispatch`` specification, all tools in the
    designated group are dispatched concurrently over the fan-out variable
    from *context*.  Otherwise tools are available for sequential calling
    (the LLM decides the call sequence via the outer harness).

    Parameters
    ----------
    phase : dict
        One entry from ``parsed["phases"]``.
    tool_executor : async callable
        ``async (tool_name, **kwargs) -> str | dict``.
    context : dict
        Runtime context (contains the fan-out variable, id_catalog, etc.).

    Returns
    -------
    PhaseResult
    """
    result = PhaseResult(
        phase_number=phase["number"],
        phase_name=phase["name"],
    )

    pd = phase.get("parallel_dispatch")

    if pd is not None:
        # ---- PARALLEL FAN-OUT ----
        result.parallel = True
        tool_group = pd["tool_group"]
        fan_out_var = pd["fan_out_over"]
        max_conc = pd.get("max_concurrent", 8)

        items = context.get(fan_out_var, [])
        if not items:
            result.error = f"fan_out_over='{fan_out_var}' is empty or missing in context"
            return result

        # For each item, call every tool in the designated group
        tools_in_group = phase.get("_resolved_tools", {}).get(tool_group, [])
        if not tools_in_group:
            # Fallback: call tool_group name directly as a single tool
            tools_in_group = [tool_group]

        async def _call_one(item: Any) -> dict[str, Any]:
            """Call all tools in the group for one fan-out item."""
            item_results = {}
            for tool_name in tools_in_group:
                call_record = {"tool": tool_name, "item": item}
                result.tool_calls.append(call_record)
                r = await tool_executor(
                    tool_name,
                    item=item,
                    context=context,
                    phase_guidance=phase.get("guidance", ""),
                )
                item_results[tool_name] = r
            return item_results

        result.results = await fan_out(items, _call_one, max_concurrent=max_conc)
    else:
        # ---- SEQUENTIAL (LLM-driven) ----
        # In sequential mode the runner does not drive tool calls itself.
        # Instead it returns the phase metadata for the outer LLM loop.
        # The LLM decides which tools to call based on the guidance.
        result.results = [{
            "mode": "sequential",
            "available_tool_groups": phase["tools"],
            "guidance": phase.get("guidance", ""),
        }]

    return result


# ---------------------------------------------------------------------------
# Full workflow execution
# ---------------------------------------------------------------------------

async def run_workflow(
    parsed: dict[str, Any],
    tool_executor: ToolExecutor,
    *,
    context: dict[str, Any] | None = None,
) -> list[PhaseResult]:
    """Execute all phases of a parsed workflow sequentially.

    Each phase runs to completion before the next starts.  Within a phase,
    tool calls may be parallel (if ``parallel_dispatch`` is set) or
    sequential.

    Parameters
    ----------
    parsed : dict
        Output of ``parse_workflow()``.
    tool_executor : async callable
        ``async (tool_name, **kwargs) -> str | dict``.
    context : dict, optional
        Initial runtime context.  Gets updated with phase results as the
        workflow progresses.

    Returns
    -------
    list[PhaseResult] — one per phase, in order.
    """
    if context is None:
        context = {}

    phase_results: list[PhaseResult] = []

    for phase in parsed["phases"]:
        # Resolve tool names from tool groups for parallel dispatch
        pd = phase.get("parallel_dispatch")
        if pd is not None:
            group_name = pd["tool_group"]
            tools_def = parsed.get("tools", {}).get(group_name, [])
            phase["_resolved_tools"] = {
                group_name: [t["name"] for t in tools_def]
            }

        pr = await run_phase(phase, tool_executor, context=context)
        phase_results.append(pr)

        # Propagate parallel results into context for subsequent phases
        if pr.parallel and pr.results:
            context[f"phase_{phase['number']}_results"] = pr.results

    return phase_results


# ---------------------------------------------------------------------------
# Adapter for synchronous tool executors
# ---------------------------------------------------------------------------

def sync_tool_executor_adapter(
    fn: Callable[..., str | dict],
) -> ToolExecutor:
    """Wrap a synchronous tool executor into an async one.

    Usage::

        async_exec = sync_tool_executor_adapter(my_sync_function)
        results = await fan_out(items, lambda it: async_exec("tool", item=it))
    """

    async def _async_wrapper(tool_name: str, **kwargs: Any) -> str | dict:
        return fn(tool_name, **kwargs)

    return _async_wrapper
