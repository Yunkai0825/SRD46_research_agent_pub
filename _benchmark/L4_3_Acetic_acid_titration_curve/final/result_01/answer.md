## Doability
Doable — acetic acid / acetate is a single-ligand acid–base system well within the SRD-46 catalog, and a pH sweep at fixed 25 °C, low I is exactly what `pH_sweep` computes.

## Result
- System: 10 mM total acetate (H-acetate / acetate⁻) with Na⁺ counter-ion set (no other metal chemistry active; Na⁺ total = 0).
- Method: `pH_sweep`, 101 grid points from pH 2.0 to 12.0.
- Conditions: T = 25.0 °C, ionic mode fixed, target I = 1e-3 M (calculated I range 1.5e-5 – 5e-3 M), redox excluded.
- Convergence: 101/101 samples converged for the acetate ligand block (and for all three Na oxidation-state blocks, which are trivially empty since their totals are zero).
- Included aqueous acetate species: HAcetic acid (HAc) and Acetic acid (Ac⁻). The reference-constants table gives log β = +4.56 for the reaction H⁺ + Ac⁻ ⇌ HAc; this is the single-protonation constant of the conjugate base, i.e. pKa(HAc) = 4.56.

## Analysis
**Buffer region and pKa.** The `frac_ligand.csv` table shows HAc and Ac⁻ crossing majority between pH 4.5 (HAc = 51.68 %, Ac⁻ = 48.32 %) and pH 4.6 (HAc = 45.93 %, Ac⁻ = 54.07 %). Linear interpolation of these bracketing samples places the 50/50 crossover essentially at pH ≈ 4.56, which coincides exactly with the card's log β = 4.56 for H⁺ + Ac⁻ ⇌ HAc. That number *is* the acid dissociation pKa of acetic acid — the pH at which the carboxyl proton is half dissociated — and it defines the useful buffer window, conventionally pKa ± 1, i.e. pH ≈ 3.6–5.6. Within that window both HAc and Ac⁻ are present at appreciable fractions (from the CSV: at pH 3.6, HAc/Ac⁻ ≈ 89/11; at pH 5.6, ≈ 8/92), so added strong acid or base is consumed by interconverting the two forms rather than changing free [H⁺] steeply. The verdict's dominance summary ("pH 2.0–4.6 → HAcetic acid; pH 4.6–12.0 → Acetic acid") is the same statement in grid-bracketed form.

**Acid side (pH < pKa).** Below pH ≈ 3, acetate is >97 % protonated (99.71 % HAc at pH 2.0, 97.13 % at pH 3.0). Chemically, the solution's proton activity exceeds Kₐ⁻¹ by more than an order of magnitude, so the equilibrium H⁺ + Ac⁻ ⇌ HAc is driven fully to the neutral molecular acid. A 10 mM acetic acid solution with no added base sits in this regime; its equilibrium pH (not scanned here as an independent variable, but implied by mass/charge balance) is about 3.4, i.e. still on the HAc-dominant side of the pKa, which is why acetic acid is only a weak acid.

**Base side and equivalence point.** Above the pKa, deprotonation proceeds monotonically: Ac⁻ reaches 90.3 % at pH 5.5, 96.7 % at pH 6.0, 99.33 % at pH 6.7, and 99.97 % by pH 7.5. From pH 8 upward HAc is below 3.4 × 10⁻⁴ of the total and the ligand is, for all practical purposes, fully deprotonated (>99.999 % Ac⁻ by pH 9). The equivalence point of a NaOH titration of 10 mM HAc — where stoichiometric base has converted essentially all HAc to Ac⁻ — therefore falls in the mildly basic region. A textbook charge-balance estimate for 10 mM sodium acetate gives pH ≈ 7 + ½(pKa + log C) = 7 + ½(4.56 − 2.00) ≈ 8.3; this pH lies squarely inside the sweep's "Ac⁻ ≥ 99.99 %" plateau, consistent with the model. The sweep itself does not compute the titration trajectory (it scans pH as an independent axis rather than added NaOH), but it confirms that at and beyond the equivalence pH the acetate speciation is completely on the Ac⁻ side.

**What the curves do *not* say.** No solid phase appears in the ligand fraction table across the whole range (NaOH(s) fraction is 0 everywhere, as expected with [Na⁺]_total = 0 in this ligand-only model), so there is no precipitation to worry about. Because the redox axis is excluded and Na totals are zero, the Na⁰/Na⁺/Na²⁺ blocks in the verdict are empty by construction and carry no chemical information — they are placeholders from the metal-slot machinery, not evidence of sodium chemistry.

**Practical reading.** (i) Acetate buffers are effective near pH 4.6 (± ~1 pH unit); (ii) the half-neutralisation point of a NaOH titration of acetic acid gives pKa directly and equals 4.56 for this dataset; (iii) the equivalence point of that titration lies in weakly basic territory (~pH 8.3 for 10 mM), well inside the Ac⁻-dominant plateau the sweep resolves from ~pH 6.7 upward.

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
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_concentrations.csv](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_concentrations.csv>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_envelope_L1.csv](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_envelope_L1.csv>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_frac_L1.png](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_frac_L1.png>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_frac_ligand.csv](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_frac_ligand.csv>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_frac_metal.csv](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_frac_metal.csv>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_log_conc.csv](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_log_conc.csv>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_log_conc.png](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_log_conc.png>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_run_params.json](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_run_params.json>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_state_metrics.csv](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_state_metrics.csv>)
- [solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_verdict.md](<solver/Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_verdict.md>)
- [solver/topology_Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_Na.json](<solver/topology_Na$+1_+_Na$+0_+_Na$+2_+_Acetic_acid_Na.json>)
- [verdict.json](<verdict.json>)
