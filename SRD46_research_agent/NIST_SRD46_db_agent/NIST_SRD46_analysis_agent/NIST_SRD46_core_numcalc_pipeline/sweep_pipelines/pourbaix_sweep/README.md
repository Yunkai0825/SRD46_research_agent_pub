# `sweep_pipelines/pourbaix_sweep/`

Unified **N-D Pourbaix sweep** — single handler covering 1-D
(single axis), 2-D (pH × E_V), and 3-D (pH × E_V × a_w), with a
straightforward extension path to higher dimensionality.

## Files

| File                                  | Purpose                                                                                |
|---------------------------------------|----------------------------------------------------------------------------------------|
| `pourbaix_sweep_main.py`              | `run_pourbaix_sweep(...)` — solver chain build, NDGridSolver driver, per-layer logger. |
| `pourbaix_sweep_export.py`            | `emit_*` orchestrators (coarse / refined / 3-D / speciation) + registry `sweep_fn`.     |
| `pourbaix_sweep_settings.py`          | Non-card algorithmic and output settings.                                             |
| `pourbaix_sweep_pipeline_research_log.md` | Design log (kept for traceability; not part of the runtime).                       |

## Pipeline (dimension-agnostic stages)

```
FreeEnergyReport
  → build_from_free_energy_report     (BuiltSystem)
  → PourbaixPointSolver + SolidManager (Newton-Raphson + active-set)
  → NDGridSolver.solve                (coarse grid + label + boundary detect + multi-layer refine)
  → extract_topology_nd               (0-D junctions, 1-D boundaries, 2-D regions; 3-D too)
  → compact_topology_nd               (RDP-simplified features)
  → fine_label_map_assembler          (dense raster from coarse + refined sub-cells)
  → emit_* outputs (dim-aware)
```

Only the final emission is dim-aware:

| ndim | Outputs                                                                                  |
|------|------------------------------------------------------------------------------------------|
| 1    | Topology JSON only.                                                                      |
| 2    | Label-map CSV (coarse + fine) + topology JSON + 2-D PNG + full speciation CSV + snapshots. |
| 3    | Topology JSON + 3-D topology PNG (`plot_3d_topology`).                                   |
| ≥ 4  | Topology JSON only.                                                                      |

## Public API

```python
def run_pourbaix_sweep(
    source, *,
    axes:         Optional[List[GridAxis]] = None,   # ND-aware (preferred)
    pH_range:     Optional[Tuple[float,float]] = None,
    E_range:      Optional[Tuple[float,float]] = None,
    aw_range:     Optional[Tuple[float,float]] = None,
    n_pH:         Optional[int] = None,
    n_E:          Optional[int] = None,
    n_aw:         Optional[int] = None,
    output_dir:   Optional[str] = None,
    temperature_K:Optional[float] = None,
    ionic_strength:Optional[float] = None,
    refine_factor:Optional[int],  # None disabled; otherwise >= 2
    n_layers:     int,            # 0 disabled; otherwise >= 1
    debug:        bool = True,
    compiled_constraints: Optional[Any] = None,
) -> Dict[str, Any]
```

There is no refinement fallback: callers must explicitly pass
`n_layers=0, refine_factor=None` or declare positive layers and a factor of
at least two for a 2-D/3-D boundary-refined run.

Returns `{report, grid, built, per_element, output_paths, …}`.

## Per-layer snapshots

`pourbaix_sweep_main` registers a `per_layer_callback` with
`NDGridSolver.solve()` to dump a 2-D PNG snapshot at each refinement
layer (`snap_NN_<stage>_<element>.png`) — invaluable for diagnosing
artefacts in the cascaded refinement.

## Output artefacts (2-D)

| File                                                                    | Purpose                                  |
|-------------------------------------------------------------------------|------------------------------------------|
| `pourbaix_map_<system>_<E>.csv`                                          | 64×64 (refined) fine label map per principal element. |
| `pourbaix_<system>_<E>.png`                                              | 2-D Pourbaix diagram.                    |
| `topology_<system>_<E>.json`                                             | `features_0d`, `features_1d`, `regions`. |
| `topo_csv_<system>_<E>/{metadata.json, features_*.csv}`                  | Per-feature CSVs for downstream consumers. |
| `speciation_full_<system>.csv`                                           | All evaluated grid points + refinement.  |
| `_snapshots/snap_NN_*.png`                                               | Per-layer refinement snapshots.          |
| `sweep_log.txt`                                                          | Timestamped pipeline log.                |

Always invoked through `sweep_method_registry_api`; never import this
package directly.
