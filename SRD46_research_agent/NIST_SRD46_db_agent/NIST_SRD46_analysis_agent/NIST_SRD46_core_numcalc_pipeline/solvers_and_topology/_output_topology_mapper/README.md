# `solvers_and_topology/_output_topology_mapper/`

Extract a dimension-agnostic topology graph (junctions, boundaries,
regions) from a labelled `NDGrid` and the refined boundary points.

## Folder map

```
_output_topology_mapper/
├── topology_dispatcher.py          ← extract_topology(grid, refined_points, …) — single entry
└── topology_nd/                    § N-D extractor (1-D / 2-D / 3-D)
    ├── topology_nd.py                top-level orchestration (extract_topology_nd)
    ├── boundary_builder.py           chain construction (1-D boundaries, 2-D faces, 3-D facets)
    ├── junction_finder.py            vertices where 3+ labels meet (interior + domain-edge)
    ├── region_builder.py             flood-fill regions from label field
    └── geometry_utils.py             collinearity / planarity / RDP helpers
```

## Public API

```python
from solvers_and_topology._output_topology_mapper.topology_dispatcher import (
    extract_topology,
)

topology = extract_topology(
    grid,                       # labelled NDGrid
    refined_points=...,         # optional: bisection sub-points
    boundary_cells=...,         # optional: auto-detected if absent
    element_name="Fe",
    debug=False,
)
# topology.features_0d   (junctions / endpoints)
# topology.features_1d   (boundary chains)
# topology.regions       (filled label-field cells)
# topology.euler_check   (V − E + F sanity check)
```

## Key behaviours

- **2-D diagonal-artifact fix** lives in
  `topology_nd/boundary_builder.py`: `_fit_line_2d` returns a
  collinearity residual; `_refine_interior_junctions_2d` gates the
  SVD-based junction relocation by
  `residual ≤ 0.25` and `max_span ≤ min(spacing)`.
- **Bottom-up extraction**: regions → junctions → boundary chains.
  Each chain is RDP-simplified only *after* its endpoints are
  pinned to junctions, preserving graph topology under simplification.

## I/O contract

- **Input:** labelled `NDGrid` + optional refined boundary points +
  optional pre-computed boundary-cell list.
- **Output:** `TopologyND` — the dim-agnostic dataclass consumed by
  `_output_topology_compactor` (compaction + JSON export) and by the
  3-D PNG renderer.
