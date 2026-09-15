## Doability
Doable. Zn(II) + EDTA is a canonical SRD-46 system; a pH sweep at fixed I with redox excluded is directly supported by the pH_sweep route.

## Result
System: Zn$^{2+}$ (1.00 mM total) + EDTA (3.00 mM total, 3:1 excess), redox excluded, T = 25.0 °C, I = 0.1 M (fixed), pH 2.0–12.0, 101 grid points. Converged: 101/101 samples. Included aqueous Zn species: Zn$^{2+}$, [Zn(OH)]$^+$, [Zn(OH)$_2$]$^0$, [Zn(OH)$_3$]$^-$, [Zn(OH)$_4$]$^{2-}$, [Zn(EDTA)H$_2$]$^0$, [Zn(EDTA)H]$^-$, [Zn(EDTA)]$^{2-}$, [Zn(EDTA)(OH)]$^{3-}$; solid Zn(OH)$_2$(α) and ZnO are catalog-included but never precipitate along the sweep (fraction = 0 at every point in `*_frac_metal.csv`).

## Analysis
**Zn distribution.** With EDTA in 3-fold excess and the SRD-46 constants supplied by the card (log β for [Zn(EDTA)]$^{2-}$ = +16.5, for [Zn(EDTA)H]$^-$ = +19.5, for [Zn(EDTA)H$_2$] = +18.3, and for the ternary hydroxo complex [Zn(EDTA)(OH)]$^{3-}$ = +28.1 — the latter combining Zn$^{2+}$ + EDTA$^{4-}$ + OH$^-$), the solver assigns the mixed hydroxo complex [Zn(EDTA)(OH)]$^{3-}$ as the dominant Zn form over the full pH 2–12 window (fraction ≈ 1.000 at every grid point in `*_frac_metal.csv`; the verdict lists a single dominance interval 2.0–12.0 → [Zn(EDTA)(OH)]$^{3-}$ with a peak of 100.0 % at pH 11.2). This reflects the very large tabulated log β for the ternary complex: at pH ≥ 2 the reservoir of EDTA and the sequestration of Zn are already essentially complete, and adding OH$^-$ to form [Zn(EDTA)(OH)]$^{3-}$ is thermodynamically downhill (μ°_canon = −40.98 kJ/mol, the most negative product potential in the table). The consequence is the practically relevant one: **Zn is quantitatively bound to EDTA across the whole pH range**, including at the boiler-water target pH 8.5.

**Bound fraction and free [Zn$^{2+}$] at pH 8.5.** From `*_concentrations.csv` at pH 8.5:
- [Zn(EDTA)(OH)]$^{3-}$ = 1.000 × 10$^{-3}$ M ⇒ Zn-bound fraction = 1.000 (i.e. 100 % within solver precision; the summed [Zn(EDTA)H$_2$] + [Zn(EDTA)H]$^-$ + [Zn(EDTA)]$^{2-}$ + [Zn(EDTA)(OH)]$^{3-}$ ≈ 1.00 × 10$^{-3}$ M vs. 1.00 × 10$^{-3}$ M total).
- Free [Zn$^{2+}$] = 1.15 × 10$^{-35}$ M.
- Free hydrolysis products at pH 8.5: [Zn(OH)]$^+$ = 1.12 × 10$^{-36}$ M, [Zn(OH)$_2$]$^0$ = 1.12 × 10$^{-34}$ M — all >30 orders of magnitude below the EDTA-bound pool. Ca$^{2+}$/Mg$^{2+}$ hardness competition is not modelled here, but the residual free Zn$^{2+}$ is so vanishing that any realistic hardness-competition penalty still leaves EDTA gripping Zn effectively.

**Precipitation windows.** The two catalog solids — Zn(OH)$_2$(α) (dissolution log K = −10.72) and ZnO (dissolution log K = −9.61) — remain undersaturated at every pH from 2 to 12 (their columns in `*_frac_metal.csv` and `*_concentrations.csv` are 0.000e+00 throughout). No metallic Zn(0) forms because redox is excluded. Similarly, the card contains no solid Zn-EDTA phase, so the Zn-EDTA family stays entirely aqueous. **No precipitation window is predicted across pH 2–12** at 1 mM Zn / 3 mM EDTA / I = 0.1 M; the EDTA excess suppresses free Zn$^{2+}$ far below any hydroxide-solubility ceiling.

**EDTA ligand ladder and crossovers.** The pH-driven changes visible in the sweep are on the *ligand* side, not the metal side. The verdict's ligand-basis dominance intervals are:
- pH 2.0 – 2.3 → [Zn(EDTA)(OH)]$^{3-}$ (Zn-bound EDTA dominates the ligand pool at the acidic end because 3 mM EDTA is only slightly super-stoichiometric to 1 mM Zn, and the tiny Zn-bound share pulls above the highly protonated free-EDTA forms present as a mix).
- pH 2.3 – 5.6 → H$_2$EDTA$^{2-}$ (free-ligand pool dominated by the doubly-deprotonated form; peaks 64.2 % at pH 3.8).
- pH 5.6 – 9.4 → HEDTA$^{3-}$ (peaks 65.0 % at pH 7.4).
- pH 9.4 – 12.0 → EDTA$^{4-}$ (peaks 66.5 % at pH 12.0).

These crossovers (bracketed by adjacent grid samples at Δ pH = 0.1) trace the successive deprotonations of the free EDTA excess: the H$_2$EDTA$^{2-}$ ↔ HEDTA$^{3-}$ swap near pH 5.6, and HEDTA$^{3-}$ ↔ EDTA$^{4-}$ near pH 9.4, are the practically observable acid–base events in this pot. They correspond, per the reference-constants table, to the last two cumulative protonation constants of EDTA (log β for H$_x$L with x = 2 → 1: 16.38 → 10.19, giving stepwise pKa ≈ 6.19; x = 1 → 0: 10.19 → 0, giving stepwise pKa ≈ 10.19 — both consistent with the observed crossovers under the card's I = 0.1 M convention).

**Practical read-out for boiler-water screening.** At pH 8.5, I = 0.1 M, 25 °C:
- Zn-bound fraction ≈ 1.000 (100 %).
- Free [Zn$^{2+}$] ≈ 10$^{-35}$ M — hardness-scale-forming free Zn$^{2+}$ is thermodynamically eliminated by 3× EDTA excess.
- No Zn(OH)$_2$ or ZnO precipitation risk anywhere in pH 2–12 with this EDTA loading.
- The free-EDTA excess is present predominantly as HEDTA$^{3-}$ at pH 8.5 (≈ 1.74 mM out of 2.00 mM free-EDTA excess), which is the form that would compete for Ca$^{2+}$/Mg$^{2+}$ hardness in a real feedwater — a competition this single-metal calculation does not resolve and that a follow-up Ca–Mg–Zn–EDTA joint sweep would be needed to quantify.

**Caveat on constants used.** All quoted equilibrium constants come from the LC2 free-energy card projected in `LC2/thermodynamic_reference_constants.md`; the extreme dominance of [Zn(EDTA)(OH)]$^{3-}$ is a direct consequence of its tabulated log β = +28.1 (SRD-46) and would shift if a different source's ternary-hydroxo constant were used. The bound-fraction and no-precipitation conclusions, however, are robust to this because even the non-hydroxo [Zn(EDTA)]$^{2-}$ (log β = +16.5) alone would keep >99.99 % of Zn bound at 3× excess.

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
- [solver/topology_Zn$+2_+_Zn$+0_+_EDTA_Zn.json](<solver/topology_Zn$+2_+_Zn$+0_+_EDTA_Zn.json>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_concentrations.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_concentrations.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_L1.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_L1.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_Zn$+2.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_Zn$+2.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_L1.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_L1.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_ligand.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_ligand.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_metal.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_metal.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_Zn.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Zn.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_run_params.json](<solver/Zn$+2_+_Zn$+0_+_EDTA_run_params.json>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_state_metrics.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_state_metrics.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_verdict.md](<solver/Zn$+2_+_Zn$+0_+_EDTA_verdict.md>)
- [verdict.json](<verdict.json>)
