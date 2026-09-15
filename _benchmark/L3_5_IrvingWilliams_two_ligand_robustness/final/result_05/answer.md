## Doability
Doable — Co(II) + ethylenediamine is fully covered in SRD-46 (three Co(en)n complexes, Co-hydroxo ladder including solid Co(OH)2, plus en protonation constants); pH_sweep is the correct method for fixed-redox 1-D speciation.

## Result
- System: 1.00 mM Co(II) + 10.0 mM ethylenediamine (en), redox excluded (only Co$^{2+}$ present; Co$^0$/Co$^{3+}$/Co$^{4+}$ totals set to 0).
- Method: `pH_sweep`, pH 2.0 – 12.0 in 101 points, T = 25.0 °C, ionic strength fixed at target I = 0.1 M (calculated span 7.9×10⁻⁴ – 2.2×10⁻² M, i.e. actual I lies well below target — activity coefficients are anchored to the declared 0.1 M reference).
- Convergence: 101/101 samples converged for every component (metal and ligand blocks both report 101/101). All quoted numbers are on-grid.
- Ligand constants used (from the deterministic reference table, cumulative from free en): log β(H·en⁺) = 9.92, log β(H₂·en²⁺) = 17.03 ⇒ pKa2 = 9.92 (en/Hen⁺), pKa1 = 17.03 − 9.92 = 7.11 (Hen⁺/H₂en²⁺).
- Complex constants: log β₁ = 5.50, log β₂ = 10.10, log β₃ = 13.40 for [Co(en)ₙ]²⁺. Hydrolysis: log β for Co(OH)⁺ = −9.70, Co(OH)₂(aq) = −18.80, Co₂(OH)³⁺ = −11.00, Co₄(OH)₄⁴⁺ = −30.50, Co(OH)₃⁻ = −31.50, Co(OH)₄²⁻ = −46.30, and dissolution log K for Co(OH)₂(s) = −13.10.

## Analysis

**Dominance ladder vs pH (metal basis).** The solver returns
- pH 2.0 – 7.0 → free Co²⁺
- pH 7.0 – 7.6 → [Co(en)]²⁺
- pH 7.6 – 8.8 → [Co(en)₂]²⁺
- pH 8.8 – 12.0 → [Co(en)₃]²⁺
- pH 12.0 (last sample) → Co(OH)₂(s)

Grid-bracketed crossovers: Co²⁺ ↔ [Co(en)]²⁺ at pH ≈ 6.96 (each ~47%), [Co(en)]²⁺ ↔ [Co(en)₂]²⁺ at pH ≈ 7.58 (each ~46%), [Co(en)₂]²⁺ ↔ [Co(en)₃]²⁺ at pH ≈ 8.79 (each ~49%), and [Co(en)₃]²⁺ ↔ Co(OH)₂(s) at pH ≈ 11.90 (each ~48%).

**pH 7.00 snapshot (from `..._concentrations.csv`, totals [Co]=1.0 mM, [en]=10 mM):**

| Species | Concentration (M) | Fraction of Co total |
|---|---:|---:|
| Co²⁺ (free) | 4.325×10⁻⁴ | 43.3% |
| [Co(en)]²⁺ | 4.951×10⁻⁴ | 49.5% |
| [Co(en)₂]²⁺ | 7.135×10⁻⁵ | 7.13% |
| [Co(en)₃]²⁺ | 5.15×10⁻⁷ | 0.052% |
| [Co(OH)]⁺ | 5.27×10⁻⁷ | 0.053% |
| [Co(OH)₂]⁰ | 4.19×10⁻⁹ | 4.2×10⁻⁴ % |
| [Co₂(OH)]³⁺ | 3.06×10⁻¹¹ | negligible |
| [Co(OH)₃]⁻, [Co₄(OH)₄]⁴⁺, [Co(OH)₄]²⁻ | ≤10⁻¹⁴ M | negligible |
| Co(OH)₂(s) | 0 | none — undersaturated |

Free en at pH 7.00 is only 3.62×10⁻⁶ M; the 10 mM ligand pool is overwhelmingly locked as H₂en²⁺ (6.35 mM) and Hen⁺ (3.01 mM), with just 6.4×10⁻⁴ M carried into Co-en complexes. There are no solids at pH 7 — Co(OH)₂(s) first appears at pH 11.70 (1.30×10⁻⁴ M, ~13% of Co total) and grows to 6.22×10⁻⁴ M (62%) at pH 12.

**Chemical interpretation.**

1. *Why the ladder is late and stepwise.* Ethylenediamine is a strong base: pKa2 = 9.92 for Hen⁺ and pKa1 = 7.11 for H₂en²⁺ mean that below pH ~7 essentially all the ligand is diprotonated and non-coordinating. The Co²⁺/Co(en)²⁺ crossover at pH ≈ 6.96 therefore tracks the H₂en²⁺ → Hen⁺ deprotonation almost exactly — Co(II) can only start recruiting en once the first proton has been titrated off. Successive crossovers at pH 7.58 and 8.79 correspond to progressive liberation of Hen⁺/en as the pKa2 window is entered; the ordering is set by the stepwise formation constants (log K₁ = 5.50, log K₂ = β₂ − β₁ = 4.60, log K₃ = β₃ − β₂ = 3.30), which show the expected monotonic decrease from statistical + electrostatic + steric effects.

2. *Why [Co(en)₃]²⁺ never quite reaches saturation of the ladder.* Its peak fraction is only 93.1% at pH 11.5; above that, hydroxide starts to compete and the tris-chelate cedes to Co(OH)₂(s). The [Co(en)₃]²⁺ ↔ Co(OH)₂(s) crossover at pH ≈ 11.90 (~48% each) sets the practical upper pH limit for keeping Co(II) dissolved as the en complex at these totals; even a modest excess of en (10:1) does not fully suppress precipitation because the solubility product of Co(OH)₂(s) (log K_sp effectively −13.1 for the dissolution stoichiometry) is aggressive at high pH.

3. *pH 7.00 practical picture.* At physiological pH the Co(II)/en system is roughly a 43/50/7 split of free Co²⁺, mono-, and bis-en with only trace tris-en. Hydrolysis is essentially inactive (Co(OH)⁺ is 0.05% and lower hydroxo forms are vanishing), so buffering effects come almost entirely from en protonation, not from cobalt hydrolysis. To push the system into predominantly [Co(en)₃]²⁺ one must go to pH ≳ 9.

4. *Relevance to the Irving–Williams comparison.* For the cross-ligand Irving–Williams test, the diagnostic number is the pH at which Co²⁺ first hands the majority to Co(en)ₙ²⁺, and the peak fraction attainable in [Co(en)₃]²⁺ before hydroxide takes over. Here that transition point is pH ≈ 6.96 and the tris-en maximum is 93.1% at pH 11.5, with precipitation onset at pH 11.70. Comparing these three numbers (transition pH, tris-en maximum, precipitation onset pH) across Mn, Fe, Co, Ni, Cu, Zn will show whether the Cu(II) maximum in the aqua system carries over to the diamine donor set, or whether Ni(II)/Cu(II) both suppress hydrolysis so strongly that the Irving–Williams ordering is preserved.

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
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_concentrations.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_concentrations.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_envelope_Co$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_envelope_Co$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_envelope_L1.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_envelope_L1.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_L1.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_L1.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_ligand.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_ligand.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_metal.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_frac_metal.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_log_conc.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_log_conc.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_log_conc.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_log_conc.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_phase_balance_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_phase_balance_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_run_params.json](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_run_params.json>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_state_metrics.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_state_metrics.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_verdict.md](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_verdict.md>)
- [solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_Co.json](<solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Ethylenediamine_Co.json>)
- [verdict.json](<verdict.json>)
