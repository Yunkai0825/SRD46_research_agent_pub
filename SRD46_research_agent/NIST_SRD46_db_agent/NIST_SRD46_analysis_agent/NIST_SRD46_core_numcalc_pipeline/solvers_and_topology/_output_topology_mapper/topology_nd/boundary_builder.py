"""
boundary_builder.py
===================
Step 2 of the bottom-up topology extractor: find (N-1)-D boundaries.

A boundary separates two adjacent regions with different labels.
Each connected set of boundary facets with the same label pair
becomes one TopologyBoundary.

Vertex-based algorithm
----------------------
1. Group boundary facets by canonical label pair (min, max).
2. Within each group, find components through shared facet ridges.
3. Preserve each canonical facet and compute its exact fence-post vertices.
4. Build geometry from that facet incidence:
   - 1-D: single coordinate (the facet vertex)
   - 2-D: edge-disjoint chains ordered from the canonical facet edges
   - N-D: point cloud of vertex positions
5. Assign junctions only through shared discrete vertex indices; create a
   two-label endpoint only when a 2-D chain ends at an exact domain vertex.
6. Merge refined boundary points for smoother geometry.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from ...nd_grid.data_types import (
        NDGrid, BoundaryCellND, RefinedBoundaryPointND,
        TopologyBoundary, TopologyJunction,
    )
except ImportError:
    from nd_grid.data_types import (
        NDGrid, BoundaryCellND, RefinedBoundaryPointND,
        TopologyBoundary, TopologyJunction,
    )

from .geometry_utils import (
    boundary_facet_connected_components,
    vertex_to_coords,
    vertex_neighbor_cells,
    facet_vertices,
)
from .topology_fixer import FixDecisions


def build_boundaries(
    grid: NDGrid,
    boundary_cells: List[BoundaryCellND],
    junctions: List[TopologyJunction],
    refined_points: Optional[List[RefinedBoundaryPointND]] = None,
    debug: bool = False,
    fix_decisions: Optional[FixDecisions] = None,
) -> List[TopologyBoundary]:
    """Build (N-1)-D topology boundaries from boundary cells.

    Uses vertex-based geometry: boundary polylines / surfaces are
    sequences of grid-vertex coordinates, not cell midpoints.

    Returns a list of TopologyBoundary with sequential IDs from 0.
    """
    if not boundary_cells:
        return []

    demoted = fix_decisions.demoted_vertices if fix_decisions else frozenset()
    axes = grid.axes
    ndim = grid.ndim
    shape = grid.shape

    # ── Step 1: group by canonical label pair ──────────────────
    groups: Dict[Tuple[int, int], List[BoundaryCellND]] = {}
    for bc in boundary_cells:
        key = (min(bc.left_label, bc.right_label),
               max(bc.left_label, bc.right_label))
        groups.setdefault(key, []).append(bc)

    # Exact discrete junction incidence.  A clustered N-D junction's centroid
    # is presentation geometry and must never be used as its incidence key.
    jnc_vertex_to_id = _build_junction_vertex_map(junctions)

    # ── Step 2-3: connected components + vertex geometry ───────
    boundaries: List[TopologyBoundary] = []
    bid = 0

    for (label_lo, label_hi), cells in sorted(groups.items()):
        components = boundary_facet_connected_components(cells, ndim)
        component_cells = [
            [cells[i] for i in comp_indices]
            for comp_indices in components
        ]

        if ndim == 2:
            # A 2-D canonical facet is already an exact graph edge between
            # two fence-post vertices.  Preserve those edges explicitly.
            # Reconstructing a graph from the *union* of their vertices and
            # then joining every cardinal neighbour invents internal edges
            # at concave turns (and drops a real facet in their place).
            chain_specs: List[
                Tuple[List[Tuple[int, ...]], List[BoundaryCellND]]
            ] = []
            for comp_cells in component_cells:
                chain_specs.extend(
                    _trace_facet_edge_chains_2d(
                        comp_cells, grid, jnc_vertex_to_id,
                    )
                )

            refined_by_chain = (
                _assign_refined_points_to_components(
                    refined_points,
                    [chain_cells for _, chain_cells in chain_specs],
                    (label_lo, label_hi),
                    grid,
                )
                if refined_points else [[] for _ in chain_specs]
            )

            for chain_pos, (chain_vertices, chain_cells) in enumerate(
                    chain_specs):
                # Register exact graph endpoints.  Existing 3+-label
                # junctions are reused and exact domain endpoints receive
                # two-label domain records.  Interior two-label degree
                # splits remain unlinked because they are not chemical
                # triple points.
                junction_ids = _chain_endpoint_junction_ids_2d(
                    chain_vertices,
                    (label_lo, label_hi),
                    grid,
                    junctions,
                    jnc_vertex_to_id,
                )

                vertex_coords = [
                    vertex_to_coords(vertex, grid)
                    for vertex in chain_vertices
                ]
                a0, a1 = axes[0].name, axes[1].name
                geometry = [
                    (coord[a0], coord[a1]) for coord in vertex_coords
                ]
                # Demotion rule: self-contact vertices (envelope interior
                # of a fixer T1 merge) are not RDP anchors (chains still
                # pass through them).  Refined points spliced in below are
                # off-lattice and never match a disabled coordinate.
                disabled_coords = {
                    (coord[a0], coord[a1])
                    for vertex, coord in zip(chain_vertices, vertex_coords)
                    if tuple(vertex) in demoted
                }
                chain_refined = refined_by_chain[chain_pos]
                if chain_refined and len(geometry) >= 2:
                    geometry = _merge_refined_2d(
                        geometry,
                        [point.coords for point in chain_refined],
                        axes,
                    )
                anchor_flags = [
                    point not in disabled_coords for point in geometry
                ]
                if anchor_flags:
                    anchor_flags[0] = True
                    anchor_flags[-1] = True

                boundaries.append(TopologyBoundary(
                    id=bid,
                    left_label=label_lo,
                    right_label=label_hi,
                    btype=_majority_btype(chain_cells),
                    geometry=geometry,
                    junction_ids=junction_ids,
                    cell_indices=_incident_cell_indices(chain_cells),
                    anchor_flags=anchor_flags,
                ))
                bid += 1
            continue

        refined_by_component = (
            _assign_refined_points_to_components(
                refined_points,
                component_cells,
                (label_lo, label_hi),
                grid,
            )
            if refined_points else [[] for _ in components]
        )

        for comp_pos, comp_cells in enumerate(component_cells):
            btype = _majority_btype(comp_cells)

            # Collect all facet vertices for this component.  In N>=3 this
            # remains a point-cloud representation of a codimension-one
            # feature; the exact 2-D edge walk is handled above.
            vert_set: Set[Tuple[int, ...]] = set()
            for bc in comp_cells:
                for v in facet_vertices(bc.index, bc.axis, ndim):
                    vert_set.add(v)

            vert_list = sorted(vert_set)
            vert_coords = [vertex_to_coords(v, grid) for v in vert_list]

            refined_lookup = (
                _build_refined_lookup(refined_by_component[comp_pos])
                if refined_by_component[comp_pos] else {}
            )
            geometry = _build_vertex_geometry(
                vert_list, vert_coords, axes, ndim,
                refined_lookup, (label_lo, label_hi))

            junction_ids = _find_junction_endpoints(
                vert_set, jnc_vertex_to_id)

            boundaries.append(TopologyBoundary(
                id=bid,
                left_label=label_lo,
                right_label=label_hi,
                btype=btype,
                geometry=geometry,
                junction_ids=junction_ids,
                cell_indices=_incident_cell_indices(comp_cells),
            ))
            bid += 1

    # Junction coordinates are never refined off-vertex.  N-D domain
    # intersections are codimension-two features, not arbitrary near-edge
    # point-cloud extrema; until their exact facet-incidence geometry is
    # represented explicitly, no heuristic N-D domain nodes are synthesized.

    if debug:
        print(f"[boundary_builder] {len(boundaries)} boundaries from "
              f"{len(boundary_cells)} cells")

    return boundaries


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

def _majority_btype(cells: List[BoundaryCellND]) -> str:
    counts: Dict[str, int] = {}
    for c in cells:
        counts[c.btype] = counts.get(c.btype, 0) + 1
    return max(counts, key=counts.get)


def _incident_cell_indices(
    cells: List[BoundaryCellND],
) -> List[Tuple[int, ...]]:
    """Unique sample-cell indices on both sides of canonical facets."""

    result: List[Tuple[int, ...]] = []
    seen: Set[Tuple[int, ...]] = set()
    for cell in cells:
        high = list(cell.index)
        high[cell.axis] += 1
        for index in (tuple(cell.index), tuple(high)):
            if index not in seen:
                seen.add(index)
                result.append(index)
    return result


def _facet_edge_2d(
    cell: BoundaryCellND,
) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """Canonical unordered fence-post edge for one 2-D facet."""

    vertices = sorted(facet_vertices(cell.index, cell.axis, 2))
    if len(vertices) != 2:
        raise RuntimeError(
            "A 2-D canonical boundary facet must have exactly two vertices"
        )
    return vertices[0], vertices[1]


def _is_domain_vertex(
    vertex: Tuple[int, ...],
    shape: Tuple[int, ...],
) -> bool:
    return any(
        vertex[axis] == 0 or vertex[axis] == shape[axis]
        for axis in range(len(shape))
    )


def _trace_facet_edge_chains_2d(
    cells: List[BoundaryCellND],
    grid: Any,
    junction_vertex_to_id: Dict[Tuple[int, ...], int],
) -> List[Tuple[List[Tuple[int, ...]], List[BoundaryCellND]]]:
    """Trace exact 2-D facet edges into junction-bounded chains.

    Every unique canonical facet is consumed exactly once.  Connectivity is
    taken from the facet edges themselves, never inferred from cardinally
    adjacent vertices.  Chains terminate at an existing junction, an exact
    domain vertex, or a graph vertex whose degree is not two.  A remaining
    all-degree-two component is emitted as a closed loop.
    """

    edge_to_cell: Dict[
        Tuple[Tuple[int, ...], Tuple[int, ...]], BoundaryCellND
    ] = {}
    for cell in cells:
        edge_to_cell.setdefault(_facet_edge_2d(cell), cell)

    adjacency: Dict[
        Tuple[int, ...],
        List[Tuple[Tuple[int, ...], Tuple[int, ...]]],
    ] = {}
    for edge in edge_to_cell:
        for vertex in edge:
            adjacency.setdefault(vertex, []).append(edge)
    for incident in adjacency.values():
        incident.sort()

    split_vertices = {
        vertex
        for vertex, incident in adjacency.items()
        if (len(incident) != 2
            or vertex in junction_vertex_to_id
            or _is_domain_vertex(vertex, grid.shape))
    }
    unvisited = set(edge_to_cell)
    chains: List[
        Tuple[List[Tuple[int, ...]], List[BoundaryCellND]]
    ] = []

    def trace(
        start: Tuple[int, ...],
        first_edge: Tuple[Tuple[int, ...], Tuple[int, ...]],
    ) -> Tuple[List[Tuple[int, ...]], List[BoundaryCellND]]:
        vertices = [start]
        chain_cells: List[BoundaryCellND] = []
        current = start
        edge = first_edge

        while edge in unvisited:
            unvisited.remove(edge)
            chain_cells.append(edge_to_cell[edge])
            next_vertex = edge[1] if edge[0] == current else edge[0]
            vertices.append(next_vertex)

            if next_vertex == start or next_vertex in split_vertices:
                break

            candidates = [
                candidate for candidate in adjacency[next_vertex]
                if candidate in unvisited
            ]
            if not candidates:
                break
            # A non-split vertex has degree exactly two, so only one
            # unvisited continuation can remain.
            edge = candidates[0]
            current = next_vertex

        return vertices, chain_cells

    # Open/junction-bounded chains first.  Sorting makes the decomposition
    # reproducible independently of boundary-detector iteration order.
    for start in sorted(split_vertices):
        for edge in adjacency[start]:
            if edge in unvisited:
                chains.append(trace(start, edge))

    # Any remainder is an all-degree-two closed loop.
    while unvisited:
        first_edge = min(unvisited)
        start = min(first_edge)
        chains.append(trace(start, first_edge))

    return chains


def _chain_endpoint_junction_ids_2d(
    vertices: List[Tuple[int, ...]],
    label_pair: Tuple[int, int],
    grid: Any,
    junctions: List[TopologyJunction],
    junction_vertex_to_id: Dict[Tuple[int, ...], int],
) -> List[int]:
    """Return/create junctions at the exact endpoints of one edge chain."""

    if len(vertices) < 2 or vertices[0] == vertices[-1]:
        return []

    junction_by_id = {junction.id: junction for junction in junctions}
    result: List[int] = []
    for vertex in (vertices[0], vertices[-1]):
        junction_id = junction_vertex_to_id.get(vertex)
        is_domain = _is_domain_vertex(vertex, grid.shape)
        if junction_id is None and not is_domain:
            # A two-label non-manifold degree split is not a chemical triple
            # point.  Keep it as an unlinked chain endpoint rather than
            # creating a marker that downstream plots would misidentify.
            continue
        if junction_id is None:
            coords = vertex_to_coords(vertex, grid)
            junction_id = max(
                (junction.id for junction in junctions), default=-1,
            ) + 1
            junction = TopologyJunction(
                id=junction_id,
                coords=coords,
                adjacent_labels=list(label_pair),
                is_domain_edge=True,
                cell_indices=vertex_neighbor_cells(vertex, grid.shape),
                vertex_indices=[tuple(vertex)],
            )
            junctions.append(junction)
            junction_by_id[junction_id] = junction
            junction_vertex_to_id[tuple(vertex)] = junction_id
        else:
            junction = junction_by_id.get(junction_id)
            if junction is not None:
                junction.adjacent_labels = sorted(set(
                    junction.adjacent_labels
                ).union(label_pair))

        if junction_id not in result:
            result.append(junction_id)
    return result


def _build_junction_vertex_map(
    junctions: List[TopologyJunction],
) -> Dict[Tuple[int, ...], int]:
    """Map every exact discrete junction vertex to its feature ID."""

    result: Dict[Tuple[int, ...], int] = {}
    for junction in junctions:
        for vertex in junction.vertex_indices:
            result[tuple(vertex)] = junction.id
    return result


def _build_refined_lookup(
    refined_points: List[RefinedBoundaryPointND],
) -> Dict[Tuple[int, int], List[Dict[str, float]]]:
    lookup: Dict[Tuple[int, int], List[Dict[str, float]]] = {}
    for rp in refined_points:
        key = (min(rp.left_label, rp.right_label),
               max(rp.left_label, rp.right_label))
        lookup.setdefault(key, []).append(rp.coords)
    return lookup


def _assign_refined_points_to_components(
    refined_points: List[RefinedBoundaryPointND],
    component_cells: List[List[BoundaryCellND]],
    label_key: Tuple[int, int],
    grid: NDGrid,
) -> List[List[RefinedBoundaryPointND]]:
    """Assign each matching refined point to one facet component.

    Components with the same label pair may be disconnected while sharing
    an incident coarse cell, so a root-path overlap test can duplicate a
    refined point across boundaries.  Instead, measure the point-to-facet
    distance in coordinates normalized by the full sweep-axis ranges and
    assign the point to the nearest component.  ``min`` preserves component
    order as a deterministic tie break.
    """

    assigned: List[List[RefinedBoundaryPointND]] = [
        [] for _ in component_cells
    ]
    if not component_cells:
        return assigned

    facet_bounds = [
        [_facet_bounds_normalized(bc, grid) for bc in cells]
        for cells in component_cells
    ]
    axis_scales = [
        abs(float(ax.values[-1]) - float(ax.values[0])) or 1.0
        for ax in grid.axes
    ]

    for rp in refined_points:
        rp_key = (min(rp.left_label, rp.right_label),
                  max(rp.left_label, rp.right_label))
        if rp_key != label_key:
            continue
        point = tuple(
            float(rp.coords[ax.name]) / axis_scales[d]
            for d, ax in enumerate(grid.axes)
        )
        best_component = min(
            range(len(component_cells)),
            key=lambda comp_pos: min(
                _squared_point_to_box_distance(point, bounds)
                for bounds in facet_bounds[comp_pos]
            ),
        )
        assigned[best_component].append(rp)

    return assigned


def _facet_bounds_normalized(
    boundary_cell: BoundaryCellND,
    grid: NDGrid,
) -> Tuple[Tuple[float, float], ...]:
    """Return one canonical facet's normalized axis-aligned bounds."""

    vertices = facet_vertices(
        boundary_cell.index, boundary_cell.axis, grid.ndim)
    coords = [vertex_to_coords(vertex, grid) for vertex in vertices]
    bounds: List[Tuple[float, float]] = []
    for axis in grid.axes:
        scale = abs(float(axis.values[-1]) - float(axis.values[0])) or 1.0
        values = [float(coord[axis.name]) / scale for coord in coords]
        bounds.append((min(values), max(values)))
    return tuple(bounds)


def _squared_point_to_box_distance(
    point: Tuple[float, ...],
    bounds: Tuple[Tuple[float, float], ...],
) -> float:
    """Squared Euclidean distance from a point to an axis-aligned box."""

    distance = 0.0
    for value, (lower, upper) in zip(point, bounds):
        if value < lower:
            distance += (lower - value) ** 2
        elif value > upper:
            distance += (value - upper) ** 2
    return distance


# ------------------------------------------------------------------
#  Vertex-based geometry construction
# ------------------------------------------------------------------

def _build_vertex_geometry(
    vert_list: List[Tuple[int, ...]],
    vert_coords: List[Dict[str, float]],
    axes: List[Any],
    ndim: int,
    refined_lookup: Dict,
    label_key: Tuple[int, int],
) -> Any:
    if ndim == 1:
        return _geometry_1d(vert_coords, axes, refined_lookup, label_key)
    elif ndim == 2:
        raise RuntimeError(
            "2-D geometry requires the exact canonical-facet edge walk"
        )
    else:
        return _geometry_nd(vert_coords, axes, refined_lookup, label_key)


def _geometry_1d(
    vert_coords: List[Dict[str, float]],
    axes: List[Any],
    refined_lookup: Dict,
    label_key: Tuple[int, int],
) -> float:
    """1-D: single coordinate (the facet vertex position)."""
    axis_name = axes[0].name
    # Use refined points if available (closer to true boundary)
    refined_list = refined_lookup.get(label_key, [])
    if refined_list:
        vertex_val = vert_coords[0][axis_name]
        margin = axes[0].spacing * 2.0
        filtered = [c for c in refined_list
                    if abs(c[axis_name] - vertex_val) < margin]
        if filtered:
            return float(np.mean([c[axis_name] for c in filtered]))
    return float(vert_coords[0][axis_name])


def _geometry_nd(
    vert_coords: List[Dict[str, float]],
    axes: List[Any],
    refined_lookup: Dict,
    label_key: Tuple[int, int],
) -> List[Dict[str, float]]:
    """N-D: point cloud of vertex coordinates."""
    cloud = list(vert_coords)

    # Merge refined points within the bounding box
    refined_list = refined_lookup.get(label_key, [])
    if refined_list and cloud:
        bboxes: Dict[str, Tuple[float, float]] = {}
        for ax in axes:
            vals = [c[ax.name] for c in cloud]
            margin = ax.spacing * 2.0
            bboxes[ax.name] = (min(vals) - margin, max(vals) + margin)

        filtered = [
            c for c in refined_list
            if all(bboxes[nm][0] <= c[nm] <= bboxes[nm][1]
                   for nm in bboxes)
        ]
        if filtered:
            cloud = cloud + filtered

    return cloud


# ------------------------------------------------------------------
#  Refined-point merging (2-D)
# ------------------------------------------------------------------

def _merge_refined_2d(
    polyline: List[Tuple[float, float]],
    refined_list: List[Dict[str, float]],
    axes: List[Any],
) -> List[Tuple[float, float]]:
    """Insert refined points in the order of their nearest raw segment.

    A global nearest-neighbour tour can jump across a concave boundary or
    reverse one branch of a chain.  The raw facet walk already supplies the
    topological order, so assign each refined point to its nearest normalized
    raw segment, sort by projected position on that segment, and retain the
    exact raw vertices between successive segment groups.
    """
    a0, a1 = axes[0].name, axes[1].name
    if len(polyline) < 2 or not refined_list:
        return polyline

    raw = np.asarray(polyline, dtype=np.float64)
    scales = np.asarray([
        abs(float(axis.range[1]) - float(axis.range[0])) or 1.0
        for axis in axes[:2]
    ], dtype=np.float64)
    raw_norm = raw / scales
    segment_vectors = raw_norm[1:] - raw_norm[:-1]
    segment_norm2 = np.sum(segment_vectors * segment_vectors, axis=1)
    grouped: List[List[Tuple[float, Tuple[float, float]]]] = [
        [] for _ in range(len(polyline) - 1)
    ]

    for coords in refined_list:
        point = np.asarray(
            [float(coords[a0]), float(coords[a1])], dtype=np.float64,
        )
        point_norm = point / scales
        best = None
        for segment_index, (start, vector, length2) in enumerate(zip(
                raw_norm[:-1], segment_vectors, segment_norm2)):
            if length2 <= 0.0:
                t_value = 0.0
                projection = start
            else:
                t_value = float(np.dot(point_norm - start, vector) / length2)
                t_value = min(1.0, max(0.0, t_value))
                projection = start + t_value * vector
            distance2 = float(np.sum((point_norm - projection) ** 2))
            candidate = (distance2, segment_index, t_value)
            if best is None or candidate < best:
                best = candidate

        if best is not None:
            _, segment_index, t_value = best
            grouped[segment_index].append(
                (t_value, (float(point[0]), float(point[1])))
            )

    merged: List[Tuple[float, float]] = [tuple(polyline[0])]
    tol2 = 1.0e-20
    for segment_index, points in enumerate(grouped):
        for _, point in sorted(points, key=lambda item: (item[0], item[1])):
            if ((point[0] - merged[-1][0]) ** 2
                    + (point[1] - merged[-1][1]) ** 2) > tol2:
                merged.append(point)
        endpoint = tuple(polyline[segment_index + 1])
        if ((endpoint[0] - merged[-1][0]) ** 2
                + (endpoint[1] - merged[-1][1]) ** 2) > tol2:
            merged.append(endpoint)
    return merged


# ------------------------------------------------------------------
#  Junction endpoint detection (exact vertex incidence)
# ------------------------------------------------------------------

def _find_junction_endpoints(
    vert_set: Set[Tuple[int, ...]],
    junction_vertex_to_id: Dict[Tuple[int, ...], int],
) -> List[int]:
    """Junction features that share an exact discrete boundary vertex."""

    return sorted({
        junction_vertex_to_id[vertex]
        for vertex in vert_set
        if vertex in junction_vertex_to_id
    })
