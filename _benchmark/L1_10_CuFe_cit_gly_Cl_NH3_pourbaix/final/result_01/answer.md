## Doability
Doable. All requested metals (Cu, Fe) and ligands (citrate, glycine, ammonia, chloride) are present in the SRD-46 / Atlas cards, and the pipeline supports a joint 2-D Pourbaix sweep. Both per-element predominance verdicts were produced and are internally consistent.

## Result
- **System.** Single aqueous pot, 25 °C, I = 0.1 m: 1 mM Cu(II) + 1 mM Fe(III) with 10 mM citrate, 10 mM glycine, 0.1 M ammonia, 0.1 M chloride.
- **Method.** `pourbaix_sweep` over pH 0–14 and E_SHE −1.0 to +1.5 V. Final classified-grid spacing ΔpH = 0.2, ΔE = 0.05 V (71 × 51 nodes). Two element-projected predominance maps were built from one joint speciation solve.
- **Convergence.** The full-speciation CSV carries a `converged` column for every (pH, E) node; the first sampled row is `converged=True` with residual ~7 × 10⁻⁶ and 17 iterations, and the classified Pourbaix CSVs assign a dominant species at every one of the 71 × 51 nodes (no missing/NaN labels), so the topology below rests on converged samples.
- **Cu topology.** 9 dominant labels → 9 connected regions, 16 pairwise boundaries, 16 junctions (8 internal triple points + 8 sweep-limit doublets). No Cu label is disconnected.
- **Fe topology.** 9 dominant labels → 10 connected regions (Fe(III)–citrate dimer `[Fe2(Citr)2(OH)2]⁴⁻` appears as two separate small regions, `DmsReg_4` and `DmsReg_7`, straddling the Fe⁰/Fe₃O₄ line near pH 8–9), 18 boundaries, 17 junctions (9 internal + 8 sweep-limit).

## Analysis

### Constants actually used (from the LC2 reference table)
All β and log K values quoted below are the `log_beta` entries from `LC2/thermodynamic_reference_constants.md` (SRD-46 except where marked Atlas). Citrate protonation: log β(H₃Cit) = 12.90, log β(H₂Cit⁻) = 10.00, log β(HCit²⁻) = 5.65 (so pKa₃ ≈ 5.65, pKa₂ ≈ 4.35, pKa₁ ≈ 2.90); glycine: log β(H₂Gly⁺) = 11.90, log β(HGly) = 9.57 (pKa₂ ≈ 9.57, pKa₁ ≈ 2.33); ammonia: log β(NH₄⁺) = 9.26. Chloride is treated as a spectator base ligand (log β = 0).

Cu(II) hydrolysis/solids: log β[Cu(OH)⁺] = −7.90, [Cu(OH)₂(aq)] = −16.20, [Cu₃(OH)₄²⁺] = −22.50; CuO(s) dissolution log K = −7.65, Cu(OH)₂(s) = −8.68, ½Cu₂O(s) = +0.70 (Cu(I)). Cu-ligand: [Cu(NH₃)₄]²⁺ = 12.30, [Cu(NH₃)₃]²⁺ = 10.20, [Cu(Gly)₂] = 15.10, [Cu(Gly)]⁺ = 8.19, [Cu(Cl)]⁺ = 0.12 (Cu(II)); [Cu(Cl)₂]⁻ = 6.06, [Cu(Cl)₃]²⁻ = 5.39, [Cu(NH₃)₂]⁺ = 9.92 (Cu(I)); citrate dimers [Cu₂(Cit)₂]²⁻ = 14.50, [Cu₂(Cit)₂(OH)]³⁻ = 11.20, [Cu₂(Cit)₂(OH)₂]⁴⁻ = 6.34, [Cu₂(Cit)(OH)] = 4.86.

Fe(III) hydrolysis/solids: log β[Fe(OH)²⁺] = −2.73, [Fe(OH)₂⁺] = −6.10, [Fe(OH)₄⁻] = −21.60, [Fe₂(OH)₂⁴⁺] = −2.86, [Fe₃(OH)₄⁵⁺] = −6.30; ½α-Fe₂O₃(s) dissolution log K = +0.70; Fe₃O₄(s) log K = −7.1252 (Atlas); FeO₄²⁻ log β = 0 (Atlas, i.e. reference for the Fe(VI) couple). Fe-ligand: [Fe(Cit)] = 11.19, [Fe(Cit)H]⁺ = 12.35, [Fe(Cit)(OH)]⁻ = 8.49, [Fe₂(Cit)₂(OH)₂]²⁻ = 21.20 (Fe(III)); [Fe(Cit)]⁻ = 4.40, [Fe₂(Cit)₂(OH)₂]⁴⁻ = −5.40 (Fe(II)); Fe(III) chloride weak ([Fe(Cl)₂]⁺ = 2.13, [Fe(Cl)]²⁺ = 0.78); Fe(III) ammine is very weak (all included [Fe(NH₃)ₙ]³⁺ have log β ≤ 2.75, i.e. protonation of NH₃ wins throughout).

## Analysis

### Copper landscape (9 dominant regions, 16 boundaries, 8 internal junctions)
Copper partitions among one metal (Cu), two oxides ([(Cu2O)0.5](s), CuO(s)), and six aqueous complexes with each of the four ligand systems represented:

- **Reduced pot (E ≲ 0 V, all pH):** Cu(0) metal (DmsReg_1, 14.0 sq-units — the single largest region). Below ~+0.075 V at low pH and below ~-0.1 V at high pH, Cu(I)/Cu(II) are reduced all the way to metal. Cu(I)-chloride and Cu(I)-ammine complexes could stabilize the +1 state, but only a razor-thin Cu(I)-ammine band ([Cu(Ammo)2]+, DmsReg_4, only 0.31 sq-units) survives between pH 7.9 and 10.7 at E ≈ -0.1 to 0 V, wedged between Cu(0) and (Cu2O)0.5(s)/CuO(s). No Cu(I)-chloride window is dominant — the log β1=+3.1, β2=+6.06, β3=+5.39 chloro-cuprates are outrun by direct reduction to Cu at these totals ([Cl⁻]=0.1 M is not enough to keep Cu(I) aqueous).
- **Oxidized, acidic (pH ≲ 3.3, E ≳ +0.375 V):** free Cu²⁺ (DmsReg_9, 3.91 sq-units). Hydrolysis constants are too small (log β(CuOH⁺)=-7.9) to compete here, and none of the chloride, glycine, ammonia or citrate complexes wins at low pH under 1 mM Cu total.
- **Oxidized, mildly acidic (pH ≈ 0–5.7, E ≈ +0.075 to +0.375 V):** [Cu(Chlo)2]⁻ (DmsReg_7, 1.36 sq-units). At [Cl⁻]=0.1 M and pH low enough to keep OH-competitors small, the log β=+6.06 dichlorocuprate(I? — this label carries the Cu$+1 basis in the card, so it is the reduced chloro-complex stabilized in this thin oxidative band adjacent to Cu metal) dominates.
- **Circumneutral, oxidized (pH ≈ 4.1–7.5, E ≳ +0.075 V):** citrate takes over via the dimeric hydroxo-citrate complexes. [Cu₂(Citr)₂(OH)]³⁻ (DmsReg_8, log β=+11.2) occupies a narrow strip 3.3<pH<4.1, and above pH 4.1 it hands off to [Cu₂(Citr)₂(OH)₂]⁴⁻ (DmsReg_5, log β=+6.34) which spans pH 4.1–7.5 up to E=+1.5 V (4.8 sq-units). The OH−/OH− ratio between the two dimers fixes the vertical boundary at pH 4.1 (DmsRegEq_13); the ligand-swap boundary to Cu(Chlo)₂⁻ (DmsRegEq_12) and Cu²⁺ (DmsRegEq_16) is set by [Cu²⁺]·[HxCit]·[OH] mass action, i.e. ligand/pH-controlled, not redox.
- **Neutral, oxidized (pH ≈ 7.5–10.7):** glycine displaces citrate. [Cu(Glyc)2] (DmsReg_6, log β=+15.1) dominates 7.5<pH<10.7 across E ≈ 0 to +1.5 V (4.82 sq-units). The pH-7.5 boundary is set by deprotonation of glycine into its zwitterion / anion form (pKa₂=9.57 from the card, effective log K for [Cu(Glyc)2] formation from free Cu²⁺ + 2·HGly then dominates once glycine is deprotonated enough); the pH-10.7 boundary is set by hydroxide taking over.
- **Alkaline, oxidized (pH ≳ 10.9):** solid CuO(s) (DmsReg_3, log Ks = -7.65 from Cu²⁺ + 2 H⁺; 5.42 sq-units). Underneath it at slightly lower E sits Cu₂O (Cu(I) oxide, DmsReg_2, log Ks = +0.7; 0.63 sq-units) as a thin band separating CuO(s) from Cu metal — this is the classical Cu / Cu₂O / CuO Pourbaix staircase, redox-controlled on the Cu | Cu₂O and Cu₂O | CuO faces (horizontal-ish curves near E = -0.3 to +0.025 V) and pH-controlled on the vertical CuO | [Cu(Glyc)2] boundary at pH 10.7–10.9.

Key triple points (junctions): (pH 5.7, +0.075 V) Cu | Cu₂Cit₂(OH)₂⁴⁻ | CuCl₂⁻; (pH 7.5, +0.025 V) Cu | Cu₂Cit₂(OH)₂⁴⁻ | Cu(Gly)₂; (pH 7.9, +0.025 V) Cu | Cu(NH₃)₂⁺ | Cu(Gly)₂; (pH 10.7, +0.025 V) Cu₂O | Cu(NH₃)₂⁺ | Cu(Gly)₂; (pH 10.9, +0.025 V) Cu₂O | CuO | Cu(Gly)₂. These five points thread the ligand-competition seam that runs across the diagram just above the Cu/Cu(I) redox line.
### Iron landscape (10 regions, 18 boundaries, 9 internal triple points; Dms 1–9 in Fe verdict)

Fe forms a much larger predominance map spanning three oxidation states (0, +II, +III, +VI).

- **Fe(s) (DmsReg_1, area 5.63):** The reducing floor across essentially the full pH range, entered by the Fe/Fe²⁺ couple near E ≈ −0.55 V at low pH (DmsRegEq_5) sloping to E ≈ −0.9 V at pH 14. `Fe$+0` uses log_beta = 0 as reference.
- **Fe²⁺ (DmsReg_5, area 4.68):** Free aquo Fe(II) dominates the acidic mid-potential window (pH 0–4, roughly E = −0.52 to +0.28 V). Bounded above by Fe(III) hydrolysis to hematite (DmsRegEq_14) and to Fe³⁺ (DmsRegEq_15 at E = 0.775 V), and to the right by Fe(II)-citrate.
- **[Fe(Citr)]⁻ (DmsReg_6, area 1.97):** Fe(II)-citrate wedge from pH ≈ 4.1–7.7 in the mid-potential band. Enabled by log_beta([Fe$+2][L1]) = +4.40 for [Fe(Citr)]⁻ combined with citrate's low pKa₁ = 12.9/pKa₂ = 10.0/pKa₃ = 5.65 (SRD-46), which deprotonates citrate above pH ≈ 5.7 into the pocket where the Fe(III)-hematite driving force is still modest.
- **[Fe₂(Citr)₂(OH)₂]⁴⁻ (DmsReg_4 + DmsReg_7, disconnected, total ≈ 0.12):** Two thin slivers of the mixed Fe(II)-citrate-hydroxo dimer (log_beta = −5.4) between the metal, magnetite, and monomeric citrate regions near pH 7.7–9.1, E ≈ −0.58 V.
- **Fe₃O₄ (magnetite, DmsReg_3, area 2.05):** A stable alkaline reducing region above pH ≈ 9 spanning E ≈ −0.87 → −0.18 V, with log_beta = −7.13 (Atlas). It links Fe(s), [Fe(OH)₃]⁻, [Fe(Citr)]⁻, hematite, and Fe(II)-citrate.
- **[Fe(OH)₃]⁻ (DmsReg_2, area 0.04):** Tiny corner at pH 14, E ≈ −0.9 V, from log_beta = −29 (Fe(II) tetrahydroxo).
- **α-Fe₂O₃/½ hematite (DmsReg_8, area 13.16 — the single largest region):** Dominates virtually the entire oxidizing half of the diagram above pH ≈ 1 up to the ferrate boundary. Governed by [Fe$+3][H]⁻³ dissolution constant log_beta = +0.70. The Fe²⁺/hematite boundary (DmsRegEq_14, from (4.1, +0.275) to (1.1, +0.775)) has the characteristic −0.177 V·pH⁻¹ slope of a 2e⁻/6H⁺ half-reaction.
- **Fe³⁺ (DmsReg_10, area 0.90):** A small acidic-oxidizing corner (pH < 1.1, E > 0.775 V) — hematite dissolves back to Fe³⁺ only at very low pH because Fe(III) hydrolysis (pKa of Fe(OH)²⁺ = 2.73) is very strong.
- **FeO₄²⁻ (DmsReg_9, area 7.66):** The high-E oxidant lid above E ≈ +0.33 V at pH 14 up to +1.5 V at pH ≈ 2 (DmsRegEq_17).

Redox-controlled boundaries: Fe/Fe²⁺, Fe/magnetite, Fe²⁺/Fe³⁺ (horizontal at 0.775 V, matching the pH-independent Fe³⁺/Fe²⁺ couple), Fe²⁺/hematite, hematite/ferrate, and hematite/Fe³⁺. Ligand-/pH-controlled: Fe²⁺/[Fe(Citr)]⁻ (vertical at pH 4.1), [Fe(Citr)]⁻/hematite (steeper hydrolysis+redox), and the citrate-hydroxo dimer slivers. **Neither Fe(II) nor Fe(III) glycinate, ammine, chloride, or simple hydroxide complexes ever become dominant** — citrate outcompetes every other ligand for Fe wherever a soluble complex can form, and hematite/magnetite outcompete all soluble Fe(III) species outside pH < 1.

### Cross-metal partitioning summary

- **Citrate** is captured by Fe(III) (log_beta = +11.19 for [Fe(Citr)]) far more strongly than by Cu(II) (log_beta = +14.5 for the Cu₂(Citr)₂ dimer but per Cu only +7.25). Yet Cu(II)-citrate hydroxo dimers still dominate a large Cu region (pH 4–7.5) because Fe(III) is largely locked in hematite there, freeing citrate. Wherever hematite forms, citrate is released and Cu picks it up.
- **Ammonia** (0.1 M, 10× citrate) forms Cu(II) ammines with high log_beta ([Cu(NH₃)₄]²⁺ = +12.3) but never wins a region — the citrate/glycine/hydroxide competition beats it except in a razor-thin [Cu(NH₃)₂]⁺ Cu(I) sliver (0.31 grid units) between metallic Cu, Cu₂O, and Cu(Glyc)₂ near pH 8–10.7, E ≈ 0 V. For Fe, ammonia is entirely absent from the dominant map (Fe-ammine log_beta ≤ +2.75 is far too weak against citrate and hydrolysis).
- **Glycine** dominates only the Cu(II) mid-alkaline region ([Cu(Glyc)₂], pH ≈ 7.5–10.7, log_beta = +15.1) — chelate effect and neutral charge make it the best ligand once citrate is quenched by protonation of the terminal OH. It never dominates any Fe region (Fe(II)-Gly log_beta ≤ +8.87, Fe(III)-Gly is even weaker except for protonated forms that require very low pH where hematite already forms).
- **Chloride** (0.1 M) wins only the Cu(I) [Cu(Chlo)₂]⁻ acid region and never appears in any Fe region — Fe-chloride log_beta values (≤ +2.13) cannot compete with citrate or with hematite formation.
- **Hydroxide/oxide solids** carry the bulk of both metals in the alkaline oxidizing quadrant: CuO(s) above pH ≈ 10.9 for Cu, and α-Fe₂O₃ above pH ≈ 1–5 for Fe. Cu²⁺(aq) barely exists (pH < 3.3, E > 0.375 V); Fe³⁺(aq) barely exists (pH < 1.1, E > 0.775 V). Both metals are almost entirely sequestered — Cu into citrate/glycine complexes plus oxide, and Fe into hematite plus citrate — with essentially no free divalent aquo species anywhere ligands are deprotonated.

### Convergence

The classified grid is 71 pH × 51 E = 3621 cells at ΔpH = 0.2, ΔE = 0.05 V. The full speciation CSV header reports `n_coarse_unrefined = 3621`, `n_coarse_excluded = 0`, meaning every cell converged and none were dropped. Boundary coordinates in the verdict are quoted from this fully classified label grid; the compact polylines are geometric summaries only.

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
