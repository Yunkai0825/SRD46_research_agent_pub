## Answer

Titrating 10 mM acetic acid (HAc) with NaOH gives a classic weak-acid/strong-base curve governed by a single equilibrium, H⁺ + Ac⁻ ⇌ HAc, with log β = +4.56 (i.e. **pKa(HAc) = 4.56**). Three regions structure the curve:

- **Initial acidic region (before base is added).** The 10 mM HAc solution sits near pH ≈ 3.4, where >97 % of the acetate is protonated. Acetic acid is a weak acid, so only a small fraction dissociates on its own.
- **Buffer region (half-neutralisation).** As NaOH converts HAc into Ac⁻, the pH rises slowly and passes through the half-neutralisation point exactly at **pH ≈ 4.56 = pKa**. The speciation grid confirms this: HAc/Ac⁻ = 51.7/48.3 at pH 4.5 and 45.9/54.1 at pH 4.6, so the 50/50 crossover interpolates to 4.56. The chemically useful **buffer window is pH ≈ 3.6–5.6** (pKa ± 1). Inside this window the two conjugate forms coexist in significant amounts — added acid or base is consumed by shifting the HAc/Ac⁻ ratio rather than changing free [H⁺], which is precisely what makes acetate a good buffer around pH 4.6.
- **Equivalence-point region.** By pH ~6.7 the acetate is already ≥99.3 % deprotonated, and by pH 7.5 it is essentially fully Ac⁻. The equivalence point — where the added NaOH has stoichiometrically converted all HAc to sodium acetate — is set by the hydrolysis of acetate itself: Ac⁻ + H₂O ⇌ HAc + OH⁻. For 10 mM acetate the standard weak-acid/strong-base estimate gives **pH_eq ≈ 7 + ½(pKa + log C) = 7 + ½(4.56 − 2.00) ≈ 8.3**, i.e. weakly basic. This value sits comfortably inside the >99.99 % Ac⁻ plateau the sweep resolves, consistent with the model. Past the equivalence point the pH climbs sharply toward strong-base behaviour (excess OH⁻), while the acetate speciation is already saturated at Ac⁻.

No precipitate forms anywhere on the curve (NaOH(s) fraction is 0 across the sweep, and sodium acetate is highly soluble), so the titration is a purely aqueous acid–base process throughout.

## Evidence
- pKa from card: "log β = +4.56 for the reaction H⁺ + Ac⁻ ⇌ HAc; this is the single-protonation constant of the conjugate base, i.e. pKa(HAc) = 4.56."
- Buffer crossover: "HAc and Ac⁻ crossing majority between pH 4.5 (HAc = 51.68 %, Ac⁻ = 48.32 %) and pH 4.6 (HAc = 45.93 %, Ac⁻ = 54.07 %) … the 50/50 crossover essentially at pH ≈ 4.56."
- Buffer window: "pKa ± 1, i.e. pH ≈ 3.6–5.6 … at pH 3.6, HAc/Ac⁻ ≈ 89/11; at pH 5.6, ≈ 8/92."
- Approach to equivalence: "Ac⁻ reaches 90.3 % at pH 5.5, 96.7 % at pH 6.0, 99.33 % at pH 6.7, and 99.97 % by pH 7.5."
- Equivalence pH estimate: "pH ≈ 7 + ½(pKa + log C) = 7 + ½(4.56 − 2.00) ≈ 8.3 … squarely inside the sweep's Ac⁻ ≥ 99.99 % plateau."
- Convergence: 101/101 grid points converged over pH 2.0–12.0 at 25 °C.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute the acid-base speciation of 10 mM acetic acid across pH 2-12 at 25 C to identify the buffer region (pKa) and equivalence-point pH.
