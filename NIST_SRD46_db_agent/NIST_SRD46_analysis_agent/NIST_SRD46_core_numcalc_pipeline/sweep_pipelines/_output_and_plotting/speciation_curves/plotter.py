"""
plotter.py
==========
Publication-quality speciation diagrams from ``SpeciationCurve`` data.

Supports:
- Fraction vs pH  (metal- and ligand-centred)
- log₁₀[species] vs pH
- Multi-component fraction diagrams

All functions are sweep-independent and can be used with any
``SpeciationCurve`` regardless of how it was produced.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import re
import sys as _sys
_SP = str(Path(__file__).resolve().parents[2])
if _SP not in _sys.path:
    _sys.path.insert(0, _SP)
from sweep_pipelines._path_utils import long_path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ── Colour palettes ──────────────────────────────────────────────

_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#aec7e8",
    "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94",
    "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5", "#393b79",
]

_SOLID_PALETTE = [
    "#006400", "#8b0000", "#00008b", "#4b0082", "#2f4f4f",
    "#8b4513", "#191970",
]


def _assert_mpl():
    if not HAS_MPL:
        raise ImportError("matplotlib required — pip install matplotlib")


_REDOX_TOKEN_RE = re.compile(r"^([A-Z][a-z]?)\$([+-]\d+)$")


def _format_total_molar(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{v:g} M" if v > 0.0 else ""


def _system_display_title(curve) -> str:
    """Element-grouped system name annotated with declared totals."""
    name = str(getattr(curve, "system_name", "") or "")
    parts = [p.strip() for p in name.split(" + ") if p.strip()]
    run_params = dict(getattr(curve, "run_params", None) or {})

    element_totals: Dict[str, float] = {}
    for key, value in (run_params.get("parent_element_totals") or {}).items():
        m = re.match(r"^\[([A-Za-z]{1,2})\]_total$", str(key))
        if m:
            element_totals[m.group(1)] = float(value or 0.0)
    for key, value in (run_params.get("redox_state_subtotals") or {}).items():
        m = re.match(r"^\[([A-Za-z]{1,2})\$[+-]?\d+\]_total$", str(key))
        if m:
            element_totals[m.group(1)] = (
                element_totals.get(m.group(1), 0.0) + float(value or 0.0))
    ligand_totals = [
        value for key, value in
        (run_params.get("component_totals") or {}).items()
        if "ligand" in str(key)
    ]

    display: List[str] = []
    seen_elements: set = set()
    lig_idx = 0
    for part in parts:
        m = _REDOX_TOKEN_RE.match(part)
        element = m.group(1) if m else (
            part if part in element_totals else None)
        if element is not None:
            if element in seen_elements:
                continue
            seen_elements.add(element)
            total = _format_total_molar(element_totals.get(element))
            display.append(f"{element} ({total})" if total else element)
        else:
            total = ""
            if lig_idx < len(ligand_totals):
                total = _format_total_molar(ligand_totals[lig_idx])
            lig_idx += 1
            display.append(f"{part} ({total})" if total else part)
    text = " + ".join(display) if display else name
    fixed_e = run_params.get("fixed_E_V")
    if fixed_e is not None:
        try:
            text = f"{text} @ Eh = {float(fixed_e):g} V"
        except (TypeError, ValueError):
            pass
    return text


def _log_concentration_plot_values(curve, sp_id, sp):
    """Mask inactive solids without altering stored solver-derived values."""

    raw = curve.series(sp_id, "log_conc")
    if getattr(sp, "phase", "aqueous") == "solid":
        vals = []
        for result, value in zip(curve.results, raw):
            amounts = getattr(result, "solid_amounts", {}) or {}
            amount = amounts.get(sp_id)
            if amount is None:
                amount = amounts.get(getattr(sp, "label", ""))
            if amount is None:
                amount = (getattr(result, "conc", {}) or {}).get(sp_id, 0.0)
            vals.append(value if float(amount or 0.0) > 0.0 else float("nan"))
        return vals
    return [value if value < 0.0 else float("nan") for value in raw]


def _draw_solid_phase_edges(ax, x_values, vals, floor, color, lw) -> None:
    """Draw vertical onset/offset edges for a masked condensed-phase trace.

    Display-only companion to the inactive-solid mask: each contiguous
    active run gets a vertical segment from the plot floor at its first
    and last sample so the precipitation window reads as a closed shape.
    """
    n = len(vals)
    for i, value in enumerate(vals):
        if math.isnan(value):
            continue
        starts_run = i == 0 or math.isnan(vals[i - 1])
        ends_run = i == n - 1 or math.isnan(vals[i + 1])
        if starts_run and i > 0:
            ax.plot([x_values[i], x_values[i]], [floor, value],
                    color=color, ls="-", lw=lw, solid_capstyle="butt")
        if ends_run and i < n - 1:
            ax.plot([x_values[i], x_values[i]], [floor, value],
                    color=color, ls="-", lw=lw, solid_capstyle="butt")


# ══════════════════════════════════════════════════════════════════
#  Fraction diagram
# ══════════════════════════════════════════════════════════════════

def plot_fraction(
    curve,
    component: str = "M",
    *,
    min_frac: float = 0.01,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Optional[str] = None,
) -> Any:
    """Plot species fraction vs pH for one component ("M" or "L").

    Parameters
    ----------
    curve : SpeciationCurve
    component : "M" for metal, "L" for ligand
    min_frac : exclude species below this max fraction
    save_path : file path to save image
    """
    _assert_mpl()
    fig, ax = plt.subplots(figsize=figsize)
    pH = curve.pH_values
    kind = "frac_M" if component == "M" else "frac_L"

    plotted = []
    ci = 0
    for sp_id, sp in curve.species.items():
        vals = curve.series(sp_id, kind)
        if max(vals) < min_frac:
            continue
        is_solid = getattr(sp, "phase", "aqueous") == "solid"
        pal = _SOLID_PALETTE if is_solid else _PALETTE
        color = pal[ci % len(pal)]
        lw = 3.0 if is_solid else 1.8
        ax.plot(pH, vals, color=color, lw=lw, label=sp.label)
        plotted.append(sp_id)
        ci += 1

    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("pH", fontsize=12)
    ylabel = ("Fraction of total metal" if component == "M"
              else "Fraction of total ligand")
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(
        title or f"Speciation: {_system_display_title(curve)} ({component})",
        fontsize=13)
    ax.grid(True, alpha=0.25)
    if plotted:
        ax.legend(fontsize=7, ncol=4, loc="lower center",
                  bbox_to_anchor=(0.5, 1.02), borderaxespad=0.0)
    fig.tight_layout(rect=[0, 0, 1, 0.88])
    if save_path:
        fig.savefig(long_path(save_path), dpi=150, bbox_inches="tight")
    return fig


# ══════════════════════════════════════════════════════════════════
#  Log-concentration diagram
# ══════════════════════════════════════════════════════════════════

def plot_log_conc(
    curve,
    *,
    min_log: float = -12.0,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Optional[str] = None,
) -> Any:
    """Plot log₁₀[species] vs pH."""
    _assert_mpl()
    fig, ax = plt.subplots(figsize=figsize)
    pH = curve.pH_values

    ci = 0
    for sp_id, sp in curve.species.items():
        vals = _log_concentration_plot_values(curve, sp_id, sp)
        finite = [value for value in vals if not math.isnan(value)]
        if not finite or max(finite) < min_log:
            continue
        color = _PALETTE[ci % len(_PALETTE)]
        ax.plot(pH, vals, color=color, lw=1.8, label=sp.label)
        if getattr(sp, "phase", "aqueous") == "solid":
            _draw_solid_phase_edges(ax, pH, vals, min_log, color, 1.8)
        ci += 1

    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(min_log, 0)
    ax.set_xlabel("pH", fontsize=12)
    ax.set_ylabel("log\u2081\u2080 [species]  (mol/L)", fontsize=12)
    ax.set_title(
        title or f"Log-concentration: {_system_display_title(curve)}",
        fontsize=13)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=4, loc="lower center",
              bbox_to_anchor=(0.5, 1.02), borderaxespad=0.0)
    fig.tight_layout(rect=[0, 0, 1, 0.88])
    if save_path:
        fig.savefig(long_path(save_path), dpi=150, bbox_inches="tight")
    return fig


# ══════════════════════════════════════════════════════════════════
#  Multi-component fraction diagram
# ══════════════════════════════════════════════════════════════════

def plot_multi_fraction(
    curve,
    component_id: str,
    *,
    min_frac: float = 0.01,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Optional[str] = None,
) -> Any:
    """Plot fraction vs pH for one metal/ligand in a multi-component system.

    Parameters
    ----------
    curve : SpeciationCurve
    component_id : internal ID (e.g. "M1", "L1")
    """
    _assert_mpl()
    fig, ax = plt.subplots(figsize=figsize)
    pH = curve.pH_values

    comp_name = (getattr(curve, "metal_names", {}).get(component_id)
                 or getattr(curve, "ligand_names", {}).get(component_id)
                 or component_id)

    plotted = []
    ci = 0
    for sp_id, sp in curve.species.items():
        vals = curve.series_multi(sp_id, component_id)
        if max(vals) < min_frac:
            continue
        color = _PALETTE[ci % len(_PALETTE)]
        ax.plot(pH, vals, color=color, lw=1.8, label=sp.label)
        plotted.append(sp_id)
        ci += 1

    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("pH", fontsize=12)
    ax.set_ylabel(f"Fraction of total {comp_name}", fontsize=12)
    ax.set_title(
        title or f"Speciation: {_system_display_title(curve)} \u2014 {comp_name}",
        fontsize=13)
    ax.grid(True, alpha=0.25)
    if plotted:
        ax.legend(fontsize=7, ncol=4, loc="lower center",
                  bbox_to_anchor=(0.5, 1.02), borderaxespad=0.0)
    fig.tight_layout(rect=[0, 0, 1, 0.88])
    if save_path:
        fig.savefig(long_path(save_path), dpi=150, bbox_inches="tight")
    return fig
