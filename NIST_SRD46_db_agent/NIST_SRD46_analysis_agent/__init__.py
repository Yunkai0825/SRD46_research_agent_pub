"""NIST SRD-46 analysis agent package.

Sibling of ``NIST_SRD46_query_agent``. Hardcoded Python pipeline drives a
fixed S1-S8 phase sequence over the calc tools in
``NIST_SRD46_core_calc_tools``. See ``ARCHITECTURE.md`` (TBD) for the
full design and ``SRD46_analysis_api.py`` for the public entry point.
"""

from typing import TYPE_CHECKING, Any

# NOTE: importing ``SRD46_analysis_run`` eagerly drags in the entire
# ``analysis_agent_orchestration`` pipeline (L0→L1→L2_card_assembler).
# That orchestration half is independent of — and currently mid-refactor
# relative to — the ``NIST_SRD46_calc_input_building_agentic_pipeline``
# half.  A broken/incomplete module there must NOT take down the whole
# package (it would block importing the calc-input-building API).  So the
# symbol is exposed lazily: it resolves on first attribute access and
# raises only if it is genuinely needed.
if TYPE_CHECKING:                                    # pragma: no cover
    from .SRD46_analysis_api import SRD46_analysis_run

__all__ = ["SRD46_analysis_run"]


def __getattr__(name: str) -> Any:                   # PEP 562
    if name == "SRD46_analysis_run":
        from .SRD46_analysis_api import SRD46_analysis_run as _run
        return _run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
