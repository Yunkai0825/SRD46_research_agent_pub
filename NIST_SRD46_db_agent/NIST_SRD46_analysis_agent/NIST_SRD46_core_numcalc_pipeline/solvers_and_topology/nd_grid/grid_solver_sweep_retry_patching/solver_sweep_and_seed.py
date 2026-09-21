"""
solver_search_and_seed.py
=========================
Seed selection and *forward-expansion* search phases of the coarse
N-D grid solve.  Package-private: callable only via
:meth:`NDGridSolver.solve`.

Functions
---------
- :func:`default_seed`        — center of an N-D grid.
- :func:`get_neighbor_guess`  — pick nearest converged neighbour's x.
- :func:`bfs_fill`            — phase 2 BFS flood-fill from seeds.
- :func:`axis_sweeps`         — phase 3 axis-by-axis directional sweeps.
"""

from __future__ import annotations

import time
from collections import deque
from itertools import product as _product
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..data_types import (
    NDGrid, PointResult,
    add_offset, in_bounds, all_offsets,
)


PointSolveFn = Callable[[Dict[str, float], Optional[np.ndarray]], PointResult]
PointProgressFn = Callable[[Tuple[int, ...], PointResult], None]


# ======================================================================
#  Seed helpers
# ======================================================================

def default_seed(shape: Tuple[int, ...]) -> Tuple[int, ...]:
    """Return the center index of an N-D grid."""
    return tuple(s // 2 for s in shape)


def get_neighbor_guess(
    grid: NDGrid,
    idx: Tuple[int, ...],
    offsets: List[Tuple[int, ...]],
) -> Optional[np.ndarray]:
    """Pick the nearest converged neighbour's ``x`` as an initial guess.

    Cardinal neighbours (passed in ``offsets``) are tried first because
    they sit geometrically closer; falls back to diagonal neighbours
    via :func:`all_offsets`.
    """
    shape = grid.shape
    for off in offsets:
        nidx = add_offset(idx, off)
        if (in_bounds(nidx, shape)
                and grid.converged_mask[nidx]
                and not np.any(np.isnan(grid.x_cache[nidx]))):
            return grid.x_cache[nidx].copy()

    diag_off = all_offsets(grid.ndim)
    for off in diag_off:
        nidx = add_offset(idx, off)
        if (in_bounds(nidx, shape)
                and grid.converged_mask[nidx]
                and not np.any(np.isnan(grid.x_cache[nidx]))):
            return grid.x_cache[nidx].copy()

    return None


# ======================================================================
#  Phase 2 — BFS flood-fill
# ======================================================================

def bfs_fill(
    grid: NDGrid,
    offsets: List[Tuple[int, ...]],
    point_solve_fn: PointSolveFn,
    debug: bool = False,
    on_point_complete: Optional[PointProgressFn] = None,
) -> int:
    """BFS from all currently converged points.

    Returns the number of additional points solved during this phase.
    """
    shape = grid.shape
    visited = np.zeros(shape, dtype=bool)
    queue: deque = deque()

    # Enqueue neighbours of all converged seeds.
    for idx in zip(*np.where(grid.converged_mask)):
        idx = tuple(int(i) for i in idx)
        visited[idx] = True
        for off in offsets:
            nidx = add_offset(idx, off)
            if in_bounds(nidx, shape) and not visited[nidx]:
                visited[nidx] = True
                queue.append(nidx)

    # If no seeds yet, enqueue every cell.
    if not queue:
        for idx in np.ndindex(*shape):
            if not visited[idx]:
                visited[idx] = True
                queue.append(idx)

    recovered = 0
    t0 = time.time()
    next_report = t0 + 10.0
    n_attempted = 0

    while queue:
        idx = queue.popleft()

        if grid.converged_mask[idx]:
            for off in offsets:
                nidx = add_offset(idx, off)
                if in_bounds(nidx, shape) and not visited[nidx]:
                    visited[nidx] = True
                    queue.append(nidx)
            continue

        x0 = get_neighbor_guess(grid, idx, offsets)
        coords = grid.coords_at(idx)
        result = point_solve_fn(coords, x0)
        grid.points[idx] = result
        if on_point_complete is not None:
            on_point_complete(idx, result)
        n_attempted += 1

        if result.converged:
            grid.converged_mask[idx] = True
            grid.x_cache[idx] = result.x
            recovered += 1
            for off in offsets:
                nidx = add_offset(idx, off)
                if in_bounds(nidx, shape) and not visited[nidx]:
                    visited[nidx] = True
                    queue.append(nidx)

        if debug:
            now = time.time()
            if now >= next_report:
                total = int(np.prod(shape))
                total_conv = int(grid.converged_mask.sum())
                print(f"[nd_grid]   BFS {n_attempted} attempted, "
                      f"conv={total_conv}/{total} "
                      f"({100*total_conv/total:.1f}%)", flush=True)
                next_report = now + 10.0

    # Mop up any cell never touched (no path from any seed).
    for idx in np.ndindex(*shape):
        if grid.points[idx] is None:
            x0 = get_neighbor_guess(grid, idx, offsets)
            coords = grid.coords_at(idx)
            result = point_solve_fn(coords, x0)
            grid.points[idx] = result
            if on_point_complete is not None:
                on_point_complete(idx, result)
            if result.converged:
                grid.converged_mask[idx] = True
                grid.x_cache[idx] = result.x
                recovered += 1

    return recovered


# ======================================================================
#  Phase 3 — axis sweeps
# ======================================================================

def _sweep_iter(
    shape: Tuple[int, ...],
    axis_dim: int,
    axis_range,
):
    """Yield multi-indices with ``axis_dim`` varying via ``axis_range``
    and all other dimensions in standard order."""
    ndim = len(shape)
    other_ranges = [range(shape[d]) if d != axis_dim else [0]
                    for d in range(ndim)]
    for combo in _product(*other_ranges):
        for a in axis_range:
            idx = list(combo)
            idx[axis_dim] = a
            yield tuple(idx)


def _sweep_along_axis(
    grid: NDGrid,
    axis_dim: int,
    direction: int,
    point_solve_fn: PointSolveFn,
    on_point_complete: Optional[PointProgressFn] = None,
) -> int:
    """Sweep the grid along one axis, seeding from that direction."""
    shape = grid.shape
    ndim = grid.ndim
    recovered = 0

    n = shape[axis_dim]
    sweep_range = range(n) if direction == 1 else range(n - 1, -1, -1)

    seed_off = [0] * ndim
    seed_off[axis_dim] = -direction
    seed_off = tuple(seed_off)

    other_offsets = []
    for d2 in range(ndim):
        if d2 == axis_dim:
            continue
        for delta in (-1, +1):
            o = [0] * ndim
            o[d2] = delta
            other_offsets.append(tuple(o))

    for idx in _sweep_iter(shape, axis_dim, sweep_range):
        if grid.converged_mask[idx]:
            continue

        x0 = None
        nidx = add_offset(idx, seed_off)
        if in_bounds(nidx, shape) and grid.converged_mask[nidx]:
            x0 = grid.x_cache[nidx].copy()

        if x0 is None:
            for off in other_offsets:
                nidx = add_offset(idx, off)
                if (in_bounds(nidx, shape) and grid.converged_mask[nidx]
                        and not np.any(np.isnan(grid.x_cache[nidx]))):
                    x0 = grid.x_cache[nidx].copy()
                    break

        if x0 is None:
            continue

        coords = grid.coords_at(idx)
        result = point_solve_fn(coords, x0)
        if on_point_complete is not None:
            on_point_complete(idx, result)
        if result.converged:
            grid.points[idx] = result
            grid.converged_mask[idx] = True
            grid.x_cache[idx] = result.x
            recovered += 1

    return recovered


def axis_sweeps(
    grid: NDGrid,
    point_solve_fn: PointSolveFn,
    debug: bool = False,
    on_point_complete: Optional[PointProgressFn] = None,
) -> int:
    """Sweep along every axis in both directions to fill dead zones.

    For each axis ``d`` and each direction ``(±1)``, iterate all grid
    points in that order, seeding from the side the sweep comes from.
    Returns the total number of cells recovered.
    """
    ndim = grid.ndim
    shape = grid.shape
    total_recovered = 0

    for d in range(ndim):
        for direction in (1, -1):
            if int((~grid.converged_mask).sum()) == 0:
                return total_recovered

            recovered = _sweep_along_axis(
                grid, d, direction, point_solve_fn,
                on_point_complete=on_point_complete)
            total_recovered += recovered

            if debug and recovered > 0:
                total = int(np.prod(shape))
                conv = int(grid.converged_mask.sum())
                ax_name = grid.axes[d].name
                dir_str = "fwd" if direction == 1 else "rev"
                print(f"[nd_grid] axis sweep {ax_name}/{dir_str}: "
                      f"+{recovered}, now {conv}/{total} "
                      f"({100*conv/total:.1f}%)", flush=True)

    return total_recovered
