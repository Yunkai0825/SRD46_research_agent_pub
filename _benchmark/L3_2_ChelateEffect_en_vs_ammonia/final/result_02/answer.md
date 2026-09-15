## Doability
Doable: Ni(II) + NH3 speciation over pH 6.5–7.5 at fixed I=0.1 M, 25 °C is squarely in scope; SRD-46 supplies the six Ni(NH3)n^2+ cumulative constants, Ni hydrolysis (mono-, di-, tri-hydroxo, tetranuclear) and Ni(OH)2(s).

## Result
System: 1.00 mM Ni(II) total + 20.0 mM ammonia total, T = 25.0 °C, ionic mode fixed (target I = 0.1 M; solver-reported I = 0.0117–0.0120 M, i.e. activity corrections applied to the target). pH sweep 6.5–7.5, 21 points, 21/21 converged. Redox excluded (only Ni$+2 subtotal non-zero). Ni(OH)2(s) was included as a possible solid but its fraction is 0 over the whole window — no precipitation. NH3(aq) is essentially fully protonated (HAmmonia+ = 99.7% of L1 at pH 6.5), so the free-ligand NH3 concentration is very small.

## Analysis
At pH 7.00 the metal fraction table gives:
- Ni2+ (free, aquo) = 0.9437 → [Ni2+] = 9.44 × 10^-4 M
- [Ni(NH3)]2+ = 5.52 × 10^-2 → 5.52 × 10^-5 M
- [Ni(NH3)2]2+ = 8.70 × 10^-4 → 8.70 × 10^-7 M
- [Ni(NH3)3]2+ = 4.24 × 10^-6 → 4.24 × 10^-9 M
- [Ni(NH3)4]2+ = 6.23 × 10^-9 → negligible
- [Ni(NH3)5]2+, [Ni(NH3)6]2+ = 3 × 10^-12, 3 × 10^-16 → negligible
- Hydroxo: [Ni(OH)]+ = 2.30 × 10^-4 (2.30 × 10^-7 M); [Ni(OH)2](aq), [Ni4(OH)4]4+, HNiO2- all ≤ 10^-5 fraction.

Across the whole pH 6.5–7.5 window Ni2+ stays dominant (98.2% → 83.9%); the only species that grows appreciably is the 1:1 monoammine [Ni(NH3)]2+ (1.83% at pH 6.5 → 15.3% at pH 7.5). Higher ammines never break 1% because the free NH3 concentration is limited: at pH 7 with pKa(NH4+) = 9.26 (log β for H+ + NH3 → NH4+ in the reference table), the neutral-NH3 fraction of total ammonia is only ~10^-2.26 ≈ 0.55%, giving [NH3] ≈ 1.1 × 10^-4 M. Populating [Ni(NH3)n]2+ requires [NH3]^n, so β2·[NH3]^2 ≈ 10^4.89·(1.1e-4)^2 ≈ 9 × 10^-4, β4·[NH3]^4 ≈ 10^7.67·(1.1e-4)^4 ≈ 6 × 10^-9 — matching the tabulated shares and explaining why the ammine ladder essentially stops at n=1.

Comparison to the ethylenediamine case (10 mM en, free [Ni2+] ≈ 2.87 × 10^-6 M): with twice as much total nitrogen donor (20 mM NH3 vs 20 mM N as 10 mM en), ammonia leaves free [Ni2+] ≈ 9.44 × 10^-4 M — about 330× higher, i.e. the chelate effect suppresses free Ni2+ by roughly 2.5 orders of magnitude at pH 7. Two chemical reasons combine: (i) en is a much stronger base per donor site only modestly (pKa ≈ 7 and 10 for enH2^2+/enH+/en), but crucially the neutral-donor fraction near pH 7 is dramatically larger for en than for NH3 (pKa 9.26), so more ligand is actually available in binding form; and (ii) each en molecule delivers two nitrogens in one entropy-cheap chelate ring, so Ni(en)3^2+ (log β3 ~18) forms readily whereas Ni(NH3)6^2+ (log β6 = 8.30) requires binding six independent ligands and never accumulates at these totals. The consequence here is that with monodentate NH3 at pH 7, essentially all the nickel is still the labile hexaaquo ion — only ~5.6% is complexed, mostly as [Ni(NH3)]2+ — while the analogous en system converts ~99.7% of Ni into tris(en) chelate. Ni(OH)2(s) is undersaturated throughout (aqueous [Ni2+] ≈ 10^-3 M with pH ≤ 7.5 keeps IP·(H+)^-2 below Ksp), consistent with the solid fraction staying at zero.

Practically: 20 mM ammonia at pH 7 is a poor masking / complexing environment for Ni(II); to buffer free Ni2+ to sub-µM levels with NH3 one must raise pH well above the ammonium pKa (≥ 9–10) to liberate free NH3, or switch to a chelate such as en.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Ammonia_Ni.json>)
- [verdict.json](<verdict.json>)
