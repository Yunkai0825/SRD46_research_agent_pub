"""
pH Sweep Plotting â€” publication-quality speciation diagrams.
=============================================================
Produces:
  - Fraction vs pH  (metal-centred and ligand-centred)
  - Log-concentration vs pH
  - Multi-component fraction diagrams

All functions accept a ``SpeciationCurve`` from ``speciation_dataclasses``.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.thermodynamics_helpers.speciation_dataclasses import (
    SpeciationCurve,
    SpeciesType,
)
from sweep_pipelines._path_utils import long_path

# â”€â”€ palettes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_METAL_PALETTES = [
    ["#1f77b4", "#4a90d9", "#6baed6", "#9ecae1", "#2166ac"],
    ["#d62728", "#e6550d", "#fd8d3c", "#f03b20", "#cb181d"],
    ["#2ca02c", "#31a354", "#74c476", "#006d2c", "#4daf4a"],
    ["#9467bd", "#756bb1", "#807dba", "#6a51a3", "#bcbddc"],
]

_LIGAND_H_PALETTE = [
    "#e377c2", "#ff7f0e", "#bcbd22", "#8c564b", "#c49c94",
    "#ffbb78", "#f7b6d2", "#dbdb8d", "#c7c7c7", "#aec7e8",
]

_FREE_ION_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#17becf", "#e377c2", "#bcbd22",
]

_SOLID_PALETTE = [
    "#006400", "#8b0000", "#00008b", "#4b0082", "#2f4f4f",
    "#8b4513", "#191970",
]

_COMPLEX_LINE_STYLES = ["-", "-", "-.", "-.", ":", ":"]

_LINE_STYLES = {
    SpeciesType.METAL:             "-",
    SpeciesType.LIGAND:            "-",
    SpeciesType.PROTONATED_LIGAND: "--",
    SpeciesType.COMPLEX:           "-",
    SpeciesType.PROTON:            ":",
    SpeciesType.HYDROXIDE:         ":",
}


# â”€â”€ style helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _classify_species_for_style(sp):
    """Return (category, group_key) for a species."""
    if sp.phase == "solid":
        return "solid", sp.id
    if sp.stype == SpeciesType.METAL:
        return "free_metal", sp.stoich.get("M0", sp.id) if sp.stoich else sp.id
    if sp.stype == SpeciesType.LIGAND:
        return "free_ligand", sp.id
    if sp.stype == SpeciesType.PROTONATED_LIGAND:
        return "ligand_H", sp.id
    if sp.stype == SpeciesType.COMPLEX:
        metals = sorted(k for k in sp.stoich if k.startswith("M"))
        return "complex", metals[0] if metals else "unknown"
    return "other", sp.id


def _assign_styles(species_dict):
    """Build a dict {sp_id: (color, linestyle, linewidth)} for all species."""
    styles = {}
    solid_idx = 0
    ligand_h_idx = 0
    free_ion_idx = 0
    metal_complex_ctr = {}
    metal_key_order = []

    for sp_id, sp in species_dict.items():
        cat, grp = _classify_species_for_style(sp)
        if cat == "complex" and grp not in metal_key_order:
            metal_key_order.append(grp)

    for sp_id, sp in species_dict.items():
        cat, grp = _classify_species_for_style(sp)

        if cat == "solid":
            color = _SOLID_PALETTE[solid_idx % len(_SOLID_PALETTE)]
            solid_idx += 1
            styles[sp_id] = (color, "-", 3.5)
        elif cat == "free_metal":
            midx = metal_key_order.index(grp) if grp in metal_key_order else 0
            pal = _METAL_PALETTES[midx % len(_METAL_PALETTES)]
            styles[sp_id] = (pal[0], "-", 2.0)
        elif cat == "free_ligand":
            color = _FREE_ION_PALETTE[free_ion_idx % len(_FREE_ION_PALETTE)]
            free_ion_idx += 1
            styles[sp_id] = (color, "-", 1.8)
        elif cat == "ligand_H":
            color = _LIGAND_H_PALETTE[ligand_h_idx % len(_LIGAND_H_PALETTE)]
            ligand_h_idx += 1
            styles[sp_id] = (color, "--", 1.8)
        elif cat == "complex":
            midx = metal_key_order.index(grp) if grp in metal_key_order else 0
            pal = _METAL_PALETTES[midx % len(_METAL_PALETTES)]
            ci = metal_complex_ctr.get(grp, 0)
            metal_complex_ctr[grp] = ci + 1
            color = pal[(ci + 1) % len(pal)]
            ls = _COMPLEX_LINE_STYLES[ci % len(_COMPLEX_LINE_STYLES)]
            styles[sp_id] = (color, ls, 1.8)
        else:
            color = _FREE_ION_PALETTE[free_ion_idx % len(_FREE_ION_PALETTE)]
            free_ion_idx += 1
            styles[sp_id] = (color, "-", 1.5)

    return styles


def _assert_mpl():
    if not HAS_MPL:
        raise ImportError("matplotlib required â€“ pip install matplotlib")


def _log_concentration_plot_values(curve, sp_id, sp):
    """Return physical log-concentration values for plotting.

    ``curve_builder`` stores a finite numerical floor for an inactive solid so
    that the text/CSV representation remains rectangular.  That floor is a
    serialization sentinel, not a solver concentration.  Drawing it joins the
    last inactive sample to the first active sample and creates a misleading
    near-vertical solid line.  Use the solver-derived ``solid_amounts`` mask so
    an absent condensed phase is a gap and every displayed solid value is the
    logarithm of its actual positive amount.
    """

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

    # ``series()`` uses 0.0 for a missing aqueous species.  Preserve the
    # established gap semantics for that sentinel.
    return [value if value < 0.0 else float("nan") for value in raw]


def _draw_solid_phase_edges(ax, x_values, vals, floor, color, lw) -> None:
    """Draw vertical onset/offset edges for a masked condensed-phase trace.

    The inactive-solid mask renders an absent phase as a gap, so the
    precipitation edge otherwise starts mid-plot.  For human display,
    drop a vertical segment from the plot floor to the first and last
    active sample of every contiguous active run (classic textbook
    solubility-onset rendering).  Display-only: no data values change.
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

# â”€â”€ display / filtering helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _safe_label(text: Any) -> str:
    """Make a label/title safe for matplotlib display.

    The internal species ids carry a ``$`` oxidation-state marker (e.g.
    ``Cu$+2``). matplotlib treats ``$`` as a math-mode delimiter, so an
    odd number of them raises or renders garbled text — and the user
    should never see the internal ``$`` notation anyway. Strip it.
    """
    return str(text).replace("$", "")


_REDOX_TOKEN_RE = re.compile(r"^([A-Z][a-z]?)\$([+-]\d+)$")


def _format_total_molar(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{v:g} M" if v > 0.0 else ""


def _system_display_title(curve) -> str:
    """Element-grouped system name annotated with declared totals.

    Collapses per-oxidation-state tokens (``Fe$+2 + Fe$+0 + Fe$+3`` → ``Fe``,
    matching the Pourbaix header convention) and appends the analytical
    total of each component from ``curve.run_params`` when available,
    e.g. ``Fe (0.001 M) + Citric acid (0.005 M)``.
    """
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


def _is_solvent_species(sp) -> bool:
    """True for the water/solvent species (hidden from speciation plots).

    Water is the medium, not a solute, and the upstream VLM sometimes
    leaves it unresolved as ``?`` / ``[?]``. Detection is structural so a
    genuinely mis-named metal/ligand complex is never hidden:

    * explicit water label (``H2O`` / ``water``), or
    * a neutral species whose stoichiometry uses only solvent atoms
      (``H`` / ``OH`` / ``O``), or
    * an unresolved ``?`` label with no stoichiometry at all (the bare
      self-ion product the labeler could not name).
    """
    lbl = (getattr(sp, "label", "") or "").strip().lower()
    keys = set(getattr(sp, "stoich", {}) or {})
    charge = getattr(sp, "charge", 0)
    if lbl in {"h2o", "h\u2082o", "water"}:
        return True
    if charge == 0 and keys and keys <= {"H", "OH", "O"}:
        return True
    if lbl in {"?", "[?]"} and not keys:
        return True
    return False


# Publication layout: fixed data-area rectangles so the enlarged legend never
# rescales the plot or changes the saved image size.  The side rect reserves
# the right margin for the outside legend; the full rect is for diagrams whose
# legend sits inside the axes.
# Two-column threshold shared by the legend and the data-area rectangles.
_PUB_2COL_THRESHOLD = 14
# Publication data-area rectangles.  A one-column legend is narrow so the plot
# can be wider; a two-column legend needs a broader reserved margin.  The full
# rect is for diagrams whose legend sits inside the axes.
_PUB_RECT_SIDE_1COL = (0.08, 0.11, 0.62, 0.80)
_PUB_RECT_SIDE_2COL = (0.08, 0.11, 0.51, 0.80)
_PUB_RECT_FULL = (0.09, 0.11, 0.86, 0.80)


def _place_legend(ax, n_entries: int, *, publication: bool = False) -> None:
    """Place the legend OUTSIDE the axes (right side) so it never overlaps
    the title. Falls back to two columns when there are many species."""
    if n_entries <= 0:
        return
    fontsize = 10 if publication else 7
    threshold = _PUB_2COL_THRESHOLD if publication else 16
    ncol = 2 if n_entries > threshold else 1
    ax.legend(fontsize=fontsize, ncol=ncol, loc="center left",
              bbox_to_anchor=(1.01, 0.5), borderaxespad=0.0,
              framealpha=0.9)


def _finalize(fig, ax, save_path, publication: bool, *,
              side_legend: bool, n_entries: int = 0) -> None:
    """Lay out and save.  Publication mode pins the data area and writes a
    fixed canvas so the enlarged legend keeps the image size unchanged."""
    if publication:
        if not side_legend:
            rect = _PUB_RECT_FULL
        elif n_entries > _PUB_2COL_THRESHOLD:
            rect = _PUB_RECT_SIDE_2COL
        else:
            rect = _PUB_RECT_SIDE_1COL
        ax.set_position(rect)
    else:
        fig.tight_layout()
    if save_path:
        save_kwargs = {} if publication else {"bbox_inches": "tight"}
        # long_path: basis-species prefixes can push the full UNC path past
        # MAX_PATH (267 chars observed, L2_1 2026-09-06) -> PIL FileNotFoundError.
        fig.savefig(long_path(save_path), dpi=150, **save_kwargs)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Fraction diagram
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def plot_fraction(
    curve: SpeciationCurve,
    component: str = "M",
    *,
    min_frac: float = 0.01,
    title: str | None = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Path | str | None = None,
    publication: bool = False,
) -> Any:
    """Plot species fraction vs pH for one component ("M" or "L")."""
    _assert_mpl()
    fig, ax = plt.subplots(figsize=figsize)
    pH = curve.pH_values
    kind = "frac_M" if component == "M" else "frac_L"

    sp_styles = _assign_styles(curve.species)
    plotted = []
    for sp_id, sp in curve.species.items():
        if _is_solvent_species(sp):
            continue
        vals = curve.series(sp_id, kind)
        if max(vals) < min_frac:
            continue
        color, ls, lw = sp_styles.get(sp_id, ("#333333", "-", 1.8))
        ax.plot(pH, vals, color=color, ls=ls, lw=lw, label=_safe_label(sp.label))
        plotted.append(sp_id)

    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("pH", fontsize=12)
    ylabel = "Fraction of total metal" if component == "M" else "Fraction of total ligand"
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title or _safe_label(
        f"Speciation: {_system_display_title(curve)} ({component})"),
        fontsize=13)
    ax.grid(True, alpha=0.25)
    _place_legend(ax, len(plotted), publication=publication)
    _finalize(fig, ax, save_path, publication, side_legend=True,
              n_entries=len(plotted))
    return fig


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Log-concentration diagram
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def plot_log_conc(
    curve: SpeciationCurve,
    *,
    min_log: float = -12.0,
    title: str | None = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Path | str | None = None,
    publication: bool = False,
) -> Any:
    """Plot log10[species] vs pH."""
    _assert_mpl()
    fig, ax = plt.subplots(figsize=figsize)
    pH = curve.pH_values

    sp_styles = _assign_styles(curve.species)
    n_plotted = 0
    for sp_id, sp in curve.species.items():
        if _is_solvent_species(sp):
            continue
        vals = _log_concentration_plot_values(curve, sp_id, sp)
        finite = [v for v in vals if not math.isnan(v)]
        if not finite or max(finite) < min_log:
            continue
        color, ls, lw = sp_styles.get(sp_id, ("#333333", "-", 1.8))
        ax.plot(pH, vals, color=color, ls=ls, lw=lw, label=_safe_label(sp.label))
        if getattr(sp, "phase", "aqueous") == "solid":
            _draw_solid_phase_edges(ax, pH, vals, min_log, color, lw)
        n_plotted += 1

    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(min_log, 0)
    ax.set_xlabel("pH", fontsize=12)
    ax.set_ylabel("log\u2081\u2080 [species]  (mol/L)", fontsize=12)
    ax.set_title(title or _safe_label(
        f"Log-concentration: {_system_display_title(curve)}"),
        fontsize=13)
    ax.grid(True, alpha=0.25)
    _place_legend(ax, n_plotted, publication=publication)
    _finalize(fig, ax, save_path, publication, side_legend=True,
              n_entries=n_plotted)
    return fig


def _component_phase_fraction_series(
    curve: SpeciationCurve,
    component_id: str,
) -> Tuple[List[float], List[float], List[float]]:
    """Return aqueous, solid, and closure fractions for one metal balance.

    These are stoichiometric component inventories, not sums of raw formula
    concentrations.  Consequently a multi-metal or multi-metal-atom species
    contributes the same coefficient used by the solver mass balance.
    """

    aqueous: List[float] = []
    solid: List[float] = []
    closure: List[float] = []
    for result in curve.results:
        if not getattr(result, "converged", True):
            aqueous.append(float("nan"))
            solid.append(float("nan"))
            closure.append(float("nan"))
            continue
        fractions = (getattr(result, "frac_metals", {}) or {}).get(
            component_id, {})
        aq_value = 0.0
        solid_value = 0.0
        for sp_id, value in fractions.items():
            sp = curve.species.get(sp_id)
            if sp is not None and getattr(sp, "phase", "aqueous") == "solid":
                solid_value += float(value)
            else:
                aq_value += float(value)
        aqueous.append(aq_value)
        solid.append(solid_value)
        closure.append(aq_value + solid_value)
    return aqueous, solid, closure


def plot_component_phase_balance(
    curve: SpeciationCurve,
    component_id: str,
    *,
    title: str | None = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Path | str | None = None,
    publication: bool = False,
) -> Any:
    """Plot the mass-conserving aqueous/solid split of one metal component.

    The ordinary log-concentration diagram shows individual species.  This
    companion view makes the conserved inventory explicit by summing all
    aqueous species and all solids with their metal stoichiometric weights.
    """

    _assert_mpl()
    aqueous, solid, closure = _component_phase_fraction_series(
        curve, component_id)
    pH = curve.pH_values
    display_name = curve.metal_names.get(component_id, component_id)

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(pH, aqueous, color="#1f77b4", lw=2.8,
            label=_safe_label(f"Σ aqueous {display_name}"))
    ax.plot(pH, solid, color="#8b0000", lw=2.8,
            label=_safe_label(f"Σ solid-bound {display_name}"))
    ax.plot(pH, closure, color="#222222", lw=1.4, ls="--",
            label="mass-balance closure")
    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(0.0, 1.05)
    ax.set_xlabel("pH", fontsize=12)
    ax.set_ylabel(f"Fraction of total {display_name}", fontsize=12)
    ax.set_title(
        title or _safe_label(
            f"Aqueous/solid inventory: {_system_display_title(curve)} "
            f"({display_name})"),
        fontsize=13,
    )
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=(11 if publication else 9), loc="best")
    _finalize(fig, ax, save_path, publication, side_legend=False)
    return fig


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Multi-component fraction diagram
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def plot_multi_fraction(
    curve: SpeciationCurve,
    component_id: str,
    *,
    min_frac: float = 0.01,
    title: str | None = None,
    figsize: Tuple[float, float] = (10, 6),
    save_path: Path | str | None = None,
    publication: bool = False,
) -> Any:
    """Plot fraction vs pH for one metal or ligand in a multi-component system."""
    _assert_mpl()
    fig, ax = plt.subplots(figsize=figsize)
    pH = curve.pH_values

    is_metal = component_id in curve.metal_names
    comp_name = (curve.metal_names.get(component_id)
                 or curve.ligand_names.get(component_id, component_id))

    sp_styles = _assign_styles(curve.species)
    plotted = []
    for sp_id, sp in curve.species.items():
        if _is_solvent_species(sp):
            continue
        vals = curve.series_multi(sp_id, component_id)
        if max(vals) < min_frac:
            continue
        color, ls, lw = sp_styles.get(sp_id, ("#333333", "-", 1.8))
        ax.plot(pH, vals, color=color, ls=ls, lw=lw, label=_safe_label(sp.label))
        plotted.append(sp_id)

    ax.set_xlim(min(pH), max(pH))
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("pH", fontsize=12)
    ylabel = f"Fraction of total {_safe_label(comp_name)}"
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title or _safe_label(
        f"Speciation: {_system_display_title(curve)} \u2014 {comp_name}"),
        fontsize=13)
    ax.grid(True, alpha=0.25)
    _place_legend(ax, len(plotted), publication=publication)
    _finalize(fig, ax, save_path, publication, side_legend=True,
              n_entries=len(plotted))
    return fig
