Verdict: supported.

The calculation is consistent with the solver outputs. Spot checks:

- `frac_ligand.csv` confirms the pKa crossover bracket: HAc = 0.51676 / Ac⁻ = 0.48324 at pH 4.5 and HAc = 0.45929 / Ac⁻ = 0.54071 at pH 4.6, giving a 50/50 point at pH ≈ 4.56, matching the log β = 4.56 cited from the reference constants.
- The dominance regions in the verdict (pH 2.0–4.6 HAc; pH 4.6–12.0 Ac⁻) reproduce what L1 reports.
- Acid-side fractions (99.71% HAc at pH 2.0, 97.13% at pH 3.0) and base-side fractions (>96.7% Ac⁻ by pH 6.0) match the CSV.
- Convergence: 101/101 samples converged per the verdict header; Na blocks are trivially empty (totals = 0), as L1 correctly notes.
- NaOH(s) fraction is 0 throughout — no precipitation, consistent with L1's statement.
- The equivalence-point estimate (~pH 8.3 from 7 + ½(pKa + log C)) is a textbook side-calculation clearly labeled as not being scanned as an independent titration axis; it lies within the >99.99% Ac⁻ plateau the sweep does resolve, so it is not a solver claim being over-read.

No contradictions or invented numbers detected.
