## Doability
Doable. Ca(II) + citric acid single-pot speciation over pH 2–12 at I = 0.1 M, 25 °C, redox excluded, is fully within the `pH_sweep` toolkit; the LC2 card carries Ca2+, Ca–OH, three Ca–citrate stepwise complexes, and three candidate solids (Ca(OH)2, CaH(Citr)(s), Ca3(Citr)2(s)).

## Result
- System: 1.00 mM Ca(II) + 3.00 mM citric acid (3:1 L:M), redox excluded.
- Method: 1-D pH_sweep, 101 grid points pH 2.0–12.0, T = 25 °C, fixed I = 0.1 M (calc. free ion strength 0.0023–0.0138 M — dominated by the imposed inert background, so activity corrections are consistent).
- Convergence: 101/101 samples converged (verdict `Converged: 101/101`).
- Precipitation: none. The three solid columns in `frac_metal.csv` — Ca(OH)2, [CaH(Citric acid)](s), [Ca3(Citric acid)2](s) — are identically zero at every pH sample, including pH 8.5. The system is undersaturated with respect to all three solids at these totals.
- Crossover between free Ca2+ and Ca–citrate complexes: **none exists in 2–12**. Free Ca2+ never drops below 68.7 % of Ca-total. Verdict lists `Dominant species by pH region: pH 2.0–12.0 → Ca2+` and `Crossover pH values:` (empty).

### Key values at pH 8.5 (from `frac_metal.csv`, row pH = 8.5000)
| Species | Fraction of Ca-total |
|---|---:|
| Ca2+ (free) | 0.71493 |
| [Ca(Citr)]− | 0.28505 |
| [Ca(Citr)H] | 1.03 × 10⁻⁵ |
| [Ca(OH)]+ | 1.26 × 10⁻⁵ |
| [Ca(Citr)H2]+ | 6.2 × 10⁻¹¹ |
| all Ca solids | 0 |

Derived: free [Ca2+] = 0.71493 × 1.00 mM = **7.15 × 10⁻⁴ M**; total Ca-bound-to-citrate (sum of the three aqueous Ca–citrate complexes) = **28.51 % ≈ 2.85 × 10⁻⁴ M**. Ligand budget: 2.85 × 10⁻⁴ M of the 3.00 mM citrate pool is tied up on Ca (≈ 9.5 % of the ligand, matching the ligand-side peak `[Ca(Citr)]- peak 9.5% at pH 9.1`).

## Analysis
**Why Ca2+ never loses dominance.** Citric acid is a triprotic acid whose fully deprotonated form Citr³⁻ is the good Ca binder; the reference-constants table lists log β₁₁₀([Ca(Citr)]−) = +3.45, with protonated variants at +7.72 (HCitr, β overall) and +11.00 (H2Citr, β overall). Converting to conditional formation from HCitr²⁻ and H2Citr⁻ using the citrate protonation β's (12.90, 10.00, 5.65) gives stepwise K's for Ca binding of only K(Ca–Citr³⁻) ≈ 10^3.45, K(Ca–HCitr²⁻) ≈ 10^2.07, K(Ca–H2Citr⁻) ≈ 10^1.00. With 3 mM citrate, [Citr³⁻] at pH 8.5 is essentially [L_total]·α₃ ≈ 3 mM (α₃ → 1 above the third pKa ≈ 5.65); the product K·[Citr³⁻] ≈ 10^3.45 × 3 × 10⁻³ ≈ 8.4, so ≈ 8.4/(1+8.4) ≈ 89 % Ca binding would be expected if activities were ideal. The solver returns only ≈ 28.5 %; the difference is the ionic-strength penalty at I = 0.1 M, which sharply reduces the effective +2/−3 pairing (Davies-type activity correction on the ×5 charge product). This is the quantitative reason citrate is a weak hardness sink under boiler-water ionic strength: even at 3-fold excess and pH well above the last pKa, ~72 % of the Ca still sits as free Ca2+.

**Ligand ladder read from the ligand table.** The citric-acid crossovers on the ligand side (H3 → H2⁻ at 2.7, H2⁻ → HCitr²⁻ at 4.0, HCitr²⁻ → Citr³⁻ at 5.1) match the tabulated protonation constants (log β_H3 = 12.90, β_H2 = 10.00, β_H1 = 5.65 → pKa1 ≈ 2.90, pKa2 ≈ 4.35, pKa3 ≈ 5.65) once ionic-strength corrections are applied, and by pH 8.5 the ligand is essentially fully Citr³⁻. So the *ligand* is fully activated at pH 8.5; what limits Ca binding is the intrinsic weakness of the Ca–citrate ion pair, not ligand availability.

**Minor species and hydrolysis.** [Ca(OH)]+ is negligible (≈ 10⁻⁵) at pH 8.5 and only becomes appreciable above pH ~11 (3.97 × 10⁻⁴ at pH 10.0, 3.83 × 10⁻² at pH 12.0), consistent with log β = −13.04 for Ca–OH. Ca(OH)2(s) never precipitates because [Ca2+] = 7 × 10⁻⁴ M and [OH⁻] at pH 8.5 (≈ 3 × 10⁻⁶ M) are far below the solubility product (dissolution log β = −22.89 → Ksp ≈ 10⁻⁵.4 as Ca²⁺·(OH⁻)² is not reached until pH ≳ 12 at millimolar Ca). The two solid Ca–citrates are similarly undersaturated at 1 mM Ca / 3 mM citrate.

**Boiler-water antiscale reading (hardness leg of the EDTA-vs-citrate screen).** At pH 8.5, citrate at 3× stoichiometric excess sequesters only ~28 % of a 1 mM Ca hardness load and leaves 0.72 mM free Ca2+. That is a poor hardness-masking performance and means most of the citrate charge (≈ 91 % of the ligand pool, 2.72 mM of the 3.00 mM) is *not* wasted on Ca and remains available for Fe(III). In other words, citrate's weakness toward Ca2+ is precisely the property that makes it attractive for the intended job of holding Fe(III) soluble: unlike EDTA, which binds Ca2+ almost quantitatively at this pH and squanders ligand on hardness, citrate preferentially routes its coordination capacity to hard-Lewis-acid Fe(III) and lets Ca2+ float free. The trade-off is that citrate provides essentially *no* hardness reduction — 72 % free Ca remains available to nucleate CaCO3 / CaSO4 scale — so a citrate-only formulation would still require a separate hardness control step. Conclusion for the screen: on the Ca-competition axis citrate wins vs EDTA by wasting less ligand, but it does not itself function as a hardness sequestrant at boiler pH.

**Caveats.** These fractions hold at the stated totals (1 mM Ca, 3 mM citrate), 25 °C, and I = 0.1 M; scaling to real boiler ionic strengths (often ≫ 0.1 M) will further weaken Ca–citrate ion pairing and push the bound fraction below 28 %. Boiler-relevant carbonate/sulfate ligands and elevated T were not modelled and could change the precipitation verdict for Ca.

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
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_concentrations.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_concentrations.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_envelope_Ca$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_envelope_Ca$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_envelope_L1.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_envelope_L1.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_L1.png](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_L1.png>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_ligand.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_ligand.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_metal.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_frac_metal.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_log_conc.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_log_conc.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_log_conc.png](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_log_conc.png>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_phase_balance_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_phase_balance_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_run_params.json](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_run_params.json>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_state_metrics.csv](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_state_metrics.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Citric_acid_verdict.md](<solver/Ca$+2_+_Ca$+0_+_Citric_acid_verdict.md>)
- [solver/topology_Ca$+2_+_Ca$+0_+_Citric_acid_Ca.json](<solver/topology_Ca$+2_+_Ca$+0_+_Citric_acid_Ca.json>)
- [verdict.json](<verdict.json>)
