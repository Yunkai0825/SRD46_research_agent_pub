Verdict: supported.

The calculation's key claims were cross-checked against the solver verdict file and the Pb²⁺ component envelope:

- Run setup (21/21 converged, pH 6.0–8.0, I ≈ 0.044–0.046 M vs 0.1 M target, redox excluded, ZnO precipitation onset at pH 7.40 with 8.41e-5 M) matches the verdict file exactly.
- Pb speciation: envelope confirms Pb²⁺ fraction 0.9894 (pH 6) → 0.3626 (pH 7) → 0.02898 (pH 8), and the [Pb4(OH)4]⁴⁺ peak 65.8% at pH 7.3 and [Pb6(OH)8]⁴⁺ peak 70.9% at pH 8.0, with crossovers at pH ≈ 6.86 and ≈ 7.69 as cited. Free [Pb²⁺] values (9.89e-4, 3.63e-4, 2.90e-5 M) reproduce fraction × 1 mM.
- Zn speciation: verdict shows Zn²⁺ 100% at pH 6, ZnO 89.2% at pH 8, crossover ≈ 7.53, matching the report; free [Zn²⁺] values follow.
- Ca is entirely Ca²⁺ across the window (verdict).
- Pb–DMSA thermodynamics: the free-energy table lists only [Pb(meso)]²⁻ (single Pb-L1 species) with μ°_canon = +54.57 kJ/mol, consistent with the unfavourable log β = −5.56 cited; multiple Zn-L1 species are present as reported. The conclusion that DMSA does not chelate any of the three metals in this window, and that Pb speciation is governed by hydroxo condensation while Zn is governed by ZnO precipitation, follows directly from the artifacts.

No contradictions or invented numbers were found; the "database is limiting" caveat is properly framed as a comment on the SRD-46 parameter set rather than as a solver output.
