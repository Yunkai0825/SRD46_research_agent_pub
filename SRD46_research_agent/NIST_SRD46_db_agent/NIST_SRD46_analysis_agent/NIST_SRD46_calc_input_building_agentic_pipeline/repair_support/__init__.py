"""Bounded source repair; no model calls occur on import."""
from .contracts import SourceRepairRequired, BroaderReviewRequired, DEFAULT_MAX_REPAIR_ATTEMPTS


def repair_lc2_from_delta(**kwargs):
    from .lc2_delta import repair_lc2_from_delta as run
    return run(**kwargs)

__all__ = ["SourceRepairRequired", "BroaderReviewRequired", "DEFAULT_MAX_REPAIR_ATTEMPTS", "repair_lc2_from_delta"]
