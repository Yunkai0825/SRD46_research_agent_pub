"""
topology_export.py
==================
Serialization of topology results to JSON.

Supports both:
- Legacy ``TopologyMap`` (with ``.nodes``, ``.edges``, ``.faces``)
- New ``TopologyND`` (with ``.junctions``, ``.boundaries``, ``.regions``)
"""

from __future__ import annotations

import json
import numpy as np
from typing import Any, Dict, List, Optional

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solver_settings import DEBUG
from sweep_pipelines._path_utils import long_path, safe_mkdir


def export_topology_json(
    topo,
    output_path: str,
    metadata: Optional[Dict[str, Any]] = None,
    debug: bool = DEBUG,
) -> None:
    """
    Serialize a TopologyMap, TopologyND, or CompactTopologyND to JSON.

    The **generalized N-D format** groups features by intrinsic dimension::

        {
            "metadata": {..., "ndim": N},
            "label_catalog": {"0": "Fe2+", ...},
            "regions": [{ id, label, name, boundary_ids, measure, flags }],
            "features_0d": [{ id, labels, btype, geometry, ... }],  # codim-N
            "features_1d": [{ id, labels, btype, geometry, ... }],  # codim-(N-1)
            ...
            "features_(N-1)d": [{ id, labels, btype, geometry, ... }],  # codim-1
        }

    Backward-compatible ``nodes``/``edges``/``faces`` keys are still
    emitted for 2-D topologies and CompactTopologyND objects.

    Parameters
    ----------
    topo        : TopologyMap (legacy) or TopologyND (new) or CompactTopologyND
    output_path : path to write JSON file
    metadata    : optional metadata dict (system_name, temperature, etc.)
    debug       : enable verbose output
    """
    meta = dict(metadata or {})
    bulk_field = meta.pop("bulk_field", None)

    if hasattr(topo, "features") and isinstance(getattr(topo, "features", None), dict):
        doc = _serialize_compact_nd(topo, meta)
    elif hasattr(topo, "boundaries"):
        doc = _serialize_topology_nd(topo, meta)
    else:
        doc = _serialize_topology_map(topo, meta)

    if bulk_field is not None:
        doc["bulk_field"] = _serialize_bulk_field(bulk_field)

    out_path = pathlib.Path(output_path)
    safe_mkdir(out_path.parent)

    with open(long_path(out_path), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False, default=_json_default)

    if debug:
        print(f"[export] Topology JSON written to {out_path}")
        # Summarise by dimension
        for k in sorted(doc):
            if k.startswith("features_"):
                print(f"  {k}: {len(doc[k])} features")
        n_regions = len(doc.get("regions", doc.get("faces", [])))
        print(f"  regions: {n_regions}")


def _serialize_bulk_field(bulk_field: Any) -> Dict[str, Any]:
    """Serialize cell-based bulk region colouring data."""
    if not isinstance(bulk_field, dict):
        return {}

    axis_names = list(bulk_field.get("axis_names", []))
    axis_values_in = bulk_field.get("axis_values", {})
    axis_values = {}
    if isinstance(axis_values_in, dict):
        for name, vals in axis_values_in.items():
            arr = np.asarray(vals, dtype=float)
            axis_values[str(name)] = arr.tolist()

    axis_ranges_in = bulk_field.get("axis_ranges", {})
    axis_ranges = {}
    if isinstance(axis_ranges_in, dict):
        for name, bounds in axis_ranges_in.items():
            values = np.asarray(bounds, dtype=float).reshape(-1)
            if values.size == 2:
                axis_ranges[str(name)] = values.tolist()

    labels = np.asarray(bulk_field.get("labels", []))
    return {
        "axis_names": axis_names,
        "axis_values": axis_values,
        "axis_ranges": axis_ranges,
        "labels": labels.tolist(),
    }


def _serialize_topology_nd(topo, metadata) -> Dict:
    """Serialize a TopologyND object using the generalized N-D format.

    Features are grouped by intrinsic dimension:
      - features_0d: 0-D critical points (codim-N; e.g. quad-points in 3D)
      - features_1d: 1-D curves (codim-(N-1); e.g. triple-lines in 3D, phase-boundary lines in 2D)
      - features_(N-1)d: (N-1)-D manifolds (codim-1; e.g. phase-boundary surfaces in 3D)
      - regions: N-D connected regions (codim-0)

    For a 2-D system (N=2): features_0d = triple points, features_1d = boundary lines, regions.
    For a 3-D system (N=3): features_0d = quad points, features_1d = triple lines,
                            features_2d = boundary surfaces, regions.
    """
    ndim = topo.ndim
    doc = {}
    doc["metadata"] = metadata or {}
    doc["metadata"]["topology_settings"] = topo.settings
    doc["metadata"]["ndim"] = ndim

    catalog = {}
    for k, v in topo.label_catalog.items():
        catalog[str(k)] = _serialize_label(v)
    doc["label_catalog"] = catalog

    axis_names = (topo.settings.get("axis_names", [])
                  if topo.settings else [])

    # ── Classify junctions by intrinsic dimension ──────────────
    # In the current extraction, junctions are cells where ≥3 labels meet.
    # For N-D, the intrinsic dimension of a junction where k regions meet is:
    #   intrinsic_dim = N - k  (when k ≤ N)
    # But we also use the junction's own .intrinsic_dim if set.
    # Additionally, group by the actual label set to find connected
    # components that form higher-dimensional features.
    junctions_by_dim = _classify_junctions_by_dim(topo.junctions, ndim)

    # ── Build features by dimension ────────────────────────────

    # codim-1 features: (N-1)-D boundary surfaces/lines between 2 regions
    codim1_key = f"features_{ndim - 1}d"
    codim1_list = []
    for bnd in topo.boundaries:
        feat = {
            "id": bnd.id,
            "labels": sorted([bnd.left_label, bnd.right_label]),
            "btype": bnd.btype,
            "junction_ids": bnd.junction_ids,
        }
        feat["geometry"] = _serialize_boundary_geometry(
            bnd.geometry, ndim, axis_names)
        codim1_list.append(feat)
    doc[codim1_key] = codim1_list

    # codim-2 to codim-N features: from junctions classified by intrinsic dim
    for idim in range(ndim - 2, -1, -1):
        key = f"features_{idim}d"
        feat_list = []
        for jnc in junctions_by_dim.get(idim, []):
            feat = {
                "id": jnc.id,
                "labels": jnc.adjacent_labels,
                "is_domain_edge": jnc.is_domain_edge,
                "coords": {k: round(v, 6) for k, v in jnc.coords.items()},
            }
            # Higher-dim junctions may have geometry (curves, etc.)
            if jnc.geometry is not None:
                feat["geometry"] = _serialize_boundary_geometry(
                    jnc.geometry, idim, axis_names)
            feat_list.append(feat)
        doc[key] = feat_list

    # codim-0: regions
    regions_json = []
    for reg in topo.regions:
        regions_json.append({
            "id": reg.id,
            "label": _serialize_label(reg.label),
            "name": reg.name,
            "boundary_ids": reg.boundary_ids,
            "measure": round(reg.measure, 6),
            "flags": list(getattr(reg, "flags", []) or []),
        })
    doc["regions"] = regions_json

    # ── Backward compat for 2-D (nodes/edges/faces) ───────────
    if ndim == 2:
        doc["nodes"] = _topology_nd_to_legacy_nodes(topo)
        doc["edges"] = _topology_nd_to_legacy_edges(topo, axis_names)
        doc["faces"] = _topology_nd_to_legacy_faces(topo)

    return doc


def _classify_junctions_by_dim(junctions, ndim):
    """Group junctions by their intrinsic dimension.

    The intrinsic dimension of a feature where k regions meet in an
    N-D system is N - k + 1 (clamped to ≥ 0).  Each additional
    region constraint removes one dimension:
      - 2 regions meet → (N-1)-D → handled by boundary_builder, not here
      - 3 regions meet → (N-2)-D → triple point (2D) or triple line (3D)
      - 4 regions meet → (N-3)-D → quad point (3D)

    If the junction already has ``intrinsic_dim`` explicitly set > 0,
    that value is used instead.

    Returns dict mapping intrinsic_dim → list of TopologyJunction.
    """
    by_dim = {}
    for jnc in junctions:
        k = len(jnc.adjacent_labels)
        # Use explicit intrinsic_dim if set, otherwise compute from k
        if hasattr(jnc, 'intrinsic_dim') and jnc.intrinsic_dim > 0:
            idim = jnc.intrinsic_dim
        else:
            idim = max(ndim - k + 1, 0)
        by_dim.setdefault(idim, []).append(jnc)
    return by_dim


def _serialize_boundary_geometry(geom, ndim_or_idim, axis_names):
    """Serialize boundary/junction geometry to JSON-safe form."""
    if geom is None:
        return None
    if isinstance(geom, (int, float)):
        # 1-D: scalar coordinate
        d = {"value": round(float(geom), 6)}
        if axis_names:
            d["axis_name"] = axis_names[0]
        return d
    if isinstance(geom, list) and geom:
        if isinstance(geom[0], (tuple, list)):
            # Polyline: list of tuples
            return {"polyline": [
                [round(x, 6) for x in pt] for pt in geom],
                "axis_order": axis_names[:len(geom[0])] if axis_names else None,
            }
        if isinstance(geom[0], dict):
            # Point cloud: list of coord dicts
            return {"point_cloud": [
                {k: round(v, 6) for k, v in pt.items()} for pt in geom]}
    if isinstance(geom, dict):
        return {k: round(v, 6) if isinstance(v, float) else v
                for k, v in geom.items()}
    return _serialize_geometry(geom)


# ── Backward-compat helpers for 2-D legacy format ─────────────

def _topology_nd_to_legacy_nodes(topo):
    """Convert TopologyND junctions to legacy node dicts."""
    nodes = []
    for jnc in topo.junctions:
        node = {
            "id": jnc.id,
            "coords": {k: round(v, 6) for k, v in jnc.coords.items()},
            "labels": jnc.adjacent_labels,
            "domain_edge": jnc.is_domain_edge,
        }
        if "pH" in jnc.coords:
            node["pH"] = round(jnc.coords["pH"], 6)
        if "E_V" in jnc.coords:
            node["E"] = round(jnc.coords["E_V"], 6)
        nodes.append(node)
    return nodes


def _topology_nd_to_legacy_edges(topo, axis_names):
    """Convert TopologyND boundaries to legacy edge dicts."""
    edges = []
    for bnd in topo.boundaries:
        edge_dict = {
            "id": bnd.id,
            "type": bnd.btype,
            "left_label": bnd.left_label,
            "right_label": bnd.right_label,
            "junction_ids": bnd.junction_ids,
        }
        geom = bnd.geometry
        if isinstance(geom, (int, float)):
            edge_dict["geometry_1d"] = round(float(geom), 6)
            if axis_names:
                edge_dict["axis_name"] = axis_names[0]
        elif isinstance(geom, list) and geom:
            if isinstance(geom[0], (tuple, list)):
                edge_dict["polyline_raw"] = [
                    [round(p[i], 6) for i in range(len(p))] for p in geom]
                if axis_names:
                    edge_dict["axis_order"] = axis_names[:len(geom[0])]
            elif isinstance(geom[0], dict):
                edge_dict["point_cloud"] = [
                    {k: round(v, 6) for k, v in pt.items()} for pt in geom]
        edges.append(edge_dict)
    return edges


def _topology_nd_to_legacy_faces(topo):
    """Convert TopologyND regions to legacy face dicts."""
    faces = []
    for reg in topo.regions:
        faces.append({
            "id": reg.id,
            "label": _serialize_label(reg.label),
            "name": reg.name,
            "edges": reg.boundary_ids,
            "measure": round(reg.measure, 6),
        })
    return faces


def _serialize_compact_nd(topo, metadata) -> Dict:
    """Serialize a CompactTopologyND object."""
    doc = {}
    doc["metadata"] = metadata or {}
    doc["metadata"]["ndim"] = topo.ndim
    doc["metadata"]["axis_names"] = topo.axis_names
    doc["metadata"]["axis_ranges"] = {
        k: list(v) for k, v in topo.axis_ranges.items()}
    doc["metadata"]["topology_settings"] = topo.settings

    catalog = {}
    for k, v in topo.label_catalog.items():
        catalog[str(k)] = _serialize_label(v)
    doc["label_catalog"] = catalog

    # Features grouped by dimension
    for dim_k, feats in sorted(topo.features.items()):
        key = f"features_{dim_k}d"
        feat_list = []
        for cf in feats:
            fd = {
                "id": cf.id,
                "labels": cf.labels,
                "btype": cf.btype,
                "boundary_ids": cf.boundary_ids,
                "is_domain_edge": cf.is_domain_edge,
                "simplification": cf.simplification_params,
            }
            # Geometry: raw
            fd["geometry_raw"] = _serialize_geometry(cf.geometry_raw)
            # Geometry: compact
            fd["geometry_compact"] = _serialize_geometry(cf.geometry_compact)
            feat_list.append(fd)
        doc[key] = feat_list

    doc["regions"] = [
        {
            "id": r.id,
            "label": _serialize_label(r.label),
            "name": r.name,
            "boundary_ids": r.boundary_ids,
            "measure": round(r.measure, 6),
            "flags": list(getattr(r, "flags", []) or []),
        }
        for r in topo.regions
    ]

    # Backward compat: nodes, edges, faces from features
    doc["nodes"] = _compact_features_to_nodes(topo)
    doc["edges"] = _compact_features_to_edges(topo)
    doc["faces"] = [
        {"id": r.id, "label": _serialize_label(r.label),
         "name": r.name, "edges": r.boundary_ids,
         "measure": round(r.measure, 6)}
        for r in topo.regions
    ]

    return doc


def _serialize_geometry(geom) -> Any:
    """Convert geometry to JSON-safe form."""
    if geom is None:
        return None
    if isinstance(geom, dict):
        return {k: round(v, 6) if isinstance(v, float) else v
                for k, v in geom.items()}
    if isinstance(geom, (list, tuple)):
        if geom and isinstance(geom[0], (list, tuple)):
            return [[round(x, 6) for x in pt] for pt in geom]
        if geom and isinstance(geom[0], dict):
            return [{k: round(v, 6) for k, v in pt.items()} for pt in geom]
        if len(geom) == 2 and hasattr(geom[0], 'tolist'):
            # (vertices, triangles) tuple from surface simplifier
            return {"vertices": geom[0].tolist(),
                    "triangles": geom[1].tolist()}
    if hasattr(geom, 'tolist'):
        return geom.tolist()
    return geom


def _compact_features_to_nodes(topo) -> List[Dict]:
    """Extract 0-D features as backward-compatible node dicts."""
    nodes = []
    for cf in topo.features.get(0, []):
        gc = cf.geometry_compact
        if isinstance(gc, dict):
            node = {"id": cf.id, "coords": gc,
                    "labels": cf.labels,
                    "domain_edge": cf.is_domain_edge}
            if "pH" in gc:
                node["pH"] = round(gc["pH"], 6)
            if "E_V" in gc:
                node["E"] = round(gc["E_V"], 6)
            nodes.append(node)
    return nodes


def _compact_features_to_edges(topo) -> List[Dict]:
    """Extract 1-D features as backward-compatible edge dicts."""
    edges = []
    for cf in topo.features.get(1, []):
        edge = {
            "id": cf.id,
            "type": cf.btype,
            "left_label": cf.labels[0] if cf.labels else -1,
            "right_label": cf.labels[1] if len(cf.labels) > 1 else -1,
            "junction_ids": cf.boundary_ids,
        }
        raw = cf.geometry_raw
        compact = cf.geometry_compact
        if isinstance(raw, list) and raw:
            if isinstance(raw[0], (list, tuple)):
                edge["polyline_raw"] = [
                    [round(x, 6) for x in pt] for pt in raw]
        if isinstance(compact, list) and compact:
            if isinstance(compact[0], (list, tuple)):
                edge["polyline_compact"] = [
                    [round(x, 6) for x in pt] for pt in compact]
        sp = cf.simplification_params
        if sp.get("envelope_pts"):
            edge["envelope"] = {
                "points": [[round(x, 6) for x in pt]
                           for pt in sp["envelope_pts"]],
                "t": [round(t, 6) for t in sp.get("envelope_t", [])],
            }
        edges.append(edge)
    return edges


def _serialize_topology_map(topo, metadata) -> Dict:
    """Serialize a legacy TopologyMap object."""
    doc = {}
    doc["metadata"] = metadata or {}
    doc["metadata"]["topology_settings"] = topo.settings

    catalog = {}
    for k, v in topo.label_catalog.items():
        catalog[str(k)] = _serialize_label(v)
    doc["label_catalog"] = catalog

    nodes_json = []
    for tp in topo.nodes:
        nodes_json.append({
            "id": tp.id,
            "pH": round(tp.pH, 6),
            "E": round(tp.E_V, 6),
            "labels": tp.labels,
            "domain_edge": tp.is_domain_edge,
        })
    doc["nodes"] = nodes_json

    edges_json = []
    for edge in topo.edges:
        edge_dict = {
            "id": edge.id,
            "node_start": edge.node_start,
            "node_end": edge.node_end,
            "type": edge.boundary_type,
            "left_label": edge.left_label,
            "right_label": edge.right_label,
            "polyline_raw": [[round(p[0], 6), round(p[1], 6)]
                             for p in edge.polyline_raw],
        }
        if edge.rdp_points is not None:
            edge_dict["rdp"] = {
                "points": [[round(p[0], 6), round(p[1], 6)]
                           for p in edge.rdp_points],
                "t": [round(t, 6) for t in (edge.rdp_t or [])],
            }
        if edge.lasso_coeffs_pH is not None:
            edge_dict["lasso"] = {
                "coeffs_pH": [round(c, 8) for c in edge.lasso_coeffs_pH],
                "coeffs_E": [round(c, 8) for c in (edge.lasso_coeffs_E or [])],
                "degree": edge.lasso_degree or 0,
            }
        edges_json.append(edge_dict)
    doc["edges"] = edges_json

    faces_json = []
    for face in topo.faces:
        faces_json.append({
            "id": face.id,
            "label": _serialize_label(face.label),
            "edges": face.edge_ids,
            "area_approx": round(face.area_approx, 6),
        })
    doc["faces"] = faces_json

    return doc


def _serialize_label(label) -> Any:
    """Convert label tuple/str to JSON-safe form."""
    if isinstance(label, tuple):
        return list(label)
    if isinstance(label, np.integer):
        return int(label)
    if isinstance(label, np.floating):
        return float(label)
    return label


def _json_default(obj):
    """Default JSON encoder for numpy types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        from solvers_and_topology.nd_grid.data_types import (
            TopologyND, TopologyBoundary, TopologyJunction, TopologyRegion,
        )
    except ImportError:
        from nd_grid.data_types import (
            TopologyND, TopologyBoundary, TopologyJunction, TopologyRegion,
        )

    junctions = [
        TopologyJunction(id=0, coords={"pH": 4.0, "E_V": 0.5},
                         adjacent_labels=[0, 1, 2], is_domain_edge=False),
        TopologyJunction(id=1, coords={"pH": 0.0, "E_V": 0.3},
                         adjacent_labels=[0, 1], is_domain_edge=True),
    ]
    boundaries = [
        TopologyBoundary(id=0, left_label=0, right_label=1,
                         btype="aqueous_crossover",
                         geometry=[(0.0, 0.3), (2.0, 0.4), (4.0, 0.5)],
                         junction_ids=[0, 1]),
    ]
    regions = [
        TopologyRegion(id=0, label=0, name="Fe2+", measure=5.0,
                       boundary_ids=[0]),
        TopologyRegion(id=1, label=1, name="Fe3+", measure=3.0,
                       boundary_ids=[0]),
    ]
    catalog = {0: "Fe2+", 1: "Fe3+", 2: "Fe(OH)3(s)"}

    topo = TopologyND(
        ndim=2,
        junctions=junctions,
        boundaries=boundaries,
        regions=regions,
        label_catalog=catalog,
        settings={"axis_names": ["pH", "E_V"]},
    )

    out_path = str(pathlib.Path(__file__).resolve().parents[1] / "_output" / "test_topology.json")
    export_topology_json(topo, out_path, metadata={"system_name": "test"}, debug=True)

    # Verify by reading back
    with open(out_path) as f:
        data = json.load(f)
    print(f"Read back: features_0d={len(data.get('features_0d', []))}, "
          f"features_1d={len(data.get('features_1d', []))}, "
          f"regions={len(data.get('regions', []))}")
