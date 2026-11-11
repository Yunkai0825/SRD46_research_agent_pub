"""Compose and complete the final N-D effective label raster.

The adaptive tree is solver state, while topology needs a single labelled
field at the requested final resolution.  This module is the shared boundary:
it expands inherited coarse labels, overlays every solved refinement node,
retries unresolved centres with solver seeds, and finally applies the existing
neighbour-label hole fill.  It contains no boundary or junction inheritance.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


EffectiveLabelMap = Tuple[List[np.ndarray], np.ndarray, Dict[int, str]]


def _catalog_for_observed_labels(
    labels: np.ndarray,
    catalog: Dict[int, str],
) -> Dict[int, str]:
    """Return only catalog entries represented by resolved raster cells.

    A coarse-grid phase can disappear after refinement (for example, when it
    occupied only a sampled endpoint outside the declared cell-centred
    domain).  Carrying that stale name into the final artifact falsely makes
    it look like a surviving predominance region.
    """

    observed = {
        int(label)
        for label in np.unique(labels)
        if int(label) >= 0
    }
    return {
        int(label): name
        for label, name in catalog.items()
        if int(label) in observed
    }


def compose_effective_label_map(
    coarse_grid,
    element_name: str,
    refine_factor: int = 4,
    debug: bool = False,
) -> EffectiveLabelMap:
    """Purely compose a cropped tree-to-raster effective label field.

    ``refine_factor`` is the effective factor ``R**L``.  Unrefined blocks
    inherit their coarse label; refined nodes overwrite only their own tree
    blocks.  Unresolved solver cells remain ``-1`` in this pure stage.
    """

    axes = coarse_grid.axes
    ndim = len(axes)
    factor = int(refine_factor)
    if factor < 1:
        raise ValueError("refine_factor must be at least 1")

    sub_indices = np.arange(factor)
    fine_axis_values: List[np.ndarray] = []
    for axis in axes:
        spacing = axis.spacing
        values = (
            axis.values[:, None] - spacing / 2.0
            + (sub_indices + 0.5)[None, :] * (spacing / factor)
        ).reshape(axis.n * factor)
        fine_axis_values.append(values)

    coarse_labels = coarse_grid.labels_per_element[element_name]
    catalog = dict(coarse_grid.label_catalog_per_element[element_name])
    fine_labels = coarse_labels
    for axis_dim in range(ndim):
        fine_labels = np.repeat(fine_labels, factor, axis=axis_dim)
    fine_labels = fine_labels.astype(np.int32, copy=True)

    def fill_block(block: np.ndarray, node: dict) -> None:
        per_element = node.get("labels_per_element")
        if per_element and element_name in per_element:
            node_labels = per_element[element_name]
        else:
            node_labels = node["labels"]
        children = node.get("children", {})
        node_factor = node_labels.shape[0]
        child_size = block.shape[0] // node_factor
        for sub_index in np.ndindex(*node_labels.shape):
            slices = tuple(
                slice(i * child_size, (i + 1) * child_size)
                for i in sub_index
            )
            child_block = block[slices]
            child = children.get(sub_index)
            if child is not None and child_size > 1:
                fill_block(child_block, child)
            else:
                child_block[:] = node_labels[sub_index]

    refined_cells = coarse_grid.refined_cells or {}
    for cell_index, node in refined_cells.items():
        slices = tuple(
            slice(
                cell_index[d] * factor,
                (cell_index[d] + 1) * factor,
            )
            for d in range(ndim)
        )
        fill_block(fine_labels[slices], node)

    # Sample-centred endpoint cells include a numerical support halo outside
    # the declared domain.  It is private solver state, never artifact data.
    for axis_dim, (axis, values) in enumerate(zip(axes, fine_axis_values)):
        lower, upper = (float(value) for value in axis.range)
        scale = max(1.0, abs(lower), abs(upper))
        tolerance = 1.0e-12 * scale
        keep = np.flatnonzero(
            (values >= lower - tolerance) & (values <= upper + tolerance)
        )
        if keep.size == 0:
            raise RuntimeError(
                f"Effective axis {axis.name!r} has no centres inside its "
                f"declared domain [{lower}, {upper}]"
            )
        fine_axis_values[axis_dim] = values[keep]
        fine_labels = np.take(fine_labels, keep, axis=axis_dim)

    if debug:
        print(
            f"[effective_label_map] {element_name}: {fine_labels.shape}, "
            f"{len(refined_cells)} refined roots, "
            f"{int((fine_labels == -1).sum())} unresolved cells",
            flush=True,
        )
    return (
        fine_axis_values,
        fine_labels,
        _catalog_for_observed_labels(fine_labels, catalog),
    )


def build_and_patch_effective_label_map(
    coarse_grid,
    element_name: str,
    *,
    point_solve_fn: Optional[Callable] = None,
    built_system: Any = None,
    x_cache: Optional[Dict] = None,
    refine_factor: int = 4,
    debug: bool = False,
) -> EffectiveLabelMap:
    """Compose the effective field and complete unresolved label cells."""

    from .grid_solver_sweep_retry_patching.solver_hole_patcher import (
        patch_grid_label_map,
    )
    from .grid_dynamic_refiner.labeler import (
        _dominant_label_for_element,
        component_indices_for_element,
        fill_unconverged_labels,
    )

    axis_values, labels, catalog = compose_effective_label_map(
        coarse_grid,
        element_name,
        refine_factor=refine_factor,
        debug=debug,
    )
    # The pure composer intentionally removes coarse-only labels.  Restore the
    # source names while solver retries are still able to introduce a phase,
    # then filter once more against the completed raster at return time.
    source_catalog = dict(
        coarse_grid.label_catalog_per_element[element_name]
    )
    source_catalog.update(catalog)
    catalog = source_catalog
    holes_before = int((labels == -1).sum())
    if (
        holes_before == 0
        or point_solve_fn is None
        or built_system is None
    ):
        return axis_values, labels, _catalog_for_observed_labels(labels, catalog)

    axis_names = [axis.name for axis in coarse_grid.axes]
    ndim = len(axis_names)
    x_cache = x_cache or {}
    x_array = np.empty(labels.shape, dtype=object)
    for index in np.ndindex(*labels.shape):
        coords = {
            axis_names[d]: float(axis_values[d][index[d]])
            for d in range(ndim)
        }
        cached = x_cache.get(tuple(sorted(coords.items())))
        x_array[index] = (
            cached if cached is not None else np.array([np.nan])
        )

    element_indices = component_indices_for_element(
        built_system, element_name,
    )
    species_ids = [species.id for species in built_system.aqueous_species]
    name_to_int = {name: label for label, name in catalog.items()}

    def resolve_label(result) -> int:
        name = _dominant_label_for_element(
            result,
            element_name,
            element_indices,
            species_ids,
            built_system.nu_elem_matrix,
            float(np.sum(built_system.C_total[element_indices])),
            built_system.dissolution_eqs,
        )
        if name in name_to_int:
            return name_to_int[name]
        new_label = max(catalog, default=-1) + 1
        name_to_int[name] = new_label
        catalog[new_label] = name
        return new_label

    recovered = patch_grid_label_map(
        axis_values,
        labels,
        x_array,
        point_solve_fn,
        resolve_label,
        axis_names,
        x_cache=x_cache,
        debug=debug,
    )
    if debug:
        print(
            f"[effective_label_map] {element_name}: solver retry recovered "
            f"{recovered}/{holes_before} unresolved cells",
            flush=True,
        )

    remaining = int((labels == -1).sum())
    if remaining:
        filled = fill_unconverged_labels(
            labels,
            ndim,
            debug=debug,
            elem_name=element_name,
            n_holes=remaining,
            hole_sentinel=-1,
        )
        if debug:
            print(
                f"[effective_label_map] {element_name}: neighbour fill "
                f"painted {filled}/{remaining} remaining cells",
                flush=True,
            )

    if debug and np.any(labels == -1):
        print(
            f"[effective_label_map] {element_name}: WARNING - "
            f"{int((labels == -1).sum())} cells remain unresolved",
            flush=True,
        )
    return axis_values, labels, _catalog_for_observed_labels(labels, catalog)


# Backward-compatible names used by existing sweep/output callers.
compose_fine_label_map = compose_effective_label_map
build_and_patch_fine_label_map = build_and_patch_effective_label_map


__all__ = [
    "EffectiveLabelMap",
    "compose_effective_label_map",
    "build_and_patch_effective_label_map",
    "compose_fine_label_map",
    "build_and_patch_fine_label_map",
]
