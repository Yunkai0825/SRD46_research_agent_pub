## Doability
Doable — Cu(II)/glycine speciation over pH 0–14 at I=0.1 M, 25 °C is a standard 1-D pH_sweep and both components exist in the SRD-46 catalog.

## Result
System: Cu(II) 1.00 mM + glycine 10.0 mM (10:1 L:M), aqueous, 25.0 °C, I = 0.1 M (fixed), redox excluded so only the Cu(II) manifold is active (Cu+, Cu(s) totals set to 0). Method: `pH_sweep`, 141 grid points across pH 0.0–14.0. Convergence: 141/141 for all components; calculated I ranged 1.4e-5 – 7.0e-3 M. Species considered included free Cu2+, mono/dihydroxo and polynuclear hydrolysis products ([Cu(OH)]+, [Cu2(OH)2]2+, [Cu(OH)2]aq, [Cu3(OH)4]2+, HCuO2-, CuO22-), the glycinate complexes [Cu(Glyc)]+ and [Cu(Glyc)2], and the solids CuO(s) and Cu(OH)2(s).

## Analysis
**Dominant Cu(II) species by pH region (grid-bracketed crossovers):**
- pH 0.0 – 3.7 → free **Cu2+** (100% at pH 0)
- pH 3.7 – 4.8 → **[Cu(Glyc)]+** (peak 63.0% at pH 4.2)
- pH 4.8 – 10.8 → **[Cu(Glyc)2]** (neutral bis-glycinate; peak 100% at pH 10.2)
- pH 10.8 – 14.0 → **CuO(s)** (99.9% at pH 12.4)

Crossovers: Cu2+ ↔ [Cu(Glyc)]+ at pH ≈ 3.64; [Cu(Glyc)]+ ↔ [Cu(Glyc)2] at pH ≈ 4.73; [Cu(Glyc)2] ↔ CuO(s) at pH ≈ 10.75. Precipitation of CuO(s) is first detected at pH 10.60 (1.73e-4 M).

**Dominant Cu species at pH 7 → [Cu(Glyc)2] (neutral bis-glycinate complex).** pH 7 lies squarely in the 4.8–10.8 dominance window of this species, which reaches ~100% of total Cu around pH 10. No hydrolysis products or solids compete in this window.

**Chemical interpretation.** The behaviour is set by the interplay of glycine's acid–base ladder (from the reference constants: log β for H+glycinate = 9.57, i.e. NH3+CH2COO- ⇌ NH2CH2COO- pKa ≈ 9.57; and log β for the diprotonated cation = 11.90, giving carboxyl pKa ≈ 11.90 − 9.57 ≈ 2.33) and Cu2+ hydrolysis. Below pH ~2 glycine is mostly the cationic H2Gly+ form and is not an effective ligand, so Cu2+ dominates. Between pH ~2.4 and 9.4 the zwitterion HGly (dominant glycine form) supplies an available carboxylate/α-amino donor pair; the reported log β for Cu2+ + Gly- ⇌ [Cu(Glyc)]+ is 8.19 and for Cu2+ + 2 Gly- ⇌ [Cu(Glyc)2] is 15.10, so the stepwise constant for adding the second glycinate is log K2 ≈ 15.10 − 8.19 = 6.91. With 10-fold excess ligand this makes the neutral bis-chelate the overwhelmingly favoured form once free glycinate becomes appreciable — hence the very narrow window (pH 3.7–4.8) in which the mono-complex is the majority species: it appears as soon as HGly is available and is immediately outcompeted by the far more stable N,O-chelated bis-glycinate. The huge combined stability (log β2 = 15.10) also *suppresses Cu(II) hydrolysis entirely* in the neutral-to-basic region: no [Cu(OH)]+, [Cu2(OH)2]2+ or [Cu3(OH)4]2+ ever becomes dominant, which is why bare Cu(OH)2(s) does not precipitate below pH 10.8 either. Only when OH- concentration is high enough to strip glycinate from copper (pH > 10.75) does tenorite CuO(s) take over.

**Practical implications.** (i) At physiological / near-neutral pH (5–10) essentially all Cu(II) in a 10:1 glycine solution is sequestered as the soluble neutral bis-glycinate — glycine acts as a strong solubilising/masking ligand for Cu(II). (ii) Cu(II) will not precipitate as hydroxide in this window, so glycine-buffered Cu(II) reagents are stable to base up to pH ≈ 10.7. (iii) Speciation between pH 3.7 and 4.8 transitions rapidly through the +1 mono-complex, relevant when interpreting charge/mobility (e.g. electrophoresis, ion-exchange loading).

Caveats (per method briefing): redox is frozen (no Cu(0)/Cu(I) chemistry considered); constants and totals hold only at I = 0.1 M and 25 °C; crossover pH values are quoted from the solver's grid-bracketed dominance table, not from analytical inversion.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_Cu.json>)
- [verdict.json](<verdict.json>)
