"""
nernst_simple_main.py
=====================
Sweep orchestration for the Nernst simple mode (Layer 4).
Separated from ``nernst_simple_export.py`` to keep solver/orchestration
logic apart from output/plotting concerns.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple


# ── Registry metadata ────────────────────────────────────────

SWEEP_ID = "nernst_simple"
SWEEP_DESCRIPTION = (
    "Quick Nernst E vs pH: uses a 257-entry E° table and the "
    "Nernst equation. Optionally couples to a speciation curve "
    "for complexation-corrected potentials."
)
SWEEP_PARAMS = {
    "metal":        {"type": "str",   "default": "",
                     "help": "Metal symbol (e.g. 'Cu')"},
    "oxidised":     {"type": "str",   "default": "",
                     "help": "Oxidised species formula"},
    "reduced":      {"type": "str",   "default": "",
                     "help": "Reduced species formula"},
    "total_metal":  {"type": "float", "default": 1e-3,
                     "help": "Total metal concentration (mol/L)"},
    "pH_range":     {"type": "tuple", "default": (0.0, 14.0),
                     "help": "(pH_min, pH_max)"},
    "n_points":     {"type": "int",   "default": 141,
                     "help": "Number of pH grid points"},
    "temperature":  {"type": "float", "default": 25.0,
                     "help": "Temperature in °C"},
}


# ══════════════════════════════════════════════════════════════
#  Sweep function (registry callable)
# ══════════════════════════════════════════════════════════════

def sweep_fn(
    *,
    couple=None,
    metal: str = "",
    oxidised: str = "",
    reduced: str = "",
    speciation_curve=None,
    total_metal: float = 1e-3,
    pH_range: Tuple[float, float] = (0.0, 14.0),
    n_points: int = 141,
    temperature: float = 25.0,
    activity_red: float = 1.0,
    mode: str = "auto",
    output_dir: Optional[str] = None,
    debug: bool = False,
):
    """Run a Nernst E-vs-pH calculation.

    If ``couple`` is not given, looks up by metal/oxidised/reduced.
    Returns (NernstCurve, output_paths).
    """
    from .nernst_core import lookup_e0, compute_nernst_curve as _compute

    if couple is None:
        hits = lookup_e0(oxidised=oxidised, reduced=reduced, metal=metal)
        if not hits:
            raise ValueError(
                f"No E° entry found for metal={metal!r}, "
                f"ox={oxidised!r}, red={reduced!r}")
        couple = hits[0]

    pH_vals = [pH_range[0] + i * (pH_range[1] - pH_range[0]) / max(n_points - 1, 1)
               for i in range(n_points)]

    curve = _compute(
        couple=couple,
        speciation_curve=speciation_curve,
        total_metal=total_metal,
        pH_values=pH_vals,
        temperature=temperature,
        activity_red=activity_red,
        mode=mode,
    )

    output_paths: List[str] = []
    if output_dir:
        from .nernst_simple_export import export_csv, plot_e_vs_ph
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        safe = couple.metal.replace(" ", "_")
        csv_p = export_csv(curve, out / f"nernst_{safe}.csv")
        output_paths.append(str(csv_p))
        img_p = plot_e_vs_ph(curve, output_path=out / f"nernst_{safe}.png")
        if img_p:
            output_paths.append(str(img_p))

    return curve, output_paths
