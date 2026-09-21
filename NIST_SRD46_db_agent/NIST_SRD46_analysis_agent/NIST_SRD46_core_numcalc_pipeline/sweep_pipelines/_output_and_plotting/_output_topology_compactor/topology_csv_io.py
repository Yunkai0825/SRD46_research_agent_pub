"""
topology_csv_io.py
==================
Export raw topological features from a TopologyND into
dimension-stratified CSV files (one file per intrinsic dimension)
and reload them for downstream compaction.

CSV layout  — one row per feature
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  id, source_id, labels_json, dominant_species_ids_json, btype,
  boundary_ids_json, source_boundary_ids_json, is_domain_edge, geometry_json

``id`` and the ``boundary_ids_json`` cross-references carry the verdict
report's canonical prefixed ids (``DmsReg_/DmsRegEq_/DmsRegEqJnc_``) when
the exporter is given the verdict id maps; the ``source_*`` columns always
hold the raw numeric topology ids used for reload.

Sidecar files
~~~~~~~~~~~~~
  {prefix}_regions.csv   — id, source_id, label, dominant_species_id, name,
                           measure, boundary_ids_json,
                           source_boundary_ids_json, flags_json
  {prefix}_metadata.json — ndim, axis_names, axis_ranges, label_catalog

Public API
----------
- classify_features_by_dim  — TopologyND → Dict[int, List[dict]]
- export_features_csv       — TopologyND + dir → CSV files
- load_features_csv         — dir → (features_by_dim, regions, metadata)
"""

from __future__ import annotations

import csv
import json
import pathlib
from typing import Any, Dict, List, Tuple

import sys
_SOLVERS = str(pathlib.Path(__file__).resolve().parents[3] / "solvers_and_topology")
if _SOLVERS not in sys.path:
    sys.path.insert(0, _SOLVERS)

from nd_grid.data_types import (
    TopologyND, TopologyBoundary, TopologyJunction, TopologyRegion,
)
_SP = str(pathlib.Path(__file__).resolve().parents[2])
if _SP not in sys.path:
    sys.path.insert(0, _SP)
from sweep_pipelines._path_utils import long_path, safe_mkdir


# ======================================================================
#  Feature dimension classifier
# ======================================================================

def classify_features_by_dim(
    topo: TopologyND,
    axis_names: List[str] | None = None,
) -> Dict[int, List[dict]]:
    """Classify TopologyND features by intrinsic dimension.

    Returns
    -------
    Dict mapping intrinsic dimension (0, 1, 2, …) to a list of
    feature dicts with keys:
        id, labels, btype, boundary_ids, is_domain_edge, geometry
    """
    if axis_names is None:
        axis_names = (topo.settings or {}).get("axis_names", [])

    features: Dict[int, List[dict]] = {}
    ndim = topo.ndim

    # --- 0-D features: junctions (in 2-D+ grids) or crossover points (1-D grids) ---
    if ndim == 1:
        # 1-D grid: boundaries are crossover *points* (dim 0)
        for bnd in topo.boundaries:
            feat = _boundary_to_dict(bnd, intrinsic_dim=0, axis_names=axis_names, ndim=ndim)
            features.setdefault(0, []).append(feat)
    else:
        # 2-D+ grid: junctions → dim-0 features
        for jnc in topo.junctions:
            feat = _junction_to_dict(jnc, ndim=ndim)
            features.setdefault(feat["dim"], []).append(feat)

        # Boundaries → dim (ndim - 1) features  (1 for 2-D, 2 for 3-D, …)
        intrinsic = ndim - 1
        for bnd in topo.boundaries:
            feat = _boundary_to_dict(bnd, intrinsic_dim=intrinsic,
                                     axis_names=axis_names, ndim=ndim)
            features.setdefault(intrinsic, []).append(feat)

    return features


# ======================================================================
#  CSV exporter
# ======================================================================

_FEATURE_COLS = [
    "id", "source_id", "labels_json", "dominant_species_ids_json", "btype",
    "boundary_ids_json", "source_boundary_ids_json",
    "is_domain_edge", "geometry_json",
]
_REGION_COLS = ["id", "source_id", "label", "dominant_species_id", "name",
                "measure", "boundary_ids_json", "source_boundary_ids_json",
                "flags_json"]


def export_features_csv(
    topo: TopologyND,
    out_dir: str | pathlib.Path,
    prefix: str = "topo",
    axis_names: List[str] | None = None,
    verdict_ids: dict | None = None,
) -> List[str]:
    """Write dimension-stratified CSVs and metadata.

    ``verdict_ids`` (from ``predominance_verdict.verdict_feature_id_maps``)
    renames every feature/region row and cross-reference to the verdict
    report's canonical prefixed id; the raw numeric topology ids stay in the
    ``source_*`` columns.  Without it both id columns hold the source id.

    Returns list of file paths written.
    """
    out_dir = pathlib.Path(out_dir)
    safe_mkdir(out_dir)

    if axis_names is None:
        axis_names = (topo.settings or {}).get("axis_names", [])

    feature_ids = (verdict_ids or {}).get("features") or {}
    region_ids = (verdict_ids or {}).get("regions") or {}
    label_ids = (verdict_ids or {}).get("labels") or {}

    def _feature_id(dim: int, source_id: Any) -> Any:
        return feature_ids.get((dim, source_id), source_id)

    feats_by_dim = classify_features_by_dim(topo, axis_names)
    written: List[str] = []

    # --- Feature CSVs (one per dimension) ---
    for dim_k, feats in sorted(feats_by_dim.items()):
        fpath = out_dir / f"{prefix}_features_{dim_k}d.csv"
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_FEATURE_COLS)
            writer.writeheader()
            for f in feats:
                writer.writerow({
                    "id": _feature_id(dim_k, f["id"]),
                    "source_id": f["id"],
                    "labels_json": json.dumps(f["labels"]),
                    "dominant_species_ids_json": json.dumps(
                        [label_ids.get(lbl, lbl) for lbl in f["labels"]]),
                    "btype": f["btype"],
                    # A feature's boundary_ids reference features one
                    # intrinsic dimension below it.
                    "boundary_ids_json": json.dumps(
                        [_feature_id(dim_k - 1, b)
                         for b in f["boundary_ids"]]),
                    "source_boundary_ids_json": json.dumps(
                        f["boundary_ids"]),
                    "is_domain_edge": f["is_domain_edge"],
                    "geometry_json": json.dumps(f["geometry"]),
                })
        written.append(str(fpath))

    # --- Regions CSV ---
    codim_one = topo.ndim - 1
    rpath = out_dir / f"{prefix}_regions.csv"
    with open(long_path(rpath), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_REGION_COLS)
        writer.writeheader()
        for reg in topo.regions:
            writer.writerow({
                "id": region_ids.get(reg.id, reg.id),
                "source_id": reg.id,
                "label": reg.label,
                "dominant_species_id": label_ids.get(reg.label, reg.label),
                "name": reg.name,
                "measure": reg.measure,
                "boundary_ids_json": json.dumps(
                    [_feature_id(codim_one, b) for b in reg.boundary_ids]),
                "source_boundary_ids_json": json.dumps(reg.boundary_ids),
                "flags_json": json.dumps(
                    list(getattr(reg, "flags", []) or [])),
            })
    written.append(str(rpath))

    # --- Metadata JSON ---
    axis_ranges = _extract_axis_ranges(topo, axis_names)
    meta = {
        "ndim": topo.ndim,
        "axis_names": axis_names,
        "axis_ranges": axis_ranges,
        "label_catalog": topo.label_catalog or {},
    }
    for _spacing_key in ("axis_spacing", "axis_spacing_coarse"):
        _spacing = (topo.settings or {}).get(_spacing_key)
        if _spacing:
            meta[_spacing_key] = _spacing
    mpath = out_dir / f"{prefix}_metadata.json"
    with open(long_path(mpath), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    written.append(str(mpath))

    return written


# ======================================================================
#  CSV loader
# ======================================================================

def load_features_csv(
    csv_dir: str | pathlib.Path,
    prefix: str = "topo",
) -> Tuple[Dict[int, List[dict]], List[dict], dict]:
    """Load dimension-stratified CSVs and metadata.

    Returns
    -------
    (features_by_dim, regions, metadata)
    """
    csv_dir = pathlib.Path(csv_dir)

    # Metadata
    mpath = csv_dir / f"{prefix}_metadata.json"
    with open(mpath, "r", encoding="utf-8") as fh:
        metadata = json.load(fh)

    # Feature files — discover all matching CSVs
    features_by_dim: Dict[int, List[dict]] = {}
    for fpath in sorted(csv_dir.glob(f"{prefix}_features_*d.csv")):
        dim_k = int(fpath.stem.split("_")[-1].replace("d", ""))
        feats: List[dict] = []
        with open(fpath, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # Numeric linkage comes from source_* columns; legacy files
                # (no source columns) carried the numeric ids directly.
                source_id = row.get("source_id")
                source_bids = row.get("source_boundary_ids_json")
                feats.append({
                    "id": int(source_id) if source_id else int(row["id"]),
                    "verdict_id": row["id"],
                    "dim": dim_k,
                    "labels": json.loads(row["labels_json"]),
                    "btype": row["btype"],
                    "boundary_ids": json.loads(
                        source_bids if source_bids
                        else row["boundary_ids_json"]),
                    "is_domain_edge": row["is_domain_edge"].lower() in ("true", "1"),
                    "geometry": json.loads(row["geometry_json"]),
                })
        features_by_dim[dim_k] = feats

    # Regions
    regions: List[dict] = []
    rpath = csv_dir / f"{prefix}_regions.csv"
    if rpath.exists():
        with open(rpath, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                source_id = row.get("source_id")
                source_bids = row.get("source_boundary_ids_json")
                regions.append({
                    "id": int(source_id) if source_id else int(row["id"]),
                    "verdict_id": row["id"],
                    "label": int(row["label"]),
                    "name": row["name"],
                    "measure": float(row["measure"]),
                    "boundary_ids": json.loads(
                        source_bids if source_bids
                        else row["boundary_ids_json"]),
                    "flags": json.loads(row.get("flags_json") or "[]"),
                })

    return features_by_dim, regions, metadata


# ======================================================================
#  Internal helpers
# ======================================================================

def _junction_to_dict(jnc: TopologyJunction, *, ndim: int) -> dict:
    """Convert a TopologyJunction to a flat feature dict."""
    intrinsic = getattr(jnc, "intrinsic_dim", 0)
    # For 0-D junctions (triple points, quad points) geometry is the centroid.
    # For higher-dim junctions (e.g. triple lines in 3-D, intrinsic_dim=1)
    # use the stored point-cloud geometry if available.
    if intrinsic >= 1 and jnc.geometry is not None:
        geom = jnc.geometry
    else:
        geom = jnc.coords  # Dict[str, float]
    return {
        "id": jnc.id,
        "dim": intrinsic,
        "labels": list(jnc.adjacent_labels),
        "btype": "junction",
        "boundary_ids": [],
        "is_domain_edge": jnc.is_domain_edge,
        "geometry": geom,
    }


def _boundary_to_dict(
    bnd: TopologyBoundary,
    *,
    intrinsic_dim: int,
    axis_names: List[str],
    ndim: int,
) -> dict:
    """Convert a TopologyBoundary to a flat feature dict."""
    geom = bnd.geometry
    if intrinsic_dim == 0:
        # 1-D grid crossover point  — geometry is float
        if isinstance(geom, (int, float)):
            axis_name = axis_names[0] if axis_names else "x"
            geom = {axis_name: float(geom)}
    elif intrinsic_dim == 1:
        # 2-D grid polyline — List[Tuple[float, float]]
        if isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
            geom = [list(pt) for pt in geom]
    # intrinsic_dim >= 2: geometry kept as-is (point cloud dicts)

    return {
        "id": bnd.id,
        "dim": intrinsic_dim,
        "labels": sorted([bnd.left_label, bnd.right_label]),
        "btype": bnd.btype,
        "boundary_ids": list(bnd.junction_ids) if bnd.junction_ids else [],
        "is_domain_edge": False,  # boundaries don't have this flag directly
        "geometry": geom,
        # Envelope-rule RDP anchor eligibility; [] on legacy objects/CSVs.
        "anchor_flags": list(getattr(bnd, "anchor_flags", []) or []),
    }


def _extract_axis_ranges(
    topo: TopologyND,
    axis_names: List[str],
) -> Dict[str, List[float]]:
    """Pull axis ranges from topology settings."""
    settings = topo.settings or {}
    axis_ranges: Dict[str, List[float]] = {}
    raw = settings.get("axis_ranges", {})
    if raw:
        return {k: list(v) for k, v in raw.items()}
    # Fallback: try to infer from junction/boundary coordinates
    for jnc in topo.junctions:
        for name, val in jnc.coords.items():
            lo, hi = axis_ranges.get(name, [val, val])
            axis_ranges[name] = [min(lo, val), max(hi, val)]
    return axis_ranges
