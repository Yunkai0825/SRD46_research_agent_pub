"""LC2_3 deterministic dedup engine.

Two structurally distinct halves around the LLM dedup pathways:

* :mod:`.group_dispatch`  — *pre-LLM*: split groups + build payloads.
* :mod:`.decision_apply`  — *post-LLM*: parse decisions + edit the card.
"""

from __future__ import annotations

from .group_dispatch import group_to_payload, split_groups
from .decision_apply import (
    GroupDecision,
    apply_decisions_to_card,
    compute_drop_keys,
    decisions_from_dicts,
)

__all__ = [
    "split_groups",
    "group_to_payload",
    "GroupDecision",
    "decisions_from_dicts",
    "compute_drop_keys",
    "apply_decisions_to_card",
]
