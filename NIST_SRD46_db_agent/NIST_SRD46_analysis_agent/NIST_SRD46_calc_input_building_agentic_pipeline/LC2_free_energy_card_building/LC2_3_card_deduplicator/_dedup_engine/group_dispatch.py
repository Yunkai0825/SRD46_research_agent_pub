"""
LC2_3 dedup — group dispatch (pre-LLM).
========================================

This is the *pre-LLM* half of the LC2_3 deterministic engine.  It takes
the parsed dedup report (a :class:`DedupReport` from LC2_2's
``deduplication_check.md``) and prepares it for the two LLM pathways:

* :func:`split_groups`     — partition groups into multi-member vs
  singleton, feeding the per-group and singleton-batch agents
  respectively.
* :func:`group_to_payload` — render one group as a JSON-serializable
  snapshot an LLM subagent can read.

No decisions are made here — see :mod:`.decision_apply` for the
*post-LLM* half that maps decisions back onto the card.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path as _Path
from typing import Any, Dict, Iterable, List, Tuple

# ── path bootstrap: import LC2's shared card-format helpers as a bare
#    top-level package (lives in the pipeline root), never via the heavy
#    NIST_SRD46_analysis_agent package __init__ chain. ──────────────────
_PIPELINE_ROOT = _Path(__file__).absolute().parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from card_management_helpers.dedup_md_card_reader import (
    DedupGroup,
    DedupReport,
)

log = logging.getLogger("Analysis.LC2_3.dispatch")


def split_groups(report: DedupReport) -> Tuple[List[DedupGroup], List[DedupGroup]]:
    """Partition the report's groups into ``(multi, singletons)`` where
    *multi* groups have >1 member and *singletons* have exactly one."""
    multi   = [g for g in report.groups if g.count > 1]
    singles = [g for g in report.groups if g.count == 1]
    return multi, singles


def group_to_payload(
    group: DedupGroup,
    inventory: Iterable[Any] = (),
) -> Dict[str, Any]:
    """JSON-serializable snapshot of a group for an LLM subagent.

    Element ownership is joined from LC2_2's explicit inventory, not inferred
    from the core label (which is unsafe for mixed-valence phases).
    """
    inventory_by_species = {
        entry.species_key: entry for entry in inventory
    }
    elements = sorted({
        element
        for species in group.species
        for element in getattr(
            inventory_by_species.get((species.name, species.source)),
            "elements", (),
        )
    })
    return {
        "phase":      group.phase,
        "core_label": group.core_label,
        "elements":   elements,
        "species": [
            {
                "name":          s.name,
                "source":        s.source,
                "charge":        s.charge,
                "mu_aligned_kJ": s.mu_aligned_kJ,
                "multiplier":    s.multiplier,
                "notes":         getattr(s, "notes", ""),
                "entry_key": getattr(
                    inventory_by_species.get((s.name, s.source)),
                    "entry_key", "",
                ),
                "phase_family": getattr(
                    inventory_by_species.get((s.name, s.source)),
                    "phase_family", group.phase,
                ),
            }
            for s in group.species
        ],
    }


__all__ = ["split_groups", "group_to_payload"]
