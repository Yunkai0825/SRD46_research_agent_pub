## Doability
Doable. Co(II) and glycine are both in the SRD-46 catalog with a full family of Co–glycinate and Co-hydroxo species, and a pH_sweep at fixed totals is exactly the supported 1-D speciation method for this question.

## Result
System: Co(II) 1.00 mM + glycine 10.0 mM, aqueous, T = 25.0 °C, ionic strength fixed at I = 0.1 M, redox excluded (only Co$^{2+}$ populated; Co(0)/Co(+3)/Co(+4) totals set to 0). Method: pH_sweep, 101 points over pH 2–12. Convergence: 101/101 samples converged (state_metrics). No solid precipitates until pH 10.10, where Co(OH)$_2$(s) first appears; at the target pH 7 the system is fully aqueous.

At the requested pH 7.0 (frac_metal CSV, row pH = 7.0000; total Co = 1.00e-3 M):

| Species | Fraction of total Co | Concentration (M) |
|---|---:|---:|
| Co$^{2+}$ (free aquo) | 0.5426 | 5.43 × 10$^{-4}$ |
| [Co(Gly)]$^{+}$ | 0.3940 | 3.94 × 10$^{-4}$ |
| [Co(Gly)$_2$] | 0.0617 | 6.17 × 10$^{-5}$ |
| [Co(Gly)$_3$]$^{-}$ | 7.07 × 10$^{-4}$ | 7.07 × 10$^{-7}$ |
| [Co(OH)]$^{+}$ | 6.62 × 10$^{-4}$ | 6.62 × 10$^{-7}$ |
| [Co(Gly)(OH)] | 3.20 × 10$^{-4}$ | 3.20 × 10$^{-7}$ |
| other hydroxo / polynuclear | < 1 × 10$^{-5}$ | negligible |

Free fraction = 54.3 %; glycine-bound fraction (sum of Co–Gly, Co–Gly$_2$, Co–Gly$_3$, and mixed Co–Gly–OH) = 45.6 %; hydroxo-only species contribute < 0.1 %.

## Analysis
**Free [Co$^{2+}$] and bound fraction.** At pH 7, 25 °C, I = 0.1 M with 10-fold excess glycine, the calculation gives [Co$^{2+}$]$_{free}$ = 5.43 × 10$^{-4}$ M and the dominant Co–glycinate is the 1:1 mono-glycinato complex [Co(Gly)]$^{+}$ at 3.94 × 10$^{-4}$ M (39.4 %). The 2:1 bis-glycinato complex [Co(Gly)$_2$] carries a further 6.2 %. Overall roughly half of the cobalt is complexed and half remains as the free aquo ion.

**Why the split sits near 50/50 at pH 7.** The reference table lists log β$_1$ = 4.67, log β$_2$ = 8.46, log β$_3$ = 10.90 for the successive Co(II)–glycinate complexes, and, most importantly, log β = 9.57 for HGly (the α-amino pKa) — meaning glycine is > 99 % protonated as the zwitterion HGly at pH 7 and only a very small fraction is present as the reactive amino-deprotonated anion Gly$^{-}$. The effective conditional constant for the reaction Co$^{2+}$ + HGly ⇌ [Co(Gly)]$^{+}$ + H$^{+}$ is log β$_1$ − pK$_a$ = 4.67 − 9.57 = −4.9, so at pH 7 the driving mass-action factor [H$^{+}$]$^{-1}$ = 10$^{7}$ combined with 10 mM total glycine is only just enough to pull about half the Co into the mono-complex. The bis-complex is further disfavoured because it consumes a second scarce Gly$^{-}$; that is why [Co(Gly)$_2$] is still small (6 %) at pH 7 even though its cumulative log β$_2$ is large.

**Dominance sequence and crossovers.** The verdict's dominance map is entirely consistent with this picture: free Co$^{2+}$ dominates from pH 2 up to 7.2, [Co(Gly)]$^{+}$ from 7.2–7.9, [Co(Gly)$_2$] from 7.9–9.4, and [Co(Gly)$_3$]$^{-}$ from 9.4–10.4 before Co(OH)$_2$(s) takes over above pH 10.4. Each successive complex requires one more deprotonated Gly$^{-}$, so the ladder is climbed as pH rises and the free-Gly$^{-}$ activity grows by an order of magnitude per pH unit. The Co$^{2+}$ ↔ [Co(Gly)]$^{+}$ crossover at pH ≈ 7.15 (each ~45 %) falls essentially at the target condition — this is exactly why the pH 7 sample straddles 50/50 free vs 1:1 bound.

**Practical readout for the Irving–Williams comparison.** For a Co(II) benchmark under the exact conditions of the L0 test — 1 mM M(II), 10 mM glycine, pH 7, 25 °C, I = 0.1 M — Co(II) sits at ≈ 54 % free / ≈ 46 % glycine-bound, with the mono-glycinato complex [Co(Gly)]$^{+}$ carrying essentially all the bound cobalt. This is the modest binding expected midway up the Irving–Williams series; the Cu(II) analogue, with log β$_1 \approx 8$ for Cu–Gly, will drive the free fraction several orders of magnitude lower at the same pH, and Ni(II) will lie between the two. Hydroxo chemistry is not yet a factor at pH 7 (Co(OH)$_2$(s) does not appear until pH 10.10), so the binding here is a clean glycinate-vs-aquo competition.

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
