## Doability
Doable — Ni(II) and glycine are both in SRD-46; standard 1-D pH_sweep at fixed totals.

## Result
- **System**: 1.00 mM Ni(II) + 10.0 mM glycine, 25 °C, I = 0.1 M (fixed-I mode)
- **Method**: `pH_sweep`, 21 points across pH 6.5–7.5, redox excluded (only Ni(II) is populated; Ni(0/III/IV) subtotals = 0)
- **Convergence**: 21/21 samples converged
- **Saturation**: `[Ni(OH)2](s)` fraction = 0 across the window — no precipitation; solution remains fully aqueous at 1 mM Ni_T

## Analysis

### Ni distribution at pH 7.00 (from `_frac_metal.csv`)

| Ni species | Fraction of Ni_T | [species] (M) |
|---|---:|---:|
| Ni²⁺ (aquo) | 4.62 × 10⁻² | 4.62 × 10⁻⁵ |
| [Ni(Gly)]⁺ | 3.479 × 10⁻¹ | 3.48 × 10⁻⁴ |
| [Ni(Gly)₂]⁰ | 5.402 × 10⁻¹ | 5.40 × 10⁻⁴ |
| [Ni(Gly)₃]⁻ | 6.57 × 10⁻² | 6.57 × 10⁻⁵ |
| [Ni(OH)]⁺ | 1.12 × 10⁻⁵ | 1.12 × 10⁻⁸ |
| [Ni(OH)₂]⁰ | 2.82 × 10⁻⁷ | 2.82 × 10⁻¹⁰ |
| [Ni(OH)₃]⁻ | 4.62 × 10⁻¹¹ | ~5 × 10⁻¹⁴ |
| [Ni₄(OH)₄]⁴⁺ | 9.7 × 10⁻¹⁴ | negligible |

**Ni-glycinate complexes carry ~95 % of the nickel** at pH 7, with the bis-glycinate [Ni(Gly)₂]⁰ (54 %) already dominant over the mono-complex [Ni(Gly)]⁺ (35 %); a small tris-complex [Ni(Gly)₃]⁻ tail (6.6 %) is present, and free aquo Ni²⁺ is reduced to **4.6 × 10⁻⁵ M (4.6 % of total Ni)** — a ~22-fold suppression relative to the ligand-free case where all 1 mM would remain as Ni²⁺(aq).

### Why the speciation looks this way

The binding chemistry is set by glycine's zwitterion-to-glycinate deprotonation. From the reference table, the conjugate-acid pKa of HGly (⁺H₃N–CH₂–COO⁻ → H₂N–CH₂–COO⁻ + H⁺, i.e. the `x = 1` protonation `H + L ⇌ HL` with log β = 9.57) is **pKa ≈ 9.57**. At pH 7 the ligand pool is therefore >99 % HGly (zwitterion) — the ligand-side dominance table confirms HGly dominates 6.5–7.5 — so only ~10⁻²·⁵⁷ of glycine exists as the free amine-carboxylate anion Gly⁻ that actually binds Ni²⁺. Even so, the stepwise formation constants are large enough (cumulative log β₁ = 5.74, log β₂ = 10.58, log β₃ = 14.10, all vs free Gly⁻) that with 10-fold excess ligand the equilibrium is pulled well past the mono-complex.

The stepwise increments log K₁ = 5.74, log K₂ = 4.84, log K₃ = 3.52 show the usual monotonically decreasing pattern (statistical + electrostatic penalty as anionic Gly⁻ ligates a progressively less-charged centre), which is why [Ni(Gly)₂]⁰ is the sweet spot at 10 mM total glycine and pH 7 while the tris-complex only becomes competitive above pH ~7.4 (crossover [Ni(Gly)]⁺ ↔ [Ni(Gly)₃]⁻ bracketed at pH 7.35–7.40, verdict quotes ≈ 7.38).

Hydrolysis is completely outcompeted: [Ni(OH)]⁺ sits at ~10⁻⁸ M and [Ni(OH)₂](s) never saturates (Ksp implied by log β = −12.8 for the dissolution row demands [Ni²⁺][OH⁻]² > 10⁻¹²·⁸; here [Ni²⁺][OH⁻]² ≈ 4.6 × 10⁻⁵ × (10⁻⁷)² = 4.6 × 10⁻¹⁹, ~6 orders of magnitude undersaturated). Glycine therefore both speciates the metal and keeps it in solution.

### Practical Irving–Williams reading

The active free-metal concentration [Ni²⁺] is buffered down from 1 mM to ~46 µM by glycine at pH 7. This is the correct quantity to feed into an Irving–Williams comparison across the M(II) series with the same ligand and pH — the ordering Mn < Fe < Co < **Ni** < Cu > Zn reflects how strongly each M²⁺ is drawn into ML/ML₂ complexes, and here Ni(II)'s log β₂ = 10.58 is large enough that under mild ligand excess most of the nickel is already sequestered as the bis-glycinate, consistent with Ni sitting near the top of the Irving–Williams series (only Cu(II) with glycine would drive [M²⁺]_free lower still). At higher pH the shift toward [Ni(Gly)₂]⁰ and [Ni(Gly)₃]⁻ continues (bis-complex peaks 63.5 % at pH 7.4), and free Ni²⁺ falls another decade by pH 7.5 (0.61 %).

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
