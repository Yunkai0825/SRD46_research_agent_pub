"""
topology_nd.py
==============
Main orchestrator for the unified N-D topology extractor.

Extracts topology bottom-up by codimension:
  Step 1: codim ≥ 2 junctions  (junction_finder)
          – 0-D quad-points (3-D) / triple-points (2-D)
          – 1-D triple-lines (3-D)
  Step 2: codim-1 boundaries   (boundary_builder)
          – (N-1)-D phase-boundary manifolds between 2 regions
  Step 3: codim-0 regions      (region_builder)
          – N-D connected domains of a single phase

Works for any dimensionality (1-D, 2-D, 3-D, ...).
"""

from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from ...nd_grid.data_types import (
        NDGrid,
        BoundaryCellND,
        RefinedBoundaryPointND,
        TopologyND,
    )
except ImportError:
    from nd_grid.data_types import (
        NDGrid,
        BoundaryCellND,
        RefinedBoundaryPointND,
        TopologyND,
    )

from .junction_finder import find_junctions
from .boundary_builder import build_boundaries
from .region_builder import build_regions
from .topology_fixer import FixDecisions
from .geometry_utils import facet_vertices


def extract_topology_nd(
    grid: NDGrid,
    boundary_cells: Optional[List[BoundaryCellND]] = None,
    refined_points: Optional[List[RefinedBoundaryPointND]] = None,
    debug: bool = False,
    fix_decisions: Optional[FixDecisions] = None,
    **kwargs,
) -> TopologyND:
    """Extract topology from an N-D labelled grid (bottom-up).

    Parameters
    ----------
    grid : NDGrid
        Labelled grid (must have ``labels`` and ``label_catalog`` set).
    boundary_cells : list of BoundaryCellND, optional
        Pre-detected canonical transition facets. If None, they are detected
        automatically via ``detect_boundary_cells_nd``.  These records stay
        one-per-facet; only the refinement scheduler expands them to both
        incident cells.
    refined_points : list of RefinedBoundaryPointND, optional
        High-resolution boundary points from bisection refinement.
    debug : bool
        Print diagnostic output.
    fix_decisions : FixDecisions, optional
        Topology-fixer decisions for the fixed second pass (T1 bridges
        and demoted vertices of the effective map, region flags, junction
        trust).  The caller passes the grid whose labels ARE the
        effective label map; ``None`` (the default) extracts the raw,
        rule-free topology.
    **kwargs
        Forwarded to boundary detection if ``boundary_cells`` is None
        (e.g., ``element_name``).

    Returns
    -------
    TopologyND
    """
    if grid.labels is None:
        raise ValueError("Grid not labelled — call label_grid_nd() first")

    label_catalog = grid.label_catalog or {}

    # Auto-detect boundary cells if not provided
    if boundary_cells is None:
        try:
            from ...nd_grid.grid_dynamic_refiner.boundary_detector import (
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

    if debug:
        print(f"[topology_nd] ndim={grid.ndim}, shape={grid.shape}, "
              f"{len(boundary_cells)} boundary facets, "
              f"{len(label_catalog)} labels")

    # Step 1: find 0-D junctions
    junctions = find_junctions(
        grid, boundary_cells, debug=debug, fix_decisions=fix_decisions)

    # Step 2: build (N-1)-D boundaries
    boundaries = build_boundaries(
        grid, boundary_cells, junctions,
        refined_points=refined_points, debug=debug,
        fix_decisions=fix_decisions)

    # Step 3: build N-D regions
    regions, n_merges = build_regions(
        grid, boundaries, debug=debug, fix_decisions=fix_decisions)

    settings = {
        "extraction_method": "bottom_up_nd",
        "axis_names": [ax.name for ax in grid.axes],
        "axis_ranges": {
            ax.name: tuple(float(value) for value in ax.range)
            for ax in grid.axes
        },
        # Grid step of the raster the topology was extracted from; the
        # compactor derives its resolution stop criterion from this.
        "axis_spacing": {
            ax.name: float(np.median(np.diff(np.asarray(ax.values, dtype=float))))
            for ax in grid.axes
            if getattr(ax, "values", None) is not None and len(ax.values) > 1
        },
        # Raw pass: no rules applied.  Fixed pass: the fixer's full
        # analysis report (orphan decisions, marks, clusters, T1
        # bridges, tolerance).
        "topology_fix": (
            dict(fix_decisions.report) if fix_decisions
            else {"applied": False}
        ),
        "region_resolution_merges": n_merges,
    }

    # A valid 2-D Euler diagnostic must include the rectangular domain frame.
    # Counting only chemical junction objects and connected boundary features
    # mixes a geometric graph with region cells and gives a meaningless V-E+F.
    if grid.ndim == 2:
        euler = _framed_euler_diagnostic_2d(
            grid, boundary_cells, regions, n_merges,
        )
        settings["euler_diagnostic"] = euler
        if debug:
            print(
                "[topology_nd] Framed Euler check: "
                f"V={euler['vertices']} - E={euler['edges']} + "
                f"F={euler['regions']} = {euler['chi']}; "
                f"boundary-graph components={euler['graph_components']} "
                f"({'PASS' if euler['identity_holds'] else 'FAIL'})"
            )

    return TopologyND(
        ndim=grid.ndim,
        regions=regions,
        boundaries=boundaries,
        junctions=junctions,
        label_catalog=label_catalog,
        settings=settings,
    )


def _framed_euler_diagnostic_2d(
    grid: NDGrid,
    boundary_cells: List[BoundaryCellND],
    regions,
    resolution_merges: int = 0,
) -> Dict[str, Any]:
    """Return a mathematically consistent Euler check for a 2-D partition.

    The embedded graph is the union of every canonical label-transition
    facet and every unit edge of the rectangular domain frame.  Its vertices
    are exact fence-post indices.  For a planar graph with ``C`` connected
    components, the number of bounded faces is ``E - V + C``; those bounded
    faces are the cardinal-connected label patches, and each fixer T1
    bridge (same-label self-contact) joins two of them into one region,
    so ``F = (E - V + C) - resolution_merges``.  The checked identity is
    therefore ``V - E + F = C - resolution_merges``, raw and fixed alike
    (raw has zero merges).  This also handles closed phase islands, whose
    boundary loops form graph components separate from the outer frame.
    """

    if grid.ndim != 2:
        raise ValueError("Framed Euler diagnostic is defined only for 2-D")

    Edge = Tuple[Tuple[int, int], Tuple[int, int]]
    edges: Set[Edge] = set()

    def add_edge(a, b) -> None:
        aa = (int(a[0]), int(a[1]))
        bb = (int(b[0]), int(b[1]))
        edges.add((aa, bb) if aa <= bb else (bb, aa))

    for cell in boundary_cells:
        vertices = facet_vertices(cell.index, cell.axis, 2)
        if len(vertices) != 2:
            raise RuntimeError(
                "A canonical 2-D boundary facet must have two vertices"
            )
        add_edge(vertices[0], vertices[1])

    n0, n1 = (int(value) for value in grid.shape)
    for i in range(n0):
        add_edge((i, 0), (i + 1, 0))
        add_edge((i, n1), (i + 1, n1))
    for j in range(n1):
        add_edge((0, j), (0, j + 1))
        add_edge((n0, j), (n0, j + 1))

    vertices = {vertex for edge in edges for vertex in edge}
    adjacency: Dict[Tuple[int, int], Set[Tuple[int, int]]] = {
        vertex: set() for vertex in vertices
    }
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)

    unseen = set(vertices)
    graph_components = 0
    while unseen:
        graph_components += 1
        stack = [unseen.pop()]
        while stack:
            current = stack.pop()
            for neighbour in adjacency[current]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)

    V = len(vertices)
    E = len(edges)
    F = len(regions)
    chi = V - E + F
    expected = graph_components - resolution_merges
    return {
        "method": "canonical_facets_plus_rectangular_domain_frame",
        "vertices": V,
        "edges": E,
        "regions": F,
        "chi": chi,
        "graph_components": graph_components,
        "resolution_merges": int(resolution_merges),
        "expected_chi": expected,
        "identity_holds": bool(chi == expected),
    }
