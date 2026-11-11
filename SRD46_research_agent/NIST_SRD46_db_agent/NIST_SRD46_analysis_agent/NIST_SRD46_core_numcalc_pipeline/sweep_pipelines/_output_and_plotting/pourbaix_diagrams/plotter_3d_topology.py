"""
plotter_3d_topology.py
======================
Rich 3D Pourbaix topology plotter.

Reads a **generalized N-D topology JSON** (features grouped by intrinsic
dimension) and renders:

  - Transparent coloured bulk voxels from the refined label field.
  - Exact codim-1 boundary cell faces from that refined field when
    available, falling back to compact triangulated surfaces otherwise.
  - Codim-2 triple-line curves (``features_1d``) where three regions meet,
    rendered as thick coloured 3-D polylines.
  - Codim-3 junction-point markers (``features_0d``) sized by the number
    of bordering regions.

Backward compatible: also reads the legacy ``nodes / edges / faces``
format produced by the 2-D compactor.
"""

from __future__ import annotations

import csv
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from matplotlib.colors import to_rgba
import sys as _sys
_SP = str(Path(__file__).resolve().parents[2])
if _SP not in _sys.path:
    _sys.path.insert(0, _SP)
from sweep_pipelines._path_utils import long_path

# ── palette ──────────────────────────────────────────────────────
_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#86bcb6", "#8cd17d", "#b6992d", "#499894", "#f1ce63",
    "#d37295", "#a0cbe8", "#ffbe7d", "#d4a6c8", "#fabfd2",
]

_BOUNDARY_TYPE_STYLE = {
    "solid_solid":       {"color": "#222222", "alpha": 0.50, "lw": 0.6},
    "solid_onset":       {"color": "#0066cc", "alpha": 0.45, "lw": 0.5},
    "aqueous_crossover": {"color": "#cc3300", "alpha": 0.40, "lw": 0.4},
}


# ── public API ───────────────────────────────────────────────────

def plot_3d_topology(
    topo_json_path: Union[str, Path],
    out_path: Union[str, Path],
    *,
    axes_order: Tuple[str, str, str] = ("pH", "a_w", "E_V"),
    show_bulk_cells: bool = True,
    show_regions: bool = False,
    show_boundaries: bool = True,
    show_boundary_mesh_edges: bool = False,
    show_triple_lines: bool = True,
    show_nodes: bool = True,
    bulk_alpha: float = 0.10,
    region_alpha: float = 0.15,
    boundary_alpha: float = 0.45,
    figsize: Tuple[int, int] = (14, 10),
    dpi: int = 150,
    elev: float = 25,
    azim: float = -60,
    title: Optional[str] = None,
) -> Path:
    """Render a rich 3D topology plot from a topology JSON file.

    Reads either:
    - **Generalized N-D format**: ``regions``, ``features_2d`` (codim-1
      boundary surfaces), ``features_1d`` (codim-2 triple lines),
      ``features_0d`` (codim-3 junction points).
    - **Legacy format**: ``faces``, ``edges``, ``nodes``.

    Parameters
    ----------
    topo_json_path : path to the topology JSON produced by the compactor.
    out_path : destination PNG path.
    axes_order : 3-tuple of axis names mapping to (x, y, z).
    show_bulk_cells : render transparent bulk colouring directly from the
        exported label grid when available.
    show_regions : render transparent convex-hull polyhedra for regions.
        Disabled by default because convex hulls are misleading for
        disconnected or non-convex stability domains.
    show_boundaries : render exact codim-1 boundary cell faces when the
        refined label field is available, else compact triangulated
        boundary surfaces from the topology JSON.
    show_boundary_mesh_edges : draw triangulation edges on boundary surfaces.
        Disabled by default because it overwhelms simple chemistries.
    show_triple_lines : render triple-line curves (codim-2, 3D only).
    show_nodes : render junction-point markers (codim-3 / codim-N).
    bulk_alpha : transparency for the cell-based bulk colouring layer.
    region_alpha : transparency for region hulls.
    boundary_alpha : transparency for boundary surfaces.

    Returns
    -------
    Path to the saved figure.
    """
    topo_json_path = Path(topo_json_path)
    out_path = Path(out_path)

    with open(long_path(topo_json_path), "r", encoding="utf-8") as fh:
        topo = json.load(fh)

    label_catalog = topo.get("label_catalog", {})
    meta = topo.get("metadata", {})
    ndim = meta.get("ndim", 3)
    ax_names = tuple(axes_order)

    # Axis order in the stored topology (for compact vertex column mapping)
    topo_axis_names = meta.get("axis_names", [])
    if not topo_axis_names:
        ts = meta.get("topology_settings", {})
        topo_axis_names = ts.get("axis_names", list(axes_order))

    # ── Read generalized format with legacy fallback ────────────
    regions = topo.get("regions", topo.get("faces", []))
    boundaries = _read_boundaries(topo, ndim)       # codim-1
    triple_lines = _read_triple_lines(topo, ndim)   # codim-2
    quad_points = _read_quad_points(topo, ndim)      # codim-3 / codim-N

    # Build colour map for region labels
    all_labels = sorted(set(int(k) for k in label_catalog))
    label_color = {lbl: _PALETTE[i % len(_PALETTE)]
                   for i, lbl in enumerate(all_labels)}

    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)

    axis_ranges = meta.get("axis_ranges", {})
    if not axis_ranges:
        axis_ranges = meta.get("topology_settings", {}).get(
            "axis_ranges", {}
        )

    # ── 1. exact bulk field, with backward-compatible recovery ──
    bulk_field = topo.get("bulk_field")
    if bulk_field is None and ndim == 3:
        bulk_field = _recover_bulk_field_from_neighbor_slices(
            topo_json_path, topo, topo_axis_names)

    # ── 1a. transparent bulk voxels ─────────────────────────────
    if show_bulk_cells and ndim == 3 and bulk_field:
        _draw_bulk_cells(
            ax, bulk_field, label_color, ax_names,
            alpha=bulk_alpha, axis_ranges=axis_ranges,
        )

    # ── 1b. optional convex-hull proxy regions ──────────────────
    if show_regions and regions and boundaries:
        _draw_region_hulls(ax, regions, boundaries, label_catalog,
                           label_color, ax_names, region_alpha,
                           topo_axis_names=topo_axis_names)

    # ── 2. exact N-1 faces when available; compact mesh fallback ─
    exact_boundaries_drawn = False
    if show_boundaries and ndim == 3 and bulk_field:
        exact_boundaries_drawn = _draw_exact_boundary_faces(
            ax, bulk_field, label_color, ax_names,
            alpha=boundary_alpha, axis_ranges=axis_ranges,
        )

    if show_boundaries and boundaries and not exact_boundaries_drawn:
        _draw_boundary_surfaces(ax, boundaries, label_catalog, label_color,
                                ax_names, boundary_alpha,
                                show_mesh_edges=show_boundary_mesh_edges,
                                topo_axis_names=topo_axis_names)

    # ── 3. triple-line curves (codim-2) ─────────────────────────
    if show_triple_lines and triple_lines:
        _draw_triple_lines(ax, triple_lines, label_catalog, label_color,
                           ax_names, topo_axis_names=topo_axis_names)

    # ── 4. junction nodes (codim-3 / codim-N) ──────────────────
    if show_nodes and quad_points:
        _draw_junction_nodes(ax, quad_points, label_catalog, label_color,
                             ax_names)

    # ── axes & legend ───────────────────────────────────────────
    ax.set_xlabel(ax_names[0], fontsize=10)
    ax.set_ylabel(ax_names[1], fontsize=10)
    ax.set_zlabel(ax_names[2], fontsize=10)
    limit_setters = (ax.set_xlim, ax.set_ylim, ax.set_zlim)
    for name, setter in zip(ax_names, limit_setters):
        bounds = axis_ranges.get(name)
        if bounds is not None and len(bounds) == 2:
            setter(float(bounds[0]), float(bounds[1]))

    if title is None:
        sys_name = meta.get("system_name", "")
        elem = meta.get("element", "")
        title = f"3D Pourbaix topology: {sys_name} ({elem})"
    ax.set_title(title, fontsize=11, pad=12)

    # Region legend
    _add_region_legend(ax, regions, label_catalog, label_color)

    # ``bbox_inches='tight'`` can crop projected 3-D axis labels, the title,
    # and the outside legend after explicit domain limits are applied.
    # Reserve their margins in the fixed canvas instead.
    fig.subplots_adjust(left=0.03, right=0.82, bottom=0.08, top=0.92)
    fig.savefig(long_path(out_path), dpi=dpi)
    plt.close(fig)
    return out_path


# ── internal helpers ─────────────────────────────────────────────

def _pt3(pt: dict, ax_names: Tuple[str, str, str]):
    """Extract (x, y, z) from a point dict according to axis order."""
    return (pt[ax_names[0]], pt[ax_names[1]], pt[ax_names[2]])


def _cell_edges(
    vals: np.ndarray,
    domain_range: Optional[Tuple[float, float]] = None,
) -> np.ndarray:
    """Convert sample centres to voxel edges within declared fenceposts."""
    vals = np.asarray(vals, dtype=float)
    if len(vals) == 0:
        if domain_range is not None:
            return np.asarray(domain_range, dtype=float)
        return np.array([0.0, 1.0], dtype=float)
    if len(vals) == 1:
        if domain_range is not None:
            return np.asarray(domain_range, dtype=float)
        return np.array([vals[0] - 0.5, vals[0] + 0.5], dtype=float)

    d = np.diff(vals)
    edges = np.empty(len(vals) + 1, dtype=float)
    edges[0] = vals[0] - d[0] / 2
    edges[-1] = vals[-1] + d[-1] / 2
    edges[1:-1] = (vals[:-1] + vals[1:]) / 2
    if domain_range is not None:
        edges[0], edges[-1] = (float(value) for value in domain_range)
    return edges


def _recover_bulk_field_from_neighbor_slices(
    topo_json_path: Path,
    topo: dict,
    topo_axis_names: List[str],
):
    """Reconstruct bulk_field from sibling slice CSVs when absent."""
    axis_names = list(topo_axis_names or ["E_V", "pH", "a_w"])
    if len(axis_names) != 3:
        return None

    topo_dir = topo_json_path.parent
    stem = topo_json_path.stem
    meta = topo.get("metadata", {})
    elem = str(meta.get("element", "")).strip()

    candidates = []
    if stem.startswith("topology_3d_"):
        suffix = stem[len("topology_3d_"):]
        candidates.extend(sorted(topo_dir.glob(f"pourbaix_slice_{suffix}_aw*.csv")))
    if not candidates and elem:
        candidates.extend(sorted(topo_dir.glob(f"pourbaix_slice_*_{elem}_aw*.csv")))
    if not candidates:
        return None

    rows = []
    for csv_path in candidates:
        try:
            with open(long_path(csv_path), "r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if not row:
                        continue
                    try:
                        rows.append({
                            "E_V": float(row["E_V"]),
                            "pH": float(row["pH"]),
                            "a_w": float(row["a_w"]),
                            "label_id": int(row["label_id"]),
                        })
                    except (KeyError, TypeError, ValueError):
                        continue
        except OSError:
            continue

    if not rows:
        return None

    axis_values = {
        "E_V": sorted({r["E_V"] for r in rows}),
        "pH": sorted({r["pH"] for r in rows}),
        "a_w": sorted({r["a_w"] for r in rows}),
    }
    if not all(axis_values.get(name) for name in axis_names):
        return None

    index_maps = {
        name: {float(v): i for i, v in enumerate(axis_values[name])}
        for name in axis_names
    }
    shape = tuple(len(axis_values[name]) for name in axis_names)
    labels = np.full(shape, fill_value=-2, dtype=int)

    for row in rows:
        try:
            idx = tuple(index_maps[name][float(row[name])] for name in axis_names)
        except KeyError:
            continue
        labels[idx] = int(row["label_id"])

    return {
        "axis_names": axis_names,
        "axis_values": axis_values,
        "labels": labels.tolist(),
    }


def _axis_index_map(topo_axis_names, display_ax_names):
    """Return column reorder indices for compact vertices → display axes.

    Compact vertices are stored in the compactor's axis order (from
    metadata.axis_names, e.g. ["E_V", "pH", "a_w"]).  The plotter's
    *display_ax_names* may differ (e.g. ("pH", "a_w", "E_V")).

    Returns an integer list ``[i, j, k]`` such that
    ``verts[:, [i,j,k]]`` maps columns to display order.
    Returns None if no reordering is needed or info is unavailable.
    """
    if not topo_axis_names or not display_ax_names:
        return None
    if len(topo_axis_names) != len(display_ax_names):
        return None
    try:
        return [topo_axis_names.index(n) for n in display_ax_names]
    except ValueError:
        return None


# ── JSON readers (generalized + legacy) ──────────────────────────

def _read_boundaries(topo: dict, ndim: int) -> List[dict]:
    """Read codim-1 boundary features from JSON.

    Generalized format: ``features_{ndim-1}d``  (e.g. ``features_2d`` for 3D).
    Legacy format: ``edges``.

    Normalises each entry to have ``id``, ``labels`` (sorted pair),
    ``btype``, ``point_cloud`` (list of coord dicts), ``junction_ids``.
    """
    key = f"features_{ndim - 1}d"
    raw = topo.get(key, [])
    if not raw:
        raw = topo.get("edges", [])
        if not raw:
            return []
        # Legacy edge format → normalise
        out = []
        for e in raw:
            norm = {
                "id": e["id"],
                "labels": sorted([e.get("left_label", -1),
                                   e.get("right_label", -1)]),
                "btype": e.get("type", "solid_solid"),
                "junction_ids": e.get("junction_ids", []),
            }
            if "point_cloud" in e:
                norm["point_cloud"] = e["point_cloud"]
            elif "polyline_raw" in e:
                # polyline_raw is [[x, y, ...], ...] — keep as list-of-lists
                norm["point_cloud"] = e["polyline_raw"] or []
            else:
                norm["point_cloud"] = []
            out.append(norm)
        return out

    # Generalized format
    out = []
    for feat in raw:
        norm = {
            "id": feat["id"],
            "labels": sorted(feat.get("labels", [])),
            "btype": feat.get("btype", "solid_solid"),
            "junction_ids": feat.get("junction_ids", []),
        }
        # Prefer compact geometry (pre-computed vertices + triangles)
        gc = feat.get("geometry_compact")
        if isinstance(gc, dict) and "vertices" in gc and "triangles" in gc:
            norm["compact_vertices"] = gc["vertices"]
            norm["compact_triangles"] = gc["triangles"]
            norm["point_cloud"] = []  # not needed when compact is present
        else:
            geom = feat.get("geometry", {})
            if isinstance(geom, dict):
                norm["point_cloud"] = geom.get("point_cloud", [])
                if not norm["point_cloud"] and "polyline" in geom:
                    norm["point_cloud"] = geom["polyline"]
            elif isinstance(geom, list):
                norm["point_cloud"] = geom
            else:
                norm["point_cloud"] = []
        out.append(norm)
    return out


def _read_triple_lines(topo: dict, ndim: int) -> List[dict]:
    """Read codim-2 triple-line features from JSON.

    Generalized format: ``features_{ndim-2}d``  (e.g. ``features_1d`` for 3D).
    Returns list of dicts with ``id``, ``labels``, ``coords``,
    ``geometry`` (point cloud / polyline).
    """
    if ndim < 3:
        return []
    key = f"features_{ndim - 2}d"
    raw = topo.get(key, [])
    out = []
    for feat in raw:
        norm = {
            "id": feat.get("id"),
            "labels": feat.get("labels", []),
            "coords": feat.get("coords", {}),
            "is_domain_edge": feat.get("is_domain_edge", False),
        }
        # Prefer compact polyline if available
        gc = feat.get("geometry_compact")
        if isinstance(gc, dict) and "polyline" in gc:
            norm["compact_polyline"] = gc["polyline"]
            norm["point_cloud"] = []
        else:
            geom = feat.get("geometry")
            if isinstance(geom, dict):
                norm["point_cloud"] = geom.get("point_cloud", [])
                if not norm["point_cloud"] and "polyline" in geom:
                    norm["point_cloud"] = geom["polyline"]
            elif isinstance(geom, list):
                norm["point_cloud"] = geom
            else:
                norm["point_cloud"] = []
        out.append(norm)
    return out


def _read_quad_points(topo: dict, ndim: int) -> List[dict]:
    """Read codim-N junction points from JSON.

    Generalized format: ``features_0d``.
    Legacy format: ``nodes``.
    """
    raw = topo.get("features_0d", [])
    if raw:
        return raw
    return topo.get("nodes", [])


def _draw_bulk_cells(
    ax, bulk_field, label_color, ax_names, alpha=0.10,
    axis_ranges=None,
):
    """Render transparent bulk colour directly from cell labels."""
    if not isinstance(bulk_field, dict):
        return

    axis_names = list(bulk_field.get("axis_names", []))
    axis_values = bulk_field.get("axis_values", {})
    labels = np.asarray(bulk_field.get("labels", []))
    if labels.ndim != 3 or len(axis_names) != 3:
        return
    if not all(name in axis_values for name in axis_names):
        return
    try:
        display_order = [axis_names.index(name) for name in ax_names]
    except ValueError:
        return

    labels_disp = np.transpose(labels, axes=display_order)
    filled = labels_disp >= 0
    if not np.any(filled):
        return

    x_vals = np.asarray(axis_values[ax_names[0]], dtype=float)
    y_vals = np.asarray(axis_values[ax_names[1]], dtype=float)
    z_vals = np.asarray(axis_values[ax_names[2]], dtype=float)
    axis_ranges = axis_ranges or bulk_field.get("axis_ranges", {})
    x_edges = _cell_edges(x_vals, axis_ranges.get(ax_names[0]))
    y_edges = _cell_edges(y_vals, axis_ranges.get(ax_names[1]))
    z_edges = _cell_edges(z_vals, axis_ranges.get(ax_names[2]))
    X, Y, Z = np.meshgrid(x_edges, y_edges, z_edges, indexing="ij")

    colors = np.zeros(labels_disp.shape + (4,), dtype=float)
    for lbl in sorted(set(labels_disp.ravel()) - {-2, -1}):
        rgba = list(to_rgba(label_color.get(int(lbl), "#888888")))
        rgba[3] = alpha
        colors[labels_disp == lbl] = rgba

    ax.voxels(
        X, Y, Z, filled,
        facecolors=colors,
        edgecolor=(0.0, 0.0, 0.0, 0.0),
        linewidth=0.0,
        shade=False,
    )


def _draw_exact_boundary_faces(
    ax, bulk_field, label_color, ax_names, alpha=0.45,
    axis_ranges=None,
):
    """Render exact N-1 boundary quads from the refined label field."""
    if not isinstance(bulk_field, dict):
        return False

    axis_names = list(bulk_field.get("axis_names", []))
    axis_values = bulk_field.get("axis_values", {})
    labels = np.asarray(bulk_field.get("labels", []))
    if labels.ndim != 3 or len(axis_names) != 3:
        return False
    if not all(name in axis_values for name in axis_names):
        return False

    try:
        display_order = [axis_names.index(name) for name in ax_names]
    except ValueError:
        return False

    axis_ranges = axis_ranges or bulk_field.get("axis_ranges", {})
    edge_values = {
        name: _cell_edges(
            np.asarray(axis_values[name], dtype=float),
            axis_ranges.get(name),
        )
        for name in axis_names
    }
    grouped_quads = defaultdict(list)

    for fixed_axis in range(3):
        a0, a1 = [i for i in range(3) if i != fixed_axis]
        for face_idx in range(labels.shape[fixed_axis] - 1):
            for i0 in range(labels.shape[a0]):
                for i1 in range(labels.shape[a1]):
                    idx_l = [0, 0, 0]
                    idx_r = [0, 0, 0]
                    idx_l[fixed_axis] = face_idx
                    idx_r[fixed_axis] = face_idx + 1
                    idx_l[a0] = idx_r[a0] = i0
                    idx_l[a1] = idx_r[a1] = i1

                    lbl_l = int(labels[tuple(idx_l)])
                    lbl_r = int(labels[tuple(idx_r)])
                    if lbl_l < 0 or lbl_r < 0 or lbl_l == lbl_r:
                        continue

                    fixed_val = edge_values[axis_names[fixed_axis]][face_idx + 1]
                    lo0 = edge_values[axis_names[a0]][i0]
                    hi0 = edge_values[axis_names[a0]][i0 + 1]
                    lo1 = edge_values[axis_names[a1]][i1]
                    hi1 = edge_values[axis_names[a1]][i1 + 1]

                    quad = np.array([
                        _face_vertex(fixed_axis, fixed_val, a0, lo0, a1, lo1),
                        _face_vertex(fixed_axis, fixed_val, a0, hi0, a1, lo1),
                        _face_vertex(fixed_axis, fixed_val, a0, hi0, a1, hi1),
                        _face_vertex(fixed_axis, fixed_val, a0, lo0, a1, hi1),
                    ], dtype=float)
                    quad = quad[:, display_order]
                    grouped_quads[tuple(sorted((lbl_l, lbl_r)))].append(quad)

    if not grouped_quads:
        return False

    for (lbl_a, lbl_b), quads in grouped_quads.items():
        color_a = np.array(to_rgba(label_color.get(lbl_a, "#888888")))
        color_b = np.array(to_rgba(label_color.get(lbl_b, "#888888")))
        face_color = (color_a + color_b) / 2.0
        face_color[3] = alpha
        poly = Poly3DCollection(
            quads,
            facecolor=tuple(face_color),
            edgecolor=(0.0, 0.0, 0.0, 0.0),
            linewidths=0.0,
            alpha=alpha,
        )
        ax.add_collection3d(poly)

    return True


def _face_vertex(fixed_axis, fixed_val, axis_a, val_a, axis_b, val_b):
    coords = [0.0, 0.0, 0.0]
    coords[fixed_axis] = fixed_val
    coords[axis_a] = val_a
    coords[axis_b] = val_b
    return coords


def _draw_region_hulls(ax, regions, boundaries, label_catalog, label_color,
                       ax_names, alpha, topo_axis_names=None):
    """Render each region as a transparent convex-hull polyhedron."""
    from scipy.spatial import ConvexHull

    ax_map = _axis_index_map(topo_axis_names, list(ax_names))

    # Build boundary id → boundary data
    bnd_by_id = {b["id"]: b for b in boundaries}

    for region in regions:
        lbl = region.get("label")
        # Generalized format uses boundary_ids; legacy uses edges
        bnd_ids = region.get("boundary_ids", region.get("edges", []))
        if not bnd_ids:
            continue

        # Collect all boundary points for this region
        pts = []
        for bid in bnd_ids:
            b = bnd_by_id.get(bid)
            if b is None:
                continue
            # Prefer compact vertices
            cv = b.get("compact_vertices")
            if cv is not None:
                arr = np.asarray(cv, dtype=float)
                if ax_map is not None:
                    arr = arr[:, ax_map]
                pts.extend(arr.tolist())
            else:
                for p in b.get("point_cloud", []):
                    if isinstance(p, dict):
                        pts.append(list(_pt3(p, ax_names)))
                    elif isinstance(p, (list, tuple)):
                        pts.append(list(p[:3]))

        pts = np.array(pts)
        if len(pts) < 4:
            continue

        # Remove duplicate points
        pts = np.unique(pts, axis=0)
        if len(pts) < 4:
            continue

        try:
            hull = ConvexHull(pts)
        except Exception:
            continue

        color = to_rgba(label_color.get(lbl, "#888888"), alpha=alpha)
        triangles = []
        for simplex in hull.simplices:
            triangles.append([pts[i] for i in simplex])

        poly = Poly3DCollection(triangles, alpha=alpha,
                                facecolor=color, edgecolor="none")
        ax.add_collection3d(poly)


def _draw_boundary_surfaces(ax, boundaries, label_catalog, label_color,
                            ax_names, alpha, topo_axis_names=None,
                            show_mesh_edges=False):
    """Render boundary surfaces coloured by type, grouped by region pair.

    Uses pre-computed compact mesh (vertices + triangles) when available
    from the topology compactor.  Falls back to PCA + Delaunay on the
    raw point cloud when no compact geometry is present.

    Each boundary is rendered individually to avoid false connections
    between disconnected components of the same label pair.

    Works with normalised boundary dicts (``labels``, ``btype``,
    ``point_cloud``, and optionally ``compact_vertices``/``compact_triangles``).
    """
    from scipy.spatial import Delaunay

    for b in boundaries:
        lbls = b.get("labels", [])
        if len(lbls) >= 2:
            lbl_a, lbl_b = min(lbls[0], lbls[1]), max(lbls[0], lbls[1])
        elif lbls:
            lbl_a = lbl_b = lbls[0]
        else:
            lbl_a = lbl_b = 0

        btype = b.get("btype", "solid_solid")
        style = _BOUNDARY_TYPE_STYLE.get(btype,
                                         _BOUNDARY_TYPE_STYLE["solid_solid"])

        # Blend the two region colours for the boundary surface
        c_a = np.array(to_rgba(label_color.get(lbl_a, "#888")))
        c_b = np.array(to_rgba(label_color.get(lbl_b, "#888")))
        face_color = (c_a + c_b) / 2
        face_color[3] = alpha
        if show_mesh_edges:
            edge_color = to_rgba(style["color"], alpha=min(alpha + 0.2, 1.0))
            line_width = style["lw"]
        else:
            edge_color = (0.0, 0.0, 0.0, 0.0)
            line_width = 0.0

        # ── Prefer compact mesh if available ────────────────────
        compact_verts = b.get("compact_vertices")
        compact_tris = b.get("compact_triangles")
        if compact_verts is not None and compact_tris is not None:
            verts = np.asarray(compact_verts, dtype=float)
            tris = np.asarray(compact_tris, dtype=int)
            if len(verts) >= 3 and len(tris) >= 1:
                # Map vertices from topology axis order to display order
                ax_map = _axis_index_map(topo_axis_names, list(ax_names))
                if ax_map is not None:
                    verts = verts[:, ax_map]
                tris = _filter_triangle_indices(verts, tris, max_ratio=4.0)
                if len(tris) == 0:
                    continue
                triangles = [[verts[t[0]], verts[t[1]], verts[t[2]]]
                             for t in tris]
                poly = Poly3DCollection(
                    triangles, alpha=alpha,
                    facecolor=tuple(face_color),
                    edgecolor=edge_color,
                    linewidths=line_width,
                )
                ax.add_collection3d(poly)
                continue

        # ── Fallback: triangulate from raw point cloud ──────────
        all_pts = []
        for p in b.get("point_cloud", []):
            if isinstance(p, dict):
                all_pts.append(_pt3(p, ax_names))
            elif isinstance(p, (list, tuple)):
                all_pts.append(tuple(p[:3]))

        if not all_pts:
            continue
        pts = np.unique(np.array(all_pts), axis=0)
        if len(pts) < 3:
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                       c="black", s=4, alpha=0.5)
            continue

        # Project 3D points onto best-fit 2D plane via PCA
        centroid = pts.mean(axis=0)
        centered = pts - centroid
        try:
            _, _, Vt = np.linalg.svd(centered, full_matrices=False)
        except np.linalg.LinAlgError:
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                       c="black", s=4, alpha=0.5)
            continue

        proj_2d = centered @ Vt[:2].T

        try:
            tri = Delaunay(proj_2d)
        except Exception:
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                       c=style["color"], s=4, alpha=0.5)
            continue

        triangles = _filter_triangles(pts, tri.simplices, max_ratio=5.0)
        if not triangles:
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                       c=style["color"], s=4, alpha=0.5)
            continue

        poly = Poly3DCollection(
            triangles, alpha=alpha,
            facecolor=tuple(face_color),
            edgecolor=edge_color,
            linewidths=line_width,
        )
        ax.add_collection3d(poly)


def _filter_triangles(pts, simplices, max_ratio=3.0):
    """Return only triangles whose longest edge ≤ max_ratio × median edge.

    This removes spurious spanning triangles from Delaunay that bridge
    disconnected boundary patches.
    """
    # Compute all edge lengths
    all_edge_lengths = []
    for s in simplices:
        for i, j in [(0, 1), (1, 2), (0, 2)]:
            all_edge_lengths.append(np.linalg.norm(pts[s[i]] - pts[s[j]]))
    if not all_edge_lengths:
        return []
    median_len = np.median(all_edge_lengths)
    threshold = max_ratio * median_len

    filtered = []
    for s in simplices:
        d01 = np.linalg.norm(pts[s[0]] - pts[s[1]])
        d12 = np.linalg.norm(pts[s[1]] - pts[s[2]])
        d02 = np.linalg.norm(pts[s[0]] - pts[s[2]])
        if max(d01, d12, d02) <= threshold:
            filtered.append([pts[s[0]], pts[s[1]], pts[s[2]]])
    return filtered


def _filter_triangle_indices(verts, triangles, max_ratio=3.0):
    """Filter indexed triangles using the same longest-edge heuristic."""
    if len(triangles) == 0:
        return triangles

    max_edges = []
    for tri in triangles:
        pts = verts[tri]
        d01 = np.linalg.norm(pts[0] - pts[1])
        d12 = np.linalg.norm(pts[1] - pts[2])
        d02 = np.linalg.norm(pts[0] - pts[2])
        max_edges.append(max(d01, d12, d02))

    max_edges = np.asarray(max_edges, dtype=float)
    positive = max_edges[max_edges > 1e-12]
    if len(positive) == 0:
        return triangles

    threshold = float(np.median(positive)) * max_ratio
    return triangles[max_edges <= threshold]


def _draw_triple_lines(ax, triple_lines, label_catalog, label_color,
                       ax_names, topo_axis_names=None):
    """Render codim-2 triple lines as thick 3-D polylines.

    Each triple line is where 3 regions meet.  It is rendered as an
    ordered polyline through its point-cloud geometry (or as scatter
    points if ordering fails).  Colour is the blend of the three
    bordering region colours.

    Uses compact polylines when available from the compactor, falling
    back to PCA ordering of raw point clouds.
    """
    ax_map = _axis_index_map(topo_axis_names, list(ax_names))

    for tl in triple_lines:
        labels = tl.get("labels", [])

        # ── Prefer compact polyline ─────────────────────────────
        compact_pl = tl.get("compact_polyline")
        if compact_pl is not None and len(compact_pl) >= 2:
            pts = np.asarray(compact_pl, dtype=float)
            if ax_map is not None:
                pts = pts[:, ax_map]
        else:
            pts_raw = tl.get("point_cloud", [])
            if not pts_raw:
                # Fallback: single centroid marker
                c = tl.get("coords", {})
                if all(a in c for a in ax_names):
                    x, y, z = c[ax_names[0]], c[ax_names[1]], c[ax_names[2]]
                    ax.scatter([x], [y], [z], c=["red"], s=60, marker="o",
                               edgecolors="black", linewidths=0.8, zorder=9)
                continue

            # Convert to numpy array
            tmp = []
            for p in pts_raw:
                if isinstance(p, dict):
                    tmp.append(_pt3(p, ax_names))
                elif isinstance(p, (list, tuple)):
                    tmp.append(tuple(p[:3]))
            pts = np.array(tmp)
            if len(pts) < 2:
                ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                           c=["red"], s=40, marker="o", zorder=9)
                continue

            # Remove duplicates and order along principal axis
            pts = np.unique(pts, axis=0)
            pts = _order_point_cloud_1d(pts)

        # Colour: blend of bordering region colours
        colors = [np.array(to_rgba(label_color.get(lbl, "#888")))
                  for lbl in labels]
        if colors:
            avg_c = np.mean(colors, axis=0)
            avg_c[3] = 1.0
        else:
            avg_c = [1.0, 0.0, 0.0, 1.0]

        # Draw as a 3D line
        ax.plot(pts[:, 0], pts[:, 1], pts[:, 2],
                color=avg_c, linewidth=2.5, alpha=0.9, zorder=8)
        # Emphasise endpoints
        ax.scatter(pts[[0, -1], 0], pts[[0, -1], 1],
                   pts[[0, -1], 2], c=[avg_c, avg_c], s=30,
                   marker="o", edgecolors="black", linewidths=0.6,
                   zorder=9, depthshade=True)


def _order_point_cloud_1d(pts: np.ndarray) -> np.ndarray:
    """Order a point cloud along its principal axis (nearest-neighbour).

    Returns the reordered array.
    """
    if len(pts) <= 2:
        return pts
    # Project onto the first principal component
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    try:
        _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return pts
    proj = centered @ Vt[0]
    order = np.argsort(proj)
    return pts[order]


def _draw_junction_nodes(ax, nodes, label_catalog, label_color, ax_names):
    """Render junction points as markers sized by number of bordering regions."""
    for n in nodes:
        coords = (
            n.get("coords")
            or n.get("geometry_compact")
            or n.get("geometry_raw")
            or {}
        )
        x = coords.get(ax_names[0], 0)
        y = coords.get(ax_names[1], 0)
        z = coords.get(ax_names[2], 0)
        n_labels = len(n.get("labels", []))
        size = 30 + 20 * n_labels

        # Colour: blend of all bordering region colours
        colors = [np.array(to_rgba(label_color.get(lbl, "#888")))
                  for lbl in n.get("labels", [])]
        if colors:
            avg = np.mean(colors, axis=0)
            avg[3] = 1.0  # fully opaque
        else:
            avg = [0, 0, 0, 1]

        ax.scatter([x], [y], [z], c=[avg], s=size, marker="D",
                   edgecolors="black", linewidths=0.8, zorder=10,
                   depthshade=True)


def _add_region_legend(ax, regions, label_catalog, label_color):
    """Add a legend mapping colours to region names."""
    handles = []
    for region in sorted(regions, key=lambda r: r.get("label", 0)):
        lbl = region.get("label")
        name = label_catalog.get(str(lbl), region.get("name", str(lbl)))
        color = label_color.get(lbl, "#888888")
        handles.append(plt.Rectangle((0, 0), 1, 1, fc=color, alpha=0.6,
                                     label=name))
    if handles:
        ax.legend(handles=handles, loc="upper left",
                  bbox_to_anchor=(1.02, 1.0), fontsize=7, framealpha=0.9)


# ── CLI for quick testing ────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python plotter_3d_topology.py <topology.json> [output.png]")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".png")
    result = plot_3d_topology(src, dst)
    print(f"Saved -> {result}")
