"""Query-assisted, session-local equilibrium estimation.

The package is imported only after the default-false estimation gate resolves
true.  Its public entry point is the main LC1_3 sequencing orchestrator.
"""

from __future__ import annotations

import os


# The mandated LC1_3 location is deep enough that its stage-local support
# modules cross the legacy Windows MAX_PATH boundary.  Put an extended-path
# spelling first in this package's search path before importing any stage.
if os.name == "nt":
    _package_dir = os.path.abspath(os.path.dirname(__file__))
    _extended = (
        "\\\\?\\UNC\\" + _package_dir[2:]
        if _package_dir.startswith("\\\\")
        else "\\\\?\\" + _package_dir
    )
    if _extended not in __path__:
        __path__.insert(0, _extended)

from .LC1_3_estimate_eq_stability_dispatch_orchestrator import (
    LC13Dependencies,
    LC13Result,
    build_default_lc1_3_dependencies,
    run_lc1_3,
)

__all__ = [
    "LC13Dependencies",
    "LC13Result",
    "build_default_lc1_3_dependencies",
    "run_lc1_3",
]
