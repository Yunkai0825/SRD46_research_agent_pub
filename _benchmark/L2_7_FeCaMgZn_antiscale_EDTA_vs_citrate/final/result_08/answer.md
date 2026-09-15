## Doability
Doable — Zn(II) + citrate system at fixed I = 0.1 M, 25 °C, redox excluded is a standard pH_sweep problem covered by the SRD-46 catalog (Zn2+, four Zn–hydroxo, three Zn–citrate mononuclear, one dinuclear Zn2(Citr)2(OH)2, ZnO/Zn(OH)2 solids).

## Result
- System: [Zn2+]_total = 1.00 mM, [citrate]_total = 3.00 mM (3:1 L:M), 25 °C, I = 0.1 M (fixed), pH 2.0–12.0, 101 samples, redox excluded.
- Convergence: 101/101 samples converged for both Zn and citrate sub-problems.
- Solids activated: ZnO (Atlas dissolution, log β = –9.61) precipitates at pH ≥ 7.10 (verdict flags onset 1.15×10⁻⁴ M at pH 7.10); Zn(OH)₂ (amorphous, log β = –12.25) never activates.

## Analysis
**Acidic regime (pH 2–4.4): free aquo Zn²⁺ dominates.** Citric acid is still largely protonated (H₃Cit dominates pH 2.0–2.7, then H₂Cit⁻ 2.7–4.0, HCit²⁻ 4.0–5.1; see verdict L1 block). With so little fully deprotonated citrate available, coordination to Zn²⁺ is weak: at pH 2.0 free Zn²⁺ = 99.9 % of total Zn, and even at pH 4.0 free Zn²⁺ is still 62.7 %. The protonated complex Zn(HCit) (log β = +8.62) reaches only 10.8 % at pH 3.9 — its narrow window reflects that H-Cit²⁻ is itself only transiently the majority ligand form.

**Mid-pH plateau (pH 4.4–7.0): mononuclear Zn–citrate takes over.** As HCit²⁻ hands off to Cit³⁻ around pH 5.1, the 1:1 chelate [Zn(Citr)]⁻ (log β = +4.77 on the fully deprotonated ligand) climbs to a peak of 54.6 % of Zn at pH 5.0 and dominates the aqueous ladder from pH 4.4 to 7.0. The bis-citrate [Zn(Citr)₂]⁴⁻ (log β = +6.80) rises in parallel because ligand is in threefold excess, peaking at 37.8 % near pH 6.2. The Zn²⁺ ↔ Zn(Citr)⁻ crossover is bracketed between pH 4.3 and 4.4 (≈ 4.35 at ~43 % each). This is the antiscale-relevant window where citrate genuinely sequesters Zn in solution.

**Above pH ~7: ZnO(s) removes Zn from solution.** Once ZnO becomes saturated at pH 7.10, the total soluble Zn drops sharply. The aqueous ladder shifts to the dinuclear hydroxo-citrate [Zn₂(Citr)₂(OH)₂]⁴⁻ (log β = –2.90 from Zn²⁺ + [H₋₁L]) — listed as dominant among *aqueous* Zn species from pH 7.0 to 12.0 with a peak of 36.8 % at pH 7.1 — but this only refers to the residual dissolved Zn. Most Zn(II) is now the solid oxide, driven by hydrolysis (log β(Zn(OH)₂,aq) = –15.8; log β(Zn(OH)₃⁻) = –28.1) overwhelming the citrate binding once Cit³⁻ has to compete with OH⁻ and the ZnO precipitation barrier.

**Precipitation window.** ZnO(s) is present from pH ≈ 7.1 upward through pH 12; below 7.1 the whole zinc pool stays dissolved. Amorphous Zn(OH)₂ is undersaturated over the entire scan and does not precipitate. So the practical antiscale window for keeping Zn dissolved on citrate alone is roughly pH 4.5–7.0.

**Snapshot at pH 8.5 (from the concentrations CSV).** Boiler-water pH sits well inside the ZnO precipitation regime:
- Free [Zn²⁺] = 6.71 × 10⁻⁸ M (≈ 67 nM). Free-Zn fraction of total Zn = 6.7 × 10⁻⁵ (0.0067 %).
- Aqueous Zn–citrate complexes: [Zn(Citr)⁻] = 6.17 × 10⁻⁷ M, [Zn(Citr)₂⁴⁻] = 8.68 × 10⁻⁷ M, [Zn₂(Citr)₂(OH)₂⁴⁻] = 7.11 × 10⁻⁷ M (contributes 2 Zn and 2 citrate per formula), [Zn(Citr)H] = 8.4 × 10⁻¹² M.
- Zn-bound total (sum over all Zn–citrate complexes, counting the dinuclear as 2 Zn): (6.17 + 8.68 + 2×7.11) × 10⁻⁷ = 2.91 × 10⁻⁶ M. As a fraction of the 1.00 mM total Zn: **≈ 0.29 %**.
- Remaining Zn hydroxo forms in solution: [Zn(OH)₂⁰] = 6.50 × 10⁻⁷ M dominates the hydroxo side; Zn(OH)⁺ 6.5 × 10⁻⁹ M; Zn(OH)₃⁻ 1.7 × 10⁻¹⁰ M. Total dissolved Zn ≈ 3.6 × 10⁻⁶ M, so **≈ 99.6 % of the Zn is locked in ZnO(s)** at pH 8.5.
- Citrate tied up on Zn (counting stoichiometry): 1×[Zn(Citr)⁻] + 2×[Zn(Citr)₂⁴⁻] + 2×[Zn₂(Citr)₂(OH)₂⁴⁻] ≈ 6.17 × 10⁻⁷ + 1.74 × 10⁻⁶ + 1.42 × 10⁻⁶ = **3.8 × 10⁻⁶ M**, i.e. **≈ 0.13 % of the 3.00 mM citrate pool**. The rest of the citrate (~2.995 mM) sits as free Cit³⁻.

**Practical read for antiscale screening.** At boiler pH 8.5, a 3:1 citrate:Zn dose does not keep Zn dissolved — ZnO precipitation wins by ~3 orders of magnitude, citrate binds barely 0.3 % of the metal, and virtually none of the ligand pool is consumed by Zn. For hardness competition studies this means citrate at threefold excess is essentially still fully available to compete with Ca²⁺/Mg²⁺ at pH 8.5 (citrate is not "burned" on Zn), but citrate is a poor Zn-antiscale ligand under alkaline boiler conditions — Zn is controlled by ZnO solubility, not by Zn–citrate complexation. Meaningful Zn sequestration on citrate is confined to the pH 4.5–7.0 window identified above.

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
- [solver/topology_Zn$+2_+_Zn$+0_+_Citric_acid_Zn.json](<solver/topology_Zn$+2_+_Zn$+0_+_Citric_acid_Zn.json>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_concentrations.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_concentrations.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_envelope_L1.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_envelope_L1.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_envelope_Zn$+2.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_envelope_Zn$+2.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_L1.png](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_L1.png>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_ligand.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_ligand.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_metal.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_metal.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_Zn.png](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_frac_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_log_conc.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_log_conc.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_log_conc.png](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_log_conc.png>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_phase_balance_Zn.png](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_phase_balance_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_run_params.json](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_run_params.json>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_state_metrics.csv](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_state_metrics.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Citric_acid_verdict.md](<solver/Zn$+2_+_Zn$+0_+_Citric_acid_verdict.md>)
- [verdict.json](<verdict.json>)
