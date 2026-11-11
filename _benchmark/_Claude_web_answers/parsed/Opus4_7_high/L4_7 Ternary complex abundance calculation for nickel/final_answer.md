---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L4_7 Ternary complex abundance calculation for nickel"
conversation: https://claude.ai/chat/5c5f7bc5-5a6f-4c03-87f8-0b1623d5c690
started: 2026-09-17T02:06:29.529810+00:00
finished: 2026-09-17T02:08:20.721959+00:00
stop_reason: end_turn
---
## Setting up the problem

**Stability constants used** (25 °C, I = 0.1 M, from NIST 46 / IUPAC compilations):

Ligand protonation: pKₐ(HGly±) = 9.57, pKₐ(NH₄⁺) = 9.25

Ni–glycinate: log β₁₁₀ = 5.78, log β₁₂₀ = 10.58, log β₁₃₀ = 13.93
Ni–ammine: log β₁₀₁ = 2.72, log β₁₀₂ = 4.89, log β₁₀₃ = 6.55, log β₁₀₄ = 7.67 (β₁₀₅,β₁₀₆ negligible here)
Mixed ternary: log β₁₁₁(Ni·gly·NH₃) ≈ 8.2 (Ni²⁺ + gly⁻ + NH₃ → Ni(gly)(NH₃)⁺)

## Free-ligand availability at pH 8

α(gly⁻) = Kₐ₂/([H⁺]+Kₐ₂) = 10⁻⁹·⁵⁷/(10⁻⁸ + 10⁻⁹·⁵⁷) = **0.0262**
α(NH₃) = 10⁻⁹·²⁵/(10⁻⁸ + 10⁻⁹·²⁵) = **0.0532**

So the "reservoirs" are: 5 mM gly ⇒ 131 μM potentially as gly⁻; 5 mM NH₃/NH₄⁺ ⇒ 266 μM as NH₃.

## Solving the mass balances

Iterating the three mass balances (Ni_T = 1 mM, gly_T = 5 mM, NH₃_T = 5 mM) converges to:

**[gly⁻] ≈ 7.9 × 10⁻⁵ M, [NH₃] ≈ 2.65 × 10⁻⁴ M, [Ni²⁺] ≈ 3.0 × 10⁻⁶ M**

(Glycine is drawn down noticeably by Ni²⁺; ammonia is barely touched because Ni–NH₃ is weak and gly⁻ outcompetes it.)

## Species distribution of total Ni

| Species | % of Ni_T |
|---|---|
| Ni²⁺ | 0.30 |
| Ni(gly)⁺ | 14.3 |
| **Ni(gly)₂⁰** | **71.7** |
| Ni(gly)₃⁻ | 12.8 |
| Ni(NH₃)²⁺ + Ni(NH₃)₂²⁺ | 0.04 |
| **Ni(gly)(NH₃)⁺** | **≈ 1.0** |

Explicitly:
[Ni(gly)(NH₃)⁺] = β₁₁₁·[Ni²⁺]·[gly⁻]·[NH₃]
= 10^8.2 × (3.0 × 10⁻⁶)(7.9 × 10⁻⁵)(2.65 × 10⁻⁴)
≈ 1.0 × 10⁻⁵ M

## Answer

**Ni(gly)(NH₃)⁺ ≈ 1 × 10⁻⁵ M, i.e. ~1.0 % of total Ni.**

The ternary complex is a minor species because gly⁻ is >1000× a stronger donor per site than NH₃ for Ni²⁺, so at these near-stoichiometric ligand levels almost three-quarters of the Ni is captured as bis-glycinate before ammonia can compete for a coordination site. The exact value is sensitive to log β₁₁₁ (typical literature range 8.0–8.3 gives 0.8–1.4 %); higher mixed species like Ni(gly)₂(NH₃)⁻ have poorly-defined constants and, if included at Δlog K ≈ –0.4, would shift the answer by only a few tenths of a percent.
