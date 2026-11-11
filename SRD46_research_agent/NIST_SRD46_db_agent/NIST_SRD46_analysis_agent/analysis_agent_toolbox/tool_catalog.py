"""
Tool catalogs for the analysis agent.
=====================================

Three catalog instances, one per LLM tier. Each exposes the
deterministic ``calc_wrappers`` as ``ToolEntry`` objects with the
mandatory ``purpose``+``tasks`` contract enforced by the wrappers
themselves.

These catalogs are *only* exercised when an LLM-driven L0/L1/L2 is
plugged in. The default deterministic implementation calls the
wrappers directly. They are exported here so that the future LLM
swap-in only needs to wire ``L0_CATALOG`` / ``L1_*_CATALOG`` /
``L2_*_CATALOG`` into ``agent_turn`` from the shared engine.
"""

from __future__ import annotations

from . import calc_wrappers as _cw

# Try to import the engine's catalog primitives. The engine is an
# optional dependency for the *deterministic* path, so degrade
# gracefully if it isn't available.
try:
    from ...general_db_query_engine.general_tool_management_helpers.general_agent_tool_catalog import (
        AgentToolCatalog, ToolEntry,
    )
    _ENGINE_AVAILABLE = True
except Exception:                                   # pragma: no cover
    AgentToolCatalog = object                       # type: ignore
    ToolEntry = None                                # type: ignore
    _ENGINE_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════
#  L0 catalog — chemistry brain. Read-only inspection only.
# ════════════════════════════════════════════════════════════════════

class AnalysisL0Catalog(AgentToolCatalog):
    """L0 sees only inspect_card-style read-only helpers + memory R/W.

    L0 has NO calc-authoring tools — that's the design contract: numbers
    come from raw DB / wrappers, not from L0's pen.
    """
    pipeline_label = "srd46-analysis-l0"

    def __init__(self) -> None:
        if not _ENGINE_AVAILABLE:
            return
        super().__init__()
        self.register_many([
            ToolEntry("parse_card",        _cw.wrap_parse_card,
                      group="card_inspect", skip_subagent=True),
            ToolEntry("find_existing_cards", _cw.find_existing_cards,
                      group="card_inspect", skip_subagent=True),
            ToolEntry("extract_topology",  _cw.wrap_extract_topology,
                      group="grid_inspect", skip_subagent=True),
        ])


# ════════════════════════════════════════════════════════════════════
#  L1 catalogs — one per phase
# ════════════════════════════════════════════════════════════════════

class AnalysisL1CardAssemblerCatalog(AgentToolCatalog):
    """S2 worker's tool catalog."""
    pipeline_label = "srd46-analysis-l1-cards"

    def __init__(self) -> None:
        if not _ENGINE_AVAILABLE:
            return
        super().__init__()
        self.register_many([
            ToolEntry("find_existing_cards",      _cw.find_existing_cards,
                      group="probe", skip_subagent=True),
            ToolEntry("build_or_load_ref_card",   _cw.wrap_build_or_load_ref_card,
                      group="build", skip_subagent=True),
            ToolEntry("merge_ref_cards",          _cw.wrap_merge_ref_cards,
                      group="merge", skip_subagent=True),
            ToolEntry("enrich_card",              _cw.wrap_enrich_card,
                      group="enrich", skip_subagent=True),
            ToolEntry("parse_card",               _cw.wrap_parse_card,
                      group="inspect", skip_subagent=True),
        ])


class AnalysisL1ConstraintBuilderCatalog(AgentToolCatalog):
    """S4 worker's tool catalog."""
    pipeline_label = "srd46-analysis-l1-constraints"

    def __init__(self) -> None:
        if not _ENGINE_AVAILABLE:
            return
        super().__init__()
        self.register_many([
            ToolEntry("validate_calc_input", _cw.wrap_validate_calc_input,
                      group="validate", skip_subagent=True),
            ToolEntry("parse_card",          _cw.wrap_parse_card,
                      group="inspect", skip_subagent=True),
        ])


class AnalysisL1CalcRunnerCatalog(AgentToolCatalog):
    """S6 worker's tool catalog."""
    pipeline_label = "srd46-analysis-l1-calc"

    def __init__(self) -> None:
        if not _ENGINE_AVAILABLE:
            return
        super().__init__()
        self.register_many([
            ToolEntry("run_calculation", _cw.wrap_run_calculation,
                      group="run", skip_subagent=True),
            ToolEntry("extract_topology", _cw.wrap_extract_topology,
                      group="post", skip_subagent=True),
        ])


# ════════════════════════════════════════════════════════════════════
#  L2 catalogs (read-only inspectors).
# ════════════════════════════════════════════════════════════════════

class AnalysisL2InspectorCatalog(AgentToolCatalog):
    """Shared L2 monitor catalog (all monitors are read-only)."""
    pipeline_label = "srd46-analysis-l2"

    def __init__(self) -> None:
        if not _ENGINE_AVAILABLE:
            return
        super().__init__()
        self.register_many([
            ToolEntry("parse_card",       _cw.wrap_parse_card,
                      group="inspect", skip_subagent=True),
            ToolEntry("extract_topology", _cw.wrap_extract_topology,
                      group="inspect", skip_subagent=True),
        ])


# ── Singletons ──────────────────────────────────────────────────────

L0_CATALOG                     = AnalysisL0Catalog()                if _ENGINE_AVAILABLE else None
L1_CARD_ASSEMBLER_CATALOG      = AnalysisL1CardAssemblerCatalog()   if _ENGINE_AVAILABLE else None
L1_CONSTRAINT_BUILDER_CATALOG  = AnalysisL1ConstraintBuilderCatalog() if _ENGINE_AVAILABLE else None
L1_CALC_RUNNER_CATALOG         = AnalysisL1CalcRunnerCatalog()      if _ENGINE_AVAILABLE else None
L2_INSPECTOR_CATALOG           = AnalysisL2InspectorCatalog()       if _ENGINE_AVAILABLE else None


__all__ = [
    "AnalysisL0Catalog",
    "AnalysisL1CardAssemblerCatalog",
    "AnalysisL1ConstraintBuilderCatalog",
    "AnalysisL1CalcRunnerCatalog",
    "AnalysisL2InspectorCatalog",
    "L0_CATALOG",
    "L1_CARD_ASSEMBLER_CATALOG",
    "L1_CONSTRAINT_BUILDER_CATALOG",
    "L1_CALC_RUNNER_CATALOG",
    "L2_INSPECTOR_CATALOG",
]
