## Doability
Doable. Well-posed pH_sweep for Fe(III)+citrate at fixed totals, T, I with redox excluded; solver converged at 101/101 grid points from pH 2 to 12.

## Result
- System: 1.00 mM Fe(III) + 3.00 mM citric acid (L:M = 3), 25 °C, I = 0.1 M (fixed), redox excluded.
- Method: pH_sweep, 101 points over pH 2.0–12.0. Convergence 101/101.
- Solid phases considered (LC2 card): α-hematite [(Fe2O3)0.5(s,α)] (dissolution log β = +0.70), α-FeOOH (goethite, log β = −0.50), crystalline Fe(OH)3(s) (log β = −3.20), amorphous Fe(OH)3 hydr. (log β = −4.84).
- Precipitation window: α-Fe2O3 (hematite) present across the entire pH 2–12 range; it is the sole solid selected at every point (peak 100.0% at pH 8.9; already 98.4% of total Fe at pH 2.0).

## Analysis
**Metal-bound (Fe–citrate) fraction at pH 8.5.** Summing the four Fe-citrate aqueous species in the `frac_metal` table at pH 8.5:

- [Fe(Citr)H]+: 6.98e−24
- [Fe(Citr)]: 1.53e−16
- [Fe(Citr)(OH)]−: 1.58e−10 (largest)
- [Fe2(Citr)2(OH)2]2−: 1.35e−18

Total Fe-citrate fraction ≈ 1.58e−10 of total Fe. In absolute terms, Σ[Fe–citrate] ≈ 1.6e−13 M — effectively zero. Free [Fe3+] fraction is 2.76e−23, i.e. [Fe3+]_free ≈ 2.8e−26 M. Hematite accounts for essentially 100.000% of the Fe inventory (fraction = 1.0000 to five decimals at pH 8.5).

**Why citrate loses.** Citrate is a strong Fe(III) chelator — the card lists log β([Fe(Citr)H]+) = +12.35, log β([Fe(Citr)]) = +11.19, and a mixed hydroxo complex log β([Fe(Citr)(OH)]−) = +8.49 — and in a citrate-only aqueous model these species would dominate above pH ~3. But the card also includes the crystalline ferric oxide α-Fe2O3, whose dissolution log β of +0.70 (per ½Fe2O3, i.e. Fe3+ + 3 H+ ⇌ ½Fe2O3(s) with log β = +0.70) makes hematite extraordinarily insoluble. At any pH above ~1.5, µ° of hematite lies far below that of every dissolved Fe species, including all citrate complexes at 3 mM ligand. The solver therefore assigns nearly all Fe to hematite from pH 2 upward. Citrate does deprotonate along the expected ladder (H3Cit → H2Cit− at pH ≈ 2.7, → HCit2− at pH ≈ 4.0, → Cit3− at pH ≈ 5.1) — but the free trianion at pH 8.5 sees a residual free-Fe3+ activity of 10−25.6, far too low to nucleate soluble complexes.

**Crossover along pH.** There is no metal-side crossover: hematite is the dominant Fe form over the entire 2–12 window (the verdict reports a single interval "pH 2.0–12.0 → [(Fe2O3)0.5(s,α)]"). Among the trace dissolved Fe, [Fe(Citr)(OH)]− is the leading aqueous Fe form from ~pH 4 up (peaks near pH 3–4 at ~1.2% of total Fe before the hematite fraction climbs to unity), and [Fe(OH)4]− is the leading dissolved species only above pH ≳ 10, but its fraction remains 10−9 or lower.

**Practical (boiler-water) implication.** For antiscale screening this is the key negative result: at 3:1 citrate:Fe(III), 1 mM Fe(III), 25 °C and I = 0.1 M, citrate does **not** hold Fe(III) in solution at pH 8.5. Thermodynamics predicts >99.999999% precipitation as ferric oxide, with the Fe(III)-bound (chelated) fraction on the order of 10−10 and free [Fe3+] on the order of 10−26 M. To keep Fe(III) soluble at boiler pH the model card would need either (i) a much stronger chelator (EDTA, DTPA, NTA, phosphonates), (ii) far higher citrate excess (still bounded by hematite stability — citrate cannot in principle beat log β ≈ 0.7 hematite at millimolar Fe), or (iii) suppression of the crystalline oxide (kinetic barrier; then amorphous Fe(OH)3, log β = −4.84, becomes the relevant solid and citrate begins to compete). Caveats: the calculation is at 25 °C, not boiler temperature — hematite becomes more stable at higher T, so the practical picture at operating temperature is at least as unfavourable for citrate. Ionic strength was fixed at 0.1 M and the calculated I stayed in 2.7e−4 – 1.4e−2 M, well within the fixed-I assumption. Redox was excluded as requested; adding Fe(II) chemistry under reducing boiler conditions would change the accessible speciation.

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
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_concentrations.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_concentrations.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_Fe$+3.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_Fe$+3.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_L1.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_envelope_L1.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_Fe.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_Fe.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_L1.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_L1.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_ligand.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_ligand.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_metal.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_frac_metal.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_log_conc.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_phase_balance_Fe.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_phase_balance_Fe.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_run_params.json](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_run_params.json>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_state_metrics.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_state_metrics.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_verdict.md](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_verdict.md>)
- [solver/topology_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_Fe.json](<solver/topology_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_Citric_acid_Fe.json>)
- [verdict.json](<verdict.json>)
