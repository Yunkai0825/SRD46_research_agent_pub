# Solver report (Pourbaix)

## System
- Components: [Cu, Fe, Citric acid, Chloride ion]
- Constraints:
  -- component totals (M): Cu=0.001;Fe=0.001;Citric acid=0.005;Chloride ion=0.1
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[2, 10], E_V=[-0.5V, 1.2V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.2, ΔE_V=0.05V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Fe2+
- Dms_2: [Fe(Citr)]-
- Dms_3: [Fe2(Citr)2(OH)2]4-
- Dms_4: [FeO(OH)(s,alpha)]
- Dms_5: [Fe2(Citr)2(OH)2]2-

## Topology stats
- 5 dominant-species labels
- 5 connected regions
- 6 pairwise boundary curves
- 2 internal junction features
- 5 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.35V)
- Fixed sample indices: (pH=swept, E_V=sample 17)
- samples 0–8, (pH=[2, 3.6], E_V=0.35V): Fe2+ (Dms_1)
- samples 9–11, (pH=[3.8, 4.2], E_V=0.35V): [Fe2(Citr)2(OH)2]2- (Dms_5)
  -- preceding label change is bracketed by adjacent samples (pH=[3.6, 3.8], E_V=0.35V)
- samples 12–40, (pH=[4.4, 10], E_V=0.35V): [FeO(OH)(s,alpha)] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=[4.2, 4.4], E_V=0.35V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6, E_V=swept)
- Fixed sample indices: (pH=sample 20, E_V=swept)
- samples 0–10, (pH=6, E_V=[-0.5V, -5.5511151e-17V]): [Fe(Citr)]- (Dms_2)
- samples 11–34, (pH=6, E_V=[0.05V, 1.2V]): [FeO(OH)(s,alpha)] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=6, E_V=[-5.5511151e-17V, 0.05V])

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
- **DmsReg_1 {[FeO(OH)(s,alpha)]}**
  -- Measure in the solver coordinate frame: 8.05
  -- Neighboring regions:
    --- DmsReg_3 {[Fe(Citr)]-} via DmsRegEq_4
    --- DmsReg_4 {[Fe2(Citr)2(OH)2]4-} via DmsRegEq_5
    --- DmsReg_5 {[Fe2(Citr)2(OH)2]2-} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_4, DmsRegEqJnc_6, DmsRegEqJnc_7]
#### liquid
- **DmsReg_2 {Fe2+}**
  -- Measure in the solver coordinate frame: 2.54
  -- Neighboring regions:
    --- DmsReg_3 {[Fe(Citr)]-} via DmsRegEq_2
    --- DmsReg_5 {[Fe2(Citr)2(OH)2]2-} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_2]
- **DmsReg_3 {[Fe(Citr)]-}**
  -- Measure in the solver coordinate frame: 1.69
  -- Neighboring regions:
    --- DmsReg_2 {Fe2+} via DmsRegEq_2
    --- DmsReg_4 {[Fe2(Citr)2(OH)2]4-} via DmsRegEq_3
    --- DmsReg_1 {[FeO(OH)(s,alpha)]} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_3, DmsRegEqJnc_4]
- **DmsReg_4 {[Fe2(Citr)2(OH)2]4-}**
  -- Measure in the solver coordinate frame: 0.24
  -- Neighboring regions:
    --- DmsReg_3 {[Fe(Citr)]-} via DmsRegEq_3
    --- DmsReg_1 {[FeO(OH)(s,alpha)]} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_4, DmsRegEqJnc_6]
- **DmsReg_5 {[Fe2(Citr)2(OH)2]2-}**
  -- Measure in the solver coordinate frame: 1.83
  -- Neighboring regions:
    --- DmsReg_2 {Fe2+} via DmsRegEq_1
    --- DmsReg_1 {[FeO(OH)(s,alpha)]} via DmsRegEq_6
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_2, DmsRegEqJnc_7]

### boundary curves/equilibria
#### liquid–liquid · redox (by species definition)
- **DmsRegEq_1: Fe2+ | [Fe2(Citr)2(OH)2]2-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.5, E_V=0.275V), (pH=2, E_V=0.675V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 22, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 21], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.5, E_V=0.275V), (pH=2, E_V=0.675V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.5, E_V=0.275V), (pH=2, E_V=0.675V)], "adaptive_t": [0.0, 1.0]}
#### liquid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_2: Fe2+ | [Fe(Citr)]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.5, E_V=-0.5V), (pH=4.5, E_V=0.275V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 17, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 16], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.5, E_V=-0.5V), (pH=4.5, E_V=0.275V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.5, E_V=-0.5V), (pH=4.5, E_V=0.275V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: [Fe(Citr)]- | [Fe2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.7, E_V=-0.5V), (pH=7.9, E_V=-0.325V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 6, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 5], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.7, E_V=-0.5V), (pH=7.9, E_V=-0.325V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=7.7, E_V=-0.5V), (pH=7.9, E_V=-0.325V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_4: [Fe(Citr)]- | [FeO(OH)(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.9, E_V=-0.325V), (pH=4.5, E_V=0.275V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 30, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 29], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.9, E_V=-0.325V), (pH=4.5, E_V=0.275V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=7.9, E_V=-0.325V), (pH=4.5, E_V=0.275V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_5: [Fe2(Citr)2(OH)2]4- | [FeO(OH)(s,alpha)]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=9.5, E_V=-0.5V), (pH=7.9, E_V=-0.325V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 13, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 12], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=9.5, E_V=-0.5V), (pH=7.9, E_V=-0.325V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=9.5, E_V=-0.5V), (pH=7.9, E_V=-0.325V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_6: [FeO(OH)(s,alpha)] | [Fe2(Citr)2(OH)2]2-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.5, E_V=0.275V), (pH=4.3, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 21, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 20], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.5, E_V=0.275V), (pH=4.3, E_V=1.2V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.5, E_V=0.275V), (pH=4.3, E_V=1.2V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, [Fe(Citr)]-]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point (pH=4.5, E_V=-0.5V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, [Fe2(Citr)2(OH)2]2-]
  -- Neighboring regions: [DmsReg_2, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=2, E_V=0.675V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [[Fe(Citr)]-, [Fe2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point (pH=7.7, E_V=-0.5V)
#### one solid
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [[Fe(Citr)]-, [Fe2(Citr)2(OH)2]4-, [FeO(OH)(s,alpha)]]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_4, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=7.9, E_V=-0.325V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Fe2+, [Fe(Citr)]-, [FeO(OH)(s,alpha)], [Fe2(Citr)2(OH)2]2-]
  -- Neighboring regions: [DmsReg_2, DmsReg_5, DmsReg_3, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_2, DmsRegEq_4, DmsRegEq_6]
  -- At sweep limit: false
  -- Geometry: compact point (pH=4.5, E_V=0.275V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [[Fe2(Citr)2(OH)2]4-, [FeO(OH)(s,alpha)]]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_5]
  -- At sweep limit: true
  -- Geometry: compact point (pH=9.5, E_V=-0.5V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [[FeO(OH)(s,alpha)], [Fe2(Citr)2(OH)2]2-]
  -- Neighboring regions: [DmsReg_1, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=4.3, E_V=1.2V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Cu**
  -- included: [Cu+, [Cu2(Chlo)4]2-, [Cu(Chlo)2]-, [Cu(Chlo)3]2-, [Cu(Chlo)], Cu2+, [Cu(OH)]+, [Cu2(OH)2]2+, [Cu(OH)2], HCuO2-, [Cu3(OH)4]2+, CuO22-, [Cu(Citr)H], [Cu2(Citr)2]2-, [Cu2(Citr)(OH)], [Cu2(Citr)2(OH)]3-, [Cu2(Citr)2(OH)2]4-, [Cu(Chlo)]+, [(Cu2O)0.5](s), [Cu(Chloride ion)](s), CuO(s), [Cu(OH)2](s), Cu]
  -- excluded: [Cu2O, CuO, Cu(OH)2]
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Citr)H2]+, [Fe(Citr)H], [Fe(Citr)2H]3-, [Fe(Citr)]-, [Fe2(Citr)2(OH)2]4-, [Fe(Chlo)]+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Citr)H]+, [Fe(Citr)], [Fe(Citr)(OH)]-, [Fe2(Citr)2(OH)2]2-, [Fe(Chlo)2]+, [Fe(Chlo)]2+, [Fe(OH)2](s), [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe(OH)3 (hydr.), Fe]
  -- excluded: [HFeO2-, FeOH2+, FeO42-, Fe(OH)2 (hydr.), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], Fe2O3 (anh.)]
