# `_output_topology_mapper/topology_nd/`

The unified N-D topology extractor — works identically for 1-D, 2-D,
and 3-D grids. Only entry point used by `topology_dispatcher`.

## Files

| File                  | Purpose                                                                                  |
|-----------------------|------------------------------------------------------------------------------------------|
| `topology_nd.py`      | `extract_topology_nd(grid, boundary_cells, refined_points, …)` — top-level orchestrator. |
| `region_builder.py`   | Flood-fill labelled cells into contiguous regions.                                       |
| `junction_finder.py`  | Vertex-based junction detection — points where 3+ labels meet (interior + domain-edge).  |
| `boundary_builder.py` | Build boundary chains (1-D edges in 2-D, facets in 3-D) between adjacent regions.        |
| `geometry_utils.py`   | Collinearity (`_fit_line_2d`), planarity, RDP simplification, span helpers.              |

## Extraction order (bottom-up)

```
labelled grid
  → region_builder.build_regions               (features_2d / features_3d)
  → junction_finder.find_junctions             (features_0d)
  → boundary_builder.build_boundaries          (features_1d / features_2d facets)
  → RDP simplification, pinned at junctions
  → assemble TopologyND
```

## 2-D diagonal-artifact fix

`boundary_builder._fit_line_2d` returns a collinearity residual.
`_refine_interior_junctions_2d` then gates the SVD-based junction
relocation by:

```
residual ≤ 0.25   AND   max_span ≤ min(spacing)
```

This prevents diagonal "spikes" between near-vertical and
near-horizontal boundaries from corrupting interior junctions.

## I/O contract

- **Input:** labelled `NDGrid` + boundary cells + refined points.
- **Output:** `TopologyND` (`features_0d`, `features_1d`, `regions`,
  Euler check).
