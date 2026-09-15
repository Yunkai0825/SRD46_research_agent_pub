# Solver report (Freeform predominance)

## System
- Components: [Cd$+2, Cd$+0, Zn$+2, Zn$+0, Ammonia, Chloride ion]
- Constraints:
  -- not reported
- Potential reference: not reported
- Domain (axis-aligned sweep box): (pH=[6.9, 7.1])
- Coarse grid spacing: (ΔpH=not reported)
- Final classified-grid spacing: (ΔpH=0.1)
- Semantics: Each connected region is the dominant calculated entity for the reported classification rule, not the exclusive entity present and not a kinetic prediction.
- Cut basis: Final classified label grid; no cut transition is inferred from compact/RDP geometry.

## Dominant species catalog
- Dms_1: ZnO (inactive)

## Topology stats
- 1 dominant-species labels
- 1 connected regions
- 0 pairwise boundary points
- 0 internal junction features
- 0 junction features at a sweep limit
- Disconnected dominant species:
  -- none

## Reference line (classified-grid cut) along pH
- One grid line; every other axis is fixed at its grid sample nearest the domain center: (pH=swept)
- Fixed sample indices: (pH=swept)
- samples 0–2, (pH=[6.9, 7.1]): ZnO (inactive) (Dms_1)

## Topology details
// Coordinate order: [pH]

### canonical topology convention
| Canonical family | Meaning |
|---|---|
| `Dms_i` | Dominant-species label |
| `DmsReg_i` | Connected region |
| `DmsRegEq_i` | Connected pairwise boundary manifold |
| `DmsRegEqJnc_i` | Lower-dimensional junction feature |

### regions
- **DmsReg_1 {ZnO (inactive)}**
  -- Measure in the solver coordinate frame: 0.3
  -- Neighboring regions:
    --- none recorded
  -- Junction features: []

### boundary points/equilibria
- none

### junction features
- none

## Canonical-to-source lookup
The normalized JSON sidecar preserves the source collection, source ID, and intrinsic dimension for every canonical topology ID. Use that mapping for ID-scoped topology reads; the raw topology JSON is not part of this verdict text.

## Calculation species by principal element
- **Cd**
  -- included: [Cd2+, [Cd2(OH)]3+, [Cd(OH)]+, [Cd(OH)2], [Cd(OH)3]-, [Cd4(OH)4]4+, [Cd(OH)4]2-, [Cd(Ammo)4]2+, [Cd(Ammo)3]2+, [Cd(Ammo)2]2+, [Cd(Ammo)]2+, [Cd(Chlo)3]-, [Cd(Chlo)2], [Cd(Chlo)]+, [Cd(OH)2(s,beta)], CdO, Cd]
  -- excluded: [HCdO2-, Cd(OH)2 (inactive), [Cd(OH)2(s,gamma)], Cd(OH)2 (active)]
- **Zn**
  -- included: [Zn2+, [Zn(OH)]+, [Zn(OH)2], [Zn(OH)3]-, [Zn(OH)4]2-, [Zn(Ammo)4]2+, [Zn(Ammo)3]2+, [Zn(Ammo)2]2+, [Zn(Ammo)]2+, [Zn(Chlo)]+, [Zn(Chlo)2], ZnO (inactive), Zn(OH)2 (alpha), Zn]
  -- excluded: [ZnOH+, HZnO2-, ZnO22-, ZnO (active), Zn(OH)2 (epsilon), Zn(OH)2 (gamma), Zn(OH)2 (beta), ZnO, ZnO(s), [Zn(OH)2(s,epsilon)], Zn(OH)2 (amorphous), [Zn(OH)2(s,gamma)], [Zn(OH)2(s,beta1)], [Zn(OH)2(s,beta2)], [Zn(OH)2(s,delta)], [Zn(OH)2(s,am)]]
