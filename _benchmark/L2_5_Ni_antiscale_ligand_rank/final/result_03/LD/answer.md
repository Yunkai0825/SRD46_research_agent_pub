Verdict: **supported**.

The calculation's load-bearing claims all check out against the persisted solver artifacts:

- **Convergence and setup** — verdict.md confirms 71/71 samples converged, fixed-I mode (target 0.1 M; realised 8.9e-5–7.0e-3 M), pH 4.0–11.0, redox excluded, Ni_total = 1.00e-3 M, L1(ammonia)_total = 1.00e-2 M.
- **Precipitation onset** — verdict.md lists first Ni(OH)2(s) sample at pH 7.50 with 7.32e-5 M solid, exactly as reported.
- **pH 9 speciation** — frac_metal.csv row pH 9.000 gives Ni(OH)2 = 0.99650, Ni2+ = 8.471e-4, [Ni(Ammo)]2+ = 1.613e-3, [Ni(Ammo)2]2+ = 8.264e-4, [Ni(OH)]+ = 2.06e-5, [Ni(OH)2](aq) = 5.18e-5, [Ni(OH)3]- = 8.47e-7, matching the report's fractions and the ~8.5e-7 M free Ni2+ figure.
- **Crossovers** — verdict.md's speciation analysis reports Ni2+↔Ni(OH)2 at pH ≈ 7.63 (~47% each) and [Ni(Ammo)]2+↔Ni(OH)2 at pH ≈ 7.50 (~8% each), and ammonia HAmmonia+↔Ammonia at pH ≈ 9.3, all consistent with the narrative.
- **Practical framing** — the conclusion that ammonia does not suppress Ni(OH)2 scaling at pH 9 with 10:1 NH3:Ni follows directly from the fraction data (solid dominates ≥98% above ~pH 8.5).

No contradictions or unsupported numerical claims were found. Verdict `supported` has been committed.
