"""
nernst_simple_export.py
=======================
Output functions for the Nernst simple mode: CSV export, plotting,
and markdown summary (Layer 5).

Sweep orchestration has been moved to ``nernst_simple_main.py``.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ── Re-export registry metadata from main (for backward compat) ──
from .nernst_simple_main import SWEEP_ID, SWEEP_DESCRIPTION, SWEEP_PARAMS, sweep_fn


# ══════════════════════════════════════════════════════════════
#  Master output generator
# ══════════════════════════════════════════════════════════════


def generate_all_output(curve, output_dir, **kwargs):
    """Master output generator for Nernst results."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: List[str] = []
    safe = curve.couple.metal.replace(" ", "_")
    csv_p = export_csv(curve, out / f"nernst_{safe}.csv")
    paths.append(str(csv_p))
    img_p = plot_e_vs_ph(curve, output_path=out / f"nernst_{safe}.png")
    if img_p:
        paths.append(str(img_p))
    return paths


# ══════════════════════════════════════════════════════════════
#  CSV export
# ══════════════════════════════════════════════════════════════

def export_csv(curve, output_path=None) -> Path:
    """Write Nernst E vs pH data to CSV."""
    if output_path is None:
        output_path = Path("nernst_data.csv")
    output_path = Path(output_path)
    with open(str(output_path), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pH", "E_V_vs_SHE", "free_ox_M",
                     "free_red_M", "alpha_ox", "ln_Q"])
        for pt in curve.points:
            w.writerow([
                f"{pt.pH:.4f}",
                f"{pt.E_V:.6f}",
                f"{pt.free_ox_M:.6e}",
                f"{pt.free_red_M:.6e}",
                f"{pt.alpha_ox:.6f}",
                f"{pt.ln_Q:.6f}",
            ])
    return output_path


def export_formal_csv(formal_data, output_path=None) -> Path:
    """Write formal-potential data to CSV."""
    if output_path is None:
        output_path = Path("formal_potential.csv")
    output_path = Path(output_path)
    with open(str(output_path), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pH", "E_formal_V", "alpha_ox"])
        for d in formal_data:
            w.writerow([f"{d['pH']:.4f}",
                         f"{d['E_formal_V']:.6f}",
                         f"{d['alpha_ox']:.6f}"])
    return output_path


# ══════════════════════════════════════════════════════════════
#  Plotting
# ══════════════════════════════════════════════════════════════

def plot_e_vs_ph(
    curve,
    *,
    show_water: bool = True,
    title: str = "",
    output_path=None,
):
    """Plot E (V vs SHE) vs pH with optional water stability window."""
    if not HAS_MPL:
        return None
    from .nernst_core import water_stability_lines

    fig, ax = plt.subplots(figsize=(8, 5))
    phs = curve.pH_values
    E_vs = curve.E_series()

    ax.plot(phs, E_vs, "b-", linewidth=2,
            label=f"{curve.couple.reaction}")

    if show_water:
        e_h2, e_o2 = water_stability_lines(phs, curve.temperature)
        ax.plot(phs, e_h2, "k--", linewidth=0.8, alpha=0.5, label="H\u2082/H\u207a")
        ax.plot(phs, e_o2, "k--", linewidth=0.8, alpha=0.5, label="O\u2082/H\u2082O")
        ax.fill_between(phs, e_h2, e_o2, alpha=0.05, color="grey")

    ax.set_title(title or f"E vs pH \u2014 {curve.system_name}", fontsize=12)
    ax.set_xlabel("pH", fontsize=11)
    ax.set_ylabel("E (V vs SHE)", fontsize=11)
    ax.legend(fontsize=9, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_path is None:
        output_path = Path("E_vs_pH.png")
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    return output_path


def plot_e_vs_ph_multi(
    curves,
    *,
    show_water: bool = True,
    title: str = "E vs pH \u2014 Multiple Couples",
    output_path=None,
):
    """Overlay multiple E vs pH curves on one figure."""
    if not HAS_MPL or not curves:
        return None
    from .nernst_core import water_stability_lines

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = plt.cm.tab10.colors

    for i, curve in enumerate(curves):
        c = colors[i % len(colors)]
        ax.plot(curve.pH_values, curve.E_series(),
                color=c, linewidth=1.8,
                label=curve.couple.reaction[:40])

    if show_water and curves:
        phs = curves[0].pH_values
        e_h2, e_o2 = water_stability_lines(phs, curves[0].temperature)
        ax.plot(phs, e_h2, "k--", linewidth=0.8, alpha=0.4, label="H\u2082/H\u207a")
        ax.plot(phs, e_o2, "k--", linewidth=0.8, alpha=0.4, label="O\u2082/H\u2082O")
        ax.fill_between(phs, e_h2, e_o2, alpha=0.04, color="grey")

    ax.set_title(title, fontsize=12)
    ax.set_xlabel("pH", fontsize=11)
    ax.set_ylabel("E (V vs SHE)", fontsize=11)
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_path is None:
        output_path = Path("E_vs_pH_multi.png")
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    return output_path


def plot_formal_potential(
    formal_data,
    couple_label: str = "",
    *,
    output_path=None,
):
    """Plot formal (conditional) potential E°' vs pH."""
    if not HAS_MPL:
        return None

    phs = [d["pH"] for d in formal_data]
    efps = [d["E_formal_V"] for d in formal_data]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(phs, efps, "r-", linewidth=2, label="E\u00b0' (formal)")
    if formal_data:
        ax.axhline(y=formal_data[0]["E_formal_V"],
                    color="grey", linestyle=":", alpha=0.4, linewidth=0.8)

    title = "Formal potential E\u00b0' vs pH"
    if couple_label:
        title += f" \u2014 {couple_label}"
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("pH", fontsize=11)
    ax.set_ylabel("E\u00b0' (V vs SHE)", fontsize=11)
    ax.legend(fontsize=9, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if output_path is None:
        output_path = Path("E_formal_vs_pH.png")
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    return output_path


# ══════════════════════════════════════════════════════════════
#  Summary helpers
# ══════════════════════════════════════════════════════════════

def summarise_nernst(curve) -> str:
    """Markdown summary of a Nernst calculation."""
    lines = [
        "## Nernst Calculation Summary",
        "",
        f"**System:** {curve.system_name}",
        f"**Half-reaction:** {curve.couple.reaction}",
        f"**E\u00b0:** {curve.couple.e0_v:.4f} V vs SHE",
        f"**n electrons:** {curve.couple.n_electrons}",
        f"**Temperature:** {curve.temperature:.1f} \u00b0C",
        f"**Total metal:** {curve.total_metal:.2e} M",
        f"**Mode:** {curve.mode}",
        f"**Valid points:** {curve.valid_points()}/{len(curve.points)}",
        "",
    ]

    valid = [p for p in curve.points if math.isfinite(p.E_V)]
    if valid:
        e_min = min(valid, key=lambda p: p.E_V)
        e_max = max(valid, key=lambda p: p.E_V)
        lines.extend([
            "### Extremes",
            "| | pH | E (V) | \u03b1_Ox |",
            "|---|-----|-------|------|",
            f"| Min E | {e_min.pH:.1f} | {e_min.E_V:.4f} | {e_min.alpha_ox:.4f} |",
            f"| Max E | {e_max.pH:.1f} | {e_max.E_V:.4f} | {e_max.alpha_ox:.4f} |",
            "",
        ])

        key_phs = [0.0, 2.0, 4.0, 7.0, 9.0, 12.0, 14.0]
        lines.extend([
            "### E at key pH values",
            "| pH | E (V vs SHE) | \u03b1_Ox |",
            "|-----|-------------|------|",
        ])
        for target in key_phs:
            closest = min(valid, key=lambda p: abs(p.pH - target))
            if abs(closest.pH - target) < 0.2:
                lines.append(
                    f"| {closest.pH:.1f} | {closest.E_V:.4f} | {closest.alpha_ox:.4f} |")
        lines.append("")

    return "\n".join(lines)
