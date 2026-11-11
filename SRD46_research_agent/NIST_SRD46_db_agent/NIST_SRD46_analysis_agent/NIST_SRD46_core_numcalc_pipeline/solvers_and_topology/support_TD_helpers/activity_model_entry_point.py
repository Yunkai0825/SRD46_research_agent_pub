"""
activity_model_entry_point.py
=============================
Sole gateway through which `solvers_and_topology` reaches the
activity-coefficient framework defined in
`thermodynamics_helpers/electrolyte_activity_models/activity_model.py`.

Rule
----
No code inside `solvers_and_topology/` may import directly from
`thermodynamics_helpers.electrolyte_activity_models`.  Activity-model
functions must come through this module.

Re-exported names
-----------------
Wildcard re-export of everything `activity_model` exposes, plus
explicit re-exports of the two functions consumed by `SolidManager`:
`compute_ionic_strength` and `recompute_activity_at_I`.
"""

from __future__ import annotations

import sys
import pathlib

# Make `thermodynamics_helpers` importable when this package is
# loaded with `solvers_and_topology` on sys.path.
_calc_root = pathlib.Path(__file__).absolute().parents[2]
if str(_calc_root) not in sys.path:
    sys.path.insert(0, str(_calc_root))

from thermodynamics_helpers.electrolyte_activity_models.activity_model import *  # noqa: E402,F401,F403
from thermodynamics_helpers.electrolyte_activity_models.activity_model import (  # noqa: E402,F401
    compute_ionic_strength,
    recompute_activity_at_I,
)
