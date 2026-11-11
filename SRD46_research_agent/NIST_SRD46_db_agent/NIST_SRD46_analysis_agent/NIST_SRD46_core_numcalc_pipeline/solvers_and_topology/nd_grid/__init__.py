"""
nd_grid — N-dimensional grid solver and topology pipeline
=========================================================

Single public face of ``solvers_and_topology``.  Downstream code
imports ONLY through this module::

    from solvers_and_topology.nd_grid import (
        NDGridSolver, SolveResult, ElementResult,
        GridAxis, NDGrid, PointResult,
        BoundaryCellND, RefinedBoundaryPointND, TopologyND,
    )

All grid-level pipeline work goes through
:meth:`NDGridSolver.solve` — the ONE public method.  Sub-modules
(``labeler``, ``boundary_detector``, ``boundary_refiner``,
``solver_hole_patcher``, ``topology_dispatcher`` …) are implementation
details and MUST NOT be imported by code outside this package.
"""

from .data_types import (
    GridAxis,
    PointResult,
    NDGrid,
    BoundaryCellND,
    RefinedBoundaryPointND,
    TopologyRegion,
    TopologyBoundary,
    TopologyJunction,
    TopologyND,
    cardinal_offsets,
    all_offsets,
    in_bounds,
    add_offset,
    make_empty_grid,
)

from .grid_solver import (
    NDGridSolver,
    SolveResult,
    ElementResult,
    SolveFn,
    SeedStrategy,
    PerLayerCallback,
)

__all__ = [
    # ── The sole public solver class + result bundles ──
    "NDGridSolver",
    "SolveResult",
    "ElementResult",
    "SolveFn",
    "SeedStrategy",
    "PerLayerCallback",
    # ── Data types (used to build inputs and read outputs) ──
    "GridAxis",
    "PointResult",
    "NDGrid",
    "BoundaryCellND",
    "RefinedBoundaryPointND",
    "TopologyRegion",
    "TopologyBoundary",
    "TopologyJunction",
    "TopologyND",
    # ── Low-level grid utilities (exposed for advanced callers) ──
    "cardinal_offsets",
    "all_offsets",
    "in_bounds",
    "add_offset",
    "make_empty_grid",
]
