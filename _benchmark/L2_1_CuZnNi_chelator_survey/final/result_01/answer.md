## Doability
Doable. Cu(II), Ni(II), Zn(II) and EDTA are all in the SRD-46 catalog with the requisite hydrolysis and ternary M(EDTA)(OH) species; a 1-D pH_sweep at fixed T = 25 °C and I = 0.1 M is the correct method.

## Result
Single joint pot: [Cu(II)]_T = [Ni(II)]_T = [Zn(II)]_T = 1.00 mM, [EDTA]_T = 5.00 mM (2.5-fold molar excess over Σmetal), 25 °C, I = 0.1 M, redox excluded. 21/21 pH samples converged over pH 6.0–8.0. Ionic strength stayed 0.0212–0.0228 M (below the 0.1 M target because chelated complexes dominate the charge budget). Artifacts: fraction CSVs for each metal, `_log_conc.csv` (used for the free-ion ratios below), and the verdict.

## Analysis
**Speciation is trivially simple: one complex per metal.** Across the entire pH 6.0–8.0 window the deterministic verdict reports

- Cu(II) → **[Cu(EDTA)(OH)]³⁻** (peak 100.0% at pH 7.0, dominant 6.0–8.0)
- Zn(II) → **[Zn(EDTA)(OH)]³⁻** (peak 100.0% at pH 7.0, dominant 6.0–8.0)
- Ni(II) → **[Ni(EDTA)(OH)]³⁻** (peak 100.0% at pH 7.8, dominant 6.0–8.0)
- Free EDTA is dominated by **HEDTA³⁻** (peak 39.0% at pH 7.4); each of the three ternary M(EDTA)(OH) complexes takes exactly 20.0% of total ligand (3 × 20% = 60% of L1 bound, matching Σmetal/L_T = 3/5).

The hexadentate EDTA cage plus one hydroxide co-ligand is thermodynamically decisive: the reference table gives log β for [M(EDTA)(OH)]³⁻ of **+30.18 (Cu), +30.30 (Ni), +28.10 (Zn)** — all far larger than the corresponding hydrolysis constants ([Cu(OH)]⁺ log β = -7.9; [Ni(OH)]⁺ -10.4; [Zn(OH)]⁺ -9.3) and larger than the simple [M(EDTA)]²⁻ chelates (+18.78 Cu, +18.40 Ni, +16.50 Zn). With ligand in 2.5× excess and every metal ≥98% chelated, no metal hydrolysis, and no oxide/hydroxide precipitation, is signalled anywhere across pH 6–8 (all solid-phase columns are at the -50 log floor).

**Free [M²⁺] and the selectivity ratios (from `_log_conc.csv`):**

| pH | log[Cu²⁺] | log[Ni²⁺] | log[Zn²⁺] | [Zn²⁺]/[Cu²⁺] | [Ni²⁺]/[Cu²⁺] |
|----|-----------|-----------|-----------|---------------|----------------|
| 6.0 | −31.95 | −32.07 | −29.87 | 10^{+2.08} ≈ 1.2×10² | 10^{−0.12} ≈ 0.76 |
| 7.0 | −34.06 | −34.18 | −31.98 | 10^{+2.08} ≈ 1.2×10² | 10^{−0.12} ≈ 0.76 |
| 8.0 | −36.06 | −36.18 | −33.98 | 10^{+2.08} ≈ 1.2×10² | 10^{−0.12} ≈ 0.76 |

The absolute free-metal levels are astronomically small (10⁻³² – 10⁻³⁶ M) and drop by two decades per pH unit — the classic slope of a chelated M(EDTA)(OH)³⁻ equilibrium (release of one H⁺ from the coordinated water and of the ligand protons). But the *ratios* are essentially pH-independent because all three metals ride the same HEDTA³⁻/OH⁻ pool.

**Selectivity verdict — Cu vs Zn vs Ni is poor.**

- **Cu vs Zn:** Cu²⁺ is held ~120× more tightly than Zn²⁺ (Δlog β for [M(EDTA)(OH)]³⁻ = 30.18 − 28.10 = 2.08, exactly reproduced by the ratio). ~2 log units is real but modest — EDTA leaves ~10⁻³⁰ M free Zn²⁺ against ~10⁻³² M free Cu²⁺; both metals are effectively fully sequestered.  In a *competition* sense EDTA is not Cu-selective over Zn — it merely binds Cu a bit more strongly, and with the 2.5× ligand excess both metals go to essentially 100% complex regardless.
- **Cu vs Ni:** Δlog β = 30.18 − 30.30 = −0.12, i.e. Ni is actually bound *very slightly more strongly* than Cu (free [Ni²⁺] is ~0.76× free [Cu²⁺]). EDTA does **not** discriminate Cu from Ni; they are indistinguishable at the ~0.1 log-unit level.

**Practical implication.** In this joint aqueous pot EDTA is a saturating, non-selective sequestering agent for all three divalent metals across pH 6–8: every metal is >99.99…% locked into its own ternary M(EDTA)(OH)³⁻ complex, no precipitation occurs, and the residual free-ion pools differ only by a factor of ~10² (Cu vs Zn) or ~0.8 (Cu vs Ni). EDTA cannot be used to fish Cu(II) out of a Zn/Ni background at near-neutral pH — a differentiation of ≤2 log β is far too small when the ligand is in excess. A truly Cu-selective strategy needs either (i) a Cu-preferring soft-donor ligand (e.g. bipyridyl/imidazole scaffolds that exploit Cu(II)'s Jahn–Teller preference), (ii) sub-stoichiometric EDTA combined with a pH low enough that Zn/Ni are partly displaced (below pH 6, HEDTA³⁻ collapses to H₂EDTA²⁻/H₃EDTA⁻ and the Δlog β pattern begins to matter more), or (iii) redox-based separation (Cu(I) chemistry), none of which is available in this equilibrium calculation.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_Ni$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_Ni$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_Zn$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_envelope_Zn$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_Ni.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_Ni.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_frac_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Ni.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Ni.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_EDTA_Cu.json>)
- [verdict.json](<verdict.json>)
