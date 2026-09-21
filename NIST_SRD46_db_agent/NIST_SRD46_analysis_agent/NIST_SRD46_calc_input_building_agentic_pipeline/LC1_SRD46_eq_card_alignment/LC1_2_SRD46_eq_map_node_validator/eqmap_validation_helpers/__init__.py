"""eqmap_validation_helpers — deterministic screen for draft eq-maps.

Public surface
--------------
- :func:`get_node_neighbors` (neighbor_query)
- :func:`screen_eq_map`, :func:`screen_node` (node_screen)
- :func:`render_screen_md`, :func:`render_neighbors_md` (report_md)
"""
from .neighbor_query import get_node_neighbors, NeighborRow
from .node_screen import (
    screen_eq_map,
    screen_node,
    NodeScreen,
    EqMapScreen,
    EqMapNode,
)
from .report_md import render_screen_md, render_neighbors_md
from .patch_validator import (
    VALID_OPERATIONS,
    PatchValidationResult,
    validate_patches,
    format_errors_for_agent,
)

__all__ = [
    "get_node_neighbors",
    "NeighborRow",
    "screen_eq_map",
    "screen_node",
    "NodeScreen",
    "EqMapScreen",
    "EqMapNode",
    "render_screen_md",
    "render_neighbors_md",
    "VALID_OPERATIONS",
    "PatchValidationResult",
    "validate_patches",
    "format_errors_for_agent",
]
