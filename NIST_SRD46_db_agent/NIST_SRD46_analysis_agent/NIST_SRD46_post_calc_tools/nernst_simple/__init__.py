"""
nernst_simple — Quick Nernst equation E vs pH calculator.
===========================================================
Fast-path mode that bypasses the full numerical speciation solver.
Uses a built-in 257-entry standard reduction potential table.

Provides:
  - ``compute_nernst_curve()``    — E vs pH (with or without speciation)
  - ``compute_formal_potential()``— conditional E°' vs pH
  - ``lookup_e0()``               — table lookup
  - ``list_couples()``            — list available redox couples
  - ``water_stability_lines()``   — H₂/O₂ boundary lines
  - ``plot_e_vs_ph()``            — single/multi curve plotting
  - ``export_nernst_csv()``       — CSV export

The E° data is imported from the legacy ``nernst_core`` module.
"""
from __future__ import annotations

# The 257-entry E° table is vendored alongside this package (nernst_core.py).
from .nernst_core import (
    RedoxCouple,
    NernstPoint,
    NernstCurve,
    _E0_TABLE,
    lookup_e0,
    list_couples,
    list_available_metals,
    compute_nernst_curve,
    compute_formal_potential,
    water_stability_lines,
    F_CONST,
    R_CONST,
    LN10,
)

from .nernst_simple_export import (               # noqa: E402
    SWEEP_ID, SWEEP_DESCRIPTION, SWEEP_PARAMS, sweep_fn,
    generate_all_output, export_csv, plot_e_vs_ph,
)
