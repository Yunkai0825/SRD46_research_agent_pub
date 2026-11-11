# Pourbaix sweep and topology processing

## Entry point

Use `SRD46_numcalculator_api.run_calculation` with a saved thermodynamic card and explicit calculation card. The dispatcher selects `run_pourbaix_sweep` for a Pourbaix method. Supply an output directory and use the returned `output_paths` to locate artifacts; chemical-name stems can be compacted for platform path limits.

See the [numerical API guide](../../API_AND_SETTINGS.md) for card requirements and the [sweep guide](README.md) for method-specific behavior.

## Grid and topology

The shared numerical pipeline produces an `NDGrid` containing point solutions and convergence status. Predominance labels and per-element results feed topology extraction. The final effective label field supplies the regions, junctions and boundaries; coarse diagnostic topology remains distinct from refined output.

Topology extraction identifies junctions, builds boundaries and groups connected regions. Boundary construction uses canonical facet incidence and shared discrete vertices. Numerical recovery solves equilibrium points again, while topology processing organizes the label field. These operations must not be confused with proof that an unconverged sample has converged.

## Compaction and export

`compact_topology_nd` produces plot-ready geometry while retaining the lower-dimensional boundary relationships. `export_topology_json` writes topology metadata and dimension-specific features. Plot and CSV writers emit the scientific views and sampled data.

| Module | Role |
|---|---|
| `solvers_and_topology/nd_grid` | Grid solutions, continuation and refinement |
| `solvers_and_topology/_output_topology_mapper/topology_nd` | Junctions, boundaries and regions |
| `sweep_pipelines/_output_and_plotting/_output_topology_compactor` | Compact geometry and topology export |
| `sweep_pipelines/_output_and_plotting/pourbaix_diagrams` | Diagram and label-map output |

Paths in this table are relative to the numerical pipeline package. Solver settings and refinement must remain explicit in the calculation evidence.
