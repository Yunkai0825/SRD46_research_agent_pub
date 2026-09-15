# Solver report (Pourbaix)

## System
- Components: [Fe, Chloride ion]
- Constraints:
  -- component totals (M): Fe=0.001;Chloride ion=0.1
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-1V, 1.5V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.0125, ΔE_V=0.003125V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Fe
- Dms_2: [Fe(OH)3]-
- Dms_3: Fe3O4 (anh.)
- Dms_4: [(Fe2O3)0.5(s,alpha)]
- Dms_5: Fe2+
- Dms_6: FeO42-
- Dms_7: Fe3+

## Topology stats
- 7 dominant-species labels
- 7 connected regions
- 10 pairwise boundary curves
- 4 internal junction features
- 8 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.2484375V)
- Fixed sample indices: (pH=swept, E_V=sample 399)
- samples 0–321, (pH=[0.00625, 4.01875], E_V=0.2484375V): Fe2+ (Dms_5)
- samples 322–1119, (pH=[4.03125, 13.99375], E_V=0.2484375V): [(Fe2O3)0.5(s,alpha)] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=[4.01875, 4.03125], E_V=0.2484375V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6.99375, E_V=swept)
- Fixed sample indices: (pH=sample 559, E_V=swept)
- samples 0–147, (pH=6.99375, E_V=[-0.9984375V, -0.5390625V]): Fe (Dms_1)
- samples 148–212, (pH=6.99375, E_V=[-0.5359375V, -0.3359375V]): Fe2+ (Dms_5)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.5390625V, -0.5359375V])
- samples 213–267, (pH=6.99375, E_V=[-0.3328125V, -0.1640625V]): Fe3O4 (anh.) (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.3359375V, -0.3328125V])
- samples 268–638, (pH=6.99375, E_V=[-0.1609375V, 0.9953125V]): [(Fe2O3)0.5(s,alpha)] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.1640625V, -0.1609375V])
- samples 639–799, (pH=6.99375, E_V=[0.9984375V, 1.4984375V]): FeO42- (Dms_6)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[0.9953125V, 0.9984375V])

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
  -- Measure in the solver coordinate frame: 5.3454297
  -- Neighboring regions:
    --- DmsReg_4 {[Fe(OH)3]-} via DmsRegEq_2
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_9
    --- DmsReg_5 {Fe2+} via DmsRegEq_3
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_9, DmsRegEqJnc_10, DmsRegEqJnc_4]
- **DmsReg_2 {Fe3O4 (anh.)}**
  -- Measure in the solver coordinate frame: 2.2657813
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_9
    --- DmsReg_4 {[Fe(OH)3]-} via DmsRegEq_7
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_10
    --- DmsReg_5 {Fe2+} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_10, DmsRegEqJnc_9, DmsRegEqJnc_5, DmsRegEqJnc_12, DmsRegEqJnc_11]
- **DmsReg_3 {[(Fe2O3)0.5(s,alpha)]}**
  -- Measure in the solver coordinate frame: 13.208008
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_10
    --- DmsReg_5 {Fe2+} via DmsRegEq_4
    --- DmsReg_6 {FeO42-} via DmsRegEq_5
    --- DmsReg_7 {Fe3+} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_12, DmsRegEqJnc_11, DmsRegEqJnc_2, DmsRegEqJnc_6, DmsRegEqJnc_7, DmsRegEqJnc_8]
#### liquid
- **DmsReg_4 {[Fe(OH)3]-}**
  -- Measure in the solver coordinate frame: 0.028203125
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_2
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_9, DmsRegEqJnc_5]
- **DmsReg_5 {Fe2+}**
  -- Measure in the solver coordinate frame: 6.1132813
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_3
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_8
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_4
    --- DmsReg_7 {Fe3+} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_10, DmsRegEqJnc_4, DmsRegEqJnc_11, DmsRegEqJnc_2, DmsRegEqJnc_1]
- **DmsReg_6 {FeO42-}**
  -- Measure in the solver coordinate frame: 7.2267188
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_6, DmsRegEqJnc_7]
- **DmsReg_7 {Fe3+}**
  -- Measure in the solver coordinate frame: 0.81257813
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_6
    --- DmsReg_5 {Fe2+} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_8, DmsRegEqJnc_1]

### boundary curves/equilibria
#### liquid–liquid · redox (by species definition)
- **DmsRegEq_1: Fe2+ | Fe3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_5, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=0.7719V), (pH=1.1875, E_V=0.7719V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 96, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 95], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=0.7719V), (pH=1.1875, E_V=0.7719V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=0.7719V), (pH=1.1875, E_V=0.7719V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_2: Fe | [Fe(OH)3]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.9219V), (pH=13.3125, E_V=-0.8594V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 76, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 75], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.9219V), (pH=13.3125, E_V=-0.8594V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.9219V), (pH=13.3125, E_V=-0.8594V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: Fe | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=-0.5375V), (pH=7.8375, E_V=-0.5375V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_10]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 628, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 627], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=-0.5375V), (pH=7.8375, E_V=-0.5375V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=-0.5375V), (pH=7.8375, E_V=-0.5375V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: [(Fe2O3)0.5(s,alpha)] | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.0375, E_V=-0.1062V), (pH=1.6125, E_V=0.675V), (pH=1.4, E_V=0.7156V), (pH=1.1875, E_V=0.7719V)]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 670, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 604, 634, 669], "t_params": [0.0, 0.9115, 0.9554, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.0375, E_V=-0.1062V), (pH=1.6125, E_V=0.675V), (pH=1.4, E_V=0.7156V), (pH=1.1875, E_V=0.7719V)], "envelope_t": [0.0, 0.9115, 0.9554, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=6.0375, E_V=-0.1062V), (pH=1.6125, E_V=0.675V), (pH=1.4, E_V=0.7156V), (pH=1.1875, E_V=0.7719V)], "adaptive_t": [0.0, 0.9115, 0.9554, 1.0]}
- **DmsRegEq_5: [(Fe2O3)0.5(s,alpha)] | FeO42-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=0.3063V), (pH=1.9125, E_V=1.5V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1350, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 1349], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=0.3063V), (pH=1.9125, E_V=1.5V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=0.3063V), (pH=1.9125, E_V=1.5V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_6: [(Fe2O3)0.5(s,alpha)] | Fe3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=1.1875, E_V=0.7719V), (pH=1.1375, E_V=0.8031V), (pH=1.1125, E_V=0.8563V), (pH=1.1125, E_V=1.5V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 240, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 14, 33, 239], "t_params": [0.0, 0.0774, 0.1545, 1.0], "envelope_n": 6, "envelope_pts": [(pH=1.1875, E_V=0.7719V), (pH=1.1375, E_V=0.8031V), (pH=1.1125, E_V=0.8563V), (pH=1.1125, E_V=1.5V)], "envelope_t": [0.0, 0.0774, 0.1545, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=1.1875, E_V=0.7719V), (pH=1.1375, E_V=0.8031V), (pH=1.1125, E_V=0.8563V), (pH=1.1125, E_V=1.5V)], "adaptive_t": [0.0, 0.0774, 0.1545, 1.0]}
#### solid–liquid · redox unresolved
- **DmsRegEq_7: [Fe(OH)3]- | Fe3O4 (anh.)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=13.3125, E_V=-0.8594V), (pH=14, E_V=-0.8406V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 62, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 61], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=13.3125, E_V=-0.8594V), (pH=14, E_V=-0.8406V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=13.3125, E_V=-0.8594V), (pH=14, E_V=-0.8406V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_8: Fe3O4 (anh.) | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.8375, E_V=-0.5375V), (pH=6.25, E_V=-0.1625V), (pH=6.0375, E_V=-0.1062V)]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 1, "separation_added": 0, "anchor_disabled": 1, "raw_n": 283, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 247, 282], "t_params": [0.0, 0.8812, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.8375, E_V=-0.5375V), (pH=6.25, E_V=-0.1625V), (pH=6.0375, E_V=-0.1062V)], "envelope_t": [0.0, 0.8812, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=7.8375, E_V=-0.5375V), (pH=6.0375, E_V=-0.1062V)], "adaptive_t": [0.0, 1.0]}
#### solid–solid · redox unresolved
- **DmsRegEq_9: Fe | Fe3O4 (anh.)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=13.3125, E_V=-0.8594V), (pH=7.8375, E_V=-0.5375V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_10]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 542, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 541], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=13.3125, E_V=-0.8594V), (pH=7.8375, E_V=-0.5375V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=13.3125, E_V=-0.8594V), (pH=7.8375, E_V=-0.5375V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_10: Fe3O4 (anh.) | [(Fe2O3)0.5(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.5781V), (pH=6.0375, E_V=-0.1062V)]
  -- Boundary/junction features: [DmsRegEqJnc_12, DmsRegEqJnc_11]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0016, "resolution_tau_norm": 0.0016, "stop_epsilon": 0.0016, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 1, "raw_n": 789, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 788], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.5781V), (pH=6.0375, E_V=-0.1062V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.5781V), (pH=6.0375, E_V=-0.1062V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, Fe3+]
  -- Neighboring regions: [DmsReg_5, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.7719V)
#### one solid
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe2+, Fe3+]
  -- Neighboring regions: [DmsReg_5, DmsReg_7, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_4, DmsRegEq_6]
  -- At sweep limit: false
  -- Geometry: compact point (pH=1.1875, E_V=0.7719V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, [Fe(OH)3]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.9219V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=-0.5375V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [[Fe(OH)3]-, Fe3O4 (anh.)]
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_7]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.8406V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_5]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=0.3063V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_5]
  -- At sweep limit: true
  -- Geometry: compact point (pH=1.9125, E_V=1.5V)
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=1.1125, E_V=1.5V)
#### two solids
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, [Fe(OH)3]-, Fe3O4 (anh.)]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_7, DmsRegEq_9]
  -- At sweep limit: false
  -- Geometry: compact point (pH=13.3125, E_V=-0.8594V)
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.), Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_5, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_8, DmsRegEq_9]
  -- At sweep limit: false
  -- Geometry: compact point (pH=7.8375, E_V=-0.5375V)
- **DmsRegEqJnc_11** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], Fe2+]
  -- Neighboring regions: [DmsReg_3, DmsReg_5, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_4, DmsRegEq_8, DmsRegEq_10]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.0375, E_V=-0.1062V)
- **DmsRegEqJnc_12** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)]]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_10]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.5781V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Chlo)]+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Chlo)2]+, [Fe(Chlo)]2+, FeO42-, [Fe(OH)2](s), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [FeO(OH)(s,alpha)], Fe]
  -- excluded: [HFeO2-, FeOH2+, Fe(OH)2 (hydr.), [Fe(OH)3](s), Fe(OH)3 (hydr.), Fe2O3 (anh.)]
