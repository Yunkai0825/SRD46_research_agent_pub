"""
simplifier_nd.py
================
Unified N-D manifold simplifier.

All simplifiers share the same *greedy farthest-point insertion*
principle.  RDP polyline simplification is the k=1 special case;
surface simplification uses constructive Delaunay triangulation
seeded from boundary curves.

Public API
----------
- simplify_curve      — N-D polyline RDP (replaces simplify_rdp)
- subsample_curve     — farthest-point insertion, budget-capped and
                        optionally resolution-terminated
- enforce_chord_planarity  — subdivide chords crossing other raw curves (2-D)
- enforce_chord_separation — subdivide conflicting chords of different
                        features so bigon faces keep area (2-D)
- simplify_surface    — 2-D surface farthest-point + Delaunay
- simplify_manifold_k — k≥3 fallback (point thinning)
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple

import sys, pathlib
_SOLVERS = str(pathlib.Path(__file__).resolve().parents[3] / "solvers_and_topology")
if _SOLVERS not in sys.path:
    sys.path.insert(0, _SOLVERS)

from solver_settings import RDP_EPSILON


# ======================================================================
#  N-D distance primitives
# ======================================================================

def _normalize_coords(
    pts: np.ndarray,
    axis_ranges: Dict[str, Tuple[float, float]],
    axis_names: List[str],
) -> np.ndarray:
    """Scale each axis to [0, 1] for balanced distance computation.

    Parameters
    ----------
    pts : (M, N) array
    axis_ranges : name → (lo, hi)
    axis_names : ordered axis names matching columns of *pts*
    """
    out = pts.copy().astype(np.float64)
    for j, name in enumerate(axis_names):
        lo, hi = axis_ranges.get(name, (0.0, 1.0))
        span = hi - lo
        if span < 1e-15:
            span = 1.0
        out[:, j] = (out[:, j] - lo) / span
    return out


def _point_to_segment_nd(
    point: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
) -> float:
    """Perpendicular distance from *point* to segment [a, b] in ℝⁿ."""
    ab = b - a
    ab_sq = np.dot(ab, ab)
    if ab_sq < 1e-30:
        return float(np.linalg.norm(point - a))
    t = np.clip(np.dot(point - a, ab) / ab_sq, 0.0, 1.0)
    proj = a + t * ab
    return float(np.linalg.norm(point - proj))


def _point_to_triangle_nd(
    point: np.ndarray,
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
) -> float:
    """Distance from *point* to triangle (v0, v1, v2) in ℝⁿ.

    Uses barycentric projection clipped to the triangle interior,
    then falls back to edge distances if the projection lands outside.
    """
    e0 = v1 - v0
    e1 = v2 - v0
    diff = v0 - point

    a00 = np.dot(e0, e0)
    a01 = np.dot(e0, e1)
    a11 = np.dot(e1, e1)
    b0 = np.dot(e0, diff)
    b1 = np.dot(e1, diff)

    det = a00 * a11 - a01 * a01
    if abs(det) < 1e-30:
        # Degenerate triangle — fall back to edge distances
        return min(
            _point_to_segment_nd(point, v0, v1),
            _point_to_segment_nd(point, v1, v2),
            _point_to_segment_nd(point, v0, v2),
        )

    s = (a01 * b1 - a11 * b0) / det
    t = (a01 * b0 - a00 * b1) / det

    # If inside triangle
    if s >= 0.0 and t >= 0.0 and s + t <= 1.0:
        proj = v0 + s * e0 + t * e1
        return float(np.linalg.norm(point - proj))

    # Outside: distance to each edge, take minimum
    return min(
        _point_to_segment_nd(point, v0, v1),
        _point_to_segment_nd(point, v1, v2),
        _point_to_segment_nd(point, v0, v2),
    )


# ======================================================================
#  Dim-1 simplifier  (N-D polyline RDP)
# ======================================================================

def simplify_curve(
    polyline: List[Tuple[float, ...]],
    epsilon: float = RDP_EPSILON,
    axis_ranges: Dict[str, Tuple[float, float]] | None = None,
    axis_names: List[str] | None = None,
) -> Tuple[List[Tuple[float, ...]], List[float]]:
    """N-D Ramer-Douglas-Peucker polyline simplification.

    Parameters
    ----------
    polyline : ordered list of N-D coordinate tuples
    epsilon : tolerance in normalised [0,1]^N space
    axis_ranges : name → (lo, hi) for normalisation
    axis_names : ordered axis names matching tuple positions

    Returns
    -------
    (simplified_points, t_params)
    t_params are normalised arc-length parameters in [0, 1].
    """
    if len(polyline) <= 2:
        t = [0.0, 1.0] if len(polyline) == 2 else [0.0]
        return list(polyline), t[:len(polyline)]

    pts = np.array(polyline, dtype=np.float64)
    ndim = pts.shape[1]

    # Normalise
    if axis_ranges and axis_names:
        norm = _normalize_coords(pts, axis_ranges, axis_names)
    else:
        norm = pts.copy()

    # Recursive RDP
    keep = [False] * len(norm)
    keep[0] = True
    keep[-1] = True
    _rdp_recurse_nd(norm, 0, len(norm) - 1, epsilon, keep)

    kept_idx = [i for i, k in enumerate(keep) if k]
    simplified = [polyline[i] for i in kept_idx]
    t_params = _arc_length_t_nd(simplified)
    return simplified, t_params


def _rdp_recurse_nd(
    pts: np.ndarray,
    start: int,
    end: int,
    epsilon: float,
    keep: List[bool],
) -> None:
    """Recursive RDP in N dimensions."""
    if end - start < 2:
        return
    a = pts[start]
    b = pts[end]
    max_dist = 0.0
    max_idx = -1
    for i in range(start + 1, end):
        d = _point_to_segment_nd(pts[i], a, b)
        if d > max_dist:
            max_dist = d
            max_idx = i
    if max_dist > epsilon:
        keep[max_idx] = True
        _rdp_recurse_nd(pts, start, max_idx, epsilon, keep)
        _rdp_recurse_nd(pts, max_idx, end, epsilon, keep)


def _arc_length_t_nd(polyline: List[Tuple[float, ...]]) -> List[float]:
    """Normalised cumulative arc-length parameters in [0, 1]."""
    if len(polyline) <= 1:
        return [0.0] * len(polyline)
    pts = np.array(polyline, dtype=np.float64)
    diffs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(diffs)])
    total = cum[-1]
    if total < 1e-15:
        return [i / max(1, len(polyline) - 1) for i in range(len(polyline))]
    return (cum / total).tolist()


def subsample_curve(
    polyline: List[Tuple[float, ...]],
    n: int = 5,
    axis_ranges: Dict[str, Tuple[float, float]] | None = None,
    axis_names: List[str] | None = None,
    return_indices: bool = False,
    stop_epsilon: float | None = None,
    min_points: int = 2,
    anchor_mask: List[bool] | None = None,
) -> (
    Tuple[List[Tuple[float, ...]], List[float]]
    | Tuple[List[Tuple[float, ...]], List[float], List[int]]
):
    """Select up to *n* points via iterative farthest-point insertion.

    At each step the interior point with the largest perpendicular
    distance to the current piecewise-linear approximation is added.  Every
    returned point is an unchanged raw vertex.  With ``return_indices=True``,
    the third return value gives those exact raw-vertex indices.

    ``stop_epsilon`` (normalised space) terminates insertion once the
    largest remaining deviation falls below it and at least ``min_points``
    vertices are selected, so a boundary that is straight at grid
    resolution keeps only its endpoints.  ``None`` reproduces the legacy
    exact-*n* behaviour.

    ``anchor_mask`` (aligned with *polyline*) restricts insertion to
    mask-``True`` vertices: envelope-interior vertices of merged
    collections carry grid noise, not geometry, so they never become
    control points here (the chord guards may still re-add them).
    Endpoints are always kept.
    """
    if n < 2:
        n = 2
    if min_points < 2:
        min_points = 2
    if len(polyline) <= 2 or (stop_epsilon is None and len(polyline) <= n):
        result = list(polyline)
        t_values = _arc_length_t_nd(polyline)
        if return_indices:
            return result, t_values, list(range(len(polyline)))
        return result, t_values

    pts = np.array(polyline, dtype=np.float64)
    if axis_ranges and axis_names:
        norm = _normalize_coords(pts, axis_ranges, axis_names)
    else:
        norm = pts.copy()

    M = len(norm)
    n_target = min(n, M)
    eligible = None
    if anchor_mask is not None and len(anchor_mask) == M:
        eligible = np.asarray(anchor_mask, dtype=bool)
    # Start with endpoints
    selected = [0, M - 1]

    while len(selected) < n_target:
        sel_sorted = sorted(selected)
        max_dist = -1.0
        max_idx = -1
        for seg_start, seg_end in zip(sel_sorted[:-1], sel_sorted[1:]):
            a = norm[seg_start]
            b = norm[seg_end]
            for i in range(seg_start + 1, seg_end):
                if eligible is not None and not eligible[i]:
                    continue
                d = _point_to_segment_nd(norm[i], a, b)
                if d > max_dist:
                    max_dist = d
                    max_idx = i
        if max_idx < 0:
            break
        if (stop_epsilon is not None and len(selected) >= min_points
                and max_dist < stop_epsilon):
            break
        selected.append(max_idx)

    selected = sorted(set(selected))
    result = [polyline[i] for i in selected]
    t_values = _arc_length_t_nd(result)
    if return_indices:
        return result, t_values, selected
    return result, t_values


def _proper_crossings(
    p0: np.ndarray,
    p1: np.ndarray,
    seg_a: np.ndarray,
    seg_b: np.ndarray,
    eps: float = 1e-12,
) -> bool:
    """True if open segment (p0, p1) properly crosses any segment (a, b).

    Proper = interiors intersect with strict sign changes on both sides;
    touching at endpoints or collinear overlap does not count.
    """
    r = p1 - p0
    d1 = r[0] * (seg_a[:, 1] - p0[1]) - r[1] * (seg_a[:, 0] - p0[0])
    d2 = r[0] * (seg_b[:, 1] - p0[1]) - r[1] * (seg_b[:, 0] - p0[0])
    s = seg_b - seg_a
    d3 = s[:, 0] * (p0[1] - seg_a[:, 1]) - s[:, 1] * (p0[0] - seg_a[:, 0])
    d4 = s[:, 0] * (p1[1] - seg_a[:, 1]) - s[:, 1] * (p1[0] - seg_a[:, 0])
    cross = (((d1 > eps) & (d2 < -eps)) | ((d1 < -eps) & (d2 > eps))) & \
            (((d3 > eps) & (d4 < -eps)) | ((d3 < -eps) & (d4 > eps)))
    return bool(np.any(cross))


def enforce_chord_planarity(
    polyline: List[Tuple[float, ...]],
    selected: List[int],
    obstacle_segments: np.ndarray | None,
    axis_ranges: Dict[str, Tuple[float, float]] | None = None,
    axis_names: List[str] | None = None,
) -> List[int]:
    """Subdivide chords that properly cross other boundaries (2-D only).

    The raw boundary network is planar, so any compact chord that crosses
    another feature's raw polyline misrepresents region adjacency.  Each
    offending chord is split at its farthest interior raw vertex until no
    crossing remains (the chord converges to the raw curve, which cannot
    cross).  Inputs and obstacles are compared in the same normalised
    space the deviation stop uses.  Dimensions other than 2 are returned
    unchanged.  Returns a sorted superset of ``selected``.
    """
    sel = sorted(set(selected))
    pts = np.array(polyline, dtype=np.float64)
    if (pts.ndim != 2 or pts.shape[1] != 2
            or obstacle_segments is None or len(obstacle_segments) == 0):
        return sel
    if axis_ranges and axis_names:
        norm = _normalize_coords(pts, axis_ranges, axis_names)
    else:
        norm = pts.copy()
    seg_a = obstacle_segments[:, 0, :]
    seg_b = obstacle_segments[:, 1, :]

    i = 0
    while i < len(sel) - 1:
        s, e = sel[i], sel[i + 1]
        if e - s < 2 or not _proper_crossings(norm[s], norm[e], seg_a, seg_b):
            i += 1
            continue
        max_dist = -1.0
        max_idx = -1
        for k in range(s + 1, e):
            d = _point_to_segment_nd(norm[k], norm[s], norm[e])
            if d > max_dist:
                max_dist = d
                max_idx = k
        if max_idx < 0:
            i += 1
            continue
        sel.insert(i + 1, max_idx)
        # re-test the shortened left chord at the same position
    return sel


def _chord_conflict(
    p0: np.ndarray,
    p1: np.ndarray,
    q0: np.ndarray,
    q1: np.ndarray,
    eps: float = 1e-12,
) -> bool:
    """True if chords properly cross or collinearly overlap with length."""
    r = p1 - p0
    d1 = r[0] * (q0[1] - p0[1]) - r[1] * (q0[0] - p0[0])
    d2 = r[0] * (q1[1] - p0[1]) - r[1] * (q1[0] - p0[0])
    s = q1 - q0
    d3 = s[0] * (p0[1] - q0[1]) - s[1] * (p0[0] - q0[0])
    d4 = s[0] * (p1[1] - q0[1]) - s[1] * (p1[0] - q0[0])
    if (((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps))
            and ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps))):
        return True
    if abs(d1) <= eps and abs(d2) <= eps:
        # Collinear: positive-length overlap of parameter intervals
        rr = float(np.dot(r, r))
        if rr < 1e-30:
            return False
        t0 = float(np.dot(q0 - p0, r)) / rr
        t1 = float(np.dot(q1 - p0, r)) / rr
        lo, hi = min(t0, t1), max(t0, t1)
        return min(hi, 1.0) - max(lo, 0.0) > 1e-9
    return False


def enforce_chord_separation(
    norm_polylines: List[np.ndarray],
    selections: List[List[int]],
    max_rounds: int = 200,
) -> List[List[int]]:
    """No two compact chords of different curves may cross or overlap.

    Coincident chords collapse the thin region between two boundaries that
    share both junction endpoints (a bigon face) into a zero-area line.
    On conflict *each* chord is subdivided at its farthest interior raw
    vertex, so both boundaries bend back toward their own raw geometry
    and the enclosed face regains area symmetrically.  Raw polylines of
    distinct boundaries neither cross nor overlap, so the fixpoint
    exists.  Returns new selections (sorted supersets).
    """
    sels = [sorted(set(s)) for s in selections]

    def _far(fi: int, ci: int) -> int:
        """Index of the farthest interior raw vertex under a chord, or -1."""
        pts = norm_polylines[fi]
        s, e = sels[fi][ci], sels[fi][ci + 1]
        best_d, best_k = -1.0, -1
        for k in range(s + 1, e):
            d = _point_to_segment_nd(pts[k], pts[s], pts[e])
            if d > best_d:
                best_d, best_k = d, k
        return best_k

    for _ in range(max_rounds):
        conflict = None
        for fa in range(len(sels)):
            pa = norm_polylines[fa]
            for fb in range(fa + 1, len(sels)):
                pb = norm_polylines[fb]
                for ca in range(len(sels[fa]) - 1):
                    a0, a1 = pa[sels[fa][ca]], pa[sels[fa][ca + 1]]
                    for cb in range(len(sels[fb]) - 1):
                        if _chord_conflict(a0, a1, pb[sels[fb][cb]],
                                           pb[sels[fb][cb + 1]]):
                            conflict = (fa, ca, fb, cb)
                            break
                    if conflict:
                        break
                if conflict:
                    break
            if conflict:
                break
        if conflict is None:
            return sels
        fa, ca, fb, cb = conflict
        ka = _far(fa, ca)
        kb = _far(fb, cb)
        if ka < 0 and kb < 0:
            return sels  # both chords are raw segments: nothing to subdivide
        if ka >= 0:
            sels[fa].insert(ca + 1, ka)
        if kb >= 0:
            sels[fb].insert(cb + 1, kb)
    return sels


# ======================================================================
#  Dim-2 simplifier  (surface farthest-point + Delaunay)
# ======================================================================

def simplify_surface(
    raw_points: List[Dict[str, float]] | np.ndarray,
    boundary_curves: List[List[Tuple[float, ...]]] | None = None,
    epsilon: float = RDP_EPSILON,
    axis_ranges: Dict[str, Tuple[float, float]] | None = None,
    axis_names: List[str] | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Simplify a 2-D surface (point cloud) via farthest-point insertion.

    Parameters
    ----------
    raw_points : point cloud — either list of coord dicts or (M, N) array
    boundary_curves : list of compact dim-1 boundary polylines
    epsilon : distance tolerance in normalised space
    axis_ranges : per-axis (lo, hi) for normalisation
    axis_names : ordered axis names

    Returns
    -------
    (vertices, triangles) — np.ndarray shapes (V, N) and (T, 3)
    """
    from scipy.spatial import Delaunay

    # --- Convert raw points to (M, N) array ---
    if axis_names is None:
        axis_names = []
    pts = _to_array(raw_points, axis_names)
    if len(pts) < 3:
        tris = np.array([[0, 1, 2]]) if len(pts) == 3 else np.empty((0, 3), dtype=int)
        return pts, tris

    # --- Normalise ---
    if axis_ranges and axis_names:
        norm = _normalize_coords(pts, axis_ranges, axis_names)
    else:
        norm = pts.copy()

    # --- Seed vertex set with boundary vertices ---
    seed_indices: List[int] = []
    if boundary_curves:
        for curve in boundary_curves:
            curve_arr = np.array(curve, dtype=np.float64)
            for cp in curve_arr:
                dists = np.linalg.norm(pts - cp, axis=1)
                nearest = int(np.argmin(dists))
                if nearest not in seed_indices:
                    seed_indices.append(nearest)

    # Always include convex-hull-like extremes as seeds
    if len(seed_indices) < 3:
        for dim in range(norm.shape[1]):
            imin = int(np.argmin(norm[:, dim]))
            imax = int(np.argmax(norm[:, dim]))
            for idx in (imin, imax):
                if idx not in seed_indices:
                    seed_indices.append(idx)

    if len(seed_indices) < 3:
        # Not enough seeds — add farthest from first two
        if len(seed_indices) >= 2:
            dists = np.linalg.norm(norm - norm[seed_indices[0]], axis=1)
            dists += np.linalg.norm(norm - norm[seed_indices[1]], axis=1)
            idx = int(np.argmax(dists))
            if idx not in seed_indices:
                seed_indices.append(idx)
        else:
            seed_indices = [0, len(pts) - 1]
            d = np.linalg.norm(norm - norm[0], axis=1)
            seed_indices.append(int(np.argmax(d)))

    selected_set = set(seed_indices)
    selected = list(seed_indices)

    # --- PCA → 2-D parameterisation for Delaunay ---
    mean = norm.mean(axis=0)
    centered = norm - mean
    cov = centered.T @ centered
    eigvals, eigvecs = np.linalg.eigh(cov)
    # Two largest eigenvectors
    order = np.argsort(eigvals)[::-1]
    basis = eigvecs[:, order[:2]]  # (N, 2)
    uv_all = centered @ basis  # (M, 2) — parameterisation

    # --- Iterative farthest-point insertion ---
    MAX_ITERS = len(pts) * 2
    for _iter in range(MAX_ITERS):
        sel_uv = uv_all[selected]
        if len(sel_uv) < 3:
            break
        try:
            tri = Delaunay(sel_uv)
        except Exception:
            break

        # For every raw point not yet selected, compute min distance
        # to current triangulation in normalised N-D space
        max_dist = 0.0
        max_idx = -1
        tri_simplices = tri.simplices  # (T, 3) — indices into selected
        verts_nd = norm[selected]  # (S, N)

        for i in range(len(pts)):
            if i in selected_set:
                continue
            pt = norm[i]
            min_d = np.inf
            for simplex in tri_simplices:
                v0 = verts_nd[simplex[0]]
                v1 = verts_nd[simplex[1]]
                v2 = verts_nd[simplex[2]]
                d = _point_to_triangle_nd(pt, v0, v1, v2)
                if d < min_d:
                    min_d = d
            if min_d > max_dist:
                max_dist = min_d
                max_idx = i

        if max_dist < epsilon or max_idx < 0:
            break
        selected.append(max_idx)
        selected_set.add(max_idx)

    # --- Final triangulation ---
    sel_uv = uv_all[selected]
    try:
        tri_final = Delaunay(sel_uv)
        triangles = tri_final.simplices.copy()
    except Exception:
        triangles = np.empty((0, 3), dtype=int)

    vertices = pts[selected]
    if len(triangles):
        triangles = _filter_surface_triangles(
            vertices,
            triangles,
            axis_ranges=axis_ranges,
            axis_names=axis_names,
        )
    return vertices, triangles


def _filter_surface_triangles(
    vertices: np.ndarray,
    triangles: np.ndarray,
    *,
    axis_ranges: Dict[str, Tuple[float, float]] | None = None,
    axis_names: List[str] | None = None,
    max_ratio: float = 4.0,
) -> np.ndarray:
    """Drop spanning triangles that bridge unrelated surface patches.

    Delaunay in PCA space happily connects distant vertices across holes or
    disconnected components. Filtering in normalized ambient coordinates keeps
    only triangles with edge lengths comparable to the local mesh scale.
    """
    if len(triangles) == 0:
        return triangles

    verts = np.asarray(vertices, dtype=np.float64)
    if axis_ranges and axis_names:
        verts_norm = _normalize_coords(verts, axis_ranges, axis_names)
    else:
        verts_norm = verts

    max_edges = np.empty(len(triangles), dtype=np.float64)
    for i, tri in enumerate(triangles):
        pts = verts_norm[tri]
        d01 = np.linalg.norm(pts[0] - pts[1])
        d12 = np.linalg.norm(pts[1] - pts[2])
        d02 = np.linalg.norm(pts[0] - pts[2])
        max_edges[i] = max(d01, d12, d02)

    positive = max_edges[max_edges > 1e-12]
    if len(positive) == 0:
        return triangles

    median_len = float(np.median(positive))
    threshold = median_len * max_ratio
    keep = max_edges <= threshold
    return triangles[keep]


# ======================================================================
#  Dim-k simplifier  (k ≥ 3 fallback — point thinning)
# ======================================================================

def simplify_manifold_k(
    raw_points: List[Dict[str, float]] | np.ndarray,
    boundary_points: List[np.ndarray] | None = None,
    epsilon: float = RDP_EPSILON,
    axis_ranges: Dict[str, Tuple[float, float]] | None = None,
    axis_names: List[str] | None = None,
) -> np.ndarray:
    """Thin a k-manifold (k≥3) point cloud via farthest-point insertion.

    Returns thinned point cloud (V, N) array.
    """
    if axis_names is None:
        axis_names = []
    pts = _to_array(raw_points, axis_names)
    if len(pts) <= 3:
        return pts

    if axis_ranges and axis_names:
        norm = _normalize_coords(pts, axis_ranges, axis_names)
    else:
        norm = pts.copy()

    # Seed with boundary points
    selected: List[int] = []
    selected_set: set = set()
    if boundary_points:
        for bps in boundary_points:
            for bp in np.atleast_2d(bps):
                dists = np.linalg.norm(pts - bp, axis=1)
                nearest = int(np.argmin(dists))
                if nearest not in selected_set:
                    selected.append(nearest)
                    selected_set.add(nearest)

    if len(selected) < 1:
        selected = [0]
        selected_set = {0}

    # Iterative farthest-point from selected set
    MAX_ITERS = len(pts) * 2
    for _ in range(MAX_ITERS):
        sel_norm = norm[selected]
        max_dist = 0.0
        max_idx = -1
        for i in range(len(pts)):
            if i in selected_set:
                continue
            d = float(np.min(np.linalg.norm(sel_norm - norm[i], axis=1)))
            if d > max_dist:
                max_dist = d
                max_idx = i
        if max_dist < epsilon or max_idx < 0:
            break
        selected.append(max_idx)
        selected_set.add(max_idx)

    return pts[selected]


# ======================================================================
#  Helpers
# ======================================================================

def _to_array(
    points: List[Dict[str, float]] | np.ndarray,
    axis_names: List[str],
) -> np.ndarray:
    """Convert various point formats to (M, N) float64 array."""
    if isinstance(points, np.ndarray):
        return points.astype(np.float64)
    if not points:
        return np.empty((0, max(1, len(axis_names))), dtype=np.float64)
    if isinstance(points[0], dict):
        if not axis_names:
            axis_names = sorted(points[0].keys())
        return np.array([[p[n] for n in axis_names] for p in points],
                        dtype=np.float64)
    # Assume list of tuples/lists
    return np.array(points, dtype=np.float64)
