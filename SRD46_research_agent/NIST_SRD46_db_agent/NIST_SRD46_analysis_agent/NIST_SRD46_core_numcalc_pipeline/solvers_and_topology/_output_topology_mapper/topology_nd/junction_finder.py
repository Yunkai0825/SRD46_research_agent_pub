"""
junction_finder.py
==================
Step 1 of the bottom-up topology extractor: find 0-D junctions.

A junction is a **grid vertex** where 3 or more labelled regions meet.
In 2-D these are triple/quadruple points; in 3-D they become
triple lines or quadruple points.

Vertex-based algorithm
----------------------
1. Enumerate every vertex of the grid (fence-post indices,
   shape ``(n_0+1, n_1+1, ...)``).
2. At each vertex, collect labels from all neighbouring cells
   (up to 2^N cells sharing the vertex as a corner).
3. Vertices with >= 3 distinct valid labels are junctions.
4. For 3-D+, cluster cardinally adjacent junction vertices with
   the same label set into features (triple lines, etc.).

Domain-edge junctions (2-label vertices at the domain boundary)
are **not** created here.  The boundary builder creates them when
a boundary chain terminates at the domain edge.
"""

from __future__ import annotations

import numpy as np
from collections import defaultdict
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

try:
    from ...nd_grid.data_types import (
        NDGrid, BoundaryCellND, TopologyJunction,
    )
except ImportError:
    from nd_grid.data_types import (
        NDGrid, BoundaryCellND, TopologyJunction,
    )

from .geometry_utils import (
    vertex_to_coords,
    vertex_neighbor_cells,
    _UnionFind,
)
from .topology_fixer import FixDecisions, _within_steps


def find_junctions(
    grid: NDGrid,
    boundary_cells: Optional[List[BoundaryCellND]] = None,
    debug: bool = False,
    fix_decisions: Optional[FixDecisions] = None,
) -> List[TopologyJunction]:
    """Find all junctions (vertices where 3+ regions meet).

    Each grid vertex is classified by the labels of its neighbouring
    cells.  Vertices with 3 or more distinct labels are junction
    candidates.  The raw pass (no ``fix_decisions``) reports every
    candidate as its own junction.  In the fixed pass the topology
    fixer's decisions demote self-contact vertices (T1 waists of the
    effective map); with a non-empty ``trust_steps`` candidates that
    share one label set within that reach are clustered into a single
    junction feature (the fixer emits an empty trust: the effective
    map is already merged, so every remaining vertex is a junction).

    In N-D the intrinsic dimension of a junction is
    ``max(N - k + 1, 0)`` where *k* is the number of meeting labels:

    - 2-D, k=3 → dim 0 (triple point)
    - 3-D, k=3 → dim 1 (triple line / curve)
    - 3-D, k=4 → dim 0 (quadruple point)

    Returns a list of TopologyJunction with sequential IDs from 0.
    """
    if grid.labels is None:
        raise ValueError("Grid not labelled")

    if grid.ndim == 1:
        return []

    ndim = grid.ndim
    shape = grid.shape
    labels = grid.labels
    v_shape = tuple(s + 1 for s in shape)
    demoted = fix_decisions.demoted_vertices if fix_decisions else frozenset()

    # ── Enumerate junction vertices (3+ labels) ───────────────
    junction_verts: List[Tuple[
        Tuple[int, ...],      # v_idx
        FrozenSet[int],        # label_set
        List[Tuple[int, ...]],  # neighbouring cells
        bool,                   # is_domain_edge
    ]] = []

    for v_idx in np.ndindex(*v_shape):
        if ndim == 2 and tuple(v_idx) in demoted:
            continue
        cells = vertex_neighbor_cells(v_idx, shape)
        label_set: Set[int] = set()
        for c in cells:
            lbl = int(labels[c])
            if lbl >= 0:
                label_set.add(lbl)
        if len(label_set) < 3:
            continue
        is_edge = any(v_idx[d] == 0 or v_idx[d] == shape[d]
                      for d in range(ndim))
        junction_verts.append(
            (v_idx, frozenset(label_set), cells, is_edge))

    if debug:
        print(f"[junction_finder] {len(junction_verts)} junction vertices "
              f"(3+ labels)")

    # ── Build junction objects ─────────────────────────────────
    if ndim == 2:
        trust_steps = fix_decisions.trust_steps if fix_decisions else ()
        junctions = _junctions_from_vertices_2d(
            junction_verts, grid, trust_steps)
    else:
        junctions = _cluster_junction_vertices_nd(junction_verts, grid)

    for i, j in enumerate(junctions):
        j.id = i

    if debug:
        n_edge = sum(1 for j in junctions if j.is_domain_edge)
        print(f"[junction_finder] {len(junctions)} junctions "
              f"({len(junctions) - n_edge} interior, "
              f"{n_edge} domain-edge)")

    return junctions


# ------------------------------------------------------------------
#  2-D: qualifying vertices → 0-D junctions, clustered within trust
# ------------------------------------------------------------------

def _junctions_from_vertices_2d(
    verts: List[Tuple[Tuple[int, ...], FrozenSet[int], List, bool]],
    grid: NDGrid,
    trust_steps: Tuple[int, ...],
) -> List[TopologyJunction]:
    """One junction per candidate cluster.

    Candidates sharing one label set within ``trust_steps`` are one
    jittered junction: the feature keeps every member vertex (boundary
    chains key on exact vertex indices), and its coords are the member
    centroid, matching the N-D cluster convention.  With empty trust
    (raw pass, and the fixer's default) every vertex is its own
    junction.
    """
    if not verts:
        return []

    n = len(verts)
    uf = _UnionFind(n)
    if trust_steps and any(s > 0 for s in trust_steps) and n > 1:
        for a in range(n):
            va, set_a = verts[a][0], verts[a][1]
            for b in range(a + 1, n):
                if (set_a == verts[b][1]
                        and _within_steps(va, verts[b][0], trust_steps)):
                    uf.union(a, b)

    clusters = sorted(uf.components().values(), key=min)
    junctions: List[TopologyJunction] = []
    for members in clusters:
        members = sorted(members)
        label_set = verts[members[0]][1]
        member_coords = []
        all_cells: List[Tuple[int, ...]] = []
        any_edge = False
        for m in members:
            v_idx, _, cells, is_edge = verts[m]
            member_coords.append(vertex_to_coords(v_idx, grid))
            all_cells.extend(tuple(c) for c in cells)
            any_edge = any_edge or is_edge
        coords = {
            ax.name: sum(c[ax.name] for c in member_coords)
            / len(member_coords)
            for ax in grid.axes
        }
        junctions.append(TopologyJunction(
            id=0,
            coords=coords,
            adjacent_labels=sorted(label_set),
            is_domain_edge=any_edge,
            cell_indices=sorted(set(all_cells)),
            vertex_indices=sorted(tuple(verts[m][0]) for m in members),
        ))
    return junctions


# ------------------------------------------------------------------
#  N-D (N >= 3): cluster adjacent junction vertices by label set
# ------------------------------------------------------------------

def _cluster_junction_vertices_nd(
    verts: List[Tuple[Tuple[int, ...], FrozenSet[int], List, bool]],
    grid: NDGrid,
) -> List[TopologyJunction]:
    """Cluster connected junction vertices sharing the same label set.

    Connected vertices with identical label sets form one junction
    feature (e.g. a triple line in 3-D).
    """
    if not verts:
        return []

    ndim = grid.ndim
    axes = grid.axes

    # Group by label set
    groups: Dict[FrozenSet[int], List[int]] = defaultdict(list)
    for i, (_, label_set, _, _) in enumerate(verts):
        groups[label_set].append(i)

    # Cardinal offsets in the vertex grid
    cardinal: List[Tuple[int, ...]] = []
    for d in range(ndim):
        for delta in (-1, 1):
            off = [0] * ndim
            off[d] = delta
            cardinal.append(tuple(off))

    junctions: List[TopologyJunction] = []

    for label_set, indices in groups.items():
        k = len(label_set)
        idim = max(ndim - k + 1, 0)

        # Connected components via cardinal vertex adjacency
        n = len(indices)
        idx_to_pos = {verts[indices[j]][0]: j for j in range(n)}
        uf = _UnionFind(n)

        for j in range(n):
            v_idx = verts[indices[j]][0]
            for off in cardinal:
                nb = tuple(v_idx[d] + off[d] for d in range(ndim))
                nb_pos = idx_to_pos.get(nb)
                if nb_pos is not None:
                    uf.union(j, nb_pos)

        for comp in uf.components().values():
            all_cells: List[Tuple[int, ...]] = []
            any_edge = False
            comp_coords: List[Dict[str, float]] = []
            comp_vertices: List[Tuple[int, ...]] = []

            for ci in comp:
                vi = indices[ci]
                v_idx_i, _, cells_i, edge_i = verts[vi]
                all_cells.extend(cells_i)
                if edge_i:
                    any_edge = True
                comp_coords.append(vertex_to_coords(v_idx_i, grid))
                comp_vertices.append(tuple(v_idx_i))

            # Centroid of component vertices
            coords: Dict[str, float] = {}
            for ax in axes:
                coords[ax.name] = (
                    sum(c[ax.name] for c in comp_coords) / len(comp_coords))

            geom = comp_coords if idim >= 1 else None
            junctions.append(TopologyJunction(
                id=0,
                coords=coords,
                adjacent_labels=sorted(label_set),
                is_domain_edge=any_edge,
                geometry=geom,
                intrinsic_dim=idim,
                cell_indices=list(set(all_cells)),
                vertex_indices=sorted(comp_vertices),
            ))

    return junctions
