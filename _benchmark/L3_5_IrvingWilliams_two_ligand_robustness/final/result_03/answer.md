## Doability
Doable. Cu(II) + glycine speciation vs pH is a canonical `pH_sweep`; SRD-46 supplies pKa(NH3+), Cu–glycinate β1 and β2, Cu hydrolysis products, and CuO(s) needed for the ladder.

## Result
- System: Cu(II) 1.00 mM + glycine 10.0 mM (10:1 L:M), aqueous, 25 °C, fixed I = 0.1 M, redox excluded (only Cu²⁺ redox-state used; Cu⁰/Cu⁺ totals zero).
- Method: 1-D `pH_sweep`, 101 points from pH 2.0 → 12.0. **Convergence 101/101.**
- Solver-supplied ladder (Cu²⁺ subsystem, dominant form):
  - pH 2.0–3.7 → Cu²⁺
  - pH 3.7–4.8 → [Cu(Gly)]⁺
  - pH 4.8–10.8 → [Cu(Gly)₂]
  - pH 10.8–12.0 → CuO(s)
- Crossovers (grid-bracketed): Cu²⁺ ↔ [Cu(Gly)]⁺ at pH ≈ 3.64, [Cu(Gly)]⁺ ↔ [Cu(Gly)₂] at pH ≈ 4.73, [Cu(Gly)₂] ↔ CuO(s) at pH ≈ 10.75. CuO(s) first appears at pH 10.60. No Cu(OH)₂(s) precipitation is predicted anywhere in the window (glycinate keeps Cu in solution well past ordinary hydroxide saturation).

## Analysis
**Fractions and concentrations at pH 7.0 (Cu_tot = 1.00 mM), from `..._frac_metal.csv` row pH = 7.0000:**

| species | fraction of Cu | [conc], M |
|---|---:|---:|
| [Cu(Gly)₂] | 0.99429 | 9.94 × 10⁻⁴ |
| [Cu(Gly)]⁺ | 5.70 × 10⁻³ | 5.70 × 10⁻⁶ |
| Cu²⁺ (free aquo) | 2.81 × 10⁻⁶ | 2.81 × 10⁻⁹ |
| [Cu(OH)]⁺ | 2.16 × 10⁻⁷ | 2.16 × 10⁻¹⁰ |
| [Cu(OH)₂]⁰ | 1.08 × 10⁻⁸ | 1.08 × 10⁻¹¹ |
| [Cu₂(OH)₂]²⁺ | 6.08 × 10⁻¹² | 6.08 × 10⁻¹⁵ |
| HCuO₂⁻ | 5.54 × 10⁻¹² | 5.54 × 10⁻¹⁵ |
| [Cu₃(OH)₄]²⁺ | 7.85 × 10⁻¹⁸ | 7.85 × 10⁻²¹ |
| CuO₂²⁻ | 1.08 × 10⁻¹⁷ | 1.08 × 10⁻²⁰ |
| CuO(s), Cu(OH)₂(s), (Cu₂O)₀.₅(s) | 0 | 0 |

Dominant species at pH 7.0: **bis(glycinato)copper(II), [Cu(Gly)₂]⁰, at ~99.4 % of total Cu.** Free aquo Cu²⁺ is suppressed to about 2.8 ppm of the total metal (2.8 nM out of 1 mM), and Cu-hydroxo species are negligible.

**Chemistry driving the ladder.** Glycine (the reference table gives log β for HGly = +9.57, for H₂Gly⁺ = +11.90 — so pKa(carboxyl) ≈ 11.90 − 9.57 = 2.33 and pKa(ammonium) ≈ 9.57) exists mainly as the zwitterion HGly across pH 2.4–9.4. In that middle window the tiny equilibrium fraction of the fully deprotonated glycinate anion Gly⁻ is what binds Cu²⁺ through the classic 5-membered N,O-chelate. The relevant formation constants from the reference table are log β₁(Cu(Gly)⁺) = +8.19 and log β₂(Cu(Gly)₂) = +15.10, giving a stepwise log K₂ = 15.10 − 8.19 = 6.91. Even though Gly⁻ is scarce at low pH, β₁ is large enough that Cu²⁺ starts losing majority already near pH 3.6, well below the ammonium pKa: freeing more Gly⁻ costs a proton, but the chelate return is so large that hydrogen-ion competition is overwhelmed by ~pH 4. Between pH 3.7 and 4.8 the 1:1 complex is the majority carrier; because L is in 10-fold excess and log K₂ is only ~1.3 units smaller than log K₁, the second glycinate binds essentially as soon as the first, so the mono-glycinate window is narrow (~1 pH unit) and [Cu(Gly)₂] takes over by pH 4.8 and stays dominant across the whole physiological/biological range. The bis-chelate is neutral and coordinatively saturated in the equatorial plane, which is precisely why it also blocks Cu(OH)₂(s) and Cu₂(OH)₂²⁺ from forming: hydrolysis products stay 5–8 orders of magnitude below the chelate all the way up to pH ~10.6, where the free-Gly⁻ activity finally cannot keep pace with OH⁻ and CuO(s) nucleates (crossover pH ≈ 10.75). Free aquo Cu²⁺ therefore loses majority at pH ≈ 3.64, and by pH 7 it is essentially absent (~3 nM).

**Irving-Williams context.** For the same donor set (N,O amino-acid chelate, β₂-type binding) and identical totals, the Irving-Williams series predicts K(Mn) < K(Fe) < K(Co) < K(Ni) < K(Cu) > K(Zn), with Cu(II) as the maximum owing to Jahn-Teller stabilization of its d⁹ tetragonal geometry. The Cu-glycinate log β₂ of +15.10 found here is markedly larger than the typical Co(II)/Ni(II)/Zn(II) glycinate β₂ values (~9–11), which manifests numerically as (i) the very low free-Cu²⁺ fraction at neutral pH (~3 × 10⁻⁶), (ii) the early crossover from Cu²⁺ to complex (pH ≈ 3.6 instead of ≥ 5 typical for weaker M(II)), and (iii) the exceptionally high pH (~10.6) at which the chelate finally yields to CuO(s). All three signatures are consistent with Cu(II) being the maximum of the series for this donor set; the definitive test is the side-by-side comparison with the Co/Ni/Zn runs at the identical 1 mM/10 mM condition.

**Practical implications.** At neutral pH with a modest excess of glycine, essentially all copper is masked as the neutral, kinetically labile [Cu(Gly)₂] chelate. Free-Cu²⁺ activities (~3 nM) are far below concentrations relevant for hydroxide/carbonate precipitation, adsorption on silica, or acute toxicity in most biological contexts — a direct chemical explanation of why glycine and related amino acids are effective Cu(II) buffers in biology and in coordination-chemistry benchwork.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Glycine_Cu.json>)
- [verdict.json](<verdict.json>)
