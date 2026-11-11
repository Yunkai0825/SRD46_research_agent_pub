---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L3_4 Hard-soft acid-base theory pre"
conversation: https://claude.ai/chat/1d2f2303-3508-454f-add4-e54d9433a94c
started: 2026-09-17T02:00:52.232222+00:00
finished: 2026-09-17T02:02:47.078637+00:00
stop_reason: end_turn
---
## Hypothesis (falsifiable form)

In a single-pot solution containing both metals and both ligands, HSAB predicts:

**H1.** The fraction of total Cd(II) present as chloro-complexes, f(Cd–Cl) = Σ[CdClₙ²⁻ⁿ]/C_Cd, will exceed the corresponding fraction for Zn, f(Zn–Cl).

**H2.** The fraction of total Zn(II) present as ammine complexes, f(Zn–NH₃) = Σ[Zn(NH₃)ₙ²⁺]/C_Zn, will exceed f(Cd–NH₃).

Both differential inequalities must hold; failure of either refutes the HSAB expectation for this system.

## Inputs

Cumulative stability constants (log βₙ, aqueous, 25 °C, values consistent with Martell & Smith / NIST Critical Stability Constants at low ionic strength; treated as conditional at I = 0.1 m):

| Equilibrium | log β₁ | log β₂ | log β₃ | log β₄ |
|---|---|---|---|---|
| Cd²⁺ + n Cl⁻ | 1.98 | 2.60 | 2.40 | 1.70 |
| Cd²⁺ + n NH₃ | 2.60 | 4.65 | 6.04 | 6.92 |
| Zn²⁺ + n Cl⁻ | 0.43 | 0.61 | 0.53 | 0.20 |
| Zn²⁺ + n NH₃ | 2.21 | 4.50 | 6.86 | 8.89 |

Hydroxo side reactions: Cd(OH)⁺ log β = 3.9; Zn(OH)⁺ log β = 5.0, Zn(OH)₂⁰ log β = 11.1. NH₄⁺ pKa = 9.25.

Because both ligands are in ≥ 100-fold excess over the metals, free-ligand depletion is negligible and I can use analytical concentrations as free concentrations after protonation correction:

- [Cl⁻]_free ≈ 0.100 M (metals consume < 4 mM of Cl total).
- [NH₃]_free = 0.1 / (1 + 10^{9.25−7}) = 0.1 / 178.8 = **5.59 × 10⁻⁴ M**. (At pH 7 the buffer is > 99 % NH₄⁺.)

## Speciation calculation

For each metal, α_M = 1 + Σ βₙ[Cl⁻]ⁿ + Σ βₙ[NH₃]ⁿ (+ hydroxo terms). Individual term contributions (dimensionless):

**Cd(II)**
- Chloro: 9.55 + 3.98 + 0.251 + 0.0050 = **13.78**
- Ammine: 0.224 + 0.0141 + 1.95 × 10⁻⁴ + 8 × 10⁻⁷ = **0.238**
- Hydroxo: ~8 × 10⁻⁴ (negligible)
- α_Cd ≈ 15.02

**Zn(II)**
- Chloro: 0.269 + 0.041 + 0.0034 + 1.6 × 10⁻⁴ = **0.314**
- Ammine: 0.0912 + 0.0100 + 0.0013 + 8 × 10⁻⁵ = **0.103**
- Hydroxo: 0.010 + 0.0013 ≈ **0.011**
- α_Zn ≈ 1.43

Dividing each term by α gives the fractional distribution:

| Species class | Cd(II) | Zn(II) |
|---|---|---|
| M²⁺ (aquo) | 6.7 % | 69.9 % |
| Σ M–Cl complexes | **91.7 %** | **21.9 %** |
| Σ M–NH₃ complexes | **1.6 %** | **7.2 %** |
| Σ M–OH complexes | ≈ 0 % | 0.8 % |

(Free-metal levels: [Cd²⁺] ≈ 6.7 × 10⁻⁵ M, [Zn²⁺] ≈ 7.0 × 10⁻⁴ M. The latter sits close to the amorphous Zn(OH)₂ solubility limit; I treat the system as metastably soluble, as is standard in these speciation exercises. Mixed-ligand ternary complexes Cd(NH₃)Clₙ etc. are not tabulated with reliable constants and are omitted; they would not reverse the trend.)

## Verdict

- **H1:** f(Cd–Cl) ≈ 92 % ≫ f(Zn–Cl) ≈ 22 %. **Confirmed.**
- **H2:** f(Zn–NH₃) ≈ 7 % > f(Cd–NH₃) ≈ 1.6 %. **Confirmed.**

The joint speciation calculation therefore *supports* the HSAB prediction: soft Cd(II) is monopolised by the chloro-complexes (with only a token ammine population), while borderline Zn(II) is pushed toward the aquo/ammine manifold and shows a chloro-bound fraction roughly four-fold smaller than Cd's.

Two secondary observations worth flagging so the test is not overread:

1. Both metals happen to hold more chloro than ammine mass in absolute terms, because at pH 7 the free-NH₃ activity is suppressed ~180-fold by protonation while Cl⁻ is fully deprotonated — the *ratio* of Cd/Zn chloro (and Zn/Cd ammine) fractions is the HSAB signal, not the absolute numbers, which are set by pH.
2. Raising the pH toward 9–10 would invert the absolute picture for Zn (it would become predominantly Zn(NH₃)₄²⁺, the classical result) while Cd would move to a mixed chloro/ammine population — the HSAB *differential* would persist but shrink, and is worth checking as a stress test of the hypothesis.
