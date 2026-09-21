"""
labeler.py
==========
Assigns composite labels to each grid point based on element-wise
predominance and solid assemblage.

N-D generalization of the legacy 2-D labeler.  All nested
``for i_E ... for i_pH`` loops are replaced with
``np.ndindex(*grid.shape)`` iteration.

Public API
----------
- ``label_grid_nd``  — label every point in an NDGrid
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple

from ..data_types import NDGrid, PointResult, all_offsets, in_bounds, add_offset
from ..settings import LABEL_TOL, LABEL_SOLID_TOL, LABEL_MODE, DEBUG


def label_grid_nd(
    grid: NDGrid,
    built_system,
    debug: bool = DEBUG,
) -> NDGrid:
    """
    Label every grid point with the dominant species per element
    and the active-solid assemblage.

    Mutates *grid* in-place (sets ``labels``, ``label_catalog``,
    ``labels_per_element``, ``label_catalog_per_element``) and returns it.
    """
    principal = built_system.principal_elements
    element_names = built_system.element_names
    species_list = built_system.aqueous_species
    diss_eqs = built_system.dissolution_eqs
    nu_elem = built_system.nu_elem_matrix
    C_total = built_system.C_total

    component_rows = {
        name: component_indices_for_element(built_system, name)
        for name in principal
    }
    sp_ids = [sp.id for sp in species_list]

    if debug:
        shape_str = "x".join(str(s) for s in grid.shape)
        print(f"[labeler] Labelling {shape_str} grid, "
              f"principal elements: {principal}, mode={LABEL_MODE}")

    if LABEL_MODE == "PER_ELEMENT":
        _label_per_element(grid, built_system, principal,
                           component_rows, sp_ids, nu_elem,
                           C_total, debug)
    else:
        _label_combined(grid, built_system, principal,
                        component_rows, sp_ids, nu_elem,
                        C_total, debug)

    return grid


def component_indices_for_element(built_system, element_name: str) -> List[int]:
    """Return solver component rows belonging to one physical element.

    Redox-enabled systems normally have one solver row per physical element.
    Redox-excluded systems may instead have independent Fe(II), Fe(III), ...
    rows.  ``element_to_ids`` retains that physical grouping so artifact
    labelling can aggregate the rows without collapsing solver degrees of
    freedom.
    """

    element_names = list(getattr(built_system, "element_names", []) or [])
    basis_tokens = list(getattr(built_system, "basis_tokens", []) or [])
    token_to_index = {
        token: index
        for index, token in enumerate(basis_tokens[:len(element_names)])
    }
    grouped_ids = (
        getattr(built_system, "element_to_ids", {}) or {}
    ).get(element_name, [])

    indices: List[int] = []
    for token in grouped_ids:
        index = token_to_index.get(token)
        if index is not None and index not in indices:
            indices.append(index)

    # Redox-enabled systems can map several source IDs to one element row;
    # only the reference token is present in ``basis_tokens``.  The physical
    # element name is then the direct and unambiguous fallback.
    if not indices and element_name in element_names:
        indices.append(element_names.index(element_name))

    # Backward compatibility for lightweight test/proxy objects that expose
    # component names but not basis tokens or element_to_ids.
    if not indices:
        matching = [
            index for index, name in enumerate(element_names)
            if name == element_name
        ]
        indices.extend(matching)

    if not indices:
        raise KeyError(
            f"Principal element {element_name!r} has no mapped solver "
            f"component; element_names={element_names!r}, "
            f"element_to_ids={getattr(built_system, 'element_to_ids', {})!r}"
        )
    return indices


# ------------------------------------------------------------------
#  PER_ELEMENT mode
# ------------------------------------------------------------------

def _label_per_element(grid, built, principal, component_rows, sp_ids,
                       nu_elem, C_total, debug):
    """One integer label map per principal element."""
    diss_eqs = built.dissolution_eqs
    shape = grid.shape

    labels_per_elem: Dict[str, np.ndarray] = {}
    catalog_per_elem: Dict[str, Dict[int, str]] = {}

    for elem_name in principal:
        e_rows = component_rows[elem_name]
        C_elem = float(np.sum(C_total[e_rows]))

        label_map = np.full(shape, -2, dtype=np.int32)
        name_to_int: Dict[str, int] = {}
        int_to_name: Dict[int, str] = {}
        next_id = 0

        for idx in np.ndindex(*shape):
            pt: PointResult = grid.points[idx]
            if pt is None or not pt.converged:
                continue  # stays -2

            lbl = _dominant_label_for_element(
                pt, elem_name, e_rows, sp_ids, nu_elem, C_elem, diss_eqs)

            if lbl not in name_to_int:
                name_to_int[lbl] = next_id
                int_to_name[next_id] = lbl
                next_id += 1
            label_map[idx] = name_to_int[lbl]

        # Fill unconverged holes by nearest-neighbor label propagation
        n_holes = int(np.sum(label_map == -2))
        if n_holes > 0:
            _fill_unconverged_labels(label_map, grid.ndim, debug,
                                     elem_name, n_holes)

        labels_per_elem[elem_name] = label_map
        catalog_per_elem[elem_name] = int_to_name

        if debug:
            print(f"  [labeler] {elem_name}: {len(int_to_name)} distinct labels")
            for k, v in sorted(int_to_name.items()):
                count = int(np.sum(label_map == k))
                print(f"    {k:3d}: {v:40s} ({count} pts)")

    grid.labels_per_element = labels_per_elem
    grid.label_catalog_per_element = catalog_per_elem

    # Also create a combined label from the first principal element
    first = principal[0]
    grid.labels = labels_per_elem[first]
    grid.label_catalog = catalog_per_elem[first]


# ------------------------------------------------------------------
#  Nearest-neighbour hole fill for unconverged cells (N-D)
# ------------------------------------------------------------------

def fill_unconverged_labels(label_map: np.ndarray, ndim: int,
                            debug: bool = False, elem_name: str = "",
                            n_holes: Optional[int] = None,
                            hole_sentinel: int = -2) -> int:
    """
    Iteratively fill ``label_map`` cells equal to ``hole_sentinel``
    using the majority label of converged (``>= 0``) neighbours.
    Uses all ``3^N - 1`` neighbour offsets (cardinal + diagonal).
    Mutates ``label_map`` in place; returns the number of cells filled.

    The coarse labeler uses ``hole_sentinel=-2`` (the default), while
    the fine-grid refiner uses ``hole_sentinel=-1`` (its convention
    for unconverged sub-cells).  Both flow through this single N-D
    routine.
    """
    shape = label_map.shape
    offsets = all_offsets(ndim)
    max_passes = max(shape) if shape else 0
    total_filled = 0

    for _pass in range(max_passes):
        holes = list(zip(*np.where(label_map == hole_sentinel)))
        if not holes:
            break
        filled_this_pass = 0
        for hole_idx in holes:
            counts: Dict[int, int] = {}
            for off in offsets:
                nb = add_offset(hole_idx, off)
                if in_bounds(nb, shape) and label_map[nb] >= 0:
                    lbl = int(label_map[nb])
                    counts[lbl] = counts.get(lbl, 0) + 1
            if counts:
                label_map[hole_idx] = max(counts, key=counts.get)
                filled_this_pass += 1
        total_filled += filled_this_pass
        if filled_this_pass == 0:
            break

    if debug and total_filled > 0:
        remaining = int(np.sum(label_map == hole_sentinel))
        denom = n_holes if n_holes is not None else total_filled
        print(f"  [labeler] {elem_name}: filled {total_filled}/{denom} "
              f"unconverged holes by neighbour vote"
              + (f" ({remaining} still unfilled)" if remaining else ""))
    return total_filled


# Backward-compat alias for in-module callers.
def _fill_unconverged_labels(label_map: np.ndarray, ndim: int,
                             debug: bool, elem_name: str,
                             n_holes: int) -> None:
    fill_unconverged_labels(label_map, ndim, debug=debug,
                            elem_name=elem_name, n_holes=n_holes,
                            hole_sentinel=-2)


# ------------------------------------------------------------------
#  COMBINED mode (N-D)
# ------------------------------------------------------------------

def _label_combined(grid, built, principal, component_rows, sp_ids,
                    nu_elem, C_total, debug):
    """Single composite label = joined element predominances."""
    diss_eqs = built.dissolution_eqs
    shape = grid.shape

    label_map = np.full(shape, -2, dtype=np.int32)
    tuple_to_int: Dict[str, int] = {}
    int_to_tuple: Dict[int, str] = {}
    next_id = 0

    for idx in np.ndindex(*shape):
        pt: PointResult = grid.points[idx]
        if pt is None or not pt.converged:
            continue

        parts = []
        for elem_name in principal:
            e_rows = component_rows[elem_name]
            C_elem = float(np.sum(C_total[e_rows]))
            lbl = _dominant_label_for_element(
                pt, elem_name, e_rows, sp_ids, nu_elem, C_elem, diss_eqs)
            parts.append(lbl)
        composite = " | ".join(parts)

        if composite not in tuple_to_int:
            tuple_to_int[composite] = next_id
            int_to_tuple[next_id] = composite
            next_id += 1
        label_map[idx] = tuple_to_int[composite]

    # Fill unconverged holes
    n_holes = int(np.sum(label_map == -2))
    if n_holes > 0:
        _fill_unconverged_labels(label_map, grid.ndim, debug,
                                 "COMBINED", n_holes)

    grid.labels = label_map
    grid.label_catalog = int_to_tuple

    if debug:
        print(f"  [labeler] COMBINED: {len(int_to_tuple)} distinct labels")
        for k, v in sorted(int_to_tuple.items()):
            count = int(np.sum(label_map == k))
            print(f"    {k:3d}: {v:40s} ({count} pts)")


# ------------------------------------------------------------------
#  Per-point label for one element (shape-agnostic)
# ------------------------------------------------------------------

def _dominant_label_for_element(
    pt: PointResult,
    elem_name: str,
    elem_row,
    sp_ids: List[str],
    nu_elem: np.ndarray,
    C_elem: float,
    diss_eqs,
) -> str:
    """
    Determine the dominant phase/species for one element at one point.

    1. Check if any solid containing this element is active and accounts
       for a large fraction of the total element.
    2. Among aqueous species, find the one carrying the most of the element.
    3. Return a label string like "Fe(OH)3(s)" or "Fe2+citrate".
    """
    if isinstance(elem_row, (int, np.integer)):
        elem_rows = [int(elem_row)]
    else:
        elem_rows = [int(row) for row in elem_row]
    if not elem_rows:
        raise ValueError(f"No solver component rows mapped to {elem_name!r}")

    # Solid fraction
    solid_total = 0.0
    solid_labels = []
    for deq in diss_eqs:
        sid = deq.id
        if sid in pt.solid_amounts and pt.solid_amounts[sid] > LABEL_SOLID_TOL:
            nu_e = sum(
                deq.nu_elements[row]
                for row in elem_rows
                if row < len(deq.nu_elements)
            )
            if nu_e > 0:
                n_s = pt.solid_amounts[sid]
                elem_in_solid = nu_e * n_s
                solid_total += elem_in_solid
                solid_labels.append((sid, elem_in_solid))

    # Aqueous species fractions
    aq_fracs = []
    aq_total = 0.0
    nu_row = np.sum(nu_elem[elem_rows, :], axis=0)
    for i, sp_id in enumerate(sp_ids):
        if nu_row[i] > 0 and sp_id in pt.conc:
            contribution = nu_row[i] * pt.conc[sp_id]
            aq_fracs.append((sp_id, contribution))
            aq_total += contribution

    total_accounted = solid_total + aq_total
    if total_accounted < 1e-30:
        return f"{elem_name}(trace)"

    # Check if solid dominates
    if solid_total / total_accounted > 0.5:
        solid_labels.sort(key=lambda x: -x[1])
        return solid_labels[0][0]

    # Fall back to dominant aqueous species
    aq_fracs.sort(key=lambda x: -x[1])
    if len(aq_fracs) == 0:
        return f"{elem_name}(trace)"

    return aq_fracs[0][0]
