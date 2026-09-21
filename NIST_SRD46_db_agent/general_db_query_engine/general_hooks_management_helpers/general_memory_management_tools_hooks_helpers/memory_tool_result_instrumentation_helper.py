"""Shared tool-result instrumentation wrapper.
======================================================
Provides ``make_instrumented_wrapper`` — a factory that wraps any tool
callable so that:

1. The result is stored in working memory.
2. The ``record_references`` anchor is fired for entity / DOI tracking.
3. ``str`` results are JSON-parsed when possible so that structured
   data (``id_updates``, ``blocks_found``, compound details, etc.)
   still feeds into the stats recorder.

Both the analysis agent and main agent orchestrators share this
pattern.  Extracting it here avoids drift between the two
implementations and ensures bug-fixes land once.
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Any, Callable

log = logging.getLogger("tool-instrumentation")


def make_instrumented_wrapper(
    name: str,
    fn: Callable,
    *,
    working_mem: Any,
    agent_hooks: Any,
    anchor_fn: Callable,
    mem_anchor_record: Any,
) -> Callable:
    """Return a wrapped version of *fn* that records results.

    Parameters
    ----------
    name : str
        The tool name (used as key in working memory).
    fn : callable
        The original tool function.
    working_mem
        An object with ``record_tool_result(name, result)`` method.
    agent_hooks
        Agent hook collection exposing ``anchors.record_references``
        and ``engine_hooks``.
    anchor_fn : callable
        The ``anchor()`` helper (from ``general_argo_engine_helpers``).
    mem_anchor_record
        The ``SYNC_WORKING_MEMORY_RECORD`` anchor point.
    """

    def wrapper(**kwargs: Any) -> Any:
        result = fn(**kwargs)

        # --- Determine raw_result (dict) and stored_result for memory ---
        raw_dict: dict | None = None

        if hasattr(result, "raw") and isinstance(getattr(result, "raw", None), dict):
            # ToolResult or similar with a .raw dict
            raw_dict = result.raw
            stored_result = anchor_fn(
                mem_anchor_record,
                agent_hooks.engine_hooks,
                tool_name=name,
                content=raw_dict,
            ) or raw_dict

        elif isinstance(result, dict):
            raw_dict = result
            stored_result = anchor_fn(
                mem_anchor_record,
                agent_hooks.engine_hooks,
                tool_name=name,
                content=result,
            ) or result

        elif isinstance(result, str):
            # Try to extract structured data from string results
            # Many tools legitimately return plain strings (e.g. "OK",
            # short status messages). Only attempt JSON parsing when the
            # payload *looks* structured; otherwise treat it as text and
            # skip the noisy traceback.
            stripped = result.lstrip()
            if stripped.startswith(("{", "[")):
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict):
                        raw_dict = parsed
                except (json.JSONDecodeError, ValueError) as exc:
                    log.debug("JSON parse failed for tool '%s' str result: %s", name, exc)

            if raw_dict is not None:
                # JSON parsed OK — pass structured dict (with text fallback)
                content = {**raw_dict, "text": result}
                stored_result = anchor_fn(
                    mem_anchor_record,
                    agent_hooks.engine_hooks,
                    tool_name=name,
                    content=content,
                ) or content
            else:
                stored_result = anchor_fn(
                    mem_anchor_record,
                    agent_hooks.engine_hooks,
                    tool_name=name,
                    content={"text": result},
                ) or {"text": result}

        else:
            stored_result = anchor_fn(
                mem_anchor_record,
                agent_hooks.engine_hooks,
                tool_name=name,
                content={"text": str(result)},
            ) or {"text": str(result)}

        working_mem.record_tool_result(name, stored_result)

        # NOTE: record_references is fired by react_loop.py after tool
        # execution — no need to duplicate it here.

        return result

    wrapper.__name__ = getattr(fn, '__name__', name)
    wrapper.__doc__ = getattr(fn, '__doc__', None)
    try:
        functools.update_wrapper(wrapper, fn)
    except (TypeError, AttributeError):
        pass  # fn is a callable object without standard function attributes
    return wrapper
