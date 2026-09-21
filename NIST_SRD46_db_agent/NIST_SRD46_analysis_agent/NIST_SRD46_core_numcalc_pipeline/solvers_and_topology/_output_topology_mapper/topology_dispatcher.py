"""
topology_dispatcher.py
======================
Single entry point for N-D topology extraction.

Delegates to the unified bottom-up extractor in ``topology_nd/``.
Boundary cells are auto-detected if not provided.

Public API
----------
- ``extract_topology``  — works for any dimensionality (1-D, 2-D, 3-D, …)
"""

from __future__ import annotations

from typing import List, Optional

try:
    from ..nd_grid.data_types import (
        NDGrid,
        RefinedBoundaryPointND,
        TopologyND,
    )
except ImportError:
    from nd_grid.data_types import (
        NDGrid,
        RefinedBoundaryPointND,
        TopologyND,
    )


def extract_topology(
    grid: NDGrid,
    refined_points: Optional[List[RefinedBoundaryPointND]] = None,
    built_system=None,
    debug: bool = False,
    **kwargs,
) -> TopologyND:
    """
    Unified topology extraction for any dimensionality.

    Parameters
    ----------
    grid            : labelled NDGrid (any dimensionality)
    refined_points  : optional refined boundary points from bisection
    built_system    : unused (kept for backward compatibility)
    debug           : print debug info
    **kwargs        : forwarded to the extractor
                      (e.g., element_name, boundary_cells)

    Returns
    -------
    TopologyND — unified topology result
    """
    from .topology_nd.topology_nd import extract_topology_nd

    boundary_cells = kwargs.pop("boundary_cells", None)
    if boundary_cells is None:
        try:
            from ..nd_grid.grid_dynamic_refiner.boundary_detector import (
                detect_boundary_cells_nd,
            )
        except ImportError:
            from nd_grid.grid_dynamic_refiner.boundary_detector import (
                detect_boundary_cells_nd,
            )
        boundary_cells = detect_boundary_cells_nd(
            grid,
            element_name=kwargs.get("element_name"),
            debug=debug,
        )

    return extract_topology_nd(
        grid,
        boundary_cells=boundary_cells,
        refined_points=refined_points,
        debug=debug,
        **kwargs,
    )
