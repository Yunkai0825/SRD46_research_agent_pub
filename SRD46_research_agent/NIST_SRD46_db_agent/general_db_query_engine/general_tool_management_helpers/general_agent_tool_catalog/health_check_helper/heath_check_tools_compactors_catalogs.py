"""
Catalog health check — pre-flight validation for tool + compactor catalogs.
===========================================================================

Validates that every tool reaching an agent is registered in the tool
catalog, every non-skipped tool has a compactor, and every compactor maps
back to a real tool.  Designed to run **once** at agent startup, before
the first ``agent_turn()`` call.

``actual_tools`` is **required** — the health check automatically detects
any tool that would reach ``agent_turn()`` but is missing from the
catalog, and any catalog entry that is not wired into the actual tools
dict.  On any mismatch the check raises ``CatalogHealthCheckError``
immediately with a detailed diagnostic listing every unregistered tool.

Public API
----------
run_health_check(catalog, *, actual_tools, compactor_catalog, label) -> None
    Raises ``CatalogHealthCheckError`` on any mismatch.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

from ..agent_tool_catalog import AgentToolCatalog
from ..agent_tool_compactor_hooks_catalog import CompactorCatalog

log = logging.getLogger("catalog-health-check")


class CatalogHealthCheckError(RuntimeError):
    """Raised when one or more health-check rules fail."""


def run_health_check(
    catalog: AgentToolCatalog,
    *,
    actual_tools: Dict[str, Callable],
    compactor_catalog: Optional[CompactorCatalog] = None,
    label: str = "agent",
) -> None:
    """Validate tool-catalog / compactor-catalog consistency.

    Parameters
    ----------
    catalog : AgentToolCatalog
        The class-based tool catalog for the agent layer.
    actual_tools : dict
        The final ``{name: callable}`` dict that will be passed to
        ``agent_turn()``.  **Required.**  Every key must be present
        in *catalog*, and every catalog entry must appear here.
    compactor_catalog : CompactorCatalog, optional
        Explicit compactor catalog.  When *None*, falls back to
        ``catalog._compactor_catalog`` (set at construction).
    label : str
        Human-readable label for log messages (e.g. ``"analysis-L0"``).

    Raises
    ------
    CatalogHealthCheckError
        Contains a multi-line summary of every failing rule.
    """

    errors: list[str] = []
    entries = catalog.entries  # shallow copy {name: ToolEntry}

    # ── Rule 1: Compactor coverage ─────────────────────────────
    # Every entry with skip_compactor=False MUST have compactor_fn.
    for name, entry in entries.items():
        if not entry.skip_compactor and entry.compactor_fn is None:
            errors.append(
                f"[MISSING_COMPACTOR] Tool {name!r} (group={entry.group!r}) "
                f"has skip_compactor=False but compactor_fn is None"
            )

    # ── Rule 2: Compactor-catalog consistency ──────────────────
    cc = compactor_catalog or getattr(catalog, "_compactor_catalog", None)
    if cc is not None:
        cc_registry = cc.registry  # {tool_name: compactor_fn}

        # 2a  Every compacted tool must appear in the compactor catalog
        for name, entry in entries.items():
            if entry.compactor_fn is not None and not entry.skip_compactor:
                if name not in cc_registry:
                    errors.append(
                        f"[COMPACTOR_NOT_IN_CATALOG] Tool {name!r} has a "
                        f"compactor_fn but no matching CompactorCatalog entry"
                    )
                elif cc_registry[name] is not entry.compactor_fn:
                    errors.append(
                        f"[COMPACTOR_MISMATCH] Tool {name!r}: ToolEntry.compactor_fn "
                        f"differs from the function in CompactorCatalog"
                    )

        # 2b  Compactor catalog entries should map back to a tool or extra
        extra_compactors = getattr(catalog, "_extra_compactors", {})
        for tool_name in cc_registry:
            if tool_name not in entries and tool_name not in extra_compactors:
                errors.append(
                    f"[ORPHAN_COMPACTOR] CompactorCatalog has {tool_name!r} "
                    f"but no matching ToolEntry or extra_compactor"
                )

    # ── Rule 3: Unregistered-tool detection (bidirectional) ────
    # 3a  Every tool in the dict passed to agent_turn() must be
    #     registered in the catalog.
    unregistered = sorted(set(actual_tools) - set(entries))
    for name in unregistered:
        errors.append(
            f"[UNREGISTERED_TOOL] Tool {name!r} will reach agent_turn() "
            f"but is NOT registered in the catalog.  "
            f"Fix: add a ToolEntry for {name!r} via catalog.register()."
        )

    # 3b  Every catalog entry should be wired into the actual tools
    #     dict (catches tools registered but accidentally omitted
    #     from the dict passed to agent_turn).
    unwired = sorted(set(entries) - set(actual_tools))
    for name in unwired:
        errors.append(
            f"[UNWIRED_TOOL] Tool {name!r} is registered in the catalog "
            f"but missing from the actual_tools dict.  "
            f"It will never be callable by the agent."
        )

    # ── Verdict ────────────────────────────────────────────────
    if errors:
        header = (
            f"Health check FAILED [{label}] — {len(errors)} error(s):"
        )
        detail = "\n  ".join([""] + errors)
        msg = header + detail
        log.error(msg)
        raise CatalogHealthCheckError(msg)

    n_total = len(entries)
    n_compacted = sum(
        1 for e in entries.values()
        if e.compactor_fn and not e.skip_compactor
    )
    n_skip = sum(1 for e in entries.values() if e.skip_compactor)
    log.info(
        "Health check PASSED [%s]: %d tools (%d compacted, %d skip)",
        label, n_total, n_compacted, n_skip,
    )


__all__ = ["run_health_check", "CatalogHealthCheckError"]
