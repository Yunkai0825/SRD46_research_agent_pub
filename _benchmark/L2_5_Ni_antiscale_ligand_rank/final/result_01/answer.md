## Doability
Doable — Ni(II)/glycine with hydrolysis and Ni(OH)2(s) is a standard SRD-46 pH-speciation problem.

## Result
- System: Ni(II) 1.00 mM + glycine 10.0 mM, 25 °C, I = 0.1 M (fixed), pH 4–11, 71 grid points.
- Method: `pH_sweep` (redox excluded; Ni(+0/+3/+4) totals zero as declared).
- Convergence: 71/71 samples converged for every component (Ni2+ and L1 blocks).
- Solid model included: `[Ni(OH)2](s)` with dissolution log β = −12.80 (from the reference table).

## Analysis
**Dominance ladder (Ni2+ block).** The verdict shows a clean, glycine-driven cascade as pH rises:

- pH 4.0–6.1 → free Ni2+
- pH 6.1–6.8 → [Ni(Glyc)]+
- pH 6.8–8.0 → [Ni(Glyc)2]
- pH 8.0–11.0 → [Ni(Glyc)3]−

The crossovers Ni2+↔[Ni(Glyc)]+ at pH ≈ 6.07, [Ni(Glyc)]+↔[Ni(Glyc)2] at pH ≈ 6.80, and [Ni(Glyc)2]↔[Ni(Glyc)3]− at pH ≈ 7.98 track the deprotonation of the ligand: HGlycine (pKa of the ammonium group log β = 9.57 for H+L ⇌ HL) dominates the total ligand pool up to pH 9.4, but the tiny free-Glycine− fraction present already at pH ~6 is captured very efficiently by Ni2+ because the stepwise formation constants are large (log β1 = 5.74, log β2 = 10.58, log β3 = 14.10). Each added glycinate contributes ~5 log units, so as [Gly−] climbs one order per pH unit the ML → ML2 → ML3 boundaries appear at nearly one pH unit apart, exactly as seen.

**Free [Ni2+] at pH 9.** From the concentrations table at pH 9.000:

- [Ni2+] = **2.95 × 10⁻⁹ M**
- Fraction of Ni_T as free Ni2+ = 2.95 × 10⁻⁹ / 1.00 × 10⁻³ = **2.95 × 10⁻⁶ (≈ 3 ppm of total Ni)**.
- Dominant Ni species at pH 9: [Ni(Glyc)3]− at 8.77 × 10⁻⁴ M (87.7 % of Ni_T), with [Ni(Glyc)2] at 1.22 × 10⁻⁴ M (12.2 %) making up essentially the rest. Hydroxo species [Ni(OH)]+, [Ni(OH)2](aq), [Ni(OH)3]− and the [Ni4(OH)4]4+ cluster are all ≤ 2 × 10⁻¹⁰ M — hydrolysis is completely out-competed by glycinate chelation.

Glycine (10:1 excess over Ni) therefore suppresses free Ni2+ by roughly **5.4 orders of magnitude** relative to the uncomplexed 1 mM total. The chemistry is straightforward: at pH 9 enough deprotonated glycinate is present to saturate the tris-glycinato coordination sphere, and the cumulative β3 is large enough that the free-metal activity is pinned many decades below what a bare Ni(II)/H2O system would give.

**Ni(OH)2(s) precipitation.** The `[Ni(OH)2](s)` column of the concentrations CSV is **0.000e+00 at every pH from 4.0 to 11.0**, i.e. the saturation criterion is never met over the whole scan window. A quick check confirms this: with log Ksp = −12.80 (K_s0 for Ni(OH)2(s) ⇌ Ni2+ + 2 OH−), the solubility limit at pH 9 (pOH = 5, [OH−] = 10⁻⁵ M at I = 0.1) is [Ni2+]_sat = 10⁻¹²·⁸ / 10⁻¹⁰ ≈ 6 × 10⁻³ M, i.e. six orders of magnitude above the actual free [Ni2+] = 3 × 10⁻⁹ M produced by the glycinate complexation. **No Ni(OH)2(s) scale forms** anywhere in the 4–11 pH window at these totals; the same conclusion holds at pH 9 specifically.

**Practical read.** A 10-fold molar excess of glycine at pH 9 is more than sufficient to keep Ni(II) fully sequestered as [Ni(Glyc)3]− / [Ni(Glyc)2] and to hold free Ni2+ ~10⁶ times below the Ni(OH)2 solubility limit. Any Ni(OH)2 scaling tendency in this alkaline regime is chemically eliminated by the ligand.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_Ni.json>)
- [verdict.json](<verdict.json>)
