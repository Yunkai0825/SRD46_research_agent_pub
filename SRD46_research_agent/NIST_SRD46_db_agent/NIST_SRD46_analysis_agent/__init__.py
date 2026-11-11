"""NIST SRD-46 analysis agent package.

Sibling of ``NIST_SRD46_query_agent``. Hardcoded Python pipeline drives a
fixed S1-S8 phase sequence over the calc tools in
``NIST_SRD46_core_calc_tools``. See ``ARCHITECTURE.md`` (TBD) for the
full design and ``SRD46_analysis_api.py`` for the public entry point.
"""

from typing import TYPE_CHECKING, Any

# Expose SRD46_analysis_run lazily so importing the calc-input-building
# API does not also import analysis_agent_orchestration. The orchestration
# dependencies resolve on first attribute access, and import failures are
# raised only when that entry point is requested.
if TYPE_CHECKING:                                    # pragma: no cover
    from .SRD46_analysis_api import SRD46_analysis_run

__all__ = ["SRD46_analysis_run"]


def __getattr__(name: str) -> Any:                   # PEP 562
    if name == "SRD46_analysis_run":
        from .SRD46_analysis_api import SRD46_analysis_run as _run
        return _run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
