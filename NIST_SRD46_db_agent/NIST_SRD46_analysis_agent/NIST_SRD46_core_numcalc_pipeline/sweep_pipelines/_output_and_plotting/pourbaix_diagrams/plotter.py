"""
plotter.py
==========
Pourbaix diagram visualization using matplotlib.

Supports two rendering modes:
1. Label-map mode (grid.labels) — coloured regions from the coarse grid.
2. Topology mode (TopologyMap) — smooth boundary curves (when available).
"""

from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from typing import Any, Dict, List, Optional, Sequence, Tuple

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solver_settings import (
    OUTPUT_DPI, OUTPUT_FORMAT, DEBUG,
    PH_RANGE, E_RANGE_V, NERNST_FACTOR, Kw_LOG,
)
from solver_core_api import SolverGridResult
_SP = str(pathlib.Path(__file__).resolve().parents[2])
if _SP not in sys.path:
    sys.path.insert(0, _SP)
from sweep_pipelines._path_utils import long_path


# A palette of distinguishable colours for up to 20 regions
_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#86bcb6", "#8cd17d", "#b6992d", "#499894", "#f1ce63",
    "#d37295", "#a0cbe8", "#ffbe7d", "#d4a6c8", "#fabfd2",
]


def _card_solid_names(built_system) -> set:
    """Display names of SOLID / dissolution phases, sourced strictly from
    the free-energy card.

    Phase identity is taken from ``BuiltSystem.diss_labels`` (the card's
    §5.2 "Dissolution / Solid Species") plus the bare-metal reference
    states in ``element_names``.  It is never inferred from a species-name
    suffix such as ``(s)`` or from the source database.
    """
    names = set(getattr(built_system, "diss_labels", None) or [])
    names |= set(getattr(built_system, "element_names", None) or [])
    return names


def _is_solid_label(lbl, catalog, spec_id_to_name, solid_names) -> bool:
    """True when the region owned by *lbl* is a solid, decided from the card.

    The label's display name is resolved exactly as the legend / region
    labels resolve it, then tested for membership in the card-derived
    solid-name set.
    """
    raw = catalog.get(lbl, str(lbl))
    display = spec_id_to_name.get(raw, raw) if spec_id_to_name else raw
    return display in solid_names or raw in solid_names


def _name_is_solid(name: str, solid_names) -> bool:
    """Solid test for a region display *name*.

    Uses the card-derived ``solid_names`` set when supplied; only falls
    back to the legacy ``(s)`` marker when no card set is available (for
    stand-alone helper calls).
    """
    if solid_names is not None:
        return name in solid_names
    return "(s)" in name


def _automatic_title(
    built_system,
    principal_element: Optional[str],
    effective_component_totals: Optional[
        Sequence[Optional[float]]
    ] = None,
) -> str:
    """Build a title from the totals actually enforced by the solver.

    Component order is ``element_names`` followed by ``ligand_names``, the
    same order used by ``BuiltSystem.C_total``.  A ``None`` entry means that
    the total depends on a plotted axis and therefore must not be presented
    as one fixed concentration.  When no explicit vector is supplied, the
    legacy pre-constraint ``BuiltSystem`` metadata remains the fallback.
    """
    component_names = (
        list(built_system.element_names)
        + list(built_system.ligand_names)
    )
    if effective_component_totals is None:
        component_totals = (
            list(built_system.element_totals)
            + list(built_system.ligand_totals)
        )
    else:
        component_totals = list(effective_component_totals)
        if len(component_totals) != len(component_names):
            raise ValueError(
                "effective_component_totals must contain one value for "
                "each element and ligand"
            )

    concentration_parts = []
    for name, value in zip(component_names, component_totals):
        if value is None:
            concentration_parts.append(f"[{name}]=varies")
        else:
            concentration_parts.append(f"[{name}]={float(value):.1e}M")

    element_tag = principal_element or "combined"
    return (
        f"Pourbaix diagram: {built_system.system_name} ({element_tag})\n"
        f"{', '.join(concentration_parts)}, "
        f"T={built_system.temperature_C}C"
    )


def _parameter_lines(
    built_system,
    principal_element: Optional[str],
    effective_component_totals: Optional[Sequence[Optional[float]]] = None,
) -> List[str]:
    """One aligned line per enforced component total, plus temperature."""
    component_names = (
        list(built_system.element_names) + list(built_system.ligand_names)
    )
    if effective_component_totals is None:
        component_totals = (
            list(built_system.element_totals)
            + list(built_system.ligand_totals)
        )
    else:
        component_totals = list(effective_component_totals)
        if len(component_totals) != len(component_names):
            raise ValueError(
                "effective_component_totals must contain one value for "
                "each element and ligand"
            )
    width = max((len(name) for name in component_names), default=0)
    lines = []
    for name, value in zip(component_names, component_totals):
        shown = "varies" if value is None else f"{float(value):.1e} M"
        lines.append(f"[{name:<{width}}] = {shown}")
    lines.append(f"T = {built_system.temperature_C} \u00b0C")
    return lines


def plot_pourbaix(
    grid: SolverGridResult,
    built_system,
    output_path: str,
    *,
    csv_path: Optional[str] = None,
    show_water_lines: bool = True,
    principal_element: Optional[str] = None,
    title: Optional[str] = None,
    boundary_cells=None,
    topology_map: Optional[Any] = None,
    boundary_segments: Optional[List[Any]] = None,
    triple_points: Optional[List[Any]] = None,
    effective_component_totals: Optional[
        Sequence[Optional[float]]
    ] = None,
    show_compact_controls: bool = False,
    publication: bool = False,
    region_label_source: Optional[np.ndarray] = None,
    side_panel: bool = True,
    font_scale: float = 1.0,
    debug: bool = DEBUG,
) -> str:
    """
    Render and save a Pourbaix diagram.

    Parameters
    ----------
    grid              : labelled SolverGridResult (used as fallback)
    built_system      : BuiltSystem (for metadata)
    output_path       : where to save the image
    csv_path          : path to Pourbaix map CSV — when provided the
                        colour-fill uses the fine label grid from the CSV
                        instead of the coarse grid stored in *grid*.
    show_water_lines  : overlay O2/H2 stability lines
    principal_element : element for per-element mode (None → combined)
    title             : custom title (auto-generated if None)
    boundary_cells    : list of BoundaryCell for coarse overlay (fallback)
    topology_map      : TopologyMap with edges and nodes (smooth rendering)
    boundary_segments : list of BoundarySegment polylines (smooth rendering)
    triple_points     : list of TriplePoint nodes (topology overlay)
    effective_component_totals : solver-effective element then ligand totals;
                        ``None`` entries denote totals that vary over the sweep
    show_compact_controls : overlay the primary fixed-budget polygon as black
                            straight chords between selected raw vertices,
                            with interior selections marked by red stars;
                            exact raw geometry remains underneath
    side_panel        : publication mode only; False drops the right-hand
                        parameter panel and marker legend and lets the plot
                        fill the canvas
    font_scale        : multiplier applied to every text size
    debug             : print debug info

    Returns
    -------
    Path to saved image file.
    """
    # ---- Choose label source: CSV (fine grid) or in-memory grid ----
    if csv_path is not None:
        from sweep_pipelines._output_and_plotting.pourbaix_diagrams.csv_exporter import load_pourbaix_csv
        pH_vals, E_vals, labels, catalog = load_pourbaix_csv(csv_path)
        if debug:
            print(f"[plotter] Using CSV label map {labels.shape} "
                  f"from {csv_path}")
    elif principal_element and grid.labels_per_element:
        labels = grid.labels_per_element[principal_element]
        catalog = grid.label_catalog_per_element[principal_element]
        pH_vals = grid.pH_values
        E_vals = grid.E_values
    else:
        labels = grid.labels
        catalog = grid.label_catalog
        pH_vals = grid.pH_values
        E_vals = grid.E_values

    if labels is None:
        raise ValueError("Grid not labelled — call label_grid() first")

    # CSV refinement maps may retain numerical support centres near an axis
    # endpoint.  The coarse sweep axes are the authoritative user-declared
    # diagram domain, so rendering (including water lines) is clipped to
    # those bounds rather than inferred from the first/last raster centre.
    pH_bounds = _declared_axis_bounds(grid, "pH", pH_vals)
    E_bounds = _declared_axis_bounds(grid, "E_V", E_vals)

    n_E, n_pH = labels.shape

    # Unique labels (exclude -2 = unconverged)
    unique_labels = sorted(set(labels.ravel()) - {-2})
    n_labels = len(unique_labels)

    # Build colour map: label_int → colour
    label_to_colour = {}
    for i, lbl in enumerate(unique_labels):
        label_to_colour[lbl] = _PALETTE[i % len(_PALETTE)]

    # Build discrete colormap
    cmap_colors = [label_to_colour[lbl] for lbl in unique_labels]
    cmap = mcolors.ListedColormap(cmap_colors)

    # Map labels to sequential indices for plotting
    label_remap = {lbl: i for i, lbl in enumerate(unique_labels)}
    plot_data = np.full_like(labels, dtype=float, fill_value=np.nan)
    for lbl, idx in label_remap.items():
        plot_data[labels == lbl] = idx

    # Solid-phase identification — sourced STRICTLY from the free-energy
    # card (BuiltSystem.diss_labels / element_names), never from species
    # name suffixes or the source database.
    solid_names = _card_solid_names(built_system)
    spec_id_to_name = built_system.spec_id_to_name or {}
    solid_labels = [
        lbl for lbl in unique_labels
        if _is_solid_label(lbl, catalog, spec_id_to_name, solid_names)
    ]

    # Create figure.  Publication styling enlarges every text element,
    # greys the raw pixel-boundary zigzag (compact chords stay black), and
    # swaps the per-phase legend for an inline parameter panel.
    pub = bool(publication)
    fig_size = (12.0, 8.5) if pub else (10, 7)
    fs_title = round((17 if pub else 11) * font_scale)
    fs_axis = round((18 if pub else 12) * font_scale)
    fs_tick = round((15 if pub else 10) * font_scale)
    fs_region = round((12 if pub else 6) * font_scale)
    if pub and not side_panel:
        fig_size = (9.0, 8.5)
    raw_line_color = "#8c8c8c" if pub else "k"
    raw_line_alpha = 0.9 if pub else 0.5
    raw_line_lw = 0.8 if pub else 0.4
    fig, ax = plt.subplots(1, 1, figsize=fig_size)
    if pub:
        # Pin the data area to a fixed rectangle so sibling figures share an
        # identical plot area regardless of parameter-panel / legend length.
        ax.set_position((0.08, 0.10, 0.60, 0.81) if side_panel
                        else (0.15, 0.17, 0.81, 0.76))

    # pcolormesh for colour fill
    pH_edges = _cell_edges(pH_vals)
    E_edges = _cell_edges(E_vals)
    mesh = ax.pcolormesh(
        pH_edges, E_edges, plot_data,
        cmap=cmap, vmin=-0.5, vmax=n_labels - 0.5,
        shading="flat",
    )

    # Overlay diagonal hatching on exactly the same categorical cells used by
    # the colour mesh.  ``contourf`` must not be used here: it interpolates a
    # binary mask between sample centres, so its diagonal contour can hatch
    # neighbouring aqueous cells and leave parts of solid cells unhatched.
    # Solid identity comes from the card.
    if solid_labels and len(pH_vals) > 1 and len(E_vals) > 1:
        solid_mask = np.isin(labels, solid_labels)
        if solid_mask.any():
            _draw_solid_cell_hatching(
                ax, solid_mask, pH_edges, E_edges,
            )

    # Boundary overlay: always draw label-based boundaries as fallback,
    # then overlay smooth topology curves on top
    has_compact_nd = (topology_map is not None
                      and hasattr(topology_map, "features")
                      and isinstance(getattr(topology_map, "features", None), dict))
    has_legacy_topo = (topology_map is not None and hasattr(topology_map, "edges")
                       and topology_map.edges)
    has_nd_topo = (topology_map is not None and hasattr(topology_map, "boundaries")
                   and topology_map.boundaries)
    has_segments = (boundary_segments is not None and boundary_segments)

    # Base layer: thin label-based boundaries (always drawn for completeness)
    _draw_boundaries_from_labels(ax, labels, pH_vals, E_vals,
                                 linewidth=raw_line_lw, alpha=raw_line_alpha,
                                 color=raw_line_color)

    # Overlay smooth curves if available (solid/aqueous line style decided
    # from the card-derived solid set, not species-name suffixes)
    if has_compact_nd:
        _draw_compact_features(
            ax, topology_map, solid_names=solid_names,
            show_compact_controls=show_compact_controls,
            raw_color=raw_line_color, publication=pub,
        )
    elif has_legacy_topo:
        _draw_topology_edges(ax, topology_map, solid_names=solid_names)
    elif has_nd_topo:
        _draw_topology_nd_boundaries(ax, topology_map, solid_names=solid_names)
    elif has_segments:
        _draw_refined_segments(ax, has_segments)

    # Triple point markers
    tp_list = None
    if has_compact_nd:
        tp_list = topology_map.features.get(0, [])
    elif has_legacy_topo:
        tp_list = topology_map.nodes
    elif has_nd_topo:
        tp_list = topology_map.junctions
    elif triple_points:
        tp_list = triple_points
    if tp_list:
        _draw_triple_points(ax, tp_list, publication=pub)

    # Water stability lines
    if show_water_lines:
        pH_line = np.linspace(pH_bounds[0], pH_bounds[1], 200)
        # O2/H2O line: E = 1.229 - 0.05916 * pH
        E_O2 = 1.229 - NERNST_FACTOR * pH_line
        # H2/H2O line: E = 0 - 0.05916 * pH
        E_H2 = -NERNST_FACTOR * pH_line
        water_lw = 1.6 if pub else 1.2
        ax.plot(pH_line, E_O2, "b--", linewidth=water_lw, alpha=0.7,
                label="O$_2$/H$_2$O")
        ax.plot(pH_line, E_H2, "b--", linewidth=water_lw, alpha=0.7,
                label="H$_2$/H$_2$O")
        if pub:
            # No legend in publication mode: label the water lines inline.
            x_ann = pH_bounds[0] + 0.78 * (pH_bounds[1] - pH_bounds[0])
            # The line slopes down across the text width; anchor the H2 tag
            # a little lower so the dashes never cross it.
            drop = 0.02 * (E_bounds[1] - E_bounds[0])
            for e_val, tag, va in (
                (1.229 - NERNST_FACTOR * x_ann, "O$_2$/H$_2$O", "bottom"),
                (-NERNST_FACTOR * x_ann - drop, "H$_2$/H$_2$O", "top"),
            ):
                ax.text(x_ann, e_val, tag, color="b", fontsize=fs_tick,
                        ha="center", va=va, fontstyle="italic",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white",
                                  ec="none", alpha=0.7))

    # Region labels.  A supplied effective (post-fixer) raster annotates the
    # FIXED regions, so orphan fragments the fixer dissolved do not receive a
    # phantom duplicate label.  Publication mode places names at each
    # region's pole of inaccessibility and falls back to a numbered side key
    # for regions too small for their name.
    region_key = _add_region_labels(
        ax, labels, pH_vals, E_vals, catalog, unique_labels,
        built_system.spec_id_to_name, fontsize=fs_region,
        label_source=region_label_source, publication=pub,
        water_lines=show_water_lines,
    )

    # Axis formatting
    ax.set_xlabel("pH", fontsize=fs_axis)
    ax.set_ylabel("E (V vs SHE)", fontsize=fs_axis)
    ax.tick_params(axis="both", labelsize=fs_tick)
    ax.set_xlim(*pH_bounds)
    ax.set_ylim(*E_bounds)

    element_tag = principal_element or "combined"
    if title is None:
        if pub:
            # Concise heading; enforced totals move to the parameter panel.
            title = f"{built_system.system_name} ({element_tag})"
        else:
            title = _automatic_title(
                built_system,
                principal_element,
                effective_component_totals,
            )
    ax.set_title(title, fontsize=fs_title,
                 fontweight=("bold" if pub else "normal"))

    if pub and not side_panel:
        # No side panel: numbered small regions are resolved in a one-line
        # footnote beneath the x-axis label.
        if region_key:
            fig.text(0.5, 0.012, "   ".join(k.strip() for k in region_key),
                     ha="center", va="bottom", fontsize=fs_tick)
    elif pub:
        # Replace the per-phase legend with a compact parameter panel in the
        # freed right-hand margin (region names are drawn in place; regions
        # too small for their name are numbered and resolved here).
        panel = _parameter_lines(
            built_system, principal_element, effective_component_totals,
        )
        if region_key:
            panel += ["", "Numbered regions:"] + region_key
        ax.text(
            1.015, 0.99, "\n".join(panel),
            transform=ax.transAxes, ha="left", va="top",
            fontsize=fs_tick, family="monospace", linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.5", fc="#f5f5f5",
                      ec="#999999", linewidth=0.8),
        )
        if show_compact_controls:
            marker_handles = [
                Line2D([], [], linestyle="none", marker="*",
                       markerfacecolor="#d62728", markeredgecolor="#7f1d1d",
                       markersize=14, label="RDP control point"),
                Line2D([], [], linestyle="none", marker="o",
                       markerfacecolor="black", markeredgecolor="white",
                       markersize=9, label="Triple point"),
                Line2D([], [], linestyle="none", marker="D",
                       markerfacecolor="black", markeredgecolor="white",
                       markersize=8, label="Domain limit"),
            ]
            ax.legend(handles=marker_handles, loc="lower left",
                      bbox_to_anchor=(1.015, 0.0), fontsize=fs_tick - 3,
                      frameon=True, framealpha=0.95, borderpad=0.7,
                      handletextpad=0.5)
    else:
        # Legend (solids get a hatched swatch matching the diagram)
        handles = []
        for lbl in unique_labels:
            raw_name = catalog.get(lbl, str(lbl))
            # CSV catalog already stores display names; in-memory catalog
            # stores raw species ids — try spec_id_to_name first, fall back.
            display = built_system.spec_id_to_name.get(raw_name, raw_name)
            color = label_to_colour[lbl]
            is_solid = lbl in solid_labels
            handles.append(plt.Rectangle(
                (0, 0), 1, 1, fc=color, label=display,
                hatch=("////" if is_solid else None),
                ec=("#1a1a1a" if is_solid else "none"),
                linewidth=(0.5 if is_solid else 0.0),
            ))
        ax.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            fontsize=8,
            framealpha=0.9,
        )

    if pub:
        # Fixed canvas (no tight bbox): the reserved right margin holds the
        # panel/legend, so a longer legend never crops or rescales the plot.
        fig.savefig(long_path(output_path), dpi=OUTPUT_DPI)
    else:
        fig.tight_layout()
        fig.savefig(long_path(output_path), dpi=OUTPUT_DPI, bbox_inches="tight")
    plt.close(fig)

    if debug:
        print(f"[plotter] Saved Pourbaix diagram to {output_path}")

    return str(output_path)


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

def _cell_edges(vals: np.ndarray) -> np.ndarray:
    """Convert cell centers to cell edges for pcolormesh."""
    d = np.diff(vals)
    edges = np.empty(len(vals) + 1)
    edges[0] = vals[0] - d[0] / 2
    edges[-1] = vals[-1] + d[-1] / 2
    edges[1:-1] = (vals[:-1] + vals[1:]) / 2
    return edges


def _declared_axis_bounds(grid, axis_name: str, fallback_values) -> Tuple[float, float]:
    """Return the original sweep endpoints for one plotted axis."""

    for axis in (getattr(grid, "axes", None) or []):
        if getattr(axis, "name", None) != axis_name:
            continue
        declared = getattr(axis, "range", None)
        if declared is not None:
            return float(declared[0]), float(declared[1])

    legacy_name = "pH_values" if axis_name == "pH" else "E_values"
    values = np.asarray(getattr(grid, legacy_name, []), dtype=float)
    if values.size:
        return float(values[0]), float(values[-1])

    fallback = np.asarray(fallback_values, dtype=float)
    return float(fallback[0]), float(fallback[-1])


def _draw_solid_cell_hatching(
    ax,
    solid_mask: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
):
    """Hatch the selected categorical raster cells without interpolation.

    The returned :class:`~matplotlib.collections.PolyCollection` contains one
    quadrilateral per contiguous horizontal run of ``True`` cells.  Its
    vertices use the very same x/y edges as the underlying ``pcolormesh``,
    guaranteeing that solid shading cannot bleed across a phase-label
    boundary while avoiding one artist path per raster cell.
    """
    mask = np.asarray(solid_mask, dtype=bool)
    x_edges = np.asarray(x_edges, dtype=float)
    y_edges = np.asarray(y_edges, dtype=float)
    expected_shape = (len(y_edges) - 1, len(x_edges) - 1)
    if mask.shape != expected_shape:
        raise ValueError(
            f"solid mask shape {mask.shape} does not match cell-edge "
            f"shape {expected_shape}"
        )

    quads = []
    for i_y, row in enumerate(mask):
        padded = np.concatenate(([False], row, [False])).astype(np.int8)
        changes = np.diff(padded)
        starts = np.flatnonzero(changes == 1)
        stops = np.flatnonzero(changes == -1)
        for i_x0, i_x1 in zip(starts, stops):
            x0, x1 = x_edges[i_x0], x_edges[i_x1]
            y0, y1 = y_edges[i_y], y_edges[i_y + 1]
            quads.append(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))

    with matplotlib.rc_context({"hatch.color": "#1a1a1a",
                                "hatch.linewidth": 0.7}):
        collection = PolyCollection(
            quads,
            facecolors="none",
            edgecolors="#1a1a1a",
            linewidths=0.0,
            hatch="////",
            zorder=1.5,
        )
        ax.add_collection(collection)
    return collection


def _draw_boundaries_from_labels(ax, labels, pH_vals, E_vals,
                                  linewidth=0.5, alpha=0.8, color="k"):
    """Draw boundary lines between adjacent cells with different labels."""
    n_E, n_pH = labels.shape
    dpH = pH_vals[1] - pH_vals[0] if len(pH_vals) > 1 else 0
    dE = E_vals[1] - E_vals[0] if len(E_vals) > 1 else 0

    # Collect boundary line segments
    h_segs = []  # horizontal boundaries (between rows)
    v_segs = []  # vertical boundaries (between columns)

    # Horizontal: between (i_E, i_pH) and (i_E, i_pH+1)
    for i_E in range(n_E):
        for i_pH in range(n_pH - 1):
            if labels[i_E, i_pH] != labels[i_E, i_pH + 1]:
                if labels[i_E, i_pH] >= 0 and labels[i_E, i_pH + 1] >= 0:
                    # Vertical line segment between the two cells
                    pH_mid = (pH_vals[i_pH] + pH_vals[i_pH + 1]) / 2
                    E_lo = E_vals[i_E] - dE / 2
                    E_hi = E_vals[i_E] + dE / 2
                    v_segs.append(([pH_mid, pH_mid], [E_lo, E_hi]))

    # Vertical: between (i_E, i_pH) and (i_E+1, i_pH)
    for i_E in range(n_E - 1):
        for i_pH in range(n_pH):
            if labels[i_E, i_pH] != labels[i_E + 1, i_pH]:
                if labels[i_E, i_pH] >= 0 and labels[i_E + 1, i_pH] >= 0:
                    pH_lo = pH_vals[i_pH] - dpH / 2
                    pH_hi = pH_vals[i_pH] + dpH / 2
                    E_mid = (E_vals[i_E] + E_vals[i_E + 1]) / 2
                    h_segs.append(([pH_lo, pH_hi], [E_mid, E_mid]))

    for seg in v_segs + h_segs:
        ax.plot(seg[0], seg[1], color=color, linestyle="-",
                linewidth=linewidth, alpha=alpha)


def _draw_topology_edges(ax, topo, solid_names=None, **_kwargs):
    """Draw smooth boundary curves from topology edges via cubic spline.

    Line style is determined by the phase of the neighboring faces, with
    solid identity taken from the card-derived ``solid_names`` set:
      - Solid line if EITHER face is a solid phase
      - Dashed line only when BOTH faces are aqueous

    Interior RDP envelope support points are drawn as small red "+" markers.
    Envelope points are connected by straight line segments (no spline).
    """
    catalog = topo.label_catalog or {}

    for edge in topo.edges:
        # Line style determined by neighboring face phases
        left_name = str(catalog.get(edge.left_label, ""))
        right_name = str(catalog.get(edge.right_label, ""))
        involves_solid = (_name_is_solid(left_name, solid_names)
                          or _name_is_solid(right_name, solid_names))
        style = "k-" if involves_solid else "k--"
        lw_main = 1.0 if involves_solid else 0.8
        lw_raw = 0.6 if involves_solid else 0.5
        alpha_main = 0.85 if involves_solid else 0.6

        # RDP envelope points → straight line segments + interior markers
        if edge.rdp_points and len(edge.rdp_points) >= 2:
            pts = edge.rdp_points
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    style, linewidth=lw_main, alpha=alpha_main)
            # Draw interior support points (exclude endpoints)
            interior = pts[1:-1]
            if interior:
                ax.scatter(
                    [p[0] for p in interior],
                    [p[1] for p in interior],
                    c="red", s=15, zorder=11, marker="+",
                    linewidths=0.8, alpha=0.9,
                )
        # Fallback: raw polyline
        elif edge.polyline_raw and len(edge.polyline_raw) >= 2:
            pts = edge.polyline_raw
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    style, linewidth=lw_raw, alpha=alpha_main * 0.8)


def _draw_refined_segments(ax, segments: List[Any]):
    """Draw refined boundary segment polylines."""
    for seg in segments:
        if len(seg.polyline) >= 2:
            pH = [p[0] for p in seg.polyline]
            E = [p[1] for p in seg.polyline]
            ax.plot(pH, E, "k-", linewidth=0.8, alpha=0.8)


def _pourbaix_axis_indices(axis_names: Sequence[str]) -> Tuple[int, int]:
    """Return positional pH/E indices or reject incomplete named metadata."""
    if axis_names:
        missing = [name for name in ("pH", "E_V") if name not in axis_names]
        if missing:
            raise ValueError(
                "Pourbaix topology axis metadata is missing required "
                f"coordinate(s): {', '.join(missing)}"
            )
        return axis_names.index("pH"), axis_names.index("E_V")
    # Legacy topology objects may lack axis metadata.  Their documented
    # positional order is [E_V, pH]; no numerical coordinate is invented.
    return 1, 0


def _finite_pourbaix_pair(pH: Any, E_V: Any) -> Optional[Tuple[float, float]]:
    """Return a finite coordinate pair, or ``None`` for malformed data."""
    if pH is None or E_V is None or isinstance(pH, bool) or isinstance(E_V, bool):
        return None
    try:
        pair = (float(pH), float(E_V))
    except (TypeError, ValueError):
        return None
    return pair if np.isfinite(pair).all() else None


def _topology_point_pair(
    point: Any,
    i_pH: int,
    i_E: int,
) -> Optional[Tuple[float, float]]:
    """Read one topology point without substituting missing coordinates."""
    if isinstance(point, dict):
        return _finite_pourbaix_pair(point.get("pH"), point.get("E_V"))
    if isinstance(point, (tuple, list)):
        try:
            return _finite_pourbaix_pair(point[i_pH], point[i_E])
        except IndexError:
            return None
    return None


def _topology_curve_pairs(
    geometry: Any,
    i_pH: int,
    i_E: int,
) -> Optional[List[Tuple[float, float]]]:
    """Read a complete curve, skipping it if any vertex is malformed."""
    if not isinstance(geometry, list):
        return None
    points = [_topology_point_pair(point, i_pH, i_E) for point in geometry]
    if any(point is None for point in points):
        return None
    return points


def _draw_topology_nd_boundaries(ax, topo, solid_names=None):
    """Draw boundary curves from a TopologyND object.

    Uses TopologyBoundary.geometry (polyline list) for 2-D boundaries.
    Geometry tuples follow grid axis order; axis_names in settings
    tells us which positional index is pH vs E_V.
    """
    catalog = topo.label_catalog or {}

    axis_names = topo.settings.get("axis_names", []) if topo.settings else []
    i_pH, i_E = _pourbaix_axis_indices(axis_names)

    for bnd in topo.boundaries:
        geom = bnd.geometry
        if not isinstance(geom, list) or not geom:
            continue

        pts = _topology_curve_pairs(geom, i_pH, i_E)
        if pts is None:
            continue

        if len(pts) < 2:
            continue

        left_name = str(catalog.get(bnd.left_label, ""))
        right_name = str(catalog.get(bnd.right_label, ""))
        involves_solid = (_name_is_solid(left_name, solid_names)
                          or _name_is_solid(right_name, solid_names))
        style = "k-" if involves_solid else "k--"
        lw = 1.0 if involves_solid else 0.8
        alpha = 0.85 if involves_solid else 0.6

        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                style, linewidth=lw, alpha=alpha)


def _extract_tp_coords(tp):
    """Extract (pH, E_V) from TriplePoint, TopologyJunction, or CompactFeature."""
    if hasattr(tp, "pH") and hasattr(tp, "E_V"):
        return _finite_pourbaix_pair(tp.pH, tp.E_V)
    if hasattr(tp, "coords"):
        coords = tp.coords
        if isinstance(coords, dict):
            return _finite_pourbaix_pair(coords.get("pH"), coords.get("E_V"))
        return None
    # CompactFeature (dim=0): geometry_compact is a dict
    if hasattr(tp, "geometry_compact"):
        gc = tp.geometry_compact
        if isinstance(gc, dict):
            return _finite_pourbaix_pair(gc.get("pH"), gc.get("E_V"))
    return None


def _draw_triple_points(ax, triple_points, publication=False):
    """Draw triple point markers on the diagram.

    Accepts both legacy TriplePoint (.pH, .E_V) and
    TopologyJunction (.coords dict) objects.  Interior junctions are
    circles; domain-limit contacts are diamonds.
    """
    interior = [
        point for tp in triple_points
        if not tp.is_domain_edge
        if (point := _extract_tp_coords(tp)) is not None
    ]
    edge_pts = [
        point for tp in triple_points
        if tp.is_domain_edge
        if (point := _extract_tp_coords(tp)) is not None
    ]

    if interior:
        ax.scatter([p[0] for p in interior], [p[1] for p in interior],
                   c="black", s=(70 if publication else 30),
                   zorder=10, marker="o", edgecolors="white",
                   linewidths=(1.2 if publication else 0.8),
                   label="Triple point")
    if edge_pts:
        ax.scatter([p[0] for p in edge_pts], [p[1] for p in edge_pts],
                   c="black", s=(46 if publication else 18),
                   zorder=10, marker="D", edgecolors="white",
                   linewidths=(1.0 if publication else 0.6))


def _draw_compact_features(
    ax,
    compact_topo,
    solid_names=None,
    show_compact_controls: bool = False,
    raw_color: str = "k",
    publication: bool = False,
):
    """Draw compact topology features from a CompactTopologyND.

    Render exact dim-1 feature geometry (solid/dashed by phase type).

    ``geometry_compact`` is a fixed-budget control polygon.  Its chords are
    intentionally unconstrained and can cross raster cells, so the
    authoritative boundary always follows ``geometry_raw``.  When
    ``show_compact_controls`` is true, the compact polygon is added as black
    straight chords between selected raw vertices, whose interior selections
    are marked by red stars.
    """
    catalog = compact_topo.label_catalog or {}
    axis_names = compact_topo.axis_names or []

    # Resolve pH/E axis indices.  Incomplete named metadata is an error;
    # legacy objects with no metadata retain their documented [E_V, pH]
    # positional interpretation.
    i_pH, i_E = _pourbaix_axis_indices(axis_names)

    # Draw dim-1 features (curves)
    for cf in compact_topo.features.get(1, []):
        polyline = cf.geometry_raw
        if not isinstance(polyline, list) or len(polyline) < 2:
            continue

        points = _topology_curve_pairs(polyline, i_pH, i_E)
        if points is None:
            continue
        pH_pts = [point[0] for point in points]
        E_pts = [point[1] for point in points]

        labels = cf.labels
        left_name = str(catalog.get(labels[0], "")) if labels else ""
        right_name = str(catalog.get(labels[1], "")) if len(labels) > 1 else ""
        involves_solid = (_name_is_solid(left_name, solid_names)
                          or _name_is_solid(right_name, solid_names))
        linestyle = "-" if involves_solid else "--"
        lw = 1.0 if involves_solid else 0.8
        alpha = 0.85 if involves_solid else 0.6

        ax.plot(pH_pts, E_pts, color=raw_color, linestyle=linestyle,
                linewidth=lw, alpha=alpha)

        if show_compact_controls:
            compact_indices = (
                (getattr(cf, "simplification_params", None) or {}).get(
                    "compact_indices"
                )
            )
            if compact_indices is not None:
                if (
                    not isinstance(compact_indices, list)
                    or len(compact_indices) < 2
                    or any(
                        not isinstance(index, int)
                        or index < 0
                        or index >= len(polyline)
                        for index in compact_indices
                    )
                    or compact_indices[0] != 0
                    or compact_indices[-1] != len(polyline) - 1
                    or any(
                        left >= right
                        for left, right in zip(
                            compact_indices, compact_indices[1:]
                        )
                    )
                ):
                    raise ValueError(
                        "Invalid compact raw-vertex indices in topology"
                    )
                # Build the displayed polygon directly from raw vertices.
                # Each successive pair is therefore a literal straight chord
                # between two selected vertices of the exact phase boundary.
                control = [polyline[index] for index in compact_indices]
            else:
                # Backward-compatible topology objects may predate persisted
                # indices.  Resolve every stored control point back to its
                # exact raw vertex in traversal order; never draw arbitrary
                # or interpolated compact coordinates as an RDP chord.
                stored_control = cf.geometry_compact
                if not isinstance(stored_control, list):
                    raise ValueError(
                        "Compact control geometry is not a raw-vertex list"
                    )
                resolved_indices = []
                search_start = 0
                for point in stored_control:
                    try:
                        index = polyline.index(point, search_start)
                    except ValueError as exc:
                        raise ValueError(
                            "Compact control point is not an actual raw "
                            "boundary vertex"
                        ) from exc
                    resolved_indices.append(index)
                    search_start = index + 1
                if (
                    len(resolved_indices) < 2
                    or resolved_indices[0] != 0
                    or resolved_indices[-1] != len(polyline) - 1
                ):
                    raise ValueError(
                        "Compact control polygon must retain both raw "
                        "boundary endpoints"
                    )
                control = [polyline[index] for index in resolved_indices]
            if not isinstance(control, list) or len(control) < 2:
                continue
            control_points = _topology_curve_pairs(control, i_pH, i_E)
            if control_points is None:
                continue
            control_pH = [point[0] for point in control_points]
            control_E = [point[1] for point in control_points]

            ax.plot(
                control_pH, control_E,
                color="black", linestyle="-",
                linewidth=(1.7 if publication else 1.15),
                alpha=0.95, zorder=9,
            )
            if len(control) > 2:
                ax.scatter(
                    control_pH[1:-1], control_E[1:-1],
                    c="#d62728", s=(120 if publication else 34),
                    zorder=11, marker="*",
                    edgecolors="#7f1d1d",
                    linewidths=(0.5 if publication else 0.3), alpha=0.95,
                )

    # Draw dim-2 features as wireframe (for 3-D slices)
    for cf in compact_topo.features.get(2, []):
        gc = cf.geometry_compact
        if gc is None:
            continue
        if isinstance(gc, tuple) and len(gc) == 2:
            verts, tris = gc
            if hasattr(verts, '__len__') and hasattr(tris, '__len__') and len(tris) > 0:
                for tri in tris:
                    for j in range(3):
                        a, b = tri[j], tri[(j + 1) % 3]
                        ax.plot([verts[a][i_pH], verts[b][i_pH]],
                                [verts[a][i_E], verts[b][i_E]],
                                "k-", linewidth=0.5, alpha=0.4)


def _draw_boundary_lines(ax, boundary_cells, pH_vals, E_vals, labels):
    """Draw boundary lines from detected BoundaryCell objects."""
    dpH = pH_vals[1] - pH_vals[0] if len(pH_vals) > 1 else 0
    dE = E_vals[1] - E_vals[0] if len(E_vals) > 1 else 0

    for bc in boundary_cells:
        if bc.direction == "horizontal":
            pH_mid = (pH_vals[bc.i_pH] + pH_vals[bc.i_pH + 1]) / 2
            E_lo = E_vals[bc.i_E] - dE / 2
            E_hi = E_vals[bc.i_E] + dE / 2
            ax.plot([pH_mid, pH_mid], [E_lo, E_hi], "k-", linewidth=0.5, alpha=0.8)
        elif bc.direction == "vertical":
            pH_lo = pH_vals[bc.i_pH] - dpH / 2
            pH_hi = pH_vals[bc.i_pH] + dpH / 2
            E_mid = (E_vals[bc.i_E] + E_vals[bc.i_E + 1]) / 2
            ax.plot([pH_lo, pH_hi], [E_mid, E_mid], "k-", linewidth=0.5, alpha=0.8)


def _add_region_labels(ax, labels, pH_vals, E_vals, catalog, unique_labels,
                       spec_id_to_name, fontsize=6, label_source=None,
                       publication=False, water_lines=False):
    """Place text labels on regions; return the numbered-region key.

    Every connected region gets its own label: a species split into
    several disconnected regions is annotated once per region (same
    text, same style).  When ``label_source`` is given (the effective
    post-fixer raster), regions are taken from it so fragments the
    topology fixer dissolved are not annotated as phantom duplicates.

    Publication mode delegates to the overlap-averse placer and returns
    its numbered key (empty list otherwise).
    """
    source = labels if label_source is None else np.asarray(label_source)
    if publication:
        return _publication_region_labels(
            ax, source, pH_vals, E_vals, catalog, unique_labels,
            spec_id_to_name, fontsize, water_lines)

    for lbl, rows, cols in _label_regions(source, unique_labels):
        pH_center = np.mean(pH_vals[cols])
        E_center = np.mean(E_vals[rows])

        raw_name = catalog.get(lbl, str(lbl))
        display = spec_id_to_name.get(raw_name, raw_name)

        # Shorten display name if too long
        if len(display) > 20:
            display = display[:18] + ".."

        ax.text(pH_center, E_center, display,
                ha="center", va="center",
                fontsize=fontsize, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2",
                         facecolor="white", alpha=0.7, edgecolor="none"))
    return []


def _publication_region_labels(ax, source, pH_vals, E_vals, catalog,
                               unique_labels, spec_id_to_name, fontsize,
                               water_lines):
    """Overlap-averse region annotation for publication figures.

    A region keeps its name only when the horizontal text box fits fully
    inside the region and the plot limits (checked by eroding the region
    mask with the text footprint); the anchor is the fitting cell with
    the most clearance, biased away from the water lines.  Every other
    region gets an index number at its pole of inaccessibility, resolved
    in the returned key lines.
    """
    try:
        from scipy.ndimage import distance_transform_edt, minimum_filter
    except ImportError:
        distance_transform_edt = minimum_filter = None

    # Data-to-display scale (points per data unit); the axes box moves a
    # little during final layout, so fit tests keep a safety margin.
    fig_w, fig_h = ax.figure.get_size_inches()
    pos = ax.get_position()
    span_pH = max(float(pH_vals[-1] - pH_vals[0]), 1e-12)
    span_E = max(float(E_vals[-1] - E_vals[0]), 1e-12)
    pts_per_pH = fig_w * pos.width * 72.0 / span_pH
    pts_per_E = fig_h * pos.height * 72.0 / span_E
    d_pH = float(np.median(np.diff(pH_vals))) if len(pH_vals) > 1 else span_pH
    d_E = float(np.median(np.diff(E_vals))) if len(E_vals) > 1 else span_E
    cell_w = d_pH * pts_per_pH
    cell_h = d_E * pts_per_E

    # Raster cells near a water line are poor label anchors.
    clear = np.ones(source.shape, dtype=bool)
    if water_lines:
        margin = 1.6 * fontsize / pts_per_E
        for offset in (1.229, 0.0):
            line_E = offset - NERNST_FACTOR * pH_vals[None, :]
            clear &= np.abs(E_vals[:, None] - line_E) > margin

    placed = []   # (row, col, text)
    pending = []  # name did not fit -> numbered
    for lbl, rows, cols in _label_regions(source, unique_labels):
        raw_name = catalog.get(lbl, str(lbl))
        display = spec_id_to_name.get(raw_name, raw_name)

        mask = np.zeros(source.shape, dtype=bool)
        mask[rows, cols] = True
        if distance_transform_edt is not None:
            dist = distance_transform_edt(
                np.pad(mask, 1), sampling=(cell_h, cell_w))[1:-1, 1:-1]
            biased = np.where(clear, dist, 0.0)
            field = biased if biased.max() > 0.0 else dist
            row, col = np.unravel_index(int(np.argmax(field)), field.shape)
        else:
            field = None
            row, col = int(np.mean(rows)), int(np.mean(cols))

        # Measure the real rendered footprint (bold text + bbox padding);
        # a safety factor absorbs the small axes rescale of final layout.
        probe = ax.text(0, 0, display, fontsize=fontsize,
                        fontweight="bold", ha="center", va="center")
        extent = probe.get_window_extent(
            ax.figure.canvas.get_renderer())
        probe.remove()
        pts_scale = 72.0 / ax.figure.dpi
        text_w = (extent.width * pts_scale + 0.4 * fontsize) / 0.9
        text_h = (extent.height * pts_scale + 0.4 * fontsize) / 0.9
        half_w = int(np.ceil(0.5 * text_w / cell_w))
        half_h = int(np.ceil(0.5 * text_h / cell_h))

        fits = False
        if minimum_filter is not None and field is not None:
            # The rim band counts as outside the region so the whole text
            # box (not merely its anchor) keeps a gap from the plot frame.
            pad_r = max(int(np.ceil(0.75 * fontsize / cell_h)), 1)
            pad_c = max(int(np.ceil(0.75 * fontsize / cell_w)), 1)
            inner = mask.copy()
            inner[:pad_r, :] = False
            inner[-pad_r:, :] = False
            inner[:, :pad_c] = False
            inner[:, -pad_c:] = False
            # Cells whose surrounding text footprint stays inside the
            # region; constant padding rejects footprints past the raster.
            feasible = minimum_filter(
                inner.astype(np.uint8),
                size=(2 * half_h + 1, 2 * half_w + 1),
                mode="constant", cval=0,
            ).astype(bool)
            if feasible.any():
                fits = True
                score = np.where(feasible, field, -1.0)
                row, col = np.unravel_index(
                    int(np.argmax(score)), score.shape)
        if fits:
            placed.append((row, col, display))
        else:
            pending.append((row, col, display))

    # Reading order: left to right, then top to bottom.
    pending.sort(key=lambda item: (item[1], -item[0]))
    key = []
    for num, (row, col, display) in enumerate(pending, start=1):
        placed.append((row, col, str(num)))
        key.append(f"{num:>2}. {display}")

    for row, col, text in placed:
        ax.text(pH_vals[col], E_vals[row], text,
                ha="center", va="center",
                fontsize=fontsize, fontweight="bold", zorder=12,
                bbox=dict(boxstyle="round,pad=0.2",
                          facecolor="white", alpha=0.75, edgecolor="none"))
    return key


def _label_regions(labels, unique_labels):
    """Yield ``(label, rows, cols)`` per connected region of each label.

    Uses the topology fixer's component walker (cardinal adjacency plus
    T1 self-contact bridges) so the annotations match the fixed
    topology's regions exactly; if the fixer is not importable
    (standalone use), falls back to one label per species at its
    overall centroid.
    """
    wanted = {int(lbl) for lbl in unique_labels}
    try:
        from _output_topology_mapper.topology_nd.topology_fixer import (
            TOPO_FIX_ENABLE, _self_contact_scan_2d, bridge_adjacency,
            label_components,
        )
    except ImportError:
        for lbl in unique_labels:
            rows, cols = np.where(labels == lbl)
            if rows.size:
                yield lbl, rows, cols
        return

    arr = np.asarray(labels)
    bridges = None
    if TOPO_FIX_ENABLE and arr.ndim == 2:
        _, bridge_pairs = _self_contact_scan_2d(arr)
        bridges = bridge_adjacency(bridge_pairs)
    for lbl, cells in label_components(arr, tuple(arr.shape), bridges):
        if lbl not in wanted:
            continue
        rows = np.fromiter((c[0] for c in cells), dtype=int, count=len(cells))
        cols = np.fromiter((c[1] for c in cells), dtype=int, count=len(cells))
        yield lbl, rows, cols
