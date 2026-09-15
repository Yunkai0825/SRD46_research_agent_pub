## Doability
Doable — Ni(II) + EDTA is a canonical SRD-46 metal–ligand system and a 1‑D pH sweep at fixed I and redox‑off is exactly what the pipeline supports.

## Result
- System: 1.00 mM Ni(II) + 5.00 mM EDTA (5× excess ligand), 25 °C, fixed ionic strength I = 0.1 M, redox excluded (only Ni(+2) carries a non‑zero total among Ni(0/+2/+3/+4)).
- Method: `pH_sweep`, pH 2.0 → 12.0, 101 points.
- Convergence: 101/101 samples converged for every component (Ni, EDTA). No solid phase forms: [Ni(OH)2](s) column is 0.000e+00 M across the whole scan (the excess EDTA holds Ni in solution well below the Ksp condition).
- Included Ni forms (all aqueous): Ni2+, [Ni(OH)]+, [Ni(OH)2]°, [Ni(OH)3]−, [Ni4(OH)4]4+, [Ni(EDTA)H]−, [Ni(EDTA)]2−, [Ni(EDTA)(OH)]3−, plus [Ni(OH)2](s) (never precipitates here).

## Analysis
**Ni distribution.** The verdict is unambiguous and holds over the entire pH window: the mixed hydroxo–EDTA complex **[Ni(EDTA)(OH)]3− is the sole dominant Ni(II) species from pH 2.0 to 12.0** (peak 100.0% at pH 2.0, dominant pH 2.0–12.0). The concentrations CSV confirms [Ni(EDTA)(OH)]3− = 1.000e−03 M at every pH sampled, i.e. it consumes essentially all of the 1 mM Ni total. All other Ni forms are trace: at pH 7.0 the CSV gives [Ni(EDTA)]2− = 2.87e−23 M, [Ni(EDTA)H]− = 1.35e−27 M, [Ni(OH)]+ = 1.75e−39 M, [Ni4(OH)4]4+ ≈ 1.4e−140 M.

**Free [Ni2+] at pH 7 (deliverable).** From the concentrations table at pH = 7.000:

- **[Ni2+]_free ≈ 7.18 × 10⁻³⁶ M** (7.175e−36 M).

This is the equilibrium free aquated Ni(II) concentration — the quantity used in metal‑selectivity matrices. It is astronomically small because EDTA is in 5× excess and the mixed hydroxo–EDTA complex has an extremely large stability (see below).

**Why one Ni complex dominates the entire pH axis.** The thermodynamic reference table lists three Ni–EDTA complexes with cumulative log β from free components (Ni2+, EDTA4−, OH−, H+):

- [Ni(EDTA)H]−: log β = +21.50 (protonated complex)
- [Ni(EDTA)]2−: log β = +18.40 (parent chelate)
- [Ni(EDTA)(OH)]3−: log β = +30.30 (mixed hydroxo complex)

The card's [Ni(EDTA)(OH)]3− formation constant (log β = 30.3, i.e. Ni2+ + EDTA4− + OH− → [Ni(EDTA)(OH)]3−) is so large that even at pH 2, where [OH−] ≈ 10⁻¹² M, the OH‑containing form still out‑competes the parent [Ni(EDTA)]2− (log β = 18.4) by ~12 orders of magnitude in the corresponding mass‑action ratio, and at high pH it is favoured even more strongly. As a result, none of the usual crossovers between Ni2+, [Ni(EDTA)H]−, [Ni(EDTA)]2−, and Ni‑hydroxo species ever occur in this window: the mixed hydroxo–EDTA chelate binds Ni essentially quantitatively from acid to base and no Ni2+ is ever liberated. This is the chemical reason the free‑Ni number at pH 7 is ~10⁻³⁶ M rather than the ~10⁻¹⁷–10⁻¹⁸ M commonly tabulated from the parent [Ni(EDTA)]2− constant alone.

**EDTA (ligand) side.** With Ni tied up as a 1:1 chelate, only ~1 mM of the 5 mM EDTA total is bound to metal; the remaining ~4 mM behaves as free EDTA and follows its own acid–base ladder. The verdict's ligand‑side crossovers are the classical EDTA protonation sequence:

- H3EDTA− dominant pH 2.0–2.1
- H2EDTA2− dominant pH 2.1–5.6 (peak 77.1% at pH 3.8)
- HEDTA3− dominant pH 5.6–8.7 (peak 75.8% at pH 7.1)
- EDTA4− dominant pH 8.7–12.0 (peak 80.0% at pH 12.0)

Each dominance switch is bracketed by neighbouring grid samples (Δ = 0.1 pH). The switches at ~pH 2.1, ~5.6, and ~8.7 correspond, respectively, to the deprotonations H3EDTA−/H2EDTA2−, H2EDTA2−/HEDTA3−, and HEDTA3−/EDTA4−. Using the reference table's cumulative log β values (H+ + EDTA4− → HEDTA3− log β = 9.52; H2EDTA2− log β = 15.71; H3EDTA− log β = 18.23), the stepwise conjugate‑acid pKa's implied are pKa(HEDTA3−) ≈ 9.52, pKa(H2EDTA2−) ≈ 15.71 − 9.52 ≈ 6.19, and pKa(H3EDTA−) ≈ 18.23 − 15.71 ≈ 2.52, in agreement with the observed HEDTA3−↔EDTA4− and H2EDTA2−↔HEDTA3− crossovers around pH 8.7 and 5.6.

**Practical implications for the selectivity matrix.** At pH 7, I = 0.1 M, 25 °C, with a 5× EDTA excess:
- Free [Ni2+] ≈ 7 × 10⁻³⁶ M — for all practical purposes, EDTA fully masks Ni(II).
- The masking species predicted by this card is the mixed hydroxo–EDTA chelate [Ni(EDTA)(OH)]3−, not the more commonly cited [Ni(EDTA)]2−. If the selectivity matrix compares Ni to metals whose SRD‑46 cards do NOT include an analogous M(EDTA)(OH) form, the comparison should note this asymmetry — the Ni number here is a lower bound on free [Ni2+] set by the presence of the OH‑adduct term in the Ni card.
- No Ni(OH)2(s) precipitates anywhere in 2 ≤ pH ≤ 12 under these totals, so free‑Ni suppression is a solubility‑stable prediction, not an artefact of an ignored solid.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_EDTA_Ni.json>)
- [verdict.json](<verdict.json>)
