## Doability
Doable — Cd(II) and ammonia are in the SRD-46 catalog and a `pH_sweep` at fixed T and I with Cd(0) suppressed is directly supported.

## Result
System: Cd$^{2+}$ 1.00 mM + NH$_3$ 0.10 M total, T = 25 °C, I = 0.1 M (fixed), pH 2–12 in 0.1 unit steps, 101/101 samples converged, Cd(0) totals set to zero (redox excluded). Ammonia protonation pKa (card `log_beta` for H+ + NH$_3$ ⇌ NH$_4^+$) is +9.26, and cumulative Cd–amine formation constants are log β$_1$=2.57, log β$_2$=4.56, log β$_3$=5.90, log β$_4$=6.72. Cd(OH)$_2$(s,β) dissolution log K = −13.65 (from `LC2/thermodynamic_reference_constants.md`).

## Analysis
**Speciation at pH 7 (target).** From `solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_metal.csv` at pH 7.00 the Cd(II) mass balance is:

- free Cd$^{2+}$: 82.36% → [Cd$^{2+}$] = 8.24 × 10$^{-4}$ M
- [Cd(NH$_3$)]$^{2+}$: 16.69% → 1.67 × 10$^{-4}$ M
- [Cd(NH$_3$)$_2$]$^{2+}$: 0.890% → 8.90 × 10$^{-6}$ M
- [Cd(NH$_3$)$_3$]$^{2+}$: 1.06 × 10$^{-4}$ (fraction) → 1.06 × 10$^{-7}$ M
- [Cd(NH$_3$)$_4$]$^{2+}$: 3.83 × 10$^{-7}$ (fraction) → 3.83 × 10$^{-10}$ M
- [Cd(OH)]$^+$: 4.00 × 10$^{-4}$ (fraction) → 4.00 × 10$^{-7}$ M
- all higher hydroxo and polynuclear species: ≤ 10$^{-7}$ fraction
- no Cd(OH)$_2$(s) precipitation at pH 7 (saturation onset only at pH 9.9 per verdict)

So at pH 7 the Cd(II) budget is essentially free aquo Cd$^{2+}$ (82%) with a modest first-ammine complex (17%); higher ammine adducts and all hydroxo species are together <1%.

**Why ammonia is such a weak sequestrant at pH 7.** The controlling factor is the ammonia protonation equilibrium (pKa 9.26). At pH 7 the free-base fraction of the ligand is only 10$^{7-9.26}$ ≈ 0.55%, so of the 0.10 M ammonia total only ~5 × 10$^{-4}$ M is present as NH$_3$; the rest is spectator NH$_4^+$. Coupled with a modest log β$_1$ = 2.57, the effective binding per free Cd$^{2+}$ is K$_1$·[NH$_3$] ≈ 10$^{2.57}$·5 × 10$^{-4}$ ≈ 0.19, which reproduces the observed [Cd(NH$_3$)$^{2+}$]/[Cd$^{2+}$] ratio (0.167/0.824 = 0.20). Higher ammines require [NH$_3$]$^n$ and are quenched by the same protonation.

**Whole-sweep behaviour.** Free Cd$^{2+}$ is the dominant Cd species from pH 2 up to pH 7.8; only above the ligand pKa does enough free NH$_3$ appear to drive successive ammine formation: pH 7.8–8.4 [Cd(NH$_3$)]$^{2+}$, pH 8.4–9.3 [Cd(NH$_3$)$_2$]$^{2+}$, pH 9.3–10.1 [Cd(NH$_3$)$_3$]$^{2+}$ (peak 45.6% at pH 9.8), with [Cd(NH$_3$)$_4$]$^{2+}$ never dominant (peak 23.7% at pH 9.9). Above pH 10.1, precipitation of Cd(OH)$_2$(s,β) takes over (99.8% at pH 11.6), cutting the ammine ladder short before the tetraammine can win — consistent with the modest overall β$_4$ = 10$^{6.72}$ competing against a very insoluble hydroxide (log K$_{sp,diss}$ = −13.65). Hydroxo aqueous species ([Cd(OH)]$^+$, [Cd(OH)$_2$]$^0$, polynuclears) never accumulate meaningfully in this system.

**HSAB implication.** With 0.1 M ammonia (a borderline/hard N-donor, protonated at physiological pH), ~82% of Cd(II) remains as free aquo Cd$^{2+}$ at pH 7. Ammonia at neutral pH simply cannot sequester borderline-soft Cd(II) — both because its own basicity ties it up as NH$_4^+$ and because the individual Cd–N stepwise constants are only moderate. This provides the expected HSAB baseline: any soft base (e.g. Cl$^-$, or more dramatically thiolates) that suppresses free [Cd$^{2+}$] more strongly than ammonia at pH 7 confirms Cd(II)'s soft-side preference.

**Convergence.** 101/101 samples converged; calculated I range 9.6 × 10$^{-5}$ – 0.052 M stayed below the fixed 0.1 M target, so activity corrections used the declared 0.1 M throughout.

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
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_concentrations.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_concentrations.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_envelope_Cd$+2.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_envelope_Cd$+2.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_envelope_L1.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_envelope_L1.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_Cd.png](<solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_Cd.png>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_L1.png](<solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_L1.png>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_ligand.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_ligand.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_metal.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_frac_metal.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_log_conc.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_log_conc.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_log_conc.png](<solver/Cd$+2_+_Cd$+0_+_Ammonia_log_conc.png>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_phase_balance_Cd.png](<solver/Cd$+2_+_Cd$+0_+_Ammonia_phase_balance_Cd.png>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_run_params.json](<solver/Cd$+2_+_Cd$+0_+_Ammonia_run_params.json>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_state_metrics.csv](<solver/Cd$+2_+_Cd$+0_+_Ammonia_state_metrics.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Ammonia_verdict.md](<solver/Cd$+2_+_Cd$+0_+_Ammonia_verdict.md>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Ammonia_Cd.json](<solver/topology_Cd$+2_+_Cd$+0_+_Ammonia_Cd.json>)
- [verdict.json](<verdict.json>)
