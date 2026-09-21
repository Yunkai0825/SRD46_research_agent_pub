"""
compact_nd.py
=============
Bottom-up N-D topology compactor.

Processes features dimension by dimension (0-D → 1-D → 2-D → …),
each level seeded by the already-compact (dim-1) features from the
previous pass.  This guarantees boundary coherence across dimensions.

Input: either a ``TopologyND`` object from the topology mapper or
a CSV directory produced by ``topology_csv_io.export_features_csv``.

Output: ``CompactTopologyND`` — a unified, dimension-agnostic
compact topology ready for JSON export and plotting.

Public API
----------
- compact_topology_nd — main entry point
- compact_from_csv    — convenience wrapper for CSV input
"""

from __future__ import annotations

import pathlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import sys
_THIS_DIR = pathlib.Path(__file__).resolve().parent
_SOLVERS = str(_THIS_DIR.parents[2] / "solvers_and_topology")
_THIS_DIR_S = str(_THIS_DIR)
for _p in (_SOLVERS, _THIS_DIR_S):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from solver_settings import (
    RDP_EPSILON,
    RDP_ENVELOPE_N,
    RDP_TAU_NORM_FACTOR,
    RDP_MIN_LOOP_FACTOR,
    RDP_LOOP_MIN_POINTS,
)

from nd_grid.data_types import (
    TopologyND,
    CompactFeature,
    CompactRegion,
    CompactTopologyND,
)

from topology_csv_io import (
    classify_features_by_dim,
    load_features_csv,
    export_features_csv,
)
from simplifier_nd import (
    simplify_curve,
    subsample_curve,
    simplify_surface,
    simplify_manifold_k,
    enforce_chord_planarity,
    enforce_chord_separation,
    _arc_length_t_nd,
    _normalize_coords,
)


# ======================================================================
#  Public API
# ======================================================================

def compact_topology_nd(
    source,
    settings: Dict[str, Any] | None = None,
    rdp_epsilon: float = RDP_EPSILON,
    envelope_n: int = RDP_ENVELOPE_N,
    csv_dir: str | pathlib.Path | None = None,
    csv_prefix: str = "topo",
) -> CompactTopologyND:
    """Compact a TopologyND (or CSV dir) into a CompactTopologyND.

    Parameters
    ----------
    source : TopologyND  or  str / Path to CSV directory
        If a path, loads CSV files produced by ``export_features_csv``.
        If a TopologyND, classifies features directly.
    settings : dict, optional
        Override settings (passed through to output).
    rdp_epsilon : float
        Simplification tolerance (normalised space).
    envelope_n : int
        Number of envelope control points per curve.
    csv_dir : Path, optional
        If given, also export raw CSVs before compaction.
    csv_prefix : str
        Prefix for CSV filenames.

    Returns
    -------
    CompactTopologyND
    """
    if isinstance(source, (str, pathlib.Path)):
        features_by_dim, regions_raw, metadata = load_features_csv(
            source, csv_prefix)
        ndim = metadata["ndim"]
        axis_names = metadata["axis_names"]
        axis_ranges = {k: tuple(v) for k, v in metadata["axis_ranges"].items()}
        label_catalog = metadata.get("label_catalog", {})
        # Convert label_catalog keys to int
        label_catalog = {int(k): v for k, v in label_catalog.items()}
        axis_spacing = metadata.get("axis_spacing") or {}
        axis_spacing_coarse = metadata.get("axis_spacing_coarse") or {}
    elif hasattr(source, 'boundaries') and hasattr(source, 'regions'):
        # Duck-type check for TopologyND — avoids isinstance failures
        # caused by the same class being imported from different sys.path
        # routes (e.g. tests vs production code).
        topo = source
        ndim = topo.ndim
        settings_raw = topo.settings or {}
        axis_names = settings_raw.get("axis_names", [])
        axis_ranges = settings_raw.get("axis_ranges", {})
        label_catalog = topo.label_catalog or {}
        axis_spacing = settings_raw.get("axis_spacing") or {}
        axis_spacing_coarse = settings_raw.get("axis_spacing_coarse") or {}

        # Optionally export CSVs
        if csv_dir is not None:
            export_features_csv(topo, csv_dir, csv_prefix, axis_names)

        features_by_dim = classify_features_by_dim(topo, axis_names)
        regions_raw = [
            {"id": r.id, "label": r.label, "name": r.name,
             "measure": r.measure, "boundary_ids": r.boundary_ids,
             "flags": list(getattr(r, "flags", []) or [])}
            for r in topo.regions
        ]
    else:
        raise TypeError(
            f"compact_topology_nd: expected TopologyND or path, "
            f"got {type(source).__name__}"
        )

    # --- Bottom-up compaction ---
    compact_features: Dict[int, List[CompactFeature]] = {}
    max_dim = max(features_by_dim.keys()) if features_by_dim else -1

    for d in range(max_dim + 1):
        feats = features_by_dim.get(d, [])
        if d == 0:
            compact_features[d] = _compact_dim_0(feats)
        elif d == 1:
            compact_features[d] = _compact_dim_1(
                feats, compact_features.get(0, []),
                axis_names, axis_ranges, rdp_epsilon, envelope_n,
                axis_spacing=axis_spacing,
                axis_spacing_coarse=axis_spacing_coarse)
        elif d == 2:
            compact_features[d] = _compact_dim_2(
                feats, compact_features.get(0, []),
                compact_features.get(1, []),
                axis_names, axis_ranges, rdp_epsilon)
        else:
            compact_features[d] = _compact_dim_k(
                feats, compact_features, d,
                axis_names, axis_ranges, rdp_epsilon)

    # --- Build compact regions ---
    compact_regions = [
        CompactRegion(
            id=r["id"], label=r["label"], name=r["name"],
            measure=r["measure"], boundary_ids=r.get("boundary_ids", []),
            flags=list(r.get("flags", []) or []),
        )
        for r in regions_raw
    ]

    merged_settings = {}
    if 'settings_raw' in locals():
        merged_settings.update(settings_raw)
    if settings:
        merged_settings.update(settings)

    return CompactTopologyND(
        ndim=ndim,
        features=compact_features,
        regions=compact_regions,
        label_catalog=label_catalog,
        axis_names=axis_names,
        axis_ranges=axis_ranges,
        settings=merged_settings,
    )


def compact_from_csv(
    csv_dir: str | pathlib.Path,
    prefix: str = "topo",
    settings: Dict[str, Any] | None = None,
) -> CompactTopologyND:
    """Convenience wrapper: load CSVs and compact."""
    return compact_topology_nd(csv_dir, settings=settings, csv_prefix=prefix)


# ======================================================================
#  Dimension-specific compactors
# ======================================================================

def _compact_dim_0(feats: List[dict]) -> List[CompactFeature]:
    """0-D critical points — copy as-is (exact)."""
    result = []
    for f in feats:
        cf = CompactFeature(
            id=f["id"],
            dim=0,
            labels=f["labels"],
            btype=f["btype"],
            geometry_raw=f["geometry"],
            geometry_compact=f["geometry"],  # exact copy
            boundary_ids=f.get("boundary_ids", []),
            is_domain_edge=f.get("is_domain_edge", False),
            simplification_params={"method": "exact"},
        )
        result.append(cf)
    return result


def _compact_dim_1(
    feats: List[dict],
    dim0_features: List[CompactFeature],
    axis_names: List[str],
    axis_ranges: Dict[str, Tuple[float, float]],
    epsilon: float,
    envelope_n: int,
    axis_spacing: Dict[str, float] | None = None,
    axis_spacing_coarse: Dict[str, float] | None = None,
) -> List[CompactFeature]:
    """1-D curves — resolution-terminated farthest-point control polyline.

    The compact geometry is a control polygon of raw feature vertices,
    chosen by farthest-point insertion.  When the source raster spacing
    is known, insertion stops once every remaining deviation is below
    the normalized cell diagonal (times ``RDP_TAU_NORM_FACTOR``), so a
    boundary that is straight at grid resolution keeps only its
    endpoints; the envelope budget acts as a cap, not a target.  Closed
    loops keep at least ``RDP_LOOP_MIN_POINTS`` vertices (bounded by the
    raw count) with the resolution stop still active above that floor,
    so a sub-cell loop ships exactly the floor rather than filling the
    budget.  A planarity guard then subdivides any chord that properly
    crosses another feature's raw polyline, and a network separation pass
    subdivides chords of different features that cross or collinearly
    overlap (a bigon face otherwise collapses to a zero-area line), so
    compaction can never change region adjacency; both guards may exceed
    the envelope budget.
    Every control point is a raw vertex of the chain itself: the fixed
    topology is extracted from the deep-merged effective grid, so chains
    already meet exactly at their junction fence-posts and nothing is
    trimmed, anchored or re-attached here.  The adaptive RDP result is
    preserved in ``simplification_params`` for diagnostics.
    """
    tau_norm = _resolution_tau_norm(axis_names, axis_ranges, axis_spacing)
    loop_spacing = axis_spacing_coarse or axis_spacing or {}

    # Normalized raw segments of every feature: obstacle bank for the
    # planarity and separation guards.
    polylines = {f["id"]: _geometry_to_polyline(f["geometry"], axis_names)
                 for f in feats}
    seg_all, seg_fid = _segment_bank(polylines, axis_names, axis_ranges)

    pending: List[dict] = []
    for f in feats:
        geom_raw = f["geometry"]
        polyline = polylines[f["id"]]
        if len(polyline) < 2:
            pending.append({"kind": "too_short", "f": f,
                            "geom_raw": geom_raw, "polyline": polyline})
            continue

        # Incidence is discrete topology, not geometry to be guessed by
        # proximity.  An explicit empty list is authoritative for a closed
        # curve; a missing legacy field likewise remains unattached.
        bids = list(f.get("boundary_ids") or [])

        # NOTE: polyline endpoints are NOT snapped to junction
        # coordinates here.  The refined boundary already has
        # zero-information-loss endpoints at the actual transition
        # location; snapping would replace those with junction
        # vertex coordinates (an averaging/extrapolation operation
        # forbidden by spec).  The junction's own ``coords`` carry
        # the exact refined-grid vertex position, and the plotter
        # uses both layers independently.

        # Adaptive RDP remains useful as diagnostic tolerance-terminated
        # geometry.  The primary stored compact representation is the
        # farthest-point control polygon used by downstream compaction (for
        # example, as a surface constraint).  Pourbaix plots retain
        # ``geometry_raw`` as the exact categorical boundary and can overlay
        # the compact polygon as explicit chords between selected vertices.
        adaptive_eps = tau_norm if tau_norm is not None else epsilon
        adaptive, adaptive_t = simplify_curve(
            polyline, adaptive_eps, axis_ranges, axis_names)

        # Demotion rule: T1 self-contact waists are not anchor candidates;
        # the guards below may still re-add them where the compact
        # geometry would be unphysical.
        anchor_mask = f.get("anchor_flags") or None
        if anchor_mask is not None and len(anchor_mask) != len(polyline):
            anchor_mask = None  # misaligned legacy record: all eligible
        if anchor_mask is not None:
            anchor_mask = list(anchor_mask)
        n_anchor_disabled = (
            int(sum(1 for flag in anchor_mask if not flag))
            if anchor_mask is not None else 0
        )

        stop_eps = tau_norm
        min_pts = 2
        loop_closed = False
        loop_protected = False
        if tau_norm is not None:
            gap = _endpoint_gap_norm(polyline, axis_ranges, axis_names)
            loop_closed = gap <= tau_norm
            if loop_closed:
                # Protection = the min-4 floor; the resolution stop stays
                # active above it, so a sub-cell loop ships exactly 4 points.
                min_pts = RDP_LOOP_MIN_POINTS
                loop_protected = _loop_below_coarse_cell(
                    polyline, axis_names, loop_spacing)

        compact_polyline, compact_t, compact_indices = subsample_curve(
            polyline, envelope_n, axis_ranges, axis_names,
            return_indices=True,
            stop_epsilon=stop_eps, min_points=min_pts,
            anchor_mask=anchor_mask,
        )

        n_target = min(envelope_n, len(polyline))
        if stop_eps is not None and len(compact_polyline) < n_target:
            stop_reason = "resolution"
        elif len(polyline) > envelope_n:
            stop_reason = "budget"
        else:
            stop_reason = "exhausted"

        # Planarity guard: subdivide any chord that crosses another
        # boundary, so compaction can never change region adjacency.
        n_pre_guard = len(compact_indices)
        if stop_eps is not None and seg_all is not None:
            obstacles = seg_all[seg_fid != f["id"]]
            compact_indices = enforce_chord_planarity(
                polyline, compact_indices, obstacles,
                axis_ranges, axis_names)

        pending.append({
            "kind": "normal", "f": f, "geom_raw": geom_raw,
            "polyline": polyline, "bids": bids,
            "adaptive": adaptive, "adaptive_t": adaptive_t,
            "adaptive_eps": adaptive_eps, "stop_eps": stop_eps,
            "min_pts": min_pts, "loop_closed": loop_closed,
            "loop_protected": loop_protected, "stop_reason": stop_reason,
            "indices": list(compact_indices),
            "n_pre_guard": n_pre_guard,
            "n_post_planarity": len(compact_indices),
            "n_anchor_disabled": n_anchor_disabled,
        })

    # Network separation: chords of different features must not cross or
    # collinearly overlap, or thin bigon faces collapse to lines.
    sep_ids = [k for k, p in enumerate(pending)
               if p["kind"] == "normal" and p["stop_eps"] is not None]
    if sep_ids and seg_all is not None:
        norm_polys = []
        for k in sep_ids:
            arr = np.array(pending[k]["polyline"], dtype=np.float64)
            norm_polys.append(_normalize_coords(arr, axis_ranges, axis_names)
                              if axis_ranges and axis_names else arr)
        new_sels = enforce_chord_separation(
            norm_polys, [pending[k]["indices"] for k in sep_ids])
        for k, sel in zip(sep_ids, new_sels):
            pending[k]["indices"] = sel

    result = []
    for p in pending:
        if p["kind"] == "too_short":
            f = p["f"]
            result.append(CompactFeature(
                id=f["id"], dim=1, labels=f["labels"], btype=f["btype"],
                geometry_raw=p["geom_raw"], geometry_compact=p["polyline"],
                boundary_ids=f.get("boundary_ids", []),
                is_domain_edge=f.get("is_domain_edge", False),
                simplification_params={"method": "too_short"},
            ))
            continue
        f = p["f"]
        polyline = p["polyline"]
        compact_indices = sorted(set(p["indices"]))
        compact_polyline = [polyline[i] for i in compact_indices]
        compact_t = _arc_length_t_nd(compact_polyline)
        planarity_added = p["n_post_planarity"] - p["n_pre_guard"]
        separation_added = len(compact_indices) - p["n_post_planarity"]

        cf = CompactFeature(
            id=f["id"], dim=1, labels=f["labels"], btype=f["btype"],
            geometry_raw=p["geom_raw"],
            geometry_compact=compact_polyline,
            boundary_ids=p["bids"],
            is_domain_edge=f.get("is_domain_edge", False),
            simplification_params={
                "method": "farthest_point_1d",
                "epsilon": epsilon,
                "epsilon_used": p["adaptive_eps"],
                "resolution_tau_norm": tau_norm,
                "stop_epsilon": p["stop_eps"],
                "min_points": p["min_pts"],
                "loop_closed": p["loop_closed"],
                "loop_protected": p["loop_protected"],
                "stop_reason": p["stop_reason"],
                "planarity_added": planarity_added,
                "separation_added": separation_added,
                "anchor_disabled": p["n_anchor_disabled"],
                "raw_n": len(p["geom_raw"]),
                "compact_n": len(compact_polyline),
                "compact_target_n": envelope_n,
                "compact_indices": compact_indices,
                "t_params": compact_t,
                "envelope_n": envelope_n,
                "envelope_pts": compact_polyline,
                "envelope_t": compact_t,
                "adaptive_n": len(p["adaptive"]),
                "adaptive_pts": p["adaptive"],
                "adaptive_t": p["adaptive_t"],
            },
        )
        result.append(cf)
    return result


def _compact_dim_2(
    feats: List[dict],
    dim0_features: List[CompactFeature],
    dim1_features: List[CompactFeature],
    axis_names: List[str],
    axis_ranges: Dict[str, Tuple[float, float]],
    epsilon: float,
) -> List[CompactFeature]:
    """2-D surfaces — farthest-point insertion + Delaunay."""
    # Build lookup: feature id → compact polyline for dim-1
    curve_lookup: Dict[int, List[Tuple[float, ...]]] = {}
    for cf in dim1_features:
        gc = cf.geometry_compact
        if isinstance(gc, list):
            curve_lookup[cf.id] = gc

    result = []
    for f in feats:
        geom_raw = f["geometry"]
        bids = list(f.get("boundary_ids") or [])

        # Gather boundary curves
        boundary_curves = [curve_lookup[bid] for bid in bids
                           if bid in curve_lookup]

        vertices, triangles = simplify_surface(
            geom_raw, boundary_curves, epsilon, axis_ranges, axis_names)

        cf = CompactFeature(
            id=f["id"], dim=2, labels=f["labels"], btype=f["btype"],
            geometry_raw=geom_raw,
            geometry_compact=(vertices, triangles),
            boundary_ids=bids,
            is_domain_edge=f.get("is_domain_edge", False),
            simplification_params={
                "method": "farthest_point_2d",
                "epsilon": epsilon,
                "raw_n": len(geom_raw) if isinstance(geom_raw, list) else 0,
                "compact_n_verts": len(vertices),
                "compact_n_tris": len(triangles),
            },
        )
        result.append(cf)
    return result


def _compact_dim_k(
    feats: List[dict],
    compact_features: Dict[int, List[CompactFeature]],
    dim: int,
    axis_names: List[str],
    axis_ranges: Dict[str, Tuple[float, float]],
    epsilon: float,
) -> List[CompactFeature]:
    """k-dim manifolds (k≥3) — point thinning fallback."""
    # Gather boundary points from (dim-1) features
    lower = compact_features.get(dim - 1, [])
    boundary_pts_lookup: Dict[int, np.ndarray] = {}
    for cf in lower:
        gc = cf.geometry_compact
        if isinstance(gc, np.ndarray):
            boundary_pts_lookup[cf.id] = gc
        elif isinstance(gc, tuple) and len(gc) == 2:
            boundary_pts_lookup[cf.id] = gc[0]  # vertices of mesh

    result = []
    for f in feats:
        geom_raw = f["geometry"]
        bids = list(f.get("boundary_ids") or [])
        bnd_arrays = [boundary_pts_lookup[bid] for bid in bids
                      if bid in boundary_pts_lookup]

        thinned = simplify_manifold_k(
            geom_raw, bnd_arrays, epsilon, axis_ranges, axis_names)

        cf = CompactFeature(
            id=f["id"], dim=dim, labels=f["labels"], btype=f["btype"],
            geometry_raw=geom_raw,
            geometry_compact=thinned,
            boundary_ids=bids,
            is_domain_edge=f.get("is_domain_edge", False),
            simplification_params={
                "method": f"farthest_point_{dim}d",
                "epsilon": epsilon,
                "raw_n": len(geom_raw) if isinstance(geom_raw, list) else 0,
                "compact_n": len(thinned),
            },
        )
        result.append(cf)
    return result


# ======================================================================
#  Helpers
# ======================================================================

def _resolution_tau_norm(
    axis_names: List[str],
    axis_ranges: Dict[str, Tuple[float, float]],
    axis_spacing: Dict[str, float] | None,
) -> Optional[float]:
    """Normalized cell diagonal of the source raster, or None if unknown.

    Computed in the same range-normalized space the simplifiers measure
    deviations in; requires a positive spacing for every axis.
    """
    if not axis_spacing or not axis_names:
        return None
    total = 0.0
    for name in axis_names:
        sp = axis_spacing.get(name)
        if sp is None or float(sp) <= 0.0:
            return None
        lo, hi = (axis_ranges or {}).get(name, (0.0, 1.0))
        span = float(hi) - float(lo)
        if span < 1e-15:
            span = 1.0
        total += (float(sp) / span) ** 2
    return RDP_TAU_NORM_FACTOR * float(np.sqrt(total))


def _segment_bank(
    polylines: Dict[int, List[Tuple[float, ...]]],
    axis_names: List[str],
    axis_ranges: Dict[str, Tuple[float, float]],
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Normalized (S, 2, 2) segment array + owning feature id per segment.

    2-D only; returns (None, None) when the guard does not apply.
    """
    if len(axis_names) != 2:
        return None, None
    segs = []
    fids = []
    for fid, pl in polylines.items():
        if len(pl) < 2:
            continue
        arr = np.array(pl, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != 2:
            return None, None
        norm = _normalize_coords(arr, axis_ranges, axis_names) \
            if axis_ranges and axis_names else arr
        segs.append(np.stack([norm[:-1], norm[1:]], axis=1))
        fids.append(np.full(len(norm) - 1, fid, dtype=np.int64))
    if not segs:
        return None, None
    return np.concatenate(segs, axis=0), np.concatenate(fids, axis=0)


def _endpoint_gap_norm(
    polyline: List[Tuple[float, ...]],
    axis_ranges: Dict[str, Tuple[float, float]],
    axis_names: List[str],
) -> float:
    """Normalized distance between the first and last polyline vertices."""
    pts = np.array([polyline[0], polyline[-1]], dtype=np.float64)
    if axis_ranges and axis_names:
        pts = _normalize_coords(pts, axis_ranges, axis_names)
    return float(np.linalg.norm(pts[0] - pts[1]))


def _loop_below_coarse_cell(
    polyline: List[Tuple[float, ...]],
    axis_names: List[str],
    spacing: Dict[str, float],
) -> bool:
    """True if the loop's raw span on any axis is below one coarse cell."""
    if not spacing:
        return False
    arr = np.array(polyline, dtype=np.float64)
    for j, name in enumerate(axis_names):
        sp = spacing.get(name)
        if sp is None or float(sp) <= 0.0:
            continue
        span_j = float(arr[:, j].max() - arr[:, j].min())
        if span_j < RDP_MIN_LOOP_FACTOR * float(sp):
            return True
    return False


def _geometry_to_polyline(
    geom: Any,
    axis_names: List[str],
) -> List[Tuple[float, ...]]:
    """Convert various dim-1 geometry formats to list of N-D tuples."""
    if not geom:
        return []
    if isinstance(geom, list):
        if isinstance(geom[0], dict):
            return [tuple(p.get(n, 0.0) for n in axis_names) for p in geom]
        if isinstance(geom[0], (list, tuple)):
            return [tuple(pt) for pt in geom]
    return []
