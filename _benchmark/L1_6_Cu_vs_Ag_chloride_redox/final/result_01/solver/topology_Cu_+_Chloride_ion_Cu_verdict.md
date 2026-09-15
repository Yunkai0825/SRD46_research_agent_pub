# Solver report (Pourbaix)

## System
- Components: [Cu, Chloride ion]
- Constraints:
  -- component totals (M): Cu=0.001;Chloride ion=0.1
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-0.5V, 1.2V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.008, ΔE_V=0.0008V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Cu
- Dms_2: [(Cu2O)0.5](s)
- Dms_3: CuO(s)
- Dms_4: [Cu(Chlo)2]-
- Dms_5: Cu2+

## Topology stats
- 5 dominant-species labels
- 5 connected regions
- 7 pairwise boundary curves
- 3 internal junction features
- 5 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.3496V)
- Fixed sample indices: (pH=swept, E_V=sample 1062)
- samples 0–738, (pH=[0, 5.904], E_V=0.3496V): [Cu(Chlo)2]- (Dms_4)
- samples 739–1750, (pH=[5.912, 14], E_V=0.3496V): CuO(s) (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=[5.904, 5.912], E_V=0.3496V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=7, E_V=swept)
- Fixed sample indices: (pH=sample 875, E_V=swept)
- samples 0–706, (pH=7, E_V=[-0.5V, 0.0648V]): Cu (Dms_1)
- samples 707–931, (pH=7, E_V=[0.0656V, 0.2448V]): [(Cu2O)0.5](s) (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[0.0648V, 0.0656V])
- samples 932–2125, (pH=7, E_V=[0.2456V, 1.2V]): CuO(s) (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[0.2448V, 0.2456V])

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
  -- Measure in the solver coordinate frame: 6.679456
  -- Neighboring regions:
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_6
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_7, DmsRegEqJnc_5, DmsRegEqJnc_3]
- **DmsReg_2 {[(Cu2O)0.5](s)}**
  -- Measure in the solver coordinate frame: 1.3632
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_6
    --- DmsReg_3 {CuO(s)} via DmsRegEq_7
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_7, DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_8]
- **DmsReg_3 {CuO(s)}**
  -- Measure in the solver coordinate frame: 9.3895488
  -- Neighboring regions:
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_7
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_3
    --- DmsReg_5 {Cu2+} via DmsRegEq_5
  -- Junction features: [DmsRegEqJnc_6, DmsRegEqJnc_8, DmsRegEqJnc_2, DmsRegEqJnc_4]
#### liquid
- **DmsReg_4 {[Cu(Chlo)2]-}**
  -- Measure in the solver coordinate frame: 1.7961728
  -- Neighboring regions:
    --- DmsReg_1 {Cu} via DmsRegEq_2
    --- DmsReg_2 {[(Cu2O)0.5](s)} via DmsRegEq_4
    --- DmsReg_3 {CuO(s)} via DmsRegEq_3
    --- DmsReg_5 {Cu2+} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_3, DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_2, DmsRegEqJnc_1]
- **DmsReg_5 {Cu2+}**
  -- Measure in the solver coordinate frame: 4.5964288
  -- Neighboring regions:
    --- DmsReg_3 {CuO(s)} via DmsRegEq_5
    --- DmsReg_4 {[Cu(Chlo)2]-} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_4, DmsRegEqJnc_1]

### boundary curves/equilibria
#### liquid–liquid · redox (by species definition)
- **DmsRegEq_1: [Cu(Chlo)2]- | Cu2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=0.3804V), (pH=5.74, E_V=0.3804V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 719, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 718], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=0.3804V), (pH=5.74, E_V=0.3804V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=0.3804V), (pH=5.74, E_V=0.3804V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_2: Cu | [Cu(Chlo)2]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=0.0964V), (pH=6.46, E_V=0.0964V)]
  -- Boundary/junction features: [DmsRegEqJnc_3, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 809, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 808], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=0.0964V), (pH=6.46, E_V=0.0964V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=0.0964V), (pH=6.46, E_V=0.0964V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_3: CuO(s) | [Cu(Chlo)2]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.468, E_V=0.2772V), (pH=5.972, E_V=0.3396V), (pH=5.812, E_V=0.3652V), (pH=5.74, E_V=0.3804V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 221, "compact_n": 4, "compact_target_n": 6, "compact_indices": [0, 140, 192, 220], "t_params": [0.0, 0.67966, 0.89995, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.468, E_V=0.2772V), (pH=5.972, E_V=0.3396V), (pH=5.812, E_V=0.3652V), (pH=5.74, E_V=0.3804V)], "envelope_t": [0.0, 0.67966, 0.89995, 1.0], "adaptive_n": 4, "adaptive_pts": [(pH=6.468, E_V=0.2772V), (pH=5.972, E_V=0.3396V), (pH=5.812, E_V=0.3652V), (pH=5.74, E_V=0.3804V)], "adaptive_t": [0.0, 0.67966, 0.89995, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_4: [(Cu2O)0.5](s) | [Cu(Chlo)2]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.46, E_V=0.0964V), (pH=6.468, E_V=0.2772V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 228, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 227], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.46, E_V=0.0964V), (pH=6.468, E_V=0.2772V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=6.46, E_V=0.0964V), (pH=6.468, E_V=0.2772V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_5: CuO(s) | Cu2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=5.74, E_V=0.3804V), (pH=5.668, E_V=0.402V), (pH=5.636, E_V=0.418V), (pH=5.596, E_V=0.4804V), (pH=5.596, E_V=1.2V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1044, "compact_n": 5, "compact_target_n": 6, "compact_indices": [0, 36, 60, 143, 1043], "t_params": [0.0, 0.08309, 0.12264, 0.20457, 1.0], "envelope_n": 6, "envelope_pts": [(pH=5.74, E_V=0.3804V), (pH=5.668, E_V=0.402V), (pH=5.636, E_V=0.418V), (pH=5.596, E_V=0.4804V), (pH=5.596, E_V=1.2V)], "envelope_t": [0.0, 0.08309, 0.12264, 0.20457, 1.0], "adaptive_n": 5, "adaptive_pts": [(pH=5.74, E_V=0.3804V), (pH=5.668, E_V=0.402V), (pH=5.636, E_V=0.418V), (pH=5.596, E_V=0.4804V), (pH=5.596, E_V=1.2V)], "adaptive_t": [0.0, 0.08309, 0.12264, 0.20457, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_6: Cu | [(Cu2O)0.5](s)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.3492V), (pH=6.46, E_V=0.0964V)]
  -- Boundary/junction features: [DmsRegEqJnc_7, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1501, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 1500], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.3492V), (pH=6.46, E_V=0.0964V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.3492V), (pH=6.46, E_V=0.0964V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_7: [(Cu2O)0.5](s) | CuO(s)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.1684V), (pH=6.468, E_V=0.2772V)]
  -- Boundary/junction features: [DmsRegEqJnc_8, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1500, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 1499], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.1684V), (pH=6.468, E_V=0.2772V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.1684V), (pH=6.468, E_V=0.2772V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [[Cu(Chlo)2]-, Cu2+]
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.3804V)
#### one solid
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [CuO(s), [Cu(Chlo)2]-, Cu2+]
  -- Neighboring regions: [DmsReg_4, DmsReg_5, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_3, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=5.74, E_V=0.3804V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [Cu(Chlo)2]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.0964V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [CuO(s), Cu2+]
  -- Neighboring regions: [DmsReg_3, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_5]
  -- At sweep limit: true
  -- Geometry: compact point (pH=5.596, E_V=1.2V)
#### two solids
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [(Cu2O)0.5](s), [Cu(Chlo)2]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_4, DmsRegEq_6]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.46, E_V=0.0964V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Cu2O)0.5](s), CuO(s), [Cu(Chlo)2]-]
  -- Neighboring regions: [DmsReg_3, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_4, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.468, E_V=0.2772V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [Cu, [(Cu2O)0.5](s)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.3492V)
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [[(Cu2O)0.5](s), CuO(s)]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_7]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.1684V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Cu**
  -- included: [Cu+, [Cu2(Chlo)4]2-, [Cu(Chlo)2]-, [Cu(Chlo)3]2-, [Cu(Chlo)], Cu2+, [Cu(OH)]+, [Cu2(OH)2]2+, [Cu(OH)2], HCuO2-, [Cu3(OH)4]2+, CuO22-, [Cu(Chlo)]+, [(Cu2O)0.5](s), [Cu(Chloride ion)](s), CuO(s), [Cu(OH)2](s), Cu]
  -- excluded: [Cu2O, CuO, Cu(OH)2]
