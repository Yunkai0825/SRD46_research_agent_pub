# Solver report (Pourbaix)

## System
- Components: [Ag, Chloride ion]
- Constraints:
  -- component totals (M): Ag=0.001;Chloride ion=0.1
- Potential reference: SHE
- Domain (axis-aligned sweep box): (pH=[0, 14], E_V=[-0.5V, 1.2V])
- Coarse grid spacing: (ΔpH=not reported, ΔE_V=not reported)
- Final classified-grid spacing: (ΔpH=0.008, ΔE_V=0.0008V)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: Ag
- Dms_2: [Ag(Chloride ion)](s)

## Topology stats
- 2 dominant-species labels
- 2 connected regions
- 1 pairwise boundary curves
- 0 internal junction features
- 2 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept, E_V=0.3496V)
- Fixed sample indices: (pH=swept, E_V=sample 1062)
- samples 0–1750, (pH=[0, 14], E_V=0.3496V): [Ag(Chloride ion)](s) (Dms_2)

## Reference line (classified-grid cut) along E_V
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=7, E_V=swept)
- Fixed sample indices: (pH=sample 875, E_V=swept)
- samples 0–944, (pH=7, E_V=[-0.5V, 0.2552V]): Ag (Dms_1)
- samples 945–2125, (pH=7, E_V=[0.256V, 1.2V]): [Ag(Chloride ion)](s) (Dms_2)
  -- preceding label change is bracketed by adjacent samples (pH=7, E_V=[0.2552V, 0.256V])

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
- **DmsReg_1 {Ag}**
  -- Measure in the solver coordinate frame: 10.590048
  -- Neighboring regions:
    --- DmsReg_2 {[Ag(Chloride ion)](s)} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_1]
- **DmsReg_2 {[Ag(Chloride ion)](s)}**
  -- Measure in the solver coordinate frame: 13.234758
  -- Neighboring regions:
    --- DmsReg_1 {Ag} via DmsRegEq_1
  -- Junction features: [DmsRegEqJnc_2, DmsRegEqJnc_1]

### boundary curves/equilibria
#### solid–solid · redox (by species definition)
- **DmsRegEq_1: Ag | [Ag(Chloride ion)](s)**
  -- Intrinsic dimension: 1 (curve)
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Geometry: compact polyline
  -- Primary compact boundary vertices: [(pH=0, E_V=0.2556V), (pH=14, E_V=0.2556V)]
  -- Boundary/junction features: [DmsRegEqJnc_1, DmsRegEqJnc_2]
  -- Simplification metadata: {"method": "farthest_point_1d", "epsilon": 0.01, "epsilon_used": 0.00075, "resolution_tau_norm": 0.00075, "stop_epsilon": 0.00075, "min_points": 2, "loop_closed": false, "loop_protected": false, "stop_reason": "resolution", "planarity_added": 0, "separation_added": 0, "anchor_disabled": 0, "raw_n": 1752, "compact_n": 2, "compact_target_n": 6, "compact_indices": [0, 1751], "t_params": [0.0, 1.0], "envelope_n": 6, "envelope_pts": [(pH=0, E_V=0.2556V), (pH=14, E_V=0.2556V)], "envelope_t": [0.0, 1.0], "adaptive_n": 2, "adaptive_pts": [(pH=0, E_V=0.2556V), (pH=14, E_V=0.2556V)], "adaptive_t": [0.0, 1.0]}

### junction features
#### two solids
- **DmsRegEqJnc_1** — intrinsic dimension 0 (point)
  -- Dominant species: [Ag, [Ag(Chloride ion)](s)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=0, E_V=0.2556V)
- **DmsRegEqJnc_2** — intrinsic dimension 0 (point)
  -- Dominant species: [Ag, [Ag(Chloride ion)](s)]
  -- Neighboring regions: [DmsReg_1, DmsReg_2]
  -- Connected boundary manifolds: [DmsRegEq_1]
  -- At sweep limit: true
  -- Geometry: compact point (pH=14, E_V=0.2556V)

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Ag**
  -- included: [Ag+, [Ag(OH)] @25C, [Ag(OH)2]- @25C, [Ag(Chlo)2]-, [Ag(Chlo)3]2-, [Ag(Chlo)], [Ag(Chlo)4]3-, Ag2O, [Ag(Chloride ion)](s), Ag]
  -- excluded: [[Ag(OH)] @20C, [Ag(OH)2]- @20C, AgO-, [(Ag2O)0.5](s) @20C, [(Ag2O)0.5](s) @25C]
