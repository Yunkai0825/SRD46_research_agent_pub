"""
solver_settings.py
==================
Single file holding every configurable parameter for the equilibrium
solver pipeline (speciation, Pourbaix, and multi-axis sweeps).

Imported by all solver modules.

Renamed from ``pourbaix_settings.py``.
"""

import math

# -- Grid ---------------------------------------------------------
PH_RANGE          = (0.0, 14.0)
E_RANGE_V         = (-1.0, 1.5)
COARSE_N_PH       = 500
COARSE_N_E        = 500
REFINE_FACTOR     = 3           # sub-grid factor per refinement layer
REFINE_LAYERS     = 2           # number of cascaded refinement layers

# -- Solver -------------------------------------------------------
NEWTON_TOL        = 1e-10
NEWTON_MAX_ITER   = 300
DAMPING_INITIAL   = 1.0
BACKTRACK_MAX     = 15
FALLBACK_STEP     = 0.1        # steepest-descent fallback factor
MIN_LOG           = -300.0       # lowered from -99 so x can reach extreme redox solutions
MAX_LOG           = 5.0
MULTI_START_N     = 3           # number of cold-start attempts on failure
POINT_TIMEOUT_S   = 5.0         # wall-clock timeout per grid point (seconds)
SEED_SCAN_TIMEOUT_S = 0.1       # very short timeout for seed-finding scan
SEED_SCAN_STRIDE  = 5           # grid stride for coarse scan fallback
BACKSCAN_MAX_PASSES = 20        # max neighbor-retry passes for unconverged pts
DEEP_RETRY_TIMEOUT_FACTOR = 3   # timeout multiplier for interpolation retry
DEEP_RETRY_RADIUS = 2           # neighbor search radius for interpolation retry

# -- Levenberg-Marquardt / trust-region ---------------------------
LM_LAMBDA_INIT    = 1e-4        # initial LM damping parameter
LM_LAMBDA_MIN     = 1e-12       # floor (essentially pure Newton)
LM_LAMBDA_MAX     = 1e8         # ceiling (essentially gradient descent)
LM_GAIN_GOOD      = 0.75        # gain ratio threshold: reduce lambda
LM_GAIN_POOR      = 0.25        # gain ratio threshold: increase lambda
LM_FACTOR_UP      = 10.0        # lambda multiplier on poor gain
LM_FACTOR_DOWN    = 0.1         # lambda multiplier on good gain
ARMIJO_C1         = 1e-4        # sufficient decrease constant
JACOBIAN_EQUIL    = True        # enable row/column equilibration

# -- Solid management --------------------------------------------
SI_THRESHOLD      = 1e-6
ACTIVE_SET_MAX    = 15
SOLID_AMOUNT_TOL  = 1e-15

# -- Temperature & thermodynamics --------------------------------
# Single source of truth: support_TD_helpers/TD_constants_entry_point.py.
# Re-exported here so callers can keep doing ``from solver_settings
# import NERNST_FACTOR`` etc. without reaching into thermodynamics_helpers.
from support_TD_helpers.TD_constants_entry_point import (  # noqa: E402,F401
    TEMPERATURE_C, TEMPERATURE_K,
    NERNST_FACTOR, Kw_LOG,
    F_CONST, R_CONST, LN10,
)

# -- Activity model -----------------------------------------------
USE_ACTIVITY      = True
IONIC_MODE        = "fixed"     # "fixed" or "auto"
FIXED_I           = 0.0         # ionic strength for fixed mode (0 = ideal)
INERT_ION_CONC    = 0.0         # background 1:1 electrolyte conc (mol/L, auto mode)
DAVIES_A          = 0.5085
AUTO_I_MAX_ITER   = 12
AUTO_I_TOL        = 1e-6

# -- Labelling ----------------------------------------------------
LABEL_TOL         = 1e-3        # min fraction gap to call dominance
LABEL_SOLID_TOL   = 1e-12       # min n_s to consider solid "present"
LABEL_MODE        = "PER_ELEMENT"  # "COMBINED" or "PER_ELEMENT"

# -- Boundary detection -------------------------------------------
BISECTION_MAX     = 30          # max bisection steps for boundary loc.
BISECTION_TOL_PH  = 1e-4
BISECTION_TOL_E   = 1e-5

# -- Topology fixer (raw -> fixed second pass) --------------------
# Extraction is rule-free; the fixer analyzes the raw topology and the
# raster, resolves below-resolution fragments ("orphans") by marking
# cells (rejoin to their body, dissolve into a neighbour, or keep and
# flag), and the second pass extracts the fixed topology from the
# resulting effective label map (the deep-merged grid).
TOPO_FIX_ENABLE   = True        # analyze the raw 2-D topology and emit a fixed solution
TOPO_FIX_TOLERANCE = None       # per-axis trust, e.g. {"pH": 0.2, "E_V": 0.05}; None = TOPO_FIX_TOLERANCE_FACTOR coarse cells
TOPO_FIX_TOLERANCE_FACTOR = 1.5  # multiplies the automatic one-cell trust radius (explicit TOPO_FIX_TOLERANCE is exact, never scaled); trust = detection-range half-width around junction clusters and the bridge reach
TOPO_FIX_TOLERANCE_SCALE = True  # True: trust stays one COARSE cell, spanning more refined steps at each layer; False: one cell of the current raster
TOPO_FIX_BAND_DEPTH = 2         # confine fix evidence to the label-boundary band: depth 1 = every cell incident to a vertex of a label-changing facet (the refiner's own rule, corner cells included), each further step one 8-connected ring (0/None = unconfined)
TOPO_FIX_ORPHAN_CELL_FACTOR = 1.0  # a component with fewer raster cells than this many coarse cells is below resolution (an orphan) when it does not touch the rim; without a coarse grid the trust radius stands in for the coarse cell

# -- Simplification -----------------------------------------------
RDP_EPSILON       = 0.01        # Douglas-Peucker tolerance (legacy fallback when grid spacing is unavailable)
RDP_ENVELOPE_N    = 6           # max number of control points for RDP envelope spline
RDP_TAU_NORM_FACTOR = 1.01      # resolution stop: tau = factor x normalized effective-cell diagonal
RDP_MIN_LOOP_FACTOR = 1.01      # protect closed loops whose span on any axis < factor x coarse cell size
RDP_LOOP_MIN_POINTS = 4         # minimum control points for any protected closed loop

# -- Output -------------------------------------------------------
OUTPUT_DPI        = 200
OUTPUT_FORMAT     = "png"

# -- Debug --------------------------------------------------------
DEBUG             = True        # master debug flag (enables verbose prints)
