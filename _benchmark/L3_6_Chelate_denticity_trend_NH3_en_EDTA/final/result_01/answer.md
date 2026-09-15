## Doability
Doable — Ni(II) and NH3 are both in the SRD-46 catalog, and a fixed-pH speciation at pH 7 is directly read from a pH_sweep (21/21 samples converged).

## Result
System: Ni(II) 1.0 mM + NH3 (total) 60 mM, 25 °C, I = 0.1 M (fixed), redox excluded (Ni^0/+3/+4 totals = 0). Method: 1-D pH_sweep from pH 6.0 to 8.0 (21 points, all converged). Ionic strength stayed within 0.029–0.032 M (below the 0.1 M target, since the only ions here are Ni^2+ and small amounts of NH4+/OH- charge carriers; no inert electrolyte was added). No precipitation at pH 7 (Ni(OH)2(s) only appears from pH 7.6 upward).

At pH 7.0:
- Free [Ni^2+] = 8.44 × 10^-4 M (i.e. 84.4% of total Ni is still the aquo ion).
- [Ni(NH3)]^2+ = 1.48 × 10^-4 M (14.8%).
- [Ni(NH3)2]^2+ = 7.01 × 10^-6 M (0.70%).
- Higher ammine complexes ([Ni(NH3)3]^2+ through [Ni(NH3)6]^2+) are all ≤10^-7 M (<0.02% each).
- Hydrolysis products ([Ni(OH)]+, [Ni(OH)2]°, [Ni4(OH)4]^4+) are all ≤10^-7 M and negligible.
- Free (unprotonated) NH3 = 3.27 × 10^-4 M; the ligand is 99.5% present as NH4+ (HAmmonia+ = 5.95 × 10^-2 M).

Dominant Ni-containing species at pH 7: free Ni^2+(aq).

## Analysis
Ammonia is a weak base (conjugate-acid pKa ≈ 9.26, from the tabulated log β = +9.26 for H+ + NH3 ⇌ NH4+). At pH 7 the solution is ~2.3 pH units below that pKa, so only ~5 × 10^-3 of the 60 mM ammonia inventory exists as the coordinating free-base form NH3 — about 3.3 × 10^-4 M. That is the effective ligand concentration a Ni^2+ ion actually sees.

With only sub-millimolar free NH3 available, the ammine-complexation ladder barely gets off the ground. The stepwise K1 for Ni^2+ + NH3 ⇌ [Ni(NH3)]^2+ is 10^2.73 ≈ 540, so [Ni(NH3)]^2+/[Ni^2+] ≈ K1·[NH3] ≈ 540 × 3.3 × 10^-4 ≈ 0.18 — exactly the ratio observed in the CSV (1.48e-4/8.44e-4 = 0.175). Successive additions of NH3 need K_n·[NH3] products, and with [NH3] < 10^-3 M each further step costs another factor of ~0.05–0.1, so the higher ammines drop off geometrically and [Ni(NH3)6]^2+ is essentially absent (2 × 10^-16 M). Hydrolysis is likewise suppressed: at pH 7 [OH-] ≈ 10^-7 M and the first hydrolysis constant is log β = -10.4, giving [Ni(OH)]+/[Ni^2+] ≈ 10^-3.4, again matching the tabulated 2.1e-7/8.4e-4.

The practical consequence for a chelate-effect comparison is that a 60-fold molar excess of a monodentate ligand like ammonia at physiological pH is very inefficient at sequestering Ni^2+: 84% of the metal remains as the free aquo ion, and pNi = -log[Ni^2+] ≈ 3.07 (barely above pNi = 3 for the ligand-free reference of 1 mM Ni^2+). A polydentate chelator (EDTA, en, cyclam, …) at the same total concentration would drive [Ni^2+] many orders of magnitude lower because (i) it does not lose most of its donor inventory to protonation, and (ii) its formation constant is not built up multiplicatively from small NH3 activities but delivered in one entropically favoured binding event — this is precisely the chelate effect the comparison is designed to expose.

Crossover behaviour outside pH 7 (for context): the [Ni(NH3)]^2+ vs Ni^2+ crossover only occurs near pH 7.78 (each ~24%) — i.e. one needs to push pH close to the NH3 pKa before mono-ammine even ties with the aquo ion — and by pH 7.60 solid Ni(OH)2 already starts to precipitate, so the ammine ladder is truncated by hydroxide competition before the higher complexes can become important at this 60 mM ammonia loading. At pH 7 itself the system is safely undersaturated with respect to Ni(OH)2(s).

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
