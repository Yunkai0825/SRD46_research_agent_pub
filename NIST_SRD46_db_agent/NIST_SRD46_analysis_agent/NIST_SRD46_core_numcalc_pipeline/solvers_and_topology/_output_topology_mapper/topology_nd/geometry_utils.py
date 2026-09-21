"""
geometry_utils.py
=================
Union-find, boundary-facet connectivity, domain fence-post tests, and
grid vertex/facet utilities for the N-D topology extractor.
"""

from __future__ import annotations

from itertools import combinations
from typing import (
    Any, Dict, List, Set, Sequence, Tuple,
)


# ------------------------------------------------------------------
#  Union-find
# ------------------------------------------------------------------

class _UnionFind:
    __slots__ = ("parent", "rank")

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def components(self) -> Dict[int, List[int]]:
        groups: Dict[int, List[int]] = {}
        for i in range(len(self.parent)):
            groups.setdefault(self.find(i), []).append(i)
        return groups


# ------------------------------------------------------------------
#  Facet-based union-find (boundary cell connectivity)
# ------------------------------------------------------------------

def boundary_facet_connected_components(
    boundary_cells: Sequence[Any],
    ndim: int,
) -> List[List[int]]:
    """Find connected components of canonical boundary *facets*.

    A :class:`BoundaryCellND` record is anchored on the lower-index cell,
    but its topology is the oriented facet identified by ``(index, axis)``.
    Comparing anchors alone loses the axis, collapses distinct facets that
    share an anchor, and can split a continuous boundary.  Here two facets
    are connected when they share a codimension-two ridge: one vertex in
    1-D/2-D, two vertices in 3-D, four in 4-D, and so on.

    The vertex buckets keep the operation local; unlike an all-pairs scan,
    runtime scales with facets that actually meet at a grid vertex.
    """
    n = len(boundary_cells)
    if n == 0:
        return []

    required_shared_vertices = 1 if ndim <= 2 else 2 ** (ndim - 2)
    facet_vertex_sets: List[Set[Tuple[int, ...]]] = []
    vertex_to_facets: Dict[Tuple[int, ...], List[int]] = {}

    for i, bc in enumerate(boundary_cells):
        vertices = set(facet_vertices(bc.index, bc.axis, ndim))
        facet_vertex_sets.append(vertices)
        for vertex in vertices:
            vertex_to_facets.setdefault(vertex, []).append(i)

    uf = _UnionFind(n)
    candidate_pairs: Set[Tuple[int, int]] = set()
    for incident in vertex_to_facets.values():
        for a, b in combinations(incident, 2):
            candidate_pairs.add((min(a, b), max(a, b)))

    for a, b in candidate_pairs:
        if len(facet_vertex_sets[a] & facet_vertex_sets[b]) \
                >= required_shared_vertices:
            uf.union(a, b)

    return list(uf.components().values())


# ------------------------------------------------------------------
#  Domain fence-post tests (N-D)
# ------------------------------------------------------------------

def is_domain_vertex_nd(
    v_idx: Tuple[int, ...],
    shape: Tuple[int, ...],
) -> bool:
    """Return whether a fencepost vertex lies on the exact N-D domain.

    ``v_idx`` belongs to the vertex lattice of shape ``shape + 1``.  This
    discrete test is preferable to a coordinate-distance heuristic whenever
    topology code still has canonical facet/vertex indices available.
    """
    if len(v_idx) != len(shape):
        raise ValueError(
            f"vertex dimensionality {len(v_idx)} does not match "
            f"grid dimensionality {len(shape)}"
        )
    if any(v < 0 or v > shape[d] for d, v in enumerate(v_idx)):
        raise ValueError(
            f"vertex {v_idx} is outside fencepost shape "
            f"{tuple(size + 1 for size in shape)}"
        )
    return any(v == 0 or v == shape[d] for d, v in enumerate(v_idx))


def is_on_domain_edge_exact_nd(
    coord: Dict[str, float],
    axes: List[Any],
    *,
    rtol: float = 1.0e-12,
) -> bool:
    """Return whether *coord* lies on a declared-domain fencepost.

    The small relative tolerance absorbs serialization round-off only; it is
    not scaled by grid spacing and cannot classify a nearby interior point
    as a domain point.
    """
    for axis in axes:
        value = coord.get(axis.name)
        if value is None:
            continue
        lower, upper = axis.range
        scale = max(1.0, abs(lower), abs(upper))
        tolerance = rtol * scale
        if (abs(float(value) - lower) <= tolerance
                or abs(float(value) - upper) <= tolerance):
            return True
    return False


# ------------------------------------------------------------------
#  Grid vertex utilities (fence-post geometry)
# ------------------------------------------------------------------

def vertex_to_coords(
    v_idx: Tuple[int, ...],
    grid: Any,
) -> Dict[str, float]:
    """Physical coordinates of the grid vertex at fence-post index *v_idx*.

    The vertex grid has shape ``(n_0+1, n_1+1, ...)`` where ``n_k``
    is the number of sample points along axis *k*.  Vertex ``v_k``
    sits at:

    - ``v_k == 0``:   ``axis.range[0]``  (declared domain low edge)
    - ``v_k == n_k``: ``axis.range[1]``  (declared domain high edge)
    - otherwise:      midpoint of ``axis.values[v_k-1]`` and
                      ``axis.values[v_k]``
    """
    coords: Dict[str, float] = {}
    for d, ax in enumerate(grid.axes):
        v = v_idx[d]
        n = ax.n
        domain_lo, domain_hi = ax.range
        if v <= 0:
            coords[ax.name] = float(domain_lo)
        elif v >= n:
            coords[ax.name] = float(domain_hi)
        else:
            coords[ax.name] = (float(ax.values[v - 1])
                               + float(ax.values[v])) / 2.0
    return coords


def vertex_neighbor_cells(
    v_idx: Tuple[int, ...],
    shape: Tuple[int, ...],
) -> List[Tuple[int, ...]]:
    """Valid cell multi-indices that share vertex *v_idx* as a corner.

    For a vertex at fence-post index ``(v_0, ..., v_{N-1})``, the
    candidate cells along axis *k* are ``{v_k-1, v_k}`` intersected
    with ``[0, n_k-1]``.  Returns all valid combinations.
    """
    from itertools import product as _product
    ndim = len(shape)
    per_axis: List[List[int]] = []
    for d in range(ndim):
        cands: List[int] = []
        if v_idx[d] - 1 >= 0:
            cands.append(v_idx[d] - 1)
        if v_idx[d] < shape[d]:
            cands.append(v_idx[d])
        if not cands:
            return []
        per_axis.append(cands)
    return [combo for combo in _product(*per_axis)]


def facet_vertices(
    cell_idx: Tuple[int, ...],
    axis: int,
    ndim: int,
) -> List[Tuple[int, ...]]:
    """Vertices of the facet between *cell_idx* and its neighbor along *axis*.

    The facet sits at fence-post position ``cell_idx[axis]+1`` along
    the transition axis, and spans ``{cell_idx[k], cell_idx[k]+1}``
    along every other axis.  Returns 2^(N-1) vertex tuples.
    """
    from itertools import product as _product
    per_axis: List[List[int]] = []
    for k in range(ndim):
        if k == axis:
            per_axis.append([cell_idx[k] + 1])
        else:
            per_axis.append([cell_idx[k], cell_idx[k] + 1])
    return [combo for combo in _product(*per_axis)]
