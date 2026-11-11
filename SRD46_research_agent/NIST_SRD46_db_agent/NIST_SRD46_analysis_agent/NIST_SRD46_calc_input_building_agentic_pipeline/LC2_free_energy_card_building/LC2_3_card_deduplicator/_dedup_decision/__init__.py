"""LC2_3 dedup-plan sources.

``load_general_plan`` supplies the static worker defaults
(``dedup_general_plan.md``).  All calculation-aware refinement is authored by
the element supervisor (case-specific recommendations committed through its
gate tool and appended to worker system prompts).  The purpose-only addendum
agent (:func:`build_dedup_plan`) is RETIRED from the live flow — it saw
neither the inventory nor the design questions; its export remains importable
for archival tooling only.
"""

from __future__ import annotations

from .dedup_decision_agent import (
    GENERAL_PLAN_PATH,
    build_dedup_plan,
    load_general_plan,
)

__all__ = ["build_dedup_plan", "load_general_plan", "GENERAL_PLAN_PATH"]
