"""
grid_dynamic_refiner — Adaptive grid refinement and boundary detection
======================================================================

Modules:
- ``labeler``            : assign predominance labels to grid points
- ``boundary_detector``  : detect label-transition boundary cells
- ``boundary_refiner``   : bisection refinement of boundary coordinates
"""

from .labeler import label_grid_nd
from .boundary_detector import (
    detect_boundary_cells_nd,
    get_boundary_cell_indices,
)
from .boundary_refiner import (
    refine_boundaries_nd,
    refine_boundaries_multilayer_nd,
)

__all__ = [
    "label_grid_nd",
    "detect_boundary_cells_nd",
    "get_boundary_cell_indices",
    "refine_boundaries_nd",
    "refine_boundaries_multilayer_nd",
]
