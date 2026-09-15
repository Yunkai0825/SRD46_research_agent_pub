## Doability
Doable — Cu(I/II)-ammonia system with hydroxide/oxide solids is fully in SRD-46 scope; pH_sweep at fixed Eh is a supported mode.

## Result
- System: 1.00e-3 M Cu(total) + 0.100 M ammonia (NH3/NH4+), fixed Eh = +0.265 V vs SHE.
- Method: 1-D pH sweep (0–14, 141 points) at 25 °C, fixed I = 0.1 M.
- Convergence: 141/141 points converged.
- Solids kept: Cu2O (cuprite) and Cu(OH)2; CuO was excluded per the hydroxide-preference instruction; Cu(s) also carried but never precipitates at this Eh.
- Precipitation windows (from verdict): Cu2O present pH 5.30 → dissolves by pH 7.20; Cu(OH)2 present pH 10.30 → dissolves by pH 13.50.

## Analysis
**Ammonia backbone.** NH4+ dominates below pH ≈ 9.3 and NH3 above (crossover at the tabulated pKa log β = +9.26 for H+ + L ⇌ NH4+). So Cu(II)-ammine chemistry can only turn on once free NH3 becomes appreciable, i.e. above pH ≈ 7–8. Below that, ammonia is locked up as NH4+ and Cu behaves essentially as an aqua/hydroxo system.

**pH regions for Cu (from the verdict's dominant-species table):**
- pH 0.0–5.6: free **Cu2+** dominates (peak 98.7 % at pH 0). Free NH3 is ~10⁻⁹ M here, so aquo Cu²⁺ is the only relevant form; a small [Cu(NH3)]²⁺ shoulder peaks 9.8 % at pH 5.3.
- pH 5.6–7.0: **Cu2O(s)** precipitates. Note this is Cu(I) — at the fixed Eh = +0.265 V the Cu²⁺/Cu2O couple is thermodynamically favourable near neutral pH, and hydrolysis of Cu²⁺ + partial reduction stabilises cuprite. Cu2O peaks at 72 % of total Cu at pH 6.2 (crossover Cu²⁺↔Cu2O at pH ≈ 5.51).
- pH 7.0–8.2: soluble **[Cu(NH3)2]+** (Cu(I) diammine) takes over as Cu2O redissolves. Its log β = +9.92 combined with rising [NH3] pulls Cu(I) back into solution; it peaks 65.4 % at pH 7.2 (Cu2O↔[Cu(NH3)2]+ crossover at pH ≈ 6.93).
- pH 8.2–8.3: narrow **[Cu(NH3)3]²+** window (peak 32.7 % at pH 8.2) — the Cu(II) ammine ladder switches on as free NH3 grows and starts to out-compete Cu(I) diammine oxidatively (fixed Eh now favours Cu(II) once strong Cu(II)-selective ligand is available).
- pH 8.3–10.5: **[Cu(NH3)4]²+** dominates, peaking 90.8 % at pH 10.2. This is the classic deep-blue tetraammine; log β4 = +12.3 is the largest Cu(II)-ammine constant and, with [NH3] now ~0.1 M, it swamps hydrolysis.
- pH 10.5–13.4: **Cu(OH)2(s)** precipitates (peak 99.5 % at pH 11.7). Above pH ≈ 10.5, OH⁻ outcompetes NH3 for Cu(II) (the ammine ladder saturates at 4 NH3, while OH⁻ activity grows another two decades), and the tetraammine is displaced by the hydroxide solid — [Cu(NH3)4]²+↔Cu(OH)2 crossover at pH ≈ 10.45.
- pH 13.4–14.0: **CuO2²⁻** (cuprate) dominates as Cu(OH)2 redissolves amphoterically; HCuO2⁻ is a minor co-species peaking 13.9 % at pH 13.5.

**Practical readings.**
- The Cu(I) window (Cu2O + [Cu(NH3)2]+) between pH ≈ 5.5 and 8.2 is entirely a consequence of the fixed Eh: +0.265 V sits close to the Cu²⁺/Cu2O and Cu(NH3)2+/Cu(NH3)4²+ boundaries, so the system parks in Cu(I) exactly where free NH3 first appears but is still scarce.
- The famous "deep-blue ammonia solution" behaviour ([Cu(NH3)4]²+) is only stable between pH ≈ 8.3 and 10.5 here; more acidic solutions lose NH3 to protonation and more basic solutions lose Cu to Cu(OH)2.
- Total dissolved Cu is suppressed by two precipitation windows (5.3–7.2 and 10.3–13.5); if the goal is to keep Cu in solution as the tetraammine, working near pH 9.5–10.3 with excess NH3 is optimal.
- Ionic-strength self-consistency: calculated I ranged 5.5e-5 – 0.052 M against the 0.1 M target, i.e. the fixed-I assumption is a mild upper bound at high pH and slightly overestimated at low pH, but does not change the qualitative ordering.

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
- [solver/Cu_+_Ammonia_concentrations.csv](<solver/Cu_+_Ammonia_concentrations.csv>)
- [solver/Cu_+_Ammonia_envelope_Cu.csv](<solver/Cu_+_Ammonia_envelope_Cu.csv>)
- [solver/Cu_+_Ammonia_envelope_L1.csv](<solver/Cu_+_Ammonia_envelope_L1.csv>)
- [solver/Cu_+_Ammonia_frac_Cu.png](<solver/Cu_+_Ammonia_frac_Cu.png>)
- [solver/Cu_+_Ammonia_frac_L1.png](<solver/Cu_+_Ammonia_frac_L1.png>)
- [solver/Cu_+_Ammonia_frac_ligand.csv](<solver/Cu_+_Ammonia_frac_ligand.csv>)
- [solver/Cu_+_Ammonia_frac_metal.csv](<solver/Cu_+_Ammonia_frac_metal.csv>)
- [solver/Cu_+_Ammonia_log_conc.csv](<solver/Cu_+_Ammonia_log_conc.csv>)
- [solver/Cu_+_Ammonia_log_conc.png](<solver/Cu_+_Ammonia_log_conc.png>)
- [solver/Cu_+_Ammonia_phase_balance_Cu.png](<solver/Cu_+_Ammonia_phase_balance_Cu.png>)
- [solver/Cu_+_Ammonia_run_params.json](<solver/Cu_+_Ammonia_run_params.json>)
- [solver/Cu_+_Ammonia_state_metrics.csv](<solver/Cu_+_Ammonia_state_metrics.csv>)
- [solver/Cu_+_Ammonia_verdict.md](<solver/Cu_+_Ammonia_verdict.md>)
- [solver/topology_Cu_+_Ammonia_Cu.json](<solver/topology_Cu_+_Ammonia_Cu.json>)
- [verdict.json](<verdict.json>)
