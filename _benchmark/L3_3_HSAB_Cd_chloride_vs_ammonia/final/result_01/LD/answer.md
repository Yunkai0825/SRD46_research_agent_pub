Verdict: **supported**.

The calculation's quantitative claims at pH 7 match `frac_metal.csv` exactly:

- Cd²⁺ 0.3153 (31.5%)
- [Cd(Chlo)]⁺ 0.3861 (38.6%)
- [Cd(Chlo)₂] 0.2809 (28.1%)
- [Cd(Chlo)₃]⁻ 0.01754 (1.75%)
- [Cd(OH)]⁺ 1.53 × 10⁻⁴
- [Cd(OH)₂]⁰ 9.66 × 10⁻⁸

Free [Cd²⁺] ≈ 3.15 × 10⁻⁴ M is correctly derived from 0.3153 × 1 mM total. Convergence 51/51 and precipitation onset at pH 8.80 for β-Cd(OH)₂(s) are both confirmed by `verdict.md`. The requested pH 7 sits comfortably in the sub-saturated, fully converged regime. Ionic strength held near 0.05 M (fixed-I target 0.1 M) — L1 quotes I = 0.1 M consistent with the run parameter, and the small deviation does not affect the qualitative story. The HSAB narrative and the ordering of chloro-species are consistent with the data.
