## Doability
Doable — Zn(II)/glycine pH sweep at fixed I and T is fully in scope; SRD-46 supplies Zn–glycinate, Zn–hydroxo, and mixed Zn(Glyc)(OH) constants.

## Result
- System: 1.00 mM Zn(II) total, 10.0 mM glycine total, 25 °C, fixed I = 0.1 m (calculated I 4.5e-4 – 1.5e-3 M inside the solver's charge accounting), redox excluded (Zn(0) inactive, [Zn0]_total = 0).
- Method: `pH_sweep`, pH 6.5–7.5, 21 points.
- Convergence: 21/21 samples converged for every component (Zn$+2, L1). No unconverged evidence.
- No solid Zn(OH)2(s,beta1) precipitates anywhere in the window (fraction 0 throughout the metal-fraction CSV); all Zn stays aqueous.

## Analysis
**Zn(II) distribution at pH 7.00 (fractions of total Zn, from `frac_metal.csv`):**

| Species | Fraction | Concentration (M) |
|---|---:|---:|
| Zn²⁺ (aquo) | 33.67 % | **3.37 × 10⁻⁴** |
| [Zn(Glyc)]⁺ | 45.99 % | 4.60 × 10⁻⁴ |
| [Zn(Glyc)₂]⁰ | 19.14 % | 1.91 × 10⁻⁴ |
| [Zn(Glyc)(OH)]⁰ | 0.579 % | 5.79 × 10⁻⁶ |
| [Zn(OH)₂]⁰ | 0.326 % | 3.26 × 10⁻⁶ |
| [Zn(OH)]⁺ | 0.103 % | 1.03 × 10⁻⁶ |
| [Zn(Glyc)₃]⁻ | 0.197 % | 1.97 × 10⁻⁶ |
| [Zn(OH)₃]⁻, [Zn(OH)₄]²⁻ | <3 × 10⁻⁸ | negligible |

**Headline number for the Irving–Williams ranking:** free aquo [Zn²⁺] at pH 7 = **3.37 × 10⁻⁴ M** (i.e. only ~34 % of the 1 mM Zn total is retained as the free hexaaquo ion; the balance is glycinate-complexed).

**Grouped totals at pH 7:**
- Zn–glycinate complexes ([Zn(Glyc)]⁺ + [Zn(Glyc)₂] + [Zn(Glyc)₃]⁻ + [Zn(Glyc)(OH)]) ≈ **65.9 %** of total Zn.
- Zn–hydroxide complexes ([Zn(OH)]⁺ + [Zn(OH)₂] + [Zn(OH)₃]⁻ + [Zn(OH)₄]²⁻) ≈ **0.43 %** of total Zn — hydrolysis is essentially irrelevant compared with glycinate binding.
- Mixed hydroxo–glycinate [Zn(Glyc)(OH)] ≈ 0.58 %.

**Chemistry of the crossovers.** The card gives log β₁(ZnGly⁺) = 4.96 and log β₂(ZnGly₂) = 9.19 (β₂/β₁ ≈ 10^4.23, i.e. K₂ ~ 10^4.23), while glycine's conjugate-acid pKa is 9.57 (log β for H+ + Gly⁻ ⇌ HGly). At pH 6.5–7.5 the ligand pool is >99 % zwitterionic HGly (verdict: HGlycine peaks at 96 % at pH 6.5 and stays dominant across the window), so free Gly⁻ is only ~10⁻²·⁵ of total glycine. Binding therefore competes directly with the ammonium deprotonation step: as pH rises, [Gly⁻] climbs one decade per pH unit, driving Zn²⁺ → [Zn(Glyc)]⁺ (crossover pH ≈ 6.86, both ~43 %) and then [Zn(Glyc)]⁺ → [Zn(Glyc)₂] (crossover pH ≈ 7.41, both ~42 %). The Zn²⁺ ↔ [Zn(Glyc)₂] equal-fraction point sits at pH ≈ 7.13 (each ~26 %), between them. Hydroxo species remain minor because Zn(OH)⁺ (log β = −9.30) and Zn(OH)₂⁰ (log β = −15.80) require substantially higher pH to compete; the Zn(OH)₂(s) dissolution constant (log β = −12.46) implies a solubility floor well above 1 mM at pH ≤ 7.5, consistent with no predicted precipitation.

**Irving–Williams context.** At pH 7 with a 10× excess of glycine, the [Zn²⁺]_free/[Zn]_total ratio is ~0.34 for Zn(II). The Irving–Williams series predicts Zn(II) should bind glycinate less strongly than Cu(II) or Ni(II) (and comparably to or slightly more strongly than Co(II)); the free-metal fraction is therefore expected to be higher (less depleted) for Zn than for Cu/Ni. The value 3.37 × 10⁻⁴ M is the number to feed into the four-metal comparison — a lower free-metal concentration at the same pH/ligand loading indicates stronger complex formation and a higher position in the series.

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
- [solver/topology_Zn$+2_+_Zn$+0_+_Glycine_Zn.json](<solver/topology_Zn$+2_+_Zn$+0_+_Glycine_Zn.json>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_concentrations.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_concentrations.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_L1.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_L1.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_Zn$+2.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_Zn$+2.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_L1.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_L1.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_ligand.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_ligand.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_metal.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_metal.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_Zn.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Zn.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_run_params.json](<solver/Zn$+2_+_Zn$+0_+_Glycine_run_params.json>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_state_metrics.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_state_metrics.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_verdict.md](<solver/Zn$+2_+_Zn$+0_+_Glycine_verdict.md>)
- [verdict.json](<verdict.json>)
