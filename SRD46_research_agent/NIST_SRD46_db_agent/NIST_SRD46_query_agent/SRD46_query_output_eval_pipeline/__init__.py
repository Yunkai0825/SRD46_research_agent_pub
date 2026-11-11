"""Query evaluation package, including standalone launches from the query folder."""

import sys
from pathlib import Path

_SRD46_ROOT = Path(__file__).absolute().parents[3]
if str(_SRD46_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRD46_ROOT))

from .models import EntityRef, ResultDoc, RunArtifacts, ToolCall

__all__ = [
    "EntityRef",
    "ResultDoc",
    "RunArtifacts",
    "ToolCall",
]
