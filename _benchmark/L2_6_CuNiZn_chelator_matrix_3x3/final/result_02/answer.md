## Doability
Doable. Cu(II) + EDTA is a canonical speciation system fully supported by SRD-46 and solved as a 1-D pH sweep at fixed I=0.1 M, T=25 °C.

## Result
**System:** 1.00 mM Cu(II) (Cu$^{+2}$ total) + 5.00 mM EDTA (L1), 25.0 °C, fixed ionic strength I = 0.1 M (calculated I range 0.008 – 0.036 M), no redox coupling (Cu(0) and Cu(I) totals set to 0; the corresponding Cu(I)/Cu(0) subsystems are inert).
**Method:** `pH_sweep`, pH 2.0 – 12.0, 51 grid points.
**Convergence:** 51/51 samples converged (100 %). Values quoted below are read directly from `..._frac_metal.csv` and `..._concentrations.csv` at pH 7.0.

## Analysis
**Dominant Cu-containing species at pH 7 (and across the full 2–12 window):** `[Cu(EDTA)(OH)]³⁻` — 100.0 % of the Cu(II) budget (the solver verdict lists the peak as 100 % at pH 9.4 and a single dominance interval pH 2.0 – 12.0 → `[Cu(EDTA)(OH)]³⁻`). The subordinate Cu-EDTA forms at pH 7.0 are `[Cu(EDTA)]²⁻` (fraction ≈ 9.1 × 10⁻²⁰), `[Cu(EDTA)H]⁻` (≈ 4.3 × 10⁻²⁴) and `[Cu(EDTA)H₂]` (≈ 2.6 × 10⁻²⁹). All Cu-hydroxo and Cu-oxide species without EDTA are at ≤ 10⁻³⁴ level, and every solid Cu phase (`Cu(OH)₂(s)`, `CuO(s)`, `Cu₂O`, `Cu(s)`) is exactly zero — the system is undersaturated with respect to every solid because virtually all Cu is chelated.

**Free [Cu²⁺] at pH 7.0:** fraction 4.35 × 10⁻³² of a 1.00 × 10⁻³ M total ⇒ **[Cu²⁺]_free ≈ 4.4 × 10⁻³⁵ M**. This is an extraordinarily low residual and reflects the SRD-46 constants for the mixed hydroxo-EDTA complex.

**Why the hydroxo-chelate wins everywhere.** The SRD-46 free-component formation constants supplied in the reference-constants table are
- `[Cu(EDTA)]²⁻` : log β = +18.78 (Cu²⁺ + EDTA⁴⁻)
- `[Cu(EDTA)(OH)]³⁻` : log β = +30.18 (Cu²⁺ + OH⁻ + EDTA⁴⁻).

The ratio [Cu(EDTA)(OH)³⁻] / [Cu(EDTA)²⁻] = K·[OH⁻] with log K = 30.18 − 18.78 = 11.40, i.e. the mixed hydroxo form takes over the simple chelate once [OH⁻] > 10⁻¹¹·⁴ (pH ≳ 2.6). Combined with the very large absolute stability of the chelate (log β_CuL = 18.78) and the 5-fold ligand excess, the two effects together drive essentially the entire Cu inventory into `[Cu(EDTA)(OH)]³⁻` over the whole pH window scanned, so no crossover between Cu-species is reported.

**EDTA acid–base biography (independent view).** The free-ligand pool (4 mM of the 5 mM total is uncomplexed) undergoes the expected protonation ladder: `H₂EDTA²⁻` dominates pH 2.2 – 5.6, `HEDTA³⁻` dominates pH 5.6 – 9.4 (peak 78.0 % at pH 7.4, consistent with the stepwise pK ≈ 6.19 implied by log β(HEDTA³⁻) = 10.19 vs log β(H₂EDTA²⁻) = 16.38), and `EDTA⁴⁻` dominates above pH 9.4. At pH 7, `HEDTA³⁻` is already the majority protonation form of the free ligand — but the small α₄ (fraction of L⁴⁻ ≈ 10⁻³) is more than compensated by the chelate stability, so complex formation is still complete.

**Practical implication.** With 5 mM EDTA at pH 7 and I = 0.1 M, Cu(II) is quantitatively sequestered; the free-ion concentration is many orders of magnitude below any biologically or environmentally meaningful threshold, and no copper solid can nucleate. The absence of any crossover in the Cu ladder means the sequestration is robust across the entire pH 2 – 12 window at this ligand-to-metal ratio; only reducing Cu(II) or destroying the EDTA ligand would release free Cu²⁺.

**Caveat on the SRD-46 log β for `[Cu(EDTA)(OH)]³⁻`.** The value log β = +30.18 (for Cu²⁺ + OH⁻ + EDTA⁴⁻) makes the mixed hydroxo form dominate at essentially all pH ≥ 3, and pushes the computed free [Cu²⁺] to ~10⁻³⁵ M — appreciably lower than the ~10⁻¹⁸ M usually quoted from the plain Cu-EDTA chelate alone at pH 7. Users who need the classical "chelate-only" free-Cu²⁺ estimate should compare the `[Cu(EDTA)]²⁻` mass (fraction 9.1 × 10⁻²⁰ here) with the mixed-hydroxo mass in this run.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_Cu.json>)
- [verdict.json](<verdict.json>)
