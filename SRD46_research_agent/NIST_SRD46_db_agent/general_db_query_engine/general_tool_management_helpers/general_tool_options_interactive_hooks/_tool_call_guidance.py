"""
Tool-call guidance — generic pre-execution hook for tool-menu calls.
=====================================================================
Two-tier validation that any agent can reuse:

1. **Tool name** — catches typos / hallucinated names and suggests
   close matches via ``difflib.get_close_matches``.
2. **Inner kwargs** — parses ``kwargs_json``, inspects the real
   function signature, and blocks on unknown or missing parameters
   before execution.

Agents subclass :class:`ToolCallGuidance` and supply a
``registry_provider`` callback that returns their
:class:`ToolMenuRegistry` instance.  The subclass is then bound to
``SYNC_TOOL_GUIDANCE_CHECK`` in the agent's hook catalog.

Example (main agent)::

    from ....general_tool_management_helpers.general_tool_options_interactive_hooks import (
        ToolCallGuidance,
    )

    class MenuToolGuidance(ToolCallGuidance):
        def __init__(self) -> None:
            super().__init__(registry_provider=_get_registry)

    menu_tool_pre_execution_guidance = MenuToolGuidance()
"""

from __future__ import annotations

import difflib
import inspect
import json
import logging
from typing import TYPE_CHECKING, Callable

from ._pre_execution_guidance import PreExecutionGuidance

if TYPE_CHECKING:
    from ..general_tool_menu_tools.tool_menu_registry import ToolMenuRegistry

_log = logging.getLogger(__name__)

_P = inspect.Parameter


class ToolCallGuidance(PreExecutionGuidance):
    """Generic two-tier validation for ``run_subagent_tool`` calls.

    Tier 1 — tool name:
      - Valid name  → fall through to tier 2.
      - Invalid name with close matches → block with suggestions.
      - Invalid name, no matches → block with browse reminder.

    Tier 2 — inner kwargs (``kwargs_json``):
      - Inspects the actual function signature.
      - Blocks on unknown keyword arguments or missing required params.
      - Shows the full signature so the agent can self-correct in one turn.
      - Graceful fallback: if JSON parse / signature inspection fails,
        proceeds without blocking (lets the tool handle the error).

    Parameters
    ----------
    registry_provider : Callable[[], ToolMenuRegistry]
        Lazy callback that returns the agent's tool menu registry.
        Called on every validation (not cached) so the registry can be
        built/rebuilt independently.
    target_tools : tuple[str, ...]
        Outer tool names this hook handles.  Defaults to
        ``("run_subagent_tool",)``.
    """

    def __init__(
        self,
        registry_provider: Callable[[], ToolMenuRegistry],
        *,
        target_tools: tuple[str, ...] = ("run_subagent_tool",),
    ) -> None:
        super().__init__(
            required_params=[],
            context_params=[],
            target_tools=target_tools,
        )
        self._registry_provider = registry_provider

    # ── Main entry point ─────────────────────────────────────

    def __call__(self, *, tool_name: str, call_kwargs: dict, **_kw) -> str | None:
        if tool_name not in self.target_tools:
            return None

        inner_name = call_kwargs.get("tool_name", "")
        if not inner_name:
            return "**BLOCKED — `tool_name` is empty.** Specify the exact tool name."

        reg = self._registry_provider()

        # ── Tier 1: tool name validation ─────────────────────
        if reg.has_tool(inner_name):
            return self._check_inner_kwargs(inner_name, call_kwargs, reg)

        all_names = sorted(reg._tools)
        close = difflib.get_close_matches(inner_name, all_names, n=2, cutoff=0.4)

        if close:
            suggestions = "\n".join(
                f"  - `{c}` — {reg._tools[c].one_liner()}" for c in close
            )
            return (
                f"**BLOCKED — unknown tool `{inner_name}`.**\n"
                f"Did you mean:\n{suggestions}\n\n"
                f"Schema: `run_subagent_tool(tool_name=<name>, kwargs_json=<json>)`"
            )

        return (
            f"**BLOCKED — unknown tool `{inner_name}` (no close matches).**\n"
            f"Call `browse_subagent_tools` to discover available tools."
        )

    # ── Tier 2: inner kwargs validation ──────────────────────

    @staticmethod
    def _check_inner_kwargs(
        inner_name: str,
        call_kwargs: dict,
        reg: ToolMenuRegistry,
    ) -> str:
        """Validate kwargs_json against the real function signature.

        Returns ``""`` to proceed, or a non-empty blocking message.
        On any introspection failure, returns ``""`` (graceful fallback).
        """
        raw_json = call_kwargs.get("kwargs_json", "{}")
        try:
            inner_kwargs = json.loads(raw_json) if raw_json else {}
        except (json.JSONDecodeError, TypeError):
            return ""  # let run_subagent_tool surface the JSON error

        if not isinstance(inner_kwargs, dict):
            return ""  # non-dict payload — let execution handle it

        entry = reg._tools.get(inner_name)
        if entry is None or entry.fn is None:
            return ""

        try:
            sig = inspect.signature(entry.fn)
        except (ValueError, TypeError):
            return ""

        # Classify parameters
        has_var_keyword = False
        valid_names: set[str] = set()
        required_names: list[str] = []

        for name, param in sig.parameters.items():
            if param.kind == _P.VAR_KEYWORD:
                has_var_keyword = True
                continue
            if param.kind == _P.VAR_POSITIONAL:
                continue
            valid_names.add(name)
            if param.default is _P.empty:
                required_names.append(name)

        # Check for unknown kwargs
        unknown = sorted(set(inner_kwargs) - valid_names) if not has_var_keyword else []
        # Check for missing required params
        missing = [n for n in required_names if n not in inner_kwargs]

        if not unknown and not missing:
            return ""

        sig_str = f"`{inner_name}{sig}`"
        parts: list[str] = []
        if unknown:
            parts.append(f"unknown arg(s) `{'`, `'.join(unknown)}`")
        if missing:
            parts.append(f"missing required arg(s) `{'`, `'.join(missing)}`")

        return (
            f"**BLOCKED — {'; '.join(parts)}.**\n"
            f"Signature: {sig_str}"
        )
