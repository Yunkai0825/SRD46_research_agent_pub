"""
thermodynamic_constants.py
==========================
Physical and thermodynamic constants used by the grid solver and
downstream modules.

Extracted from ``solver_settings.py`` (formerly ``pourbaix_settings.py``).
"""

import math

# ── Temperature (defaults, can be overridden per-run) ────────
TEMPERATURE_C     = 25.0
TEMPERATURE_K     = 298.15

# ── Fundamental constants ────────────────────────────────────
NERNST_FACTOR     = 0.05916         # RT ln10 / F at 25 degC  (V)
Kw_LOG            = -14.0           # log10(Kw) at 25 degC
F_CONST           = 96_485.332      # Faraday constant  (C mol-1)
R_CONST           = 8.314_462       # Gas constant      (J mol-1 K-1)
LN10              = math.log(10.0)
