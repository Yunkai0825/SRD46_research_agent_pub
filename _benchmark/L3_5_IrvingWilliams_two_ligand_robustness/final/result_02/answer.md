## Doability
Doable: NIST SRD-46 provides Ni(II)–glycine stepwise constants (log β1 = 5.74, log β2 = 10.58, log β3 = 14.10), Ni(II) hydrolysis species, and Ni(OH)2(s) solubility; a pH_sweep at fixed I and T is squarely in scope.

## Result
- System: Ni(II) 1.00 mM + glycine (H₂L⁺/HL/L⁻) 10.0 mM, ratio 1:10.
- Method: pH_sweep, pH 2.0–12.0 in 0.1 steps (101 points), T = 25 °C, I = 0.1 M (fixed-I mode), redox excluded (only Ni(II) admitted; Ni(0)/(III)/(IV) totals zero).
- Convergence: 101/101 samples converged (metal, ligand, and each nickel oxidation-state block).
- Precipitation: Ni(OH)2(s) first appears at pH 11.0 (8.24×10⁻⁵ M) and is the dominant nickel sink above pH ≈ 11.23.

## Analysis
**pH 7.00 (the requested point).** From the metal fraction table:
- Free Ni²⁺: fraction = 4.62×10⁻² (4.62 %) → [Ni²⁺] ≈ 4.62×10⁻⁵ M.
- [Ni(Glyc)]⁺ (mono): 34.8 %.
- **[Ni(Glyc)₂] (bis, neutral): 54.0 % — the dominant Ni species at pH 7.**
- [Ni(Glyc)₃]⁻ (tris): 6.57 %.
- Hydroxo species are negligible: [Ni(OH)]⁺ ≈ 1.1×10⁻⁵ (i.e. ~1×10⁻³ %), [Ni(OH)₂]° ≈ 2.8×10⁻⁷, [Ni(OH)₃]⁻ ≈ 5×10⁻¹¹, and the tetranuclear [Ni₄(OH)₄]⁴⁺ ≈ 10⁻¹³. No solid at pH 7 (Ni(OH)₂(s) fraction = 0). Sum of Ni-glycinate fractions ≈ 95.3 %, so glycine sequesters ~20× more Ni than remains as aquo ion, and hydrolysis is completely suppressed by chelation at neutral pH.

**Why the bis-complex wins at pH 7.** The ligand-side ladder (H₂L⁺ ↔ HL 2.4; HL ↔ L⁻ 9.4) shows glycine is >99 % zwitterionic HL at pH 7; the free anion L⁻ needed for Ni binding is only ~4×10⁻⁴ of total glycine. Chelation via the (N, carboxylate-O) five-membered ring pays back this deprotonation cost through the strong stepwise constants (log K₁ = 5.74, log K₂ = 4.84, log K₃ = 3.52 from the reference table). At the 10:1 L/Ni ratio, the free L⁻ at pH 7 (≈4×10⁻⁶ M) puts K₂[L]/1 near unity, so mono and bis are comparable and the neutral [Ni(Glyc)₂] just edges out; the tris form still needs another ~10-fold more free L⁻ and only takes over above pH ≈ 8.

**Dominance ladder vs pH (crossovers grid-bracketed at 0.1 pH steps).**
- pH 2.0–6.1: aquo Ni²⁺ (Ni²⁺/[Ni(Glyc)]⁺ crossover at pH ≈ 6.07, each ~45 %).
- pH 6.1–6.8: mono [Ni(Glyc)]⁺ (peak 52 % at pH 6.4). Mono/bis crossover at pH ≈ 6.80.
- pH 6.8–8.0: bis [Ni(Glyc)₂] (peak 63.5 % at pH 7.4). Bis/tris crossover at pH ≈ 7.98.
- pH 8.0–11.3: tris [Ni(Glyc)₃]⁻ (peak 95.8 % at pH 10.9).
- pH 11.3–12.0: Ni(OH)₂(s) — tris/solid crossover pH ≈ 11.23; at pH 12 the solid holds 97.5 % of nickel. Between pH 11.0 and 11.3 aqueous [Ni(OH)₃]⁻ is still ≤2×10⁻⁴, so precipitation, not soluble hydrolysis, ends the glycinate regime.

**Comparison to the Irving–Williams expectation.** Chelation shifts Ni²⁺ loss of dominance from the hydrolysis-onset region (pKa1 for Ni(OH)⁺ ≈ 10.4 from the reference table) all the way down to pH ≈ 6.07 — a ~4 pH-unit stabilisation of glycinate over aquo/hydroxo Ni. This is the Ni entry in the Irving–Williams series; the accompanying Cu(II)/glycine calculation should show the same ladder but with each crossover pushed 1.5–2 pH units lower and a Cu(Glyc)₂ regime that both starts earlier and survives further into base (because Cu(II) has larger log K₁ and K₂), which is the Irving–Williams maximum. For Ni at pH 7 with 10 mM glycine, only ~5 % of the metal is free — well suppressed but not as extreme as Cu(II) would be under the same conditions.

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
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_concentrations.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_concentrations.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_L1.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_L1.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Ni$+2.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_envelope_Ni$+2.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_L1.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_L1.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_ligand.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_ligand.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_metal.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_metal.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_frac_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_log_conc.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Ni.png](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_phase_balance_Ni.png>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_run_params.json](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_run_params.json>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_state_metrics.csv](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_state_metrics.csv>)
- [solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_verdict.md](<solver/Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_verdict.md>)
- [solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_Ni.json](<solver/topology_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Glycine_Ni.json>)
- [verdict.json](<verdict.json>)
