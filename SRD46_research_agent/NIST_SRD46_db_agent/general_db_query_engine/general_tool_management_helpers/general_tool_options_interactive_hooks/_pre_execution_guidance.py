"""
Pre-execution guidance — base framework.
=========================================
A ``PreExecutionGuidance`` subclass is **bound to** the
``SYNC_TOOL_GUIDANCE_CHECK`` anchor via ``bind_hook`` in the agent's
hook catalog.  The engine fires the anchor once per tool call in a
batch, passing ``tool_name`` and a **mutable** ``call_kwargs`` dict.

The hook either:

- **hard-parses** missing params in-place → returns ``""``  (proceed)
- **blocks** execution → returns a non-empty guidance string
- **declines** (wrong tool) → returns ``None``

This module provides:

1. :class:`PreExecutionGuidance` — a dataclass base that each agent's
   hook subclasses.  Override :meth:`check_and_fill` with domain-specific
   logic (column detection, constraint selection, etc.).
2. :func:`block_msg` — a reusable formatter for "BLOCKED" messages that
   shows available columns and partial auto-fill progress.

Architecture note
-----------------
Follows the same general/specific split as ``InteractiveCompactor``
(``general_context_hooks`` → ``interactive_hooks/``) and
``ToolResultCompactor`` (``general_tool_results_compactor_agentic_hooks``
→ ``compactor_hooks/``).

The only interface between a guidance hook and the rest of the engine
is the ``SYNC_TOOL_GUIDANCE_CHECK`` anchor.  There is **no** direct
function call from ``validate_batch`` to the hook; the anchor dispatch
handles routing.

Usage::

    # In agent_context_hooks/interactive_hooks/fitting_variable_guidance.py
    from ....general_tool_management_helpers.general_tool_options_interactive_hooks import (
        PreExecutionGuidance,
        block_msg,
    )

    class FittingVariableGuidance(PreExecutionGuidance):
        def check_and_fill(self, call_kwargs: dict) -> str | None:
            ...   # domain-specific auto-detection

    fitting_guidance = FittingVariableGuidance(
        required_params=["x_vars", "y_props", "x_vars_constrained"],
        target_tools=("fit_block",),
    )
    # Bind in hook_catalog:
    #   bind_hook(fitting_guidance, SYNC_TOOL_GUIDANCE_CHECK.anchor_type)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Sequence

_log = logging.getLogger(__name__)


# ------------------------------------------------------------------
#  Base dataclass
# ------------------------------------------------------------------

@dataclass
class PreExecutionGuidance:
    """Pre-execution guidance hook — subclass per agent/domain.

    Subclass in ``<agent>_context_hooks/interactive_hooks/`` and
    override :meth:`check_and_fill` with domain logic.

    The instance is **callable** and is bound to the
    ``SYNC_TOOL_GUIDANCE_CHECK`` anchor via ``bind_hook``.
    The engine fires it with ``tool_name`` and ``call_kwargs``
    keyword arguments.

    Parameters
    ----------
    required_params : list[str]
        Param names that must be present and non-empty for the tool to
        proceed.  If all are already supplied, ``check_and_fill`` is
        still called (it can short-circuit via :meth:`all_present`).
    context_params : list[str]
        Param names needed to fetch context for auto-detection
        (e.g. ``["doi", "block_number"]``).  The base ``__call__``
        checks these before delegating to ``check_and_fill``.
    target_tools : tuple[str, ...]
        Tool names this guidance hook handles.  If a tool call's
        ``tool_name`` is not in this set, ``__call__`` returns
        ``None`` (= "I don't handle this tool").
    """

    required_params: list[str] = field(default_factory=list)
    context_params: list[str] = field(default_factory=list)
    target_tools: tuple[str, ...] = ()

    # ── Protocol: callable via SYNC_TOOL_GUIDANCE_CHECK anchor ──

    def __call__(self, *, tool_name: str, call_kwargs: dict, **_kw) -> str | None:
        """Entry point fired by the ``SYNC_TOOL_GUIDANCE_CHECK`` anchor.

        Returns
        -------
        None
            This hook does not handle *tool_name* — anchor keeps looking.
        ``""``  (empty string)
            Handled successfully; params are valid or were auto-filled.
        non-empty str
            Guidance/block message — the batch is blocked.
        """
        if tool_name not in self.target_tools:
            return None

        if self.all_present(call_kwargs):
            return ""

        missing_ctx = [
            p for p in self.context_params
            if not call_kwargs.get(p, "")
        ]
        if missing_ctx:
            missing_req = [
                p for p in self.required_params
                if not call_kwargs.get(p, "")
            ]
            return (
                f"**BLOCKED — missing `{'`/`'.join(missing_req)}` "
                f"and no `{'`+`'.join(missing_ctx)}` to auto-detect them.**"
            )

        result = self.check_and_fill(call_kwargs)
        return result if result else ""

    # ── Override in subclass ─────────────────────────────────

    def check_and_fill(self, call_kwargs: dict) -> str | None:
        """Domain-specific auto-detection and param filling.

        Override in subclass.  The base implementation is a no-op
        that always proceeds.

        Parameters
        ----------
        call_kwargs : dict  (mutable — modify in-place to auto-fill)

        Returns
        -------
        str or None
            ``None`` → all params resolved, proceed with execution.
            str → guidance text, block execution.
        """
        return None

    # ── Helpers ──────────────────────────────────────────────

    def all_present(self, call_kwargs: dict) -> bool:
        """Return True when all *required_params* are non-empty."""
        return all(call_kwargs.get(p, "") for p in self.required_params)


# ------------------------------------------------------------------
#  Reusable block message formatter
# ------------------------------------------------------------------

def block_msg(
    param_name: str,
    columns: Sequence[str],
    identified_x: Sequence[str] | None = None,
    identified_y: Sequence[str] | None = None,
    reason: str = "",
    *,
    filled: list[str] | None = None,
) -> str:
    """Build a short guidance message when auto-detection fails for one param.

    Shows available columns and any params that were already auto-filled
    before this failure, so the agent has full context.

    Parameters
    ----------
    param_name : str
        The parameter that could not be resolved.
    columns : sequence of str
        Available column names in the block.
    identified_x, identified_y : sequence of str or None
        Column identification results (for diagnostics).
    reason : str
        Short explanation of why auto-detection failed.
    filled : list[str] or None
        Params already auto-filled earlier in the same pass.
    """
    cols_str = ", ".join(columns[:12])
    if len(columns) > 12:
        cols_str += f" (+{len(columns) - 12} more)"
    parts = [
        f"**BLOCKED \u2014 cannot auto-detect `{param_name}`: {reason}**",
        f"Available columns: [{cols_str}]",
    ]
    if identified_x is not None or identified_y is not None:
        parts.append(
            f"Identified x: {list(identified_x or [])}, "
            f"y: {list(identified_y or [])}"
        )
    if filled:
        parts.append(f"(already auto-filled: {', '.join(filled)})")
    return "\n".join(parts)
