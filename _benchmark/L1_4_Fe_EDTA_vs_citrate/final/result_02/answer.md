## Doability
Doable. Fe(III) + citric acid with Fe(OH)3(s) as a permitted solid is a canonical SRD-46 pH-speciation problem, and every needed constant (Fe hydrolysis, Fe–citrate mono/dinuclear complexes, Fe(OH)3(s) dissolution) is present in the reference table.

## Result
- System: Fe(III)_tot = 1.00 mM, citrate_tot = 5.00 mM, T = 25 °C, target I = 0.1 M (fixed), Fe(OH)3(s) allowed to precipitate.
- Method: pH_sweep, 51 points over pH 4.0–9.0.
- Convergence: 51/51 successful. Calculated I stayed in 6.7e-3 – 2.2e-2 M (below the 0.1 M target because no inert electrolyte was declared; activity corrections still use I = 0.1 M as set).
- Precipitation onset reported by the solver: pH 6.10, with 2.99e-4 M Fe(OH)3(s) already present at that sample.

## Analysis
**Below pH ~6.1 — citrate holds all Fe(III) in solution.** From pH 4.0 up to 6.0, no Fe(OH)3(s) is present and essentially 100 % of the Fe(III) is complexed by citrate. The dominant species is the dinuclear μ-hydroxo dicitrate complex **[Fe2(Citr)2(OH)2]2−**, which carries 87.0–87.3 % of Fe over pH 4.0–6.0 (frac_metal.csv), accompanied by the mononuclear **[Fe(Citr)(OH)]−** at 12.6–12.7 %. Minor contributions from [Fe(Citr)] (≤0.4 %) and [Fe(Citr)H]+ (≤6e-4 %) fall off as pH rises. Free Fe3+ and simple hydrolysis products ([Fe(OH)]2+, [Fe(OH)2]+, [Fe3(OH)4]5+) are all ≤2e-7 fraction — citrate outcompetes hydrolysis by many orders of magnitude because the cumulative log β values for Fe–citrate species (log β = +11.2 for [Fe(Citr)], +8.5 for [Fe(Citr)(OH)]−, +21.2 for the dinuclear) far exceed those of the corresponding Fe(III) hydrolysis products (log β = −2.7, −6.1, −6.3, −21.6 in the reference table). The dinuclear species dominates over the mononuclear because citrate is in 5-fold excess and its own protonation constants (pKa3-like row at log β +5.65, cumulative +10.0 and +12.9) mean citrate is largely present as HCitr2−/Citr3− above pH 5, favouring the polynuclear μ-OH bridged assembly.

**pH 6.10 — Fe(OH)3(s) reappears.** This is the pH at which the Fe(III)–citrate solution becomes supersaturated with respect to ferrihydrite. At pH 6.1 the solid already holds 29.9 % of total Fe (2.99e-4 M), the dinuclear drops to 59.6 %, and [Fe(Citr)(OH)]− to 10.5 %. Precipitation is triggered because rising pH deprotonates coordinated OH and dissociates the μ-OH dimer while simultaneously lowering [Fe3+] × [OH−]3 far enough above K_s0 (log K for [Fe3+] + 3 OH− ⇌ Fe(OH)3(s), reported as log β = −3.20 in the dissolution direction) that even citrate complexation cannot keep Fe soluble.

**Crossover pH values (verdict):** [Fe(Citr)(OH)]− ↔ Fe(OH)3(s) at pH ≈ 6.04 (~12 % each); [Fe2(Citr)2(OH)2]2− ↔ Fe(OH)3(s) at pH ≈ 6.15 (~45 % each). Between these, the citrate complexes and the solid trade the metal.

**Above pH 6.5 — Fe(OH)3(s) is overwhelmingly dominant.** Solid fraction climbs to 91.6 % at pH 6.4, 95.8 % at pH 6.5, 99.3 % at pH 6.8, and ≥99.9 % from pH 7.5 onward. The soluble Fe carried as [Fe2(Citr)2(OH)2]2− falls from 28.5 % (pH 6.2) to 2.2 % (pH 6.5), 0.14 % (pH 7.0), and 5.9e-5 (pH 7.6); [Fe(Citr)(OH)]− decays from 7.3 % (pH 6.2) to 0.13 % (pH 7.1). No Fe(III)–citrate window reopens between pH 6.1 and 9.0 — once ferrihydrite forms, it grows monotonically. The anionic hydrolysis product [Fe(OH)4]− stays in the 1e-8 range and never becomes significant below pH 9.

**Citrate speciation** (frac_ligand summary from the verdict): HCitr2− dominates pH 4.0–5.1 (peak 50.7 % at pH 4.5) and Citr3− above pH 5.1 (peak 100 % at pH 9.0). Only 17.5 % of total citrate at most (at pH 6.0) is tied up as [Fe2(Citr)2(OH)2]2− because citrate is in 5× stoichiometric excess over Fe.

**Practical take-away.** With a 5:1 citrate:Fe(III) ratio, ferric iron is kept fully soluble as a dinuclear μ-hydroxo dicitrate up to pH 6.0. Precipitation of ferrihydrite sets in sharply at pH 6.1 and is essentially complete (>99 %) by pH 6.8. The window where citrate keeps Fe in solution at circumneutral pH is therefore quite narrow — the classic reason 5–10× citrate is not enough to buffer Fe(III) solubility at physiological pH, and why stronger chelators (EDTA, siderophores) are needed above pH 7.

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
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_concentrations.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_concentrations.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_Fe$+3.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_Fe$+3.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_L1.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_L1.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_Fe.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_Fe.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_L1.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_L1.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_ligand.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_ligand.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_metal.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_metal.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_phase_balance_Fe.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_phase_balance_Fe.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_run_params.json](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_run_params.json>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_state_metrics.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_state_metrics.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_verdict.md](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_verdict.md>)
- [solver/topology_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_Fe.json](<solver/topology_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_Fe.json>)
- [verdict.json](<verdict.json>)
