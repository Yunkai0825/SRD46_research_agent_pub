## Doability
Doable — well-posed pH speciation for Fe(III)/Ca(II)/Mg(II) + EDTA at fixed I, no redox; all constants and Fe(III) oxide/hydroxide phases present in the SRD-46 card.

## Result
- System: 1 mM Fe(III) + 1 mM Ca(II) + 1 mM Mg(II) + 5 mM EDTA, 25 °C, fixed I = 0.1 M, redox excluded.
- Method: `pH_sweep`, 41 points over pH 6.0–10.0.
- Convergence: 41/41 across the window (all metal and ligand blocks report 41/41). Calculated I actually spanned 0.013–0.026 M in the fixed-I mode — the numeric solve uses the target 0.1 M consistently, but note the compiled ion inventory is below that.
- Precipitation flag: hematite proxy `[(Fe2O3)0.5(s,alpha)]` becomes stable from pH 6.90 onward (1.55e-4 M at 6.9); no Ca(OH)2, Mg(OH)2, FeO(OH), or Fe(OH)3 solid ever appears (all zero in the concentration table).

## Analysis

### Ca(II): fully complexed, non-competitive
The fraction table shows [Ca(EDTA)]2- ≥ 0.998 across the whole pH 6–10 window, with free Ca2+ only 1.6e-3 at pH 6 and dropping to 1.1e-6 at pH 10. At pH 7, 8, 9 the [Ca(EDTA)]2- fractions are 0.99984, 0.99999, 0.99999; the mixed protonated [Ca(EDTA)H]- contributes ≤5e-5 above pH 7 and no Ca(OH)2 ever precipitates. Ca is essentially quantitatively sequestered by EDTA — the log β = 10.65 for [Ca(EDTA)]2- combined with excess ligand overwhelms the trivial hydrolysis of Ca(II) (log β for [Ca(OH)]+ = –13.04).

### Mg(II): also fully complexed
[Mg(EDTA)]2- dominates throughout (0.893 at pH 6, ≥ 0.992 by pH 7, 0.9996 by pH 9). At pH 7/8/9 the bound fractions are 0.9917, 0.9993, 0.99996. Free Mg2+ falls from 0.103 at pH 6 to 3.7e-4 at pH 7 and 3.7e-6 at pH 9. Even though [Mg(EDTA)]2- (log β = 8.79) is ~100× weaker than the Ca analogue, 5 mM ligand vs 3 mM total metal keeps Mg saturated with EDTA once pH ≥ 6.5. No brucite forms.

### Fe(III): quantitatively pulled out of solution as an oxide above pH 7
The verdict names the dominance change: [Fe(EDTA)]- rules from pH 6.0 to ≈ 7.0 (peak 90.2 % at pH 6), then the hematite proxy `[(Fe2O3)0.5(s,alpha)]` takes over from pH 7.0 to 10.0 (100 % at pH 10). The crossover cluster near pH 6.97–7.00 puts three species at ~33 % each: [Fe(EDTA)]-, [Fe(EDTA)(OH)]2-, and the solid. Reading the concentration table:

| pH | [Fe(EDTA)]- | [Fe(EDTA)(OH)]2- | Σ EDTA-Fe | (Fe2O3)0.5(s) | free/hydroxo aqueous |
|----|-------------|------------------|-----------|---------------|---------------------|
| 7.0 | 0.313 | 0.341 | 0.654 | 0.346 | <1e-10 |
| 8.0 | 3.89e-3 | 4.24e-2 | 0.046 | 0.954 | <1e-11 |
| 9.0 | 2.83e-5 | 3.09e-3 | 3.12e-3 | 0.997 | <1e-12 |

Free Fe3+ and all aqueous hydroxo Fe(III) species (Fe(OH)2+, Fe(OH)2+, Fe(OH)4-, dimer, trimer) never rise above ~1e-10 fractional — the aqueous ladder is essentially empty; whatever isn't in an EDTA complex is in the oxide. Dominant EDTA form is [Fe(EDTA)]- below pH 7 and the hydroxo-EDTA ternary [Fe(EDTA)(OH)]2- above (peak 40.8 % at pH 6.8), consistent with log β = 25.10 for [Fe(EDTA)]- and 17.71 for [Fe(EDTA)(OH)]2- — the ternary wins at high pH because it consumes an OH-.

Even with log β = 25.10 the hematite-type Fe(III) oxide (dissolution log K = +0.70, i.e. very insoluble at circumneutral pH) is thermodynamically preferred once pH ≥ 7. Excess EDTA holds only ~65 % of Fe(III) at pH 7 and drops below 5 % by pH 8. FeO(OH) and Fe(OH)3(s) never precipitate in this card because the more stable Fe2O3 proxy is the thermodynamic sink.

### Selectivity verdict
EDTA does NOT selectively hold Fe(III) in solution across pH 7–9. It does the opposite of what a water-treatment iron-control application usually wants: at pH 7 roughly one-third of Fe(III) has already dropped out as an iron oxide, and by pH 8–9 essentially all Fe(III) is on the solid while Ca(II) and Mg(II) are ≥99.9 % locked up as soluble EDTA complexes. So EDTA is highly selective, but backwards for this purpose: it preferentially chelates the hardness cations and effectively wastes on Ca/Mg while Fe(III) precipitates as (hydr)oxide. To keep Fe(III) soluble above pH 7 one would need either much higher EDTA:M ratios, a stronger Fe(III)-selective chelator (e.g., DTPA, siderophore-type), or acidic operation (pH ≤ 6.5 keeps [Fe(EDTA)]- ≥ 90 %). The ionic-strength note (compiled I ≈ 0.013–0.026 M vs. target 0.1 M) does not alter the qualitative selectivity conclusion.

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
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_concentrations.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_concentrations.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_Ca$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_Ca$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_Fe$+3.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_Fe$+3.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_L1.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_L1.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_Mg$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_envelope_Mg$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_Fe.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_Fe.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_L1.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_L1.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_ligand.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_ligand.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_metal.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_metal.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_Mg.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_frac_Mg.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_log_conc.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_log_conc.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_log_conc.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_log_conc.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Fe.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Fe.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Mg.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Mg.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_run_params.json](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_run_params.json>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_state_metrics.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_state_metrics.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_verdict.md](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_verdict.md>)
- [solver/topology_Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_Ca.json](<solver/topology_Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_EDTA_Ca.json>)
- [verdict.json](<verdict.json>)
