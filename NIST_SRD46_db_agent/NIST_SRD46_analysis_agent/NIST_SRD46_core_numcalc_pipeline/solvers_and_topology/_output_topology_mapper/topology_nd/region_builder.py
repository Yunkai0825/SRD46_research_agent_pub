"""
region_builder.py
=================
Step 3 of the bottom-up topology extractor: find N-D regions.

A region is a connected component of cells sharing the same label.
Connectivity is cardinal; extraction itself applies no resolution
rules.  When a fixed pass runs, the topology fixer's decisions
(``topology_fixer.FixDecisions``) supply pre-validated same-label
diagonal bridges — fragments meeting at a self-contact vertex are one
region — and per-region flags for below-resolution interstitials.
Labels of intervening cells are never rewritten.
Each region records its measure (length in 1-D, area in 2-D,
volume in 3-D) and the IDs of its bordering boundaries.
"""

from __future__ import annotations

import numpy as np
from typing import List, Optional, Tuple

try:
    from ...nd_grid.data_types import (
        NDGrid, TopologyRegion, TopologyBoundary,
    )
except ImportError:
    from nd_grid.data_types import (
        NDGrid, TopologyRegion, TopologyBoundary,
    )

from .topology_fixer import FixDecisions, bridge_adjacency, label_components


def build_regions(
    grid: NDGrid,
    boundaries: List[TopologyBoundary],
    debug: bool = False,
    fix_decisions: Optional[FixDecisions] = None,
) -> Tuple[List[TopologyRegion], int]:
    """Find connected components of same-label cells.

    Returns ``(regions, n_merges)``: TopologyRegion list with sequential
    IDs from 0, and the number of cardinal components absorbed through
    the fixer's T1 bridges (0 in the raw pass).
    """
    if grid.labels is None:
        raise ValueError("Grid not labelled")

    labels = grid.labels
    shape = grid.shape
    label_catalog = grid.label_catalog or {}
    axes = grid.axes

    cell_measure = 1.0
    for ax in axes:
        cell_measure *= ax.spacing

    bridges = list(fix_decisions.bridges) if fix_decisions else []
    region_flags = dict(fix_decisions.region_flags) if fix_decisions else {}
    comps = label_components(labels, shape, bridge_adjacency(bridges))
    if bridges:
        n_cardinal = len(label_components(labels, shape))
    else:
        n_cardinal = len(comps)
    n_merges = n_cardinal - len(comps)

    regions: List[TopologyRegion] = []
    for rid, (lbl, region_cells) in enumerate(comps):
        # A label may occur in multiple disconnected islands.  Associate
        # only boundaries that are actually incident to this connected
        # component; matching the label alone attaches every same-label
        # boundary to every island.
        bnd_ids = [
            b.id for b in boundaries
            if (b.left_label == lbl or b.right_label == lbl)
            and any(tuple(idx) in region_cells for idx in b.cell_indices)
        ]

        regions.append(TopologyRegion(
            id=rid,
            label=lbl,
            name=label_catalog.get(lbl, str(lbl)),
            measure=len(region_cells) * cell_measure,
            boundary_ids=bnd_ids,
            flags=list(region_flags.get(min(region_cells), [])),
        ))

    if debug:
        print(f"[region_builder] {len(regions)} regions "
              f"({n_merges} fixer bridge merges)")

    return regions, n_merges
