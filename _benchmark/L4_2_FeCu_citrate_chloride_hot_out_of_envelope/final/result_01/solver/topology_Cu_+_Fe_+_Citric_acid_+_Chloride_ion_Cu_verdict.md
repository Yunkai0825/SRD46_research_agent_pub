# Solver report (Pourbaix)

## System
- Components: [Cu, Fe, Citric acid, Chloride ion]
- Constraints:
  -- component totals (M): Cu=0.001;Fe=0.001;Citric acid=0.005;Chloride ion=0.1
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-1V, 1.2V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.0125, ΔE_V=0.0022916667V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Cu
- Dms_2: [(Cu2O)0.5](s)
- Dms_3: CuO(s)
- Dms_4: [Cu(Chlo)2]-
- Dms_5: [Cu2(Citr)2(OH)2]4-
- Dms_6: [Cu2(Citr)2(OH)]3-
- Dms_7: [Cu(Citr)H]
- Dms_8: Cu2+

## Topology stats
- 8 dominant-species labels
- 8 connected regions
- 13 pairwise boundary curves
- 6 internal junction features
- 8 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.098854167V)
- Fixed sample indices: (pH=swept, E_V=sample 479)
- samples 0–416, (pH=[0.00625, 5.20625], E_V=0.098854167V): [Cu(Chlo)2]- (Dms_4)
- samples 417–821, (pH=[5.21875, 10.26875], E_V=0.098854167V): [Cu2(Citr)2(OH)2]4- (Dms_5)
  -- preceding label change is bracketed by adjacent samples (pH=[5.20625, 5.21875], E_V=0.098854167V)
- samples 822–1119, (pH=[10.28125, 13.99375], E_V=0.098854167V): CuO(s) (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=[10.26875, 10.28125], E_V=0.098854167V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6.99375, E_V=swept)
- Fixed sample indices: (pH=sample 559, E_V=swept)
- samples 0–366, (pH=6.99375, E_V=[-0.99885417V, -0.16010417V]): Cu (Dms_1)
- samples 367–420, (pH=6.99375, E_V=[-0.1578125V, -0.036354167V]): [(Cu2O)0.5](s) (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.16010417V, -0.1578125V])
- samples 421–959, (pH=6.99375, E_V=[-0.0340625V, 1.1988542V]): [Cu2(Citr)2(OH)2]4- (Dms_5)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.036354167V, -0.0340625V])

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
- **DmsReg_1 {Cu}**
  -- Measure in the solver coordinate frame: 10.465927
  -- Neighboring regions:
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_12
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_13, DmsRegEqJnc_11, DmsRegEqJnc_9]
- **DmsReg_2 {[(Cu2O)0.5](s)}**
  -- Measure in the solver coordinate frame: 1.9974167
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_12
    --- DmsReg_3 {CuO(s)} via DmsRegEq_13
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_10
    --- DmsReg_5 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_9
  -- Junction features: [DmsRegEqJnc_13, DmsRegEqJnc_11, DmsRegEqJnc_12, DmsRegEqJnc_14, DmsRegEqJnc_8]
- **DmsReg_3 {CuO(s)}**
  -- Measure in the solver coordinate frame: 4.9796771
  -- Neighboring regions:
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_13
    --- DmsReg_5 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_11
  -- Junction features: [DmsRegEqJnc_12, DmsRegEqJnc_14, DmsRegEqJnc_10]
#### liquid
- **DmsReg_4 {[Cu(Chlo)2]-}**
  -- Measure in the solver coordinate frame: 2.4551198
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_8
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_10
    --- DmsReg_5 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_1
    --- DmsReg_6 {[Cu2(Citr)2(OH)]3-} via DmsRegEq_2
    --- DmsReg_7 {[Cu(Citr)H]} via DmsRegEq_3
    --- DmsReg_8 {Cu2+} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_11, DmsRegEqJnc_8, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_4]
- **DmsReg_5 {[Cu2(Citr)2(OH)2]4-}**
  -- Measure in the solver coordinate frame: 6.5080469
  -- Neighboring regions:
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_9
    --- DmsReg_3 {CuO(s)} via DmsRegEq_11
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_1
    --- DmsReg_6 {[Cu2(Citr)2(OH)]3-} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_8, DmsRegEqJnc_12, DmsRegEqJnc_10, DmsRegEqJnc_1, DmsRegEqJnc_5]
- **DmsReg_6 {[Cu2(Citr)2(OH)]3-}**
  -- Measure in the solver coordinate frame: 1.3236953
  -- Neighboring regions:
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_2
    --- DmsReg_5 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_5
    --- DmsReg_7 {[Cu(Citr)H]} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_5, DmsRegEqJnc_6]
- **DmsReg_7 {[Cu(Citr)H]}**
  -- Measure in the solver coordinate frame: 0.21094792
  -- Neighboring regions:
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_3
    --- DmsReg_6 {[Cu2(Citr)2(OH)]3-} via DmsRegEq_6
    --- DmsReg_8 {Cu2+} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_6, DmsRegEqJnc_7]
- **DmsReg_8 {Cu2+}**
  -- Measure in the solver coordinate frame: 2.8591693
  -- Neighboring regions:
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_4
    --- DmsReg_7 {[Cu(Citr)H]} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_3, DmsRegEqJnc_7]

### boundary curves/equilibria
#### liquid–liquid · redox (by species definition)
- **DmsRegEq_1: [Cu(Chlo)2]- | [Cu2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.95, E_V=-0.0352V), (pH=6.6375, E_V=-0.0238V), (pH=5.9, E_V=0.029V), (pH=5.2625, E_V=0.0908V), (pH=4.8625, E_V=0.1435V)]
  -- Boundary/junction features: [DmsRegEqJnc_8, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 246, "compact_n": 5, "compact_target_n": 6, "compact_indices": [0, 30, 112, 190, 245], "t_params": [0.0, 0.1492, 0.5019, 0.8075, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.95, E_V=-0.0352V), (pH=6.6375, E_V=-0.0238V), (pH=5.9, E_V=0.029V), (pH=5.2625, E_V=0.0908V), (pH=4.8625, E_V=0.1435V)], "envelope_t": [0.0, 0.1492, 0.5019, 0.8075, 1.0], "adaptive_n": 5, "adaptive_pts": [(pH=6.95, E_V=-0.0352V), (pH=6.6375, E_V=-0.0238V), (pH=5.9, E_V=0.029V), (pH=5.2625, E_V=0.0908V), (pH=4.8625, E_V=0.1435V)], "adaptive_t": [0.0, 0.1492, 0.5019, 0.8075, 1.0]}
- **DmsRegEq_2: [Cu(Chlo)2]- | [Cu2(Citr)2(OH)]3-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.8625, E_V=0.1435V), (pH=4.5875, E_V=0.1665V), (pH=4.2, E_V=0.21V), (pH=3.85, E_V=0.2581V), (pH=3.55, E_V=0.3085V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 178, "compact_n": 5, "compact_target_n": 6, "compact_indices": [0, 32, 82, 131, 177], "t_params": [0.0, 0.2085, 0.5032, 0.7701, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.8625, E_V=0.1435V), (pH=4.5875, E_V=0.1665V), (pH=4.2, E_V=0.21V), (pH=3.85, E_V=0.2581V), (pH=3.55, E_V=0.3085V)], "envelope_t": [0.0, 0.2085, 0.5032, 0.7701, 1.0], "adaptive_n": 5, "adaptive_pts": [(pH=4.8625, E_V=0.1435V), (pH=4.5875, E_V=0.1665V), (pH=4.2, E_V=0.21V), (pH=3.85, E_V=0.2581V), (pH=3.55, E_V=0.3085V)], "adaptive_t": [0.0, 0.2085, 0.5032, 0.7701, 1.0]}
- **DmsRegEq_3: [Cu(Chlo)2]- | [Cu(Citr)H]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.55, E_V=0.3085V), (pH=3.2625, E_V=0.3269V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 32, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 31], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.55, E_V=0.3085V), (pH=3.2625, E_V=0.3269V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=3.55, E_V=0.3085V), (pH=3.2625, E_V=0.3269V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: [Cu(Chlo)2]- | Cu2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_8]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=0.3269V), (pH=3.2625, E_V=0.3269V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 262, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 261], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=0.3269V), (pH=3.2625, E_V=0.3269V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=0.3269V), (pH=3.2625, E_V=0.3269V)], "adaptive_t": [0.0, 1.0]}
#### liquid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_5: [Cu2(Citr)2(OH)2]4- | [Cu2(Citr)2(OH)]3-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.8625, E_V=0.1435V), (pH=4.8625, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 462, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 461], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.8625, E_V=0.1435V), (pH=4.8625, E_V=1.2V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.8625, E_V=0.1435V), (pH=4.8625, E_V=1.2V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_6: [Cu2(Citr)2(OH)]3- | [Cu(Citr)H]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.55, E_V=0.3085V), (pH=3.5125, E_V=0.3819V), (pH=3.5125, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 393, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 35, 392], "t_params": [0.0, 0.0915, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.55, E_V=0.3085V), (pH=3.5125, E_V=0.3819V), (pH=3.5125, E_V=1.2V)], "envelope_t": [0.0, 0.0915, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=3.55, E_V=0.3085V), (pH=3.5125, E_V=0.3819V), (pH=3.5125, E_V=1.2V)], "adaptive_t": [0.0, 0.0915, 1.0]}
- **DmsRegEq_7: [Cu(Citr)H] | Cu2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_7, DmsReg_8]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.2625, E_V=0.3269V), (pH=3.275, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 383, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 382], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.2625, E_V=0.3269V), (pH=3.275, E_V=1.2V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=3.2625, E_V=0.3269V), (pH=3.275, E_V=1.2V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_8: Cu | [Cu(Chlo)2]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=-0.1383V), (pH=6.675, E_V=-0.1383V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 535, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 534], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=-0.1383V), (pH=6.675, E_V=-0.1383V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=-0.1383V), (pH=6.675, E_V=-0.1383V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_9: [(Cu2O)0.5](s) | [Cu2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.95, E_V=-0.0352V), (pH=7.3875, E_V=-0.0283V), (pH=8.0375, E_V=-0.026V), (pH=10.275, E_V=-0.026V)]
  -- Boundary/junction features: [DmsRegEqJnc_8, DmsRegEqJnc_12]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 271, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 38, 91, 270], "t_params": [0.0, 0.1316, 0.3271, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.95, E_V=-0.0352V), (pH=7.3875, E_V=-0.0283V), (pH=8.0375, E_V=-0.026V), (pH=10.275, E_V=-0.026V)], "envelope_t": [0.0, 0.1316, 0.3271, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=6.95, E_V=-0.0352V), (pH=7.3875, E_V=-0.0283V), (pH=8.0375, E_V=-0.026V), (pH=10.275, E_V=-0.026V)], "adaptive_t": [0.0, 0.1316, 0.3271, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_10: [(Cu2O)0.5](s) | [Cu(Chlo)2]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.675, E_V=-0.1383V), (pH=6.6875, E_V=-0.065V), (pH=6.7625, E_V=-0.0467V), (pH=6.95, E_V=-0.0352V)]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 68, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 33, 47, 67], "t_params": [0.0, 0.2192, 0.4466, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.675, E_V=-0.1383V), (pH=6.6875, E_V=-0.065V), (pH=6.7625, E_V=-0.0467V), (pH=6.95, E_V=-0.0352V)], "envelope_t": [0.0, 0.2192, 0.4466, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=6.675, E_V=-0.1383V), (pH=6.6875, E_V=-0.065V), (pH=6.7625, E_V=-0.0467V), (pH=6.95, E_V=-0.0352V)], "adaptive_t": [0.0, 0.2192, 0.4466, 1.0]}
- **DmsRegEq_11: CuO(s) | [Cu2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=10.275, E_V=-0.026V), (pH=10.275, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_12, DmsRegEqJnc_10]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 536, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 535], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=10.275, E_V=-0.026V), (pH=10.275, E_V=1.2V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=10.275, E_V=-0.026V), (pH=10.275, E_V=1.2V)], "adaptive_t": [0.0, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_12: Cu | [(Cu2O)0.5](s)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.5737V), (pH=6.675, E_V=-0.1383V)]
  -- Boundary/junction features: [DmsRegEqJnc_13, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 777, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 776], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.5737V), (pH=6.675, E_V=-0.1383V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.5737V), (pH=6.675, E_V=-0.1383V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_13: [(Cu2O)0.5](s) | CuO(s)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.246V), (pH=10.275, E_V=-0.026V)]
  -- Boundary/junction features: [DmsRegEqJnc_14, DmsRegEqJnc_12]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 395, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 394], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.246V), (pH=10.275, E_V=-0.026V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.246V), (pH=10.275, E_V=-0.026V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, [Cu2(Citr)2(OH)2]4-, [Cu2(Citr)2(OH)]3-]
  -- Neighboring regions: [DmsReg_4, DmsReg_5, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_2, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=4.8625, E_V=0.1435V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, [Cu2(Citr)2(OH)]3-, [Cu(Citr)H]]
  -- Neighboring regions: [DmsReg_4, DmsReg_6, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_3, DmsRegEq_6]
  -- At sweep limit: false
  -- Geometry: compact point (pH=3.55, E_V=0.3085V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, [Cu(Citr)H], Cu2+]
  -- Neighboring regions: [DmsReg_4, DmsReg_7, DmsReg_8]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_4, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=3.2625, E_V=0.3269V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, Cu2+]
  -- Neighboring regions: [DmsReg_4, DmsReg_8]
  -- Connected boundary manifolds: [DmsRegEq_4]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.3269V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu2(Citr)2(OH)2]4-, [Cu2(Citr)2(OH)]3-]
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_5]
  -- At sweep limit: true
  -- Geometry: compact point (pH=4.8625, E_V=1.2V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu2(Citr)2(OH)]3-, [Cu(Citr)H]]
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=3.5125, E_V=1.2V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Citr)H], Cu2+]
  -- Neighboring regions: [DmsReg_7, DmsReg_8]
  -- Connected boundary manifolds: [DmsRegEq_7]
  -- At sweep limit: true
  -- Geometry: compact point (pH=3.275, E_V=1.2V)
#### one solid
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Cu2O)0.5](s), [Cu(Chlo)2]-, [Cu2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_4, DmsReg_5, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_9, DmsRegEq_10]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.95, E_V=-0.0352V)
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [Cu(Chlo)2]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=-0.1383V)
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [CuO(s), [Cu2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_11]
  -- At sweep limit: true
  -- Geometry: compact point (pH=10.275, E_V=1.2V)
#### two solids
- **DmsRegEqJnc_11** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [(Cu2O)0.5](s), [Cu(Chlo)2]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_8, DmsRegEq_10, DmsRegEq_12]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.675, E_V=-0.1383V)
- **DmsRegEqJnc_12** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Cu2O)0.5](s), CuO(s), [Cu2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_2, DmsReg_5, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_9, DmsRegEq_11, DmsRegEq_13]
  -- At sweep limit: false
  -- Geometry: compact point (pH=10.275, E_V=-0.026V)
- **DmsRegEqJnc_13** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [(Cu2O)0.5](s)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_12]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.5737V)
- **DmsRegEqJnc_14** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Cu2O)0.5](s), CuO(s)]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_13]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.246V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Cu**
  -- included: [Cu+, [Cu2(Chlo)4]2-, [Cu(Chlo)2]-, [Cu(Chlo)3]2-, [Cu(Chlo)], Cu2+, [Cu(OH)]+, [Cu2(OH)2]2+, [Cu(OH)2], HCuO2-, [Cu3(OH)4]2+, CuO22-, [Cu(Citr)H], [Cu2(Citr)2]2-, [Cu2(Citr)(OH)], [Cu2(Citr)2(OH)]3-, [Cu2(Citr)2(OH)2]4-, [Cu(Chlo)]+, [(Cu2O)0.5](s), [Cu(Chloride ion)](s), CuO(s), Cu]
  -- excluded: [Cu2O, CuO, [Cu(OH)2](s), Cu(OH)2]
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Citr)H2]+, [Fe(Citr)H], [Fe(Citr)2H]3-, [Fe(Citr)]-, [Fe2(Citr)2(OH)2]4-, [Fe(Chlo)]+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Citr)H]+, [Fe(Citr)], [Fe(Citr)(OH)]-, [Fe2(Citr)2(OH)2]2-, [Fe(Chlo)2]+, [Fe(Chlo)]2+, FeO42-, [Fe(OH)2](s), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe]
  -- excluded: [HFeO2-, FeOH2+, Fe(OH)2 (hydr.), Fe(OH)3 (hydr.), Fe2O3 (anh.)]
