"""
ToolEntry — frozen dataclass describing one tool in an agent catalog.
=====================================================================

Each entry pairs a callable with its compaction metadata:

- **compactor_fn** — hardcoded dict→markdown formatter (Layer 1 / full).
- **condense_fn** — lighter compactor: strips data tables (Layer 1 / condense).
- **ultra_condense_fn** — one-liner summaries (Layer 1 / ultra-condense).
- **skip_compactor** — bypass Layer 1 (JSON fallback instead).
- **skip_subagent** — bypass Layer 2 (no KEEP/DISCARD subagent).

When both ``skip_compactor`` and ``skip_subagent`` are True the tool
is passed through as-is (useful for L2 dispatchers that already return
strings, or memory tools that need no compaction).

Condensation levels
-------------------
Some tools (e.g. ``search_blocks``, ``search_system_registry``) produce
large markdown that can be condensed in two additional tiers:

- **condense** — L1 condense: metadata kept, data-table rows stripped.
- **ultra_condense** — L2 ultra-condense: header + one-liner per block.

When ``condense_fn`` or ``ultra_condense_fn`` are set, the catalog's
size-adaptive compaction can escalate automatically (full → condense →
ultra-condense) when the output exceeds configurable character limits.
Tools that already handle this internally (via ``_apply_block_condensation``)
should set ``adaptive_condense = True`` so the catalog knows not to
double-apply condensation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ToolEntry:
    """One tool in an agent's catalog."""

    name: str
    """Canonical tool name (the key in the agent's tool dict)."""

    fn: Callable
    """The underlying callable."""

    group: str = ""
    """Logical group: id_resolution, block_search, L2_subagent, memory, fitting, …"""

    compactor_fn: Optional[Callable] = None
    """Layer 1 compactor (full): ``(raw_dict) → markdown_str``.
    ``None`` means the JSON fallback will be used (unless *skip_compactor*)."""

    condense_fn: Optional[Callable] = None
    """Layer 1 condense: ``(raw_dict) → markdown_str``.
    Lighter than full — strips data tables, keeps metadata.
    ``None`` means condense tier is unavailable."""

    ultra_condense_fn: Optional[Callable] = None
    """Layer 1 ultra-condense: ``(raw_dict) → markdown_str``.
    One-liner summaries per result.  ``None`` means unavailable."""

    adaptive_condense: bool = False
    """If True, the compactor_fn itself already handles size-adaptive
    condensation internally (e.g. via ``_apply_block_condensation``).
    The catalog will not try to re-apply condense/ultra_condense on
    top of the compactor output."""

    skip_compactor: bool = False
    """If True, Layer 1 (hardcoded dict→md) is bypassed entirely."""

    skip_subagent: bool = False
    """If True, Layer 2 (KEEP/DISCARD LLM subagent) is bypassed."""

    guidance_fn: Optional[Callable] = None
    """**Deprecated direct-call field** — kept for backward compatibility.

    Previously called directly by ``validate_batch()``.  Now guidance
    hooks are dispatched through the ``SYNC_TOOL_GUIDANCE_CHECK`` anchor
    via ``bind_hook()`` in the agent's ``hook_catalog.py``.

    New guidance hooks should subclass ``PreExecutionGuidance``, set
    ``target_tools``, and be bound to ``SYNC_TOOL_GUIDANCE_CHECK`` —
    NOT registered here.  This field is no longer read by
    ``validate_batch()``.
    """

    description: str = ""
    """One-line purpose.  Auto-derived from ``fn.__doc__`` if empty."""

    @property
    def has_condense(self) -> bool:
        """True if any condensation tier is available."""
        return self.adaptive_condense or self.condense_fn is not None

    @property
    def condensation_levels(self) -> list[str]:
        """List of available condensation level names."""
        levels = ["full"]
        if self.condense_fn:
            levels.append("condense")
        if self.ultra_condense_fn:
            levels.append("ultra_condense")
        if self.adaptive_condense:
            levels.append("adaptive")
        return levels

    @property
    def available_compactors(self) -> tuple:
        """All compactor functions this tool can use.

        Reads ``fn._compactor_fns`` (set by ``@uses_compactors``
        decorator or by ``__post_init__`` auto-tagging).
        Falls back to ``(compactor_fn,)`` if the attribute is absent.
        """
        fns = getattr(self.fn, "_compactor_fns", None)
        if fns:
            return tuple(fns)
        if self.compactor_fn is not None:
            return (self.compactor_fn,)
        return ()

    def __post_init__(self) -> None:
        # Auto-resolve compactor_fn from fn._compactor_fns if not explicit
        if self.compactor_fn is None and not self.skip_compactor:
            fn_compactors = getattr(self.fn, "_compactor_fns", None)
            if fn_compactors:
                object.__setattr__(self, "compactor_fn", fn_compactors[0])

        # Auto-tag fn with _compactor_fns from compactor_fn if not already set
        if self.compactor_fn is not None and not getattr(self.fn, "_compactor_fns", None):
            try:
                self.fn._compactor_fns = (self.compactor_fn,)
            except AttributeError as exc:
                logging.getLogger("agent-tool-entry").debug(
                    "Callable %r cannot be annotated with _compactor_fns: %s",
                    self.fn,
                    exc,
                )

        if not self.description and self.fn and getattr(self.fn, "__doc__", None):
            object.__setattr__(
                self, "description",
                self.fn.__doc__.strip().split("\n")[0],
            )
