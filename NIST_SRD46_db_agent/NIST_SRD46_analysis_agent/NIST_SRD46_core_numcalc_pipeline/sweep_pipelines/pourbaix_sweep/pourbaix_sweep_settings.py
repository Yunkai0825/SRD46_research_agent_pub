"""
pourbaix_sweep_settings.py
==========================
Legacy grid constants and non-card algorithmic settings for the unified N-D
Pourbaix sweep.  Calculation-card axes and refinement policy are explicit;
these constants are not refinement fallbacks for ``run_pourbaix_sweep``.

Currently supports 1-D (single axis), 2-D (E vs pH) and 3-D (E vs pH
vs a_w) Pourbaix grids.
"""

# ── Grid ──────────────────────────────────────────────────────
PH_RANGE            = (0.0, 14.0)
E_RANGE_V           = (-1.0, 1.5)
AW_RANGE            = (0.7, 1.0)            # 3-D water-activity axis
COARSE_N_PH         = 500
COARSE_N_E          = 500
COARSE_N_AW         = 3                     # 3-D water-activity axis

# ── Solver ────────────────────────────────────────────────────
POINT_TIMEOUT_S     = 5.0

# ── Output ────────────────────────────────────────────────────
OUTPUT_DPI          = 200
OUTPUT_FORMAT       = "png"
RDP_ENVELOPE_N      = 6

# ── Debug ─────────────────────────────────────────────────────
DEBUG               = True
