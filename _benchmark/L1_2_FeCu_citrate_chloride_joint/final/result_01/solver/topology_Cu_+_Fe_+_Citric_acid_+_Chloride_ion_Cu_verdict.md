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
- Dms_1: Cu
- Dms_2: [(Cu2O)0.5](s)
- Dms_3: [Cu(Chlo)2]-
- Dms_4: [Cu2(Citr)2(OH)2]4-
- Dms_5: [Cu2(Citr)2(OH)]3-
- Dms_6: Cu2+

## Topology stats
- 6 dominant-species labels
- 6 connected regions
- 9 pairwise boundary curves
- 4 internal junction features
- 6 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.35V)
- Fixed sample indices: (pH=swept, E_V=sample 17)
- samples 0–7, (pH=[2, 3.4], E_V=0.35V): [Cu(Chlo)2]- (Dms_3)
- samples 8–10, (pH=[3.6, 4], E_V=0.35V): [Cu2(Citr)2(OH)]3- (Dms_5)
  -- preceding label change is bracketed by adjacent samples (pH=[3.4, 3.6], E_V=0.35V)
- samples 11–40, (pH=[4.2, 10], E_V=0.35V): [Cu2(Citr)2(OH)2]4- (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=[4, 4.2], E_V=0.35V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6, E_V=swept)
- Fixed sample indices: (pH=sample 20, E_V=swept)
- samples 0–11, (pH=6, E_V=[-0.5V, 0.05V]): Cu (Dms_1)
- samples 12–34, (pH=6, E_V=[0.1V, 1.2V]): [Cu2(Citr)2(OH)2]4- (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=6, E_V=[0.05V, 0.1V])

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
  -- Measure in the solver coordinate frame: 4.6
  -- Neighboring regions:
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_9
    --- DmsReg_3 {[Cu(Chlo)2]-} via DmsRegEq_6
    --- DmsReg_4 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_10, DmsRegEqJnc_7, DmsRegEqJnc_6]
- **DmsReg_2 {[(Cu2O)0.5](s)}**
  -- Measure in the solver coordinate frame: 0.32
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_9
    --- DmsReg_4 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_8
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_10, DmsRegEqJnc_8]
#### liquid
- **DmsReg_3 {[Cu(Chlo)2]-}**
  -- Measure in the solver coordinate frame: 0.81
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_6
    --- DmsReg_4 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_1
    --- DmsReg_5 {[Cu2(Citr)2(OH)]3-} via DmsRegEq_2
    --- DmsReg_6 {Cu2+} via DmsRegEq_3
  -- Junction features: [DmsRegEqJnc_7, DmsRegEqJnc_6, DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_3]
- **DmsReg_4 {[Cu2(Citr)2(OH)2]4-}**
  -- Measure in the solver coordinate frame: 6.71
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_7
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_8
    --- DmsReg_3 {[Cu(Chlo)2]-} via DmsRegEq_1
    --- DmsReg_5 {[Cu2(Citr)2(OH)]3-} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_9, DmsRegEqJnc_6, DmsRegEqJnc_8, DmsRegEqJnc_1, DmsRegEqJnc_4]
- **DmsReg_5 {[Cu2(Citr)2(OH)]3-}**
  -- Measure in the solver coordinate frame: 0.72
  -- Neighboring regions:
    --- DmsReg_3 {[Cu(Chlo)2]-} via DmsRegEq_2
    --- DmsReg_4 {[Cu2(Citr)2(OH)2]4-} via DmsRegEq_4
    --- DmsReg_6 {Cu2+} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2, DmsRegEqJnc_4, DmsRegEqJnc_5]
- **DmsReg_6 {Cu2+}**
  -- Measure in the solver coordinate frame: 1.19
  -- Neighboring regions:
    --- DmsReg_3 {[Cu(Chlo)2]-} via DmsRegEq_3
    --- DmsReg_5 {[Cu2(Citr)2(OH)]3-} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_2, DmsRegEqJnc_5]

### boundary curves/equilibria
#### liquid–liquid · redox (by species definition)
- **DmsRegEq_1: [Cu(Chlo)2]- | [Cu2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=5.9, E_V=0.075V), (pH=4.1, E_V=0.275V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 14, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 13], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=5.9, E_V=0.075V), (pH=4.1, E_V=0.275V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=5.9, E_V=0.075V), (pH=4.1, E_V=0.275V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_2: [Cu(Chlo)2]- | [Cu2(Citr)2(OH)]3-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.1, E_V=0.275V), (pH=3.3, E_V=0.375V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 7, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 6], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.1, E_V=0.275V), (pH=3.3, E_V=0.375V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.1, E_V=0.275V), (pH=3.3, E_V=0.375V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: [Cu(Chlo)2]- | Cu2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=2, E_V=0.375V), (pH=3.3, E_V=0.375V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 8, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 7], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=2, E_V=0.375V), (pH=3.3, E_V=0.375V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=2, E_V=0.375V), (pH=3.3, E_V=0.375V)], "adaptive_t": [0.0, 1.0]}
#### liquid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_4: [Cu2(Citr)2(OH)2]4- | [Cu2(Citr)2(OH)]3-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=4.1, E_V=0.275V), (pH=4.1, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 20, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 19], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=4.1, E_V=0.275V), (pH=4.1, E_V=1.2V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=4.1, E_V=0.275V), (pH=4.1, E_V=1.2V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_5: [Cu2(Citr)2(OH)]3- | Cu2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=3.3, E_V=0.375V), (pH=3.3, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 18, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 17], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=3.3, E_V=0.375V), (pH=3.3, E_V=1.2V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=3.3, E_V=0.375V), (pH=3.3, E_V=1.2V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_6: Cu | [Cu(Chlo)2]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=2, E_V=0.075V), (pH=5.9, E_V=0.075V)]
  -- Boundary/junction features: [DmsRegEqJnc_7, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 21, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 20], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=2, E_V=0.075V), (pH=5.9, E_V=0.075V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=2, E_V=0.075V), (pH=5.9, E_V=0.075V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_7: Cu | [Cu2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=5.9, E_V=0.075V), (pH=7.3, E_V=0.075V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 8, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 7], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=5.9, E_V=0.075V), (pH=7.3, E_V=0.075V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=5.9, E_V=0.075V), (pH=7.3, E_V=0.075V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_8: [(Cu2O)0.5](s) | [Cu2(Citr)2(OH)2]4-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.3, E_V=0.075V), (pH=10, E_V=0.075V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 15, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 14], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.3, E_V=0.075V), (pH=10, E_V=0.075V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=7.3, E_V=0.075V), (pH=10, E_V=0.075V)], "adaptive_t": [0.0, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_9: Cu | [(Cu2O)0.5](s)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=10, E_V=-0.125V), (pH=7.3, E_V=0.075V)]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.039, "resolution_tau_norm": 0.039, "stop_epsilon": 0.039, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 19, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 18], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=10, E_V=-0.125V), (pH=7.3, E_V=0.075V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=10, E_V=-0.125V), (pH=7.3, E_V=0.075V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, [Cu2(Citr)2(OH)2]4-, [Cu2(Citr)2(OH)]3-]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_2, DmsRegEq_4]
  -- At sweep limit: false
  -- Geometry: compact point (pH=4.1, E_V=0.275V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, [Cu2(Citr)2(OH)]3-, Cu2+]
  -- Neighboring regions: [DmsReg_3, DmsReg_5, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_3, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=3.3, E_V=0.375V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, Cu2+]
  -- Neighboring regions: [DmsReg_3, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point (pH=2, E_V=0.375V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu2(Citr)2(OH)2]4-, [Cu2(Citr)2(OH)]3-]
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_4]
  -- At sweep limit: true
  -- Geometry: compact point (pH=4.1, E_V=1.2V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu2(Citr)2(OH)]3-, Cu2+]
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_5]
  -- At sweep limit: true
  -- Geometry: compact point (pH=3.3, E_V=1.2V)
#### one solid
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [Cu(Chlo)2]-, [Cu2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_6, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=5.9, E_V=0.075V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [Cu(Chlo)2]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=2, E_V=0.075V)
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Cu2O)0.5](s), [Cu2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point (pH=10, E_V=0.075V)
#### two solids
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [(Cu2O)0.5](s), [Cu2(Citr)2(OH)2]4-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_7, DmsRegEq_8, DmsRegEq_9]
  -- At sweep limit: false
  -- Geometry: compact point (pH=7.3, E_V=0.075V)
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [(Cu2O)0.5](s)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_9]
  -- At sweep limit: true
  -- Geometry: compact point (pH=10, E_V=-0.125V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Cu**
  -- included: [Cu+, [Cu2(Chlo)4]2-, [Cu(Chlo)2]-, [Cu(Chlo)3]2-, [Cu(Chlo)], Cu2+, [Cu(OH)]+, [Cu2(OH)2]2+, [Cu(OH)2], HCuO2-, [Cu3(OH)4]2+, CuO22-, [Cu(Citr)H], [Cu2(Citr)2]2-, [Cu2(Citr)(OH)], [Cu2(Citr)2(OH)]3-, [Cu2(Citr)2(OH)2]4-, [Cu(Chlo)]+, [(Cu2O)0.5](s), [Cu(Chloride ion)](s), CuO(s), [Cu(OH)2](s), Cu]
  -- excluded: [Cu2O, CuO, Cu(OH)2]
- **Fe**
  -- included: [Fe2+, [Fe(OH)]+, [Fe(OH)2], [Fe(OH)3]-, [Fe(OH)4]2-, [Fe(Citr)H2]+, [Fe(Citr)H], [Fe(Citr)2H]3-, [Fe(Citr)]-, [Fe2(Citr)2(OH)2]4-, [Fe(Chlo)]+, Fe3+, [Fe(OH)]2+, [Fe2(OH)2]4+, [Fe(OH)2]+, [Fe3(OH)4]5+, [Fe(OH)4]-, [Fe(Citr)H]+, [Fe(Citr)], [Fe(Citr)(OH)]-, [Fe2(Citr)2(OH)2]2-, [Fe(Chlo)2]+, [Fe(Chlo)]2+, [Fe(OH)2](s), [FeO(OH)(s,alpha)], [Fe(OH)3](s), Fe(OH)3 (hydr.), Fe]
  -- excluded: [HFeO2-, FeOH2+, FeO42-, Fe(OH)2 (hydr.), Fe3O4 (anh.), [(Fe2O3)0.5(s,alpha)], Fe2O3 (anh.)]
