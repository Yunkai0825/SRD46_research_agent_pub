## Doability
Doable and executed: a 1-D pH sweep over pH 6.0-8.0 for Pb(II)/Zn(II)/Ca(II) (1 mM each) with 5 mM meso-2,3-dimercaptosuccinic acid (DMSA) at 25 °C and I ≈ 0.1 M, with redox excluded.

## Result
- System: Ca(II) + Pb(II) + Zn(II) + DMSA (labeled `meso-Dithiotartaric acid`, L1) in the SRD-46 card.
- Method: `pH_sweep`, 21 points, all converged (21/21). Calculated I range 0.0436-0.0460 M (below the 0.1 M target — the fixed-I mode did not force additional inert salt, so activity corrections are self-consistent with the free ions only).
- One solid appears: ZnO precipitates starting at pH 7.4 (8.4e-5 M) and grows to 8.9e-4 M at pH 8.0. No Ca or Pb solid forms in-window.

## Analysis

**A striking negative result: DMSA, as parameterized in SRD-46, does not chelate any of the three metals over pH 6-8.**

*Ligand protonation.* The card lists four cumulative protonation constants for L1 (relative to the fully deprotonated tetra-anion `L1^4-`): log β for H4L = +4.00, H3L^- = +1.60, H2L^2- = -1.86, HL^3- = -11.50. The stepwise pKa's derived from these (pKa1 ≈ 2.40 for H4L↔H3L, pKa2 ≈ 3.46, pKa3 ≈ 9.64, pKa4 ≈ 11.50) belong to the two carboxylates and two thiols. Two features are decisive: (i) the fully deprotonated L1^4- form has log β = 0.00, meaning the card treats L1^4- as the reference and the *neutral* H4L as spontaneously formed with β = 10^4 at unit H+; (ii) above pH ~5 the ligand pool is almost entirely `meso-Dithiotartaric acid` written as the neutral fully deprotonated reference form (5.0e-3 M free at every sampled pH). In other words the card's log β for the metal-ligand complexes is defined against a ligand form (L1^4-) whose actual concentration is essentially the full 5 mM, so the reported metal-L1 log β values act on a huge free-ligand reservoir.

*Pb(II).* Even so, Pb-DMSA binding is negligible. The only Pb-L1 species in the card is `[Pb(meso)]^2-` with log β = -5.56 — i.e. formation of the complex from Pb^2+ + L1^4- has β ≈ 10^-5.6, which is *unfavourable*. The computed [Pb(meso)^2-] stays between 2.7e-13 (pH 6) and 7.8e-15 M (pH 8) — twelve orders of magnitude below total Pb. Pb chemistry is instead controlled entirely by hydrolysis: dominant Pb^2+ from pH 6.0-6.9, then the polynuclear [Pb4(OH)4]^4+ from 6.9-7.7 (peak 65.8% at pH 7.3), then [Pb6(OH)8]^4+ from 7.7-8.0 (peak 70.9% at pH 8.0). Crossovers: Pb^2+↔[Pb4(OH)4]^4+ at pH ≈ 6.86 and [Pb4(OH)4]^4+↔[Pb6(OH)8]^4+ at pH ≈ 7.69. Free [Pb^2+] falls from 9.89e-4 M (pH 6) → 3.63e-4 M (pH 7) → 2.90e-5 M (pH 8), a 34-fold drop driven purely by polynuclear hydroxo condensation, not by chelation.

*Zn(II).* Zn-DMSA species (`Zn(meso)H^-`, `Zn2(meso)2H^3-`, `Zn2(meso)2^4-`, `Zn(meso)2^6-`, `Zn2(meso)2(OH)^5-`) all remain below 10^-13 M across the window. Zn^2+ dominates from pH 6.0-7.6 (100% at pH 6), then ZnO precipitates and takes 89.2% of total Zn by pH 8.0. Free [Zn^2+] tracks 1.00e-3 M (pH 6) → 9.87e-4 M (pH 7) → 5.41e-5 M (pH 8), with the fall past pH 7.5 driven by ZnO(s), not DMSA.

*Ca(II).* Ca^2+ is 100% of Ca throughout; DMSA does not touch it (no Ca-L1 species in the card) and [Ca(OH)]^+ is negligible.

*Pb-selectivity ratios* (free divalent aquo cations):

| pH | [Pb^2+] (M) | [Zn^2+] (M) | [Ca^2+] (M) | [Pb^2+]/[Zn^2+] | [Pb^2+]/[Ca^2+] |
|---:|---:|---:|---:|---:|---:|
| 6.0 | 9.894e-4 | 9.996e-4 | 1.000e-3 | 0.990 | 0.989 |
| 7.0 | 3.626e-4 | 9.874e-4 | 9.9999e-4 | 0.367 | 0.363 |
| 8.0 | 2.898e-5 | 5.407e-5 | 9.9999e-4 | 0.536 | 0.029 |

The apparent [Pb^2+]/[Ca^2+] < 1 and [Pb^2+]/[Zn^2+] ≤ 1 are entirely artifacts of Pb hydrolysis (siphoning Pb into Pb4/Pb6 hydroxo clusters) and Zn precipitation (siphoning Zn into ZnO). DMSA plays no role.

*Chemical verdict on the DTPA-vs-DMSA question.* The premise of the sweep — that DMSA's dithiol soft-donor set should preferentially bind soft Pb(II) over borderline Zn(II) and hard Ca(II) — cannot be tested with the current SRD-46 card, because the card's Pb-DMSA thermodynamics (a single unfavourable `Pb(meso)^2-` with log β = -5.56, no protonated Pb-DMSA analogue of `Zn(meso)H^-`, and no polynuclear Pb-DMSA species) does not reproduce the well-known strong Pb-DMSA affinity from the pharmacology literature. In this model Pb "selectivity" is nil: Pb ends up sequestered by hydroxide, not by DMSA, and the free Pb^2+ suppression that the ligand should deliver is absent. Practically, if these are the only Pb-L1 parameters available in SRD-46, DMSA cannot be evaluated as a Pb-selective chelator inside this toolkit — the *database* is the limiting factor, not the underlying chemistry. Any comparison to DTPA on this basis would be misleading.

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
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_concentrations.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_concentrations.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_Ca$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_Ca$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_L1.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_L1.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_Pb$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_Pb$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_Zn$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_envelope_Zn$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_L1.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_L1.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_ligand.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_ligand.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_metal.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_metal.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_Pb.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_Pb.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_Zn.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_frac_Zn.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_log_conc.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_log_conc.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_log_conc.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_log_conc.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_phase_balance_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_phase_balance_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_phase_balance_Pb.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_phase_balance_Pb.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_phase_balance_Zn.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_phase_balance_Zn.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_run_params.json](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_run_params.json>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_state_metrics.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_state_metrics.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_verdict.md](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_verdict.md>)
- [solver/topology_Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_Ca.json](<solver/topology_Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_meso_Dithiotartaric_acid_Ca.json>)
- [verdict.json](<verdict.json>)
