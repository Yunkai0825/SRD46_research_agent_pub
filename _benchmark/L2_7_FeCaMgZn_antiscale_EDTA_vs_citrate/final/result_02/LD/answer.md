Verdict: **supported**.

The calculation is consistent with the persisted solver artifacts. Key checks:

- Convergence and grid: verdict.md confirms 101/101 converged over pH 2.0–12.0, 25 °C, fixed I = 0.1 M, redox excluded, with totals [Fe³⁺] = 1.00e−3 M and [citrate] = 3.00e−3 M — matching the report.
- Solid selection: verdict.md explicitly reports α-hematite dominant over pH 2.0–12.0 with peak 100.0% at pH 8.9. The frac_metal.csv rows at pH 2.0–3.0 already show hematite fractions of 0.984–0.985, corroborating the "98.4% at pH 2.0" and full precipitation window claims.
- Species inventory: the free-energy species table lists exactly the four Fe-citrate aqueous species L1 sums at pH 8.5, plus the four candidate ferric solids with the log β values L1 quotes (hematite +0.70, goethite −0.50, Fe(OH)₃(s) −3.20, amorphous Fe(OH)₃ −4.84 — as derived from μ° divided by −RT ln10).
- Citrate ladder: the reported crossovers (H3Cit→H2Cit⁻ at pH 2.7, H2Cit⁻→HCit²⁻ at pH 4.0, HCit²⁻→Cit³⁻ at pH 5.1) match the verdict's "Dominant species by pH region" exactly.
- Practical conclusion (citrate cannot keep Fe(III) soluble at pH 8.5 under these conditions) follows directly from the ~100% hematite fraction and the trace Fe-citrate sum.

No contradictions or unsupported numerical claims were found; the report is an accurate reading of the artifacts.
