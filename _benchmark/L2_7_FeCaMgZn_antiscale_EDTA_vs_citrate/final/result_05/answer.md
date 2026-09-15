## Doability
Doable. Mg(II) + EDTA is well within the SRD-46 catalog; a 1-D pH_sweep at fixed I and T is the correct method for this question.

## Result
- **System**: 1.00 mM Mg(II) + 3.00 mM EDTA (3:1 ligand:metal excess), Mg(0) redox-state subtotal = 0 (redox excluded).
- **Conditions** (from run verdict / run_params.json): T = 25.0 °C, fixed ionic strength I = 0.1 M (calculated I ranges 4.6e-3 – 1.80e-2 M within the pH sweep), pH 2.0–12.0 at 101 points.
- **Convergence**: 101/101 converged (state_metrics / verdict); every reported point is evidence.
- **Species set included**: aqueous Mg2+, [Mg(OH)]+, [Mg2(OH)]3+, [Mg4(OH)4]4+, [Mg(EDTA)H]-, [Mg(EDTA)]2-; the seven EDTA protonation states; and the brucite solid [Mg(OH)2(s)] as a dissolution equilibrium.

## Analysis

**Mg speciation across the sweep** (from `frac_metal.csv`; dominance labels from verdict):
- pH 2.0 – ~4.9: **Mg2+** dominant (0.9999 at pH 2, falling through 0.50 near the crossover).
- pH ~4.9 – 12.0: **[Mg(EDTA)]2-** dominant, rising past 90% by pH 5.6 and exceeding 99.9% by pH 8.
- Crossover Mg2+ ↔ [Mg(EDTA)]2- at **pH ≈ 4.91** (each ~49%). The protonated complex [Mg(EDTA)H]- is never dominant; it peaks around pH 4.7–4.8 at only ~2.3% of total Mg, then falls off as HEDTA3- deprotonates to EDTA4-.
- Hydroxo species ([Mg(OH)]+, [Mg2(OH)]3+, [Mg4(OH)4]4+) remain trace throughout (fractions < 1e-4 even at pH 12), because EDTA sequesters Mg long before Mg2+ hydrolysis becomes competitive (log β for [Mg(OH)]+ is only –11.4).

**At pH 8.5 (the antiscale target)** — read directly from `frac_metal.csv` and `log_conc.csv`:
- Fraction as **[Mg(EDTA)]2-**: 0.999886 (99.99%).
- Fraction as [Mg(EDTA)H]-: 1.18e-5.
- Fraction as free Mg2+: 1.026e-4 (~0.010%).
- Fractions as [Mg(OH)]+, [Mg2(OH)]3+, [Mg4(OH)4]4+: 7.9e-8, 2.2e-14, 1.5e-30 — negligible.
- **Mg-bound fraction (sum of all Mg–EDTA aqueous complexes)** = 0.999886 + 1.18e-5 ≈ **0.9999 (≈99.99%)**.
- **Free [Mg2+]** at pH 8.5: log c = –10.10, so [Mg2+] ≈ **7.9 × 10⁻¹¹ M** — ~7 orders of magnitude below the 1.00 mM total. That is the direct measure of hardness suppression by EDTA and confirms Mg(II) is essentially fully sequestered at boiler-water pH.

**Solid formation across the sweep**: the [Mg(OH)2(s,brucite)] column in `frac_metal.csv` is exactly 0 at every pH from 2 to 12; correspondingly its log_conc entry is pinned at –50 (the "excluded" floor). No precipitation window exists under these totals. Chemically, [Mg2+]_free at high pH is capped near ~4.2×10⁻⁵ M (the tail plateau of the free-Mg curve set by [Mg(EDTA)]2- ↔ EDTA4- equilibrium as [OH⁻] rises), which stays comfortably below the brucite saturation threshold at I = 0.1 M. So EDTA at 3:1 excess prevents Mg(OH)2 scale entirely across the sweep. (The Mg-EDTA fraction table also shows the ligand distribution: H4EDTA/H3EDTA- dominate below pH 2.1; H2EDTA2- from 2.1–5.6; HEDTA3- 5.6–8.7; EDTA4- above 8.7 — the ligand's transition to HEDTA3-/EDTA4- around pH 5–6 is what drives the sharp Mg2+ → [Mg(EDTA)]2- crossover in the same window.)

**Practical read for the antiscale screen**: at pH 8.5 with 3 mM EDTA vs 1 mM Mg, EDTA suppresses free Mg2+ to ~8×10⁻¹¹ M and ties up 99.99% of the total as [Mg(EDTA)]2-. Mg hardness is fully controlled; there is no Mg(OH)2 scale. The metric that matters for Fe(III)-vs-hardness selectivity is how much of the added EDTA is consumed by Mg: essentially 1 mM out of 3 mM (the EDTA fraction column shows [Mg(EDTA)]2- ≈ 33.3% of total EDTA at pH 10.2 peak), leaving ~2 mM of unbound EDTA available to chelate other cations. In a mixed hardness+Fe(III) matrix that free-ligand budget is what determines whether EDTA still preferentially binds Fe(III) or is exhausted by Ca/Mg/Zn competition — to be compared against the parallel Ca, Zn, and Fe(III) runs in this screen.

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
- [solver/Mg$+2_+_Mg$+0_+_EDTA_concentrations.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_concentrations.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_envelope_L1.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_envelope_L1.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_envelope_Mg$+2.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_envelope_Mg$+2.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_frac_L1.png](<solver/Mg$+2_+_Mg$+0_+_EDTA_frac_L1.png>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_frac_ligand.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_frac_ligand.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_frac_metal.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_frac_metal.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_frac_Mg.png](<solver/Mg$+2_+_Mg$+0_+_EDTA_frac_Mg.png>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_log_conc.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_log_conc.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_log_conc.png](<solver/Mg$+2_+_Mg$+0_+_EDTA_log_conc.png>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Mg.png](<solver/Mg$+2_+_Mg$+0_+_EDTA_phase_balance_Mg.png>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_run_params.json](<solver/Mg$+2_+_Mg$+0_+_EDTA_run_params.json>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_state_metrics.csv](<solver/Mg$+2_+_Mg$+0_+_EDTA_state_metrics.csv>)
- [solver/Mg$+2_+_Mg$+0_+_EDTA_verdict.md](<solver/Mg$+2_+_Mg$+0_+_EDTA_verdict.md>)
- [solver/topology_Mg$+2_+_Mg$+0_+_EDTA_Mg.json](<solver/topology_Mg$+2_+_Mg$+0_+_EDTA_Mg.json>)
- [verdict.json](<verdict.json>)
