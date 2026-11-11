"""
topology_nd — Unified N-D topology extraction (bottom-up).

Extracts topology features from a labelled NDGrid in dimension order:
0-D junctions → (N-1)-D boundaries → N-D regions.
"""

from .topology_nd import extract_topology_nd

__all__ = ["extract_topology_nd"]
