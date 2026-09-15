## Doability
Doable. Fe(III), Ca(II), Mg(II) and DTPA are all present in the SRD-46 catalog with a full ladder of DTPA protonation, hydrolysis, and 1:1 / 2:1 / protonated / hydroxo-mixed complexes for each metal, and the request maps cleanly onto a 1-D pH_sweep at fixed totals, T, I.

## Result
System: 1 mM Fe(III) + 1 mM Ca(II) + 1 mM Mg(II) + 5 mM DTPA, T = 25 °C, I = 0.1 M (fixed-I mode; solver-reported I range 0.020–0.044 M reflecting the charged DTPA speciation), pH 6.0–10.0, 41 points. Redox states are frozen (no e- balance). Convergence: 41/41 for every metal group and for the ligand. One solid appears in the window: FeO(OH)(s,alpha) precipitates from pH ≈ 8.40 onward (first sample at pH 8.40, fraction 3.15%; grows to 87.4% of Fe(III) at pH 9.0 and 99.8% at pH 10.0). No Ca(OH)2, Mg(OH)2 or Fe(OH)3 (amorph) reaches saturation in this window.

## Analysis
**Fraction of each metal bound to DTPA vs free/hydroxo (from `*_frac_metal.csv`, group-normalised to each metal's total).**

| pH | Ca(II) DTPA-bound | Ca(II) free/OH | Fe(III) DTPA-bound (aq) | Fe(III) free/hydroxo (aq) | Fe(III) as FeO(OH)(s) | Mg(II) DTPA-bound | Mg(II) free/OH |
|----|---|---|---|---|---|---|---|
| 7.0 | 99.80 % ([Ca(DTPA)]3- 96.94 %, [Ca(DTPA)H]2- 2.85 %) | 0.20 % (Ca2+) | ≈100 % ([Fe(DTPA)]2- 99.04 %, [Fe(DTPA)(OH)]3- 0.95 %) | ≈0 (Fe(OH)_x < 1e-10) | 0 | 95.0 % ([Mg(DTPA)]3- 78.59 %, [Mg(DTPA)H]2- 16.36 %, [Mg2(DTPA)]- 0.05 %) | 5.00 % (Mg2+) |
| 8.0 | 99.99 % ([Ca(DTPA)]3- 99.70 %) | 0.005 % | ≈100 % ([Fe(DTPA)]2- 91.25 %, [Fe(DTPA)(OH)]3- 8.74 %); no solid yet | ≈0 | 0 | 99.79 % ([Mg(DTPA)]3- 97.81 %, [Mg(DTPA)H]2- 2.04 %) | 0.15 % (Mg2+) |
| 9.0 | 99.97 % ([Ca(DTPA)]3- 99.97 %) | ~3e-4 % | 12.6 % of total Fe (aqueous: [Fe(DTPA)]2- 6.42 %, [Fe(DTPA)(OH)]3- 6.15 %) | ≈0 aqueous free/OH | **87.4 % as FeO(OH)(s,alpha)** | 99.98 % ([Mg(DTPA)]3- 99.72 %, [Mg(DTPA)H]2- 0.21 %) | 0.01 % (Mg2+) |

**Selectivity picture.** DTPA is *not* selective for Fe(III) over Ca/Mg in the thermodynamic sense — all three metals are essentially quantitatively chelated at pH ≥ 7 because 5 mM DTPA is a 5:3 molar excess over the summed metal totals. The reference constants explain why every metal ends up in a DTPA complex: log β for M + DTPA(5-) → M(DTPA) is 28.00 for Fe(III), 10.75 for Ca(II) and 9.27 for Mg(II); even the weakest (Mg) has a formation constant large enough that, when ligand is in excess and pH is high enough to expose the free ligand form, essentially all Mg is captured.

**Why the dominant species change where they do.** The free-ligand fraction is set by DTPA's own protonation ladder (dominance in the ligand table: H2DTPA(3-) below pH 7.8, HDTPA(4-) from 7.8 to 9.5, fully deprotonated DTPA(5-) above 9.5). For Ca and Mg, whose binding is modest, the protonated complex [M(DTPA)H]2- competes near pH 6-7 (Ca: [Ca(DTPA)H]2- peaks 20.5 % at pH 6.0; Mg: [Mg(DTPA)H]2- peaks 32.1 % at pH 6.3), and free M2+ persists at low pH because the ligand is mostly locked up as H2DTPA(3-)/H3DTPA(2-); Mg2+ still holds 57.8 % at pH 6.0 and Ca2+ 9.8 %. Deprotonation of the DTPA pool feeds the fully deprotonated [M(DTPA)]3- complex, which is dominant for Ca from pH 6 upward and takes over Mg above pH 6.4 (Mg crossover Mg2+ ↔ [Mg(DTPA)]3- at pH ≈ 6.34). By pH 8 both alkaline-earth complexes are ≥99.7 % chelated. Fe(III) never has a free-ion problem: log β Fe(DTPA)H(-) = 31.56 and log β Fe(DTPA)2- = 28.00, so even the tightly protonated H2DTPA(3-) at pH 6 can supply Fe with enough ligand, and [Fe(DTPA)]2- reaches its 99.8 % peak at pH 6.1.

**The real selectivity issue is precipitation, not competition.** The Fe(III) hydroxide/oxyhydroxide is so insoluble (log K for Fe3+ + 3 OH- → FeO(OH)(s,alpha): -0.5; Fe(OH)3(s): -3.2) that above pH 8.4 the FeO(OH)(alpha) solid becomes thermodynamically preferred over the DTPA chelate. The solver reports the crossover at pH ≈ 8.58 (each ~42 %), and by pH 9 only 12.6 % of Fe stays in the DTPA pool. This is chemically sensible: at high pH the OH- activity beats even the log β = 28 of the DTPA complex, because the solid has effectively infinite ligand activity. Meanwhile Ca and Mg have no analogous solid competitor in the window (Ca(OH)2, Mg(OH)2 stay undersaturated), so they remain fully chelated and free in solution as [M(DTPA)]3-.

**Practical reading.** If the water-treatment goal is to *hold* Fe(III) in solution as a benign chelate while leaving Ca/Mg untouched, DTPA fails on both counts: (i) it *does* bind Ca and Mg almost quantitatively at pH ≥ 7, so it will strip hardness ions and be consumed by them, and with a 5:3 stoichiometry there is only 2 mM ligand headroom over the metal totals; (ii) even the Fe(III)-DTPA complex is defeated by oxyhydroxide precipitation above pH ≈ 8.5, so at typical drinking-water pH (7.5-8.5) DTPA holds Fe(III) well but at pH 9 iron mostly drops out as FeOOH(s) despite the excess ligand. For selective Fe(III) capture in hard water one needs either (a) a lower pH (≤ 8) to keep Fe in [Fe(DTPA)]2-, or (b) a chelator whose Ca/Mg formation constants are much lower than DTPA's log β = 10.75 / 9.27 while retaining Fe(III) affinity.

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
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_concentrations.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_concentrations.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_Ca$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_Ca$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_Fe$+3.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_Fe$+3.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_L1.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_L1.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_Mg$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_envelope_Mg$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_Fe.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_Fe.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_L1.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_L1.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_ligand.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_ligand.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_metal.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_metal.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_Mg.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_frac_Mg.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_log_conc.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_log_conc.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_log_conc.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_log_conc.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_phase_balance_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_phase_balance_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_phase_balance_Fe.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_phase_balance_Fe.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_phase_balance_Mg.png](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_phase_balance_Mg.png>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_run_params.json](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_run_params.json>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_state_metrics.csv](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_state_metrics.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_verdict.md](<solver/Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_verdict.md>)
- [solver/topology_Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_Ca.json](<solver/topology_Ca$+2_+_Ca$+0_+_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Mg$+2_+_Mg$+0_+_DTPA_Ca.json>)
- [verdict.json](<verdict.json>)
