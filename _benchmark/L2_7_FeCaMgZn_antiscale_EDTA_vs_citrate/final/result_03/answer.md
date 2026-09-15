## Doability
Doable — standard pH speciation for Ca(II) + EDTA at fixed I and T; supported by the pH_sweep pipeline and by SRD-46 constants for Ca–EDTA and EDTA protonation.

## Result
- System: Ca(II) 1.00 mM + EDTA 3.00 mM (3:1 ligand:metal excess), T = 25 °C, fixed ionic strength I = 0.1 M, redox excluded.
- Method: 1-D pH_sweep, pH 2.0–12.0, 101 points, converged 101/101 (calculated I range 0.0046–0.018 M — well below the target cap of 0.1 M, so activity corrections use the specified I).
- Included aqueous Ca species: Ca²⁺, [Ca(OH)]⁺, [Ca(EDTA)H]⁻, [Ca(EDTA)]²⁻; solid Ca(OH)₂(s) available but its saturation column is 0 across the entire pH range, so no precipitation is predicted at these totals.
- Key result at pH 8.5 (from the concentrations table): [Ca²⁺]_free = 4.51 × 10⁻⁹ M; [Ca(EDTA)]²⁻ = 1.000 × 10⁻³ M; [Ca(EDTA)H]⁻ ≈ 1.5 × 10⁻⁹ M; [Ca(OH)]⁺ ≈ 8 × 10⁻¹⁴ M. Ca-bound fraction = [Ca(EDTA)]²⁻ / Ca_T = 99.9994 % (i.e. essentially complete complexation; ~4.5 ppb of the calcium remains as free aquo ion).

## Analysis
**Dominance regions for calcium.** The verdict identifies just two dominant Ca forms across the whole scanned window: free Ca²⁺ from pH 2.0 to ~4.3, and [Ca(EDTA)]²⁻ from ~4.3 to 12.0, with the Ca²⁺ ↔ [Ca(EDTA)]²⁻ crossover bracketed at pH ≈ 4.29 (each ~49 %). Below pH 4.3 the EDTA is locked up as H₃EDTA⁻/H₂EDTA²⁻ (the protonated forms peak at low pH — H₂EDTA²⁻ reaches 94.2 % at pH 3.5), so the fully deprotonated EDTA⁴⁻ needed to form the chelate is vanishingly scarce and Ca²⁺ dominates by default. As pH rises, successive deprotonations (cumulative log β values from the reference table: 16.38, 10.19, 0.00 for H₂EDTA²⁻, HEDTA³⁻, EDTA⁴⁻) release EDTA⁴⁻, and because the Ca–EDTA formation constant (log β₁ = 10.65 for Ca²⁺ + EDTA⁴⁻ ⇌ [Ca(EDTA)]²⁻) is very large, the chelate captures essentially all of the calcium the moment enough deprotonated ligand is available. This is the classic "conditional-stability-driven" onset of chelation: the transition pH is set not by K_f but by the pKa ladder of the ligand.

**At pH 8.5 (the boiler-relevant condition).** The equilibrium is far past the transition. The concentrations file gives [Ca(EDTA)]²⁻ = 9.99994 × 10⁻⁴ M out of 1.000 × 10⁻³ M total Ca, so 99.9994 % of Ca is EDTA-bound and free [Ca²⁺] is 4.51 × 10⁻⁹ M (≈ 0.18 µg L⁻¹). The protonated chelate [Ca(EDTA)H]⁻ is negligible here (log β for Ca²⁺ + HEDTA³⁻ is 13.75, but at pH 8.5 HEDTA³⁻ itself is falling — it is the dominant free-EDTA form only through pH ~9.4 — and the proton on the chelate is lost well below this pH). Hydrolysis to [Ca(OH)]⁺ is thermodynamically insignificant (log β = −13.04); it never becomes a meaningful sink even at pH 12. Ca(OH)₂(s) does not saturate anywhere in the sweep at 1 mM Ca_T, consistent with its dissolution log K = −22.81 requiring much higher [Ca²⁺]·[OH⁻]² than is available once EDTA has scavenged the Ca.

**EDTA speciation and "wasted ligand" accounting.** With 3 mM EDTA and only 1 mM Ca, 1 mM of ligand is committed to [Ca(EDTA)]²⁻ (a fixed 33.3 % of ligand across the whole chelated region — this is the [Ca(EDTA)]²⁻ peak of 33.3 % at pH 11.4 in the ligand-fraction summary), and the remaining ~2 mM circulates as free EDTA protonation states: H₂EDTA²⁻ dominates 2.1–5.6, HEDTA³⁻ dominates 5.6–9.4, and EDTA⁴⁻ dominates 9.4–12.0. At pH 8.5 specifically the free-ligand pool is 1.74 mM HEDTA³⁻ + 0.26 mM EDTA⁴⁻ (plus trace H₂EDTA²⁻), i.e. ~2.0 mM of uncomplexed ligand still available to compete for other hardness ions (Mg²⁺, Fe, etc.) or scale-forming cations.

**Practical read for the antiscale screen.** For a boiler feed at pH 8.5 with 1 mM Ca hardness, EDTA at 3× stoichiometric excess sequesters Ca essentially quantitatively — free [Ca²⁺] is driven ~5 orders of magnitude below its total, far below any CaCO₃/CaSO₄ saturation threshold. The "waste" is the 1 mM of EDTA irreversibly tied up per mM of Ca; only the remaining ~2 mM is available for other hardness or transition-metal targets. If Ca is the only hardness ion of concern, a smaller EDTA:Ca ratio (say 1.1:1) would already give >99 % complexation at this pH, since the ligand is nearly fully deprotonated (HEDTA³⁻/EDTA⁴⁻) and the chelate log β is high; the 3× excess is only justified if competing cations or kinetic margin are needed. Note the caveats from the method briefing: these numbers hold at the fixed totals, T = 25 °C, and I = 0.1 M of the card; real boiler water is hotter and may include carbonate/sulfate, which are not in this system and would change both Ca-EDTA conditional stability and scaling saturation.

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
- [solver/Ca$+2_+_Ca$+0_+_EDTA_concentrations.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_concentrations.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_envelope_Ca$+2.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_envelope_Ca$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_envelope_L1.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_envelope_L1.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_frac_Ca.png](<solver/Ca$+2_+_Ca$+0_+_EDTA_frac_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_frac_L1.png](<solver/Ca$+2_+_Ca$+0_+_EDTA_frac_L1.png>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_frac_ligand.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_frac_ligand.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_frac_metal.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_frac_metal.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_log_conc.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_log_conc.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_log_conc.png](<solver/Ca$+2_+_Ca$+0_+_EDTA_log_conc.png>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_phase_balance_Ca.png](<solver/Ca$+2_+_Ca$+0_+_EDTA_phase_balance_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_run_params.json](<solver/Ca$+2_+_Ca$+0_+_EDTA_run_params.json>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_state_metrics.csv](<solver/Ca$+2_+_Ca$+0_+_EDTA_state_metrics.csv>)
- [solver/Ca$+2_+_Ca$+0_+_EDTA_verdict.md](<solver/Ca$+2_+_Ca$+0_+_EDTA_verdict.md>)
- [solver/topology_Ca$+2_+_Ca$+0_+_EDTA_Ca.json](<solver/topology_Ca$+2_+_Ca$+0_+_EDTA_Ca.json>)
- [verdict.json](<verdict.json>)
