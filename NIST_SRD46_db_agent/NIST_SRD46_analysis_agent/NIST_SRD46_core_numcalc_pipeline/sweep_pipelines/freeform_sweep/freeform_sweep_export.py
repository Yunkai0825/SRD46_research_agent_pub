"""
freeform_sweep_export.py
========================
Axis-agnostic output emitters for the freeform sweep.

Provides:
  - ``emit_cell_table_csv``      — one wide row per grid cell.
  - ``emit_fraction_csvs``       — per-principal-element fraction tables.
  - ``write_run_params_json``    — sweep metadata.
  - ``emit_1d_fraction_plots``   — fractions vs single axis (1-D only).
  - ``emit_2d_label_heatmaps``   — per-element label heatmap (2-D only).
  - ``generate_all_output``      — convenience orchestrator.

Also exposes the sweep-registry metadata (``SWEEP_ID``, ``sweep_fn``).
"""
from __future__ import annotations

import csv
import json as _json
import pathlib
from itertools import product
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .freeform_sweep_main import run_freeform_sweep
from ._paths import long_path


sweep_fn = run_freeform_sweep

SWEEP_ID = "freeform_sweep"
SWEEP_DESCRIPTION = (
    "Generic N-D freeform sweep: accepts an arbitrary set of axes "
    "(pH, E_V, a_w, total concentrations, user-declared freeform "
    "variables, …) and emits axis-agnostic per-cell tables and "
    "topology. Catch-all for sweeps that do not fit pH_sweep or "
    "pourbaix_sweep."
)
SWEEP_PARAMS = {
    "axes":          {"type": "list[GridAxis|dict]",
                      "required": True,
                      "description": "Ordered list of axis specs."},
    "refine_factor": {"type": "int|null", "required": True,
                      "description": "Null when disabled; otherwise >=2."},
    "n_layers":      {"type": "int", "required": True,
                      "description": "0 disables refinement; >=1 enables it."},
}


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

def _iter_cells(grid):
    """Yield ``(multi_index, PointResult)`` for every cell."""
    for idx in product(*[range(n) for n in grid.shape]):
        pr = grid.points[idx]
        if pr is None:
            continue
        yield idx, pr


def _safe_get(d: Optional[Dict[str, float]], key: str, default: float = 0.0) -> float:
    if d is None:
        return default
    v = d.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# Integer sentinel written by the labeler for cells that never converged
# (see grid_dynamic_refiner/labeler.py).  Excluded from region maps.
_UNCONVERGED = -2

# Distinguishable categorical palette (shared look with the Pourbaix
# region plotter) — one flat colour per predominance region.
_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#86bcb6", "#8cd17d", "#b6992d", "#499894", "#f1ce63",
    "#d37295", "#a0cbe8", "#ffbe7d", "#d4a6c8", "#fabfd2",
]


def _cell_edges(vals: np.ndarray) -> np.ndarray:
    """Convert 1-D cell centres to ``len(vals)+1`` edges for pcolormesh.

    Handles non-uniform spacing (e.g. an explicit ``values`` axis).
    """
    vals = np.asarray(vals, dtype=float)
    if len(vals) == 1:
        return np.array([vals[0] - 0.5, vals[0] + 0.5])
    d = np.diff(vals)
    edges = np.empty(len(vals) + 1)
    edges[0] = vals[0] - d[0] / 2.0
    edges[-1] = vals[-1] + d[-1] / 2.0
    edges[1:-1] = (vals[:-1] + vals[1:]) / 2.0
    return edges


def _draw_label_boundaries(ax, labels_xy: np.ndarray,
                           x_edges: np.ndarray, y_edges: np.ndarray,
                           *, lw: float = 0.5, alpha: float = 0.7) -> None:
    """Draw thin lines between adjacent cells with different labels.

    ``labels_xy`` is indexed ``[ix, iy]`` (x-axis first), matching the
    grid's native ``(ax0, ax1)`` cell layout.  Boundaries touching an
    unconverged sentinel are skipped.
    """
    nx, ny = labels_xy.shape
    for ix in range(nx - 1):
        xe = x_edges[ix + 1]
        for iy in range(ny):
            a, b = labels_xy[ix, iy], labels_xy[ix + 1, iy]
            if a != b and a >= 0 and b >= 0:
                ax.plot([xe, xe], [y_edges[iy], y_edges[iy + 1]],
                        "k-", linewidth=lw, alpha=alpha)
    for iy in range(ny - 1):
        ye = y_edges[iy + 1]
        for ix in range(nx):
            a, b = labels_xy[ix, iy], labels_xy[ix, iy + 1]
            if a != b and a >= 0 and b >= 0:
                ax.plot([x_edges[ix], x_edges[ix + 1]], [ye, ye],
                        "k-", linewidth=lw, alpha=alpha)


# ------------------------------------------------------------------
#  1.  Wide per-cell table
# ------------------------------------------------------------------

def emit_cell_table_csv(
    grid, built, output_dir: pathlib.Path, *,
    prefix: str = "", debug: bool = False,
) -> str:
    """One row per converged cell: axes + scalar metrics + log_conc per species."""
    out = pathlib.Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""
    fpath = out / f"{pfx}cells.csv"

    axis_names = [ax.name for ax in grid.axes]
    species_ids = list(getattr(built, "species_ids", []) or [])
    species_labels = list(getattr(built, "species_labels", species_ids) or species_ids)
    solid_ids = list(getattr(built, "diss_labels", []) or [])

    header = (
        list(axis_names)
        + ["converged", "iterations", "residual"]
        + [f"logc[{lbl}]" for lbl in species_labels]
        + [f"n_s[{lbl}]" for lbl in solid_ids]
    )

    with open(long_path(fpath), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for idx, pr in _iter_cells(grid):
            coords = grid.coords_at(idx)
            row: List[Any] = [f"{coords[name]:.6g}" for name in axis_names]
            row.append(1 if pr.converged else 0)
            row.append(int(getattr(pr, "iterations", 0) or 0))
            try:
                row.append(f"{float(pr.residual):.6e}")
            except Exception:
                row.append("nan")
            for sid in species_ids:
                row.append(f"{_safe_get(pr.log_conc, sid, float('nan')):.6f}")
            for solid in solid_ids:
                row.append(f"{_safe_get(pr.solid_amounts, solid, 0.0):.6e}")
            w.writerow(row)
    if debug:
        print(f"[freeform_export] cells table -> {fpath}")
    return str(fpath)


# ------------------------------------------------------------------
#  2.  Per-element fraction CSVs
# ------------------------------------------------------------------

def emit_fraction_csvs(
    grid, built, output_dir: pathlib.Path, *,
    prefix: str = "", debug: bool = False,
) -> List[str]:
    """Emit one CSV per principal element with fraction-of-element per species."""
    out = pathlib.Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""
    axis_names = [ax.name for ax in grid.axes]

    elements = list(getattr(built, "principal_elements", None)
                    or getattr(built, "element_names", []) or [])
    species_ids = list(getattr(built, "species_ids", []) or [])
    species_labels = list(getattr(built, "species_labels", species_ids) or species_ids)
    paths: List[str] = []

    for elem in elements:
        fpath = out / f"{pfx}frac_{elem}.csv"
        header = list(axis_names) + [f"frac[{lbl}]" for lbl in species_labels]
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            for idx, pr in _iter_cells(grid):
                coords = grid.coords_at(idx)
                fracs = (pr.frac_element or {}).get(elem, {}) if pr else {}
                row: List[Any] = [f"{coords[name]:.6g}" for name in axis_names]
                for sid in species_ids:
                    row.append(f"{_safe_get(fracs, sid, 0.0):.6e}")
                w.writerow(row)
        paths.append(str(fpath))
        if debug:
            print(f"[freeform_export] fractions[{elem}] -> {fpath}")

    # Ligand fractions: one CSV per ligand id present in any PointResult.
    ligand_ids: List[str] = []
    seen = set()
    for _idx, pr in _iter_cells(grid):
        for lid in (pr.frac_ligand or {}).keys():
            if lid not in seen:
                seen.add(lid); ligand_ids.append(lid)
        if len(seen) >= 8:
            break
    for lid in ligand_ids:
        fpath = out / f"{pfx}frac_lig_{lid}.csv"
        header = list(axis_names) + [f"frac[{lbl}]" for lbl in species_labels]
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            for idx, pr in _iter_cells(grid):
                coords = grid.coords_at(idx)
                fracs = (pr.frac_ligand or {}).get(lid, {}) if pr else {}
                row: List[Any] = [f"{coords[name]:.6g}" for name in axis_names]
                for sid in species_ids:
                    row.append(f"{_safe_get(fracs, sid, 0.0):.6e}")
                w.writerow(row)
        paths.append(str(fpath))
        if debug:
            print(f"[freeform_export] lig fractions[{lid}] -> {fpath}")

    return paths


# ------------------------------------------------------------------
#  3.  Run-params metadata
# ------------------------------------------------------------------

def write_run_params_json(
    built, axes, output_dir: pathlib.Path, *,
    prefix: str = "", ionic_strength: Optional[float] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> str:
    out = pathlib.Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""
    fpath = out / f"{pfx}run_params.json"
    payload: Dict[str, Any] = {
        "sweep_id":        SWEEP_ID,
        "system_name":     getattr(built, "system_name", None),
        "principal_elements": list(getattr(built, "principal_elements", []) or []),
        "element_names":   list(getattr(built, "element_names", []) or []),
        "ligand_ids":      list(getattr(built, "ligand_ids", []) or []),
        "ionic_strength":  ionic_strength if ionic_strength is not None
                            else getattr(built, "ionic_strength", None),
        "axes": [
            {"name": ax.name,
             "min":  float(ax.values[0]),
             "max":  float(ax.values[-1]),
             "n_points": int(ax.n)}
            for ax in axes
        ],
    }
    if extras:
        payload.update(extras)
    with open(long_path(fpath), "w", encoding="utf-8") as fh:
        _json.dump(payload, fh, indent=2, default=str)
    return str(fpath)


# ------------------------------------------------------------------
#  4.  Optional 1-D plot
# ------------------------------------------------------------------

def emit_1d_fraction_plots(
    grid, built, output_dir: pathlib.Path, *,
    prefix: str = "", debug: bool = False,
) -> List[str]:
    """Plot fraction-of-component vs the single axis (one PNG per component).

    A *component* is a principal element or a ligand (one PNG each).  The
    per-species fraction is computed directly from the solved cell state
    — aqueous concentrations (``PointResult.conc``) weighted by the
    species' basis stoichiometry (``built.stoich_pq``) plus precipitated
    solids (``PointResult.solid_amounts`` weighted by
    ``built.diss_stoich_pq``) — and normalised by the component total.

    Computing fractions here (rather than relying on the labeler's
    aqueous-only ``frac_element``) means the plot stays meaningful even
    when the component is largely sequestered in a solid phase: the solid
    appears as a dashed curve so the diagram never comes out empty.
    """
    if grid.ndim != 1:
        return []
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = pathlib.Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""

    axis = grid.axes[0]
    x = np.asarray(axis.values, dtype=float)
    n = int(axis.n)

    element_names = list(getattr(built, "element_names", []) or [])
    n_metals = len(element_names)
    ligand_names = list(getattr(built, "ligand_names", []) or [])
    principal = list(getattr(built, "principal_elements", None)
                     or element_names)

    species_ids = list(getattr(built, "species_ids", []) or [])
    species_labels = list(getattr(built, "species_labels", species_ids)
                          or species_ids)
    label_map = dict(zip(species_ids, species_labels))
    solid_ids = list(getattr(built, "diss_labels", []) or [])

    stoich_pq = np.asarray(getattr(built, "stoich_pq",
                                   np.zeros((len(species_ids), 0))),
                           dtype=float)
    diss_pq = np.asarray(getattr(built, "diss_stoich_pq",
                                 np.zeros((len(solid_ids), 0))),
                         dtype=float)
    n_basis = int(getattr(built, "n_basis", stoich_pq.shape[1] if stoich_pq.ndim == 2 else 0))

    # Build the ordered list of (display_label, basis_column, file_tag).
    components: List = []
    for name in principal:
        if name in element_names:
            components.append((name, element_names.index(name), name))
        else:  # tolerate redox-decorated names (e.g. "Cu$+2")
            base = name.split("$", 1)[0]
            col = next((k for k, nm in enumerate(element_names)
                        if nm.split("$", 1)[0] == base), None)
            if col is not None:
                components.append((name, col, name))
    for j, lname in enumerate(ligand_names):
        col = n_metals + j
        if col < n_basis:
            components.append((lname, col, f"lig_{lname}"))

    paths: List[str] = []
    for disp, col, tag in components:
        if col >= stoich_pq.shape[1] and col >= diss_pq.shape[1]:
            continue
        aq_series = {sid: np.zeros(n, dtype=float) for sid in species_ids}
        sol_series = {sd: np.zeros(n, dtype=float) for sd in solid_ids}
        for i in range(n):
            pr = grid.points[(i,)]
            if pr is None or not getattr(pr, "converged", False):
                continue
            conc = pr.conc or {}
            samt = pr.solid_amounts or {}
            aq_amt: Dict[str, float] = {}
            sol_amt: Dict[str, float] = {}
            tot = 0.0
            for si, sid in enumerate(species_ids):
                coeff = (stoich_pq[si, col]
                         if si < stoich_pq.shape[0] and col < stoich_pq.shape[1]
                         else 0.0)
                if coeff <= 0:
                    continue
                amt = float(conc.get(sid, 0.0) or 0.0) * float(coeff)
                if amt > 0:
                    aq_amt[sid] = amt
                    tot += amt
            for sj, sd in enumerate(solid_ids):
                coeff = (diss_pq[sj, col]
                         if sj < diss_pq.shape[0] and col < diss_pq.shape[1]
                         else 0.0)
                if coeff <= 0:
                    continue
                amt = float(samt.get(sd, 0.0) or 0.0) * float(coeff)
                if amt > 0:
                    sol_amt[sd] = amt
                    tot += amt
            if tot <= 0:
                continue
            for sid, amt in aq_amt.items():
                aq_series[sid][i] = amt / tot
            for sd, amt in sol_amt.items():
                sol_series[sd][i] = amt / tot

        fig, ax = plt.subplots(figsize=(8, 5))
        any_plotted = False
        for sid in species_ids:
            ser = aq_series[sid]
            if float(np.nanmax(ser)) < 1e-3:
                continue
            ax.plot(x, ser, label=label_map.get(sid, sid))
            any_plotted = True
        for sd in solid_ids:
            ser = sol_series[sd]
            if float(np.nanmax(ser)) < 1e-3:
                continue
            ax.plot(x, ser, "--", label=f"{sd} (s)")
            any_plotted = True
        if not any_plotted:
            plt.close(fig); continue
        ax.set_xlabel(getattr(axis, "display_label", axis.name))
        ax.set_ylabel(f"fraction of {disp}")
        ax.set_ylim(0, 1.05)
        ax.set_title(
            f"{getattr(built,'system_name','')} — frac({disp}) vs {axis.name}")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        fpath = out / f"{pfx}frac_{tag}.png"
        fig.tight_layout()
        fig.savefig(long_path(fpath), dpi=120)
        plt.close(fig)
        paths.append(str(fpath))
        if debug:
            print(f"[freeform_export] frac plot[{disp}] -> {fpath}")
    return paths



# ------------------------------------------------------------------
#  5.  2-D categorical predominance-region map
# ------------------------------------------------------------------

def emit_2d_label_heatmaps(
    grid, built, output_dir: pathlib.Path, *,
    prefix: str = "", debug: bool = False,
) -> List[str]:
    """Per-element categorical predominance-region map over a 2-D grid.

    Colours every grid cell by its dominant-species label using a
    discrete palette (one flat colour per species) and plots it against
    the two *declared* freeform axes — the first declared axis on x, the
    second on y (the same convention Pourbaix uses: pH on x, E on y).
    A legend keyed on the per-element label catalog names each region;
    unconverged cells are masked (white).
    """
    if grid.ndim != 2:
        return []
    if grid.labels_per_element is None or grid.label_catalog_per_element is None:
        return []
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch

    out = pathlib.Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""

    # First declared axis -> x, second -> y.
    ax_x, ax_y = grid.axes
    x_vals = np.asarray(ax_x.values, dtype=float)
    y_vals = np.asarray(ax_y.values, dtype=float)
    x_edges = _cell_edges(x_vals)
    y_edges = _cell_edges(y_vals)
    paths: List[str] = []

    for elem, label_arr in grid.labels_per_element.items():
        if label_arr is None:
            continue
        # Native cell layout is (n_ax0, n_ax1) == (n_x, n_y).
        labels_xy = np.asarray(label_arr)
        catalog = grid.label_catalog_per_element.get(elem, {}) or {}

        # Distinct converged labels (exclude the unconverged sentinel).
        uniq = sorted({int(v) for v in np.unique(labels_xy)
                       if int(v) != _UNCONVERGED})
        if not uniq:
            continue

        colour_of = {lbl: _PALETTE[i % len(_PALETTE)]
                     for i, lbl in enumerate(uniq)}
        cmap = mcolors.ListedColormap([colour_of[l] for l in uniq])
        cmap.set_bad("#ffffff")  # masked (unconverged) -> white

        # Remap label ints to sequential plot indices; sentinel -> masked.
        remap = {lbl: i for i, lbl in enumerate(uniq)}
        plot_xy = np.full(labels_xy.shape, np.nan, dtype=float)
        for lbl, i in remap.items():
            plot_xy[labels_xy == lbl] = i
        # pcolormesh wants C as (n_y, n_x) -> transpose (x-axis first).
        plot_masked = np.ma.masked_invalid(plot_xy.T)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pcolormesh(
            x_edges, y_edges, plot_masked,
            cmap=cmap, vmin=-0.5, vmax=len(uniq) - 0.5,
            shading="flat",
        )
        _draw_label_boundaries(ax, labels_xy, x_edges, y_edges)

        ax.set_xlabel(ax_x.display_label)
        ax.set_ylabel(ax_y.display_label)
        ax.set_xlim(float(x_edges[0]), float(x_edges[-1]))
        ax.set_ylim(float(y_edges[0]), float(y_edges[-1]))
        ax.set_title(
            f"{getattr(built, 'system_name', '')} — predominance({elem})")

        handles = [
            Patch(facecolor=colour_of[l], edgecolor="none",
                  label=str(catalog.get(l, l)))
            for l in uniq
        ]
        ax.legend(handles=handles, loc="center left",
                  bbox_to_anchor=(1.02, 0.5), fontsize=8, title=elem,
                  frameon=False)

        fig.tight_layout()
        fpath = out / f"{pfx}label_{elem}.png"
        fig.savefig(long_path(fpath), dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(str(fpath))
        if debug:
            print(f"[freeform_export] region map[{elem}] -> {fpath}")
    return paths


# ------------------------------------------------------------------
#  Convenience orchestrator (used by registry)
# ------------------------------------------------------------------

def generate_all_output(
    sweep_result: Dict[str, Any],
    output_dir: pathlib.Path,
    *, prefix: str = "", debug: bool = False,
) -> List[str]:
    """Aggregate emitters into a single call (registry convenience)."""
    grid = sweep_result.get("grid")
    built = sweep_result.get("built")
    if grid is None or built is None:
        return []
    paths: List[str] = []
    paths.append(emit_cell_table_csv(grid, built, output_dir,
                                      prefix=prefix, debug=debug))
    paths.extend(emit_fraction_csvs(grid, built, output_dir,
                                     prefix=prefix, debug=debug))
    if grid.ndim == 1:
        paths.extend(emit_1d_fraction_plots(grid, built, output_dir,
                                             prefix=prefix, debug=debug))
    elif grid.ndim == 2:
        paths.extend(emit_2d_label_heatmaps(grid, built, output_dir,
                                             prefix=prefix, debug=debug))
    return paths
