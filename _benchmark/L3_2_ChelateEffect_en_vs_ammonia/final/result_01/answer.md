## Doability
Doable: Ni(II) and ethylenediamine (en) are both in the SRD-46 catalog, and a 1-D pH speciation at fixed T, I, and totals is the native pH_sweep route.

## Result
System: Ni(II) 1.00 mM + ethylenediamine 10.0 mM, T = 25.0 °C, I = 0.1 M (fixed), pH 6.5–7.5 in 11 samples (redox excluded, so only Ni(+2) is populated). Convergence: 11/11 samples. Included species cover Ni2+, mono/bis/tris-en complexes, hydrolysis monomers [Ni(OH)]+, [Ni(OH)2], [Ni(OH)3]−, the tetranuclear [Ni4(OH)4]4+, solid Ni(OH)2, and the two protonated en forms; ligand protonation constants (from the reference table, cumulative in the card convention) are log β(HL+) = +9.92 and log β(H2L2+) = +17.03, so the effective pKa's of en are ≈9.92 (HL+ ↔ L) and ≈7.11 (H2L2+ ↔ HL+). Formation constants used: log β1 = +7.30, log β2 = +13.44, log β3 = +17.51 for [Ni(en)n]2+.

## Analysis
At pH 7.00 the solved aqueous concentrations (concentrations.csv) are:
- Free Ni2+ = 2.87 × 10⁻⁶ M (≈0.29 % of total Ni)
- [Ni(en)2]2+ = 7.87 × 10⁻⁴ M (≈78.7 % — dominant)
- [Ni(en)]2+ = 1.81 × 10⁻⁴ M (≈18.1 %)
- [Ni(en)3]2+ = 2.92 × 10⁻⁵ M (≈2.9 %)
- All hydrolysis species ≤ 7 × 10⁻¹⁰ M; Ni(OH)2(s) is undersaturated (0 mol/L in every row), so no precipitation.

So at pH 7 the answer to the brief is unambiguous: **free Ni2+ is suppressed to ~3 µM (three orders of magnitude below the 1 mM total), and the dominant Ni-containing species is [Ni(en)2]2+**, with [Ni(en)]2+ as the main minor form.

Chemically, this is the chelate effect in action. At pH 7, the free-en fraction is tiny — the verdict's ligand ladder shows H2en2+ still dominant (with HEn+ crossing over only near pH 7.4) and [en]free ≈ 3.15 × 10⁻⁶ M — yet Ni(II) is almost fully complexed. Each en bite delivers two donors per ligand association event, so β2 = 10¹³·⁴⁴ is enormous relative to what two monodentate amines would give, and the equilibrium tolerates a very low free-ligand activity. Formally, at [en] ≈ 3.15 µM, β2·[en]² ≈ 10¹³·⁴⁴ × (3.15 × 10⁻⁶)² ≈ 2.7 × 10², i.e. [Ni(en)2]2+/Ni2+ ≈ 270, matching the CSV ratio 7.87 × 10⁻⁴ / 2.87 × 10⁻⁶ ≈ 274.

Why bis- and not tris-en at pH 7? The stepwise K3/K2 for en on Ni(II) is small (log K3 = 17.51 − 13.44 = 4.07 vs log K2 = 13.44 − 7.30 = 6.14), and building [Ni(en)3]2+ requires a third free en, which the acidic H2en2+ reservoir has not yet released at pH 7. The verdict's crossovers confirm this: [Ni(en)]2+ ↔ [Ni(en)2]2+ near pH 6.63 (each ~48 %) marks where the second en outcompetes water on Ni; [Ni(en)3]2+ ↔ [Ni(en)]2+ near pH 7.25 shows tris-en only starts to matter as HEn+/en grow toward pH 7.5. Across the full window [Ni(en)2]2+ peaks at 84.2 % at pH 7.3 — pH 7 sits on its rising edge.

Hydrolysis is chemically irrelevant here: at 1 mM Ni2+ the onset of Ni(OH)2(s) and of [Ni(OH)]+ lies well above pH 7.5, and en outcompetes OH− for the coordination sphere long before that. Practically, this is why en (and polyamines generally) are used as Ni(II) masking/buffering ligands near neutral pH: a 10:1 en:Ni ratio at pH 7 pins free [Ni2+] in the low-µM range without needing a solid to form.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ethylenediamine_Ni.json>)
- [verdict.json](<verdict.json>)
