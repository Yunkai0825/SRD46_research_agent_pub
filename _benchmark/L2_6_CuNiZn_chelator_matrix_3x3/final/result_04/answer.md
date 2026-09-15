## Doability
Doable — Ni(II) + glycine 1-D pH speciation is directly supported by SRD-46 and the pH_sweep method.

## Result
System: 1.00 mM Ni(II) + 5.00 mM glycine, 25.0 °C, I = 0.1 M (fixed ionic mode), pH 2.0–12.0 in 0.1 pH steps (101 points). Redox excluded — Ni(II) only. Convergence: 101/101 samples converged. Included aqueous species: Ni2+, [Ni(OH)]+, [Ni(OH)2], [Ni(OH)3]-, [Ni4(OH)4]4+, [Ni(Glyc)]+, [Ni(Glyc)2], [Ni(Glyc)3]-, plus glycine acid–base forms (H2Glycine+, HGlycine, Glycine) and Ni(OH)2(s). Precipitation begins at pH 10.20 (Ni(OH)2, 6.60e-05 M).

**At pH 7.00 (from concentrations.csv):**

| Species | Concentration (M) | % of total Ni |
|---|---:|---:|
| Ni2+ (free) | 1.453e-04 | 14.5% |
| [Ni(Glyc)]+ | 4.923e-04 | 49.2% |
| [Ni(Glyc)2] | 3.436e-04 | 34.4% |
| [Ni(Glyc)3]- | 1.878e-05 | 1.9% |
| [Ni(OH)]+ | 3.54e-08 | ~0% |
| Ni(OH)2(s) | 0 (undersaturated) | 0% |

**Free [Ni2+] at pH 7.00 = 1.45 × 10⁻⁴ M** (i.e., ~85.5% of total nickel is bound by glycine; the conditional side-reaction coefficient α_Ni(L) ≈ 6.9).

## Analysis
**Ligand availability controls the onset of complexation.** Glycine has card protonation constants log β(H+L) = 9.57 and log β(2H+L) = 11.90, so the singly protonated zwitterion HGlycine dominates from pH ≈ 2.4 up to ≈ 8.9. The chelating amine is only deprotonated as pH rises above ~9, so the free anionic ligand fraction [Glycine]/[L]_tot grows by roughly one decade per pH unit through the neutral range. This is why almost no Ni–Gly complex is seen below pH ~5 even though the metal is thermodynamically capable of binding: the effective free ligand concentration is too low.

**Crossover from aqua to mono-glycinate near pH 6.4.** Ni2+ remains the dominant Ni form from pH 2 up to ≈ 6.5, where [Ni(Glyc)]+ overtakes it (verdict crossover pH ≈ 6.41). The stepwise formation constants from the reference card are log K1 = 5.74, log K2 = 10.58 − 5.74 = 4.84, log K3 = 14.10 − 10.58 = 3.52 — a normal statistically-attenuated chelate series for an octahedral d⁸ ion with bidentate N,O donors. Because K2 is only ~ one order below K1, once the mono complex has formed the bis complex follows immediately, so [Ni(Glyc)2] takes the lead by pH ≈ 7.2 (crossover with mono at pH ≈ 7.18, each ~44%).

**pH 7.00 sits inside the mono/bis transition.** At exactly pH 7 the mono complex [Ni(Glyc)]+ is the single largest Ni-containing species (49.2%), with [Ni(Glyc)2] a close second (34.4%) and a still-substantial 14.5% free Ni2+. This intermediate distribution — not a clean 1:1 or 1:2 speciation — is a direct consequence of the 5:1 ligand-to-metal ratio being only modestly in excess of the stoichiometric demand for the bis complex (which needs 2:1) once one accounts for the fact that most glycine is still HGlycine at pH 7. For a metal-selectivity matrix this means the effective ligand competition for Ni at neutral pH is governed by K1 primarily and K2 secondarily; the tris complex is negligible (<2%) until pH ≈ 8.5 where it takes over (peak 85.6% at pH 10.1).

**Hydroxide chemistry and precipitation.** Mononuclear hydrolysis (log β for [Ni(OH)]+ = −10.4, [Ni(OH)2] = −19.0) is far too weak to compete with glycine anywhere in the aqueous window: [Ni(OH)]+ never exceeds ~5 × 10⁻⁸ M and the tetramer [Ni4(OH)4]4+ is entirely negligible at 1 mM total Ni. Solid Ni(OH)2 first appears at pH 10.20 and grows to 99.6% of Ni by pH 12; between pH 10.7 and 12 the precipitate is the dominant sink, displacing even [Ni(Glyc)3]-. The chelate therefore extends the solubility window of Ni(II) by roughly 1.5 pH units beyond the ligand-free hydroxide precipitation threshold.

**Practical implication for the selectivity matrix.** At pH 7.00 the conditional side-reaction coefficient α_Ni(Gly) = [Ni]_total/[Ni2+] ≈ 6.88 (log α ≈ 0.84). Any competing ligand entered into the matrix at pH 7 must be compared against a Ni that is already ~85% complexed by glycine; effective conditional stability constants for other Ni-L systems should be scaled by 1/α to reflect the free-metal buffering that 5 mM glycine imposes.

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
