"""Shared rule registry and stable manual-fix ledger identifiers."""
from __future__ import annotations

from typing import Dict
from dataclasses import dataclass


LEDGER_SOURCE_PREFIX = "manual_rules."


def ledger_source(rule_id: str, detail: str = "") -> str:
    """``source`` string written to manual_fix_log for an application of ``rule_id``."""
    return f"{LEDGER_SOURCE_PREFIX}{rule_id}" + (f":{detail}" if detail else "")


# =============================================================================
# 0. Rule registry
# =============================================================================
@dataclass(frozen=True)
class Rule:
    id: str
    stage: str        # pipeline stage that applies the rule
    table: str        # staging table whose rows it touches
    summary: str
    why: str


RULES: Dict[str, Rule] = {}


def _declare(rule: Rule) -> Rule:
    if rule.id in RULES:
        raise ValueError(f"duplicate manual rule id {rule.id}")
    RULES[rule.id] = rule
    return rule


__all__ = [
    'LEDGER_SOURCE_PREFIX',
    'ledger_source',
    'Rule',
    'RULES',
]
