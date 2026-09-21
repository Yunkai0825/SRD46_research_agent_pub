"""
boundary_detector.py
====================
Scan the labelled N-D grid for canonical transition facets (label
transitions between adjacent grid cells along each axis).

Replaces the legacy 2-D detector which used separate horizontal and
vertical scan loops.  The N-D version loops over each axis dimension,
comparing ``labels[idx]`` with ``labels[idx + 1 along that axis]``.

Public API
----------
- ``detect_boundary_cells_nd``  — returns ``List[BoundaryCellND]``
"""

from __future__ import annotations

import numpy as np
from itertools import product
from typing import Dict, List, Optional, Sequence, Tuple

from ..data_types import NDGrid, BoundaryCellND
from ..settings import DEBUG


def detect_boundary_cells_nd(
    grid: NDGrid,
    element_name: Optional[str] = None,
    debug: bool = DEBUG,
) -> List[BoundaryCellND]:
    """
    Scan the label map for adjacent-pair transitions along each axis.

    One record is emitted per physical transition facet.  Its ``index`` is
    the lower-index incident cell and ``axis`` identifies the +1 incident
    cell.  Consumers that need refinement targets expand each record to all
    in-domain cells touching any facet vertex with
    :func:`get_boundary_cell_indices`; topology consumers keep the canonical
    facet records unchanged.

    For an N-D grid with axes ``[a0, a1, ..., a_{N-1}]``, this checks
    every pair of adjacent cells along every axis dimension.

    Parameters
    ----------
    grid          : labelled NDGrid
    element_name  : if given, use ``labels_per_element[element_name]``;
                    otherwise use ``grid.labels``
    debug         : print debug info

    Returns
    -------
    List of BoundaryCellND objects.
    """
    if element_name and grid.labels_per_element:
        labels = grid.labels_per_element[element_name]
        catalog = grid.label_catalog_per_element[element_name]
    else:
        labels = grid.labels
        catalog = grid.label_catalog

    if labels is None:
        raise ValueError("Grid not labelled yet — call label_grid_nd() first")

    shape = labels.shape
    ndim = len(shape)
    boundaries: List[BoundaryCellND] = []

    # Scan along each axis dimension
    for axis_dim in range(ndim):
        axis_name = grid.axes[axis_dim].name
        n_along = shape[axis_dim]

        # Iterate over all multi-indices, but restrict the scanning axis
        # to range [0, n_along - 1) so we can compare idx with idx+1.
        for idx in np.ndindex(*shape):
            if idx[axis_dim] >= n_along - 1:
                continue  # no right neighbour along this axis

            # Build the neighbour index (shift +1 along axis_dim)
            nb = list(idx)
            nb[axis_dim] += 1
            nb = tuple(nb)

            L = labels[idx]
            R = labels[nb]
            if L != R and L >= 0 and R >= 0:
                btype = _classify_boundary(grid, idx, nb)
                boundaries.append(BoundaryCellND(
                    index=idx,
                    axis=axis_dim,
                    axis_name=axis_name,
                    left_label=int(L),
                    right_label=int(R),
                    btype=btype,
                ))

    if debug:
        type_counts: Dict[str, int] = {}
        for bc in boundaries:
            type_counts[bc.btype] = type_counts.get(bc.btype, 0) + 1
        elem_tag = f" ({element_name})" if element_name else ""
        print(f"[detector] Found {len(boundaries)} transition facets{elem_tag}: "
              f"{type_counts}")

        pair_counts: Dict[Tuple[int, int], int] = {}
        for bc in boundaries:
            pair = (min(bc.left_label, bc.right_label),
                    max(bc.left_label, bc.right_label))
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        for (a, b), cnt in sorted(pair_counts.items(),
                                   key=lambda x: -x[1])[:10]:
            name_a = catalog.get(a, str(a)) if catalog else str(a)
            name_b = catalog.get(b, str(b)) if catalog else str(b)
            print(f"  {name_a} <-> {name_b}: {cnt} cells")

    return boundaries


def get_boundary_cell_indices(
    boundaries: List[BoundaryCellND],
    shape: Optional[Sequence[int]] = None,
) -> List[Tuple[int, ...]]:
    """Return the N-D cells touching any vertex of a transition facet.

    ``BoundaryCellND`` stores one canonical, oriented label-changing facet:
    ``index`` is the lower normal-side cell and ``axis`` points toward the
    upper normal-side cell.  Refining only that pair misses cells that touch
    the facet at an edge or corner.  For refinement, each facet therefore
    contributes both normal-side indices and, in every transverse dimension,
    the lower, aligned, and upper neighbours.  An interior N-D facet can
    consequently schedule ``2 * 3**(N-1)`` cells; domain clipping reduces
    that count at an outer boundary.

    The stable first-seen order makes runs reproducible and deduplication
    prevents cells shared by adjacent facet vertices from being solved more
    than once.  *shape* is required because vertex incidence must be clipped
    against the actual grid domain.
    """
    if shape is None:
        raise ValueError(
            "shape is required to expand boundary-facet vertices into "
            "in-domain refinement cells"
        )

    seen = set()
    indices: List[Tuple[int, ...]] = []
    for bc in boundaries:
        for incident in get_facet_vertex_incident_indices(
            bc.index, bc.axis, shape,
        ):
            if incident not in seen:
                seen.add(incident)
                indices.append(incident)
    return indices


def get_facet_vertex_incident_indices(
    index: Sequence[int],
    axis: int,
    shape: Sequence[int],
) -> List[Tuple[int, ...]]:
    """Expand one canonical N-D facet to its vertex-incident cells.

    The normal-side pair is returned first, followed by any remaining
    in-domain cells in deterministic product order.  This primitive is used
    for both coarse facets and same-level adaptive-refinement links.
    """
    low = tuple(int(i) for i in index)
    grid_shape = tuple(int(n) for n in shape)
    ndim = len(low)
    if not grid_shape or any(n <= 0 for n in grid_shape):
        raise ValueError(f"Invalid grid shape: {grid_shape!r}")
    if ndim != len(grid_shape):
        raise ValueError(
            f"Boundary facet index {low} does not match grid "
            f"dimensionality {grid_shape}"
        )
    if not 0 <= axis < ndim:
        raise ValueError(
            f"Boundary facet axis {axis} is invalid for index {low}"
        )

    high_list = list(low)
    high_list[axis] += 1
    high = tuple(high_list)
    for incident in (low, high):
        if any(i < 0 or i >= grid_shape[d]
               for d, i in enumerate(incident)):
            raise ValueError(
                f"Boundary facet {low} + axis {axis} has out-of-bounds "
                f"incident cell {incident} for {grid_shape}"
            )

    result = [low, high]
    seen = {low, high}
    offset_choices = [
        (0, 1) if d == axis else (-1, 0, 1)
        for d in range(ndim)
    ]
    for offsets in product(*offset_choices):
        incident = tuple(low[d] + offsets[d] for d in range(ndim))
        if any(i < 0 or i >= grid_shape[d]
               for d, i in enumerate(incident)):
            continue
        if incident not in seen:
            seen.add(incident)
            result.append(incident)
    return result


def _classify_boundary(grid: NDGrid,
                       idx1: Tuple[int, ...],
                       idx2: Tuple[int, ...]) -> str:
    """Classify boundary type from the two adjacent points."""
    pt1 = grid.points[idx1]
    pt2 = grid.points[idx2]

    solids1 = set(pt1.active_solid_ids) if pt1 and pt1.converged else set()
    solids2 = set(pt2.active_solid_ids) if pt2 and pt2.converged else set()

    if solids1 != solids2:
        if solids1 and solids2:
            return "solid_solid"
        return "solid_onset"
    return "aqueous_crossover"
