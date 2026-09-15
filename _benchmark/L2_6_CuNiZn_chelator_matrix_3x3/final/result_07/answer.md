## Doability
Doable — Zn(II) + glycine is a canonical SRD-46 speciation problem, and a 1-D pH sweep is exactly what fixes the free-metal question at pH 7.

## Result
- System: Zn²⁺ 1.00 mM + glycine 5.00 mM, aqueous, 25 °C, fixed ionic strength I = 0.1 M, redox excluded (Zn⁰ carried as 0 M subtotal, so no metallic Zn reduction pathway).
- Method: `pH_sweep`, pH 2.0–12.0 in 101 steps (Δ = 0.1). Convergence 101/101; every reported pH point is evidence.
- Included aqueous Zn forms: Zn²⁺, [Zn(OH)]⁺, [Zn(OH)₂], [Zn(OH)₃]⁻, [Zn(OH)₄]²⁻, [Zn(Glyc)]⁺ (log β₁ = 4.96), [Zn(Glyc)₂] (log β₂ = 9.19), [Zn(Glyc)₃]⁻ (log β₃ = 11.60), [Zn(Glyc)(OH)] (log β = −3.94). Glycine protonation: HGly pKa₁(carboxyl) ≈ 2.4 (from β = 11.90 for H₂Gly⁺ minus 9.57 for HGly), pKa₂(ammonium) = 9.57. Solid Zn(OH)₂(α) and ZnO are in the card; the solver reports ZnO precipitates from pH 6.5 onward (verdict: “pH 6.50: ZnO (inactive) (1.62 × 10⁻⁴ M)”).

## Analysis
**Free [Zn²⁺] at pH 7.** From the concentrations table at pH 7.0:
- [Zn²⁺]_free = **6.71 × 10⁻⁵ M** (≈ 6.7 % of total Zn),
- [Zn(Glyc)]⁺ = 4.94 × 10⁻⁵ M (4.9 %),
- [Zn(Glyc)₂] = 1.11 × 10⁻⁵ M (1.1 %),
- [Zn(OH)₂]° = 6.50 × 10⁻⁷ M, [Zn(OH)]⁺ = 2.06 × 10⁻⁷ M, [Zn(Glyc)(OH)] = 6.22 × 10⁻⁷ M, [Zn(Glyc)₃]⁻ = 6.15 × 10⁻⁸ M (all negligible).

The aqueous fractions in the Zn²⁺ envelope sum to only ≈ 0.128 at pH 7 (Zn²⁺ 0.0671 + [Zn(Glyc)]⁺ 0.0494 + [Zn(Glyc)₂] 0.0111). The remaining ≈ 87 % of the 1 mM zinc total is sequestered as **precipitated ZnO(s)**, whose onset the verdict places at pH 6.5 with 1.62 × 10⁻⁴ M solid at that first supersaturated grid point; between pH 6.5 and 7.0 the solid load grows further (the aqueous Zn²⁺ envelope fraction drops from 0.87 → 0.42 → 0.067 across pH 6.3 / 6.6 / 7.0), which is the deterministic driver of the free-Zn²⁺ collapse.

**Why the numbers look this way.** Below pH ≈ 5 the ligand is the zwitterion HGly (peak 99.6 % at pH 5.1) with a vanishing free-Gly⁻ concentration, so essentially no Zn–glycinate forms and Zn²⁺ is > 99 % of total Zn (verdict: Zn²⁺ dominant from pH 2.0 to 7.2). Only when the ammonium group starts to deprotonate near pKa₂ = 9.57 does [Gly⁻] rise enough to make [Zn(Glyc)]⁺ competitive — the verdict places the aqueous Zn²⁺ → [Zn(Glyc)]⁺ crossover between pH 7.1 and 7.2. At pH 7 we are still on the “glycine is protonated” side of that crossover: only ≈ 4.3 × 10⁻⁶ of glycine is present as free Gly⁻ (2.16 × 10⁻⁵ M out of 5 mM), so the effective conditional stability of the mono-glycinate is modest and Zn²⁺ survives as a bulk aqueous form only where hydroxide precipitation does not already remove it. Above pH ≈ 6.5, hydrolysis (formally K_sp of ZnO/Zn(OH)₂) wins the competition against a still-mostly-protonated ligand, so ZnO(s) drops out before glycinate chelation can capture the metal; this is why the free-[Zn²⁺] curve does not go to zero via [Zn(Glyc)ₙ] formation but via solid precipitation.

**Practical implication for the selectivity matrix.** At the stated conditions, glycine at 5:1 ligand:metal ratio does **not** hold Zn(II) in solution at pH 7 — it buffers pZn only mildly (pZn ≈ 4.17 for the aqueous fraction, driven mostly by ZnO precipitation, not by chelation). About 87 % of the zinc is a ZnO solid load; the remaining ≈ 13 % of total Zn is roughly evenly split between free hexaaquo Zn²⁺ and the mono-glycinate [Zn(Glyc)]⁺, with the bis-glycinate a minor contributor. If the matrix needs a truly soluble, glycinate-bound Zn pool at pH 7, either the ligand excess must be raised substantially, the pH lowered below the ZnO onset (~pH 6.5 here), or a stronger chelator used; glycine alone at 5 mM cannot suppress Zn hydroxide precipitation at neutral pH.

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
- [solver/topology_Zn$+2_+_Zn$+0_+_Glycine_Zn.json](<solver/topology_Zn$+2_+_Zn$+0_+_Glycine_Zn.json>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_concentrations.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_concentrations.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_L1.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_L1.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_Zn$+2.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_envelope_Zn$+2.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_L1.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_L1.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_ligand.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_ligand.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_metal.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_metal.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_frac_Zn.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_frac_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_log_conc.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Zn.png](<solver/Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_run_params.json](<solver/Zn$+2_+_Zn$+0_+_Glycine_run_params.json>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_state_metrics.csv](<solver/Zn$+2_+_Zn$+0_+_Glycine_state_metrics.csv>)
- [solver/Zn$+2_+_Zn$+0_+_Glycine_verdict.md](<solver/Zn$+2_+_Zn$+0_+_Glycine_verdict.md>)
- [verdict.json](<verdict.json>)
