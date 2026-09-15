## Doability
Doable — Cu(II)/NTA is fully represented in the SRD-46 free-energy card (H4NTA+ through NTA3-, [Cu(NTA)H], [Cu(NTA)]-, [Cu(NTA)2]4-, [Cu(NTA)(OH)]2-) and pH_sweep is a supported method.

## Result
- System: Cu(II) 1.00 mM total + NTA 5.00 mM total, aqueous, 25 °C, fixed ionic strength I = 0.1 M, redox excluded (Cu(II) only).
- Method: 1-D pH_sweep, pH 3.0–10.0, 71 grid points (Δ pH = 0.1).
- Convergence: 71/71 samples converged; residuals ~10⁻¹⁴, iterations = 4 throughout. Full evidentiary basis.

## Analysis
**Cu speciation is dominated end-to-end by two Cu–NTA chelates.** From the metal-fraction verdict, the 1:1 anionic chelate [Cu(NTA)]⁻ dominates from pH 3.0 to ≈5.93 (peak 98.9 % near pH 3.6), and the 1:2 chelate [Cu(NTA)₂]⁴⁻ dominates from ≈5.93 to 10.0 (peak 99.4 % near pH 8.8). The two chelates cross at pH ≈ 5.93 (each ~50 %). The minor proto-chelate [Cu(NTA)H] contributes only near the acid end (2.4 % at pH 3.0, 1.5 % at 3.5, <0.1 % by pH 5), and the mixed hydroxo chelate [Cu(NTA)(OH)]²⁻ stays ≤0.05 % over the entire window (frac_metal CSV).

**Free Cu²⁺ is suppressed at every pH in 3–10.** From `..._frac_metal.csv`, the Cu²⁺ fraction of total copper is:
- pH 3.0 : 6.90 × 10⁻⁴ (0.069 %)
- pH 3.5 : 2.05 × 10⁻⁴
- pH 4.0 : 6.30 × 10⁻⁵
- pH 5.0 : 5.75 × 10⁻⁶
- pH 6.0 and above: <10⁻⁶, dropping to <10⁻⁹ by pH 7 and negligible thereafter.

So with 1 mM Cu(II) total, [Cu²⁺]_free ≈ 7 × 10⁻⁷ M at the acidic extreme (pH 3) and drops by roughly a factor of 3 per 0.1 pH unit through pH 3–5, i.e. ~10⁴-fold suppression per two pH units. Hydrolysis species of Cu(II) (Cu(OH)⁺, Cu₂(OH)₂²⁺, Cu(OH)₂, Cu₃(OH)₄²⁺, HCuO₂⁻, CuO₂²⁻) are all <10⁻⁸ fractions across the window — NTA outcompetes hydroxide everywhere.

**Onset of appreciable free Cu²⁺ at low pH.** Even at pH 3.0 the free-Cu²⁺ fraction is only 0.069 %; it never reaches 1 % anywhere in 3–10. Chemically this is expected: NTA is 5× in excess and its high-pH fully deprotonated form (log β₁ = 12.7 for [Cu(NTA)]⁻; log β₂ = 17.4 for [Cu(NTA)₂]⁴⁻, from the reference-constants table) has to compete only against ligand protonation. The apparent free-Cu²⁺ minimum occurs where the ligand is fully deprotonated and 1:2 chelation is engaged (pH 6–10). Below pH 3 (outside the scan) NTA becomes protonated in earnest — the reference table gives cumulative protonation constants log β(H₁L) = 9.46, log β(H₂L) = 11.98, log β(H₃L) = 10.17, log β(H₄L) = 9.17, i.e. the conjugate-acid pKa of HNTA²⁻ ↔ NTA³⁻ is 9.46 and the successive pKa of H₂NTA⁻ is 2.52 — so genuine dissociation of Cu–NTA to appreciable free Cu²⁺ requires pH well below 3, outside the requested window.

**Why the 1:1 → 1:2 crossover sits at pH ≈ 5.93.** Below pH ~5 the free NTA³⁻ activity is throttled by protonation to HNTA²⁻ (which peaks at 79 % of ligand at pH 4.3, per the ligand block of the verdict), so only one NTA per Cu can be assembled and [Cu(NTA)]⁻ dominates. Once pH climbs past ~5 the pool of NTA³⁻ grows (log β for the second NTA on Cu is +4.7 relative to the first), and the second chelate ring closes, giving [Cu(NTA)₂]⁴⁻. The 50/50 point at pH ≈ 5.93 marks the pH where free [NTA³⁻] equals the value 10^(β₁−β₂) needed for the two chelates to be equimolar. Above pH 9.2 excess NTA is left over as free NTA³⁻ (56.8 % of ligand at pH 10) because Cu is only 1 mM and can bind at most 2 mM of ligand.

**Cu-hydroxide solids.** No Cu(I) or Cu(II) solid precipitates anywhere in pH 3–10. The columns for [(Cu₂O)₀.₅](s), CuO(s), and Cu(OH)₂(s) in `..._frac_metal.csv` are identically 0.0 at every sample from pH 3.0 through 10.0 (spot-checked pH 3–5.7; the metric CSV shows the same all the way to pH 10). Physically, NTA holds so much of the Cu(II) inventory as the [Cu(NTA)]⁻ / [Cu(NTA)₂]⁴⁻ chelates that the free Cu²⁺ activity is far below the solubility products of tenorite and Cu(OH)₂ — NTA masks Cu against hydroxide precipitation across the entire biologically and environmentally relevant pH range.

**Comparison hint vs Cu–EDTA.** Both ligands wipe out free Cu²⁺ over most of pH 3–10, but the NTA system is a two-chelate story (1:1 → 1:2 handoff near pH 6) rather than a single dominant 1:1 chelate, and NTA leaves slightly more free Cu²⁺ at the acidic end (~7 × 10⁻⁴ fraction at pH 3) because HNTA²⁻ protonation competes for the ligand more strongly than protonation of the more basic EDTA donors would.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_NTA_Cu.json>)
- [verdict.json](<verdict.json>)
