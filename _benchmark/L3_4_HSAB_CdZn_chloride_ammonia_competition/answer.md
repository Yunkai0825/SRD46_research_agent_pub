## Answer

**Hypothesis (falsifiable form).** In a single pot containing Cd(II), Zn(II), Cl⁻ and NH₃ together, HSAB predicts that (i) the *chloro-bound fraction of Cd will exceed the chloro-bound fraction of Zn*, and (ii) the *ammine (or hard-donor: ammine/hydroxo/oxide) fraction of Zn will exceed the corresponding fraction of Cd*. If the joint equilibrium instead shows Zn dominating the chloro ladder or Cd dominating the ammines, HSAB is refuted for this system.

**Test result — HSAB is confirmed, and rather cleanly.** With 1 mM Cd(II) + 1 mM Zn(II), 0.1 M Cl⁻ and 0.1 M NH₃ (total) held at pH 7, 25 °C, I = 0.1 m, the converged joint speciation partitions the two metals in opposite senses:

- **Cd(II)** stays essentially fully aqueous and pours into the chloro ladder. [Cd(Cl)]⁺ alone is the single dominant Cd species; summed chloro-complexes account for ~54 % of the Cd budget, free Cd²⁺ another ~35 %, and ammine complexes only ~7.5 %. No Cd solid precipitates. Chloro-bound Cd outranks ammine-bound Cd by roughly 7 : 1.
- **Zn(II)** does the opposite. About 92 % of the Zn drops out as a ZnO(s) precipitate — a hard oxide sink. Of the ~8 % that remains dissolved, ammine complexes (~11 % of dissolved Zn) outrank chloro-complexes (~1.7 %) by ~7 : 1, even though Cl⁻ is present at ~200× the free-NH₃ concentration. Zn's chloro-bound fraction of the total budget is under 0.2 %.

**Chemical interpretation.** Two effects reinforce the HSAB pattern. First, the intrinsic binding constants already favour it: for Cd(II), log β₁(CdCl⁺) is competitive with log β₁(Cd(NH₃)²⁺), and once mass-action is applied at pH 7 (where NH₃ is >95 % protonated to NH₄⁺, leaving only ~5.5 × 10⁻⁴ M free NH₃ against ~0.1 M free Cl⁻) the chloro ladder wins decisively for Cd. For Zn(II) the ordering is reversed at the constant level — log β₁(Zn(NH₃)²⁺) ≈ +2.33 versus log β₁(ZnCl⁺) ≈ −0.30, i.e. Zn binds NH₃ ~400× more strongly per ligand than Cl⁻ — so even the small free-NH₃ pool beats the abundant chloride. Second, the harder Zn²⁺ is also the more oxophilic cation, so at pH 7 it preferentially forms the ZnO/Zn(OH)₂ solid, removing most of the metal from the aqueous competition altogether; softer Cd²⁺ does not hydrolyse under these conditions and remains available for Cl⁻. The net picture — soft Cl⁻ clinging to soft Cd(II) as chloro-complexes, hard O/N donors (oxide, ammine, water) taking hard Zn(II) — is exactly the qualitative split HSAB predicts, and the two 7 : 1 ratios (Cd Cl-over-NH₃, Zn NH₃-over-Cl) make the inversion between the two metals unambiguous.

## Evidence

- Convergence: "all 3 pH samples converged=1 with residual ~1e-12 (cells.csv)".
- Cd predominance: "[Cd(Chlo)]+ (Dms_1) as the dominant Cd form across the whole band" (Cd verdict, pH 6.9–7.1).
- Cd partition (from cells.csv, pH 7, basis 1 mM): "Chloro complexes: [Cd(Chlo)]+ 4.5e-4, [Cd(Chlo)2] 9.1e-5, [Cd(Chlo)3]- 2.0e-5 → sum ~5.6e-4, i.e. ~54% of total Cd"; "Aquo Cd2+: 3.6e-4, ~35%"; "Ammine complexes … sum ~7.8e-5, ~7.5%"; "no Cd(OH)2 or CdO precipitates (n_s columns are 0)".
- Zn predominance: "ZnO(inactive) (Dms_1) as the dominant Zn form across the whole band" (Zn verdict).
- Zn partition: "n_s[ZnO(inactive)] = 9.22e-4 mol at pH 7 … ~92% of the 1 mM Zn budget drops out"; "Zn2+ 6.8e-5 (~7% of total Zn, ~87% of the aqueous Zn pool)"; "Ammine … sum ~8.5e-6 (~11% of dissolved Zn)"; "Chloro: [Zn(Chlo)]+ 1.25e-6, [Zn(Chlo)2] 7.6e-8 → ~1.7% of dissolved Zn".
- Mass-action driver for Cd: "free ammonia at pH 7 is only ~5.5e-4 M … whereas free Cl- is ~0.1 M".
- Intrinsic driver for Zn: "log_beta1(ZnCl+) = -0.30 while log_beta1(Zn(NH3)+) = +2.33, i.e. Zn(II) binds NH3 more than 400x more strongly (per ligand) than Cl-".

## Final deliverables

- [Result 01](final/result_01/answer.md): Test the HSAB prediction that soft Cd(II) monopolises chloro-complexes while harder Zn(II) is pushed toward ammine/aquo species when both metals share one pot with chloride and ammonia.
