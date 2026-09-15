## Doability
Doable and executed. Both metals, all four ligands (citrate, glycine, chloride, ammonia) and OH/redox families are present in the SRD-46/Atlas card at 25 °C, I = 0.1 m. The requested Fe oxides (Fe2O3, CuO, FeOOH, Fe3O4) were explicitly excluded from the include set (see the "excluded" lists in the verdicts); ferrihydrite Fe(OH)3(s), Fe(OH)2(s), Cu(OH)2(s), Cu2O(s) and metallic Cu/Fe remained enabled, consistent with a water-rich electrodeposition context.

## Result
- System: [Cu] = [Fe] = 1 mM; [citrate] = [glycine] = 10 mM; [NH3]_tot = [Cl−] = 0.1 M; T = 25 °C; I = 0.1 m; SHE reference.
- Method: two-dimensional Pourbaix (`pourbaix_sweep`), independent axes pH ∈ [0, 14] and E ∈ [−1.0, +1.5] V.
- Final classified grid: ΔpH = 0.0125, ΔE = 0.003125 V (1121 × 800 cells per element map). Two per-element predominance maps were built (Cu, Fe) plus a joint full-speciation CSV.
- Copper map: 10 dominant labels, 13 connected regions, 26 pairwise boundaries, 14 internal + 10 boundary-limit junctions. Three copper labels occupy disconnected regions: [Cu(Glyc)2] (2 regions), [Cu2(Citr)2(OH)2]4− (2), [Cu(Chlo)2]− (2). No convergence flags were raised on the verdict-reported regions.
- Iron map: 11 dominant labels, 13 connected regions, 29 boundaries, 17 internal + 7 boundary-limit junctions. [Fe(Citr)]− occupies three disconnected regions. All classified samples were assigned.

## Analysis

### Copper partitioning across the E–pH field
At reducing potentials (E ≲ −0.15 V) copper is metallic Cu(0) across nearly the whole pH span (DmsReg_1, measure 13.58 — by far the largest region), consistent with the Cu2+/Cu couple lying near E° ≈ +0.34 V but with strong Cu(I)/Cu(II) stabilization by the ligands pulling the metal deposition boundary down. Rising E crosses the Cu/aqueous-Cu(II)-complex line at values that depend strongly on pH because the aqueous product changes with ligand availability:

- **Very acidic, pH < ~3.2**: Cu2+ (DmsReg_13) is the dominant Cu(II) form above the Cu-metal line (Cu | [Cu(Chlo)2]− and Cu | Cu2+ boundaries near E ≈ +0.10–0.38 V). Chloride complexation only competes weakly here: [Cu(Chlo)2]− (log β = +6.06 for Cu(I)!, i.e. this label corresponds to the reduced Cu(I) dichloro complex from the card) dominates a narrow strip DmsReg_11 between the Cu-metal region and Cu2+ from pH 0 up to the Cu(Citr) region at pH ≈ 3.2 (junction DmsRegEqJnc_14 at pH 3.225, E +0.381 V). The junction {[Cu(Chlo)2]−, [Cu2(Citr)2(OH)]3−, Cu2+} at (3.225, +0.381) marks the point at which citrate coordination overtakes free Cu2+.
- **pH 3.2 – 6.0**: The Cu(II) side is entirely captured by citrate complexes — first [Cu2(Citr)2(OH)]3− (DmsReg_12, pH 3.2–4.0) and then the bis-hydroxo dimer [Cu2(Citr)2(OH)2]4− (DmsReg_9, the dominant Cu(II) speciation over a very large slice, measure 4.95). The transition at pH 4.0 (junction DmsRegEqJnc_13, E +0.275 V) is a stepwise deprotonation of the μ-OH bridge, driven by the citrate log βs +11.20 → +6.34 (the numerical drop reflects the extra OH lost from H+·L notation, so the effective proton-release constant is ≈10^−4.86).
- **pH 6.0 – 7.4**: Chloride returns briefly along the Cu(0) upper edge as [Cu(Chlo)2]− (DmsReg_11/10) between the metal and the citrate dimer, because at these pH the citrate is only just fully deprotonated and 0.1 M Cl− wins on mass action.
- **pH 7.4 – 10.8**: The glycine bischelate [Cu(Glyc)2] (log β2 = 15.1) dominates the Cu(II) side (DmsReg_6, measure 5.30). The Cu | [Cu(Glyc)2] boundary at E ≈ +0.016–0.038 V is essentially the Cu2+/Cu potential shifted cathodic by RT/2F·ln β2 ≈ 0.44 V, which is exactly the observed depression from ~+0.34 V to ~+0.02 V.
- **pH 10.8 – 11.55**: A narrow ammonia window opens — [Cu(Ammo)2]+ (DmsReg_4) sits between Cu(0) and Cu2O(s) around the triple point (10.463, −0.141). This is the classic ammoniacal Cu(I) plating chemistry: ammonia (pKa 9.26) becomes free enough here to build up the log β2(Cu(I)) = 9.92 diammine.
- **pH > 11.5**: Solid Cu(OH)2(s) (DmsReg_5, measure 3.14) precipitates and dominates all the way to pH ≈ 13.59, where dissolution as CuO22− takes over (junction at (13.588, −0.084)). The narrow Cu2O(s) sliver (DmsReg_2) survives just below Cu(OH)2 at low E, exactly as expected from the Cu(I) dissolution log β = +0.70 for ½Cu2O.

### Iron partitioning across the E–pH field
Metallic Fe(0) (DmsReg_1) dominates only at strongly reducing potentials; its upper boundary is exceptionally low and pH-dependent, going from E ≈ −0.54 V at pH 0 (Fe/Fe2+ line, DmsRegEq_5, essentially the standard −0.44 V shifted by log-scale conventions and I=0.1) down to −0.92 V at pH 14. Above that line the aqueous Fe(II) fields are:

- **pH < 4.04**: Fe2+ (DmsReg_7, measure 4.65) — the free hexaquo ion; neither chloride (log β = −0.20 for FeCl+) nor ammonia (log β1 = +1.40) can compete at 0.1 M against free water.
- **pH 4.04 – 6.36**: Citrate takes over. First [Fe(Citr)]− (DmsReg_6, log β = +4.56, measure 2.74), then the μ-hydroxo dimer [Fe2(Citr)2(OH)2]2− near pH 6 (DmsReg_10, measure 4.07). The pH-4 crossover from Fe2+ to Fe(Citr)− matches H3Cit's third pKa ≈ 5.65 combined with the +4.56 formation constant.
- **pH > 6.3, Fe(II) side**: Fe(OH)2(s) (small region DmsReg_3, measure 0.31) survives only in a narrow high-pH, low-E wedge between Fe(0) and the Fe(III) hydroxide field; [Fe(OH)3]− (DmsReg_2) is dominant on the extreme high-pH, low-E edge.

On the Fe(III) side the exclusion of Fe2O3, Fe3O4 and FeOOH leaves **Fe(OH)3(s) (ferrihydrite, DmsReg_8) as the single dominant solid, and it occupies a huge region (measure 7.16 — the largest single Fe label)** from pH ≈ 6.3 up to pH 14 and from E ≈ +0.03 V up to the ferrate line at E ≈ +0.90–1.0 V. Its lower boundary against [Fe(Citr)]− (DmsRegEq_22) runs from (8.06, −0.144) down to (6.36, +0.156) — i.e. citrate can hold Fe(III) in solution up to about pH 6.3 but no further, because ferrihydrite dissolution is log Ksp,dis = −3.20 (Fe(OH)3(s) ⇌ Fe3+ + 3OH−).

The Fe(III) aqueous pocket at low pH is small but well resolved: Fe3+ (DmsReg_13) is dominant only in a wedge pH < 1.46, E > +0.77 V (Fe2+/Fe3+ line, close to the textbook +0.771 V and card values recovered directly by the solver). Between pH 1.46 and 1.89, [Fe(Citr)] (neutral, log β = +11.19) dominates (DmsReg_12), and from pH 1.89 to 4.08 the Fe(III) citrate dimer [Fe2(Citr)2(OH)2]2− (DmsReg_10, log β = +21.20) takes over. FeO42− (ferrate, DmsReg_11) appears only above E ≈ +0.9 V and is nearly independent of pH, as expected for the high-order Fe(VI)/Fe(III) couple.

No Fe(II)–chloride, Fe(II)–ammonia or Fe(III)–glycine complex became dominant anywhere, because their log βs (Fe(Chlo)+ −0.20; Fe(Ammo)_n +1.4 to +2.75; Fe(Glyc)2+ −8.57) are far too small at these totals.

### Principal boundaries and triple points (with card values actually used)
Using the log β values in the reference-constants table (SRD-46/Atlas rows with `include=true`):

**Copper triple points (junctions):**
| Junction | pH | E (V) | Species |
|---|---:|---:|---|
| DmsRegEqJnc_1 | 10.46 | −0.141 | Cu / Cu2O(s) / [Cu(Ammo)2]+ |
| DmsRegEqJnc_4 | 7.78 | +0.016 | Cu / [Cu(Ammo)2]+ / [Cu(Glyc)2] |
| DmsRegEqJnc_3 | 10.81 | +0.006 | Cu2O(s) / [Cu(Ammo)2]+ / [Cu(Glyc)2] |
| DmsRegEqJnc_5 | 11.34 | +0.034 | Cu2O(s) / [Cu(Glyc)2] / [Cu2(Citr)2(OH)2]4− |
| DmsRegEqJnc_8 | 11.55 | +0.038 | Cu2O(s) / Cu(OH)2(s) / [Cu2(Citr)2(OH)2]4− |
| DmsRegEqJnc_2 | 13.59 | −0.084 | Cu2O(s) / CuO22− / Cu(OH)2(s) |
| DmsRegEqJnc_13 | 4.00 | +0.275 | [Cu2(Citr)2(OH)2]4− / [Cu(Chlo)2]− / [Cu2(Citr)2(OH)]3− |
| DmsRegEqJnc_14 | 3.23 | +0.381 | [Cu(Chlo)2]− / [Cu2(Citr)2(OH)]3− / Cu2+ |

**Iron triple points:**
| Junction | pH | E (V) | Species |
|---|---:|---:|---|
| DmsRegEqJnc_6 | 4.04 | −0.553 | Fe / Fe2+ / [Fe(Citr)]− |
| DmsRegEqJnc_2 | 10.49 | −0.653 | Fe / Fe(OH)2(s) / [Fe2(Citr)2(OH)2]4− |
| DmsRegEqJnc_1 | 11.91 | −0.738 | Fe / [Fe(OH)3]− / Fe(OH)2(s) |
| DmsRegEqJnc_8 | 10.49 | −0.438 | Fe(OH)2(s) / [Fe2(Citr)2(OH)2]4− / Fe(OH)3(s) |
| DmsRegEqJnc_12 | 6.36 | +0.156 | [Fe(Citr)]− / Fe(OH)3(s) / [Fe2(Citr)2(OH)2]2− |
| DmsRegEqJnc_13 | 4.08 | +0.291 | Fe2+ / [Fe(Citr)]− / [Fe2(Citr)2(OH)2]2− |
| DmsRegEqJnc_14 | 1.89 | +0.700 | Fe2+ / [Fe2(Citr)2(OH)2]2− / [Fe(Citr)] |
| DmsRegEqJnc_15 | 1.46 | +0.772 | Fe2+ / [Fe(Citr)] / Fe3+ |
| DmsRegEqJnc_16 | 6.36 | +0.975 | Fe(OH)3(s) / [Fe2(Citr)2(OH)2]2− / FeO42− |

All junction coordinates and boundary curves are read directly from the solver's classified label grid; the compact polylines in DmsRegEq_* traces (e.g. Fe(OH)3(s)/FeO42− running from (14.0, +0.228) down to (6.36, +0.975), slope ≈ −0.1 V/pH consistent with 2H+/e− for the FeO4^2− + 8H+ + 3e− ⇌ Fe(OH)3 + … half-reaction) confirm the correct Nernst behaviour.

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
- [solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu.png](<solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu.png>)
- [solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe.png](<solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe.png>)
- [solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu.csv](<solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu.csv>)
- [solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe.csv](<solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe.csv>)
- [solver/speciation_full_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion.csv](<solver/speciation_full_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_features_0d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_features_1d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_metadata.json](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_regions.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu/topo_regions.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_features_0d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_features_1d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_metadata.json](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_regions.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe/topo_regions.csv>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu_verdict.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu_verdict.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu_verdict.md](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Cu_verdict.md>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe_verdict.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe_verdict.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe_verdict.md](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion_Fe_verdict.md>)
- [verdict.json](<verdict.json>)
