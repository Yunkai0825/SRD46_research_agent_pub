"""Topology reconstruction from one resolved effective label field.

This module is deliberately independent of the adaptive-refinement scheduler.
Its input is a complete N-D label raster at one requested resolution.  All
canonical facets, junctions, boundary components, and regions are therefore
caused by that raster alone; no facet or junction from an upstream grid is
accepted as an input.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .data_types import BoundaryCellND, GridAxis, TopologyND
from .._output_topology_mapper.topology_nd.topology_nd import (
    extract_topology_nd,
)
from .._output_topology_mapper.topology_nd.topology_fixer import (
    analyze_fixes_2d,
)


EffectiveLabelMap = Tuple[List[np.ndarray], np.ndarray, Dict[int, str]]


class _EffectiveLabelGrid:
    """Minimal labelled-grid interface used by the topology extractor."""

    def __init__(self, axes, labels, catalog):
        self.axes = axes
        self.labels = labels
        self.label_catalog = dict(catalog or {})
        self.labels_per_element = None
        self.label_catalog_per_element = None

    @property
    def ndim(self):
        return len(self.axes)

    @property
    def shape(self):
        return self.labels.shape


def extract_effective_topology(
    coarse_grid,
    effective_label_map: EffectiveLabelMap,
    *,
    debug: bool = False,
) -> Tuple[
    TopologyND, List[GridAxis], np.ndarray, List[BoundaryCellND],
    TopologyND,
]:
    """Rebuild complete topology exclusively from an effective label map.

    Returns ``(topology, effective_axes, labels, canonical_facets,
    raw_topology)``.  The raw extraction applies no resolution rules and
    is preserved as the audit reference; the topology fixer then
    analyzes it and resolves below-resolution fragments into cell marks,
    and a second pass extracts the fixed ``topology`` from the resulting
    *effective* label map -- the deep-merged grid.  That grid is what
    ``labels`` and ``canonical_facets`` describe, so every downstream
    consumer (compaction, plotting, the verdict report) sees one
    consistent raster; the solver's own raster is recoverable from the
    ``marks`` list in ``topology.settings["topology_fix"]``.  When the
    fixer is disabled or the grid is not 2-D, the raw solution is the
    final one (both return slots hold the same object, and ``labels`` is
    the input raster).  The original grid contributes only axis names,
    display labels, declared domain fenceposts, and the coarse spacings
    that size the fixer's trust; its labels, facets, refined points, and
    junctions are intentionally not consulted.
    """

    if effective_label_map is None:
        raise ValueError("effective_label_map must not be None")

    axis_values, labels, catalog = effective_label_map
    labels = np.asarray(labels)
    ndim = len(coarse_grid.axes)
    if len(axis_values) != ndim or labels.ndim != ndim:
        raise ValueError(
            "effective label-map dimensionality does not match the grid: "
            f"{len(axis_values)} axes and a {labels.ndim}-D label array for "
            f"a {ndim}-D grid"
        )

    effective_axes: List[GridAxis] = []
    for axis_dim, (coarse_axis, values) in enumerate(
        zip(coarse_grid.axes, axis_values)
    ):
        values = np.asarray(values, dtype=float)
        if values.ndim != 1:
            raise ValueError(
                f"effective axis {coarse_axis.name!r} must be one-dimensional"
            )
        if labels.shape[axis_dim] != len(values):
            raise ValueError(
                f"effective axis {coarse_axis.name!r} has {len(values)} "
                f"values but label dimension {axis_dim} has length "
                f"{labels.shape[axis_dim]}"
            )
        effective_axes.append(GridAxis(
            coarse_axis.name,
            values,
            display_label=coarse_axis.display_label,
            domain_range=coarse_axis.range,
        ))

    facets = _canonical_facets(labels, effective_axes)

    if debug:
        print(
            "[effective_topology] Reconstructing from resolved grid "
            f"{labels.shape} ({len(facets)} canonical facets)",
            flush=True,
        )

    effective_grid = _EffectiveLabelGrid(
        effective_axes, labels, catalog,
    )
    # Pass 1 — raw extraction: no resolution rules, the audit reference.
    raw_topology = extract_topology_nd(
        effective_grid,
        boundary_cells=facets,
        refined_points=[],
        debug=debug,
    )
    common_settings = {
        "resolution": "final_effective_grid",
        "causal_source": "effective_label_map_only",
        # Coarse-grid step, used by the compactor to protect closed loops
        # smaller than one coarse cell.
        "axis_spacing_coarse": {
            axis.name: float(np.median(np.diff(
                np.asarray(axis.values, dtype=float))))
            for axis in coarse_grid.axes
            if getattr(axis, "values", None) is not None
            and len(axis.values) > 1
        },
    }
    # Pass 2 — fixer analysis + fixed extraction on the effective map.
    # Labels were decided at the coarse scale, so the fixer's trust
    # defaults to coarse cells; below-resolution fragments are resolved
    # into cell marks and the fixed pass extracts the topology of the
    # marked (deep-merged) grid.
    decisions = analyze_fixes_2d(
        effective_grid, raw_topology,
        coarse_axes=coarse_grid.axes, debug=debug,
    )
    if decisions is not None:
        if decisions.effective_labels is not None:
            labels = np.asarray(decisions.effective_labels)
            facets = _canonical_facets(labels, effective_axes)
        fixed_grid = _EffectiveLabelGrid(effective_axes, labels, catalog)
        topology = extract_topology_nd(
            fixed_grid,
            boundary_cells=facets,
            refined_points=[],
            debug=debug,
            fix_decisions=decisions,
        )
        raw_topology.settings.update(common_settings)
        raw_topology.settings.update({
            "is_final": False,
            "role": "raw_pre_fix",
            "label_source": "solver_raster",
        })
        topology.settings["label_source"] = "effective_label_map_with_fixer_marks"
    else:
        topology = raw_topology
        topology.settings["label_source"] = "solver_raster"
    topology.settings.update(common_settings)
    topology.settings.update({"is_final": True})
    return topology, effective_axes, labels, facets, raw_topology


def _canonical_facets(labels: np.ndarray, axes: List[GridAxis]) -> List[BoundaryCellND]:
    """Label-changing facets of the raster, one record per facet."""
    ndim = labels.ndim
    facets: List[BoundaryCellND] = []
    for axis_dim, axis in enumerate(axes):
        left_slice = [slice(None)] * ndim
        right_slice = [slice(None)] * ndim
        left_slice[axis_dim] = slice(None, -1)
        right_slice[axis_dim] = slice(1, None)
        left = labels[tuple(left_slice)]
        right = labels[tuple(right_slice)]
        transitions = (left != right) & (left >= 0) & (right >= 0)
        for raw_index in np.argwhere(transitions):
            index = tuple(int(value) for value in raw_index)
            facets.append(BoundaryCellND(
                index=index,
                axis=axis_dim,
                axis_name=axis.name,
                left_label=int(left[index]),
                right_label=int(right[index]),
                btype="unknown",
            ))
    return facets


__all__ = ["EffectiveLabelMap", "extract_effective_topology"]
