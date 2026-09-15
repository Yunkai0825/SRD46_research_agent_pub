Verdict: **supported**.

The calculation's key quantitative claims all line up with the on-disk artifacts I inspected:

- Convergence "101/101" and the fixed I = 0.1 M sweep with calculated I ≈ 0.0023–0.0138 M are reproduced verbatim in `..._verdict.md`.
- Dominant-species verdict "pH 2.0–12.0 → Ca2+" and the empty crossover list confirm L1's "no crossover in 2–12" statement.
- Species peaks reported by L1 (Ca²⁺ peak 99.8% at pH 2.0; [Ca(Citr)]⁻ peak 28.5% metal-side at pH 9.1 and 9.5% ligand-side at pH 9.1) match the verdict's peak table exactly.
- The three solid columns (Ca(OH)₂, [CaH(Citric acid)](s), [Ca₃(Citric acid)₂](s)) are 0 across the frac_metal rows sampled — consistent with L1's "no precipitation, including at pH 8.5" finding.
- Component totals (1.00 mM Ca²⁺, 3.00 mM citrate) and the free-energy card (including log β = −13.04-consistent μ° for [Ca(OH)]⁺ and the two Ca–citrate solids) match L1's description of the LC2 card.
- Ligand ladder crossovers (H3→H2⁻ 2.7, H2⁻→HCitr²⁻ 4.0, HCitr²⁻→Citr³⁻ 5.1) are the verdict's ligand-region boundaries.

The interpretation (Ca²⁺ never loses dominance because of the modest log β₁₁₀ = +3.45 combined with the I = 0.1 M activity penalty on the ×6 charge product) is a reasonable explanation of the numerical outcome, and the boiler-water/EDTA-vs-citrate framing is presented as chemical inference, not as an artifact-grounded quantitative claim. The caveats about ionic-strength scaling and unmodelled carbonate/sulfate are appropriate.

No contradictions found; no revision required.
