"""
solver_retry_helpers.py
=======================
*Retry* phases of the coarse N-D grid solve.  These run after the
initial flood-fill + axis sweeps and only consider points that are
still unconverged.  Package-private: callable only via
:meth:`NDGridSolver.solve`.

Functions
---------
- :func:`radius_offsets`        — Chebyshev-ball offsets minus origin.
- :func:`backscan_retry`        — phase 4: re-seed with neighbour x's.
- :func:`interpolation_retry`   — phase 5: mean/median/blend guesses.
"""

from __future__ import annotations

import time
from itertools import product as _product
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..data_types import (
    NDGrid, PointResult,
    add_offset, in_bounds, all_offsets,
)
from ..settings import (
    BACKSCAN_MAX_PASSES,
    DEEP_RETRY_RADIUS,
    DEEP_RETRY_TIMEOUT_FACTOR,
)


PointSolveFn = Callable[[Dict[str, float], Optional[np.ndarray]], PointResult]
PointProgressFn = Callable[[Tuple[int, ...], PointResult], None]


# ======================================================================
#  Offset helper
# ======================================================================

def radius_offsets(ndim: int, radius: int) -> List[Tuple[int, ...]]:
    """All offsets within a Chebyshev radius, excluding the origin."""
    r = range(-radius, radius + 1)
    return [d for d in _product(*([r] * ndim))
            if any(x != 0 for x in d)]


# ======================================================================
#  Phase 4 — back-scan retry
# ======================================================================

def backscan_retry(
    grid: NDGrid,
    offsets: List[Tuple[int, ...]],
    point_solve_fn: PointSolveFn,
    debug: bool = False,
    on_point_complete: Optional[PointProgressFn] = None,
) -> int:
    """Multi-pass retry: seed unconverged points from converged
    neighbours.  Continues until no new recoveries or
    ``BACKSCAN_MAX_PASSES`` passes have run.
    """
    shape = grid.shape
    all_off = all_offsets(grid.ndim)
    total_recovered = 0

    for pass_idx in range(BACKSCAN_MAX_PASSES):
        failed = list(zip(*np.where(~grid.converged_mask)))
        if not failed:
            break
        failed = [tuple(int(i) for i in f) for f in failed]

        candidates = []
        for idx in failed:
            for off in all_off:
                nidx = add_offset(idx, off)
                if in_bounds(nidx, shape) and grid.converged_mask[nidx]:
                    candidates.append(idx)
                    break

        if not candidates:
            break

        recovered = 0
        for idx in candidates:
            neighbor_xs = []
            for off in all_off:
                nidx = add_offset(idx, off)
                if (in_bounds(nidx, shape) and grid.converged_mask[nidx]
                        and not np.any(np.isnan(grid.x_cache[nidx]))):
                    neighbor_xs.append(grid.x_cache[nidx].copy())

            coords = grid.coords_at(idx)
            for x0 in neighbor_xs:
                result = point_solve_fn(coords, x0)
                if on_point_complete is not None:
                    on_point_complete(idx, result)
                if result.converged:
                    grid.points[idx] = result
                    grid.converged_mask[idx] = True
                    grid.x_cache[idx] = result.x
                    recovered += 1
                    break

        total_recovered += recovered
        if debug:
            total = int(np.prod(shape))
            conv = int(grid.converged_mask.sum())
            remaining = total - conv
            print(f"[nd_grid] backscan pass {pass_idx+1}: +{recovered}, "
                  f"conv={conv}/{total} ({100*conv/total:.1f}%), "
                  f"{remaining} remaining", flush=True)

        if recovered == 0:
            break

    return total_recovered


# ======================================================================
#  Phase 5 — interpolation retry
# ======================================================================

def interpolation_retry(
    grid: NDGrid,
    point_timeout_s: float,
    point_solve_fn: PointSolveFn,
    debug: bool = False,
    on_point_complete: Optional[PointProgressFn] = None,
) -> int:
    """Retry with averaged / blended neighbour guesses.

    Generates a richer set of initial conditions than back-scan:
      (a) mean / median of converged neighbours in a wider radius
      (b) each individual neighbour (extended timeout)
      (c) pair-wise convex blends between neighbour solutions
    """
    shape = grid.shape
    ndim = grid.ndim
    radius = DEEP_RETRY_RADIUS
    total_recovered = 0

    _BLEND_ALPHAS = (0.25, 0.5, 0.75)
    _PER_POINT_BUDGET = point_timeout_s * DEEP_RETRY_TIMEOUT_FACTOR
    _RADIUS_OFFSETS = radius_offsets(ndim, radius)

    for pass_idx in range(BACKSCAN_MAX_PASSES):
        failed = list(zip(*np.where(~grid.converged_mask)))
        if not failed:
            break
        failed = [tuple(int(i) for i in f) for f in failed]

        recovered = 0
        for idx in failed:
            t_start = time.perf_counter()
            budget_end = t_start + _PER_POINT_BUDGET

            neighbor_xs = []
            for off in _RADIUS_OFFSETS:
                nidx = add_offset(idx, off)
                if (in_bounds(nidx, shape)
                        and grid.converged_mask[nidx]
                        and not np.any(np.isnan(grid.x_cache[nidx]))):
                    neighbor_xs.append(grid.x_cache[nidx])

            if not neighbor_xs:
                continue

            coords = grid.coords_at(idx)
            stacked = np.array(neighbor_xs)

            guesses: List[np.ndarray] = []
            guesses.append(np.mean(stacked, axis=0))
            if len(neighbor_xs) >= 3:
                guesses.append(np.median(stacked, axis=0))
            for nx in neighbor_xs:
                guesses.append(nx.copy())
            n_neigh = len(neighbor_xs)
            for i in range(min(n_neigh, 8)):
                for j in range(i + 1, min(n_neigh, 8)):
                    for alpha in _BLEND_ALPHAS:
                        guesses.append(
                            alpha * neighbor_xs[i]
                            + (1.0 - alpha) * neighbor_xs[j])

            for x0 in guesses:
                now = time.perf_counter()
                remaining = budget_end - now
                if remaining < 0.5:
                    break
                result = point_solve_fn(coords, x0)
                if on_point_complete is not None:
                    on_point_complete(idx, result)
                if result.converged:
                    grid.points[idx] = result
                    grid.converged_mask[idx] = True
                    grid.x_cache[idx] = result.x
                    recovered += 1
                    break

        total_recovered += recovered
        if debug:
            total = int(np.prod(shape))
            conv = int(grid.converged_mask.sum())
            remaining = total - conv
            print(f"[nd_grid] interp pass {pass_idx+1}: +{recovered}, "
                  f"conv={conv}/{total} ({100*conv/total:.1f}%), "
                  f"{remaining} remaining", flush=True)

        if recovered == 0:
            break

    return total_recovered
