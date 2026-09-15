## Doability
Doable. SRD-46 supplies Ni(II) hydrolysis and Ni–citrate complexes plus Ni(OH)2(s); the pH_sweep method fits the request exactly.

## Result
System: 1.00 mM Ni(II) + 10.0 mM citric acid, aqueous, 25 °C, ionic strength held at 0.1 M, pH 4.0–11.0, 71 grid points. Redox is fixed (Ni(II) only). Ni(OH)2(s) is included. Convergence: 71/71. Precipitation event flagged at pH 9.20 (Ni(OH)2, 1.94×10⁻⁶ M).

Dominant Ni(II) species by region (from the verdict):
- pH 4.0–4.4 → [Ni(Citr)2H]³⁻ (mono-protonated bis-citrate)
- pH 4.4–9.4 → [Ni(Citr)2]⁴⁻ (fully deprotonated bis-citrate; peaks 96.8% at pH 7.6)
- pH 9.4–11.0 → Ni(OH)2(s)

Crossovers: [Ni(Citr)2H]³⁻ ↔ [Ni(Citr)2]⁴⁻ at pH ≈ 4.30; [Ni(Citr)2]⁴⁻ ↔ Ni(OH)2(s) at pH ≈ 9.36.

## Analysis
**Free [Ni²⁺] at pH 9.** From the concentrations table, at pH 9.0 free aquated Ni²⁺ = **4.03×10⁻⁷ M**, i.e. **0.040 %** (fraction 4.03×10⁻⁴) of the 1.00 mM total Ni. Citrate has driven the free-ion activity down by more than three orders of magnitude relative to a citrate-free 1 mM Ni²⁺ solution. Essentially all of the metal at pH 9 is in the bis-citrate chelate [Ni(Citr)2]⁴⁻ (≈82.9% of Ni_total, 8.29×10⁻⁴ M), with the dinuclear hydroxo-bridged [Ni2(Citr)2(OH)2]⁴⁻ picking up ~14% (7.24×10⁻⁵ M by Ni). All simple hydrolysis products ([Ni(OH)]⁺, [Ni(OH)2]⁰, [Ni(OH)3]⁻) sit at ≤2.5×10⁻⁸ M and are chemically irrelevant here.

**Does Ni(OH)2(s) precipitate?** At pH 9.0 the solver reports **no solid** (Ni(OH)2 column = 0). The first precipitation grid point is pH 9.20 with only 1.94×10⁻⁶ M Ni(OH)2(s) — less than 0.2% of the metal. The [Ni(Citr)2]⁴⁻ ↔ Ni(OH)2(s) predominance crossover is at pH ≈ 9.36 (bracketed between pH 9.3 and 9.4 in the grid, each ≈42%), and the solid becomes dominant only above pH 9.4. So at exactly pH 9, citrate at a 10:1 ligand:metal ratio **suppresses Ni(OH)2 scaling completely**; a modest excursion of ~0.2–0.4 pH units into the alkaline is enough to begin nucleating hydroxide, and by pH ≥ 9.5 most Ni is in the solid.

**Why the biography looks this way.** Citric acid is a triprotic α-hydroxy tricarboxylate whose cumulative protonation constants on the card (log β = 5.65, 10.00, 12.90 for H, H2, H3 forms) correspond to stepwise pKa values of roughly 5.65, 4.35, 2.90. Above pH ~5 the fully deprotonated citrate³⁻ (with the α-OH available as a fourth donor) dominates the free-ligand pool, and its bis-chelate with Ni²⁺ has a strong cumulative log β = 8.13 for [Ni(Citr)2]⁴⁻. That single number, combined with a 10-fold ligand excess, is what pushes free Ni²⁺ down to sub-µM across almost the entire near-neutral to mildly alkaline window. Below pH ~4.3 the second citrate begins to protonate on the metal (→ [Ni(Citr)2H]³⁻) as HCit²⁻/H2Cit⁻ take over the free-ligand ladder; above pH ~9.3 the driving force from Ni²⁺ + 2 OH⁻ → Ni(OH)2(s) (log Ksp corresponding to card μ°) finally beats the chelate, first via the hydroxo-bridged binuclear [Ni2(Citr)2(OH)2]⁴⁻ (peaks 26% at pH 9.2) and then via bulk hydroxide precipitation.

**Practical read for scale control.** Operating at pH 9 with a 10× citrate excess keeps ≥99.9% of Ni chelated and no Ni(OH)2 forms; the safety margin against scaling is only ~0.2 pH units, so pH creep toward 9.3–9.4 should be treated as the onset boundary and controlled. Adding more citrate would push the crossover further to the right; reducing the citrate:Ni ratio or lowering total citrate would collapse it back toward pH 9.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Citric_acid_Ni.json>)
- [verdict.json](<verdict.json>)
