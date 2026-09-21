"""
CompactorEntry + CompactorCatalog — structured registry for tool compactors.
============================================================================

Analogous to ``ToolEntry`` / ``AgentToolCatalog`` for tool functions, this
module provides a structured way to register and look up the hardcoded
dict→markdown compactor functions used in the Layer 1 compaction stage.

Decorators
----------
``compacts(*tool_names)``
    Tag a compactor function with the tool names it is designed for.
``uses_compactors(*compactor_fns)``
    Tag a tool function with the compactor functions it can use.

Both decorators simply set a private attribute on the function object
(``_compacts_tools`` and ``_compactor_fns`` respectively).  The catalog
and ``ToolEntry`` read these attributes for auto-wiring.

Usage::

    @compacts("resolve_compounds")
    def compact_resolve_compounds(data: dict) -> str: ...

    @uses_compactors(compact_resolve_compounds)
    def resolve_compounds(names: str) -> dict: ...

    catalog = CompactorCatalog.from_functions([compact_resolve_compounds, ...])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

log = logging.getLogger("compactor-catalog")


# ═══════════════════════════════════════════════════════════════
#  Decorators — tag compactors & tools with their relationships
# ═══════════════════════════════════════════════════════════════

def compacts(*tool_names: str):
    """Decorator: tag a compactor function with the tool names it serves.

    Sets ``fn._compacts_tools = tool_names`` on the decorated function.
    ``CompactorCatalog.from_functions()`` reads this attribute to
    auto-build the registry.

    Example::

        @compacts("resolve_compounds")
        def compact_resolve_compounds(data: dict) -> str: ...
    """
    def _decorator(fn: Callable) -> Callable:
        fn._compacts_tools = tool_names
        return fn
    return _decorator


def uses_compactors(*compactor_fns: Callable):
    """Decorator: tag a tool function with the compactors it can use.

    Sets ``fn._compactor_fns = compactor_fns`` on the decorated function.
    ``ToolEntry.__post_init__`` reads this attribute to auto-resolve
    ``compactor_fn`` when not explicitly provided.

    Example::

        @uses_compactors(compact_resolve_compounds)
        def resolve_compounds(names: str) -> dict: ...
    """
    def _decorator(fn: Callable) -> Callable:
        fn._compactor_fns = compactor_fns
        return fn
    return _decorator


# ═══════════════════════════════════════════════════════════════
#  CompactorEntry — one tool-name → compactor-function mapping
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CompactorEntry:
    """One compactor registration: maps a tool name to its compactor function."""

    tool_name: str
    """Canonical tool name (the key used in the compactor registry)."""

    compactor_fn: Callable
    """Hardcoded dict→markdown compactor: ``(raw_dict) → str``."""


# ═══════════════════════════════════════════════════════════════
#  CompactorCatalog — structured registry of tool compactors
# ═══════════════════════════════════════════════════════════════

class CompactorCatalog:
    """Structured registry of tool compactors.

    Collects ``CompactorEntry`` objects and provides:

    - ``registry`` — a plain dict ``{tool_name: compactor_fn}`` suitable
      for passing to ``ToolResultCompactor(compactor_registry=...)``.
    - ``compact(tool_name, data)`` — direct lookup + call.
    - ``register`` / ``register_many`` — entry management.
    - ``from_functions()`` — build from tagged compactor functions.
    """

    def __init__(self, entries: Optional[Iterable[CompactorEntry]] = None) -> None:
        self._entries: Dict[str, CompactorEntry] = {}
        if entries:
            self.register_many(entries)

    # ── Entry management ────────────────────────────────────

    def register(self, entry: CompactorEntry) -> None:
        self._entries[entry.tool_name] = entry

    def register_many(self, entries: Iterable[CompactorEntry]) -> None:
        for e in entries:
            self._entries[e.tool_name] = e

    # ── Read accessors ──────────────────────────────────────

    @property
    def entries(self) -> Dict[str, CompactorEntry]:
        return dict(self._entries)

    @property
    def registry(self) -> Dict[str, Callable]:
        """Plain dict ``{tool_name: compactor_fn}`` — for ToolResultCompactor."""
        return {e.tool_name: e.compactor_fn for e in self._entries.values()}

    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    # ── Direct compaction ───────────────────────────────────

    def compact(self, tool_name: str, data: dict) -> str:
        """Look up the compactor for *tool_name* and return markdown."""
        entry = self._entries.get(tool_name)
        if entry is None:
            raise KeyError(f"No compactor registered for tool {tool_name!r}")
        return entry.compactor_fn(data)

    # ── Auto-build from tagged functions ────────────────────

    @classmethod
    def from_functions(cls, fns: Iterable[Callable]) -> "CompactorCatalog":
        """Build a catalog by reading ``_compacts_tools`` from each function.

        Each function must have been decorated with ``@compacts(...)`` (or
        have ``_compacts_tools`` set manually).  Functions without the
        attribute are silently skipped.

        Example::

            catalog = CompactorCatalog.from_functions([
                compact_resolve_compounds,
                compact_resolve_properties,
                ...
            ])
        """
        entries: list[CompactorEntry] = []
        for fn in fns:
            tool_names = getattr(fn, "_compacts_tools", ())
            for tool_name in tool_names:
                entries.append(CompactorEntry(tool_name, fn))
        return cls(entries)
