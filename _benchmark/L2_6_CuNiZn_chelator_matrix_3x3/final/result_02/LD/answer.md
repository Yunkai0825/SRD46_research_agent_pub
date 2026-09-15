Verdict: **supported**.

The calculation is consistent with the persisted solver artifacts:

- The verdict file confirms 51/51 samples converged at fixed I = 0.1 M, T = 25 °C, pH 2–12, with `[Cu(EDTA)(OH)]³⁻` peaking at 100 % at pH 9.4 and dominating the entire pH 2.0–12.0 window — exactly as L1 states.
- Component totals in the verdict match L1's system description: Cu²⁺ = 1.00 mM, EDTA = 5.00 mM, Cu(0) and Cu(I) totals = 0 (redox excluded).
- The free-energy species table lists all the Cu-EDTA and Cu-hydroxo species L1 discusses; the μ° values are consistent with the log β figures L1 quotes for `[Cu(EDTA)]²⁻` and `[Cu(EDTA)(OH)]³⁻`, and the resulting dominance argument (K·[OH⁻] with Δlog β = 11.4) is sound.
- The `frac_metal.csv` rows at low pH show `[Cu(EDTA)(OH)]³⁻` = 1.0 with residual Cu²⁺ fractions of order 10⁻¹⁸ at pH 2, decreasing sharply with pH, fully consistent with L1's ~10⁻³² fraction (~10⁻³⁵ M free Cu²⁺) at pH 7.
- The EDTA acid-base ladder L1 reports (H₂EDTA²⁻ 2.2–5.6, HEDTA³⁻ 5.6–9.4, EDTA⁴⁻ above 9.4; HEDTA³⁻ peak 78.0 % at pH 7.4) matches the verdict's dominance regions exactly.
- L1's caveat about the unusually low free [Cu²⁺] driven by the SRD-46 log β for `[Cu(EDTA)(OH)]³⁻` is an honest disclosure and does not overreach.

No unsupported numerical claims or conclusions were identified.
