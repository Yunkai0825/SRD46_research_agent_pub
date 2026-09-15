Verdict: **supported**.

The calculation is consistent with the persisted solver artifacts:

- **Convergence**: state_metrics.csv confirms 52/61 samples converged, with pH 4.0–9.1 giving residuals ≤ ~1e-11 and pH 9.2–10.0 failing (residual O(1), converged=0). L1's exclusion of pH ≥ 9.2 as non-evidence is correct.
- **Precipitation onsets** in the verdict file match L1 exactly: Co(OH)₂ at pH 8.40, NiO at 8.70, CuO at 8.90 (L1 rounds these to 8.4/8.7/8.9).
- **Crossovers and dominant regions** in the verdict block match L1's chemical narrative: Cu²⁺↔[Cu(Gly)₂] at pH ≈ 4.53, Ni²⁺↔[Ni(Gly)]⁺ at pH ≈ 6.68, [Cu(Gly)₂] dominant across pH 5.2–9.2, Ni sequence Ni²⁺ → [Ni(Gly)]⁺ → [Ni(Gly)₂], Co mostly Co²⁺ up to pH 8.37.
- **Free-ion values** at pH 6/7/8 are consistent with the fraction-of-metal claims (e.g. Cu²⁺ ≈ 0.19% × 1 mM ≈ 1.85e-6 M at pH 6).
- **L1 correctly flags** the post-pH 9.2 "return to M²⁺" strings in the verdict as artifacts of unconverged cells.
- **Glycine pKa values** cited (9.57 amine, 2.33 carboxylate) are derivable from the μ° table shown in the verdict.

The discrimination narrative (Cu ≫ Ni > Co, best window pH 7–8, terminated by precipitation at pH ≥ 8.4) follows directly from the tabulated free-ion contrasts and precipitation onsets. No contradictions found.
