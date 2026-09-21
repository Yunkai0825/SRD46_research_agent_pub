"""
simplifier_rdp.py
=================
Ramer-Douglas-Peucker polyline simplification.

Removes intermediate points whose perpendicular distance to the
line segment connecting retained neighbors is < epsilon.
Coordinates are normalised to [0,1] in both axes before distance
computation to handle pH/E scale differences.
"""

from __future__ import annotations

import numpy as np
from typing import List, Tuple

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solver_settings import RDP_EPSILON, DEBUG


def simplify_rdp(
    polyline: List[Tuple[float, float]],
    epsilon: float = RDP_EPSILON,
    pH_range: Tuple[float, float] = (0.0, 14.0),
    E_range: Tuple[float, float] = (-1.0, 1.5),
) -> Tuple[List[Tuple[float, float]], List[float]]:
    """
    Ramer-Douglas-Peucker polyline simplification.

    Parameters
    ----------
    polyline  : ordered [(pH, E), ...] boundary points
    epsilon   : distance threshold (in normalised [0,1]x[0,1] space)
    pH_range  : domain pH range for normalisation
    E_range   : domain E range for normalisation

    Returns
    -------
    (simplified_points, corresponding_t_params)
    where t_params are normalised arc-length parameters [0, 1].
    """
    if len(polyline) <= 2:
        t = [0.0, 1.0] if len(polyline) == 2 else [0.0]
        return list(polyline), t[:len(polyline)]

    # Normalise to [0, 1]
    pH_scale = pH_range[1] - pH_range[0]
    E_scale = E_range[1] - E_range[0]
    if pH_scale < 1e-15:
        pH_scale = 1.0
    if E_scale < 1e-15:
        E_scale = 1.0

    norm_pts = [((p[0] - pH_range[0]) / pH_scale,
                 (p[1] - E_range[0]) / E_scale) for p in polyline]

    # Recursive RDP
    keep = [False] * len(norm_pts)
    keep[0] = True
    keep[-1] = True
    _rdp_recurse(norm_pts, 0, len(norm_pts) - 1, epsilon, keep)

    # Extract kept points
    kept_indices = [i for i, k in enumerate(keep) if k]
    simplified = [polyline[i] for i in kept_indices]

    # Compute arc-length t-parameters
    t_params = _arc_length_t(simplified)

    return simplified, t_params


def _rdp_recurse(
    pts: List[Tuple[float, float]],
    start: int,
    end: int,
    epsilon: float,
    keep: List[bool],
) -> None:
    """Recursive RDP: mark points to keep."""
    if end - start < 2:
        return

    max_dist = 0.0
    max_idx = -1

    for i in range(start + 1, end):
        d = _perp_distance(pts[i], pts[start], pts[end])
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist > epsilon:
        keep[max_idx] = True
        _rdp_recurse(pts, start, max_idx, epsilon, keep)
        _rdp_recurse(pts, max_idx, end, epsilon, keep)


def _perp_distance(
    point: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float],
) -> float:
    """Perpendicular distance from point to line segment, in normalised space."""
    dx = line_end[0] - line_start[0]
    dy = line_end[1] - line_start[1]
    line_len2 = dx * dx + dy * dy

    if line_len2 < 1e-30:
        return np.sqrt((point[0] - line_start[0]) ** 2 +
                        (point[1] - line_start[1]) ** 2)

    # Project point onto line
    t = ((point[0] - line_start[0]) * dx +
         (point[1] - line_start[1]) * dy) / line_len2
    t = max(0.0, min(1.0, t))

    proj_x = line_start[0] + t * dx
    proj_y = line_start[1] + t * dy

    return np.sqrt((point[0] - proj_x) ** 2 + (point[1] - proj_y) ** 2)


def _arc_length_t(polyline: List[Tuple[float, float]]) -> List[float]:
    """Compute normalised cumulative arc-length parameters [0, 1]."""
    if len(polyline) <= 1:
        return [0.0] * len(polyline)

    dists = [0.0]
    for i in range(1, len(polyline)):
        dx = polyline[i][0] - polyline[i - 1][0]
        dy = polyline[i][1] - polyline[i - 1][1]
        dists.append(dists[-1] + np.sqrt(dx * dx + dy * dy))

    total = dists[-1]
    if total < 1e-15:
        return [i / max(1, len(polyline) - 1) for i in range(len(polyline))]

    return [d / total for d in dists]


def subsample_to_n_points(
    polyline: List[Tuple[float, float]],
    n: int = 5,
    pH_range: Tuple[float, float] = (0.0, 14.0),
    E_range: Tuple[float, float] = (-1.0, 1.5),
) -> Tuple[List[Tuple[float, float]], List[float]]:
    """
    Select exactly *n* points from the polyline via iterative farthest-point
    insertion (greedy RDP-style).

    At each step the point with the largest perpendicular distance to the
    current piecewise-linear approximation is added.  Distances are
    computed in normalised [0,1]×[0,1] space so that pH and E scales are
    treated equally.  This guarantees the N envelope points eliminate as
    much residual deviation as possible.

    Parameters
    ----------
    polyline  : ordered [(pH, E), ...]
    n         : desired number of output points (>= 2)
    pH_range  : domain pH range for normalisation
    E_range   : domain E range for normalisation

    Returns
    -------
    (selected_points, t_params)  where t in [0, 1].
    """
    import bisect as _bisect

    if n < 2:
        n = 2

    if len(polyline) <= 2:
        # Only 2 (or 1) points — interpolate linearly to produce n points
        p0, p1 = polyline[0], polyline[-1]
        result = []
        for k in range(n):
            frac = k / (n - 1)
            result.append((p0[0] + frac * (p1[0] - p0[0]),
                           p0[1] + frac * (p1[1] - p0[1])))
        return result, [k / (n - 1) for k in range(n)]

    # --- Normalise coordinates for distance computation ---
    pH_scale = pH_range[1] - pH_range[0]
    E_scale  = E_range[1]  - E_range[0]
    if pH_scale < 1e-15:
        pH_scale = 1.0
    if E_scale < 1e-15:
        E_scale = 1.0
    norm = [((p[0] - pH_range[0]) / pH_scale,
             (p[1] - E_range[0])  / E_scale) for p in polyline]

    # Check for zero-length polyline
    span = max(abs(norm[-1][0] - norm[0][0]),
               abs(norm[-1][1] - norm[0][1]))
    if span < 1e-15:
        p0, p1 = polyline[0], polyline[-1]
        result = []
        for k in range(n):
            frac = k / (n - 1)
            result.append((p0[0] + frac * (p1[0] - p0[0]),
                           p0[1] + frac * (p1[1] - p0[1])))
        return result, [k / (n - 1) for k in range(n)]

    if len(polyline) <= n:
        # Fewer vertices than n — interpolate along the polyline arc
        cum = [0.0]
        for i in range(1, len(polyline)):
            dx = polyline[i][0] - polyline[i - 1][0]
            dy = polyline[i][1] - polyline[i - 1][1]
            cum.append(cum[-1] + np.sqrt(dx * dx + dy * dy))
        total = cum[-1]
        if total < 1e-15:
            total = 1.0
        cum_arr = np.array(cum)
        target_s = [total * k / (n - 1) for k in range(n)]
        pH_arr = np.array([p[0] for p in polyline])
        E_arr  = np.array([p[1] for p in polyline])
        result = [polyline[0]]
        for ti in range(1, n - 1):
            s = target_s[ti]
            seg_idx = int(np.searchsorted(cum_arr, s, side='right')) - 1
            seg_idx = max(0, min(seg_idx, len(polyline) - 2))
            seg_len = cum_arr[seg_idx + 1] - cum_arr[seg_idx]
            if seg_len > 1e-15:
                frac = (s - cum_arr[seg_idx]) / seg_len
            else:
                frac = 0.0
            pH_interp = pH_arr[seg_idx] + frac * (pH_arr[seg_idx + 1] - pH_arr[seg_idx])
            E_interp  = E_arr[seg_idx]  + frac * (E_arr[seg_idx + 1]  - E_arr[seg_idx])
            result.append((float(pH_interp), float(E_interp)))
        result.append(polyline[-1])
        return result, [k / (n - 1) for k in range(n)]

    # --- Iterative farthest-point insertion (greedy RDP) ---
    # Start with the two endpoints.
    selected = [0, len(polyline) - 1]

    for _ in range(n - 2):
        best_dist = -1.0
        best_idx = -1
        # Scan every segment between consecutive selected indices
        for seg in range(len(selected) - 1):
            si, ei = selected[seg], selected[seg + 1]
            if ei - si < 2:
                continue  # no interior points in this segment
            for i in range(si + 1, ei):
                d = _perp_distance(norm[i], norm[si], norm[ei])
                if d > best_dist:
                    best_dist = d
                    best_idx = i
        if best_idx < 0:
            break  # no more interior points available
        _bisect.insort(selected, best_idx)

    # Deduplicate consecutive identical positions (can happen when a
    # node endpoint coincides with the next boundary pixel).
    deduped = [selected[0]]
    for idx in selected[1:]:
        prev = deduped[-1]
        p1, p2 = polyline[prev], polyline[idx]
        if abs(p1[0] - p2[0]) > 1e-12 or abs(p1[1] - p2[1]) > 1e-12:
            deduped.append(idx)
    selected = deduped

    result = [polyline[i] for i in selected]
    t_params = _arc_length_t(result)

    # Ensure strictly increasing t (needed by PchipInterpolator).
    # Nudge any duplicate t values with a tiny epsilon.
    for i in range(1, len(t_params)):
        if t_params[i] <= t_params[i - 1]:
            t_params[i] = t_params[i - 1] + 1e-9

    return result, t_params


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Test with a line plus noise
    pts = [(float(i), 0.3 + 0.01 * np.sin(i * 0.5)) for i in range(50)]
    simp, t = simplify_rdp(pts, epsilon=0.005, pH_range=(0, 50), E_range=(0, 1))
    print(f"Original: {len(pts)} points")
    print(f"Simplified: {len(simp)} points (epsilon=0.005)")
    print(f"t-params: [{t[0]:.3f}, ..., {t[-1]:.3f}]")

    # Test with a sharp corner
    pts2 = [(float(i), 0.0) for i in range(10)]
    pts2 += [(10.0 + float(i) * 0.1, float(i) * 0.5) for i in range(10)]
    simp2, t2 = simplify_rdp(pts2, epsilon=0.01, pH_range=(0, 20), E_range=(0, 5))
    print(f"\nCorner test: {len(pts2)} -> {len(simp2)} points")
