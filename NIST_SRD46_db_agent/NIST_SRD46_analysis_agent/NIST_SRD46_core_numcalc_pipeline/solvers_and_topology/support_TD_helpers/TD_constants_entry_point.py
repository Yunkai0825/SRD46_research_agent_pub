"""
TD_constants_entry_point.py
===========================
Sole gateway through which ``solvers_and_topology`` reaches the
thermodynamic constants defined in
``thermodynamics_helpers/thermodynamic_constants.py``.

Rule
----
No code inside ``solvers_and_topology/`` may import directly from
``thermodynamics_helpers``.  All numerical / thermodynamic constants
must come through this module.

Re-exported symbols
-------------------
- ``TEMPERATURE_C``
- ``TEMPERATURE_K``
- ``NERNST_FACTOR``   — RT ln10 / F at 25 °C  (V)
- ``Kw_LOG``          — log10(Kw) at 25 °C
- ``F_CONST``         — Faraday constant  (C mol⁻¹)
- ``R_CONST``         — Gas constant      (J mol⁻¹ K⁻¹)
- ``LN10``            — natural log of 10
"""

from __future__ import annotations

import sys
import pathlib

# Make ``thermodynamics_helpers`` importable when this package is
# loaded with ``solvers_and_topology`` on sys.path (the standard
# invocation mode of the numcalc pipeline).
_calc_root = pathlib.Path(__file__).absolute().parents[2]
if str(_calc_root) not in sys.path:
    sys.path.insert(0, str(_calc_root))

from thermodynamics_helpers.thermodynamic_constants import (  # noqa: E402,F401
    TEMPERATURE_C,
    TEMPERATURE_K,
    NERNST_FACTOR,
    Kw_LOG,
    F_CONST,
    R_CONST,
    LN10,
)

__all__ = [
    "TEMPERATURE_C",
    "TEMPERATURE_K",
    "NERNST_FACTOR",
    "Kw_LOG",
    "F_CONST",
    "R_CONST",
    "LN10",
]
