---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L3_6 The chelate effect predicts th"
conversation: https://claude.ai/chat/8074d689-06f9-4c2e-a974-262816adaade
started: 2026-09-17T02:01:59.769713+00:00
finished: 2026-09-17T02:04:05.584703+00:00
stop_reason: end_turn
---
**Falsifiable prediction.** For a fixed metal, pH, temperature, and ionic strength, and holding total donor-atom concentration constant, the free metal ion concentration is a strictly decreasing function of ligand denticity. Concretely: log[Ni²⁺]_NH₃ > log[Ni²⁺]_en > log[Ni²⁺]_EDTA. Any non-monotonic ordering (e.g. en below EDTA, or NH₃ below en) falsifies it.

**Constants used (I = 0.1 m, 25 °C).**
- NH₃: pKa(NH₄⁺) = 9.25; log β₁–β₆ for Ni(NH₃)ₙ²⁺ = 2.80, 5.04, 6.77, 7.96, 8.71, 8.74.
- en: pKa₁ = 6.85, pKa₂ = 9.93; log β₁–β₃ for Ni(en)ₙ²⁺ = 7.51, 13.86, 18.06.
- EDTA: pKa's = 2.0, 2.67, 6.16, 10.26; log K(NiY²⁻) = 18.62.
- Ni(II) hydrolysis at pH 7 is negligible (log[NiOH⁺/Ni²⁺] ≈ −2.9).

**Ammonia (60 mM total, pH 7).** Only α(NH₃) = Ka/(Ka + [H⁺]) = 5.6×10⁻³ of the ammonia is deprotonated, so [NH₃]_free ≈ 60 mM × 5.6×10⁻³ = 3.4×10⁻⁴ M. Then Σβₙ[NH₃]ⁿ = 0.21 + 0.012 + 2×10⁻⁴ + … = 0.22. So [Ni²⁺]/[Ni]_T = 1/(1 + 0.22) = 0.82, giving

  **[Ni²⁺] ≈ 8.2 × 10⁻⁴ M** (log ≈ −3.09).

Only ~18% of the Ni is complexed; the dominant Ni species is still free Ni²⁺(aq), with Ni(NH₃)²⁺ a minor contributor.

**Ethylenediamine (30 mM total, pH 7).** α(en) = Ka₁Ka₂/([H⁺]² + Ka₁[H⁺] + Ka₁Ka₂) = 6.9×10⁻⁴. Iterating to account for ~2.2 en per Ni bound (removing ~2.2 mM from the ligand pool), [en]_free ≈ 1.9×10⁻⁵ M. Then β₁[en] = 620, β₂[en]² = 2.7×10⁴, β₃[en]³ = 8.1×10³; sum ≈ 3.5×10⁴. Thus

  **[Ni²⁺] ≈ 2.8 × 10⁻⁸ M** (log ≈ −7.55).

The bis(en) complex dominates (~75%) with tris(en) next.

**EDTA (10 mM total, pH 7).** log α(Y⁴⁻) at pH 7 = −3.32, so the conditional constant is log K′ = 18.62 − 3.32 = 15.30. With essentially all 1 mM Ni pulled into NiY²⁻, free EDTA (all protonation states) ≈ 9 mM. Then [Ni²⁺] = [NiY²⁻]/(K′·[EDTA_free]) = 10⁻³/(10^15.30 × 9×10⁻³):

  **[Ni²⁺] ≈ 5.6 × 10⁻¹⁷ M** (log ≈ −16.25).

**Result.**

| Ligand | Denticity | Total (mM) | Donor-atom (mM) | [Ni²⁺] (M) | log[Ni²⁺] |
|---|---|---|---|---|---|
| NH₃ | 1 | 60 | 60 | 8.2 × 10⁻⁴ | −3.09 |
| en | 2 | 30 | 60 | 2.8 × 10⁻⁸ | −7.55 |
| EDTA | 6 | 10 | 60 | 5.6 × 10⁻¹⁷ | −16.25 |

log[Ni²⁺] falls monotonically by ~4.5 units going mono→bi and another ~8.7 units going bi→hexa, a total drop of nearly 13 orders of magnitude. **The monotonic denticity prediction is upheld, not falsified.**

**Caveat on interpretation.** The gap is not "pure" chelate effect. A substantial part of the NH₃→en jump comes from protonation: at pH 7, NH₃ is 99.4% protonated as NH₄⁺, whereas en has one free amine at a significant mole fraction. Even after correcting for that (comparing β at equal free-ligand concentration), the chelate contribution alone still shifts log[Ni²⁺] by several units per step, and the EDTA point — where a single hexadentate ligand cage dwarfs the entropic penalty of assembling six independent donors — remains the extreme case that the classical Schwarzenbach picture predicts.
