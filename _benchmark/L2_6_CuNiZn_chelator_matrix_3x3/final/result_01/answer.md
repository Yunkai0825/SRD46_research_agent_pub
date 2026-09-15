## Doability
Doable: Cu(II) and glycine are in the SRD-46 catalog, pH 7 falls inside the pH 3–11 sweep, and a `pH_sweep` at fixed T/I is the appropriate method for a single-pH speciation snapshot.

## Result
- System: Cu(II) 1.00 mM + glycine 5.00 mM, T = 25 °C, ionic strength fixed at 0.1 M, redox excluded (Cu(0)/Cu(+I) totals = 0).
- Method: 1-D `pH_sweep` over pH 3.0–11.0, 81 points; convergence 81/81. No precipitation at pH 7 (first solid, CuO(s), appears only at pH ≈ 10.10).
- Values quoted at pH 7.0 come from `solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv` and `..._frac_metal.csv`.

**Cu distribution at pH 7 (fraction of total Cu, [conc] in M):**

| Species | Fraction of total Cu | Concentration (M) |
|---|---:|---:|
| [Cu(Glyc)2]⁰ (bis-glycinate) | 0.98498 | 9.850e-4 |
| [Cu(Glyc)]⁺ (mono-glycinate) | 0.01500 | 1.500e-5 |
| Cu²⁺ (free aquo) | 1.961e-5 | 1.961e-8 |
| [Cu(OH)₂]⁰ | 7.56e-8 | 7.56e-11 |
| [Cu(OH)]⁺ | 1.51e-6 | 1.51e-9 |
| all other Cu(II) hydroxo species | < 1e-10 | < 1e-13 |

**Answer to the brief:** free [Cu²⁺] ≈ **1.96 × 10⁻⁸ M**, i.e. a fraction ≈ **2.0 × 10⁻⁵** (~20 ppm) of the 1 mM total copper. The dominant Cu-containing species at pH 7 is the neutral bis-glycinate complex **[Cu(Gly)₂]⁰ (98.5 %)**, with the mono-glycinate **[Cu(Gly)]⁺ (1.5 %)** as the only other non-trace form.

## Analysis
At pH 7 the glycine buffer is almost entirely in the zwitterionic HGlycine form: the reference card gives log β for H + Gly⁻ ⇌ HGly of +9.57 and for 2H + Gly⁻ ⇌ H₂Gly⁺ of +11.90 (so the α-COOH pKa ≈ 11.90 − 9.57 ≈ 2.33 and the α-NH₃⁺ pKa ≈ 9.57). At pH 7 the CSV shows [HGly] = 3.00 mM and [Gly⁻] = 1.32 × 10⁻⁵ M — the free amino-anion fraction is only ~10⁻⁽⁹·⁵⁷⁻⁷⁾ ≈ 3 × 10⁻³ of the free ligand pool. Even so, this tiny free-Gly⁻ activity is enough to drive Cu²⁺ complexation because the SRD-46 formation constants are large: log β₁ = 8.19 for Cu²⁺ + Gly⁻ ⇌ [Cu(Gly)]⁺ and log β₂ = 15.10 for Cu²⁺ + 2 Gly⁻ ⇌ [Cu(Gly)₂]⁰. With ~5-fold ligand excess, virtually all Cu is pulled into the bis-chelate.

A quick check reproduces the CSV: β₂ [Cu²⁺][Gly⁻]² = 10^15.10 · (1.96e-8)(1.32e-5)² ≈ 1.0 × 10⁻³ M, which matches the tabulated [Cu(Gly)₂]⁰ = 9.85 × 10⁻⁴ M and confirms the mass-balance solution. The mono-complex fraction is [Cu(Gly)]⁺/[Cu(Gly)₂]⁰ = β₁[Cu²⁺][Gly⁻]/β₂[Cu²⁺][Gly⁻]² = 10^(8.19−15.10)/[Gly⁻] ≈ 10⁻⁶·⁹¹ / 1.32 × 10⁻⁵ ≈ 9 × 10⁻³, matching the 1.5 % observed at slightly less-than-saturating [Gly⁻].

Why hydroxo species are absent at pH 7: pure Cu(II) hydrolysis begins to matter only near log β([Cu(OH)]⁺) = −7.90 (first hydrolysis pKa ≈ 7.9) and Cu(OH)₂(s) precipitates around pH 10 (Ksp for [Cu(OH)₂](s) with log β = −8.68 and CuO(s) with log β = −7.65 in the H⁺ basis). The glycinate chelate ring (5-membered NH₂–CH₂–COO⁻ with Cu²⁺) is so much more stable than the aqua/hydroxo complexes at these concentrations that it outcompetes hydrolysis by ~5 orders of magnitude in fractional occupancy at pH 7. This is exactly why glycine (and other α-amino acids) are effective Cu(II) buffers/chelators in the neutral pH range used in biochemistry: they keep the toxic free [Cu²⁺] well below 10⁻⁷ M while keeping the copper soluble as a neutral complex.

Dominance regions from the verdict confirm the pH 7 result sits inside the wide 5.2–10.4 window in which [Cu(Gly)₂]⁰ is the dominant Cu species; free Cu²⁺ dominates only below pH 4.0, the mono-glycinate briefly between pH 4.0 and 5.2, and precipitated CuO(s) above pH 10.4. All 81 sweep points converged, so the numeric answer is well-supported.

**Bottom line:** at pH 7, 25 °C, I = 0.1 M with 1 mM Cu(II) and 5 mM glycine, free [Cu²⁺] ≈ 2.0 × 10⁻⁸ M (~2 × 10⁻⁵ of total Cu); >98 % of the copper is sequestered as neutral [Cu(Gly)₂]⁰, with [Cu(Gly)]⁺ contributing the remaining ~1.5 %.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_Cu.json>)
- [verdict.json](<verdict.json>)
