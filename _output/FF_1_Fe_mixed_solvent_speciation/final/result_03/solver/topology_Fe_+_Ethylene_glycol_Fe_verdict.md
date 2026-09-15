# Solver report (Pourbaix)

## System
- Components: [Fe, Ethylene glycol]
- Constraints:
  -- component totals (M): Fe=0.1;Ethylene glycol=1
- Potential reference: SHE
- Domain: pH [0, 14]; E_V [-1, 1.5]
- Coarse grid spacing: ΔpH=not reported; ΔE_V=not reported
- Final classified-grid spacing: ΔpH=0.00625; ΔE_V=0.00125
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
- Fixed coordinates in domain order: [not reported, 0.250625]
- Fixed sample indices in domain order: [None, 1000]
- samples 0–534, pH [0.003125, 3.340625]: Fe2+ (Dms_4)
- samples 535–2239, pH [3.346875, 13.996875]: [(Fe2O3)0.5(s,alpha)] (Dms_3)
  -- preceding label change is bracketed by adjacent samples [3.340625, 3.346875]

## Example classified-grid cut along E_V
- Fixed coordinates in domain order: [6.996875, not reported]
- Fixed sample indices in domain order: [1119, None]
- samples 0–409, E_V [-0.999375, -0.488125]: Fe (Dms_1)
- samples 410–668, E_V [-0.486875, -0.164375]: Fe3O4 (anh.) (Dms_2)
  -- preceding label change is bracketed by adjacent samples [-0.488125, -0.486875]
- samples 669–1628, E_V [-0.163125, 1.035625]: [(Fe2O3)0.5(s,alpha)] (Dms_3)
  -- preceding label change is bracketed by adjacent samples [-0.164375, -0.163125]
- samples 1629–1999, E_V [1.036875, 1.499375]: FeO42- (Dms_5)
  -- preceding label change is bracketed by adjacent samples [1.035625, 1.036875]

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
  -- Measure in the solver coordinate frame: 5.7838594
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_1
    --- DmsReg_4 {Fe2+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1, DmsRegEqJnc_5]
- **DmsReg_2 {Fe3O4 (anh.)}**
  -- Measure in the solver coordinate frame: 2.6125547
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_1
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_3
    --- DmsReg_4 {Fe2+} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_6]
- **DmsReg_3 {[(Fe2O3)0.5(s,alpha)]}**
  -- Measure in the solver coordinate frame: 14.755859
  -- Neighboring regions:
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_3
    --- DmsReg_4 {Fe2+} via DmsRegEq_5
    --- DmsReg_5 {FeO42-} via DmsRegEq_6
    --- DmsReg_6 {Fe3+} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_6, DmsRegEqJnc_3, DmsRegEqJnc_8, DmsRegEqJnc_7, DmsRegEqJnc_9]
- **DmsReg_4 {Fe2+}**
  -- Measure in the solver coordinate frame: 4.7861094
  -- Neighboring regions:
    --- DmsReg_1 {Fe} via DmsRegEq_2
    --- DmsReg_2 {Fe3O4 (anh.)} via DmsRegEq_4
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_5
    --- DmsReg_6 {Fe3+} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_3, DmsRegEqJnc_10]
- **DmsReg_5 {FeO42-}**
  -- Measure in the solver coordinate frame: 6.7570859
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_8, DmsRegEqJnc_7]
- **DmsReg_6 {Fe3+}**
  -- Measure in the solver coordinate frame: 0.30453125
  -- Neighboring regions:
    --- DmsReg_3 {[(Fe2O3)0.5(s,alpha)]} via DmsRegEq_7
    --- DmsReg_4 {Fe2+} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_3, DmsRegEqJnc_10]

### boundary curves/equilibria
- **DmsRegEq_1: Fe | Fe3O4 (anh.)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, -0.90125], [13.975, -0.90125], [13.875, -0.89375], [13.7, -0.885], [13.43125, -0.8675], [6.84375, -0.47875]]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 1484, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 4, 26, 61, 118, 1483], "t_params": [0.0, 0.00349, 0.01748, 0.04192, 0.07949, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, -0.90125], [13.975, -0.90125], [13.875, -0.89375], [13.7, -0.885], [13.43125, -0.8675], [6.84375, -0.47875]], "envelope_t": [0.0, 0.00349, 0.01748, 0.04192, 0.07949, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, -0.90125], [6.84375, -0.47875]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_2: Fe | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.0, -0.47875], [1.78125, -0.47875], [3.14375, -0.47875], [3.54375, -0.47875], [5.2625, -0.47875], [6.84375, -0.47875]]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 1096, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 285, 503, 567, 842, 1095], "t_params": [0.0, 0.26027, 0.45936, 0.51781, 0.76895, 1.0], "envelope_n": 6, "envelope_pts": [[0.0, -0.47875], [1.78125, -0.47875], [3.14375, -0.47875], [3.54375, -0.47875], [5.2625, -0.47875], [6.84375, -0.47875]], "envelope_t": [0.0, 0.26027, 0.45936, 0.51781, 0.76895, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.0, -0.47875], [6.84375, -0.47875]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: Fe3O4 (anh.) | [(Fe2O3)0.5(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, -0.5775], [13.74375, -0.56375], [13.475, -0.54625], [13.3, -0.5375], [13.03125, -0.52], [5.025, -0.0475]]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 1861, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 52, 109, 144, 201, 1860], "t_params": [0.0, 0.02854, 0.0585, 0.07799, 0.10794, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, -0.5775], [13.74375, -0.56375], [13.475, -0.54625], [13.3, -0.5375], [13.03125, -0.52], [5.025, -0.0475]], "envelope_t": [0.0, 0.02854, 0.0585, 0.07799, 0.10794, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, -0.5775], [5.025, -0.0475]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: Fe3O4 (anh.) | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[6.84375, -0.47875], [5.25, -0.1], [5.2125, -0.09375], [5.18125, -0.08375], [5.14375, -0.0775], [5.025, -0.0475]]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 637, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 558, 569, 582, 593, 636], "t_params": [0.0, 0.87626, 0.8966, 0.91415, 0.93448, 1.0], "envelope_n": 6, "envelope_pts": [[6.84375, -0.47875], [5.25, -0.1], [5.2125, -0.09375], [5.18125, -0.08375], [5.14375, -0.0775], [5.025, -0.0475]], "envelope_t": [0.0, 0.87626, 0.8966, 0.91415, 0.93448, 1.0], "adaptive_n": 2, "adaptive_pts": [[6.84375, -0.47875], [5.025, -0.0475]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_5: [(Fe2O3)0.5(s,alpha)] | Fe2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[5.025, -0.0475], [0.9625, 0.675], [0.95, 0.675], [0.69375, 0.72375], [0.59375, 0.74625], [0.5125, 0.77]]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 1377, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 1228, 1230, 1310, 1344, 1376], "t_params": [0.0, 0.8996, 0.90233, 0.9592, 0.98154, 1.0], "envelope_n": 6, "envelope_pts": [[5.025, -0.0475], [0.9625, 0.675], [0.95, 0.675], [0.69375, 0.72375], [0.59375, 0.74625], [0.5125, 0.77]], "envelope_t": [0.0, 0.8996, 0.90233, 0.9592, 0.98154, 1.0], "adaptive_n": 2, "adaptive_pts": [[5.025, -0.0475], [0.5125, 0.77]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_6: [(Fe2O3)0.5(s,alpha)] | FeO42-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[14.0, 0.34625], [3.49375, 1.3825], [3.475, 1.3825], [3.05, 1.42625], [3.03125, 1.42625], [2.3, 1.5]]
  -- Boundary/junction features: [DmsRegEqJnc_7, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 2796, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 2510, 2513, 2616, 2619, 2795], "t_params": [0.0, 0.89796, 0.89955, 0.93589, 0.93749, 1.0], "envelope_n": 6, "envelope_pts": [[14.0, 0.34625], [3.49375, 1.3825], [3.475, 1.3825], [3.05, 1.42625], [3.03125, 1.42625], [2.3, 1.5]], "envelope_t": [0.0, 0.89796, 0.89955, 0.93589, 0.93749, 1.0], "adaptive_n": 2, "adaptive_pts": [[14.0, 0.34625], [2.3, 1.5]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_7: [(Fe2O3)0.5(s,alpha)] | Fe3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.5125, 0.77], [0.46875, 0.78875], [0.44375, 0.80625], [0.425, 0.84625], [0.41875, 0.84625], [0.4125, 1.5]]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 601, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 22, 40, 75, 76, 600], "t_params": [0.0, 0.06084, 0.09985, 0.15632, 0.16431, 1.0], "envelope_n": 6, "envelope_pts": [[0.5125, 0.77], [0.46875, 0.78875], [0.44375, 0.80625], [0.425, 0.84625], [0.41875, 0.84625], [0.4125, 1.5]], "envelope_t": [0.0, 0.06084, 0.09985, 0.15632, 0.16431, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.5125, 0.77], [0.4125, 1.5]], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_8: Fe2+ | Fe3+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [[0.0, 0.77], [0.21875, 0.77], [0.2375, 0.77], [0.25625, 0.77], [0.41875, 0.77], [0.5125, 0.77]]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "raw_n": 83, "compact_n": 6, "compact_target_n": 6, "compact_indices": [0, 35, 38, 41, 67, 82], "t_params": [0.0, 0.42683, 0.46341, 0.5, 0.81707, 1.0], "envelope_n": 6, "envelope_pts": [[0.0, 0.77], [0.21875, 0.77], [0.2375, 0.77], [0.25625, 0.77], [0.41875, 0.77], [0.5125, 0.77]], "envelope_t": [0.0, 0.42683, 0.46341, 0.5, 0.81707, 1.0], "adaptive_n": 2, "adaptive_pts": [[0.0, 0.77], [0.5125, 0.77]], "adaptive_t": [0.0, 1.0]}

### junction features
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.), Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_2, DmsRegEq_4]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 6.84375, "E_V": -0.47875}
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], Fe2+]
  -- Neighboring regions: [DmsReg_2, DmsReg_3, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_4, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 5.025, "E_V": -0.0475}
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe2+, Fe3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_5, DmsRegEq_7, DmsRegEq_8]
  -- At sweep limit: false
  -- Geometry: compact point {"pH": 0.5125, "E_V": 0.77}
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe3O4 (anh.)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": -0.90125}
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe, Fe2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.0, "E_V": -0.47875}
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)]]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": -0.5775}
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 14.0, "E_V": 0.34625}
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], FeO42-]
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 2.3, "E_V": 1.5}
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Fe2O3)0.5(s,alpha)], Fe3+]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_7]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.4125, "E_V": 1.5}
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, Fe3+]
  -- Neighboring regions: [DmsReg_4, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point {"pH": 0.0, "E_V": 0.77}

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Ethy)(OH)]+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Ethy)(OH)]2+, FeO42-, [Fe(OH)2](s), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe]
  -- excluded: [HFeO2-, FeOH2+, Fe(OH)2 (hydr.), Fe(OH)3 (hydr.), Fe2O3 (anh.)]
