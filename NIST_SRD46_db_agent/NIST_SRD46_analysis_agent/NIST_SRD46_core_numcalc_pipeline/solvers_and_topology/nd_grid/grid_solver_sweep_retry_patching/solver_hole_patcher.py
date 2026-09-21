"""
solver_hole_patcher.py
======================
Re-attempt unconverged sub-cells in a refined N-D sub-grid by seeding
the solver with neighbouring converged x-vectors and, if those fail,
with extrapolated seeds derived from collinear converged neighbours.

This is **not** a label-level fallback (no voting, averaging, or
nearest-neighbour relabelling): every label that the patcher writes
comes from a fresh solver call that has reported ``converged=True``.
A hole that the solver cannot crack even with neighbour / extrapolated
seeds is left as ``-1`` so downstream code can decide what to do
without inheriting a spurious label.

The only public entry point is :func:`patch_subgrid_holes`, intended
to be called by the refiner immediately after the initial sub-grid
solve loop (both at layer 1 and at every deeper layer).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..data_types import PointResult
from solver_settings import MIN_LOG, MAX_LOG


# Number of least-likely species to drop in the species-elimination
# homotopy seed (Stage 1).  Their log-conc is clamped to MIN_LOG and
# the solver naturally re-grows them through Newton iterations once
# the dominant species' basin is established.
_ELIM_K_DEFAULT = 3


# ── public type aliases ──────────────────────────────────────────
PointSolveFn = Callable[[Dict[str, float], Optional[np.ndarray]], PointResult]
"""``(coords, x0) -> PointResult`` — same signature as in the refiner."""

LabelIntResolver = Callable[[PointResult], int]
"""``PointResult -> int`` — return the catalog integer label for the
given converged solve (or ``-1`` if the labeller refuses)."""


# ── neighbour-iteration helpers ──────────────────────────────────

def _axis_aligned_neighbours(
    sub_idx: Tuple[int, ...], sub_shape: Tuple[int, ...],
) -> List[Tuple[int, ...]]:
    """Return the 2*ndim immediate axis-aligned neighbours that lie
    inside ``sub_shape``."""
    out: List[Tuple[int, ...]] = []
    ndim = len(sub_idx)
    for d in range(ndim):
        for delta in (-1, +1):
            nb = list(sub_idx)
            nb[d] += delta
            if 0 <= nb[d] < sub_shape[d]:
                out.append(tuple(nb))
    return out


def _diagonal_neighbours(
    sub_idx: Tuple[int, ...], sub_shape: Tuple[int, ...],
) -> List[Tuple[int, ...]]:
    """Return all 3^ndim - 1 in-bounds neighbours excluding self."""
    out: List[Tuple[int, ...]] = []
    ndim = len(sub_idx)
    for offset in np.ndindex(*([3] * ndim)):
        off = tuple(o - 1 for o in offset)
        if all(o == 0 for o in off):
            continue
        nb = tuple(sub_idx[d] + off[d] for d in range(ndim))
        if all(0 <= nb[d] < sub_shape[d] for d in range(ndim)):
            out.append(nb)
    return out


def _coord_dict(
    sub_axes_vals: List[np.ndarray],
    axis_names: List[str],
    sub_idx: Tuple[int, ...],
) -> Dict[str, float]:
    return {axis_names[d]: float(sub_axes_vals[d][sub_idx[d]])
            for d in range(len(sub_idx))}


# ── seed extraction ─────────────────────────────────────────────

def _collect_neighbour_seeds(
    sub_points: np.ndarray,
    sub_labels: np.ndarray,
    sub_idx: Tuple[int, ...],
    max_seeds: int,
) -> List[np.ndarray]:
    """Gather converged x-vectors from up to ``max_seeds`` neighbours
    (axis-aligned first, then diagonal).  Each x-vector is returned as
    an independent copy.
    """
    seeds: List[np.ndarray] = []
    sub_shape = sub_points.shape

    # Axis-aligned first (closer in coordinate space).
    for nb in _axis_aligned_neighbours(sub_idx, sub_shape):
        if sub_labels[nb] >= 0:
            res = sub_points[nb]
            if res is not None and getattr(res, "converged", False):
                seeds.append(res.x.copy())
                if len(seeds) >= max_seeds:
                    return seeds

    # Then diagonal neighbours.
    for nb in _diagonal_neighbours(sub_idx, sub_shape):
        if sub_labels[nb] >= 0:
            res = sub_points[nb]
            if res is not None and getattr(res, "converged", False):
                # Avoid duplicates already collected as axis-aligned.
                already = any(np.array_equal(s, res.x) for s in seeds)
                if not already:
                    seeds.append(res.x.copy())
                    if len(seeds) >= max_seeds:
                        return seeds
    return seeds


def _extrapolated_seeds(
    sub_points: np.ndarray,
    sub_labels: np.ndarray,
    sub_idx: Tuple[int, ...],
) -> List[np.ndarray]:
    """Linear-extrapolation seeds.

    For each axis ``d``, look for two collinear converged neighbours at
    offsets ``(+1, +2)`` or ``(-1, -2)`` along that axis and extrapolate
    the x-vector linearly to ``sub_idx``.  Returns one seed per axis
    direction where a clean extrapolation is possible.  Holes deep
    inside an unconverged region will simply yield an empty list.
    """
    seeds: List[np.ndarray] = []
    sub_shape = sub_points.shape
    ndim = len(sub_idx)

    for d in range(ndim):
        for direction in (+1, -1):
            i1 = list(sub_idx); i1[d] += direction
            i2 = list(sub_idx); i2[d] += 2 * direction
            if not (0 <= i1[d] < sub_shape[d]
                    and 0 <= i2[d] < sub_shape[d]):
                continue
            t1, t2 = tuple(i1), tuple(i2)
            if sub_labels[t1] < 0 or sub_labels[t2] < 0:
                continue
            r1, r2 = sub_points[t1], sub_points[t2]
            if (r1 is None or r2 is None
                    or not getattr(r1, "converged", False)
                    or not getattr(r2, "converged", False)):
                continue
            if r1.x.shape != r2.x.shape:
                continue
            # x_hole ≈ x1 + (x1 - x2) ; one-step linear extrapolation
            # along the axis (uniform spacing in sub-grid).
            extrap = r1.x + (r1.x - r2.x)
            extrap = np.clip(extrap, MIN_LOG, MAX_LOG)
            seeds.append(extrap.astype(r1.x.dtype, copy=False))
    return seeds


# ── Stage 1 (species-elimination homotopy) ──────────────────────

def _species_elimination_seeds(
    neighbour_seeds: List[np.ndarray],
    k_eliminate: int = _ELIM_K_DEFAULT,
) -> List[np.ndarray]:
    """For each neighbour x-vector, return a copy in which the
    ``k_eliminate`` smallest log-concentration entries are clamped to
    ``MIN_LOG``.

    Rationale
    ---------
    The "least likely species" in the neighbour solution are the ones
    most prone to (a) trapping Newton in the wrong basin or
    (b) inflating Jacobian condition number with near-zero numerical
    noise.  Pushing them down to ``MIN_LOG`` removes that noise; the
    solver naturally re-grows the entries through Newton iterations
    once the dominant species' basin is established.

    Only entries strictly above ``MIN_LOG`` are eligible for
    elimination (we never re-clamp entries that are already at the
    floor).  Returns one mutated seed per input seed.
    """
    out: List[np.ndarray] = []
    for seed in neighbour_seeds:
        if seed is None or seed.size == 0:
            continue
        sd = seed.copy()
        eligible = np.where(sd > MIN_LOG)[0]
        if eligible.size == 0:
            continue
        k = min(int(k_eliminate), eligible.size)
        # k smallest log-conc entries among eligible
        small_in_elig = np.argpartition(sd[eligible], k - 1)[:k] \
            if k < eligible.size else np.arange(eligible.size)
        sd[eligible[small_in_elig]] = MIN_LOG
        out.append(sd)
    return out


# ── Stage 4 (per-species inverse-distance extrapolation) ────────

def _per_species_extrapolation_seed(
    sub_points: np.ndarray,
    sub_labels: np.ndarray,
    sub_idx: Tuple[int, ...],
) -> Optional[np.ndarray]:
    """Per-species inverse-distance-weighted extrapolation of the hole
    x-vector from ALL converged neighbours in the surrounding
    ``3x3x...`` window.

    For each species index ``j`` we collect ``(distance, x_nb[j])``
    pairs from every converged neighbour and predict ``x_hole[j]`` as
    the IDW average (``weight = 1 / distance``).  Returns a single seed
    or ``None`` if the window contains no converged neighbour at all.
    """
    sub_shape = sub_points.shape
    ndim = len(sub_idx)

    # Reference x to learn the basis size from
    ref_x: Optional[np.ndarray] = None

    # Collect (distance, x) pairs from in-window converged neighbours
    pairs: List[Tuple[float, np.ndarray]] = []
    # 5x5x...x5 window for robustness on isolated holes
    for offset in np.ndindex(*([5] * ndim)):
        off = tuple(o - 2 for o in offset)
        if all(o == 0 for o in off):
            continue
        nb = tuple(sub_idx[d] + off[d] for d in range(ndim))
        if not all(0 <= nb[d] < sub_shape[d] for d in range(ndim)):
            continue
        if sub_labels[nb] < 0:
            continue
        res = sub_points[nb]
        if res is None or not getattr(res, "converged", False):
            continue
        dist = float(np.sqrt(sum(o * o for o in off)))
        pairs.append((dist, res.x))
        if ref_x is None:
            ref_x = res.x

    if ref_x is None or not pairs:
        return None

    n = ref_x.size
    num = np.zeros(n, dtype=ref_x.dtype)
    den = 0.0
    for dist, x_nb in pairs:
        if x_nb.shape != ref_x.shape:
            continue
        w = 1.0 / max(dist, 1e-12)
        num += w * x_nb
        den += w
    if den <= 0.0:
        return None
    extrap = num / den
    extrap = np.clip(extrap, MIN_LOG, MAX_LOG)
    return extrap.astype(ref_x.dtype, copy=False)


# ── public entry point ──────────────────────────────────────────

def patch_subgrid_holes(
    sub_axes_vals: List[np.ndarray],
    sub_points: np.ndarray,
    sub_labels: np.ndarray,
    solve_fn: PointSolveFn,
    label_int_resolver: LabelIntResolver,
    axis_names: List[str],
    x_cache: Optional[Dict[Tuple, np.ndarray]] = None,
    max_neighbor_seeds: int = 4,
    debug: bool = False,
    extra_label_targets: Optional[
        List[Tuple[np.ndarray, "LabelIntResolver"]]
    ] = None,
) -> int:
    """Retry every unconverged sub-cell with seeded solver calls.

    Parameters
    ----------
    sub_axes_vals
        Per-axis 1-D arrays of sub-cell-centre coordinates (length =
        ``sub_labels.shape[d]``) — same convention as the refiner.
    sub_points
        ``object`` array of shape ``sub_labels.shape`` holding the
        ``PointResult`` for every sub-cell.  Mutated in place: any
        sub-cell the patcher converges gets its slot overwritten.
    sub_labels
        ``int32`` array of catalog integer labels (-1 for unconverged).
        Mutated in place.
    solve_fn
        The same point-solve callable used by the refiner.
    label_int_resolver
        Callable that, given a converged ``PointResult``, returns the
        catalog integer label (or ``-1`` if the labeller refuses, in
        which case the sub-cell stays a hole).
    axis_names
        Axis name list (e.g. ``["E_V", "pH"]``) in the same order as
        ``sub_axes_vals``.
    x_cache
        Optional warm-start cache shared with the refiner; updated for
        every freshly converged hole.
    max_neighbor_seeds
        Maximum number of neighbour x-vectors to try before falling
        through to extrapolation.

    Returns
    -------
    Number of sub-cells whose label was successfully patched.
    """
    if sub_labels.size == 0:
        return 0

    hole_indices = list(zip(*np.where(sub_labels < 0)))
    if not hole_indices:
        return 0

    n_fixed = 0
    n_holes = len(hole_indices)

    # We iterate up to twice: a freshly patched hole may give a
    # neighbour-seed that unsticks a deeper hole on the second pass.
    for _pass in range(2):
        progress_this_pass = 0
        # Re-evaluate the hole list each pass since some may now be filled.
        remaining = [idx for idx in hole_indices if sub_labels[idx] < 0]
        if not remaining:
            break

        for sub_idx in remaining:
            coords = _coord_dict(sub_axes_vals, axis_names, sub_idx)

            # Collect neighbour seeds once — used by stages 1 and 2.
            seeds = _collect_neighbour_seeds(
                sub_points, sub_labels, sub_idx, max_neighbor_seeds)

            converged_res: Optional[PointResult] = None

            # ── Stage 1: species-elimination homotopy ──────────
            # Clamp the K least-likely species in each neighbour seed
            # to MIN_LOG and re-solve.  This frees Newton from the
            # neighbour's basin when a new species is dominant at the
            # hole.  Tried FIRST because a stale basin is the most
            # common reason warm-start neighbour-x fails.
            if seeds:
                for elim_seed in _species_elimination_seeds(
                        seeds, _ELIM_K_DEFAULT):
                    res = solve_fn(coords, elim_seed)
                    if res.converged:
                        converged_res = res
                        break

            # ── Stage 2: neighbour-x warm starts (unmodified) ──
            if converged_res is None:
                for seed in seeds:
                    res = solve_fn(coords, seed)
                    if res.converged:
                        converged_res = res
                        break

            # ── Stage 3: collinear-pair extrapolation seeds ────
            if converged_res is None:
                for seed in _extrapolated_seeds(
                        sub_points, sub_labels, sub_idx):
                    res = solve_fn(coords, seed)
                    if res.converged:
                        converged_res = res
                        break

            # ── Stage 4: per-species IDW extrapolation (fallback)
            if converged_res is None:
                ps_seed = _per_species_extrapolation_seed(
                    sub_points, sub_labels, sub_idx)
                if ps_seed is not None:
                    res = solve_fn(coords, ps_seed)
                    if res.converged:
                        converged_res = res

            if converged_res is None:
                continue

            label_int = label_int_resolver(converged_res)
            if label_int < 0:
                # Solver converged but labeller refused; do not write
                # a fake label.  Leave the hole as -1.
                continue

            sub_points[sub_idx] = converged_res
            sub_labels[sub_idx] = int(label_int)
            if extra_label_targets:
                for tgt_arr, tgt_resolver in extra_label_targets:
                    tgt_arr[sub_idx] = int(tgt_resolver(converged_res))
            if x_cache is not None:
                key = tuple(sorted(coords.items()))
                x_cache[key] = converged_res.x.copy()
            n_fixed += 1
            progress_this_pass += 1

        if progress_this_pass == 0:
            break

    if debug:
        print(f"[hole_patcher] {n_fixed}/{n_holes} sub-cell holes "
              f"patched via seeded retries (extrap fallback engaged "
              f"where neighbour seeds were exhausted)", flush=True)

    return n_fixed


# ── label-map convenience wrapper (N-D) ─────────────────────────

class _XOnlyPoint:
    """Minimal duck-typed stand-in for a :class:`PointResult`.

    Only ``.x`` and ``.converged`` are read by the patcher's
    neighbour-collection and extrapolation helpers, so we use this
    lightweight shim when the caller only has raw x-vectors per cell
    (no full ``PointResult``).  When the patcher converges a hole, the
    ``solve_fn`` returns a real ``PointResult`` which overwrites the
    shim in the points array.
    """
    __slots__ = ("x", "converged")

    def __init__(self, x: np.ndarray, converged: bool) -> None:
        self.x = x
        self.converged = converged


def patch_grid_label_map(
    axes_vals: List[np.ndarray],
    labels: np.ndarray,
    x_array: np.ndarray,
    solve_fn: PointSolveFn,
    label_int_resolver: LabelIntResolver,
    axis_names: List[str],
    x_cache: Optional[Dict[Tuple, np.ndarray]] = None,
    debug: bool = False,
) -> int:
    """Patch unconverged cells in an N-D label map by seeded re-solves.

    Fine-grid analogue of :func:`patch_subgrid_holes`: instead of an
    object array of full :class:`PointResult` instances, the caller
    supplies a raw object array of converged x-vectors (``x_array``)
    with NaN-array sentinels at holes.  Identical four-stage
    strategy; fully N-D generic.

    Parameters
    ----------
    axes_vals
        Per-axis 1-D arrays of cell-centre coordinates, in
        ``axis_names`` order.
    labels
        ``int32`` array of catalog integer labels (negative = hole).
        Mutated in place.
    x_array
        ``object`` array of shape ``labels.shape`` holding the
        converged x-vector per cell (NaN-only array at holes).
        Mutated in place: freshly converged x-vectors are written
        back so subsequent passes can use them.
    solve_fn, label_int_resolver, axis_names, x_cache, debug
        See :func:`patch_subgrid_holes`.

    Returns
    -------
    Number of cells whose label was successfully patched.
    """
    if labels.size == 0:
        return 0

    # Wrap each x-vector into a lightweight shim.  A cell is treated
    # as "converged neighbour" iff its label is non-negative AND its
    # cached x-vector is finite.
    sub_points = np.empty(labels.shape, dtype=object)
    for idx in np.ndindex(*labels.shape):
        x_vec = x_array[idx]
        ok = (
            x_vec is not None
            and isinstance(x_vec, np.ndarray)
            and x_vec.size > 0
            and not np.any(np.isnan(x_vec))
            and labels[idx] >= 0
        )
        sub_points[idx] = _XOnlyPoint(
            x_vec if isinstance(x_vec, np.ndarray) else np.array([np.nan]),
            bool(ok),
        )

    n_fixed = patch_subgrid_holes(
        sub_axes_vals=axes_vals,
        sub_points=sub_points,
        sub_labels=labels,
        solve_fn=solve_fn,
        label_int_resolver=label_int_resolver,
        axis_names=axis_names,
        x_cache=x_cache,
        debug=debug,
    )

    # Mirror freshly converged x-vectors back into x_array so the
    # caller's external view is consistent.
    if n_fixed > 0:
        for idx in np.ndindex(*labels.shape):
            pt = sub_points[idx]
            if pt is not None and not isinstance(pt, _XOnlyPoint) \
                    and hasattr(pt, "x"):
                x_array[idx] = pt.x

    return n_fixed
