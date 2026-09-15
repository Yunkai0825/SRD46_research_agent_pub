## Doability
Doable. Cu + NH3 is a well-catalogued SRD-46 system and the pipeline supports 2-D Pourbaix (E-pH) sweeps.

## Result
- System: 1 mM Cu(tot), 0.1 M NH3(tot), 25 C, I=0.1 m, SHE reference.
- Domain: pH [0,14], E [-1.0, +1.4] V. Final classified grid ΔpH=0.008, ΔE=0.0016 V.
- Method: pourbaix_sweep. Solver produced a classified label map with 9 dominant-species labels, 11 connected regions, 21 pairwise boundary curves, 11 internal junctions, 9 boundary-limit junctions. Cu(OH)2(s) was included in preference to CuO(s) (CuO/CuO listed as excluded in the calculation-species list); Cu2O was retained as the Cu(I) solid.
- All boundaries were extracted from the final label grid (no compact/RDP-inferred cuts).

## Analysis

### Region catalogue (11 connected regions, 9 unique labels)
Approximate locations from the verdict junctions/boundary vertices:

1. **DmsReg_1  Cu(s)** — reducing floor. Bounded above by the Cu/Cu2+ line at E≈+0.239 V for pH 0–5.05 (DmsRegEq_4), then by Cu/Cu2O rising from (5.05, 0.238) to (7.05, 0.119) (DmsRegEq_2), the Cu/[Cu(NH3)2]+ curve from (7.05, 0.119) to (11.47, -0.143) (DmsRegEq_3), and the Cu/Cu2O curve to (14, -0.292) (DmsRegEq_1).
2. **DmsReg_8  Cu2+** — acidic oxidised: pH 0–5.05, E above +0.239 V, up to the Cu2+/[Cu(NH3)]2+ vertical at pH 6.164 (DmsRegEq_21).
3. **DmsReg_11  [Cu(NH3)]2+** — narrow vertical sliver, pH 6.164–6.42, E from +0.284 up to the top (1.4 V). Bounded by Cu2+ (left), Cu2O (bottom-left, DmsRegEq_11), and Cu(OH)2(s) (right, DmsRegEq_19 at pH≈6.324 for high E).
4. **DmsReg_6  Cu2O** (Cu(I) solid, low-pH lobe) — small triangle centred near pH 5–6.9, E≈+0.24 to +0.28, between Cu(s), Cu2+/[Cu(NH3)]2+/[Cu(NH3)2]+ complexes, and Cu(OH)2(s).
5. **DmsReg_2  Cu2O** (Cu(I) solid, high-pH lobe) — near pH 11.5–14, E≈-0.29 to -0.14, between Cu(s), [Cu(NH3)2]+, Cu(OH)2(s), and CuO22-.
6. **DmsReg_4  [Cu(NH3)2]+** (Cu(I) ammine) — the reduced-ammine wedge spanning pH ≈7.05–11.47 just above the Cu/Cu2O line, extending upward to meet Cu(OH)2(s) and the Cu(II)-ammine complexes near E≈+0.13 to +0.27 V. Triple points at (7.052, 0.1192; Cu/Cu2O/[Cu(NH3)2]+), (11.468, -0.1432; Cu/Cu2O/[Cu(NH3)2]+), (11.468, -0.0152; Cu2O/[Cu(NH3)2]+/Cu(OH)2(s)), (10.324, 0.1352; [Cu(NH3)2]+/Cu(OH)2(s)/[Cu(NH3)4]2+), (8.204, 0.2616; [Cu(NH3)2]+/[Cu(NH3)4]2+/[Cu(NH3)3]2+), (7.996, 0.2712; [Cu(NH3)2]+/Cu(OH)2(s)/[Cu(NH3)3]2+).
7. **DmsReg_7  [Cu(NH3)4]2+** — the principal Cu(II)-ammine oxidised field: pH ≈8.20–10.32, E from ~+0.14 up to +1.4 V. Left boundary is the vertical [Cu(NH3)4]2+/[Cu(NH3)3]2+ line at pH=8.204 (DmsRegEq_20); right boundary is [Cu(NH3)4]2+/Cu(OH)2(s) essentially vertical at pH≈10.14 above E≈+0.28 (DmsRegEq_17); lower boundary is [Cu(NH3)2]+/[Cu(NH3)4]2+ (DmsRegEq_15).
8. **DmsReg_10  [Cu(NH3)3]2+** — thin vertical strip pH 7.996–8.204 from E≈+0.27 to +1.4 V, wedged between [Cu(NH3)4]2+ (right), Cu(OH)2(s) (left, DmsRegEq_18 vertical at pH≈8.172 above E≈+0.35), and the [Cu(NH3)2]+ Cu(I) wedge below.
9. **DmsReg_5  Cu(OH)2(s)** (main, high-pH lobe) — pH ≈10.14–13.58, E from ~+0.14 to +1.4 V; right edge is the vertical Cu(OH)2/CuO22- at pH=13.58 (DmsRegEq_12).
10. **DmsReg_9  Cu(OH)2(s)** (low-pH, oxidised lobe) — smaller region pH ≈6.32–7.996 above the Cu(NH3)_n ammine wedge and Cu2O lobe.
11. **DmsReg_3  CuO22-** — strong-alkali dissolved Cu(II): pH 13.58–14, spanning most of the E window down to the CuO22-/Cu2O curve at pH≈13.58–14, E≈-0.14 to -0.21.

### E–pH windows where soluble Cu(II)-ammine complexes dominate
The requested target (Cu(II)-ammine soluble complexes dominating both Cu(OH)2(s) and Cu(s)) is realised in three contiguous fields, all above the Cu(s)/complex reduction line and below/beside Cu(OH)2(s):

- **[Cu(NH3)4]2+ (DmsReg_7):** pH 8.20–10.32, E from the [Cu(NH3)2]+/[Cu(NH3)4]2+ curve (rising from (10.324, 0.135) to (8.204, 0.262)) up to +1.4 V. This is the dominant "ammoniacal Cu(II) leach" window and covers the largest oxidised-ammine area.
- **[Cu(NH3)3]2+ (DmsReg_10):** pH 7.996–8.204, E ≈ +0.27 to +1.4 V. A narrow transitional strip on the acidic side of [Cu(NH3)4]2+ where the fourth NH3 ligand cannot compete with protonation of free ammonia (pKa(NH4+)=9.26 from the reference table).
- **[Cu(NH3)]2+ (DmsReg_11):** pH 6.164–6.42, E ≥ +0.284 V. A very narrow sliver just above the Cu2+/ammine crossover, because at pH<pKa most ammonia is NH4+ and only the mono-ammine complex out-competes free Cu2+.

The Cu(I) ammine [Cu(NH3)2]+ (DmsReg_4) additionally dominates a large wedge pH 7.05–11.47 at moderately reducing E (Cu/Cu2O line up to ~+0.27 V); this is a *soluble* Cu-ammine field but Cu(I), not Cu(II).

### Chemistry driving the topology
- Below pH ≈9.26 (NH4+/NH3 pKa in the reference table), free ammonia is a small fraction of 0.1 M total; hence the Cu(II)-ammine fields are pushed to more alkaline pH and shrink on the acid side ([Cu(NH3)]2+ and [Cu(NH3)3]2+ appear only as narrow slivers). Above pH ≈9.3 free NH3 rises rapidly and Cu(NH3)4^2+ (log β4=+12.30) becomes competitive with Cu(OH)2(s) (log Ksp-like value -8.68 in the card convention), giving the broad [Cu(NH3)4]2+ field between pH 8.2 and 10.3.
- The Cu(OH)2(s) field is truncated on its low-pH side by ammine complexation (the boundary [Cu(NH3)4]2+/Cu(OH)2(s) is essentially vertical at pH≈10.14 above E≈+0.28 V — DmsRegEq_17). Without NH3 this boundary would sit near pH 6–7 for 1 mM Cu(II); ammonia shifts precipitation up by ~3–4 pH units, i.e. classic ammoniacal dissolution of Cu(OH)2.
- The Cu(I) ammine [Cu(NH3)2]+ (log β2=+9.92 for Cu(I)) stabilises Cu(I) in solution and lowers the Cu(s)/Cu(I) redox couple from the bare Cu/Cu2+ line (~+0.24 V at pH<5) down to ~-0.14 V at pH>11: this is the diagonal Cu(s)/[Cu(NH3)2]+ line (DmsRegEq_3) and the reason electrochemical Cu deposition in ammoniacal baths occurs at much more negative potentials than in acid sulfate.
- The Cu2O lobes appear where neither ammonia (protonated) nor hydroxide is strong enough to solubilise Cu(I): a low-pH lobe near pH 5–7 between Cu(s), Cu2+ and the emerging ammines; a high-pH lobe near pH 11.5–14 between [Cu(NH3)2]+, Cu(OH)2(s), and CuO22-.
- The strong-alkali CuO22- field appears only for pH>13.58; the Cu(OH)2/CuO22- line is vertical because it is a pure acid-base dissolution and does not involve electrons.
- Vertical boundaries (DmsRegEq_12, 17, 18, 19, 20, 21) are pH-only equilibria (no electron transfer between the two adjacent species); diagonal boundaries (Cu/Cu2+, Cu/Cu2O, Cu/[Cu(NH3)2]+, Cu2O/[Cu(NH3)2]+, [Cu(NH3)2]+/[Cu(NH3)4]2+) are proton-coupled redox equilibria with the expected ~-59 mV/pH type slopes modified by ligand stoichiometry.

### Convergence / evidence quality
The solver reports a fully classified fine grid (ΔpH=0.008, ΔE=0.0016 V; 1751 × 1501 samples) with 21 well-resolved boundary curves and 20 junction features; each label transition in the example cuts is bracketed within one grid step. No unconverged samples are flagged. Two dominant species (Cu2O, Cu(OH)2(s)) legitimately occupy two disconnected regions each — this is preserved in the topology and not collapsed. Cut-basis is the final classified label grid.

## Final deliverables

- [LC1/lc1_2_eqmap_card.json](<LC1/lc1_2_eqmap_card.json>)
- [LC1/lc1_sweep_input.json](<LC1/lc1_sweep_input.json>)
- [LC1/status.json](<LC1/status.json>)
- [LC2/free_energy_card.md](<LC2/free_energy_card.md>)
- [LC2/status.json](<LC2/status.json>)
- [LC2/thermodynamic_reference_constants.md](<LC2/thermodynamic_reference_constants.md>)
- [LC3/calc_input_card.json](<LC3/calc_input_card.json>)
- [LC3/status.json](<LC3/status.json>)
- [LD/answer.md](<LD/answer.md>)
- [LD/verdict.json](<LD/verdict.json>)
- [solver/pourbaix_Cu_+_Ammonia_Cu.png](<solver/pourbaix_Cu_+_Ammonia_Cu.png>)
- [solver/pourbaix_map_Cu_+_Ammonia_Cu.csv](<solver/pourbaix_map_Cu_+_Ammonia_Cu.csv>)
- [solver/speciation_full_Cu_+_Ammonia.csv](<solver/speciation_full_Cu_+_Ammonia.csv>)
- [solver/topo_csv_Cu_+_Ammonia_Cu/topo_features_0d.csv](<solver/topo_csv_Cu_+_Ammonia_Cu/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Ammonia_Cu/topo_features_1d.csv](<solver/topo_csv_Cu_+_Ammonia_Cu/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Ammonia_Cu/topo_metadata.json](<solver/topo_csv_Cu_+_Ammonia_Cu/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Ammonia_Cu/topo_regions.csv](<solver/topo_csv_Cu_+_Ammonia_Cu/topo_regions.csv>)
- [solver/topology_Cu_+_Ammonia_Cu.json](<solver/topology_Cu_+_Ammonia_Cu.json>)
- [solver/topology_Cu_+_Ammonia_Cu_verdict.json](<solver/topology_Cu_+_Ammonia_Cu_verdict.json>)
- [solver/topology_Cu_+_Ammonia_Cu_verdict.md](<solver/topology_Cu_+_Ammonia_Cu_verdict.md>)
- [verdict.json](<verdict.json>)
