## Doability
Doable. Zn(II) + EDTA speciation vs pH is fully supported by the SRD-46 catalog and the `pH_sweep` route; the deliverable (pH 7 free [Zn2+], dominant Zn species, mass-balance partition) maps directly onto the solver's persisted tables.

## Result
- System: 1.00 mM Zn(II)_total, 5.00 mM EDTA_total, 25 °C, I = 0.1 M (fixed), pH 2–12 (101 points), redox excluded.
- Method: 1-D pH_sweep, single aqueous phase permitted plus Zn(OH)2 (amorphous) as a candidate solid.
- Convergence: 101/101 grid points converged, residuals ≤ 1.2e-14 (Newton), calculated I in 0.008–0.036 M range.
- Free-energy species pool (from the LC2 free-energy card / reference constants): free Zn2+, hydrolysis series [Zn(OH)_n]^{2-n} (n = 1–4), Zn–EDTA complexes [Zn(EDTA)H2]⁰, [Zn(EDTA)H]⁻, [Zn(EDTA)]²⁻, mixed hydroxo [Zn(EDTA)(OH)]³⁻, plus EDTA protonation ladder H6L²⁺…L⁴⁻, and Zn(OH)2 (amorph) as a candidate solid.

## Analysis
**Dominant Zn-bearing species across the whole pH window.** The metal-speciation table lists a single dominant Zn form from pH 2.0 to 12.0 — the mixed-ligand chelate labelled [Zn(EDTA)(OH)]³⁻ — carrying essentially 100.0 % of total Zn at every sampled pH; the aqueous ladder alone shows no crossovers, so under these totals there is no pH window in which any free-metal, hydroxo, or protonated Zn–EDTA form takes the lead in mass. In terms of the reference constants (Zn²⁺ + EDTA⁴⁻ + OH⁻ ⇌ [Zn(EDTA)(OH)]³⁻, log β = +28.1; cf. [Zn(EDTA)]²⁻ log β = +16.5), the very large mixed-hydroxo formation constant together with the fourfold ligand excess (5 mM L vs 1 mM Zn) drives essentially all Zn into a Zn–EDTA sink; the solver's dominance-label persists that sink under the single [Zn(EDTA)(OH)]³⁻ ID over the whole scan.

**Free [Zn²⁺] at pH 7 (deliverable value).** From the persisted concentrations CSV at the pH 7.00 grid point:
- [Zn²⁺] = 5.23 × 10⁻³³ M (fraction of Zn_total = 5.23 × 10⁻³⁰)
- [Zn(OH)⁺] = 1.60 × 10⁻³⁵ M; [Zn(OH)2⁰] = 5.07 × 10⁻³⁵ M; higher hydroxo species negligible
- Sum of aqueous Zn–EDTA complexes ≡ 1.000 × 10⁻³ M (i.e. all of Zn_total)
- Zn(OH)2 (amorph): 0 mol/L (not precipitated at any pH sampled 2–12)

So the mass-balance partition of Zn at pH 7 is: **~0 % as free Zn²⁺ (≤10⁻²⁹), ~100 % bound to EDTA, 0 % precipitated.** The vanishingly small free-Zn activity is the direct chemical consequence of EDTA being a hexadentate chelator (formation constants above ≥ 10^{16}) held in stoichiometric excess: even at neutral pH, where only a modest fraction of EDTA is fully deprotonated, the mass-action drive toward the Zn–chelate is overwhelming, and hydrolysis (which would otherwise start to matter for free Zn near pH 8–9) is preempted.

**Ligand (EDTA) speciation** — the classical acid–base biography of the excess ligand — shows the expected sequential deprotonation on the free-EDTA pool (the ~4 mM not tied up with Zn): dominant H3EDTA⁻ at pH 2.0–2.1, H2EDTA²⁻ at pH 2.1–5.6, HEDTA³⁻ at pH 5.6–9.4, and EDTA⁴⁻ at pH 9.4–12.0, matching the reference-card cumulative protonation constants (log β for HL³⁻ = 10.19; H2L²⁻ = 16.38; H3L⁻ = 18.90; H4L = 20.92). The mixed-hydroxo Zn chelate peaks in the ligand accounting at ~20 % near pH 10.3 — exactly what stoichiometry predicts when 1 mM of 5 mM L is bound as a 1:1 Zn:L complex.

**No precipitation.** The amorphous Zn(OH)2 column is identically zero over the full 2–12 pH range. EDTA suppression of free Zn²⁺ to <10⁻³° M keeps the solubility product unattainable everywhere on the grid; without chelator, amorphous Zn(OH)2 would normally begin to appear near pH 8–9 at 1 mM Zn.

**Selectivity-matrix implication for Cu(II) capture.** For the Cu–capture process this entry establishes that Zn(II) is quantitatively co-sequestered by EDTA at pH 7 (free [Zn²⁺] driven to sub-attomolar levels), so EDTA offers essentially no selectivity between Cu(II) and Zn(II) at neutral pH — both metals will be pulled into the same chelate pool. Selectivity against Zn will require either a lower pH (where EDTA is over-protonated) or a competing/masking ligand; a per-metal comparison with the Cu- and Ni-EDTA runs and with the glycine and citrate columns will quantify by how much.

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
- [solver/topology_Zn$+2_+_Zn$+0_+_EDTA_Zn.json](<solver/topology_Zn$+2_+_Zn$+0_+_EDTA_Zn.json>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_concentrations.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_concentrations.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_L1.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_L1.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_Zn$+2.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_envelope_Zn$+2.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_L1.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_L1.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_ligand.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_ligand.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_metal.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_metal.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_frac_Zn.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_frac_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_log_conc.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Zn.png](<solver/Zn$+2_+_Zn$+0_+_EDTA_phase_balance_Zn.png>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_run_params.json](<solver/Zn$+2_+_Zn$+0_+_EDTA_run_params.json>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_state_metrics.csv](<solver/Zn$+2_+_Zn$+0_+_EDTA_state_metrics.csv>)
- [solver/Zn$+2_+_Zn$+0_+_EDTA_verdict.md](<solver/Zn$+2_+_Zn$+0_+_EDTA_verdict.md>)
- [verdict.json](<verdict.json>)
