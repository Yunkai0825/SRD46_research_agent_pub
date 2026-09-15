Verdict: **supported**.

The calculation is consistent with the solver artifacts:

- The verdict.md confirms 41/41 convergence, T=25 °C, fixed-I=0.1 M with calculated I in 0.022–0.027 M, pH 6.0–8.0, redox excluded, and no solid saturation (Ca(OH)₂(s) and Zn(OH)₂(α) at the −50 floor).
- Dominant-species peaks match exactly: Pb → [Pb(DTPA)]³⁻ 100.0% at pH 8.0; Zn → [Zn(DTPA)]³⁻ 99.9% with [Zn(DTPA)H]²⁻ 8.3% shoulder at pH 6.0; Ca → [Ca(DTPA)]³⁻ 99.7% with [Ca(DTPA)H]²⁻ 20% and free Ca²⁺ 12% at pH 6.0.
- Ligand ledger matches: H₂DTPA³⁻ 41.5% at pH 6.0, HDTPA⁴⁻ 25.1% and each M(DTPA) ≈ 20% at pH 8.0; dominance crossover at pH 7.8.
- log_conc.csv rows corroborate the free-metal table (pH 6.0: log[Pb²⁺]≈−11.81, log[Zn²⁺]≈−11.24, log[Ca²⁺]≈−3.92; pH 7.0: ≈−13.72 / −13.12 / −5.68 within rounding). The selectivity ratios computed by L1 follow directly from these columns.
- The qualitative conclusion — DTPA does not selectively discriminate Pb²⁺ from Zn²⁺ (ratio ≈ 0.25 across pH 6–8), but strongly discriminates both from Ca²⁺ — follows correctly from the data and the log β values quoted from the reference table.

No contradictions or invented numbers were found; the fixed-I caveat and honest presentation of the last-row sample are appropriate. Verdict committed as `supported`.
