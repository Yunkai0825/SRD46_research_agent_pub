## Doability
Doable. Both metals, citrate, and chloride are in the SRD-46 catalog, and a joint E-pH sweep (pH 2-10, E_V -0.5 to +1.2 V vs SHE) is exactly the pourbaix_sweep route.

## Result
- System: 1 mM Cu(II) + 1 mM Fe(III) + 5 mM citrate + 0.1 M Cl-, 25 C, I = 0.1 m.
- Method: `pourbaix_sweep`, pH 2-10 x E_V [-0.5, +1.2] V (SHE); final classified grid dpH = 0.2, dE = 0.05 V; 1435 coarse cells with 0 excluded and 0 refined-only; verdict topology stats report no disconnected labels and no parser failures. Two per-element verdicts (Cu, Fe) were produced.
- Cu verdict: 6 dominant-species labels / 6 connected regions / 9 boundary curves.
- Fe verdict: 5 dominant-species labels / 5 connected regions / 6 boundary curves.

## Analysis

### Feature roster used
**Cu regions** (from `topology_..._Cu_verdict.md`):
- DmsReg_3 {[Cu(Chlo)2]-}: low-pH oxidised field, corners at DmsRegEqJnc_7 (pH 2, E 0.075 V), _6 (pH 5.9, 0.075 V), _1 (pH 4.1, 0.275 V), _2 (pH 3.3, 0.375 V), _3 (pH 2, 0.375 V).
- DmsReg_6 {Cu2+}: small acidic-oxidised wedge, corners DmsRegEqJnc_3 (pH 2, 0.375 V), _2 (pH 3.3, 0.375 V), _5 (pH 3.3, 1.2 V, sweep limit).
- DmsReg_5 {[Cu2(Citr)2(OH)]3-}: narrow slab, corners _1 (4.1, 0.275), _2 (3.3, 0.375), _4 (4.1, 1.2), _5 (3.3, 1.2).
- DmsReg_4 {[Cu2(Citr)2(OH)2]4-}: largest region (measure 6.71); dominant oxidised field for pH >~4.1, corners _1, _4, _6, _9 (7.3, 0.075), _8 (10, 0.075).
- DmsReg_1 {Cu(s)}: reduced field below E ~0.075 V, corners _7, _6, _9, _10 (10, -0.125).
- DmsReg_2 {[(Cu2O)0.5](s), cuprite}: small alkaline reduced wedge, corners _9, _10, _8.
**Fe regions** (from `topology_..._Fe_verdict.md`):
- DmsReg_2 {Fe2+}: acidic reduced field left of pH ~4.5, bounded by DmsRegEqJnc_1 (pH 4.5, -0.5 V, sweep limit), _5 (pH 4.5, 0.275 V), _2 (pH 2, 0.675 V).
- DmsReg_3 {[Fe(Citr)]-}: reduced-plus-citrate field for pH ~4.5-7.8 at low E, corners _1, _5, _3 (pH 7.7, -0.5 V), _4 (pH 7.9, -0.325 V).
- DmsReg_4 {[Fe2(Citr)2(OH)2]4- (Fe(II) dimer)}: thin alkaline reduced sliver between _3, _4, _6 (pH 9.5, -0.5 V); solver measure only 0.24.
- DmsReg_5 {[Fe2(Citr)2(OH)2]2- (Fe(III) dimer)}: acidic oxidised citrate dimer, corners _5, _2, _7 (pH 4.3, 1.2 V).
- DmsReg_1 {[FeO(OH)(s,alpha)] = goethite/alpha-FeOOH}: dominant oxidised field for pH >~4.5, corners _5, _4, _6, _7; largest solver measure (8.05).

### Cu partitioning across the map
- **Very acidic (pH 2-3.3), moderately oxidised (E > 0.075 V):** boundary DmsRegEq_3 places the Cu2+ / [Cu(Chlo)2]- interconversion at E ~ 0.375 V (compact vertices (pH 2, 0.375 V) - (pH 3.3, 0.375 V)). Above that potential Cu(II) as Cu2+ is dominant; below it, chloride simultaneously reduces and complexes Cu to the Cu(I) chloro-complex [Cu(Chlo)2]-. This is a genuine redox transition (Cu(II) -> Cu(I)) stabilised by chloride: card log beta = +6.06 for Cu+ + 2 Cl- -> [Cu(Chlo)2]-, plus +3.10 for [Cu(Chlo)] and +5.39 for [Cu(Chlo)3]2-. The corresponding Cu(II)-Cl complex is much weaker (log beta = +0.20 for [Cu(Chlo)]+), so at 0.1 M Cl- chloride never dominates the divalent field but strongly stabilises Cu(I), pulling the Cu(II)/Cu(I) couple well below the aqua-ion standard potential.### Cu partitioning across the map
- **Very acidic (pH 2-3.3), moderately oxidised (E > 0.075 V):** boundary DmsRegEq_3 places the Cu2+ / [Cu(Chlo)2]- interconversion at E ~ 0.375 V (compact vertices (2, 0.375)-(3.3, 0.375)). Above that potential Cu2+ is dominant; below it, Cl- reduces and complexes Cu to Cu(I) chloro-complex [Cu(Chlo)2]-. This is a redox transition (Cu(II) -> Cu(I)) stabilised by chloride: card log beta = +6.06 for Cu+ + 2 Cl- -> [Cu(Chlo)2]-, plus +3.10 for [Cu(Chlo)] and +5.39 for [Cu(Chlo)3]2-, all Cu(I). The Cu(II)-Cl complex is much weaker (log beta = +0.20 for [Cu(Chlo)]+), so at 0.1 M Cl- chloride does not dominate the divalent field but heavily stabilises Cu(I) and pulls the Cu(II)/Cu(I) couple far below the aqua-ion E_0.
- **pH 3.3-5.9, oxidised (E ~ 0.075-0.375 V):** [Cu(Chlo)2]- persists at low potentials but for pH >~4.1 citrate dimers take over. DmsRegEq_2 gives [Cu(Chlo)2]- / [Cu2(Citr)2(OH)]3- from (3.3, 0.375) to (4.1, 0.275); DmsRegEq_1 gives [Cu(Chlo)2]- / [Cu2(Citr)2(OH)2]4- from (4.1, 0.275) to (5.9, 0.075). The pH-line at E=0.35 V shows the ladder [Cu(Chlo)2]- (pH 2-3.4) -> [Cu2(Citr)2(OH)]3- (3.6-4.0) -> [Cu2(Citr)2(OH)2]4- (>=4.2). Card values: log beta = +11.20 for [Cu2(Citr)2(OH)]3- and +6.34 for [Cu2(Citr)2(OH)2]4- (from Cu2+ + [H-1L1]). Mononuclear [Cu(Citr)H] (+9.26) and [Cu2(Citr)2]2- (+14.50) do not dominate: once citrate is fully deprotonated (stepwise pKa 5.65 for the third proton) the doubly-hydroxo dimer is cooperatively favoured.

- **pH 3.3-5.9, oxidised (E ~ 0.075-0.375 V):** [Cu(Chlo)2]- persists at low potentials, but for pH >~4.1 the citrate dimers take over. Boundary DmsRegEq_2 gives [Cu(Chlo)2]- / [Cu2(Citr)2(OH)]3- from (pH 3.3, E 0.375 V) to (4.1, 0.275); DmsRegEq_1 gives [Cu(Chlo)2]- / [Cu2(Citr)2(OH)2]4- from (4.1, 0.275) to (5.9, 0.075). The pH-line reference cut at fixed E = 0.35 V confirms the ladder: [Cu(Chlo)2]- (pH 2-3.4) -> [Cu2(Citr)2(OH)]3- (3.6-4.0) -> [Cu2(Citr)2(OH)2]4- (>=4.2). The Cu-citrate binuclear species are strong: card log beta = +11.20 for [Cu2(Citr)2(OH)]3- and +6.34 for [Cu2(Citr)2(OH)2]4- (both from Cu2+ + [H-1L]/L basis). The mononuclear [Cu(Citr)H] (log beta = +9.26) and [Cu2(Citr)2]2- (+14.50) never win the label because at 1 mM Cu / 5 mM citrate the deprotonated hydroxo-citrate dimers are cooperatively favoured once citrate is fully deprotonated (citrate stepwise pKa values from the table: 5.65, 4.35, 2.90; so [L]3- exceeds 50% above pH ~5.7).

- **pH >~4.1 at E > ~0.1 V (essentially the neutral/alkaline oxidised half):** [Cu2(Citr)2(OH)2]4- fills the map (region measure 6.71, the largest Cu field). It contacts metallic Cu on DmsRegEq_7 (pH 5.9-7.3, E 0.075 V) and cuprite [(Cu2O)0.5](s) on DmsRegEq_8 (pH 7.3-10, E 0.075 V). Citrate keeps Cu(II) fully dissolved through the entire neutral-alkaline range where, without citrate, tenorite CuO(s) (card log beta = -7.65) or Cu(OH)2(s) (-8.68) would precipitate. Both solids appear in the calculation species list but never as dominant labels - citrate has out-competed hydrolysis and precipitation.

- **pH >~4.1 at E > ~0.1 V (essentially the whole neutral/alkaline oxidised half):** [Cu2(Citr)2(OH)2]4- fills the map. It touches metallic Cu on DmsRegEq_7 (pH 5.9-7.3, E 0.075 V) and touches cuprite [(Cu2O)0.5](s) on DmsRegEq_8 (pH 7.3-10, E 0.075 V). So Cu-citrate keeps Cu(II) fully dissolved through the entire neutral-alkaline range where, in a citrate-free 1 mM Cu(II) solution, tenorite CuO(s) or Cu(OH)2(s) would precipitate (card log beta CuO(s) = -7.65, Cu(OH)2(s) = -8.68). Here they do not appear as dominant labels - citrate has out-competed both hydrolysis (Cu(OH)+ log beta = -7.90; Cu2(OH)2 = -11.20; Cu(OH)2 aq = -16.20) and precipitation.
- **Reduced half (E < ~0.075 V):** metallic Cu(s) is dominant across almost the whole pH range (Cu region measure 4.6). Only above pH ~7.3 does cuprite [(Cu2O)0.5](s) (card log beta = +0.70 for Cu+ + H- -> 0.5 Cu2O) intervene as an alkaline reduced solid before oxidation to the Cu-citrate dimer. Junction DmsRegEqJnc_9 (Cu | cuprite | Cu-citrate dimer) sits at pH 7.3, E 0.075 V - the practical corrosion/passivation point for Cu in this pot.

### Fe partitioning across the map
- **Acidic reduced (pH < 4.5, E < 0.275 V):** Fe2+ is dominant. The Fe2+ / [Fe(Citr)]- boundary (DmsRegEq_2) is vertical at pH 4.5 (from E = -0.5 V up to 0.275 V). This is a non-redox displacement: at pH >~4.5 enough [L]3- is present that [Fe(Citr)]- (card log beta = +4.40 from Fe2+ + [L]3-) overtakes free aqua Fe(II). The lower-pH protonated Fe(II)-citrate species [Fe(Citr)H2]+ (+11.10) and [Fe(Citr)H] (+8.55) never dominate: free ligand activity is too small below pH ~4 where citrate is largely H3L / H2L-.### Fe partitioning across the map
- **Acidic reduced (pH < 4.5, E < 0.275 V):** Fe2+ is dominant. The Fe2+ / [Fe(Citr)]- boundary (DmsRegEq_2) is vertical at pH 4.5 (from E = -0.5 V up to 0.275 V). This is a non-redox displacement: at pH >~4.5 enough [L]3- is present that [Fe(Citr)]- (card log beta = +4.40 from Fe2+ + [L]3-) overtakes free aqua Fe(II). Protonated Fe(II)-citrate forms - [Fe(Citr)H2]+ (+11.10) and [Fe(Citr)H] (+8.55) - are present as minors but never dominate: at 1 mM Fe / 5 mM citrate the free ligand activity at pH < 4 is too small (citrate is largely H3L and H2L-).
- **Neutral-alkaline reduced (pH 4.5-9.5, E < ~-0.3 V):** [Fe(Citr)]- fills the field. The Fe(II) dimer [Fe2(Citr)2(OH)2]4- (card log beta = -5.40) appears only as a small alkaline sliver (DmsReg_4, measure 0.24) between pH 7.7 and 9.5 at strongly reducing E, bounded by junctions _3, _4, _6. In practice Fe(II) is quantitatively held by citrate wherever it is thermodynamically reduced.
- **Acidic oxidised (pH 2-4.5, E > ~0.275 V):** [Fe2(Citr)2(OH)2]2- (Fe(III) citrate dimer, card log beta = +21.20) dominates. The boundary against Fe2+ (DmsRegEq_1) runs from (4.5, 0.275) to (2, 0.675) - a redox line whose potential rises to 0.675 V at pH 2 and falls to 0.275 V at pH 4.5, showing that citrate massively stabilises Fe(III) relative to Fe(II) (in absence of citrate, the aqua Fe3+/Fe2+ couple sits at +0.77 V). Mononuclear [Fe(Citr)] (+11.19), [Fe(Citr)H]+ (+12.35), and [Fe(Citr)(OH)]- (+8.49) exist as minors but the doubly deprotonated dimer wins mass balance.

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
- [solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.png](<solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.png>)
- [solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.png](<solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.png>)
- [solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.csv](<solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.csv>)
- [solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.csv](<solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.csv>)
- [solver/speciation_full_Cu_+_Fe_+_Citric_acid_+_Chloride_ion.csv](<solver/speciation_full_Cu_+_Fe_+_Citric_acid_+_Chloride_ion.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_0d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_1d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_metadata.json](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_regions.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_regions.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_0d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_1d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_metadata.json](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_regions.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_regions.csv>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.md](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.md>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.md](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.md>)
- [verdict.json](<verdict.json>)
