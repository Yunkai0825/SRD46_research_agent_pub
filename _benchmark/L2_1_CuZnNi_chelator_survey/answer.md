## Answer

**Recommendation: ethylenediamine (en) is the best Cu(II)-selective chelator of the three SRD-46 candidates surveyed** (EDTA, ethylenediamine, glycine) when Cu(II), Ni(II) and Zn(II) are all present at 1 mM in a shared pot with 5 mM ligand at pH 6–8, I = 0.1 M.

Ranking by discrimination of Cu²⁺ from the free Ni²⁺ and Zn²⁺ pools:

| Ligand | [Ni²⁺]/[Cu²⁺] @ pH 7 | [Zn²⁺]/[Cu²⁺] @ pH 7 | Verdict |
|---|---|---|---|
| **Ethylenediamine** | **5.9 × 10⁵** | **9.2 × 10⁶** | Excellent Cu selectivity, no precipitation |
| Glycine | 6.1 × 10³ | 1.5 × 10⁴ | Modest selectivity; Zn(OH)₂(s) forms above pH ≈ 7.05 (solubility artefact) |
| EDTA | 0.76 (i.e. Ni is actually held *more* tightly than Cu) | 1.2 × 10² | **Not** Cu-selective — a saturating, near-indiscriminate sequestrant |

**Why ethylenediamine wins — the chemistry.** All three ligands sit on the Irving–Williams series, so Cu(II) is intrinsically favoured, but the *magnitude* of the discrimination depends on how much of the log β difference survives the neutral-pH proton competition:

- **EDTA is too strong and too flat.** The dominant species for every metal across pH 6–8 is the *ternary* [M(EDTA)(OH)]³⁻, with log β = +30.18 (Cu), +30.30 (Ni), +28.10 (Zn). Because Ni actually edges out Cu by 0.12 log units in this ternary form, EDTA fails outright at separating Cu from Ni. With 2.5-fold ligand excess every metal is >99.99 % locked up and the free pools differ by ≤2 log units — chemically indiscriminate. This is why "EDTA titrates all divalents together" is a textbook truth.
- **Glycine works, but modestly, and Zn precipitates.** Cu's bis-glycinate β₂ (log β₂ = 15.10) is ~4.5 log units above Ni's (10.58) and ~6 log units above Zn's (9.19), which is enough to drive Cu into [Cu(Gly)₂] essentially quantitatively (99.6 % at pH 8) while Ni climbs the ligand ladder only sluggishly and Zn hardly binds. But Zn's weak binding lets Zn(OH)₂(α) nucleate at pH ≈ 7.05, so the apparent Cu/Zn selectivity above that pH is a solubility artefact, not a competition victory.
- **Ethylenediamine gets the largest usable log β spread.** Cu(II)'s d⁹ Jahn–Teller-stabilised square-planar [Cu(en)₂]²⁺ has log β₂ = 19.60 versus 13.44 (Ni) and 10.64 (Zn) — a Cu/Ni gap of 6.2 log units and Cu/Zn gap of 8.9 log units, the largest of the three ligands. Crucially, all these log β values are set at real occupancy, no solid phase saturates anywhere in pH 6–8, and Cu is already ≥95 % bound at pH 6 while Ni and Zn are barely engaged. As pH rises past pKa₂ ≈ 7.1 of H₂en²⁺, newly liberated en spills first to Ni (its stronger of the two remaining partners) and only above pH 7.6 to Zn — the Irving–Williams cascade playing out in real time.

**Quantitative justification at the recommended operating point (pH 7.0, 5 mM en, 1 mM each metal, 25 °C, I = 0.1 M):**
- [Cu²⁺]_free ≈ 8.4 × 10⁻¹¹ M (Cu is 99.99999 % bound as [Cu(en)₂]²⁺)
- [Ni²⁺]_free ≈ 5.0 × 10⁻⁵ M (only ~95 % complexed)
- [Zn²⁺]_free ≈ 7.7 × 10⁻⁴ M (only ~23 % complexed; no precipitation)
- **Cu is discriminated from Ni by ~5.9 × 10⁵ and from Zn by ~9.2 × 10⁶ in free-ion activity.**

At pH 8 the discrimination widens further (Ni/Cu ≈ 1.2 × 10⁶, Zn/Cu ≈ 1.3 × 10⁸) and still no solid forms — this is a robust window for a Cu(II)-selective mask across the entire pH 6–8 target range.

## Evidence

**EDTA (final/result_01)**
- Verdict: [Cu(EDTA)(OH)]³⁻, [Ni(EDTA)(OH)]³⁻, [Zn(EDTA)(OH)]³⁻ each dominant at 100 % across pH 6–8.
- log β (ref. table): +30.18 (Cu), +30.30 (Ni), +28.10 (Zn) → "Δlog β = 30.18 − 30.30 = −0.12, i.e. Ni is actually bound very slightly more strongly than Cu".
- Free-ion ratios pH 6–8: [Zn²⁺]/[Cu²⁺] ≈ 1.2 × 10² (constant); [Ni²⁺]/[Cu²⁺] ≈ 0.76.

**Ethylenediamine (final/result_02)**
- log β₂ = 19.60 (Cu), 13.44 (Ni), 10.64 (Zn) — from thermodynamic reference table.
- Free [M²⁺] at pH 7.0: [Cu²⁺] = 8.42 × 10⁻¹¹ M, [Ni²⁺] = 4.96 × 10⁻⁵ M, [Zn²⁺] = 7.73 × 10⁻⁴ M.
- Selectivity: "[Ni²⁺]/[Cu²⁺] = 5.9 × 10⁵ and [Zn²⁺]/[Cu²⁺] = 9.2 × 10⁶ at pH 7"; rising to 1.2 × 10⁶ and 1.3 × 10⁸ at pH 8.
- Cu fraction bound: 99.99 % at pH 6, ≥99.99999 % at pH 7–8. No solids form anywhere.

**Glycine (final/result_03)**
- log β₂ = 15.10 (Cu), 10.58 (Ni), 9.19 (Zn).
- Free [M²⁺] at pH 7.0: [Cu²⁺] = 4.97 × 10⁻⁸ M, [Ni²⁺] = 3.02 × 10⁻⁴ M, [Zn²⁺] = 7.56 × 10⁻⁴ M.
- Selectivity: "[Ni²⁺]/[Cu²⁺] ≈ 6.1 × 10³ and [Zn²⁺]/[Cu²⁺] ≈ 1.5 × 10⁴ at pH 7".
- Zn(OH)₂(α) precipitates from pH ≈ 7.05 upward (96 % of Zn as solid at pH 8) — apparent Cu/Zn discrimination above pH 7 is a solubility artefact.

## Final deliverables

- [Result 01](final/result_01/answer.md): Evaluate EDTA as a Cu(II)-selective chelator versus Zn(II) and Ni(II) in a shared aqueous pot at near-neutral pH.
- [Result 02](final/result_02/answer.md): Evaluate ethylenediamine as a Cu(II)-selective chelator over Ni(II) and Zn(II) in one shared aqueous pot at near-neutral pH.
- [Result 03](final/result_03/answer.md): Evaluate glycine as a Cu(II)-selective chelator over Ni(II) and Zn(II) in one shared aqueous pot at near-neutral pH.
