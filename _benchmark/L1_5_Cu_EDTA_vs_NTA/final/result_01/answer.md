## Doability
Doable — Cu(II) + EDTA is a canonical SRD-46 speciation problem, well-suited to a 1-D pH sweep at fixed T and I.

## Result
- **System:** Cu²⁺ 1.00 mM total, EDTA (L1) 5.00 mM total (5:1 ligand excess).
- **Conditions:** 25 °C, ionic strength fixed at 0.1 M (calculated range 0.012 – 0.034 M within the run), redox excluded (only Cu(+II) subtotal is nonzero).
- **Method:** `pH_sweep`, pH 3.0 → 10.0, 71 points (Δ pH = 0.1).
- **Convergence:** 71/71 for every reported component (`state_metrics`; verdict header). All samples are evidence.
- **Included species carrying Cu:** Cu²⁺, [Cu(OH)]⁺, [Cu₂(OH)₂]²⁺, [Cu(OH)₂](aq), HCuO₂⁻, [Cu₃(OH)₄]²⁺, CuO₂²⁻, [Cu(EDTA)H₂], [Cu(EDTA)H]⁻, [Cu(EDTA)]²⁻, [Cu(EDTA)(OH)]³⁻, plus solids Cu₂O(s), CuO(s), Cu(OH)₂(s), Cu(s). No solid precipitates form in this window (all solid columns of `frac_metal.csv` are 0.0 from pH 3 to 10).

## Analysis
### Fraction of free Cu²⁺ vs Cu–EDTA complexes
`frac_metal.csv` shows that the total Cu is almost entirely tied up in Cu–EDTA complexation across the whole pH 3 – 10 window. The mixed hydroxo–EDTA complex **[Cu(EDTA)(OH)]³⁻ carries essentially 100 % of the Cu at every sampled pH** (fraction = 1.000000 to six decimals from pH 3.0 through pH 9.0+ in the table). The remaining Cu-EDTA species ([Cu(EDTA)]²⁻, [Cu(EDTA)H]⁻, [Cu(EDTA)H₂]) sit at fractions ≤ 10⁻¹⁶ throughout, and free hydrolysis products (Cu(OH)⁺, Cu(OH)₂, Cu₂(OH)₂²⁺, etc.) are even smaller.

**Free Cu²⁺ is suppressed to negligible values everywhere:**
- pH 3.0: x(Cu²⁺) ≈ 1.68 × 10⁻²¹ (⇒ [Cu²⁺] ≈ 1.7 × 10⁻²⁴ M)
- pH 5.0: x(Cu²⁺) ≈ 1.90 × 10⁻²⁷
- pH 7.0: x(Cu²⁺) ≈ 4.35 × 10⁻³²
- pH 9.0: x(Cu²⁺) ≈ 6.12 × 10⁻³⁶

So the ratio [Cu–EDTA] : [Cu²⁺] is ≥ 10²¹ across the entire scan. In practical terms **no dissociation of the Cu–EDTA complex occurs anywhere in pH 3 – 10**; there is no pH within the window below which free Cu²⁺ or protonated Cu–EDTA species become significant. Even at the acidic edge (pH 3.0) free Cu²⁺ is 21 orders of magnitude below the complexed pool. Any onset of dissociation would lie well below pH 3, outside the requested range.

### Dominant Cu species per pH region
From `frac_metal.csv` and the verdict's dominance analysis for the Cu²⁺ subtotal:

| pH region | Dominant Cu species | Fraction of total Cu |
|---|---|---|
| 3.0 – 10.0 | **[Cu(EDTA)(OH)]³⁻** | ≈ 1.000 (100 %) |

There are no crossovers on the Cu axis in this window — one species owns the entire Cu budget from pH 3 to pH 10.

### Why [Cu(EDTA)(OH)]³⁻ wins everywhere
The reference table gives the cumulative formation constants (from free Cu²⁺, free EDTA⁴⁻, free OH⁻, free H⁺):
- log β([Cu(EDTA)]²⁻) = **+18.78**
- log β([Cu(EDTA)H]⁻) = +21.88 (from Cu²⁺ + HEDTA³⁻)
- log β([Cu(EDTA)H₂]) = +23.88 (from Cu²⁺ + H₂EDTA²⁻)
- log β([Cu(EDTA)(OH)]³⁻) = **+30.18** (from Cu²⁺ + OH⁻ + EDTA⁴⁻)

The SRD-46 card thus assigns the ternary hydroxo-EDTA complex an ~11.4 log-unit advantage in β over the simple [Cu(EDTA)]²⁻ chelate. Combined with the 5× ligand excess and the very strong Cu–EDTA binding, this makes [Cu(EDTA)(OH)]³⁻ the sole significant Cu form throughout the neutral-to-alkaline window and, because β is so large, it remains dominant even in the acidic regime where free EDTA is heavily protonated. This is why no acid-driven dissociation is seen down to pH 3.

(Note: quantitatively the very high weight put on [Cu(EDTA)(OH)]³⁻ in this SRD-46 card is unusually strong compared with common textbook Cu-EDTA descriptions that emphasise [Cu(EDTA)]²⁻ as the dominant form near neutral pH. The result reported here reflects the constants in the LC2 free-energy card exactly.)

### EDTA-side speciation (context)
From the ligand-side dominance in the verdict (`frac_ligand`): with only 20 % of the EDTA bound to Cu at most (peak of the Cu-EDTA complex is 20.0 % of L1 at pH 4.2, consistent with 1 mM Cu ÷ 5 mM EDTA), the free ligand pool follows classic EDTA protonation:
- pH 3.0 – 5.6 → **H₂EDTA²⁻** dominates the free ligand (peak 77.1 % of L1 at pH 3.8)
- pH 5.6 – 9.4 → **HEDTA³⁻** dominates (peak 78.0 % at pH 7.4)
- pH 9.4 – 10.0 → fully deprotonated **EDTA⁴⁻** takes over (peak 65.8 % at pH 10.0)

These ligand transitions do not translate into Cu-side transitions here because the excess EDTA plus the very large Cu-binding constants keep essentially all Cu locked in [Cu(EDTA)(OH)]³⁻ regardless of the protonation state of the free ligand pool.

### Practical implication
Under these conditions (1 mM Cu, 5 mM EDTA, I = 0.1 M, 25 °C) EDTA acts as an essentially perfect masking agent for Cu(II) across the entire pH 3 – 10 window: [Cu²⁺]_free is ≲ 10⁻²⁴ M at pH 3 and drops further as pH rises. Copper hydroxide solids do not appear (all solid fractions are 0), so EDTA also prevents Cu(OH)₂(s)/CuO(s) precipitation in this range.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_EDTA_Cu.json>)
- [verdict.json](<verdict.json>)
