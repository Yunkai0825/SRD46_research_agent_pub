"""LC1_1 — Chemical-system ID alignment (agent + deterministic enrichment).

Module split:

* :mod:`.LC1_1_subagent`        — LLM ReAct loop, tool plumbing,
  session state, public ``align_chemical_system`` entry point.
* :mod:`.id_enrichment_helpers` — pure-Python, DB-row enrichment
  (``build_system_catalog``, etc.) re-usable by any layer that already
  has canonical ``metal_<int>`` / ``ligand_<int>`` IDs.
"""

from .LC1_1_ID_alignment_subagent import (
    align_chemical_system,
    configure_lc1_1_session,
)
from .id_enrichment_helpers import build_system_catalog

__all__ = [
    "align_chemical_system",
    "configure_lc1_1_session",
    "build_system_catalog",
]
