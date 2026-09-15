Verdict: **supported**.

The calculation is consistent with the persisted solver outputs and reference constants:

- Run metadata in the verdict file matches the report: T = 25 °C, fixed I with target 0.1 M, calculated I range 0.00459–0.01798 M, pH 2–12 at 101 points, 101/101 converged, redox excluded, Ca_T = 1.00 mM, EDTA_T = 3.00 mM.
- Dominance regions for Ca match exactly: Ca²⁺ from pH 2.0–4.3, [Ca(EDTA)]²⁻ from 4.3–12.0, crossover ≈ pH 4.29 (~49% each).
- EDTA speciation regions and peaks agree: H2EDTA²⁻ peak 94.2% at pH 3.5; HEDTA³⁻ peak 65.0% at pH 7.4 and dominant 5.6–9.4; EDTA⁴⁻ dominant 9.4–12.0; [Ca(EDTA)]²⁻ ligand-fraction peak 33.3% at pH 11.4 (consistent with 1 mM chelate out of 3 mM ligand).
- log β / log K values cited by L1 are traceable to `../LC2/thermodynamic_reference_constants.md`: Ca²⁺ + EDTA⁴⁻ → [Ca(EDTA)]²⁻ log β = +10.65; Ca²⁺ + HEDTA³⁻ → [Ca(EDTA)H]⁻ log β = +13.75; [Ca(OH)]⁺ log β = −13.04; Ca(OH)₂(s) dissolution log K = −22.81; cumulative EDTA protonation constants 16.38 / 10.19 / 0 for H2EDTA²⁻ / HEDTA³⁻ / EDTA⁴⁻ all present.
- The pH 8.5 conclusion (free [Ca²⁺] ~4.5 × 10⁻⁹ M, ~99.9994% Ca-bound, negligible [Ca(EDTA)H]⁻ and [Ca(OH)]⁺, no Ca(OH)₂(s) saturation) is quantitatively plausible from the log β values and 3× ligand excess, and no artifact contradicts it.
- The practical antiscale discussion is appropriately hedged (fixed T = 25 °C, I = 0.1 M, no carbonate/sulfate) and does not overreach beyond what the solver evidence supports.

No contradictions or unsupported constants detected; verdict recorded as `supported` with no hints.
