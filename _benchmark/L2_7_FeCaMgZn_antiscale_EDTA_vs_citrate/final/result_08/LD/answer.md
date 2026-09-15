Verdict: supported.

The calculation is consistent with the solver artifacts I examined:

- Convergence (101/101 for the Zn sub-problem, redox excluded, I = 0.1 M fixed, 25 °C) matches the verdict header.
- The dominant-species map (Zn²⁺ pH 2.0–4.4, [Zn(Citr)]⁻ pH 4.4–7.0, [Zn₂(Citr)₂(OH)₂]⁴⁻ pH 7.0–12.0) and the individual peak fractions (Zn²⁺ 99.9 % at pH 2.0; [Zn(Citr)H] 10.8 % at pH 3.9; [Zn(Citr)]⁻ 54.6 % at pH 5.0; [Zn(Citr)₂]⁴⁻ 37.8 % at pH 6.2; [Zn₂(Citr)₂(OH)₂]⁴⁻ 36.8 % at pH 7.1) reproduce the verdict block exactly.
- Citrate ladder (H₃Cit 2.0–2.7, H₂Cit⁻ 2.7–4.0, HCit²⁻ 4.0–5.1, Cit³⁻ 5.1–12.0) matches the ligand speciation table.
- The Zn²⁺ ↔ [Zn(Citr)]⁻ crossover at pH ≈ 4.35 (≈ 43 % each) is exactly what the verdict reports.
- Precipitation onset at pH 7.10 with 1.15 × 10⁻⁴ M matches the verdict's precipitation entry, and the Zn envelope fractions collapsing from ~100 % soluble at pH 6.6 to well below 1 % by pH 8.4 is consistent with L1's claim that ~99.6 % of Zn is in the solid phase at pH 8.5.
- The qualitative practical conclusion — citrate poorly sequesters Zn at boiler pH 8.5, meaningful Zn-citrate binding is confined to pH ~4.5–7.0, ligand pool remains essentially free — follows directly from the envelope and precipitation evidence.

Minor caveats flagged as hints (non-blocking):
1. The verdict's precipitation label is "ZnO (inactive)" and the free-energy species table lists only "Zn(OH)₂ (amorphous)" as the solid, yet L1 confidently names ZnO as the precipitating phase and quotes specific log β values (ZnO −9.61, Zn(OH)₂ am −12.25) that I did not locate in the artifacts I opened. The identity of the controlling solid is worth double-checking against `../LC2/thermodynamic_reference_constants.md`.
2. L1 also cites log β(Zn(OH)₂,aq) = −15.8 and log β(Zn(OH)₃⁻) = −28.1 as free numbers; these are not traced to a specific artifact line in the
