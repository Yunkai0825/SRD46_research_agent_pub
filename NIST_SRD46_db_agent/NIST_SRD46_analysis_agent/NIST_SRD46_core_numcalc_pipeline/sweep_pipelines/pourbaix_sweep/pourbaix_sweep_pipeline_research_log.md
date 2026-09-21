# Pourbaix Sweep Pipeline Research

## Entry Points
- Unified: `sweep_pipelines._sweep_input_entry_point.run_sweep(source, sweep_type="pourbaix", ...)`
- Direct: `sweep_pipelines.pourbaix_sweep.pourbaix_sweep_main.run_pourbaix_sweep(source, ...)`
- E2E test: `_DEBUG_script/test_sweep_orchestrator_e2e.py`

## Card format
- `.md` files in `_outputs_user/<bucket>/<DB>/<Agent>/Diagnostics/test_XX_*/free_energy_card_enriched.md`
- Headers: System, Metals, Ligands, Notation, Species, Reactions, Valence Groups

## Output directory
- Default: `_output_pourbaix/` relative to cwd
- Custom via `output_dir=` param
- Files: `pourbaix_map_{system}_{elem}.csv`, `pourbaix_{system}_{elem}.png`, `topology_{system}_{elem}.json`, speciation CSVs/plots

## CWD requirement
- Must run from `NIST_SRD46_core_calc_tools/` for sys.path to work

---

## TOPOLOGY EXTRACTION PIPELINE (Complete Topology Exploration)

### Entry Points
1. **Grid → Topology**: `extract_topology(grid: NDGrid, ...) → TopologyND`
   - Location: `solvers_and_topology/_output_topology_mapper/topology_dispatcher.py:32`
   - Auto-detects boundary cells if not provided
   - Delegates to `extract_topology_nd()`

2. **Topology → Compact**: `compact_topology_nd(source: TopologyND|Path, ...) → CompactTopologyND`
   - Location: `sweep_pipelines/_output_and_plotting/_output_topology_compactor/compact_nd.py:65`
   - Processes dimension-by-dimension (0-D → 1-D → 2-D → ...)
   - Input: TopologyND object OR CSV files
   - Output: Simplified, plot-ready CompactTopologyND

3. **Compact → JSON**: `export_topology_json(topo: CompactTopologyND|TopologyND|TopologyMap, ...)`
   - Location: `sweep_pipelines/_output_and_plotting/_output_topology_compactor/topology_export.py:23`
   - Supports 3 topology types (legacy TopologyMap, new TopologyND, compact CompactTopologyND)
   - Output: JSON with metadata, label catalog, nodes/edges/faces + dimension-specific features

### Core Data Types
- **NDGrid**: `nd_grid.data_types.NDGrid` — N-D grid of PointResult solutions
- **TopologyND**: `nd_grid.data_types.TopologyND` — Complete N-D topology (junctions, boundaries, regions)
- **CompactTopologyND**: `nd_grid.data_types.CompactTopologyND` — Simplified, dimension-agnostic topology
- **TopologyJunction**: 0-D points where 3+ regions meet
- **TopologyBoundary**: (N-1)-D manifold separating regions (geometry: float/polyline/point-cloud)
- **TopologyRegion**: N-D connected region with measure & boundary list
- **CompactFeature**: Unified feature type (dim 0-D/1-D/2-D/k-D with raw & compact geometry)

### 3-Stage Extraction Pipeline
1. **Stage 1 - Junction Finding**: `find_junctions(grid, boundary_cells)`
   - Detects 0-D critical points (triple points in 2-D, triple lines in 3-D)
   - Clusters candidates, runs clique analysis
   - Identifies domain-edge junctions

2. **Stage 2 - Boundary Building**: `build_boundaries(grid, boundary_cells, junctions, refined_points)`
   - Groups boundary facets by label pair
   - Builds geometry: 1-D=float, 2-D=polyline, N-D=point-cloud
   - Integrates refined bisection points
   - Assigns junction endpoints

3. **Stage 3 - Region Building**: `build_regions(grid, boundaries)`
   - Connected components of same-label cells
   - Computes measure (length/area/volume)
   - Records bordering boundaries

### 3-Pass Compaction Pipeline
- **Dim 0**: Exact copy (dict coords)
- **Dim 1**: RDP simplification + envelope subsampling (RDP_EPSILON, RDP_ENVELOPE_N)
- **Dim 2**: Farthest-point insertion + Delaunay triangulation → (vertices, triangles)
- **Dim k≥3**: Point thinning fallback
- Each pass seeded by previous (dim-1) features for boundary coherence

### JSON Export Format
```json
{
  "metadata": { ndim, axis_names, axis_ranges, topology_settings },
  "label_catalog": { "int": "label_name" },
  "nodes": [ { id, coords, labels, domain_edge } ],
  "edges": [ { id, type, geometry, junction_ids } ],
  "faces": [ { id, label, name, measure, edges } ],
  "features_0d": [ { geometry_raw, geometry_compact, ... } ],
  "features_1d": [ ... ]
}
```

### Key Files
- Dispatcher: `solvers_and_topology/_output_topology_mapper/topology_dispatcher.py`
- Extractor: `solvers_and_topology/_output_topology_mapper/topology_nd/topology_nd.py`
- Junction: `solvers_and_topology/_output_topology_mapper/topology_nd/junction_finder.py`
- Boundaries: `solvers_and_topology/_output_topology_mapper/topology_nd/boundary_builder.py`
- Regions: `solvers_and_topology/_output_topology_mapper/topology_nd/region_builder.py`
- Compactor: `sweep_pipelines/_output_and_plotting/_output_topology_compactor/compact_nd.py`
- Exporter: `sweep_pipelines/_output_and_plotting/_output_topology_compactor/topology_export.py`
- Data types: `solvers_and_topology/nd_grid/data_types.py`
