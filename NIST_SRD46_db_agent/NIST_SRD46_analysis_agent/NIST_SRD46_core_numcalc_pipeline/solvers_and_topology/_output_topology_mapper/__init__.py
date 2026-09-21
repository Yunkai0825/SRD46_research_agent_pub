"""
topology_output_mapper — Downstream topology extraction and annotation
======================================================================

Dispatches to dimension-specific topology extractors (1D, 2D).
Separated from grid refinement since this is post-processing.
"""

from .topology_dispatcher import extract_topology

__all__ = ["extract_topology"]
