"""Chemical-query normalization shared with the canonical database tools."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).absolute().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from NIST_SRD46_core_db_search_tools._normalization_helpers.chem_query import (
    normalize_chem_query,
)

__all__ = ["normalize_chem_query"]
