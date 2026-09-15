## Doability
Doable — Fe(III)/EDTA system with Fe(OH)3(s) allowed is fully within SRD-46 catalog and the pH_sweep method.

## Result
- System: Fe(III) 1.00 mM total, EDTA 5.00 mM total (5× ligand excess).
- Method: pH_sweep, pH 4.0–9.0, 51 points, T = 25 °C, fixed ionic strength target 0.1 M (calculated I = 0.0087–0.0296 M actual).
- Solids allowed: Fe(OH)3(s) (log K_s0 line: log β = −3.20 for Fe3+ + 3 OH− ⇌ Fe(OH)3(s)) and Fe(OH)2(s).
- Convergence: 51/51 grid points converged; redox excluded (Fe(III) locked).

## Analysis
Across the entire pH 4–9 window, essentially 100% of the iron is held in solution as Fe(III)–EDTA complexes; **Fe(OH)3(s) is never predicted to precipitate**. The verdict lists only two Fe(III) species reaching appreciable population:

- **[Fe(EDTA)]−** dominates from pH 4.0 to ~6.96, peaking at 99.9% at pH 4.0.
- **[Fe(EDTA)(OH)]2−** takes over above pH ≈ 6.96, peaking at 99.1% at pH 9.0.
- Crossover of the two Fe(EDTA) species is at **pH ≈ 6.96**, where each is ~50%.

No hydrolysis species (Fe(OH)2+, Fe(OH)2+, Fe2(OH)2 4+, Fe(OH)4−) and no Fe(OH)3(s) reach reporting significance — they are absent from the dominant-species and peak lists. Correspondingly, the Fe phase-balance stays entirely aqueous over pH 4–9, and **there is no pH within the scanned window at which Fe(OH)3(s) reappears**.

Chemically, this is exactly what the thermodynamic constants predict for 5× EDTA excess:
- The Fe(III)–EDTA complex is extraordinarily stable: log β([Fe(EDTA)]−) = +25.10 for Fe3+ + EDTA4− ⇌ [Fe(EDTA)]−. Even after paying the cost of deprotonating EDTA (cumulative protonation constants log β up to +20.25 for H4EDTA), the effective conditional stability at pH 4–7 remains far larger than the Fe(OH)3(s) solubility constraint (log K_s0 = −3.20). With 4 mM free-ligand headroom, Fe3+ activity is suppressed to well below the level needed to saturate Fe(OH)3(s).
- The pH ≈ 6.96 crossover reflects hydrolysis *of the complex*, not of free Fe3+. As pH rises, an axial water/OH− on the Fe(EDTA) chelate deprotonates: [Fe(EDTA)]− + OH− ⇌ [Fe(EDTA)(OH)]2−. From the card, log β([Fe(EDTA)(OH)]2−) = +17.71 versus log β([Fe(EDTA)]−) = +25.10, giving an effective hydrolysis constant of the complex of log K ≈ −7.39 (i.e. pK ≈ 7.0 for loss of one proton from a coordinated water), matching the observed crossover.
- On the ligand side (as reported in the EDTA speciation block), free-ligand protonation dominates: H2EDTA2− is the main free-ligand form up to pH 5.6, HEDTA3− from 5.6–8.7, and fully deprotonated EDTA4− only above pH 8.7. The Fe(EDTA) complexes carry only ~20% of total EDTA at each end of the range because ligand is in 5× excess; the remaining ~80% is free protonated ligand.

Practically: at 5:1 EDTA:Fe(III), Fe(III) is fully solubilized as chelate across the entire 4–9 pH band. To force Fe(OH)3(s) reappearance one would need to (a) reduce EDTA below stoichiometric, (b) push pH well above 9 into the [Fe(OH)4]− / [Fe(EDTA)(OH)]2− competition regime, or (c) introduce a competing metal that displaces Fe from EDTA. Within the requested window, **no precipitation pH exists**.

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
