## Doability
Doable. Mg(II)/citrate with hydrolysis and brucite are catalogued in SRD-46; a pH_sweep at fixed I=0.1 M, 25 C, redox excluded is the correct method.

## Result
System: [Mg2+]_tot = 1.00e-3 M, [citrate]_tot = 3.00e-3 M (3:1 L:M), T = 25 C, I = 0.1 M (fixed), redox excluded, pH 2.0–12.0 in 101 points. Sweep converged 101/101 (state_metrics/verdict). Ionic-strength actual span 2.3e-3 to 1.4e-2 M (well under the target I set for activity corrections). One precipitation event flagged: brucite Mg(OH)2(s) first appears at pH 10.20 (3.24e-4 M). No aqueous Mg-hydroxo polymer ever becomes significant.

## At pH 8.5 (frac_metal + log_conc CSVs, row pH=8.500)
- Free Mg2+ mole fraction of Mg total: 0.7232 → [Mg2+] = 10^-3.1408 = 7.23e-4 M.
- [Mg(Citr)]- (Mg·L^3-, fully deprotonated citrate complex): 0.2763 → 2.76e-4 M (log C = -3.559).
- [Mg(Citr)H] (protonated ternary): 6.27e-6 (6.3e-9 M); [Mg(Citr)H2]+: 3.14e-11 (negligible).
- [Mg(OH)]+: 5.56e-4 fraction (5.6e-7 M); dimer/tetramer hydroxo species <1e-6 fraction.
- **Mg-bound (sum of all Mg–citrate aqueous complexes) = 0.2763 + 6.3e-6 + 3.1e-11 ≈ 0.2763, i.e. 27.6 % of Mg total is citrate-bound; 72.3 % remains as free Mg2+.** No solid at pH 8.5 (brucite column = 0).

## Analysis
**Dominant Mg speciation regions (envelope over pH 2–12).** From the fraction table the Mg(II) partitioning splits into three regimes:
- pH 2.0 – ~10.2: free hexaaquo **Mg2+** is dominant. Its fraction falls monotonically from 0.999 at pH 2 to 0.724 at pH 8–9 as citrate progressively deprotonates and forms [Mg(Citr)]-. Because Mg2+ is a hard, weakly complexing s-block ion, even with 3× ligand excess the free-ion fraction never drops below ~0.72 in the pre-precipitation window.
- pH ~5 – 10.2: the **[Mg(Citr)]-** complex (Mg2+ + fully deprotonated citrate L^3-, log β = +3.43 from the reference table) is the only appreciable bound form, peaking at 0.276 near pH 8.3–9. Its rise mirrors the citrate speciation ladder — H3Cit (pKa1 chain), H2Cit-, HCit^2-, Cit^3- successively dominate up through pH ≈ 5.1, after which free Cit^3- (fraction ≈ 1.00 of citrate at pH ≥ 6) is available to bind. The protonated ternaries [Mg(Citr)H] and [Mg(Citr)H2]+ (log β = +7.50 and +10.70) contribute only a shoulder at pH 3–5 (peaks ~1.7% and ~0.4% of Mg) — modest because Mg2+ binds the carboxylates so weakly that even with three protons still on the ligand the affinity is low.
- pH ≥ 10.24: **brucite Mg(OH)2(s)** takes over. The verdict marks the Mg2+↔brucite crossover at pH ≈ 10.24 (each ~41%) and [Mg(Citr)]-↔brucite at pH ≈ 10.17 (each ~21%). By pH 12 brucite holds >99.95% of Mg. This is the classic hydroxide dissolution equilibrium (log β = -16.86 for Mg2+ + 2 OH- ⇌ Mg(OH)2(s)); at 1 mM Mg it saturates just above pH 10, and 3 mM citrate is far too weak a competitor to keep Mg in solution.

**Practical answers for the boiler-water antiscale screen.**
1. Mg-bound fraction at pH 8.5 = **0.276 (27.6%)**; free [Mg2+] = **7.2e-4 M** (log[Mg2+] = -3.14). Threefold citrate excess sequesters only about one Mg in four — citrate is a **poor Mg-hardness chelant** at practical boiler-side pH.
2. Precipitation window: brucite deposits from **pH ≈ 10.2 upward** at these totals; between the target pH 8.5 and pH ≈ 10.2 the solution is undersaturated. If pH climbs into the 10–11 range (common in HP boiler water), 3 mM citrate suppresses brucite only marginally (co-existence at pH 10.17), so citrate should be viewed as a Ca-selective agent rather than a Mg antiscalant.
3. There is no pH window in 2–12 where citrate binds >30% of Mg — the intrinsic Mg2+/citrate log β of only +3.43 (vs, e.g., >4.5 for Ca2+/citrate and much higher for transition metals) is the limiting chemistry. For competitive-hardness screening this establishes the Mg baseline; a stronger phosphonate/polymer or a larger ligand:metal ratio would be needed to meaningfully reduce free [Mg2+] below ~5e-4 M near pH 8.5.

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
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_concentrations.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_concentrations.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_envelope_L1.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_envelope_L1.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_envelope_Mg$+2.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_envelope_Mg$+2.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_L1.png](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_L1.png>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_ligand.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_ligand.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_metal.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_metal.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_Mg.png](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_frac_Mg.png>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_log_conc.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_log_conc.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_log_conc.png](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_log_conc.png>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_phase_balance_Mg.png](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_phase_balance_Mg.png>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_run_params.json](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_run_params.json>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_state_metrics.csv](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_state_metrics.csv>)
- [solver/Mg$+2_+_Mg$+0_+_Citric_acid_verdict.md](<solver/Mg$+2_+_Mg$+0_+_Citric_acid_verdict.md>)
- [solver/topology_Mg$+2_+_Mg$+0_+_Citric_acid_Mg.json](<solver/topology_Mg$+2_+_Mg$+0_+_Citric_acid_Mg.json>)
- [verdict.json](<verdict.json>)
