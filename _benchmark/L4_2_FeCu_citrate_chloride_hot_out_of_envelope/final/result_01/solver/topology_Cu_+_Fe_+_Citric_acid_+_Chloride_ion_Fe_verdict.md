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
- Dms_1: Fe
- Dms_2: [(Fe2O3)0.5(s,alpha)]
- Dms_3: FeO42-
- Dms_4: [Fe(Citr)]-
- Dms_5: Fe2+
- Dms_6: [Fe(Citr)H]
- Dms_7: [Fe(Chlo)2]+

## Topology stats
- 7 dominant-species labels
- 7 connected regions
- 13 pairwise boundary curves
- 7 internal junction features
- 5 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.098854167V)
- Fixed sample indices: (pH=swept, E_V=sample 479)
- samples 0–224, (pH=[0.00625, 2.80625], E_V=0.098854167V): Fe2+ (Dms_5)
- samples 225–663, (pH=[2.81875, 8.29375], E_V=0.098854167V): [(Fe2O3)0.5(s,alpha)] (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=[2.80625, 2.81875], E_V=0.098854167V)
- samples 664–1119, (pH=[8.30625, 13.99375], E_V=0.098854167V): FeO42- (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=[8.29375, 8.30625], E_V=0.098854167V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6.99375, E_V=swept)
- Fixed sample indices: (pH=sample 559, E_V=swept)
- samples 0–240, (pH=6.99375, E_V=[-0.99885417V, -0.44885417V]): Fe (Dms_1)
- samples 241–535, (pH=6.99375, E_V=[-0.4465625V, 0.2271875V]): [(Fe2O3)0.5(s,alpha)] (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.44885417V, -0.4465625V])
- samples 536–959, (pH=6.99375, E_V=[0.22947917V, 1.1988542V]): FeO42- (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[0.2271875V, 0.22947917V])

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
- **DmsReg_1 {Fe}**
  -- Measure in the solver coordinate frame: 6.8103464
  -- Neighboring regions:
    --- DmsReg_2 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_13
    --- DmsReg_4 {[Fe(Citr)]-} via DmsRegEq_5
    --- DmsReg_6 {Fe2+} via DmsRegEq_6
    --- DmsReg_5 {[Fe(Citr)H]} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_12, DmsRegEqJnc_11, DmsRegEqJnc_3, DmsRegEqJnc_9, DmsRegEqJnc_4]
- **DmsReg_2 {[(Fe2O3)0.5(s,alpha)]}**
  -- Measure in the solver coordinate frame: 7.2575651
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_13
    --- DmsReg_3 {FeO42-} via DmsRegEq_8
    --- DmsReg_4 {[Fe(Citr)]-} via DmsRegEq_9
    --- DmsReg_6 {Fe2+} via DmsRegEq_10
    --- DmsReg_5 {[Fe(Citr)H]} via DmsRegEq_11
    --- DmsReg_7 {[Fe(Chlo)2]+} via DmsRegEq_12
  -- Junction features: [DmsRegEqJnc_12, DmsRegEqJnc_11, DmsRegEqJnc_10, DmsRegEqJnc_8, DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_7]
#### liquid
- **DmsReg_3 {FeO42-}**
  -- Measure in the solver coordinate frame: 13.596716
  -- Neighboring regions:
    --- DmsReg_2 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_8
    --- DmsReg_7 {[Fe(Chlo)2]+} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_10, DmsRegEqJnc_8, DmsRegEqJnc_1]
- **DmsReg_4 {[Fe(Citr)]-}**
  -- Measure in the solver coordinate frame: 0.30822917
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_5
    --- DmsReg_2 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_9
    --- DmsReg_5 {[Fe(Citr)H]} via DmsRegEq_3
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_11, DmsRegEqJnc_5]
- **DmsReg_5 {[Fe(Citr)H]}**
  -- Measure in the solver coordinate frame: 0.040820312
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_7
    --- DmsReg_2 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_11
    --- DmsReg_4 {[Fe(Citr)]-} via DmsRegEq_3
    --- DmsReg_6 {Fe2+} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_4, DmsRegEqJnc_5, DmsRegEqJnc_6]
- **DmsReg_6 {Fe2+}**
  -- Measure in the solver coordinate frame: 2.3102005
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_6
    --- DmsReg_2 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_10
    --- DmsReg_5 {[Fe(Citr)H]} via DmsRegEq_4
    --- DmsReg_7 {[Fe(Chlo)2]+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_4, DmsRegEqJnc_6, DmsRegEqJnc_7, DmsRegEqJnc_2]
- **DmsReg_7 {[Fe(Chlo)2]+}**
  -- Measure in the solver coordinate frame: 0.4761224
  -- Neighboring regions:
    --- DmsReg_2 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_12
    --- DmsReg_3 {FeO42-} via DmsRegEq_1
    --- DmsReg_6 {Fe2+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_7, DmsRegEqJnc_8, DmsRegEqJnc_1, DmsRegEqJnc_2]

### boundary curves/equilibria
#### liquid–liquid · redox (by species definition)
- **DmsRegEq_1: FeO42- | [Fe(Chlo)2]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=1.0875, E_V=0.799V), (pH=0, E_V=0.9708V)]
  -- Boundary/junction features: [DmsRegEqJnc_8, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 163, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 162], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=1.0875, E_V=0.799V), (pH=0, E_V=0.9708V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=1.0875, E_V=0.799V), (pH=0, E_V=0.9708V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_2: Fe2+ | [Fe(Chlo)2]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=0.4323V), (pH=1.0875, E_V=0.4323V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 88, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 87], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=0.4323V), (pH=1.0875, E_V=0.4323V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=0.4323V), (pH=1.0875, E_V=0.4323V)], "adaptive_t": [0.0, 1.0]}
#### liquid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_3: [Fe(Citr)]- | [Fe(Citr)H]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.15, E_V=-0.3652V), (pH=4.15, E_V=-0.1085V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 113, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 112], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.15, E_V=-0.3652V), (pH=4.15, E_V=-0.1085V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.15, E_V=-0.3652V), (pH=4.15, E_V=-0.1085V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: Fe2+ | [Fe(Citr)H]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.9625, E_V=-0.3606V), (pH=4, E_V=-0.3537V), (pH=4, E_V=-0.104V), (pH=3.9625, E_V=-0.0833V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 128, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 6, 115, 127], "t_params": [0.0, 0.1153, 0.8706, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.9625, E_V=-0.3606V), (pH=4, E_V=-0.3537V), (pH=4, E_V=-0.104V), (pH=3.9625, E_V=-0.0833V)], "envelope_t": [0.0, 0.1153, 0.8706, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=3.9625, E_V=-0.3606V), (pH=4, E_V=-0.3537V), (pH=4, E_V=-0.104V), (pH=3.9625, E_V=-0.0833V)], "adaptive_t": [0.0, 0.1153, 0.8706, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_5: Fe | [Fe(Citr)]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.2875, E_V=-0.4065V), (pH=5.3125, E_V=-0.3973V), (pH=4.15, E_V=-0.3652V)]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 190, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 82, 189], "t_params": [0.0, 0.4561, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.2875, E_V=-0.4065V), (pH=5.3125, E_V=-0.3973V), (pH=4.15, E_V=-0.3652V)], "envelope_t": [0.0, 0.4561, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.2875, E_V=-0.4065V), (pH=5.3125, E_V=-0.3973V), (pH=4.15, E_V=-0.3652V)], "adaptive_t": [0.0, 0.4561, 1.0]}
- **DmsRegEq_6: Fe | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.9625, E_V=-0.3606V), (pH=2.85, E_V=-0.3492V), (pH=0, E_V=-0.3492V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 323, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 94, 322], "t_params": [0.0, 0.2808, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.9625, E_V=-0.3606V), (pH=2.85, E_V=-0.3492V), (pH=0, E_V=-0.3492V)], "envelope_t": [0.0, 0.2808, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=3.9625, E_V=-0.3606V), (pH=2.85, E_V=-0.3492V), (pH=0, E_V=-0.3492V)], "adaptive_t": [0.0, 0.2808, 1.0]}
- **DmsRegEq_7: Fe | [Fe(Citr)H]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.15, E_V=-0.3652V), (pH=3.9625, E_V=-0.3606V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 18, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 17], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.15, E_V=-0.3652V), (pH=3.9625, E_V=-0.3606V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.15, E_V=-0.3652V), (pH=3.9625, E_V=-0.3606V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_8: [(Fe2O3)0.5(s,alpha)] | FeO42-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.4615V), (pH=1.5375, E_V=0.7669V), (pH=1.2, E_V=0.7967V), (pH=1.0875, E_V=0.799V)]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1584, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 1533, 1573, 1583], "t_params": [0.0, 0.9652, 0.9913, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.4615V), (pH=1.5375, E_V=0.7669V), (pH=1.2, E_V=0.7967V), (pH=1.0875, E_V=0.799V)], "envelope_t": [0.0, 0.9652, 0.9913, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=14, E_V=-0.4615V), (pH=1.5375, E_V=0.7669V), (pH=1.2, E_V=0.7967V), (pH=1.0875, E_V=0.799V)], "adaptive_t": [0.0, 0.9652, 0.9913, 1.0]}
- **DmsRegEq_9: [(Fe2O3)0.5(s,alpha)] | [Fe(Citr)]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.2875, E_V=-0.4065V), (pH=5.9875, E_V=-0.3537V), (pH=5.4625, E_V=-0.2735V), (pH=4.95, E_V=-0.2048V), (pH=4.15, E_V=-0.1085V)]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 302, "compact_n": 5, "compact_target_n": 6, "compact_indices": [0, 47, 124, 195, 301], "t_params": [0.0, 0.1411, 0.3872, 0.6267, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.2875, E_V=-0.4065V), (pH=5.9875, E_V=-0.3537V), (pH=5.4625, E_V=-0.2735V), (pH=4.95, E_V=-0.2048V), (pH=4.15, E_V=-0.1085V)], "envelope_t": [0.0, 0.1411, 0.3872, 0.6267, 1.0], "adaptive_n": 5, "adaptive_pts": [(pH=6.2875, E_V=-0.4065V), (pH=5.9875, E_V=-0.3537V), (pH=5.4625, E_V=-0.2735V), (pH=4.95, E_V=-0.2048V), (pH=4.15, E_V=-0.1085V)], "adaptive_t": [0.0, 0.1411, 0.3872, 0.6267, 1.0]}
- **DmsRegEq_10: [(Fe2O3)0.5(s,alpha)] | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.9625, E_V=-0.0833V), (pH=3.05, E_V=0.0565V), (pH=1.7375, E_V=0.2856V), (pH=1.2875, E_V=0.3704V), (pH=1.1375, E_V=0.4094V), (pH=1.0875, E_V=0.4323V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "budget", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 456, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 134, 339, 412, 441, 455], "t_params": [0.0, 0.3158, 0.7715, 0.9282, 0.9812, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.9625, E_V=-0.0833V), (pH=3.05, E_V=0.0565V), (pH=1.7375, E_V=0.2856V), (pH=1.2875, E_V=0.3704V), (pH=1.1375, E_V=0.4094V), (pH=1.0875, E_V=0.4323V)], "envelope_t": [0.0, 0.3158, 0.7715, 0.9282, 0.9812, 1.0], "adaptive_n": 6, "adaptive_pts": [(pH=3.9625, E_V=-0.0833V), (pH=3.05, E_V=0.0565V), (pH=1.7375, E_V=0.2856V), (pH=1.2875, E_V=0.3704V), (pH=1.1375, E_V=0.4094V), (pH=1.0875, E_V=0.4323V)], "adaptive_t": [0.0, 0.3158, 0.7715, 0.9282, 0.9812, 1.0]}
- **DmsRegEq_11: [(Fe2O3)0.5(s,alpha)] | [Fe(Citr)H]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.15, E_V=-0.1085V), (pH=3.9625, E_V=-0.0833V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 27, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 26], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.15, E_V=-0.1085V), (pH=3.9625, E_V=-0.0833V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.15, E_V=-0.1085V), (pH=3.9625, E_V=-0.0833V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_12: [(Fe2O3)0.5(s,alpha)] | [Fe(Chlo)2]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=1.0875, E_V=0.4323V), (pH=1.0375, E_V=0.4919V), (pH=1.0375, E_V=0.7875V), (pH=1.0875, E_V=0.799V)]
  -- Boundary/junction features: [DmsRegEqJnc_7, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 169, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 30, 159, 168], "t_params": [0.0, 0.1831, 0.8792, 1.0], "envelope_n": 6, "envelope_pts": [(pH=1.0875, E_V=0.4323V), (pH=1.0375, E_V=0.4919V), (pH=1.0375, E_V=0.7875V), (pH=1.0875, E_V=0.799V)], "envelope_t": [0.0, 0.1831, 0.8792, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=1.0875, E_V=0.4323V), (pH=1.0375, E_V=0.4919V), (pH=1.0375, E_V=0.7875V), (pH=1.0875, E_V=0.799V)], "adaptive_t": [0.0, 0.1831, 0.8792, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_13: Fe | [(Fe2O3)0.5(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.8625V), (pH=6.2875, E_V=-0.4065V)]
  -- Boundary/junction features: [DmsRegEqJnc_12, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 817, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 816], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.8625V), (pH=6.2875, E_V=-0.4065V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.8625V), (pH=6.2875, E_V=-0.4065V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [FeO42-, [Fe(Chlo)2]+]
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.9708V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, [Fe(Chlo)2]+]
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.4323V)
#### one solid
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, [Fe(Citr)]-, [Fe(Citr)H]]
  -- Neighboring regions: [DmsReg_4, DmsReg_5, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_5, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=4.15, E_V=-0.3652V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe2+, [Fe(Citr)H]]
  -- Neighboring regions: [DmsReg_5, DmsReg_6, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_4, DmsRegEq_6, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=3.9625, E_V=-0.3606V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], [Fe(Citr)]-, [Fe(Citr)H]]
  -- Neighboring regions: [DmsReg_4, DmsReg_5, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_9, DmsRegEq_11]
  -- At sweep limit: false
  -- Geometry: compact point (pH=4.15, E_V=-0.1085V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe2+, [Fe(Citr)H]]
  -- Neighboring regions: [DmsReg_5, DmsReg_6, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_4, DmsRegEq_10, DmsRegEq_11]
  -- At sweep limit: false
  -- Geometry: compact point (pH=3.9625, E_V=-0.0833V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe2+, [Fe(Chlo)2]+]
  -- Neighboring regions: [DmsReg_6, DmsReg_7, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_10, DmsRegEq_12]
  -- At sweep limit: false
  -- Geometry: compact point (pH=1.0875, E_V=0.4323V)
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-, [Fe(Chlo)2]+]
  -- Neighboring regions: [DmsReg_3, DmsReg_7, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_8, DmsRegEq_12]
  -- At sweep limit: false
  -- Geometry: compact point (pH=1.0875, E_V=0.799V)
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=-0.3492V)
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.4615V)
#### two solids
- **DmsRegEqJnc_11** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, [(Fe2O3)0.5(s,alpha)], [Fe(Citr)]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_5, DmsRegEq_9, DmsRegEq_13]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.2875, E_V=-0.4065V)
- **DmsRegEqJnc_12** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, [(Fe2O3)0.5(s,alpha)]]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_13]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.8625V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Cu**
  -- included: [Cu+, [Cu2(Chlo)4]2-, [Cu(Chlo)2]-, [Cu(Chlo)3]2-, [Cu(Chlo)], Cu2+, [Cu(OH)]+, [Cu2(OH)2]2+, [Cu(OH)2], HCuO2-, [Cu3(OH)4]2+, CuO22-, [Cu(Citr)H], [Cu2(Citr)2]2-, [Cu2(Citr)(OH)], [Cu2(Citr)2(OH)]3-, [Cu2(Citr)2(OH)2]4-, [Cu(Chlo)]+, [(Cu2O)0.5](s), [Cu(Chloride ion)](s), CuO(s), Cu]
  -- excluded: [Cu2O, CuO, [Cu(OH)2](s), Cu(OH)2]
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Citr)H2]+, [Fe(Citr)H], [Fe(Citr)2H]3-, [Fe(Citr)]-, [Fe2(Citr)2(OH)2]4-, [Fe(Chlo)]+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Citr)H]+, [Fe(Citr)], [Fe(Citr)(OH)]-, [Fe2(Citr)2(OH)2]2-, [Fe(Chlo)2]+, [Fe(Chlo)]2+, FeO42-, [Fe(OH)2](s), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe]
  -- excluded: [HFeO2-, FeOH2+, Fe(OH)2 (hydr.), Fe(OH)3 (hydr.), Fe2O3 (anh.)]
