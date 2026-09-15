## Doability
Doable. Fe(III) + EDTA speciation with SRD-46 constants for Fe(OH)x, Fe-EDTA (Fe(EDTA)-, Fe(EDTA)(OH)2-, Fe(EDTA)H), and FeO(OH)(s,alpha) is well within scope for a pH_sweep at fixed I and T.

## Result
- System: Fe(III) 1.00 mM + EDTA 3.00 mM (3:1 ligand excess), 25 °C, fixed I = 0.1 M, pH 2.0–12.0 (101 points).
- Method: 1-D pH_sweep, redox excluded (Fe3+ only).
- Convergence: 101/101 samples converged over the full pH grid.
- Ionic-strength check: calculated I stayed within 0.00223–0.02398 M against the 0.10 M target (the fixed-I option pins activity corrections to 0.1 M; deviations are cosmetic, not a solver failure).
- Precipitation onset: FeO(OH)(s, α-goethite) first appears at pH 7.80 (1.14e-4 M) and grows to dominate the Fe balance above ~pH 8.1.

## Analysis
**Dominant Fe(III) speciation vs pH** (from the verdict's Fe$+3 ladder):
- pH 2.0–7.0: [Fe(EDTA)]- (peaks at 100.0% at pH 2.7).
- pH 7.0–8.1: [Fe(EDTA)(OH)]2- (peaks 84.5% at pH 7.7).
- pH 8.1–12.0: FeO(OH)(s,α) (reaches 100% at pH 11.8).
- Grid-bracketed crossovers: [Fe(EDTA)]- ↔ [Fe(EDTA)(OH)]2- at pH ≈ 6.96; [Fe(EDTA)(OH)]2- ↔ FeO(OH)(s) at pH ≈ 8.07 (each ~48%).

**At pH 8.5 (the target row from the concentrations CSV):**
- [Fe(EDTA)]- = 5.367e-6 M
- [Fe(EDTA)(OH)]2- = 1.851e-4 M
- [Fe(EDTA)H] ≈ 5.2e-16 M (negligible; this protonated adduct only matters below pH ~3)
- Σ Fe–EDTA (aq) = 1.905e-4 M → **metal-bound fraction = 19.0% of the 1.00 mM Fe total.**
- FeO(OH)(s,α) = 8.095e-4 M → 80.9% of Fe has precipitated as goethite.
- Free [Fe3+] = **4.38e-25 M** (aquo ion, uncomplexed and unhydrolyzed).
- All Fe(III) hydrolysis species combined (Fe(OH)2+, Fe(OH)2+, Fe(OH)4−, Fe2(OH)2 4+, Fe3(OH)4 5+) sum to ~4e-13 M — vanishingly small next to the EDTA complexes and the solid.

**Chemistry driving these numbers.** EDTA is an extraordinarily strong hexadentate chelator for Fe(III): the reference table gives log β(Fe(EDTA)−) = +25.10 and log β(Fe(EDTA)(OH)2−) = +17.71 (mixed hydroxo–chelate). Between pH 2 and 7 the free ligand is present mostly as H2EDTA2- then HEDTA3-, but the huge Fe(III) affinity still pulls essentially all Fe into [Fe(EDTA)]-, so the aquo Fe3+ activity is driven to sub-attomolar levels even at low pH. Near neutral pH one coordinated water on the chelate deprotonates to give the mixed hydroxo complex [Fe(EDTA)(OH)]2-; the [Fe(EDTA)]- ↔ [Fe(EDTA)(OH)]2- crossover at pH ≈ 6.96 is the effective pKa of that bound water (~7.0), consistent with the tabulated log β difference (25.10 − 17.71 = 7.39, close to log Kw + hydrolysis balance).

Above pH ~7.8 the hydroxide activity is finally high enough that even a 25-log-unit chelate cannot outcompete goethite precipitation (FeO(OH)(s,α), log β for dissolution −0.5). Because the free ligand is in only 3-fold excess and much of it is tied up as HEDTA3-/H2EDTA2- rather than fully deprotonated EDTA4-, the mass-balance no longer favors the chelate: goethite takes over at pH 8.07 and by pH 8.5 already holds ~81% of the iron.

**Practical implication for boiler-water antiscale screening at pH 8.5.** With a 3:1 EDTA:Fe(III) ratio, EDTA sequesters only ~19% of the Fe(III) at pH 8.5 and cannot suppress iron-oxide/oxyhydroxide scale — 4/5 of the iron drops out as α-FeOOH. Free Fe3+ is 4.4e-25 M, which is chemically irrelevant (it is set by the FeOOH solubility, not by "unprotected" iron), but the operationally important quantity is the ~810 μM ferric oxyhydroxide precipitate. To keep Fe(III) in solution as [Fe(EDTA)(OH)]2- at pH 8.5 the ligand:metal ratio must be raised substantially (or pH lowered), because at this pH the free EDTA4- activity is still low (HEDTA3- is the dominant free-ligand form, ~2.45 mM out of 3 mM total) and the mixed hydroxo chelate cannot compete with goethite at only a 3:1 stoichiometric excess.

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
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_concentrations.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_concentrations.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_envelope_Fe$+3.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_envelope_Fe$+3.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_envelope_L1.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_envelope_L1.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_Fe.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_Fe.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_L1.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_L1.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_ligand.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_ligand.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_metal.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_frac_metal.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_log_conc.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_log_conc.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_log_conc.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_log_conc.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_phase_balance_Fe.png](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_phase_balance_Fe.png>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_run_params.json](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_run_params.json>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_state_metrics.csv](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_state_metrics.csv>)
- [solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_verdict.md](<solver/Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_verdict.md>)
- [solver/topology_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_Fe.json](<solver/topology_Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_EDTA_Fe.json>)
- [verdict.json](<verdict.json>)
