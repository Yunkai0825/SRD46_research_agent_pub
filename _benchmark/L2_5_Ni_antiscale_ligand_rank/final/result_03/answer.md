## Doability
Doable — SRD-46 supplies Ni2+/NH3 mononuclear ammine complexes (β1–β6), Ni-hydroxo species, the Ni4(OH)4^4+ cluster, and Ni(OH)2(s); a fixed-I pH sweep 4–11 fits the pH_sweep method exactly.

## Result
- System: 1.00 mM Ni(II) + 10.0 mM total ammonia (NH3/NH4+), 25 °C, I = 0.1 M (fixed-ionic-strength mode; realised I range 8.9e-5 – 7.0e-3 M as neutral species dominate), pH 4.0–11.0, 71 grid points.
- Method: 1-D pH speciation with Ni(OH)2(s) allowed as a solid phase; redox excluded (Ni(II) only).
- Convergence: 71/71 samples converged.
- Precipitation onset: first sample carrying Ni(OH)2(s) is pH 7.50 (7.32e-05 M solid).
- Aqueous-ladder dominance (Ni basis): Ni2+ from pH 4.0 up to the crossover with Ni(OH)2(s) at pH ≈ 7.63 (each ~47%), then Ni(OH)2(s) to pH 11.

## Analysis
**Free [Ni2+] and dominant Ni form at pH 9.** From the metal fraction table (`*_frac_metal.csv`, row pH 9.000), the Ni distribution is:
- Ni(OH)2(s): fraction 0.99650 → 9.965e-04 M as solid
- Free Ni2+(aq): fraction 8.471e-04 → **[Ni2+] ≈ 8.5e-7 M** (about 0.085 % of Ni_total)
- [Ni(Ammo)]2+: 1.61e-03 fraction (1.6e-6 M); [Ni(Ammo)2]2+ 8.26e-04 (8.3e-7 M); higher ammines all ≤1e-7 M
- [Ni(OH)]+ 2.06e-05, [Ni(OH)2](aq) 5.18e-05, [Ni(OH)3]- 8.47e-07 fractions

So at pH 9 the dominant Ni sink is clearly **solid Ni(OH)2**, which sequesters ~99.65 % of the Ni; the residual dissolved Ni is only ~3.5 µM, and free aquo Ni2+ within that is ~0.85 µM.

**Why ammonia fails to suppress precipitation here.** Ammonia is a genuinely strong ligand for Ni(II) — the reference table gives cumulative log β1…β6 = 2.73, 4.89, 6.54, 7.67, 8.33, 8.30 for [Ni(NH3)n]2+ — but the *free* NH3 concentration at pH 9 is throttled by the ammonium acid–base equilibrium. Because NH4+ has pKa = 9.26 (from the LC2 card, single-protonation log β for H+ + NH3 ⇌ NH4+), at pH 9 the ligand ladder still has HNH3+ as majority (crossover to neutral NH3 at pH ≈ 9.3). Only ~35 % of the 10 mM total is present as free NH3, i.e. [NH3] ≈ 3.5e-3 M. To hold Ni as the hexammine, [Ni(NH3)6]2+/[Ni2+] = β6·[NH3]^6 ≈ 10^8.30·(3.5e-3)^6 ≈ 0.9 — i.e. the ammine complexes cannot outcompete hydroxide precipitation, and the calculation confirms this: the summed ammine fraction at pH 9 is only ~0.35 % of Ni, while Ni(OH)2(s) captures ~99.65 %.

**Crossover chemistry.** In the aqueous ladder alone Ni2+ hands over to Ni(OH)2(s) at pH ≈ 7.63 (each ~47 %) and to the ammine [Ni(Ammo)]2+ at pH ≈ 7.50 (each ~8 %). Precipitation is thus the controlling event from ~pH 7.5 upward; above pH ~8.5 more than 98 % of the Ni is already locked in the solid.

**Practical implication for scaling.** At pH 9 with 10:1 NH3:Ni, ammonia does **not** meaningfully suppress Ni(OH)2 scaling — free [Ni2+] drops to sub-µM levels precisely because Ni(OH)2(s) forms, not because ammine complexation holds Ni in solution. To keep Ni dissolved as ammine complexes one would need either substantially more ammonia (so that [NH3]_free rises well above ~10 mM, requiring total ammonia >>0.1 M at pH 9), or a higher pH where a larger share of the ammonia buffer is deprotonated — but going higher in pH also drives Ni(OH)2 harder, so the practical remedy is a much larger NH3 excess, not a pH shift.

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
