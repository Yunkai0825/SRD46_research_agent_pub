"""
pH Sweep Settings — defaults and constants for pH sweep method.
===============================================================
"""

# Default pH range
DEFAULT_PH_MIN = 0.0
DEFAULT_PH_MAX = 14.0
DEFAULT_N_POINTS = 141

# Retry parameters for non-converged segments
MAX_RETRY_SWEEPS = 3

# Auto ionic-strength iteration
MAX_OUTER_IONIC = 12
IONIC_TOL = 1e-6
