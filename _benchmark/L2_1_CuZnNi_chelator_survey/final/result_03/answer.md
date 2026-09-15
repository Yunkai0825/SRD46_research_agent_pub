## Doability
Doable — a supported pH_sweep with Cu²⁺/Ni²⁺/Zn²⁺ + glycine (SRD-46 ligand), full hydroxo and M(OH)₂(s) species included, redox excluded. All 41/41 grid points converged.

## Result
One shared aqueous pot: [Cu²⁺]ᴛ=[Ni²⁺]ᴛ=[Zn²⁺]ᴛ=1.00 mM, [Glycine]ᴛ=5.00 mM, 25 °C, I=0.1 M fixed, pH 6.0–8.0 (41 samples, all converged). Method = pH_sweep (no redox axis). Zn(OH)₂(α) precipitates from pH ≈ 7.05 upward (first appearance 6.82×10⁻⁵ M at pH 7.05; grows to ~9.58×10⁻⁴ M at pH 8, i.e. essentially all Zn as solid). Glycine card constants used: HGly pKa = 9.57, H₂Gly⁺ cumulative log β = 11.90 (so –NH₃⁺ pKa ≈ 11.90–9.57 = 2.33). Cu–glycinate log β₁ = 8.19, log β₂ = 15.10; Ni: 5.74, 10.58, 14.10; Zn: 4.96, 9.19, 11.60 plus mixed [Zn(Gly)(OH)] log β = –3.94.

## Analysis
**Cu(II) — completely locked up as bis-glycinate across the whole window.** [Cu(Gly)₂] is dominant at every sampled pH (peak 99.6 % at pH 8; already ≈86 % at pH 6 with [Cu(Gly)]⁺ only 13.7 %). Free [Cu²⁺] falls from 1.87×10⁻⁶ M (pH 6) → 4.97×10⁻⁸ M (pH 7) → 1.35×10⁻⁹ M (pH 8), i.e. six orders of magnitude below total. This is driven by Cu(II)'s exceptionally large β₂ (log β₂ = 15.10, the largest of the three metals by >4.5 log units) combined with the fact that even at pH 6, deprotonated Gly⁻ (though only ~10⁻⁶ M free) is enough to saturate Cu because the effective conditional constant K′ = β₂·α_L² is still huge. No Cu(OH)₂(s) forms — chelation keeps Cu²⁺ activity far below the Ksp.

**Ni(II) — climbs the glycinate ladder with pH.** Free Ni²⁺ dominates (78 %) at pH 6 because Ni's β₁ (5.74) is ~2.5 log units weaker than Cu's and the tiny free-Gly⁻ pool at pH 6 is insufficient to compete. Crossovers: Ni²⁺ ↔ [Ni(Gly)]⁺ at pH ≈ 6.69, [Ni(Gly)]⁺ ↔ [Ni(Gly)₂] at pH ≈ 7.56; [Ni(Gly)₂] tops out at 59.6 % by pH 8 with [Ni(Gly)₃]⁻ reaching 10 %. Free [Ni²⁺]: 7.85×10⁻⁴ M → 3.02×10⁻⁴ M → 2.67×10⁻⁵ M. Ni hydrolysis is negligible in this window (log β for Ni(OH)⁺ = –10.4), and no Ni(OH)₂(s) precipitates.

**Zn(II) — glycinate loses to hydroxide precipitation.** Zn's β's are the weakest of the three (β₂ = 9.19), so at pH 6 Zn²⁺ is 96 % free with only ~4 % [Zn(Gly)]⁺. Between pH 7.05 and 7.17 Zn(OH)₂(α) nucleates and rapidly dominates: 41 % solid at pH 7.17, ≥96 % solid at pH 8. Free [Zn²⁺]: 9.58×10⁻⁴ M → 7.56×10⁻⁴ M → 8.65×10⁻⁶ M — the pH-8 drop is set by the Zn(OH)₂ solubility, not by chelation. Glycine cannot outcompete hydroxide here because β_ZnGly is small and [OH⁻] rises 100-fold across the window.

**Selectivity ratios (free [M²⁺] over free [Cu²⁺]):**

| pH | [Ni²⁺]/[Cu²⁺] | [Zn²⁺]/[Cu²⁺] |
|----|---------------|---------------|
| 6.0 | 4.2×10² | 5.1×10² |
| 7.0 | 6.1×10³ | 1.5×10⁴ |
| 8.0 | 2.0×10⁴ | 6.4×10³ |

Cu selectivity over Ni improves monotonically with pH (rising [Gly⁻] preferentially saturates Cu first because Cu grabs the second glycinate ~4.5 log units more strongly than Ni). Cu-over-Zn selectivity peaks near pH 7 and then falls at pH 8 only because Zn precipitates out — the drop in free [Zn²⁺] at pH 8 is a solubility artefact, not a competition between Cu and Zn for glycine. **Practical read**: at pH 7 glycine already discriminates Cu²⁺ from Ni²⁺ by ~3.8 orders of magnitude in free-ion activity and from Zn²⁺ by ~4.2 orders; a pH-7, 5:1 glycine:total-metal buffer is a clean Cu(II)-selective mask, and Zn is additionally removed as a precipitate above pH ≈ 7.05. Glycine is a genuinely Cu-selective chelator here because of the Irving–Williams β₂ ordering Cu ≫ Ni > Zn combined with Cu²⁺'s Jahn–Teller-favoured square-planar bis-glycinate geometry.

**Ligand budget** (from verdict): at pH 8, 39.8 % of total glycine is bound in [Cu(Gly)₂] (uses ~2 mM of the 5 mM), 23.8 % in [Ni(Gly)₂], 6.0 % in [Ni(Gly)₃]⁻, remainder as HGly/Gly⁻; the 5 mM budget (2.5× stoichiometric for bis-chelation of all three metals) is enough to fully complex Cu and largely complex Ni without stripping Zn from its hydroxide.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_Ni$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_Ni$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_Zn$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_envelope_Zn$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_Ni.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_Ni.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_frac_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Ni.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Ni.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_phase_balance_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Glycine_Cu.json>)
- [verdict.json](<verdict.json>)
