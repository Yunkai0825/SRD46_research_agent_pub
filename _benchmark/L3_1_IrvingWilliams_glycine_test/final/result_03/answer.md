## Doability
Doable — standard aqueous Cu(II)/glycine speciation over a narrow pH window; all 21 grid points converged and no redox coupling is active (Cu(0) and Cu(I) totals are zero).

## Result
- System: Cu(II) 1.00 mM + glycine 10.0 mM, T = 25 °C, I = 0.1 M (fixed), redox excluded (Cu²⁺ subtotal only).
- Method: 1‑D pH sweep, pH 6.5 → 7.5, 21 points.
- Convergence: 21/21 samples converged; calculated ionic-strength range 1.4×10⁻⁵ – 5.6×10⁻⁵ M is well below the imposed 0.1 M ceiling, so the fixed‑I activity model — not the trace background electrolyte — sets the corrections.
- No solid phase forms in this window: [(Cu₂O)₀.₅](s), CuO(s), and Cu(OH)₂(s) all sit at 0 mol/L throughout (undersaturated), so the aqueous ladder tells the whole story.

## Analysis
Across the entire pH 6.5–7.5 window the bis‑glycinate complex **[Cu(Glyc)₂]** dominates the Cu(II) budget, rising monotonically from 98.2% at pH 6.5 to 99.8% at pH 7.5 (peak reported in the verdict). At **pH 7.00** the Cu(II) inventory partitions as:

| Species | [ ] / mol L⁻¹ | Fraction of Cu_total |
|---|---:|---:|
| [Cu(Glyc)₂] (neutral) | 9.943 × 10⁻⁴ | 99.43% |
| [Cu(Glyc)]⁺ (mono) | 5.702 × 10⁻⁶ | 0.570% |
| free **Cu²⁺** (aquo) | **2.808 × 10⁻⁹** | 2.81 × 10⁻⁶ |
| [Cu(OH)]⁺ | 2.16 × 10⁻¹⁰ | 2.2 × 10⁻⁷ |
| [Cu(OH)₂]⁰ | 1.08 × 10⁻¹¹ | 1.1 × 10⁻⁸ |
| [Cu₂(OH)₂]²⁺, [Cu₃(OH)₄]²⁺, HCuO₂⁻, CuO₂²⁻ | ≤ 3 × 10⁻¹⁵ | negligible |

There are no crossover pH values in the range because [Cu(Glyc)₂] is dominant at every sampled pH; the only ratio that shifts is bis:mono glycinate. The chemistry driving this is the balance between glycine speciation and Cu(II) affinity. The reference table gives log β(H⁺ + Gly⁻ → HGly) = 9.57 and log β(2H⁺ + Gly⁻ → H₂Gly⁺) = 11.90, so glycine's carboxylate pKₐ ≈ 11.90 − 9.57 = 2.33 and its ammonium pKₐ = 9.57. Near neutral pH glycine is almost entirely the zwitterion HGly (99.7–99.9% of L_total in the CSV), and only the tiny deprotonated Gly⁻ tail (1.1 × 10⁻⁵ → 1.1 × 10⁻⁴ M from pH 6.5 → 7.5) is available to coordinate. Cu(II) nevertheless captures it essentially quantitatively because β₂ for Cu²⁺ + 2 Gly⁻ → Cu(Gly)₂ is 10¹⁵·¹⁰ — the largest bis‑amino‑acid formation constant of the first‑row divalents — so despite the 10⁻⁵–10⁻⁴ M free‑Gly⁻ pool, log β₂ + 2 log[Gly⁻] ≈ 15.1 − 8 ≈ 7 easily overwhelms the ≈ 10⁻¹⁰ chelate‑free Cu²⁺ activity and drives the metal into the chelate.

The step from mono‑ to bis‑glycinate is also energetically favourable here: log K₂ = log β₂ − log β₁ = 15.10 − 8.19 = 6.91, and with [Gly⁻] ≈ 3.5 × 10⁻⁵ M at pH 7, [Cu(Glyc)₂]/[Cu(Glyc)⁺] ≈ 10^6.91 × [Gly⁻] ≈ 2.9 × 10², matching the observed 9.943 × 10⁻⁴ / 5.702 × 10⁻⁶ ≈ 174 (order‑of‑magnitude consistent given activity corrections). Hydrolysis products are entirely suppressed — [Cu(OH)]⁺ at 2 × 10⁻¹⁰ M and dimer/trimer hydroxo clusters at 10⁻¹⁵ or below — because chelation strips Cu²⁺ out of solution faster than OH⁻ can reach it, and this is precisely why no CuO(s)/Cu(OH)₂(s) forms even though pH 7 would otherwise flirt with Cu(OH)₂ saturation at 1 mM total Cu.

**Irving–Williams ranking use.** The single number to compare against parallel Co(II), Ni(II), Zn(II) runs is the residual free aquo metal at pH 7 under identical totals: for Cu(II) here it is **[Cu²⁺]_free = 2.81 × 10⁻⁹ M**, i.e. only 2.8 parts per million of total Cu remains uncomplexed, corresponding to a conditional pM = −log[Cu²⁺]_free = 8.55 at pH 7, I = 0.1 M, 25 °C, [Gly]_T = 10 mM. In the Irving–Williams series (Mn < Fe < Co < Ni < **Cu** > Zn) Cu(II) is the maximum, so we predict Co, Ni, and Zn to leave substantially larger free‑M²⁺ pools (smaller pM) at pH 7 under the same conditions, with Ni closest to Cu and Co / Zn further away. The Cu bis‑glycinate log β₂ of 15.10 used here is the quantitative anchor for that comparison.

Caveats: results hold at the fixed totals, T = 25 °C, and I = 0.1 M of this card; the sweep is aqueous only (no explicit solid was needed because none saturated), and no oxidation‑state chemistry was considered (Cu(0)/Cu(I) totals were zero, so their entries in the free‑energy table are inert reference states, not participating species).

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
