"""
settings.py
===========
Configurable parameters for the N-D grid solver, retry strategies,
labelling, and boundary refinement.

Extracted from ``solver_settings.py`` (formerly ``pourbaix_settings.py``).  Parameters specific to
a single sweep type (pH range defaults, output DPI, ...) stay in the
respective ``sweep_pipelines/*/settings.py`` modules.
"""

# ── Newton-Raphson solver ────────────────────────────────────
NEWTON_TOL          = 1e-10
NEWTON_MAX_ITER     = 300
DAMPING_INITIAL     = 1.0
BACKTRACK_MAX       = 15
FALLBACK_STEP       = 0.1          # steepest-descent fallback factor
MIN_LOG             = -300.0       # lower bound on log10(conc) unknowns
MAX_LOG             = 5.0          # upper bound on log10(conc) unknowns
MULTI_START_N       = 3            # cold-start attempts on failure

# ── Per-point timeout ────────────────────────────────────────
POINT_TIMEOUT_S     = 5.0          # wall-clock seconds per grid point

# ── Seed discovery ───────────────────────────────────────────
SEED_SCAN_TIMEOUT_S = 0.1          # very short timeout for seed probing
SEED_SCAN_STRIDE    = 5            # grid stride for coarse scan fallback

# ── Retry strategies ─────────────────────────────────────────
BACKSCAN_MAX_PASSES         = 20   # max neighbor-retry passes
DEEP_RETRY_TIMEOUT_FACTOR   = 3    # timeout multiplier for interpolation
DEEP_RETRY_RADIUS           = 2    # neighbor search radius (in grid cells)

# ── Levenberg-Marquardt / trust-region ───────────────────────
LM_LAMBDA_INIT      = 1e-4
LM_LAMBDA_MIN       = 1e-12
LM_LAMBDA_MAX       = 1e8
LM_GAIN_GOOD        = 0.75
LM_GAIN_POOR        = 0.25
LM_FACTOR_UP        = 10.0
LM_FACTOR_DOWN      = 0.1
ARMIJO_C1           = 1e-4
JACOBIAN_EQUIL      = True

# ── Solid management ────────────────────────────────────────
SI_THRESHOLD        = 1e-6
ACTIVE_SET_MAX      = 15
SOLID_AMOUNT_TOL    = 1e-15

# ── Activity model ──────────────────────────────────────────
USE_ACTIVITY        = True
IONIC_MODE          = "fixed"      # "fixed" or "auto"
FIXED_I             = 0.0
INERT_ION_CONC      = 0.0
DAVIES_A            = 0.5085
AUTO_I_MAX_ITER     = 12
AUTO_I_TOL          = 1e-6

# ── Labelling ───────────────────────────────────────────────
LABEL_TOL           = 1e-3         # min fraction gap for dominance call
LABEL_SOLID_TOL     = 1e-12        # min n_s to consider solid "present"
LABEL_MODE          = "PER_ELEMENT"

# ── Boundary refinement ────────────────────────────────────
REFINE_FACTOR       = 3            # sub-grid factor per refinement layer
REFINE_LAYERS       = 2            # cascaded refinement layers
BISECTION_MAX       = 30           # max bisection iterations
BISECTION_TOL       = 1e-4         # default tolerance (all axes)

# ── Debug ───────────────────────────────────────────────────
DEBUG               = True
