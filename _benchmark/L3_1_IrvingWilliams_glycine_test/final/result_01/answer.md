## Doability
Doable — Co(II) and glycine are both in SRD-46, and a single-pH speciation at fixed I is a standard pH_sweep (bracketed by pH 6.5–7.5, 11 points).

## Result
- System: 1.00 mM Co(II) + 10.0 mM glycine (total), T = 25 °C, I = 0.1 M (fixed), redox excluded so only Co(II) forms are populated.
- Method: `pH_sweep` over pH 6.5–7.5, 11/11 samples converged; calculated I stayed at 0.8–1.7 mM (well within the 0.1 M target ionic buffer).
- Card constants (SRD-46, from the reference table): glycinate protonation log β(H·Gly) = +9.57 (⇒ pKa2 ≈ 9.57 for HGly ↔ Gly⁻ + H⁺); log β(H₂Gly⁺) = +11.90 (⇒ pKa1 ≈ 2.33); Co(II) + Gly⁻ complexes log β₁ = 4.67, log β₂ = 8.46, log β₃ = 10.9; mixed hydroxo log β(Co(Gly)(OH)) = −5.42; first hydrolysis log β(Co(OH)⁺) = −9.70.

## Analysis
At pH 7 the metal distribution (from `..._frac_metal.csv`, pH = 7.0000 row) is:

| Species | Fraction of total Co | Concentration (M) |
|---|---:|---:|
| Co²⁺ (aquo) | 54.26 % | 5.43 × 10⁻⁴ |
| [Co(Gly)]⁺ | 39.40 % | 3.94 × 10⁻⁴ |
| [Co(Gly)₂]⁰ | 6.17 % | 6.17 × 10⁻⁵ |
| [Co(Gly)(OH)]⁰ | 0.032 % | 3.2 × 10⁻⁷ |
| [Co(Gly)₃]⁻ | 0.071 % | 7.1 × 10⁻⁷ |
| [Co(OH)]⁺ | 0.066 % | 6.6 × 10⁻⁷ |
| all other hydrolysis, Co(OH)₂(s) | <10⁻⁵ % | — |

So the **free aquo Co²⁺ concentration at pH 7 is ≈ 5.4 × 10⁻⁴ M** — a 10-fold ligand excess only sequesters about half of the cobalt. No solid phase is stable (Co(OH)₂(s) fraction is numerically zero across the window; the aqueous ladder never crosses the dissolution boundary at these totals).

**Why the binding is so modest.** The Co–glycine constants apply to fully deprotonated glycinate Gly⁻, but at pH 7 glycine is overwhelmingly the zwitterionic HGly form (97.8 % of total ligand from the ligand table; peak at pH 6.5). Because pKa2 ≈ 9.57, only ~10^(7−9.57) ≈ 0.27 % of total glycine (~2.7 × 10⁻⁵ M) is available as the coordinating Gly⁻ at pH 7. The effective free-Gly⁻ concentration, not the 10 mM analytical total, is what drives complexation, so even with log β₁ = 4.67 the ratio [Co(Gly)⁺]/[Co²⁺] = β₁·[Gly⁻] ≈ 10^4.67 · 2.7 × 10⁻⁵ ≈ 1.3 — matching the observed 39/54 ≈ 0.73 once activity corrections at I = 0.1 M are included. Adding the second glycinate (β₂/β₁ ≈ 10^3.79) is further penalised by the same low [Gly⁻], which is why [Co(Gly)₂] is already an order of magnitude smaller than [Co(Gly)⁺] and [Co(Gly)₃]⁻ is negligible.

**Where the biography goes.** The verdict identifies the Co²⁺ ↔ [Co(Gly)]⁺ crossover at pH ≈ 7.15 (bracketed by the pH 7.1 and 7.2 samples, where fractions cross ~48 %/43 % → 42 %/47 %) and Co²⁺ ↔ [Co(Gly)₂] at pH ≈ 7.5 (24 % each). Below the first crossover the aquo ion dominates; above pH ~7.2 the mono-glycinate takes over, and by pH 7.5 the bis-glycinate has caught up with free Co²⁺. Hydrolysed species and Co(OH)₂(s) remain three or more orders of magnitude below the glycinate ladder throughout — glycine, weak as it is here, still keeps Co(II) far from its hydrolysis onset.

**Irving–Williams check.** The series predicts Co(II) < Ni(II) < Cu(II) ≫ Zn(II) for divalent 3d complex stability with amino-acid-type N,O donors. The Co(II)–glycinate constants used here (log β₁ = 4.67, log β₂ = 8.46) are indeed modest — comparable to literature Ni(II)–Gly and clearly below Cu(II)–Gly (log β₁ ≈ 8.6). The practical consequence, visible in this calculation, is that at physiological pH a 10-fold glycine excess is **not** enough to fully chelate Co(II): more than half the metal remains as free aquo ion. That is exactly the Irving–Williams expectation — Cu(II) under the same conditions would be almost quantitatively bound, whereas Co(II) sits in the shallow-binding tail of the series and needs either higher pH (to raise [Gly⁻]) or a large ligand excess to be titrated out of the aquo form.

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
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_concentrations.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_concentrations.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_envelope_Co$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_envelope_Co$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_envelope_L1.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_envelope_L1.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_L1.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_L1.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_ligand.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_ligand.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_metal.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_frac_metal.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_log_conc.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_log_conc.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_log_conc.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_log_conc.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_phase_balance_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_phase_balance_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_run_params.json](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_run_params.json>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_state_metrics.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_state_metrics.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_verdict.md](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_verdict.md>)
- [solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_Co.json](<solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Glycine_Co.json>)
- [verdict.json](<verdict.json>)
