# Solver report (Pourbaix)

## System
- Components: [Zn, Chloride ion]
- Constraints:
  -- component totals (M): Zn=0.001;Chloride ion=0.1
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-1.5V, 1.5V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.0125, ΔE_V=0.003125V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Zn
- Dms_2: [Zn(OH)4]2-
- Dms_3: ZnO (inactive)
- Dms_4: Zn2+

## Topology stats
- 4 dominant-species labels
- 4 connected regions
- 5 pairwise boundary curves
- 2 internal junction features
- 4 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=-0.0015625V)
- Fixed sample indices: (pH=swept, E_V=sample 479)
- samples 0–526, (pH=[0.00625, 6.58125], E_V=-0.0015625V): Zn2+ (Dms_4)
- samples 527–1076, (pH=[6.59375, 13.45625], E_V=-0.0015625V): ZnO (inactive) (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=[6.58125, 6.59375], E_V=-0.0015625V)
- samples 1077–1119, (pH=[13.46875, 13.99375], E_V=-0.0015625V): [Zn(OH)4]2- (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=[13.45625, 13.46875], E_V=-0.0015625V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6.99375, E_V=swept)
- Fixed sample indices: (pH=sample 559, E_V=swept)
- samples 0–196, (pH=6.99375, E_V=[-1.4984375V, -0.8859375V]): Zn (Dms_1)
- samples 197–959, (pH=6.99375, E_V=[-0.8828125V, 1.4984375V]): ZnO (inactive) (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.8859375V, -0.8828125V])

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
- **DmsReg_1 {Zn}**
  -- Measure in the solver coordinate frame: 7.2958594
  -- Neighboring regions:
    --- DmsReg_3 {[Zn(OH)4]2-} via DmsRegEq_1
    --- DmsReg_2 {ZnO (inactive)} via DmsRegEq_5
    --- DmsReg_4 {Zn2+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_1, DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_2]
- **DmsReg_2 {ZnO (inactive)}**
  -- Measure in the solver coordinate frame: 17.636133
  -- Neighboring regions:
    --- DmsReg_1 {Zn} via DmsRegEq_5
    --- DmsReg_3 {[Zn(OH)4]2-} via DmsRegEq_3
    --- DmsReg_4 {Zn2+} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_6, DmsRegEqJnc_5, DmsRegEqJnc_3, DmsRegEqJnc_4]
#### liquid
- **DmsReg_3 {[Zn(OH)4]2-}**
  -- Measure in the solver coordinate frame: 1.5050391
  -- Neighboring regions:
    --- DmsReg_1 {Zn} via DmsRegEq_1
    --- DmsReg_2 {ZnO (inactive)} via DmsRegEq_3
  -- Junction features: [DmsRegEqJnc_1, DmsRegEqJnc_5, DmsRegEqJnc_3]
- **DmsReg_4 {Zn2+}**
  -- Measure in the solver coordinate frame: 15.562969
  -- Neighboring regions:
    --- DmsReg_1 {Zn} via DmsRegEq_2
    --- DmsReg_2 {ZnO (inactive)} via DmsRegEq_4
  -- Junction features: [DmsRegEqJnc_6, DmsRegEqJnc_2, DmsRegEqJnc_4]

### boundary curves/equilibria
#### solid–liquid · redox (by species definition)
- **DmsRegEq_1: Zn | [Zn(OH)4]2-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-1.3312V), (pH=13.4625, E_V=-1.2687V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 64, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 63], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-1.3312V), (pH=13.4625, E_V=-1.2687V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-1.3312V), (pH=13.4625, E_V=-1.2687V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_2: Zn | Zn2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=-0.8625V), (pH=6.5875, E_V=-0.8625V)]
  -- Boundary/junction features: [DmsRegEqJnc_2, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 528, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 527], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=-0.8625V), (pH=6.5875, E_V=-0.8625V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=-0.8625V), (pH=6.5875, E_V=-0.8625V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_3: [Zn(OH)4]2- | ZnO (inactive)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=13.4625, E_V=-1.2687V), (pH=13.4625, E_V=1.5V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 887, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 886], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=13.4625, E_V=-1.2687V), (pH=13.4625, E_V=1.5V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=13.4625, E_V=-1.2687V), (pH=13.4625, E_V=1.5V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_4: ZnO (inactive) | Zn2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.5875, E_V=-0.8625V), (pH=6.5875, E_V=1.5V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 757, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 756], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.5875, E_V=-0.8625V), (pH=6.5875, E_V=1.5V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=6.5875, E_V=-0.8625V), (pH=6.5875, E_V=1.5V)], "adaptive_t": [0.0, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_5: Zn | ZnO (inactive)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=13.4625, E_V=-1.2687V), (pH=6.5875, E_V=-0.8625V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0014, "resolution_tau_norm": 0.0014, "stop_epsilon": 0.0014, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 681, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 680], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=13.4625, E_V=-1.2687V), (pH=6.5875, E_V=-0.8625V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=13.4625, E_V=-1.2687V), (pH=6.5875, E_V=-0.8625V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### one solid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Zn, [Zn(OH)4]2-]
  -- Neighboring regions: [DmsReg_1, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-1.3312V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Zn, Zn2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=-0.8625V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [[Zn(OH)4]2-, ZnO (inactive)]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point (pH=13.4625, E_V=1.5V)
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [ZnO (inactive), Zn2+]
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_4]
  -- At sweep limit: true
  -- Geometry: compact point (pH=6.5875, E_V=1.5V)
#### two solids
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Zn, [Zn(OH)4]2-, ZnO (inactive)]
  -- Neighboring regions: [DmsReg_1, DmsReg_3, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_3, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=13.4625, E_V=-1.2687V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [Zn, ZnO (inactive), Zn2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_4, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.5875, E_V=-0.8625V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Zn**
  -- included: [Zn2+, [Zn(OH)]+, [Zn(OH)2], [Zn(OH)3]-, [Zn(OH)4]2-, [Zn(Chlo)2], [Zn(Chlo)]+, ZnO (inactive), Zn(OH)2 (alpha), Zn]
  -- excluded: [ZnOH+, HZnO2-, ZnO22-, ZnO (active), Zn(OH)2 (epsilon), Zn(OH)2 (gamma), Zn(OH)2 (beta), ZnO, ZnO(s), [Zn(OH)2(s,epsilon)], Zn(OH)2 (amorphous), [Zn(OH)2(s,gamma)], [Zn(OH)2(s,beta1)], [Zn(OH)2(s,beta2)], [Zn(OH)2(s,delta)], [Zn(OH)2(s,am)]]
