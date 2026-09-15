## Doability
Doable — Ni(II) and citric acid are in the SRD-46 catalog; a 1-D pH sweep at fixed I, redox excluded, is directly supported.

## Result
System: 1.00 mM Ni(II) + 5.00 mM citric acid, T = 25 °C, fixed ionic strength I = 0.1 M, pH 2.0–12.0, redox excluded. Method: `pH_sweep`, 101 grid points, all 101/101 converged. Included Ni-bearing aqueous species: Ni²⁺, [Ni(OH)]⁺, [Ni(OH)₂]⁰, [Ni(OH)₃]⁻, [Ni₄(OH)₄]⁴⁺, [Ni(Citr)H₂]⁺, [Ni(Citr)H]⁰, [Ni(Citr)₂H]³⁻, [Ni(Citr)]⁻, [Ni(Citr)₂]⁴⁻, [Ni₂(Citr)₂(OH)₂]⁴⁻, plus solid [Ni(OH)₂](s). Solver-reported precipitation onset: pH 9.80 ([Ni(OH)₂](s), 2.07e-4 M at that sample).

## Analysis
**Free [Ni²⁺] at pH 7.00 (matrix entry).** From the log-concentration table at pH 7.00, log₁₀[Ni²⁺] = −5.6968, i.e. **[Ni²⁺] ≈ 2.01 × 10⁻⁶ M**. Against a nickel total of 1.00 × 10⁻³ M this is a free-metal fraction of ≈2.0 × 10⁻³ (≈0.20 %), i.e. citrate suppresses free Ni²⁺ by roughly 500× at circumneutral pH. The single dominant Ni-bearing species is **[Ni(Citr)₂]⁴⁻** at log₁₀c = −3.0229 (≈9.49 × 10⁻⁴ M, ≈95 % of total Ni); all hydroxo and mono-citrato forms are ≥4 orders of magnitude lower.

**Why the pH-dependent picture looks the way it does.** Dominance regions from the verdict:
- pH 2.0–3.8: free **Ni²⁺** (peak 98.2 % at pH 2.0). Below the second citrate pKa the ligand is present mainly as H₃Cit / H₂Cit⁻ (log β for H₃L = 12.90, H₂L⁻ = 10.00 → effective pK's ≈ 2.9 and 4.35 from the constants table), whose free tridentate carboxylate/alkoxide donor set is largely blocked by protons; only minor [Ni(Citr)H₂]⁺ and [Ni(Citr)H]⁰ appear.
- pH 3.8–4.2: **[Ni(Citr)₂H]³⁻** takes over briefly (peak 35.9 % at pH 4.1) as the second citrate proton comes off and a 1:2 bis-citrato assembly with one residual proton becomes competitive (log β = 13.395 vs. 8.355 for the fully deprotonated 1:2 → the extra proton is worth ≈5 log units and appears exactly in the HCit²⁻ window).
- pH 4.2–9.4: **[Ni(Citr)₂]⁴⁻** dominates broadly (peak 94.9 % at pH 7.4). Full deprotonation to Cit³⁻ (log β for H⁻¹ step / pK ≈ 5.65 from the H:1 → 0 step in the constants table) enables the fully-formed bis-citrato chelate, which with 5 mM citrate and only 1 mM Ni is stoichiometrically favoured over the 1:1 [Ni(Citr)]⁻ (log β = 8.355 vs 5.18 — the second citrate is worth ≈3.2 log units when ligand is in excess).
- pH 9.4–9.9: crossover to the hydrolysed dimer **[Ni₂(Citr)₂(OH)₂]⁴⁻** (peak 70.8 % at pH 9.7), reflecting deprotonation of coordinated water on the bis-chelate before free Ni(OH)₂ becomes stable.
- pH 9.9–12.0: **[Ni(OH)₂](s) precipitates** (onset at pH 9.80, 2.07 × 10⁻⁴ M solid at that point; log₁₀c(s) reaches ≈ −3.00 by pH 11, i.e. essentially all Ni is in the solid). Solubility control by log β(diss) = −12.80 (Ksp ≈ 10⁻¹²·⁸ for Ni²⁺ + 2OH⁻ ⇌ Ni(OH)₂(s)) overtakes even the strong citrate chelate at high [OH⁻].

**Practical / matrix implication.** At pH 7, 5-fold excess citrate over 1 mM Ni(II) drives free [Ni²⁺] to ≈2 × 10⁻⁶ M (log[Ni²⁺] ≈ −5.70), a ≈2.7 log-unit suppression versus uncomplexed nickel. This entry can be compared directly to the Cu and Zn / glycine and EDTA counterparts in the 3×3 matrix. Practically important flags: **no solid at pH 7** (the aqueous chelate is fully in charge), but any drift above pH ≈ 9.8 in this composition will precipitate Ni(OH)₂ and invalidate the free-metal reading; the redox-excluded assumption is appropriate as long as no oxidant/reductant chemistry is invoked downstream.

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
