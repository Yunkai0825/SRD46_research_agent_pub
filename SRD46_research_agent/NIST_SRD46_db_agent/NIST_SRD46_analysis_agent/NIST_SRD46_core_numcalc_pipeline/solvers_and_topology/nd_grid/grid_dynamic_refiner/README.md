# `nd_grid/grid_dynamic_refiner/`

Labelling, boundary detection, and multi-layer cascaded refinement.
All three stages are dimension-agnostic and consumed only by
`NDGridSolver.solve()`.

## Files

| File                  | Purpose                                                                            |
|-----------------------|------------------------------------------------------------------------------------|
| `labeler.py`          | `label_grid_nd(grid, built)` — assign per-element phase labels to each coarse sample. |
| `boundary_detector.py`| `detect_boundary_cells_nd(grid, element_name)` — emit one canonical facet for each positive-axis adjacent-label transition. |
| `boundary_refiner.py` | `refine_boundaries_multilayer_nd(...)` — expand every facet to all cells touching its vertices, solve their deduplicated sub-grids, and localize inter-label transitions. |

## Pipeline order (inside `NDGridSolver.solve()`)

```
grid (coarse, solved)
  → labeler.label_grid_nd                 → per-element label field
  → boundary_detector.detect_boundary_cells_nd → canonical BoundaryCellND facets
  → stable union of every cell touching any facet vertex
  → boundary_refiner.refine_boundaries_multilayer_nd
                                           → RefinedBoundaryPointND list
     (repeated n_layers times)
```

`BoundaryCellND.index` is the lower-index anchor of a unique oriented facet;
it is not, by itself, the refinement target set.  Topology keeps the canonical
facet records, while the numerical scheduler refines every vertex-incident
cell once.
In multi-element systems, the union is solved once and labelled for every
principal element.

`boundary_refiner` uses `solver_hole_patcher.patch_holes` from the
sibling `grid_solver_sweep_retry_patching/` package to re-seed
sub-cells that fail to converge during refinement.

## I/O contract

- **Input:** `NDGrid` (already solved at the coarse level), the
  `BuiltSystem`, plus the active `point_solve_fn`.
- **Output:** per-element label field + canonical boundary-facet list + refined
  sub-grid points (`RefinedBoundaryPointND`).
