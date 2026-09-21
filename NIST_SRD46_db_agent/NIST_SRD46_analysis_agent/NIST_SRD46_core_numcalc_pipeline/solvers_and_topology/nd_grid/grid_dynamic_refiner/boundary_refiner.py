"""
boundary_refiner.py
===================
Adaptive refinement of coarse boundary cells in N dimensions.

Every canonical label-transition facet schedules every sample-centred cell
that touches any of the facet's vertices.  Each refinement layer solves a
stable deduplicated set of target cells, registers their sub-cell centres on
a common global fine lattice, and scans each positive-axis neighbour pair
exactly once.
The resulting transition links schedule every in-domain cell touching their
facet vertices at the next layer, while axis-aligned bisection supplies tagged
boundary geometry.

Junctions are not persistent scheduler inputs.  At every depth they are
implicit in the intersection of that depth's resolved transition facets, so a
downstream junction may move, disappear, or emerge without inheriting an
upstream junction coordinate.

Replaces the legacy 2-D refiner which had separate ``_bisect_pH`` and
``_bisect_E`` routines and 2-D sub-grid loops.

Public API
----------
- ``refine_boundaries_nd``           â€” single-pass refinement
- ``refine_boundaries_multilayer_nd`` â€” cascaded multi-layer refinement
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from ..data_types import (
    NDGrid, BoundaryCellND, RefinedBoundaryPointND, PointResult,
    in_bounds, all_offsets, add_offset,
)
from ..settings import REFINE_FACTOR, REFINE_LAYERS, BISECTION_MAX, BISECTION_TOL, DEBUG
from .boundary_detector import (
    get_boundary_cell_indices,
    get_facet_vertex_incident_indices,
)


# â”€â”€ type alias for the point-solve callable â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#   solve_fn(coords: Dict[str, float], x0: Optional[np.ndarray]) -> PointResult
PointSolveFn = Callable[[Dict[str, float], Optional[np.ndarray]], PointResult]


# ==================================================================
#  Same-level refinement scheduler
# ==================================================================

GridIndex = Tuple[int, ...]
TreePath = Tuple[GridIndex, ...]


@dataclass(frozen=True)
class _RefinementTransitionND:
    """One canonical same-level transition used to schedule refinement.

    ``low_path`` and ``high_path`` identify the two solved sub-cells on
    opposite sides of an axis-adjacent label change.  This private link
    is deliberately separate from :class:`RefinedBoundaryPointND`: a
    geometric bisection point is topology evidence, whereas a link is
    scheduler state and must retain *both* incident paths.
    """

    element_name: str
    axis: int
    low_path: TreePath
    high_path: TreePath
    low_label: int
    high_label: int


@dataclass
class _RegistryEntryND:
    """Solved centre registered on one global fine lattice level."""

    global_index: GridIndex
    path: TreePath
    coords: Dict[str, float]
    point: PointResult
    labels_per_element: Dict[str, int]


@dataclass
class _MaterializedNodeND:
    """A newly solved tree node that can be registered at its level."""

    parent_path: TreePath
    sub_axes_vals: List[np.ndarray]
    sub_points: np.ndarray
    sub_labels_per_elem: Dict[str, np.ndarray]


@dataclass
class _RefinementLabelContext:
    """Immutable-ish chemistry metadata shared by all layer solves."""

    principal: List[str]
    e_idx_per_elem: Dict[str, List[int]]
    sp_ids: List[str]
    nu_elem: np.ndarray
    C_total: np.ndarray
    diss_eqs: Any
    name_to_int_per_elem: Dict[str, Dict[str, int]]

    @property
    def primary_element(self) -> str:
        return self.principal[0]


def _build_label_context(
    coarse_grid: NDGrid,
    built_system,
) -> _RefinementLabelContext:
    """Build per-element catalog lookups once for the complete cascade."""

    principal = list(built_system.principal_elements)
    if not principal:
        raise ValueError("Boundary refinement requires a principal element")

    from .labeler import component_indices_for_element

    label_catalog = coarse_grid.label_catalog_per_element or {}
    name_to_int_per_elem: Dict[str, Dict[str, int]] = {}
    e_idx_per_elem: Dict[str, List[int]] = {}
    for elem in principal:
        catalog = label_catalog.get(elem, {}) if label_catalog else {}
        if not catalog and elem == principal[0]:
            catalog = coarse_grid.label_catalog or {}
        name_to_int_per_elem[elem] = {v: k for k, v in catalog.items()}
        e_idx_per_elem[elem] = component_indices_for_element(
            built_system, elem,
        )

    return _RefinementLabelContext(
        principal=principal,
        e_idx_per_elem=e_idx_per_elem,
        sp_ids=[sp.id for sp in built_system.aqueous_species],
        nu_elem=built_system.nu_elem_matrix,
        C_total=built_system.C_total,
        diss_eqs=built_system.dissolution_eqs,
        name_to_int_per_elem=name_to_int_per_elem,
    )


def _stable_incident_root_indices(
    boundary_cells: List[BoundaryCellND],
    shape: Tuple[int, ...],
) -> List[GridIndex]:
    """Return the stable union of all facet-vertex incident root cells.

    ``BoundaryCellND`` remains the canonical one-record-per-facet
    topology representation.  Expansion happens only in the refinement
    target scheduler, so topology builders never see mirrored or artificial
    boundary records.
    """
    return get_boundary_cell_indices(boundary_cells, shape)


def _stable_transition_vertex_paths(
    links: List[_RefinementTransitionND],
    coarse_shape: Tuple[int, ...],
    current_layer: int,
    refine_factor: int,
) -> List[TreePath]:
    """Return all in-domain cells touching same-level facet vertices.

    A transition link is the adaptive-lattice analogue of a canonical coarse
    facet.  Its low/high paths alone cover only the normal pair; this expands
    the link in every transverse dimension and maps each global fine-lattice
    index back to its tree path.  Missing sparse-tree ancestors are
    materialized separately before the next layer is solved, so no valid
    vertex-incident target is discarded merely because it lies at the edge
    of the current adaptive patch.
    """

    fine_shape = tuple(
        int(coarse_shape[d]) * (refine_factor ** current_layer)
        for d in range(len(coarse_shape))
    )
    targets: List[TreePath] = []
    seen = set()
    for link in links:
        low_index = _global_fine_index(link.low_path, refine_factor)
        high_index = _global_fine_index(link.high_path, refine_factor)
        expected_high = list(low_index)
        expected_high[link.axis] += 1
        if tuple(expected_high) != high_index:
            raise RuntimeError(
                "Refinement transition endpoints are not a canonical "
                f"positive-axis pair: {link!r}"
            )
        for global_index in get_facet_vertex_incident_indices(
            low_index, link.axis, fine_shape,
        ):
            path = _tree_path_from_global_fine_index(
                global_index, coarse_shape,
                refine_factor, current_layer,
            )
            if path not in seen:
                seen.add(path)
                targets.append(path)
    return targets


def _sub_axes_from_parent(
    centres: List[float],
    parent_sizes: List[float],
    refine_factor: int,
) -> List[np.ndarray]:
    """Return R sub-cell centres per axis for a sample-centred parent."""

    sub_axes_vals: List[np.ndarray] = []
    for center, size in zip(centres, parent_sizes):
        step = size / refine_factor
        left = center - size / 2.0 + step / 2.0
        sub_axes_vals.append(left + np.arange(refine_factor) * step)
    return sub_axes_vals


def _solve_layer_node(
    sub_axes_vals: List[np.ndarray],
    axes,
    solve_fn: PointSolveFn,
    x0: Optional[np.ndarray],
    context: _RefinementLabelContext,
    x_cache: Optional[Dict[Tuple, np.ndarray]],
    debug: bool,
) -> Tuple[dict, np.ndarray, Dict[str, np.ndarray]]:
    """Solve, retry, label, and package one R^N refinement node.

    A label is written only for a converged solve.  The existing
    two-pass seeded hole patcher is retained verbatim; any unresolved
    centre therefore remains ``-1``.
    """

    from .labeler import _dominant_label_for_element
    from ..grid_solver_sweep_retry_patching.solver_hole_patcher import (
        patch_subgrid_holes,
    )

    sub_shape = tuple(len(vals) for vals in sub_axes_vals)
    sub_points = np.empty(sub_shape, dtype=object)
    sub_labels_per_elem: Dict[str, np.ndarray] = {
        elem: np.full(sub_shape, -1, dtype=np.int32)
        for elem in context.principal
    }
    primary = context.primary_element
    sub_labels = sub_labels_per_elem[primary]
    x_guess = x0.copy() if x0 is not None else None

    for sub_idx in np.ndindex(*sub_shape):
        coords = {
            axes[d].name: float(sub_axes_vals[d][sub_idx[d]])
            for d in range(len(axes))
        }
        res = solve_fn(coords, x_guess)
        sub_points[sub_idx] = res
        if not res.converged:
            continue
        x_guess = res.x.copy()
        for elem in context.principal:
            e_idx = context.e_idx_per_elem[elem]
            lbl_name = _dominant_label_for_element(
                res, elem, e_idx, context.sp_ids, context.nu_elem,
                float(np.sum(context.C_total[e_idx])), context.diss_eqs,
            )
            sub_labels_per_elem[elem][sub_idx] = (
                context.name_to_int_per_elem[elem].get(lbl_name, -1)
            )
        if x_cache is not None:
            x_cache[tuple(sorted(coords.items()))] = res.x.copy()

    def _make_resolver(elem: str):
        e_idx = context.e_idx_per_elem[elem]
        name_to_int = context.name_to_int_per_elem[elem]

        def _resolver(res):
            lbl_name = _dominant_label_for_element(
                res, elem, e_idx, context.sp_ids, context.nu_elem,
                float(np.sum(context.C_total[e_idx])), context.diss_eqs,
            )
            return name_to_int.get(lbl_name, -1)

        return _resolver

    patch_subgrid_holes(
        sub_axes_vals=sub_axes_vals,
        sub_points=sub_points,
        sub_labels=sub_labels,
        solve_fn=solve_fn,
        label_int_resolver=_make_resolver(primary),
        axis_names=[ax.name for ax in axes],
        x_cache=x_cache,
        extra_label_targets=[
            (sub_labels_per_elem[elem], _make_resolver(elem))
            for elem in context.principal if elem != primary
        ],
        debug=debug,
    )

    node = {
        "axes_vals": [arr.copy() for arr in sub_axes_vals],
        "labels": sub_labels.copy(),
        "labels_per_element": {
            elem: sub_labels_per_elem[elem].copy()
            for elem in context.principal
        },
        "children": {},
    }
    return node, sub_points, sub_labels_per_elem


def _global_fine_index(path: TreePath, refine_factor: int) -> GridIndex:
    """Encode one tree path as an integer index on its fine level.

    For a path ``(coarse, sub_1, ..., sub_L)``, each sub-index is a
    base-R digit.  Equal-level centres in adjacent parent nodes are
    therefore consecutive integers, which lets one scan internal and
    cross-node transitions with the same canonical ``g -> g+1`` rule.
    """

    layer = len(path) - 1
    if layer < 1:
        raise ValueError(f"A fine-centre path needs a sub-index: {path!r}")
    ndim = len(path[0])
    if any(len(idx) != ndim for idx in path):
        raise ValueError(f"Inconsistent path dimensionality: {path!r}")
    out = [path[0][d] * (refine_factor ** layer) for d in range(ndim)]
    for q in range(1, layer + 1):
        weight = refine_factor ** (layer - q)
        for d in range(ndim):
            out[d] += path[q][d] * weight
    return tuple(out)


def _tree_path_from_global_fine_index(
    global_index: GridIndex,
    coarse_shape: Tuple[int, ...],
    refine_factor: int,
    layer: int,
) -> TreePath:
    """Decode one same-level global lattice index into a base-R tree path."""
    if layer < 1:
        raise ValueError(f"Fine-tree layer must be positive, got {layer}")
    if refine_factor < 1:
        raise ValueError("refine_factor must be at least 1")
    if len(global_index) != len(coarse_shape):
        raise ValueError(
            f"Global index {global_index!r} does not match "
            f"coarse shape {coarse_shape!r}"
        )

    scale = refine_factor ** layer
    fine_shape = tuple(int(n) * scale for n in coarse_shape)
    if any(g < 0 or g >= fine_shape[d]
           for d, g in enumerate(global_index)):
        raise ValueError(
            f"Global index {global_index!r} is outside fine shape "
            f"{fine_shape!r}"
        )

    root = tuple(int(g) // scale for g in global_index)
    sub_indices: List[GridIndex] = []
    for depth in range(1, layer + 1):
        weight = refine_factor ** (layer - depth)
        sub_indices.append(tuple(
            (int(global_index[d]) // weight) % refine_factor
            for d in range(len(global_index))
        ))
    path = (root, *sub_indices)
    if _global_fine_index(path, refine_factor) != tuple(global_index):
        raise RuntimeError(
            f"Fine-index path round trip failed for {global_index!r}: "
            f"{path!r}"
        )
    return path


def _register_layer_node(
    registry: Dict[GridIndex, _RegistryEntryND],
    parent_path: TreePath,
    sub_axes_vals: List[np.ndarray],
    sub_points: np.ndarray,
    sub_labels_per_elem: Dict[str, np.ndarray],
    axes,
    refine_factor: int,
) -> None:
    """Add every centre of one solved node to the same-level registry."""

    for sub_idx in np.ndindex(*sub_points.shape):
        child_path = parent_path + (tuple(sub_idx),)
        global_idx = _global_fine_index(child_path, refine_factor)
        if global_idx in registry:
            other = registry[global_idx]
            raise RuntimeError(
                "Two refinement paths map to the same fine centre: "
                f"{other.path!r} and {child_path!r}")
        coords = {
            axes[d].name: float(sub_axes_vals[d][sub_idx[d]])
            for d in range(len(axes))
        }
        registry[global_idx] = _RegistryEntryND(
            global_index=global_idx,
            path=child_path,
            coords=coords,
            point=sub_points[sub_idx],
            labels_per_element={
                elem: int(labels[sub_idx])
                for elem, labels in sub_labels_per_elem.items()
            },
        )


def _iter_same_level_label_transitions(
    registry: Dict[GridIndex, _RegistryEntryND],
    context: _RefinementLabelContext,
) -> Iterator[Tuple[
    int, str, _RegistryEntryND, _RegistryEntryND, int, int,
]]:
    """Yield canonical label-changing neighbour pairs in stable N-D order."""

    if not registry:
        return
    ndim = len(next(iter(registry)))
    for global_idx in sorted(registry):
        low = registry[global_idx]
        for axis_dim in range(ndim):
            high_idx = list(global_idx)
            high_idx[axis_dim] += 1
            high = registry.get(tuple(high_idx))
            if high is None:
                continue
            for elem in context.principal:
                label_low = low.labels_per_element[elem]
                label_high = high.labels_per_element[elem]
                if (label_low == label_high
                        or label_low < 0 or label_high < 0):
                    continue
                yield (
                    axis_dim, elem, low, high,
                    label_low, label_high,
                )


def _same_level_transition_links(
    registry: Dict[GridIndex, _RegistryEntryND],
    context: _RefinementLabelContext,
) -> List[_RefinementTransitionND]:
    """Detect scheduler links without running geometric bisections."""

    return [
        _RefinementTransitionND(
            element_name=elem,
            axis=axis_dim,
            low_path=low.path,
            high_path=high.path,
            low_label=label_low,
            high_label=label_high,
        )
        for (
            axis_dim, elem, low, high, label_low, label_high,
        ) in _iter_same_level_label_transitions(registry, context)
    ]


def _scan_same_level_registry(
    registry: Dict[GridIndex, _RegistryEntryND],
    axes,
    solve_fn: PointSolveFn,
    context: _RefinementLabelContext,
    bisection_tol: float,
) -> Tuple[List[RefinedBoundaryPointND], List[_RefinementTransitionND]]:
    """Scan every available positive-axis neighbour exactly once.

    The global lattice removes the old node-local blind spot: a pair
    can straddle two root cells, two sibling nodes, or live within one
    node and is handled identically.  Negative labels are ignored so
    unresolved ``-1`` centres never create invented transitions.
    """

    refined_points: List[RefinedBoundaryPointND] = []
    links: List[_RefinementTransitionND] = []
    for (
        axis_dim, elem, low, high, label_low, label_high,
    ) in _iter_same_level_label_transitions(registry, context):
        lo_val = float(low.coords[axes[axis_dim].name])
        hi_val = float(high.coords[axes[axis_dim].name])
        if hi_val <= lo_val:
            raise RuntimeError(
                "Global refinement neighbours are not ordered in "
                f"physical space: {low.path!r}, {high.path!r}")
        x0 = None
        if low.point is not None and low.point.converged:
            x0 = low.point.x.copy()
        elif high.point is not None and high.point.converged:
            x0 = high.point.x.copy()

        e_idx = context.e_idx_per_elem[elem]
        mid_val = _bisect_along_axis(
            axis_dim, lo_val, hi_val, low.coords,
            label_low, label_high, solve_fn, x0,
            elem, e_idx, context.sp_ids, context.nu_elem,
            context.C_total, context.diss_eqs,
            context.name_to_int_per_elem[elem], axes,
            bisection_tol,
        )
        ref_coords = dict(low.coords)
        ref_coords[axes[axis_dim].name] = float(mid_val)
        refined_points.append(RefinedBoundaryPointND(
            coords=ref_coords,
            left_label=label_low,
            right_label=label_high,
            btype=_classify_sub(low.point, high.point),
            bisection_axis=axis_dim,
            element_name=elem,
            parent_path=low.path,
        ))
        links.append(_RefinementTransitionND(
            element_name=elem,
            axis=axis_dim,
            low_path=low.path,
            high_path=high.path,
            low_label=label_low,
            high_label=label_high,
        ))

    return refined_points, links


def _locate_parent_node(
    coarse_grid: NDGrid,
    target_path: TreePath,
) -> Tuple[dict, GridIndex]:
    """Return ``(parent_node, leaf_sub_idx)`` for a deeper target path."""

    if len(target_path) < 2 or not coarse_grid.refined_cells:
        raise KeyError(f"Cannot locate refinement path {target_path!r}")
    node = coarse_grid.refined_cells.get(target_path[0])
    if node is None:
        raise KeyError(f"Missing root refinement node {target_path[0]!r}")
    for sub_idx in target_path[1:-1]:
        child = node.get("children", {}).get(sub_idx)
        if child is None:
            raise KeyError(
                f"Missing child {sub_idx!r} in path {target_path!r}")
        node = child
    return node, target_path[-1]


def _ensure_tree_path_container(
    coarse_grid: NDGrid,
    target_path: TreePath,
    solve_fn: PointSolveFn,
    context: _RefinementLabelContext,
    refine_factor: int,
    x_cache: Optional[Dict[Tuple, np.ndarray]],
    debug: bool,
    on_node_complete: Optional[Callable] = None,
) -> List[_MaterializedNodeND]:
    """Lazily materialize sparse-tree ancestors for one fine-cell path.

    ``target_path`` identifies a cell at the current fine level that must be
    subdivided at the next level.  A full facet-vertex star can extend beyond
    the already solved adaptive patch, so its root node or an intermediate
    child node may not yet exist.  This helper solves only the missing R^N
    ancestor nodes needed to make :func:`_locate_parent_node` valid.

    Returns registration data for every newly solved node.  The caller uses
    the record whose ``parent_path`` is at the current lattice level to add
    all R^N centres from that container to the closure registry.
    """
    if len(target_path) < 2:
        raise ValueError(f"Fine target path is incomplete: {target_path!r}")
    ndim = coarse_grid.ndim
    if any(len(index) != ndim for index in target_path):
        raise ValueError(f"Inconsistent target path: {target_path!r}")
    root = target_path[0]
    if not in_bounds(root, coarse_grid.shape):
        raise ValueError(
            f"Target root {root!r} is outside {coarse_grid.shape!r}"
        )
    for sub_index in target_path[1:]:
        if any(i < 0 or i >= refine_factor for i in sub_index):
            raise ValueError(
                f"Sub-cell index {sub_index!r} is outside factor "
                f"{refine_factor} in {target_path!r}"
            )

    axes = coarse_grid.axes
    spacings = [float(axis.spacing) for axis in axes]
    if coarse_grid.refined_cells is None:
        coarse_grid.refined_cells = {}
    materialized: List[_MaterializedNodeND] = []

    node = coarse_grid.refined_cells.get(root)
    if node is None:
        centres = [float(axes[d].values[root[d]]) for d in range(ndim)]
        sub_axes_vals = _sub_axes_from_parent(
            centres, spacings, refine_factor,
        )
        node, sub_points, sub_labels_per_elem = _solve_layer_node(
            sub_axes_vals, axes, solve_fn,
            _get_initial_guess(coarse_grid, root), context,
            x_cache, debug,
        )
        coarse_grid.refined_cells[root] = node
        if on_node_complete is not None:
            on_node_complete(
                (root,), node, sub_points, sub_labels_per_elem,
            )
        materialized.append(_MaterializedNodeND(
            parent_path=(root,),
            sub_axes_vals=sub_axes_vals,
            sub_points=sub_points,
            sub_labels_per_elem=sub_labels_per_elem,
        ))

    # Ensure the containing node at each level above the target cell.  The
    # final sub-index is deliberately not materialized here; the ordinary
    # next-layer loop will solve that target once.
    parent_path: TreePath = (root,)
    for depth, sub_index in enumerate(target_path[1:-1], start=1):
        child = node.get("children", {}).get(sub_index)
        child_parent_path = parent_path + (sub_index,)
        if child is None:
            centres = [
                float(node["axes_vals"][d][sub_index[d]])
                for d in range(ndim)
            ]
            parent_sizes = [
                spacings[d] / (refine_factor ** depth)
                for d in range(ndim)
            ]
            x0 = None
            if x_cache is not None:
                coord_key = tuple(sorted(
                    (axes[d].name, centres[d]) for d in range(ndim)
                ))
                cached = x_cache.get(coord_key)
                if cached is not None:
                    x0 = cached.copy()
            sub_axes_vals = _sub_axes_from_parent(
                centres, parent_sizes, refine_factor,
            )
            child, sub_points, sub_labels_per_elem = _solve_layer_node(
                sub_axes_vals, axes, solve_fn, x0, context,
                x_cache, debug,
            )
            node["children"][sub_index] = child
            if on_node_complete is not None:
                on_node_complete(
                    child_parent_path,
                    child,
                    sub_points,
                    sub_labels_per_elem,
                )
            materialized.append(_MaterializedNodeND(
                parent_path=child_parent_path,
                sub_axes_vals=sub_axes_vals,
                sub_points=sub_points,
                sub_labels_per_elem=sub_labels_per_elem,
            ))
        node = child
        parent_path = child_parent_path
    return materialized


def _cell_refinement_node(
    coarse_grid: NDGrid,
    cell_path: TreePath,
) -> Optional[dict]:
    """Return the child node refining one fine cell, if it exists."""

    parent_node, leaf_sub_idx = _locate_parent_node(
        coarse_grid, cell_path,
    )
    return (parent_node.get("children") or {}).get(leaf_sub_idx)


def _refine_registered_cell(
    coarse_grid: NDGrid,
    cell_path: TreePath,
    registry: Dict[GridIndex, _RegistryEntryND],
    next_registry: Dict[GridIndex, _RegistryEntryND],
    solve_fn: PointSolveFn,
    context: _RefinementLabelContext,
    refine_factor: int,
    x_cache: Optional[Dict[Tuple, np.ndarray]],
    debug: bool,
    on_node_complete: Optional[Callable] = None,
) -> bool:
    """Subdivide one available fine cell and register all R^N children."""

    depth = len(cell_path) - 1
    if depth < 1:
        raise ValueError(f"Expected a fine-cell path, got {cell_path!r}")
    global_index = _global_fine_index(cell_path, refine_factor)
    entry = registry.get(global_index)
    if entry is None:
        raise RuntimeError(
            f"Cannot refine unregistered depth-{depth} cell {cell_path!r}"
        )

    existing = _cell_refinement_node(coarse_grid, cell_path)
    if existing is not None:
        expected_children = {
            _global_fine_index(cell_path + (tuple(sub_idx),), refine_factor)
            for sub_idx in np.ndindex(
                *tuple([refine_factor] * coarse_grid.ndim)
            )
        }
        missing = expected_children - set(next_registry)
        if missing:
            raise RuntimeError(
                "A pre-existing refinement node is absent from the in-memory "
                f"depth-{depth + 1} registry: {sorted(missing)[:8]!r}"
            )
        return False

    parent_node, leaf_sub_idx = _locate_parent_node(
        coarse_grid, cell_path,
    )
    centres = [
        float(parent_node["axes_vals"][d][leaf_sub_idx[d]])
        for d in range(coarse_grid.ndim)
    ]
    parent_sizes = [
        float(axis.spacing) / (refine_factor ** depth)
        for axis in coarse_grid.axes
    ]
    sub_axes_vals = _sub_axes_from_parent(
        centres, parent_sizes, refine_factor,
    )
    x0 = None
    if entry.point is not None and entry.point.converged:
        x0 = entry.point.x.copy()
    elif x_cache is not None:
        coord_key = tuple(sorted(
            (coarse_grid.axes[d].name, centres[d])
            for d in range(coarse_grid.ndim)
        ))
        cached = x_cache.get(coord_key)
        if cached is not None:
            x0 = cached.copy()

    node, sub_points, sub_labels_per_elem = _solve_layer_node(
        sub_axes_vals, coarse_grid.axes, solve_fn, x0, context,
        x_cache, debug,
    )
    parent_node["children"][leaf_sub_idx] = node
    if on_node_complete is not None:
        on_node_complete(
            cell_path, node, sub_points, sub_labels_per_elem,
        )
    _register_layer_node(
        next_registry, cell_path, sub_axes_vals, sub_points,
        sub_labels_per_elem, coarse_grid.axes, refine_factor,
    )
    return True


def _build_hierarchical_vertex_closure(
    coarse_grid: NDGrid,
    layer_one_registry: Dict[GridIndex, _RegistryEntryND],
    solve_fn: PointSolveFn,
    context: _RefinementLabelContext,
    refine_factor: int,
    n_layers: int,
    x_cache: Optional[Dict[Tuple, np.ndarray]],
    debug: bool,
    initial_registries: Optional[
        Dict[int, Dict[GridIndex, _RegistryEntryND]]
    ] = None,
    on_node_complete: Optional[Callable] = None,
) -> Dict[int, Dict[GridIndex, _RegistryEntryND]]:
    """Construct the least finite N-D facet-vertex refinement closure.

    A support solve at depth ``q`` can reveal facets not only at ``q`` but
    also in newly created ancestor blocks at shallower depths.  Registries
    are therefore retained for every depth and revisited through a global
    dirty-depth work set.  For each ``q < n_layers``, every resolved
    label-changing facet among materialized depth-q cells ultimately has all
    in-domain vertex-incident cells subdivided at depth ``q + 1``.

    No coarse facet or junction is reinserted at a later depth.  Junction
    neighbourhoods arise solely from the union of the current depth's facet
    stars, which lets their resolved location change between depths.

    In a worst-case checkerboard or percolating interface the correct least
    fixed point can be the complete finite grid.  The implementation never
    clips that closure silently; domain-size assertions guard bookkeeping
    errors rather than impose an approximation budget.
    """

    registries: Dict[int, Dict[GridIndex, _RegistryEntryND]] = dict(
        initial_registries or {}
    )
    registries[1] = layer_one_registry
    if n_layers <= 1:
        return registries

    targets: Dict[int, List[TreePath]] = {
        depth: [] for depth in range(1, n_layers)
    }
    target_seen = {
        depth: set() for depth in range(1, n_layers)
    }
    dirty_depths = {1}
    scan_counts = {depth: 0 for depth in range(1, n_layers)}
    refined_counts = {depth: 0 for depth in range(1, n_layers)}
    support_counts = {depth: 0 for depth in range(1, n_layers + 1)}
    while dirty_depths:
        depth = min(dirty_depths)
        dirty_depths.remove(depth)
        registry = registries.setdefault(depth, {})
        scan_counts[depth] += 1

        links = _same_level_transition_links(registry, context)

        for path in _stable_transition_vertex_paths(
            links, coarse_grid.shape, depth, refine_factor,
        ):
            if path not in target_seen[depth]:
                target_seen[depth].add(path)
                targets[depth].append(path)

        fine_cell_bound = int(np.prod(coarse_grid.shape)) * (
            refine_factor ** (depth * coarse_grid.ndim)
        )
        if (len(registry) > fine_cell_bound
                or len(targets[depth]) > fine_cell_bound):
            raise RuntimeError(
                f"Depth-{depth} N-D closure exceeded finite domain bound "
                f"{fine_cell_bound}"
            )

        for path in targets[depth]:
            global_index = _global_fine_index(path, refine_factor)
            if global_index not in registry:
                records = _ensure_tree_path_container(
                    coarse_grid, path, solve_fn, context,
                    refine_factor, x_cache, debug,
                    on_node_complete=on_node_complete,
                )
                for record in records:
                    record_depth = len(record.parent_path)
                    record_registry = registries.setdefault(
                        record_depth, {},
                    )
                    before = len(record_registry)
                    _register_layer_node(
                        record_registry,
                        record.parent_path,
                        record.sub_axes_vals,
                        record.sub_points,
                        record.sub_labels_per_elem,
                        coarse_grid.axes,
                        refine_factor,
                    )
                    if len(record_registry) > before:
                        support_counts[record_depth] = (
                            support_counts.get(record_depth, 0) + 1
                        )
                        if record_depth < n_layers:
                            dirty_depths.add(record_depth)

            if global_index not in registry:
                raise RuntimeError(
                    "N-D hierarchical closure failed to materialize "
                    f"depth-{depth} target {path!r}"
                )

            next_registry = registries.setdefault(depth + 1, {})
            if _refine_registered_cell(
                coarse_grid, path, registry, next_registry,
                solve_fn, context, refine_factor, x_cache, debug,
                on_node_complete=on_node_complete,
            ):
                refined_counts[depth] += 1
                if depth + 1 < n_layers:
                    dirty_depths.add(depth + 1)

    # Strong postcondition: every currently visible facet star is present and
    # each of its cells owns a child node at the next requested depth.
    for depth in range(1, n_layers):
        registry = registries.get(depth, {})
        links = _same_level_transition_links(registry, context)
        for path in _stable_transition_vertex_paths(
            links, coarse_grid.shape, depth, refine_factor,
        ):
            global_index = _global_fine_index(path, refine_factor)
            if global_index not in registry:
                raise RuntimeError(
                    f"Depth-{depth} closure target is not materialized: "
                    f"{path!r}"
                )
            if _cell_refinement_node(coarse_grid, path) is None:
                raise RuntimeError(
                    f"Depth-{depth} closure target is not refined: "
                    f"{path!r}"
                )

    if debug:
        for depth in range(1, n_layers):
            print(
                f"[refiner] Depth {depth} hierarchical closure: "
                f"{len(targets[depth])} targets, "
                f"{refined_counts[depth]} new child nodes, "
                f"{support_counts.get(depth, 0)} support nodes, "
                f"{scan_counts[depth]} scan pass(es)",
                flush=True,
            )
    return registries


def _run_layer_one(
    coarse_grid: NDGrid,
    boundary_cells: List[BoundaryCellND],
    solve_fn: PointSolveFn,
    context: _RefinementLabelContext,
    refine_factor: int,
    bisection_tol: float,
    debug: bool,
    x_cache: Optional[Dict[Tuple, np.ndarray]],
    initial_registry: Optional[
        Dict[GridIndex, _RegistryEntryND]
    ] = None,
    on_node_complete: Optional[Callable] = None,
) -> Tuple[
    List[RefinedBoundaryPointND],
    List[_RefinementTransitionND],
    Dict[GridIndex, _RegistryEntryND],
]:
    """Solve all facet-vertex incident coarse cells and scan layer 1."""

    axes = coarse_grid.axes
    ndim = coarse_grid.ndim
    spacings = [ax.spacing for ax in axes]
    targets = _stable_incident_root_indices(boundary_cells, coarse_grid.shape)
    if coarse_grid.refined_cells is None:
        coarse_grid.refined_cells = {}

    if debug:
        sub_desc = "x".join([str(refine_factor)] * ndim)
        print(
            f"[refiner] Refining {len(targets)} unique incident cells "
            f"from {len(boundary_cells)} boundary facets "
            f"({sub_desc} sub-grid per cell)",
            flush=True,
        )

    registry: Dict[GridIndex, _RegistryEntryND] = dict(
        initial_registry or {}
    )
    completed_roots = {
        entry.path[0]
        for entry in registry.values()
        if entry.path
    }
    for pos, cell_multi in enumerate(targets, start=1):
        if cell_multi in completed_roots:
            continue
        centres = [
            float(axes[d].values[cell_multi[d]]) for d in range(ndim)
        ]
        sub_axes_vals = _sub_axes_from_parent(
            centres, spacings, refine_factor)
        node, sub_points, sub_labels_per_elem = _solve_layer_node(
            sub_axes_vals, axes, solve_fn,
            _get_initial_guess(coarse_grid, cell_multi), context,
            x_cache, debug,
        )
        coarse_grid.refined_cells[cell_multi] = node
        if on_node_complete is not None:
            on_node_complete(
                (cell_multi,), node, sub_points, sub_labels_per_elem,
            )
        _register_layer_node(
            registry, (cell_multi,), sub_axes_vals, sub_points,
            sub_labels_per_elem, axes, refine_factor,
        )
        if debug and pos % max(1, len(targets) // 10) == 0:
            print(
                f"[refiner]   {pos}/{len(targets)} incident cells solved",
                flush=True,
            )

    points, links = _scan_same_level_registry(
        registry, axes, solve_fn, context, bisection_tol)
    if debug:
        print(
            f"[refiner] Layer 1 complete: {len(points)} transition points "
            f"from {len(targets)} unique incident cells",
            flush=True,
        )
    return points, links, registry


# ==================================================================
#  Public single-pass and multi-layer refinement
# ==================================================================

def _restore_refinement_node_records(
    coarse_grid: NDGrid,
    records: Optional[List[dict]],
    refine_factor: int,
    x_cache: Optional[Dict[Tuple, np.ndarray]],
) -> Dict[int, Dict[GridIndex, _RegistryEntryND]]:
    """Reattach independently committed refinement nodes and registries."""

    registries: Dict[int, Dict[GridIndex, _RegistryEntryND]] = {}
    if not records:
        return registries
    coarse_grid.refined_cells = {}
    for record in sorted(
        records,
        key=lambda row: (
            len(row.get("parent_path") or ()),
            row.get("parent_path") or (),
        ),
    ):
        parent_path = tuple(
            tuple(int(value) for value in index)
            for index in (record.get("parent_path") or ())
        )
        node = record.get("node")
        sub_points = record.get("sub_points")
        sub_labels = record.get("sub_labels_per_element")
        if (
            not parent_path
            or not isinstance(node, dict)
            or not isinstance(sub_points, np.ndarray)
            or not isinstance(sub_labels, dict)
        ):
            continue
        node["children"] = {}
        if len(parent_path) == 1:
            coarse_grid.refined_cells[parent_path[0]] = node
        else:
            parent_node, leaf_sub_idx = _locate_parent_node(
                coarse_grid, parent_path,
            )
            parent_node.setdefault("children", {})[leaf_sub_idx] = node

        registry = registries.setdefault(len(parent_path), {})
        _register_layer_node(
            registry,
            parent_path,
            node["axes_vals"],
            sub_points,
            sub_labels,
            coarse_grid.axes,
            refine_factor,
        )
        if x_cache is not None:
            for sub_idx in np.ndindex(*sub_points.shape):
                point = sub_points[sub_idx]
                if point is None or not getattr(point, "converged", False):
                    continue
                coords = {
                    coarse_grid.axes[d].name: float(
                        node["axes_vals"][d][sub_idx[d]]
                    )
                    for d in range(coarse_grid.ndim)
                }
                x_cache[tuple(sorted(coords.items()))] = point.x.copy()
    return registries

def refine_boundaries_nd(
    coarse_grid: NDGrid,
    boundary_cells: List[BoundaryCellND],
    solve_fn: PointSolveFn,
    built_system,
    refine_factor: int = REFINE_FACTOR,
    bisection_tol: float = BISECTION_TOL,
    debug: bool = DEBUG,
    x_cache: Optional[Dict[Tuple, "np.ndarray"]] = None,
) -> List[RefinedBoundaryPointND]:
    """Refine all cells touching every canonical boundary-facet vertex.

    Boundary records remain one-per-facet.  The scheduler expands each
    record to the complete in-domain N-D vertex-incidence neighbourhood,
    solves each R^N block once, and detects transitions on a global
    same-level lattice.  Consequently corner/edge transitions and
    cross-root transitions are not lost, while unresolved centres remain
    excluded.
    """

    if refine_factor < 1:
        raise ValueError("refine_factor must be at least 1")
    context = _build_label_context(coarse_grid, built_system)
    points, _, _ = _run_layer_one(
        coarse_grid, boundary_cells, solve_fn, context,
        refine_factor, bisection_tol, debug, x_cache,
    )
    return points


def refine_boundaries_multilayer_nd(
    coarse_grid: NDGrid,
    boundary_cells: List[BoundaryCellND],
    solve_fn: PointSolveFn,
    built_system,
    refine_factor: int = REFINE_FACTOR,
    n_layers: int = REFINE_LAYERS,
    bisection_tol: float = BISECTION_TOL,
    debug: bool = DEBUG,
    collect_x_cache: bool = False,
    on_layer_complete: Optional[Callable[[int, List, Optional[Dict]], None]] = None,
    on_node_complete: Optional[Callable] = None,
    resume_node_records: Optional[List[dict]] = None,
):
    """Cascaded N-D vertex-star refinement on a same-level lattice.

    Layer 1 refines every coarse cell touching a vertex of every supplied
    facet.
    Each detected transition is a canonical fine-grid facet.  The next layer
    refines the stable unique union of every in-domain cell touching any
    vertex of those facets.  Encoding tree paths as base-R global indices
    lets one canonical scan detect transitions within nodes and across
    root/sibling boundaries.

    Public return and callback shapes are unchanged.  With
    ``collect_x_cache=True`` the function returns ``(final_points,
    x_cache)``; otherwise it returns only ``final_points``.  The callback
    still receives ``(layer_index, points_for_that_layer, x_cache)``.
    """

    if refine_factor < 1:
        raise ValueError("refine_factor must be at least 1")
    x_cache: Optional[Dict[Tuple, np.ndarray]] = (
        {} if collect_x_cache else None
    )
    context = _build_label_context(coarse_grid, built_system)
    axes = coarse_grid.axes
    restored_registries = _restore_refinement_node_records(
        coarse_grid,
        resume_node_records,
        refine_factor,
        x_cache,
    )
    if debug and resume_node_records:
        print(
            f"[refiner] Replayed {len(resume_node_records)} committed "
            "refinement nodes",
            flush=True,
        )

    layer_one_points, _, layer_one_registry = _run_layer_one(
        coarse_grid, boundary_cells, solve_fn, context,
        refine_factor, bisection_tol, debug, x_cache,
        initial_registry=restored_registries.get(1),
        on_node_complete=on_node_complete,
    )
    if n_layers <= 1:
        if on_layer_complete is not None:
            try:
                on_layer_complete(1, layer_one_points, x_cache)
            except Exception as exc:
                if debug:
                    print(
                        f"[refiner] on_layer_complete(1) failed: {exc}",
                        flush=True,
                    )
        return ((layer_one_points, x_cache) if collect_x_cache
                else layer_one_points)

    registries = _build_hierarchical_vertex_closure(
        coarse_grid,
        layer_one_registry,
        solve_fn,
        context,
        refine_factor,
        n_layers,
        x_cache,
        debug,
        initial_registries=restored_registries,
        on_node_complete=on_node_complete,
    )

    # Run expensive bisection geometry only after the label/refinement work
    # queues have reached closure.  Callbacks remain layer ordered; the dense
    # snapshot assembler uses the requested effective factor and therefore
    # ignores already-built deeper children for earlier-layer snapshots.
    reported_pts: List[RefinedBoundaryPointND] = []
    for layer in range(1, n_layers + 1):
        registry = registries.get(layer, {})
        current_pts, _ = _scan_same_level_registry(
            registry, axes, solve_fn, context, bisection_tol,
        )
        reported_pts = current_pts
        if debug:
            print(
                f"[refiner] Layer {layer} complete: "
                f"{len(current_pts)} sampled transition points from "
                f"{len(registry)} materialized cells",
                flush=True,
            )
        if on_layer_complete is not None:
            try:
                on_layer_complete(layer, reported_pts, x_cache)
            except Exception as exc:
                if debug:
                    print(
                        f"[refiner] on_layer_complete({layer}) failed: "
                        f"{exc}",
                        flush=True,
                    )

    return (reported_pts, x_cache) if collect_x_cache else reported_pts


# ==================================================================
#  Bisection along any axis (unified)
# ==================================================================

def _bisect_along_axis(
    axis_dim: int,
    lo_val: float,
    hi_val: float,
    base_coords: Dict[str, float],
    label_lo: int,
    label_hi: int,
    solve_fn: PointSolveFn,
    x0: Optional[np.ndarray],
    elem_name: str,
    e_idx: List[int],
    sp_ids: List[str],
    nu_elem: np.ndarray,
    C_total: np.ndarray,
    diss_eqs,
    name_to_int: Dict[str, int],
    axes,
    tol: float,
) -> float:
    """
    Bisection along axis *axis_dim* with all other coordinates fixed
    at *base_coords* values.  Returns the midpoint coordinate where
    the label transition occurs.
    """
    from .labeler import _dominant_label_for_element

    axis_name = axes[axis_dim].name
    x_guess = x0

    for _ in range(BISECTION_MAX):
        if (hi_val - lo_val) < tol:
            break
        mid = (lo_val + hi_val) / 2.0

        # Build coords for this probe point
        probe_coords = dict(base_coords)
        probe_coords[axis_name] = mid

        lbl, x_guess = _label_at(
            probe_coords, solve_fn, x_guess,
            elem_name, e_idx, sp_ids, nu_elem, C_total, diss_eqs,
            name_to_int)

        if lbl == label_lo:
            lo_val = mid
        else:
            hi_val = mid

    return (lo_val + hi_val) / 2.0


def _label_at(
    coords: Dict[str, float],
    solve_fn: PointSolveFn,
    x0: Optional[np.ndarray],
    elem_name: str,
    e_idx: List[int],
    sp_ids: List[str],
    nu_elem: np.ndarray,
    C_total: np.ndarray,
    diss_eqs,
    name_to_int: Dict[str, int],
) -> Tuple[int, Optional[np.ndarray]]:
    """Solve one point and return (integer_label, updated_x0)."""
    from .labeler import _dominant_label_for_element

    res = solve_fn(coords, x0)
    if not res.converged:
        return -1, x0
    lbl_name = _dominant_label_for_element(
        res, elem_name, e_idx, sp_ids, nu_elem,
        float(np.sum(C_total[e_idx])), diss_eqs)
    return name_to_int.get(lbl_name, -1), res.x.copy()


# ==================================================================
#  Helpers
# ==================================================================

def _get_initial_guess(grid: NDGrid,
                       idx: Tuple[int, ...]) -> Optional[np.ndarray]:
    """Get initial guess x0 from the coarse grid at *idx* or neighbours."""
    pt = grid.points[idx]
    if pt is not None and pt.converged:
        return pt.x.copy()

    # Try cardinal neighbours, then diagonal
    for off in all_offsets(grid.ndim):
        nb = add_offset(idx, off)
        if in_bounds(nb, grid.shape):
            nb_pt = grid.points[nb]
            if nb_pt is not None and nb_pt.converged:
                return nb_pt.x.copy()
    return None


def _classify_sub(pt1, pt2) -> str:
    """Classify boundary type from two sub-grid points."""
    s1 = set(pt1.active_solid_ids) if pt1 and pt1.converged else set()
    s2 = set(pt2.active_solid_ids) if pt2 and pt2.converged else set()
    if s1 != s2:
        if s1 and s2:
            return "solid_solid"
        return "solid_onset"
    return "aqueous_crossover"


