# Solver report (Pourbaix)

## System
- Components: [Fe, DMF]
- Constraints:
  -- component totals (M): Fe=0.1;DMF=1
- Potential reference: SHE
- Domain: pH [0, 14]; E_V [-1, 1.5]
- Coarse grid spacing: ΔpH=not reported; ΔE_V=not reported
- Final classified-grid spacing: ΔpH=0.0125; ΔE_V=0.003125
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Fe
- Dms_2: Fe3O4 (anh.)
- Dms_3: [(Fe2O3)0.5(s,alpha)]
- Dms_4: [Fe(DMF)4]2+
- Dms_5: FeO42-
- Dms_6: [Fe(DMF)]3+

## Topology stats
- 6 dominant-species labels
- 7 connected regions
- 10 pairwise boundary curves
- 4 internal junction features
- 7 junction features at a sweep limit
- Disconnected dominant species:
  -- Fe3O4 (anh.): 2 separate regions [DmsReg_2, DmsReg_5]

## Example classified-grid cut along pH
- Fixed coordinates in domain order: [not reported, 0.2484375]
- Fixed sample indices in domain order: [None, 399]
- samples 0–324, pH [0.00625, 4.05625]: [Fe(DMF)4]2+ (Dms_4)
- samples 325–1119, pH [4.06875, 13.99375]: [(Fe2O3)0.5(s,alpha)] (Dms_3)
  -- preceding label change is bracketed by adjacent samples [4.05625, 4.06875]

## Example classified-grid cut along E_V
- Fixed coordinates in domain order: [6.99375, not reported]
- Fixed sample indices in domain order: [559, None]
- samples 0–146, E_V [-0.9984375, -0.5421875]: Fe (Dms_1)
- samples 147–215, E_V [-0.5390625, -0.3265625]: [Fe(DMF)4]2+ (Dms_4)
  -- preceding label change is bracketed by adjacent samples [-0.5421875, -0.5390625]
- samples 216–267, E_V [-0.3234375, -0.1640625]: Fe3O4 (anh.) (Dms_2)
  -- preceding label change is bracketed by adjacent samples [-0.3265625, -0.3234375]
- samples 268–651, E_V [-0.1609375, 1.0359375]: [(Fe2O3)0.5(s,alpha)] (Dms_3)
  -- preceding label change is bracketed by adjacent samples [-0.1640625, -0.1609375]
- samples 652–799, E_V [1.0390625, 1.4984375]: FeO42- (Dms_5)
  -- preceding label change is bracketed by adjacent samples [1.0359375, 1.0390625]

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
- **DmsReg_1 {Fe}**
  -- Measure in the solver coordinate frame: 5.3278906
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_1
    --- DmsReg_4 {[Fe(DMF)4]2+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_6]
- **DmsReg_2 {Fe3O4 (anh.)}**
  -- Measure in the solver coordinate frame: 2.26875
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_1
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_3
    --- DmsReg_4 {[Fe(DMF)4]2+} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_7]
- **DmsReg_3 {[(Fe2O3)0.5(s,alpha)]}**
  -- Measure in the solver coordinate frame: 13.929258
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_3
    --- DmsReg_5 {Fe3O4 (anh.)} via DmsRegEq_4
    --- DmsReg_4 {[Fe(DMF)4]2+} via DmsRegEq_7
    --- DmsReg_6 {FeO42-} via DmsRegEq_8
    --- DmsReg_7 {[Fe(DMF)]3+} via DmsRegEq_9
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_7, DmsRegEqJnc_3, DmsRegEqJnc_4, DmsRegEqJnc_8, DmsRegEqJnc_9, DmsRegEqJnc_10]
- **DmsReg_4 {[Fe(DMF)4]2+}**
  -- Measure in the solver coordinate frame: 6.2419531
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_2
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_5
    --- DmsReg_5 {Fe3O4 (anh.)} via DmsRegEq_6
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_7
    --- DmsReg_7 {[Fe(DMF)]3+} via DmsRegEq_10
  -- Junction features: [DmsRegEqJnc_6, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_4, DmsRegEqJnc_11]
- **DmsReg_5 {Fe3O4 (anh.)}**
  -- Measure in the solver coordinate frame: 3.90625e-05
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_4
    --- DmsReg_4 {[Fe(DMF)4]2+} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
- **DmsReg_6 {FeO42-}**
  -- Measure in the solver coordinate frame: 6.7570313
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_8, DmsRegEqJnc_9]
- **DmsReg_7 {[Fe(DMF)]3+}**
  -- Measure in the solver coordinate frame: 0.47507813
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_9
    --- DmsReg_4 {[Fe(DMF)4]2+} via DmsRegEq_10
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_10, DmsRegEqJnc_11]

### boundary curves/equilibria
- **DmsRegEq_1: Fe | Fe3O4 (anh.)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, -0.9031], [13.7875, -0.8875], [13.5125, -0.875], [13.3125, -0.8594], [13.0375, -0.8469], [7.9, -0.5406]]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 605, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 22, 48, 69, 95, 604], "t_params": [0.0, 0.0349, 0.0799, 0.1127, 0.1578, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, -0.9031], [13.7875, -0.8875], [13.5125, -0.875], [13.3125, -0.8594], [13.0375, -0.8469], [7.9, -0.5406]], "envelope_t": [0.0, 0.0349, 0.0799, 0.1127, 0.1578, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, -0.9031], [7.9, -0.5406]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_2: Fe | [Fe(DMF)4]2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.0, -0.5406], [3.3125, -0.5406], [3.8, -0.5406], [5.775, -0.5406], [6.525, -0.5406], [7.9, -0.5406]]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 633, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 265, 304, 462, 522, 632], "t_params": [0.0, 0.4193, 0.481, 0.731, 0.8259, 1.0], "envelope_n": 6, "envelope_pts": [[0.0, -0.5406], [3.3125, -0.5406], [3.8, -0.5406], [5.775, -0.5406], [6.525, -0.5406], [7.9, -0.5406]], "envelope_t": [0.0, 0.4193, 0.481, 0.731, 0.8259, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.0, -0.5406], [7.9, -0.5406]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: Fe3O4 (anh.) | [(Fe2O3)0.5(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, -0.5781], [7.3125, -0.1844], [7.1125, -0.1687], [6.8375, -0.1562], [6.6375, -0.1406], [6.1, -0.1125]]
  -- Boundary/junction features: [DmsRegEqJnc_7, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 782, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 661, 682, 708, 729, 781], "t_params": [0.0, 0.8465, 0.8719, 0.9066, 0.932, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, -0.5781], [7.3125, -0.1844], [7.1125, -0.1687], [6.8375, -0.1562], [6.6375, -0.1406], [6.1, -0.1125]], "envelope_t": [0.0, 0.8465, 0.8719, 0.9066, 0.932, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, -0.5781], [6.1, -0.1125]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: Fe3O4 (anh.) | [(Fe2O3)0.5(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[6.1, -0.1125], [6.1, -0.1094], [6.0875, -0.1094]]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 3, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 1, 2], "t_params": [0.0, 0.2, 1.0], "envelope_n": 6, "envelope_pts": [[6.1, -0.1125], [6.1, -0.1094], [6.0875, -0.1094]], "envelope_t": [0.0, 0.2, 1.0], "adaptive_n": 2, "adaptive_pts": [[6.1, -0.1125], [6.0875, -0.1094]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_5: Fe3O4 (anh.) | [Fe(DMF)4]2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[7.9, -0.5406], [6.4625, -0.1969], [6.4375, -0.1969], [6.225, -0.1406], [6.2, -0.1406], [6.1, -0.1125]]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 282, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 225, 227, 262, 264, 281], "t_params": [0.0, 0.7982, 0.8117, 0.9304, 0.9439, 1.0], "envelope_n": 6, "envelope_pts": [[7.9, -0.5406], [6.4625, -0.1969], [6.4375, -0.1969], [6.225, -0.1406], [6.2, -0.1406], [6.1, -0.1125]], "envelope_t": [0.0, 0.7982, 0.8117, 0.9304, 0.9439, 1.0], "adaptive_n": 2, "adaptive_pts": [[7.9, -0.5406], [6.1, -0.1125]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_6: Fe3O4 (anh.) | [Fe(DMF)4]2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[6.1, -0.1125], [6.0875, -0.1125], [6.0875, -0.1094]]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 3, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 1, 2], "t_params": [0.0, 0.8, 1.0], "envelope_n": 6, "envelope_pts": [[6.1, -0.1125], [6.0875, -0.1125], [6.0875, -0.1094]], "envelope_t": [0.0, 0.8, 1.0], "adaptive_n": 2, "adaptive_pts": [[6.1, -0.1125], [6.0875, -0.1094]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_7: [(Fe2O3)0.5(s,alpha)] | [Fe(DMF)4]2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[6.0875, -0.1094], [1.9625, 0.6188], [1.325, 0.7375], [1.2625, 0.7437], [1.0, 0.7937], [0.825, 0.8375]]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 725, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 563, 652, 659, 696, 724], "t_params": [0.0, 0.7833, 0.9046, 0.9163, 0.9663, 1.0], "envelope_n": 6, "envelope_pts": [[6.0875, -0.1094], [1.9625, 0.6188], [1.325, 0.7375], [1.2625, 0.7437], [1.0, 0.7937], [0.825, 0.8375]], "envelope_t": [0.0, 0.7833, 0.9046, 0.9163, 0.9663, 1.0], "adaptive_n": 2, "adaptive_pts": [[6.0875, -0.1094], [0.825, 0.8375]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_8: [(Fe2O3)0.5(s,alpha)] | FeO42-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, 0.3469], [3.9625, 1.3375], [3.8875, 1.3406], [3.55, 1.3781], [3.475, 1.3813], [2.3125, 1.5]]
  -- Boundary/junction features: [DmsRegEqJnc_8, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 1305, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 1120, 1127, 1166, 1173, 1304], "t_params": [0.0, 0.8588, 0.8652, 0.8941, 0.9005, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, 0.3469], [3.9625, 1.3375], [3.8875, 1.3406], [3.55, 1.3781], [3.475, 1.3813], [2.3125, 1.5]], "envelope_t": [0.0, 0.8588, 0.8652, 0.8941, 0.9005, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, 0.3469], [2.3125, 1.5]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_9: [(Fe2O3)0.5(s,alpha)] | [Fe(DMF)]3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.825, 0.8375], [0.7375, 0.875], [0.7125, 0.9], [0.7125, 0.9219], [0.7, 0.9219], [0.7, 1.5]]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_10]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 223, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 19, 29, 36, 37, 222], "t_params": [0.0, 0.1281, 0.1757, 0.2051, 0.222, 1.0], "envelope_n": 6, "envelope_pts": [[0.825, 0.8375], [0.7375, 0.875], [0.7125, 0.9], [0.7125, 0.9219], [0.7, 0.9219], [0.7, 1.5]], "envelope_t": [0.0, 0.1281, 0.1757, 0.2051, 0.222, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.825, 0.8375], [0.7, 1.5]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_10: [Fe(DMF)4]2+ | [Fe(DMF)]3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.0, 0.8281], [0.7375, 0.8281], [0.7375, 0.8313], [0.7625, 0.8313], [0.7625, 0.8344], [0.825, 0.8375]]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 70, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 59, 60, 62, 63, 69], "t_params": [0.0, 0.8871, 0.8909, 0.921, 0.9247, 1.0], "envelope_n": 6, "envelope_pts": [[0.0, 0.8281], [0.7375, 0.8281], [0.7375, 0.8313], [0.7625, 0.8313], [0.7625, 0.8344], [0.825, 0.8375]], "envelope_t": [0.0, 0.8871, 0.8909, 0.921, 0.9247, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.0, 0.8281], [0.825, 0.8375]], "adaptive_t": [0.0, 1.0]}

### junction features
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.), [Fe(DMF)4]2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_2, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 7.9, "E_V": -0.5406}
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [Fe(DMF)4]2+]
  -- Neighboring regions: [DmsReg_2, DmsReg_3, DmsReg_5, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_4, DmsRegEq_5, DmsRegEq_6]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 6.1, "E_V": -0.1125}
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [Fe(DMF)4]2+]
  -- Neighboring regions: [DmsReg_3, DmsReg_5, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_4, DmsRegEq_6, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 6.0875, "E_V": -0.1094}
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], [Fe(DMF)4]2+, [Fe(DMF)]3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_7, DmsRegEq_9, DmsRegEq_10]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 0.825, "E_V": 0.8375}
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": -0.9031}
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, [Fe(DMF)4]2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.0, "E_V": -0.5406}
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)]]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": -0.5781}
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": 0.3469}
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 2.3125, "E_V": 1.5}
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], [Fe(DMF)]3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_9]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.7, "E_V": 1.5}
- **DmsRegEqJnc_11** — intrinsic dimension 0 (point)
  -- Dominant species: [[Fe(DMF)4]2+, [Fe(DMF)]3+]
  -- Neighboring regions: [DmsReg_4, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_10]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.0, "E_V": 0.8281}

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(DMF)4]2+, [Fe(DMF)3]2+, [Fe(DMF)2]2+, [Fe(DMF)]2+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(DMF)]3+, FeO42-, [Fe(OH)2](s), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe]
  -- excluded: [HFeO2-, FeOH2+, Fe(OH)2 (hydr.), Fe(OH)3 (hydr.), Fe2O3 (anh.)]
