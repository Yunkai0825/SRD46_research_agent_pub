---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L3_1 The Irving–Williams series pre"
conversation: https://claude.ai/chat/ef3954e9-5b51-46a2-b1b8-659e73143dca
started: 2026-09-17T01:59:39.418217+00:00
finished: 2026-09-17T02:01:40.665685+00:00
stop_reason: end_turn
---
## Hypothesis (falsifiable form)

For the reaction M²⁺ + Gly⁻ ⇌ M(Gly)⁺, the Irving–Williams series predicts

log K₁(Co) < log K₁(Ni) < log K₁(Cu) > log K₁(Zn),

with Cu(II) the maximum and Zn(II) falling back but still above Co(II). Equivalently, at fixed pH, temperature, and total M/L, the free [M²⁺] at equilibrium must rank

[Cu²⁺] < [Ni²⁺] < [Zn²⁺] < [Co²⁺] (Cu most suppressed, Co least).

The prediction is falsified if any adjacent pair inverts — most diagnostically, if [Ni²⁺] < [Cu²⁺] (no maximum at Cu), or if [Zn²⁺] < [Ni²⁺] (no drop at Zn).

## Inputs (I = 0.1 m, 25 °C; NIST 46 / Martell–Smith)

Glycine: pK_a1 = 2.36, pK_a2 = 9.57. At pH 7, α(Gly⁻) = 1/(1 + 10^2.57 + 10^−2.07) = 2.69 × 10⁻³.

| M(II) | log K₁ | log β₂ | log β₃ |
|---|---|---|---|
| Co | 4.64 | 8.51 | 10.81 |
| Ni | 5.78 | 10.58 | 13.61 |
| Cu | 8.15 | 15.01 | — (Jahn–Teller; negligible) |
| Zn | 4.96 | 9.11 | 11.51 |

## Speciation (C_M = 1 mM, C_L = 10 mM, pH 7)

Solving the coupled mass balances
C_M = [M²⁺](1 + K₁[Gly⁻] + β₂[Gly⁻]² + β₃[Gly⁻]³)
C_L = [Gly⁻]/α + [M²⁺](K₁[Gly⁻] + 2β₂[Gly⁻]² + 3β₃[Gly⁻]³)

iteratively for [Gly⁻] gives:

| M(II) | [Gly⁻] (M) | [M²⁺] (M) | % free M | Dominant bound form |
|---|---|---|---|---|
| Co | 2.51 × 10⁻⁵ | **4.35 × 10⁻⁴** | 43 % | MGly⁺ (~48 %), M(Gly)₂ (~18 %) |
| Zn | 2.43 × 10⁻⁵ | **2.51 × 10⁻⁴** | 25 % | MGly⁺ (~56 %), M(Gly)₂ (~19 %) |
| Ni | 2.27 × 10⁻⁵ | **2.88 × 10⁻⁵** | 2.9 % | M(Gly)₂ (~56 %), MGly⁺ (~39 %) |
| Cu | 2.15 × 10⁻⁵ | **2.1 × 10⁻⁹** | 2 × 10⁻⁴ % | M(Gly)₂ (~99 %) |

## Ranking by suppression of free [M²⁺]

Cu (2 × 10⁻⁹) ≪ Ni (2.9 × 10⁻⁵) < Zn (2.5 × 10⁻⁴) < Co (4.4 × 10⁻⁴).

## Verdict

The computed ordering matches the Irving–Williams prediction exactly: Cu(II) is the maximum (five orders of magnitude more suppressed than its neighbors), Ni(II) sits second, and Zn(II) drops back below Ni but stays above Co(II). No adjacent pair inverts, so the falsifiable hypothesis is **confirmed** for the glycine system at these conditions.

Worth flagging: the ranking of [M²⁺] tracks K₁ even though the dominant species is not 1:1 for every metal — Cu is essentially all Cu(Gly)₂ and Ni is mostly Ni(Gly)₂ — because β₂ and β₃ inherit the K₁ ordering. If one instead ran the test with a ligand that specifically disfavors Cu(II) geometry (e.g. a rigid tetrahedral chelate), the maximum could shift, which is the sort of experiment that would genuinely put Irving–Williams at risk rather than merely re-confirm it.
