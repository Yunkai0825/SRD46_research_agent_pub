# Solver report (Pourbaix)

## System
- Components: [Fe, Acetonitrile]
- Constraints:
  -- component totals (M): Fe=0.1;Acetonitrile=1
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
- Dms_4: Fe2+
- Dms_5: FeO42-
- Dms_6: Fe3+

## Topology stats
- 6 dominant-species labels
- 6 connected regions
- 8 pairwise boundary curves
- 3 internal junction features
- 7 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Example classified-grid cut along pH
- Fixed coordinates in domain order: [not reported, 0.2484375]
- Fixed sample indices in domain order: [None, 399]
- samples 0–272, pH [0.00625, 3.40625]: Fe2+ (Dms_4)
- samples 273–1119, pH [3.41875, 13.99375]: [(Fe2O3)0.5(s,alpha)] (Dms_3)
  -- preceding label change is bracketed by adjacent samples [3.40625, 3.41875]

## Example classified-grid cut along E_V
- Fixed coordinates in domain order: [6.99375, not reported]
- Fixed sample indices in domain order: [559, None]
- samples 0–163, E_V [-0.9984375, -0.4890625]: Fe (Dms_1)
- samples 164–267, E_V [-0.4859375, -0.1640625]: Fe3O4 (anh.) (Dms_2)
  -- preceding label change is bracketed by adjacent samples [-0.4890625, -0.4859375]
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
  -- Measure in the solver coordinate frame: 5.7450781
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_1
    --- DmsReg_4 {Fe2+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1, DmsRegEqJnc_5]
- **DmsReg_2 {Fe3O4 (anh.)}**
  -- Measure in the solver coordinate frame: 2.5843359
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_1
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_3
    --- DmsReg_4 {Fe2+} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_6]
- **DmsReg_3 {[(Fe2O3)0.5(s,alpha)]}**
  -- Measure in the solver coordinate frame: 14.672578
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_3
    --- DmsReg_4 {Fe2+} via DmsRegEq_5
    --- DmsReg_5 {FeO42-} via DmsRegEq_6
    --- DmsReg_6 {Fe3+} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_6, DmsRegEqJnc_3, DmsRegEqJnc_8, DmsRegEqJnc_7, DmsRegEqJnc_9]
- **DmsReg_4 {Fe2+}**
  -- Measure in the solver coordinate frame: 4.9015625
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_2
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_4
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_5
    --- DmsReg_6 {Fe3+} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_10]
- **DmsReg_5 {FeO42-}**
  -- Measure in the solver coordinate frame: 6.7570313
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_8, DmsRegEqJnc_7]
- **DmsReg_6 {Fe3+}**
  -- Measure in the solver coordinate frame: 0.33941406
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_7
    --- DmsReg_4 {Fe2+} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_3, DmsRegEqJnc_10]

### boundary curves/equilibria
- **DmsRegEq_1: Fe | Fe3O4 (anh.)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, -0.9031], [12.8375, -0.8313], [12.775, -0.8313], [12.625, -0.8188], [12.5625, -0.8188], [6.925, -0.4844]]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 701, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 116, 121, 137, 142, 700], "t_params": [0.0, 0.1643, 0.1731, 0.1944, 0.2032, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, -0.9031], [12.8375, -0.8313], [12.775, -0.8313], [12.625, -0.8188], [12.5625, -0.8188], [6.925, -0.4844]], "envelope_t": [0.0, 0.1643, 0.1731, 0.1944, 0.2032, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, -0.9031], [6.925, -0.4844]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_2: Fe | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.0, -0.4844], [1.7875, -0.4844], [3.5375, -0.4844], [5.2375, -0.4844], [5.375, -0.4844], [6.925, -0.4844]]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 555, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 143, 283, 419, 430, 554], "t_params": [0.0, 0.2581, 0.5108, 0.7563, 0.7762, 1.0], "envelope_n": 6, "envelope_pts": [[0.0, -0.4844], [1.7875, -0.4844], [3.5375, -0.4844], [5.2375, -0.4844], [5.375, -0.4844], [6.925, -0.4844]], "envelope_t": [0.0, 0.2581, 0.5108, 0.7563, 0.7762, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.0, -0.4844], [6.925, -0.4844]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: Fe3O4 (anh.) | [(Fe2O3)0.5(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, -0.5781], [6.15, -0.1156], [5.95, -0.1], [5.675, -0.0875], [5.475, -0.0719], [5.1125, -0.0531]]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 880, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 776, 797, 823, 844, 879], "t_params": [0.0, 0.8832, 0.9058, 0.9367, 0.9592, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, -0.5781], [6.15, -0.1156], [5.95, -0.1], [5.675, -0.0875], [5.475, -0.0719], [5.1125, -0.0531]], "envelope_t": [0.0, 0.8832, 0.9058, 0.9367, 0.9592, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, -0.5781], [5.1125, -0.0531]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: Fe3O4 (anh.) | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[6.925, -0.4844], [6.775, -0.4437], [6.75, -0.4437], [6.5375, -0.3875], [6.5125, -0.3875], [5.1125, -0.0531]]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 284, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 25, 27, 62, 64, 283], "t_params": [0.0, 0.0833, 0.0968, 0.2146, 0.2281, 1.0], "envelope_n": 6, "envelope_pts": [[6.925, -0.4844], [6.775, -0.4437], [6.75, -0.4437], [6.5375, -0.3875], [6.5125, -0.3875], [5.1125, -0.0531]], "envelope_t": [0.0, 0.0833, 0.0968, 0.2146, 0.2281, 1.0], "adaptive_n": 2, "adaptive_pts": [[6.925, -0.4844], [5.1125, -0.0531]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_5: [(Fe2O3)0.5(s,alpha)] | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[5.1125, -0.0531], [1.6125, 0.5656], [1.0625, 0.6688], [1.0, 0.675], [0.6375, 0.7469], [0.5625, 0.7719]]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 629, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 478, 555, 562, 614, 628], "t_params": [0.0, 0.7684, 0.8894, 0.903, 0.9829, 1.0], "envelope_n": 6, "envelope_pts": [[5.1125, -0.0531], [1.6125, 0.5656], [1.0625, 0.6688], [1.0, 0.675], [0.6375, 0.7469], [0.5625, 0.7719]], "envelope_t": [0.0, 0.7684, 0.8894, 0.903, 0.9829, 1.0], "adaptive_n": 2, "adaptive_pts": [[5.1125, -0.0531], [0.5625, 0.7719]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_6: [(Fe2O3)0.5(s,alpha)] | FeO42-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, 0.3469], [3.9625, 1.3375], [3.8875, 1.3406], [3.55, 1.3781], [3.475, 1.3813], [2.3125, 1.5]]
  -- Boundary/junction features: [DmsRegEqJnc_7, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 1305, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 1120, 1127, 1166, 1173, 1304], "t_params": [0.0, 0.8588, 0.8652, 0.8941, 0.9005, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, 0.3469], [3.9625, 1.3375], [3.8875, 1.3406], [3.55, 1.3781], [3.475, 1.3813], [2.3125, 1.5]], "envelope_t": [0.0, 0.8588, 0.8652, 0.8941, 0.9005, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, 0.3469], [2.3125, 1.5]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_7: [(Fe2O3)0.5(s,alpha)] | Fe3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.5625, 0.7719], [0.5, 0.7969], [0.475, 0.8188], [0.475, 0.8375], [0.4625, 0.8375], [0.4625, 1.5]]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 242, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 13, 22, 28, 29, 241], "t_params": [0.0, 0.0847, 0.1266, 0.1502, 0.1659, 1.0], "envelope_n": 6, "envelope_pts": [[0.5625, 0.7719], [0.5, 0.7969], [0.475, 0.8188], [0.475, 0.8375], [0.4625, 0.8375], [0.4625, 1.5]], "envelope_t": [0.0, 0.0847, 0.1266, 0.1502, 0.1659, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.5625, 0.7719], [0.4625, 1.5]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_8: Fe2+ | Fe3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.0, 0.7719], [0.1375, 0.7719], [0.1875, 0.7719], [0.2375, 0.7719], [0.35, 0.7719], [0.5625, 0.7719]]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 46, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 11, 15, 19, 28, 45], "t_params": [0.0, 0.2444, 0.3333, 0.4222, 0.6222, 1.0], "envelope_n": 6, "envelope_pts": [[0.0, 0.7719], [0.1375, 0.7719], [0.1875, 0.7719], [0.2375, 0.7719], [0.35, 0.7719], [0.5625, 0.7719]], "envelope_t": [0.0, 0.2444, 0.3333, 0.4222, 0.6222, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.0, 0.7719], [0.5625, 0.7719]], "adaptive_t": [0.0, 1.0]}

### junction features
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.), Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_2, DmsRegEq_4]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 6.925, "E_V": -0.4844}
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], Fe2+]
  -- Neighboring regions: [DmsReg_2, DmsReg_3, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_4, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 5.1125, "E_V": -0.0531}
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe2+, Fe3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_5, DmsRegEq_7, DmsRegEq_8]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 0.5625, "E_V": 0.7719}
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": -0.9031}
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.0, "E_V": -0.4844}
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)]]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": -0.5781}
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": 0.3469}
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 2.3125, "E_V": 1.5}
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_7]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.4625, "E_V": 1.5}
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, Fe3+]
  -- Neighboring regions: [DmsReg_4, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.0, "E_V": 0.7719}

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Acet)]2+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Acet)]3+, [Fe(Acet)2]3+, [Fe(Acet)3]3+, FeO42-, [Fe(OH)2](s), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe]
  -- excluded: [HFeO2-, FeOH2+, Fe(OH)2 (hydr.), Fe(OH)3 (hydr.), Fe2O3 (anh.)]
