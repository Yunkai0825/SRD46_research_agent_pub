# Solver report (Pourbaix)

## System
- Components: [Ni, Glycine]
- Constraints:
  -- component totals (M): Ni=0.001;Glycine=0.01
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-1V, 1.6V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.008, ΔE_V=0.002V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Ni
- Dms_2: Ni(OH)2
- Dms_3: [Ni(Glyc)3]-
- Dms_4: [Ni(Glyc)2]
- Dms_5: [Ni(Glyc)]+
- Dms_6: Ni2+
- Dms_7: Ni3O4.2H2O
- Dms_8: Ni2O3.H2O
- Dms_9: NiO2.2H2O

## Topology stats
- 9 dominant-species labels
- 9 connected regions
- 18 pairwise boundary curves
- 10 internal junction features
- 6 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.3V)
- Fixed sample indices: (pH=swept, E_V=sample 650)
- samples 0–759, (pH=[0, 6.072], E_V=0.3V): Ni2+ (Dms_6)
- samples 760–849, (pH=[6.08, 6.792], E_V=0.3V): [Ni(Glyc)]+ (Dms_5)
  -- preceding label change is bracketed by adjacent samples (pH=[6.072, 6.08], E_V=0.3V)
- samples 850–996, (pH=[6.8, 7.968], E_V=0.3V): [Ni(Glyc)2] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=[6.792, 6.8], E_V=0.3V)
- samples 997–1381, (pH=[7.976, 11.048], E_V=0.3V): [Ni(Glyc)3]- (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=[7.968, 7.976], E_V=0.3V)
- samples 1382–1750, (pH=[11.056, 14], E_V=0.3V): Ni3O4.2H2O (Dms_7)
  -- preceding label change is bracketed by adjacent samples (pH=[11.048, 11.056], E_V=0.3V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=7, E_V=swept)
- Fixed sample indices: (pH=sample 875, E_V=swept)
- samples 0–312, (pH=7, E_V=[-1V, -0.376V]): Ni (Dms_1)
- samples 313–870, (pH=7, E_V=[-0.374V, 0.74V]): [Ni(Glyc)2] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[-0.376V, -0.374V])
- samples 871–957, (pH=7, E_V=[0.742V, 0.914V]): Ni3O4.2H2O (Dms_7)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[0.74V, 0.742V])
- samples 958–1028, (pH=7, E_V=[0.916V, 1.056V]): Ni2O3.H2O (Dms_8)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[0.914V, 0.916V])
- samples 1029–1300, (pH=7, E_V=[1.058V, 1.6V]): NiO2.2H2O (Dms_9)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[1.056V, 1.058V])

## Topology details
// Coordinate order: [pH, E_V]

### canonical topology convention
| Canonical family | Meaning |
|---|---|
| `Dms_i` | Dominant-species label |
| `DmsReg_i` | Connected region |
| `DmsRegEq_i` | Connected pairwise boundary manifold |
| `DmsRegEqJnc_i` | Lower-dimensional junction feature |

### regions
#### solid
- **DmsReg_1 {Ni}**
  -- Measure in the solver coordinate frame: 7.837664
  -- Neighboring regions:
    --- DmsReg_2 {Ni(OH)2} via DmsRegEq_15
    --- DmsReg_6 {[Ni(Glyc)3]-} via DmsRegEq_4
    --- DmsReg_7 {[Ni(Glyc)2]} via DmsRegEq_5
    --- DmsReg_8 {[Ni(Glyc)]+} via DmsRegEq_6
    --- DmsReg_9 {Ni2+} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_13, DmsRegEqJnc_9, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_7]
- **DmsReg_2 {Ni(OH)2}**
  -- Measure in the solver coordinate frame: 2.23032
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_15
    --- DmsReg_6 {[Ni(Glyc)3]-} via DmsRegEq_10
    --- DmsReg_3 {Ni3O4.2H2O} via DmsRegEq_17
  -- Junction features: [DmsRegEqJnc_13, DmsRegEqJnc_9, DmsRegEqJnc_10, DmsRegEqJnc_14]
- **DmsReg_3 {Ni3O4.2H2O}**
  -- Measure in the solver coordinate frame: 2.17712
  -- Neighboring regions:
    --- DmsReg_2 {Ni(OH)2} via DmsRegEq_17
    --- DmsReg_6 {[Ni(Glyc)3]-} via DmsRegEq_11
    --- DmsReg_7 {[Ni(Glyc)2]} via DmsRegEq_12
    --- DmsReg_8 {[Ni(Glyc)]+} via DmsRegEq_13
    --- DmsReg_9 {Ni2+} via DmsRegEq_14
    --- DmsReg_4 {Ni2O3.H2O} via DmsRegEq_18
  -- Junction features: [DmsRegEqJnc_14, DmsRegEqJnc_10, DmsRegEqJnc_4, DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_11, DmsRegEqJnc_15]
- **DmsReg_4 {Ni2O3.H2O}**
  -- Measure in the solver coordinate frame: 1.311584
  -- Neighboring regions:
    --- DmsReg_9 {Ni2+} via DmsRegEq_8
    --- DmsReg_3 {Ni3O4.2H2O} via DmsRegEq_18
    --- DmsReg_5 {NiO2.2H2O} via DmsRegEq_16
  -- Junction features: [DmsRegEqJnc_11, DmsRegEqJnc_12, DmsRegEqJnc_15, DmsRegEqJnc_16]
- **DmsReg_5 {NiO2.2H2O}**
  -- Measure in the solver coordinate frame: 7.16632
  -- Neighboring regions:
    --- DmsReg_9 {Ni2+} via DmsRegEq_9
    --- DmsReg_4 {Ni2O3.H2O} via DmsRegEq_16
  -- Junction features: [DmsRegEqJnc_8, DmsRegEqJnc_12, DmsRegEqJnc_16]
#### liquid
- **DmsReg_6 {[Ni(Glyc)3]-}**
  -- Measure in the solver coordinate frame: 3.472416
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_4
    --- DmsReg_2 {Ni(OH)2} via DmsRegEq_10
    --- DmsReg_7 {[Ni(Glyc)2]} via DmsRegEq_1
    --- DmsReg_3 {Ni3O4.2H2O} via DmsRegEq_11
  -- Junction features: [DmsRegEqJnc_1, DmsRegEqJnc_9, DmsRegEqJnc_10, DmsRegEqJnc_4]
- **DmsReg_7 {[Ni(Glyc)2]}**
  -- Measure in the solver coordinate frame: 1.307824
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_5
    --- DmsReg_6 {[Ni(Glyc)3]-} via DmsRegEq_1
    --- DmsReg_8 {[Ni(Glyc)]+} via DmsRegEq_2
    --- DmsReg_3 {Ni3O4.2H2O} via DmsRegEq_12
  -- Junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_4, DmsRegEqJnc_5]
- **DmsReg_8 {[Ni(Glyc)]+}**
  -- Measure in the solver coordinate frame: 0.83832
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_6
    --- DmsReg_7 {[Ni(Glyc)2]} via DmsRegEq_2
    --- DmsReg_9 {Ni2+} via DmsRegEq_3
    --- DmsReg_3 {Ni3O4.2H2O} via DmsRegEq_13
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_5, DmsRegEqJnc_6]
- **DmsReg_9 {Ni2+}**
  -- Measure in the solver coordinate frame: 10.107248
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_7
    --- DmsReg_8 {[Ni(Glyc)]+} via DmsRegEq_3
    --- DmsReg_3 {Ni3O4.2H2O} via DmsRegEq_14
    --- DmsReg_4 {Ni2O3.H2O} via DmsRegEq_8
    --- DmsReg_5 {NiO2.2H2O} via DmsRegEq_9
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_7, DmsRegEqJnc_6, DmsRegEqJnc_11, DmsRegEqJnc_12, DmsRegEqJnc_8]

### boundary curves/equilibria
#### liquid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_1: [Ni(Glyc)3]- | [Ni(Glyc)2]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.916, E_V=-0.429V), (pH=7.972, E_V=-0.421V), (pH=7.972, E_V=0.649V), (pH=7.908, E_V=0.687V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 574, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 11, 546, 573], "t_params": [0.0, 0.0471, 0.938, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.916, E_V=-0.429V), (pH=7.972, E_V=-0.421V), (pH=7.972, E_V=0.649V), (pH=7.908, E_V=0.687V)], "envelope_t": [0.0, 0.0471, 0.938, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=7.916, E_V=-0.429V), (pH=7.972, E_V=-0.421V), (pH=7.972, E_V=0.649V), (pH=7.908, E_V=0.687V)], "adaptive_t": [0.0, 0.0471, 0.938, 1.0]}
- **DmsRegEq_2: [Ni(Glyc)2] | [Ni(Glyc)]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_7, DmsReg_8]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.764, E_V=-0.365V), (pH=6.796, E_V=-0.357V), (pH=6.796, E_V=0.735V), (pH=6.764, E_V=0.765V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 574, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 8, 554, 573], "t_params": [0.0, 0.0282, 0.9625, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.764, E_V=-0.365V), (pH=6.796, E_V=-0.357V), (pH=6.796, E_V=0.735V), (pH=6.764, E_V=0.765V)], "envelope_t": [0.0, 0.0282, 0.9625, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=6.764, E_V=-0.365V), (pH=6.796, E_V=-0.357V), (pH=6.796, E_V=0.735V), (pH=6.764, E_V=0.765V)], "adaptive_t": [0.0, 0.0282, 0.9625, 1.0]}
- **DmsRegEq_3: [Ni(Glyc)]+ | Ni2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_8, DmsReg_9]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.06, E_V=-0.345V), (pH=6.076, E_V=-0.335V), (pH=6.076, E_V=0.841V), (pH=6.06, E_V=0.869V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 612, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 7, 595, 611], "t_params": [0.0, 0.0154, 0.9737, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.06, E_V=-0.345V), (pH=6.076, E_V=-0.335V), (pH=6.076, E_V=0.841V), (pH=6.06, E_V=0.869V)], "envelope_t": [0.0, 0.0154, 0.9737, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=6.06, E_V=-0.345V), (pH=6.076, E_V=-0.335V), (pH=6.076, E_V=0.841V), (pH=6.06, E_V=0.869V)], "adaptive_t": [0.0, 0.0154, 0.9737, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_4: Ni | [Ni(Glyc)3]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=11.236, E_V=-0.549V), (pH=10.22, E_V=-0.545V), (pH=9.748, E_V=-0.537V), (pH=9.436, E_V=-0.527V), (pH=8.74, E_V=-0.489V), (pH=7.916, E_V=-0.429V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "budget", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 476, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 129, 192, 236, 342, 475], "t_params": [0.0, 0.3057, 0.4477, 0.5417, 0.7514, 1.0], "envelope_n": 6, "envelope_pts": [(pH=11.236, E_V=-0.549V), (pH=10.22, E_V=-0.545V), (pH=9.748, E_V=-0.537V), (pH=9.436, E_V=-0.527V), (pH=8.74, E_V=-0.489V), (pH=7.916, E_V=-0.429V)], "envelope_t": [0.0, 0.3057, 0.4477, 0.5417, 0.7514, 1.0], "adaptive_n": 6, "adaptive_pts": [(pH=11.236, E_V=-0.549V), (pH=10.22, E_V=-0.545V), (pH=9.748, E_V=-0.537V), (pH=9.436, E_V=-0.527V), (pH=8.74, E_V=-0.489V), (pH=7.916, E_V=-0.429V)], "adaptive_t": [0.0, 0.3057, 0.4477, 0.5417, 0.7514, 1.0]}
- **DmsRegEq_5: Ni | [Ni(Glyc)2]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.916, E_V=-0.429V), (pH=7.284, E_V=-0.389V), (pH=6.764, E_V=-0.365V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 177, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 99, 176], "t_params": [0.0, 0.5488, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.916, E_V=-0.429V), (pH=7.284, E_V=-0.389V), (pH=6.764, E_V=-0.365V)], "envelope_t": [0.0, 0.5488, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=7.916, E_V=-0.429V), (pH=7.284, E_V=-0.389V), (pH=6.764, E_V=-0.365V)], "adaptive_t": [0.0, 0.5488, 1.0]}
- **DmsRegEq_6: Ni | [Ni(Glyc)]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_8]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.764, E_V=-0.365V), (pH=6.46, E_V=-0.353V), (pH=6.06, E_V=-0.345V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 99, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 44, 98], "t_params": [0.0, 0.432, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.764, E_V=-0.365V), (pH=6.46, E_V=-0.353V), (pH=6.06, E_V=-0.345V)], "envelope_t": [0.0, 0.432, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.764, E_V=-0.365V), (pH=6.46, E_V=-0.353V), (pH=6.06, E_V=-0.345V)], "adaptive_t": [0.0, 0.432, 1.0]}
- **DmsRegEq_7: Ni | Ni2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_9]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.06, E_V=-0.345V), (pH=5.26, E_V=-0.335V), (pH=0, E_V=-0.333V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 765, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 105, 764], "t_params": [0.0, 0.132, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.06, E_V=-0.345V), (pH=5.26, E_V=-0.335V), (pH=0, E_V=-0.333V)], "envelope_t": [0.0, 0.132, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.06, E_V=-0.345V), (pH=5.26, E_V=-0.335V), (pH=0, E_V=-0.333V)], "adaptive_t": [0.0, 0.132, 1.0]}
- **DmsRegEq_8: Ni2+ | Ni2O3.H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_9]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=5.364, E_V=1.013V), (pH=4.892, E_V=1.091V), (pH=4.132, E_V=1.227V)]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_12]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 262, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 98, 261], "t_params": [0.0, 0.3826, 1.0], "envelope_n": 6, "envelope_pts": [(pH=5.364, E_V=1.013V), (pH=4.892, E_V=1.091V), (pH=4.132, E_V=1.227V)], "envelope_t": [0.0, 0.3826, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=5.364, E_V=1.013V), (pH=4.892, E_V=1.091V), (pH=4.132, E_V=1.227V)], "adaptive_t": [0.0, 0.3826, 1.0]}
- **DmsRegEq_9: Ni2+ | NiO2.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_5, DmsReg_9]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.132, E_V=1.227V), (pH=0.972, E_V=1.6V)]
  -- Boundary/junction features: [DmsRegEqJnc_12, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 583, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 582], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.132, E_V=1.227V), (pH=0.972, E_V=1.6V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.132, E_V=1.227V), (pH=0.972, E_V=1.6V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_10: Ni(OH)2 | [Ni(Glyc)3]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=11.236, E_V=-0.549V), (pH=11.236, E_V=0.257V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_10]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 404, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 403], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=11.236, E_V=-0.549V), (pH=11.236, E_V=0.257V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=11.236, E_V=-0.549V), (pH=11.236, E_V=0.257V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox unresolved
- **DmsRegEq_11: [Ni(Glyc)3]- | Ni3O4.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=11.236, E_V=0.257V), (pH=10.22, E_V=0.487V), (pH=9.54, E_V=0.605V), (pH=9.276, E_V=0.635V), (pH=8.948, E_V=0.659V), (pH=7.908, E_V=0.687V)]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "budget", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 632, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 242, 386, 434, 487, 631], "t_params": [0.0, 0.3094, 0.5144, 0.5933, 0.691, 1.0], "envelope_n": 6, "envelope_pts": [(pH=11.236, E_V=0.257V), (pH=10.22, E_V=0.487V), (pH=9.54, E_V=0.605V), (pH=9.276, E_V=0.635V), (pH=8.948, E_V=0.659V), (pH=7.908, E_V=0.687V)], "envelope_t": [0.0, 0.3094, 0.5144, 0.5933, 0.691, 1.0], "adaptive_n": 9, "adaptive_pts": [(pH=11.236, E_V=0.257V), (pH=10.78, E_V=0.365V), (pH=10.22, E_V=0.487V), (pH=9.852, E_V=0.557V), (pH=9.54, E_V=0.605V), (pH=9.276, E_V=0.635V), (pH=8.948, E_V=0.659V), (pH=8.572, E_V=0.673V), (pH=7.908, E_V=0.687V)], "adaptive_t": [0.0, 0.1392, 0.3094, 0.4207, 0.5144, 0.5933, 0.691, 0.8027, 1.0]}
- **DmsRegEq_12: [Ni(Glyc)2] | Ni3O4.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.908, E_V=0.687V), (pH=7.636, E_V=0.697V), (pH=7.316, E_V=0.715V), (pH=7.012, E_V=0.739V), (pH=6.764, E_V=0.765V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 183, "compact_n": 5, "compact_target_n": 6, "compact_indices": [0, 39, 88, 138, 182], "t_params": [0.0, 0.2373, 0.5167, 0.7826, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.908, E_V=0.687V), (pH=7.636, E_V=0.697V), (pH=7.316, E_V=0.715V), (pH=7.012, E_V=0.739V), (pH=6.764, E_V=0.765V)], "envelope_t": [0.0, 0.2373, 0.5167, 0.7826, 1.0], "adaptive_n": 5, "adaptive_pts": [(pH=7.908, E_V=0.687V), (pH=7.636, E_V=0.697V), (pH=7.316, E_V=0.715V), (pH=7.012, E_V=0.739V), (pH=6.764, E_V=0.765V)], "adaptive_t": [0.0, 0.2373, 0.5167, 0.7826, 1.0]}
- **DmsRegEq_13: [Ni(Glyc)]+ | Ni3O4.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_8]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.764, E_V=0.765V), (pH=6.396, E_V=0.813V), (pH=6.06, E_V=0.869V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 141, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 70, 140], "t_params": [0.0, 0.5214, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.764, E_V=0.765V), (pH=6.396, E_V=0.813V), (pH=6.06, E_V=0.869V)], "envelope_t": [0.0, 0.5214, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.764, E_V=0.765V), (pH=6.396, E_V=0.813V), (pH=6.06, E_V=0.869V)], "adaptive_t": [0.0, 0.5214, 1.0]}
- **DmsRegEq_14: Ni2+ | Ni3O4.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_9]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.06, E_V=0.869V), (pH=5.716, E_V=0.935V), (pH=5.364, E_V=1.013V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 160, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 76, 159], "t_params": [0.0, 0.4928, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.06, E_V=0.869V), (pH=5.716, E_V=0.935V), (pH=5.364, E_V=1.013V)], "envelope_t": [0.0, 0.4928, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.06, E_V=0.869V), (pH=5.716, E_V=0.935V), (pH=5.364, E_V=1.013V)], "adaptive_t": [0.0, 0.4928, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_15: Ni | Ni(OH)2**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.711V), (pH=11.236, E_V=-0.549V)]
  -- Boundary/junction features: [DmsRegEqJnc_13, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 428, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 427], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.711V), (pH=11.236, E_V=-0.549V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.711V), (pH=11.236, E_V=-0.549V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_16: Ni2O3.H2O | NiO2.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=0.643V), (pH=4.132, E_V=1.227V)]
  -- Boundary/junction features: [DmsRegEqJnc_16, DmsRegEqJnc_12]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1527, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 1526], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=0.643V), (pH=4.132, E_V=1.227V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=0.643V), (pH=4.132, E_V=1.227V)], "adaptive_t": [0.0, 1.0]}
#### solid–solid · redox unresolved
- **DmsRegEq_17: Ni(OH)2 | Ni3O4.2H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=0.095V), (pH=11.236, E_V=0.257V)]
  -- Boundary/junction features: [DmsRegEqJnc_14, DmsRegEqJnc_10]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 428, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 427], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=0.095V), (pH=11.236, E_V=0.257V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=0.095V), (pH=11.236, E_V=0.257V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_18: Ni3O4.2H2O | Ni2O3.H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=0.501V), (pH=5.364, E_V=1.013V)]
  -- Boundary/junction features: [DmsRegEqJnc_15, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.001, "resolution_tau_norm": 0.001, "stop_epsilon": 0.001, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1337, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 1336], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=0.501V), (pH=5.364, E_V=1.013V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=0.501V), (pH=5.364, E_V=1.013V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### one solid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, [Ni(Glyc)3]-, [Ni(Glyc)2]]
  -- Neighboring regions: [DmsReg_6, DmsReg_7, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_4, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=7.916, E_V=-0.429V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, [Ni(Glyc)2], [Ni(Glyc)]+]
  -- Neighboring regions: [DmsReg_7, DmsReg_8, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_5, DmsRegEq_6]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.764, E_V=-0.365V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, [Ni(Glyc)]+, Ni2+]
  -- Neighboring regions: [DmsReg_8, DmsReg_9, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_6, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.06, E_V=-0.345V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [[Ni(Glyc)3]-, [Ni(Glyc)2], Ni3O4.2H2O]
  -- Neighboring regions: [DmsReg_6, DmsReg_7, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_11, DmsRegEq_12]
  -- At sweep limit: false
  -- Geometry: compact point (pH=7.908, E_V=0.687V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [[Ni(Glyc)2], [Ni(Glyc)]+, Ni3O4.2H2O]
  -- Neighboring regions: [DmsReg_7, DmsReg_8, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_12, DmsRegEq_13]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.764, E_V=0.765V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [[Ni(Glyc)]+, Ni2+, Ni3O4.2H2O]
  -- Neighboring regions: [DmsReg_8, DmsReg_9, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_13, DmsRegEq_14]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.06, E_V=0.869V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_9]
  -- Connected boundary manifolds: [DmsRegEq_7]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=-0.333V)
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni2+, NiO2.2H2O]
  -- Neighboring regions: [DmsReg_5, DmsReg_9]
  -- Connected boundary manifolds: [DmsRegEq_9]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0.972, E_V=1.6V)
#### two solids
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni(OH)2, [Ni(Glyc)3]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_6, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_4, DmsRegEq_10, DmsRegEq_15]
  -- At sweep limit: false
  -- Geometry: compact point (pH=11.236, E_V=-0.549V)
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni(OH)2, [Ni(Glyc)3]-, Ni3O4.2H2O]
  -- Neighboring regions: [DmsReg_2, DmsReg_6, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_10, DmsRegEq_11, DmsRegEq_17]
  -- At sweep limit: false
  -- Geometry: compact point (pH=11.236, E_V=0.257V)
- **DmsRegEqJnc_11** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni2+, Ni3O4.2H2O, Ni2O3.H2O]
  -- Neighboring regions: [DmsReg_4, DmsReg_9, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_8, DmsRegEq_14, DmsRegEq_18]
  -- At sweep limit: false
  -- Geometry: compact point (pH=5.364, E_V=1.013V)
- **DmsRegEqJnc_12** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni2+, Ni2O3.H2O, NiO2.2H2O]
  -- Neighboring regions: [DmsReg_4, DmsReg_9, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_8, DmsRegEq_9, DmsRegEq_16]
  -- At sweep limit: false
  -- Geometry: compact point (pH=4.132, E_V=1.227V)
- **DmsRegEqJnc_13** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni(OH)2]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_15]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.711V)
- **DmsRegEqJnc_14** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni(OH)2, Ni3O4.2H2O]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_17]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=0.095V)
- **DmsRegEqJnc_15** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni3O4.2H2O, Ni2O3.H2O]
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_18]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=0.501V)
- **DmsRegEqJnc_16** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni2O3.H2O, NiO2.2H2O]
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_16]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=0.643V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Ni**
  -- included: [Ni2+, [Ni(OH)]+, [Ni(OH)2], [Ni(OH)3]-, [Ni4(OH)4]4+, [Ni(Glyc)]+, [Ni(Glyc)2], [Ni(Glyc)3]-, Ni(OH)2, Ni3O4.2H2O, Ni2O3.H2O, NiO2.2H2O, Ni]
  -- excluded: [HNiO2-, NiO, [Ni(OH)2](s)]
