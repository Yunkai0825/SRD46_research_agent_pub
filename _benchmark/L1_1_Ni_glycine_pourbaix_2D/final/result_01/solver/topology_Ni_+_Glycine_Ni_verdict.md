# Solver report (Pourbaix)

## System
- Components: [Ni, Glycine]
- Constraints:
  -- component totals (M): Ni=0.001;Glycine=0.01
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-1V, 1.6V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.0125, ΔE_V=0.0025V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Ni
- Dms_2: Ni(OH)2
- Dms_3: [Ni(Glyc)3]-
- Dms_4: [Ni(Glyc)2]
- Dms_5: Ni2+
- Dms_6: [Ni(Glyc)]+
- Dms_7: Ni2O3.H2O

## Topology stats
- 7 dominant-species labels
- 7 connected regions
- 10 pairwise boundary curves
- 4 internal junction features
- 8 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.30125V)
- Fixed sample indices: (pH=swept, E_V=sample 520)
- samples 0–485, (pH=[0.00625, 6.06875], E_V=0.30125V): Ni2+ (Dms_5)
- samples 486–543, (pH=[6.08125, 6.79375], E_V=0.30125V): [Ni(Glyc)]+ (Dms_6)
  -- preceding label change is bracketed by adjacent samples (pH=[6.06875, 6.08125], E_V=0.30125V)
- samples 544–637, (pH=[6.80625, 7.96875], E_V=0.30125V): [Ni(Glyc)2] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=[6.79375, 6.80625], E_V=0.30125V)
- samples 638–898, (pH=[7.98125, 11.23125], E_V=0.30125V): [Ni(Glyc)3]- (Dms_3)
  -- preceding label change is bracketed by adjacent samples (pH=[7.96875, 7.98125], E_V=0.30125V)
- samples 899–1119, (pH=[11.24375, 13.99375], E_V=0.30125V): Ni(OH)2 (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=[11.23125, 11.24375], E_V=0.30125V)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=6.99375, E_V=swept)
- Fixed sample indices: (pH=sample 559, E_V=swept)
- samples 0–249, (pH=6.99375, E_V=[-0.99875V, -0.37625V]): Ni (Dms_1)
- samples 250–1039, (pH=6.99375, E_V=[-0.37375V, 1.59875V]): [Ni(Glyc)2] (Dms_4)
  -- preceding label change is bracketed by adjacent samples (pH=6.99375, E_V=[-0.37625V, -0.37375V])

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
- **DmsReg_1 {Ni}**
  -- Measure in the solver coordinate frame: 7.813375
  -- Neighboring regions:
    --- DmsReg_2 {Ni(OH)2} via DmsRegEq_9
    --- DmsReg_4 {[Ni(Glyc)3]-} via DmsRegEq_4
    --- DmsReg_5 {[Ni(Glyc)2]} via DmsRegEq_5
    --- DmsReg_7 {Ni2+} via DmsRegEq_6
    --- DmsReg_6 {[Ni(Glyc)]+} via DmsRegEq_7
  -- Junction features: [DmsRegEqJnc_10, DmsRegEqJnc_9, DmsRegEqJnc_4, DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_7]
- **DmsReg_2 {Ni(OH)2}**
  -- Measure in the solver coordinate frame: 5.9924063
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_9
    --- DmsReg_4 {[Ni(Glyc)3]-} via DmsRegEq_8
    --- DmsReg_3 {Ni2O3.H2O} via DmsRegEq_10
  -- Junction features: [DmsRegEqJnc_10, DmsRegEqJnc_9, DmsRegEqJnc_8, DmsRegEqJnc_11, DmsRegEqJnc_12]
- **DmsReg_3 {Ni2O3.H2O}**
  -- Measure in the solver coordinate frame: 0.1680625
  -- Neighboring regions:
    --- DmsReg_2 {Ni(OH)2} via DmsRegEq_10
  -- Junction features: [DmsRegEqJnc_11, DmsRegEqJnc_12]
#### liquid
- **DmsReg_4 {[Ni(Glyc)3]-}**
  -- Measure in the solver coordinate frame: 6.9043125
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_4
    --- DmsReg_2 {Ni(OH)2} via DmsRegEq_8
    --- DmsReg_5 {[Ni(Glyc)2]} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_9, DmsRegEqJnc_8, DmsRegEqJnc_1]
- **DmsReg_5 {[Ni(Glyc)2]}**
  -- Measure in the solver coordinate frame: 2.3467187
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_5
    --- DmsReg_4 {[Ni(Glyc)3]-} via DmsRegEq_1
    --- DmsReg_6 {[Ni(Glyc)]+} via DmsRegEq_2
  -- Junction features: [DmsRegEqJnc_4, DmsRegEqJnc_5, DmsRegEqJnc_1, DmsRegEqJnc_2]
- **DmsReg_6 {[Ni(Glyc)]+}**
  -- Measure in the solver coordinate frame: 1.4165625
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_7
    --- DmsReg_5 {[Ni(Glyc)2]} via DmsRegEq_2
    --- DmsReg_7 {Ni2+} via DmsRegEq_3
  -- Junction features: [DmsRegEqJnc_5, DmsRegEqJnc_6, DmsRegEqJnc_2, DmsRegEqJnc_3]
- **DmsReg_7 {Ni2+}**
  -- Measure in the solver coordinate frame: 11.758563
  -- Neighboring regions:
    --- DmsReg_1 {Ni} via DmsRegEq_6
    --- DmsReg_6 {[Ni(Glyc)]+} via DmsRegEq_3
  -- Junction features: [DmsRegEqJnc_6, DmsRegEqJnc_7, DmsRegEqJnc_3]

### boundary curves/equilibria
#### liquid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_1: [Ni(Glyc)3]- | [Ni(Glyc)2]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.9125, E_V=-0.43V), (pH=7.975, E_V=-0.42V), (pH=7.975, E_V=1.6V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_1]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 818, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 9, 817], "t_params": [0.0, 0.0304, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.9125, E_V=-0.43V), (pH=7.975, E_V=-0.42V), (pH=7.975, E_V=1.6V)], "envelope_t": [0.0, 0.0304, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=7.9125, E_V=-0.43V), (pH=7.975, E_V=-0.42V), (pH=7.975, E_V=1.6V)], "adaptive_t": [0.0, 0.0304, 1.0]}
- **DmsRegEq_2: [Ni(Glyc)2] | [Ni(Glyc)]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.7625, E_V=-0.365V), (pH=6.8, E_V=-0.3575V), (pH=6.8, E_V=1.6V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 790, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 6, 789], "t_params": [0.0, 0.0192, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.7625, E_V=-0.365V), (pH=6.8, E_V=-0.3575V), (pH=6.8, E_V=1.6V)], "envelope_t": [0.0, 0.0192, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.7625, E_V=-0.365V), (pH=6.8, E_V=-0.3575V), (pH=6.8, E_V=1.6V)], "adaptive_t": [0.0, 0.0192, 1.0]}
- **DmsRegEq_3: Ni2+ | [Ni(Glyc)]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.0625, E_V=-0.345V), (pH=6.075, E_V=1.6V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_3]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 780, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 779], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.0625, E_V=-0.345V), (pH=6.075, E_V=1.6V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=6.0625, E_V=-0.345V), (pH=6.075, E_V=1.6V)], "adaptive_t": [0.0, 1.0]}
#### solid–liquid · redox (by species definition)
- **DmsRegEq_4: Ni | [Ni(Glyc)3]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=11.2375, E_V=-0.5475V), (pH=10.2, E_V=-0.545V), (pH=9.4375, E_V=-0.5275V), (pH=8.8625, E_V=-0.4975V), (pH=7.9125, E_V=-0.43V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_4]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 314, "compact_n": 5, "compact_target_n": 6, "compact_indices": [0, 84, 152, 210, 313], "t_params": [0.0, 0.3117, 0.5409, 0.7139, 1.0], "envelope_n": 6, "envelope_pts": [(pH=11.2375, E_V=-0.5475V), (pH=10.2, E_V=-0.545V), (pH=9.4375, E_V=-0.5275V), (pH=8.8625, E_V=-0.4975V), (pH=7.9125, E_V=-0.43V)], "envelope_t": [0.0, 0.3117, 0.5409, 0.7139, 1.0], "adaptive_n": 5, "adaptive_pts": [(pH=11.2375, E_V=-0.5475V), (pH=10.2, E_V=-0.545V), (pH=9.4375, E_V=-0.5275V), (pH=8.8625, E_V=-0.4975V), (pH=7.9125, E_V=-0.43V)], "adaptive_t": [0.0, 0.3117, 0.5409, 0.7139, 1.0]}
- **DmsRegEq_5: Ni | [Ni(Glyc)2]**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_5]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=7.9125, E_V=-0.43V), (pH=7.2625, E_V=-0.3875V), (pH=6.7625, E_V=-0.365V)]
  -- Boundary/junction features: [DmsRegEqJnc_4, DmsRegEqJnc_5]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 119, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 69, 118], "t_params": [0.0, 0.5655, 1.0], "envelope_n": 6, "envelope_pts": [(pH=7.9125, E_V=-0.43V), (pH=7.2625, E_V=-0.3875V), (pH=6.7625, E_V=-0.365V)], "envelope_t": [0.0, 0.5655, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=7.9125, E_V=-0.43V), (pH=7.2625, E_V=-0.3875V), (pH=6.7625, E_V=-0.365V)], "adaptive_t": [0.0, 0.5655, 1.0]}
- **DmsRegEq_6: Ni | Ni2+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_7]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.0625, E_V=-0.345V), (pH=5.3125, E_V=-0.335V), (pH=0, E_V=-0.335V)]
  -- Boundary/junction features: [DmsRegEqJnc_6, DmsRegEqJnc_7]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 490, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 64, 489], "t_params": [0.0, 0.1237, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.0625, E_V=-0.345V), (pH=5.3125, E_V=-0.335V), (pH=0, E_V=-0.335V)], "envelope_t": [0.0, 0.1237, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.0625, E_V=-0.345V), (pH=5.3125, E_V=-0.335V), (pH=0, E_V=-0.335V)], "adaptive_t": [0.0, 0.1237, 1.0]}
- **DmsRegEq_7: Ni | [Ni(Glyc)]+**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_6]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=6.7625, E_V=-0.365V), (pH=6.275, E_V=-0.3475V), (pH=6.0625, E_V=-0.345V)]
  -- Boundary/junction features: [DmsRegEqJnc_5, DmsRegEqJnc_6]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 65, "compact_n": 3, "compact_target_n": 6, "compact_indices": [0, 46, 64], "t_params": [0.0, 0.6966, 1.0], "envelope_n": 6, "envelope_pts": [(pH=6.7625, E_V=-0.365V), (pH=6.275, E_V=-0.3475V), (pH=6.0625, E_V=-0.345V)], "envelope_t": [0.0, 0.6966, 1.0], "adaptive_n": 3, "adaptive_pts": [(pH=6.7625, E_V=-0.365V), (pH=6.275, E_V=-0.3475V), (pH=6.0625, E_V=-0.345V)], "adaptive_t": [0.0, 0.6966, 1.0]}
#### solid–liquid · non-redox (by species definition, may vary with detailed converged topo)
- **DmsRegEq_8: Ni(OH)2 | [Ni(Glyc)3]-**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=11.2375, E_V=-0.5475V), (pH=11.2375, E_V=1.6V)]
  -- Boundary/junction features: [DmsRegEqJnc_9, DmsRegEqJnc_8]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 860, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 859], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=11.2375, E_V=-0.5475V), (pH=11.2375, E_V=1.6V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=11.2375, E_V=-0.5475V), (pH=11.2375, E_V=1.6V)], "adaptive_t": [0.0, 1.0]}
#### solid–solid · redox (by species definition)
- **DmsRegEq_9: Ni | Ni(OH)2**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=-0.7125V), (pH=11.2375, E_V=-0.5475V)]
  -- Boundary/junction features: [DmsRegEqJnc_10, DmsRegEqJnc_9]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 288, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 287], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=-0.7125V), (pH=11.2375, E_V=-0.5475V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=-0.7125V), (pH=11.2375, E_V=-0.5475V)], "adaptive_t": [0.0, 1.0]}
- **DmsRegEq_10: Ni(OH)2 | Ni2O3.H2O**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=14, E_V=1.46V), (pH=11.6375, E_V=1.6V)]
  -- Boundary/junction features: [DmsRegEqJnc_11, DmsRegEqJnc_12]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.0013, "resolution_tau_norm": 0.0013, "stop_epsilon": 0.0013, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 246, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 245], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=14, E_V=1.46V), (pH=11.6375, E_V=1.6V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=14, E_V=1.46V), (pH=11.6375, E_V=1.6V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### all liquid
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [[Ni(Glyc)3]-, [Ni(Glyc)2]]
  -- Neighboring regions: [DmsReg_4, DmsReg_5]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=7.975, E_V=1.6V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [[Ni(Glyc)2], [Ni(Glyc)]+]
  -- Neighboring regions: [DmsReg_5, DmsReg_6]
  -- Connected boundary manifolds: [DmsRegEq_2]
  -- At sweep limit: true
  -- Geometry: compact point (pH=6.8, E_V=1.6V)
- **DmsRegEqJnc_3** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni2+, [Ni(Glyc)]+]
  -- Neighboring regions: [DmsReg_6, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_3]
  -- At sweep limit: true
  -- Geometry: compact point (pH=6.075, E_V=1.6V)
#### one solid
- **DmsRegEqJnc_4** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, [Ni(Glyc)3]-, [Ni(Glyc)2]]
  -- Neighboring regions: [DmsReg_4, DmsReg_5, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_1, DmsRegEq_4, DmsRegEq_5]
  -- At sweep limit: false
  -- Geometry: compact point (pH=7.9125, E_V=-0.43V)
- **DmsRegEqJnc_5** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, [Ni(Glyc)2], [Ni(Glyc)]+]
  -- Neighboring regions: [DmsReg_5, DmsReg_6, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_2, DmsRegEq_5, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.7625, E_V=-0.365V)
- **DmsRegEqJnc_6** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni2+, [Ni(Glyc)]+]
  -- Neighboring regions: [DmsReg_6, DmsReg_7, DmsReg_1]
  -- Connected boundary manifolds: [DmsRegEq_3, DmsRegEq_6, DmsRegEq_7]
  -- At sweep limit: false
  -- Geometry: compact point (pH=6.0625, E_V=-0.345V)
- **DmsRegEqJnc_7** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni2+]
  -- Neighboring regions: [DmsReg_1, DmsReg_7]
  -- Connected boundary manifolds: [DmsRegEq_6]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=-0.335V)
- **DmsRegEqJnc_8** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni(OH)2, [Ni(Glyc)3]-]
  -- Neighboring regions: [DmsReg_2, DmsReg_4]
  -- Connected boundary manifolds: [DmsRegEq_8]
  -- At sweep limit: true
  -- Geometry: compact point (pH=11.2375, E_V=1.6V)
#### two solids
- **DmsRegEqJnc_9** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni(OH)2, [Ni(Glyc)3]-]
  -- Neighboring regions: [DmsReg_1, DmsReg_4, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_4, DmsRegEq_8, DmsRegEq_9]
  -- At sweep limit: false
  -- Geometry: compact point (pH=11.2375, E_V=-0.5475V)
- **DmsRegEqJnc_10** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni, Ni(OH)2]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_9]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=-0.7125V)
- **DmsRegEqJnc_11** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni(OH)2, Ni2O3.H2O]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_10]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=1.46V)
- **DmsRegEqJnc_12** — intrinsic dimension 0 (point)
  -- Dominant species: [Ni(OH)2, Ni2O3.H2O]
  -- Neighboring regions: [DmsReg_2, DmsReg_3]
  -- Connected boundary manifolds: [DmsRegEq_10]
  -- At sweep limit: true
  -- Geometry: compact point (pH=11.6375, E_V=1.6V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Ni**
  -- included: [Ni2+, [Ni(OH)]+, [Ni(OH)2], [Ni(OH)3]-, [Ni4(OH)4]4+, [Ni(Glyc)]+, [Ni(Glyc)2], [Ni(Glyc)3]-, Ni(OH)2, Ni3O4.2H2O, Ni2O3.H2O, NiO2.2H2O, Ni]
  -- excluded: [HNiO2-, NiO, [Ni(OH)2](s)]
