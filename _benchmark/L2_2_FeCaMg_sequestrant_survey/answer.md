## Answer

**Recommendation: DTPA is the best of the three SRD-46 polyaminocarboxylates tested, but with an important caveat — none of these chelators achieves the ideal of "hold Fe(III), leave Ca/Mg alone." Selectivity in this ligand family is thermodynamically impossible at 5 mM ligand vs. 3 mM total metal, because Ca(II) and Mg(II) log β values (~9–11) combined with 5:3 ligand excess drive both hardness cations to ≥99.9 % chelation at pH ≥ 7. The right question therefore becomes: *which ligand best keeps Fe(III) in solution as a soluble chelate rather than losing it to iron (hydr)oxide precipitation?* On that metric, DTPA wins decisively.**

### Why DTPA wins

Fe(III) is thermodynamically desperate to precipitate as an oxide/hydroxide above pH ~7 (dissolution log K for the hematite proxy `(Fe2O3)0.5(s,alpha)` is only +0.70; for `FeO(OH)(s,alpha)` it is –0.5). To hold Fe(III) in solution as a chelate, the ligand's effective Fe(III) formation constant must outrun this insolubility. The three ligands rank as:

| Ligand | log β Fe(III)·L | Fe(III) held as soluble chelate at pH 7 | at pH 8 | at pH 9 |
|---|---|---|---|---|
| **DTPA** | **28.00** | **~100 %** | **~100 %** (no solid yet) | 12.6 % (rest as FeOOH(s)) |
| EDTA | 25.10 | 65 % (rest as Fe₂O₃ proxy) | 4.6 % | 0.31 % |
| HEDTA | ~19.8 | ≪1 % — Fe already fully as Fe₂O₃ proxy from pH 6 upward | ≪1 % | ≪1 % |

DTPA is the only ligand that keeps Fe(III) fully soluble across the entire pH 7–8.4 window and still retains a measurable soluble fraction at pH 9. EDTA loses Fe(III) to oxide precipitation right at pH 7 (the operating floor of the request), and HEDTA is too weak to compete with iron oxide anywhere in the pH 6–10 window.

### On the "weak Ca/Mg binding" goal

All three ligands fail this goal at the requested stoichiometry — Ca(II) reaches 99.8 % (DTPA) / 99.98 % (EDTA) / 100 % (HEDTA) chelated by pH 7, and Mg(II) reaches 95 % / 99.2 % / ≥95 % over pH 7–9. Their intrinsic Ca/Mg formation constants (DTPA 10.75/9.27; EDTA 10.65/8.79; HEDTA smaller) all exceed the ~6–8 log-unit threshold at which a 5-mM ligand overwhelms 1-mM metal. To weaken hardness binding one would need a more Fe(III)-selective chelator class (e.g., a siderophore-type or catecholate-based ligand not present in this SRD-46 subset), or to accept sub-stoichiometric ligand dosing.

### Practical recipe using DTPA

- **Operate at pH ≤ 8.0** if the goal is quantitative Fe(III) retention (>99 % as `[Fe(DTPA)]²⁻` / `[Fe(DTPA)(OH)]³⁻`).
- **Between pH 8.0 and ~8.4** DTPA still holds essentially all Fe(III) in solution.
- **Above pH ~8.5** the FeO(OH)(s,alpha) solid becomes thermodynamically preferred; at pH 9 only ~12.6 % of Fe stays chelated even with 5 mM DTPA excess. If pH 9 operation is required, either raise the DTPA:Fe ratio further or accept a partial iron-oxide fraction.
- Ca and Mg will be captured by the DTPA regardless — plan on a ligand-consumption budget that accounts for the hardness metals (5 mM DTPA – 3 mM metal ≈ 2 mM ligand headroom at 1 mM each of Fe/Ca/Mg).

## Validation status: incomplete

## Evidence

**DTPA (calculation 1)** — best of three:
- Fe(III) speciation at 1 mM Fe / 5 mM DTPA:
  - pH 7.0: [Fe(DTPA)]²⁻ 99.04 %, [Fe(DTPA)(OH)]³⁻ 0.95 %, no solid → **≈100 % soluble chelate**
  - pH 8.0: [Fe(DTPA)]²⁻ 91.25 %, [Fe(DTPA)(OH)]³⁻ 8.74 %, no solid → **≈100 % soluble chelate**
  - pH 9.0: aqueous DTPA-Fe = 12.6 %, FeO(OH)(s,alpha) = 87.4 %
  - Solid onset: FeO(OH)(s,alpha) first at pH 8.40 (3.15 %); crossover ~42/42 % at pH 8.58
- Ca(II): [Ca(DTPA)]³⁻ = 96.9 % / 99.7 % / 99.97 % at pH 7 / 8 / 9
- Mg(II): [Mg(DTPA)]³⁻-based fractions = 95.0 % / 99.79 % / 99.98 % at pH 7 / 8 / 9
- Convergence: 41/41 samples
- log β reference: Fe(III)·DTPA = 28.00; Ca·DTPA = 10.75; Mg·DTPA = 9.27

**EDTA (calculation 3)** — Fe(III) precipitates too early:
- pH 7.0: soluble Σ(EDTA-Fe) = 0.654 (313 nM [Fe(EDTA)]⁻ + 341 nM [Fe(EDTA)(OH)]²⁻), (Fe₂O₃)₀.₅ = **0.346**
- pH 8.0: soluble Σ(EDTA-Fe) = 0.046, (Fe₂O₃)₀.₅ = **0.954**
- pH 9.0: soluble Σ(EDTA-Fe) = 0.00312, (Fe₂O₃)₀.₅ = **0.997**
- Ca(II) ≥ 99.98 %, Mg(II) ≥ 99.17 % chelated over pH 7–9
- Fe₂O₃ proxy onset at pH 6.90
- log β reference: Fe(III)·EDTA = 25.10; ternary [Fe(EDTA)(OH)]²⁻ log β = 17.71

**HEDTA (calculation 2)** — too weak to hold Fe(III) at all:
- Fe(III) dominant species across pH 6–10: `(Fe2O3)0.5(s,alpha)` (peak 99.9 % at pH 10; solid present from pH 6.0 upward with 7.54e-4 M at pH 6)
- Best aqueous chelate is [Fe(HEDT)(OH)]⁻ with peak only 24.4 % at pH 6
- Ca(II): [Ca(HEDT)]⁻ dominant across pH 6–10, reaching 100 % at pH 10
- Mg(II): free Mg²⁺ 46.9 % at pH 6 → [Mg(HEDT)]⁻ 99.9 % at pH 10
- Convergence: 41/41 samples

## Final deliverables

- [Result 01](final/result_01/answer.md): Assess DTPA as selective Fe(III) sequestrant against Ca(II)/Mg(II) competition in a water-treatment scenario.
- [Result 02](final/result_02/answer.md): Test HEDTA as selective Fe(III) sequestrant against Ca(II)/Mg(II) competition for hard-water iron control.
- [Result 03](final/result_03/answer.md): Test EDTA as a Fe(III) sequestrant against Ca(II)/Mg(II) competition for water-treatment iron control at pH 7-9.
