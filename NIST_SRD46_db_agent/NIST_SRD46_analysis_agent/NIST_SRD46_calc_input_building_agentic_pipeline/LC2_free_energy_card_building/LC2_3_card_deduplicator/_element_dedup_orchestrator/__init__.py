"""LC2_3 element-level dedup instruction and review orchestration.

LC2_2 remains deterministic and persists the immutable element inventory;
LC2_3 consumes it for chemistry-aware instructions and fresh-context review.
"""

from ...LC2_2_card_db_merger.element_inventory import (
    ElementInventoryEntry,
    build_element_inventory,
    card_include_index,
    inventory_by_element,
    inventory_from_json,
    inventory_to_json,
    render_element_inventory,
)
from .instruction_agent import (
    ElementDedupOrchestrationSession,
    build_element_instructions,
    run_element_review_phase,
)

__all__ = [
    "ElementInventoryEntry",
    "build_element_inventory",
    "card_include_index",
    "inventory_by_element",
    "inventory_from_json",
    "inventory_to_json",
    "render_element_inventory",
    "ElementDedupOrchestrationSession",
    "build_element_instructions",
    "run_element_review_phase",
]
