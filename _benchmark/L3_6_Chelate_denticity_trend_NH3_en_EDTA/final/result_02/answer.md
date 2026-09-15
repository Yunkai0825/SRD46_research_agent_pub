## Doability
Doable. Ni(II) + ethylenediamine at fixed pH 7 is a well-posed pH_sweep problem; both components exist in the SRD-46 catalog with a full Ni-en and Ni-hydrolysis ladder.

## Result
- System: 1 mM Ni(II) + 30 mM ethylenediamine (en), 25 °C, I = 0.1 M (fixed), redox excluded.
- Method: pH_sweep, pH 6.5–7.5, 11 points, all 11 converged.
- Solid Ni(OH)₂(s) is included in the model but does not precipitate anywhere in the window (dissolution column = 0 at every pH).
- Dominant Ni(II) species across the entire 6.5–7.5 window: [Ni(en)₂]²⁺ (peak 84.3% at pH 6.9). At pH 7.0: [Ni(en)₂]²⁺ = 83.7% of Ni.

### Key concentrations at pH 7.00 (from concentrations.csv)
| Species | Concentration (M) | Fraction of Ni_total |
|---|---:|---:|
| [Ni(en)₂]²⁺ | 8.37 × 10⁻⁴ | 83.7% |
| [Ni(en)₃]²⁺ | 1.06 × 10⁻⁴ | 10.6% |
| [Ni(en)]²⁺ | 5.61 × 10⁻⁵ | 5.6% |
| **Ni²⁺ (free)** | **2.60 × 10⁻⁷** | **0.026%** |
| [Ni(OH)]⁺ | 6.33 × 10⁻¹¹ | negligible |
| [Ni(OH)₂]⁰ | 1.59 × 10⁻¹² | negligible |
| Ni(OH)₂(s) | 0 | not saturated |

**pNi = −log[Ni²⁺] = 6.58 at pH 7.0.**

Ligand side at pH 7: H₂en²⁺ dominates (fraction 63% of L_total → 1.89 × 10⁻² M), Hen⁺ is 30% (8.99 × 10⁻³ M), and free neutral en is only 1.08 × 10⁻⁵ M. Roughly 3.3 mM of the total 30 mM en is tied up as Ni complexes (≈11% of the ligand pool).

## Analysis
**Why [Ni(en)₂]²⁺ dominates at pH 7.** The reference table gives cumulative formation constants log β₁ = 7.30, log β₂ = 13.44, log β₃ = 17.51 for Ni²⁺ + n en, and en protonation constants log β(Hen⁺) = 9.92 and log β(H₂en²⁺) = 17.03 (so pKa₂ ≈ 9.92, pKa₁ ≈ 7.11). At pH 7 the ligand is almost entirely protonated (H₂en²⁺ + Hen⁺ ≈ 99.99% of L_total), leaving free neutral en at only ~1.1 × 10⁻⁵ M. That small free-en activity is what the Ni²⁺ actually sees. Under those conditions the stepwise mass-action balance favors the bis complex: [Ni(en)₃]²⁺ requires three simultaneous free-en encounters and is disadvantaged by the low [en]; the mono complex [Ni(en)]²⁺ is thermodynamically weaker (log K₁ = 7.30 vs log K₂ = 6.14 and log K₃ = 4.07). The result is a clean [Ni(en)₂]²⁺ plateau across 6.5–7.5, flanked by [Ni(en)]²⁺ (falling as pH rises and more en deprotonates) and [Ni(en)₃]²⁺ (rising with pH). The verdict flags a mono/tris crossover at pH ≈ 6.92 (each ~8%), symmetric about the bis maximum — a classic signature of a well-behaved stepwise chelate system.

**Why free Ni²⁺ is suppressed to 2.6 × 10⁻⁷ M (pNi = 6.58).** Chelation by two bidentate en ligands sequesters 83.7% of the metal into [Ni(en)₂]²⁺, and the remainder goes into the mono/tris complexes. Only 0.026% of the Ni budget remains as aquated Ni²⁺. This is the chelate-effect number the comparison needs: with 30 mM en the pNi at pH 7 is 6.58, versus a nominal pNi = 3.0 in the absence of any ligand. En, being bidentate, provides ~4 orders of magnitude of Ni²⁺ suppression at neutral pH despite most of the ligand being protonated. This will be intermediate between monodentate NH₃ (weaker per donor, similar total donor budget) and hexadentate EDTA (one ligand can wrap the whole coordination sphere), which is exactly why the trio is a textbook chelate-effect probe.

**Hydrolysis and precipitation.** Ni hydroxo species are negligible at pH 7 ([Ni(OH)]⁺ ≈ 6 × 10⁻¹¹ M, [Ni(OH)₂]⁰ ≈ 2 × 10⁻¹² M, [Ni₄(OH)₄]⁴⁺ ≈ 2 × 10⁻²⁶ M) because the en complexes hold [Ni²⁺] far below any hydrolysis threshold. Ni(OH)₂(s) does not precipitate anywhere in 6.5–7.5 — the free [Ni²⁺] is 4+ orders of magnitude below what would be needed to reach saturation given the Atlas dissolution log K = −11.71. This is a practically important point for the comparison: at 30 mM en, Ni is fully retained in solution as chelate complexes at pH 7, with no solid loss to confound the pNi reading.

**Caveats.** Values hold at the fixed totals (1 mM Ni, 30 mM en), 25 °C, and I ≈ 0.03–0.05 M (the solver reports the actual I range; the target 0.1 M was not enforced by inert electrolyte). Crossover pH is grid-bracketed to the 0.1-pH mesh. Redox is excluded, so only Ni(II) chemistry is described.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_Ni.json>)
- [verdict.json](<verdict.json>)
