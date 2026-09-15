## Doability
Doable. SRD-46 provides glycinate complexes ([M(Gly)]+, [M(Gly)2], [M(Gly)3]-) and hydrolysis + hydroxide solids for all three metals; single-pot pH sweep is the correct pH_sweep application.

## Result
System: Co(II) + Ni(II) + Cu(II) each at 1.0 mM with 5.0 mM total glycine, 25 °C, I = 0.1 M (fixed), pH 4.0–10.0 in 0.1 steps. Convergence: 52/61 samples. Samples pH 4.0–9.1 converged (residual ≤ 3e-12); samples pH 9.2–10.0 did NOT converge (residual O(1)) and are excluded as non-evidence. Solids begin to form at pH 8.4 (Co(OH)2), joined by NiO at 8.7 and CuO at 8.9 — see verdict *Precipitation* block. Glycine acid-base constants (from `LC2/thermodynamic_reference_constants.md`): carboxylate pKa ≈ 11.9 − 9.57 = 2.33 (H2Gly+ → HGly), amine pKa = 9.57 (HGly → Gly−).

## Analysis
**Free [M²⁺] at the three requested pH values** (concentrations.csv):

| pH  | [Co²⁺] (M) | [Ni²⁺] (M) | [Cu²⁺] (M) |
|-----|-----------|-----------|-----------|
| 6.0 | 9.78 × 10⁻⁴ | 7.84 × 10⁻⁴ | 1.85 × 10⁻⁶ |
| 7.0 | 8.64 × 10⁻⁴ | 2.90 × 10⁻⁴ | 4.54 × 10⁻⁸ |
| 8.0 | 5.66 × 10⁻⁴ | 4.45 × 10⁻⁵ | 2.46 × 10⁻⁹ |

**Dominant complexes at each pH (fractions of that metal's total):**
- pH 6.0 — Co: Co²⁺ 98 %, [Co(Gly)]⁺ 2.2 %.  Ni: Ni²⁺ 78 %, [Ni(Gly)]⁺ 20 %, [Ni(Gly)₂] 4.6 %.  Cu: [Cu(Gly)₂] 86 %, [Cu(Gly)]⁺ 14 %, free Cu²⁺ 0.19 %.
- pH 7.0 — Co: Co²⁺ 86 %, [Co(Gly)]⁺ 13 %.  Ni: Ni²⁺ 29 %, [Ni(Gly)]⁺ 52 %, [Ni(Gly)₂] 19 %.  Cu: [Cu(Gly)₂] 98 %, [Cu(Gly)]⁺ 2.3 %.
- pH 8.0 — Co: Co²⁺ 57 %, [Co(Gly)]⁺ 37 %, [Co(Gly)₂] 5.2 %.  Ni: Ni²⁺ 4.5 %, [Ni(Gly)]⁺ 37 %, [Ni(Gly)₂] 52 %, [Ni(Gly)₃]⁻ 6.8 %.  Cu: [Cu(Gly)₂] 99.5 %.

**Chemical interpretation.** The three metals are ordered by their glycinate log β values (SRD-46): log β₂ = 15.1 (Cu) ≫ 10.58 (Ni) > 8.46 (Co). Because a bidentate α-aminoacidate needs the deprotonated amine to chelate, complexation only turns on as pH approaches the amine pKa 9.57; but the very large Cu affinity pulls Cu into [Cu(Gly)₂] already at pH 4.5 (Cu²⁺↔[Cu(Gly)₂] crossover at pH ≈ 4.53), driving free [Cu²⁺] into the nanomolar range by pH 7 and near 10⁻⁹ M by pH 8. Ni, with an intermediate log β, is roughly half complexed by pH 6.7 (Ni²⁺↔[Ni(Gly)]⁺ crossover at 6.68) and >95 % complexed by pH 8. Cobalt, the weakest binder, stays majority-Co²⁺ all the way to pH 8.37, so its free-ion fraction is still 57 % at pH 8.

**Discrimination.** Between Cu and Co the free-ion contrast is enormous — a factor of ~5 × 10⁵ at pH 6, ~2 × 10⁷ at pH 7, ~2 × 10⁵ at pH 8. Glycine therefore functions as a very effective Cu-vs-(Co,Ni) mask across pH 5–8. Ni-vs-Co separation is much weaker: only a factor of 1.2 at pH 6, 3 at pH 7, and 13 at pH 8. Useful Ni/Co discrimination requires the higher end of the window, but from pH 8.4 onward Co(OH)₂(s) starts to precipitate (verdict *Precipitation*), and by pH 8.9 CuO(s) and NiO(s) also appear, terminating clean solution-phase chemistry. Practically the best free-[M²⁺] discrimination window is pH ≈ 7–8: Cu is essentially quantitatively sequestered as [Cu(Gly)₂], most Ni is bound as mixed [Ni(Gly)]⁺/[Ni(Gly)₂], and Co remains largely aqua-ion — a clean Cu ≫ Ni > Co ordering. The pH ≥ 9.2 region is not resolved by this calculation (solver did not converge; the apparent “return to M²⁺ dominance” printed in the verdict for that region is a non-evidence artifact and should be disregarded).

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
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_concentrations.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_concentrations.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Co$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Co$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Cu$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Cu$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_L1.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_L1.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Ni$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Ni$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Cu.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Cu.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_L1.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_L1.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_ligand.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_ligand.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_metal.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_metal.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Ni.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Ni.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Cu.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Cu.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Ni.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Ni.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_run_params.json](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_run_params.json>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_state_metrics.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_state_metrics.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_verdict.md](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_verdict.md>)
- [solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_Co.json](<solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_Co.json>)
- [verdict.json](<verdict.json>)
