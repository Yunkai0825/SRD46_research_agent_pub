## Doability
Doable as a pH speciation, but the specific ternary target species Ni(Gly)(NH3)+ is not represented in the SRD-46 catalog used by the pipeline, so its abundance can only be reported as effectively 0% within this model — not as a positive quantitative prediction.

## Result
System: Ni(II) 1.00 mM + glycine 5.00 mM + ammonia 5.00 mM, 25 °C, target I = 0.1 M (fixed-I mode; computed I stays in the 1.7–4.0 mM range because no inert electrolyte was added). Method: pH_sweep from pH 6.0 to 10.0, 41 points, redox excluded (only Ni(II) present as a metal component). Convergence: 41/41 samples converged for every element channel. Included aqueous nickel species (from the LC2 free-energy card): Ni2+, hydroxo Ni(OH)+, Ni(OH)2, Ni(OH)3-, Ni4(OH)4(4+); glycinate Ni(Glyc)+, Ni(Glyc)2, Ni(Glyc)3-; ammine Ni(Ammo)_n^{2+} for n = 1–6; plus Ni(OH)2(s). No mixed-ligand (ternary) Ni–glycinate–ammine species is present in the card.

## Analysis
**Ni(II) speciation at pH 8.0** (fractions of total Ni, from the frac_metal CSV):

| Species | Fraction at pH 8.0 |
|---|---:|
| [Ni(Glyc)2] (neutral bis-glycinate) | 62.27 % |
| [Ni(Glyc)3]- | 25.06 % |
| [Ni(Glyc)]+ | 12.11 % |
| Ni2+ (aquo) | 0.49 % |
| [Ni(Ammo)]2+ | 0.068 % |
| [Ni(Ammo)2]2+ | 2.6e-3 % |
| [Ni(OH)]+ | 1.2e-3 % |
| [Ni(OH)2] (aq) | 3.0e-4 % |
| all higher Ni–ammine (n ≥ 3) | < 1e-7 % |
| Ni(OH)2(s) | not saturated (0) |

The sum of the three Ni–glycinate complexes accounts for **99.4 %** of dissolved Ni at pH 8; ammine binding is essentially invisible; hydrolysis is negligible and no Ni(OH)2 precipitates.

**Why glycinate wins, and ammonia loses, at pH 8.** Glycine is a chelating N,O bidentate whose amine pKa is 9.57 (log β for HGlycine in the reference table). At pH 8 about 6.5 % of total glycine is present as the free glycinate anion L1(-) — small in fraction but ample in absolute terms (~3.3e-4 M), and each binding step is worth log K1 = 5.74, K2 = 4.84, K3 = 3.52 (from the cumulative log β values 5.74, 10.58, 14.10). Ammonia, in contrast, has pKa(NH4+) = 9.26, so at pH 8 only ~5 % of the ammonia pool is the reactive NH3 (~2.5e-4 M free). Its stepwise Ni–ammine constants are also weaker per donor (log K1 = 2.73, K2 = 2.16, K3 = 1.65, …), and — critically — ammonia is monodentate: it cannot chelate. The bidentate chelate effect plus the somewhat larger stepwise constants let glycinate outcompete ammonia by many orders of magnitude even though the two ligands have equal analytical totals. That is why at pH 8 the coordination sphere is essentially filled by two glycinates (Ni(Gly)2 dominant, 62 %), with tris-glycinate already rising (25 %) and mono-glycinate the third significant form (12 %). The crossover Ni(Glyc)2 ↔ Ni(Glyc)3- lies at pH ≈ 8.48, so pH 8 sits just inside the bis-glycinate plateau.

**The ternary Ni(Gly)(NH3)+ species.** The SRD-46 catalog compiled into this run's free-energy card does **not** contain any mixed-ligand Ni–glycinate–ammine complex (see the 'Free-Energy Species Table' in the verdict and the deterministic reference-constants table: every Ni complex listed contains L1 only or L2 only, never both). Consequently the computed abundance of Ni(Gly)(NH3)+ is exactly 0 % of total Ni — not because the model predicts it to be absent thermodynamically, but because the required formation constant is not in the underlying database and the species is therefore excluded from the equilibrium set.

This is a real limitation of the answer: literature values (e.g. Sigel, Martell) put log K for Ni2+ + Gly- + NH3 ⇌ Ni(Gly)(NH3)+ in the range 3–4, which under the present conditions would place a few-percent ternary population near pH 8 at the expense of Ni(Glyc)+ and, to a lesser extent, Ni(Glyc)2. Quantifying that would require adding the ternary log β to the LC2 card and rerunning; the current pipeline, faithful to SRD-46, cannot supply that value.

**Bottom line at pH 8.0, I = 0.1 M target, 25 °C:** Ni(II) speciation is dominated by Ni(glycinate)2 (62 %), with Ni(glycinate)3- (25 %) and Ni(glycinate)+ (12 %) making up nearly all of the balance; free Ni2+ is 0.5 %; ammine and hydroxo species are ≤0.07 %; no solid forms; and the mixed-ligand Ni(Gly)(NH3)+ complex requested by the task is not in the SRD-46 model and returns 0 % by construction.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_envelope_L2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_envelope_L2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_L2.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_L2.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_+_Ammonia_Ni.json>)
- [verdict.json](<verdict.json>)
