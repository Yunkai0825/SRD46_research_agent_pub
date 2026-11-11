---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L3_3 Cadmium complexation_ chloride versus ammonia"
conversation: https://claude.ai/chat/a74fc7a1-ae1a-4e1d-b8e8-4e74e12fc4c9
started: 2026-09-17T02:00:15.119656+00:00
finished: 2026-09-17T02:02:02.668925+00:00
stop_reason: end_turn
---
**HSAB prediction.** Cd(II) is a soft (d¹⁰, polarizable) Lewis acid, sitting on the soft side of the borderline zone with Zn(II) above it and Hg(II) below. Chloride is a borderline base that leans soft (larger, more polarizable than F⁻ or O-donors), whereas ammonia — despite the modest polarizability of its lone pair — is usually placed on the hard side of borderline (donor atom N with a small, tightly held lone pair, comparable to H₂O/OH⁻). The "soft prefers soft" rule therefore predicts Cd(II)–Cl⁻ should be favored over Cd(II)–NH₃ at matched conditions.

**Computation (25 °C, I = 0.1 m, pH 7, C_Cd = 1 mM).**

Stability constants I used (β values as cumulative; Cd–Cl corrected to I = 0.1 via Davies, Cd–NH₃ corrections cancel since all Cd(NH₃)ₙ²⁺ carry the same charge as Cd²⁺):

- Cd–Cl (conc. basis, I = 0.1): log β₁,β₂,β₃,β₄ ≈ 1.55, 2.00, 1.66, 1.25
- Cd–NH₃: log β₁,β₂,β₃,β₄ ≈ 2.60, 4.65, 5.90, 6.60
- pKₐ(NH₄⁺) = 9.25; Cd²⁺ hydrolysis (log*K₁ ≈ –10.1) is negligible at pH 7.

*Case A — 0.1 M chloride.* With only 1 mM Cd, essentially all Cl⁻ is free, so [Cl⁻] ≈ 0.1 M. The side-reaction coefficient is

α_Cd(Cl) = 1 + 35.5(0.1) + 100(0.1)² + 45.7(0.1)³ + 17.8(0.1)⁴
        = 1 + 3.55 + 1.00 + 0.046 + 0.002 ≈ 5.60

so [Cd²⁺] ≈ 1 mM / 5.60 ≈ **1.8 × 10⁻⁴ M** (≈18 % of Cd_T is free; the rest is mainly CdCl⁺ and CdCl₂).

*Case B — 0.1 M total ammonia.* At pH 7 only

[NH₃]_free = 0.1 · 1/(1 + 10^(9.25–7)) ≈ 5.6 × 10⁻⁴ M.

Then

α_Cd(NH₃) = 1 + 398·(5.6e-4) + 4.47e4·(5.6e-4)² + 7.94e5·(5.6e-4)³ + 3.98e6·(5.6e-4)⁴
         = 1 + 0.222 + 0.0139 + 1.4e-4 + 4e-7 ≈ 1.24

so [Cd²⁺] ≈ 1 mM / 1.24 ≈ **8.1 × 10⁻⁴ M** (≈81 % free).

**Verdict.** The chloride medium leaves ~4.5× less free Cd²⁺ than the ammonia medium at pH 7, i.e., Cd(II) is held more strongly by chloride under the stated conditions — the HSAB prediction is **confirmed**.

**But the reason is not entirely HSAB.** If you compare the intrinsic constants at equal *free* ligand concentration, ammonia is by far the better donor to Cd(II) (log β₄ ≈ 6.6 vs ~1.25 for Cl⁻); at 0.1 M *free* NH₃ the free-Cd²⁺ level would collapse below 10⁻⁶ M. What tips the balance at pH 7 is protonation: only ~0.6 % of "ammonia" is actually NH₃, while chloride is fully deprotonated and available. Rerun the experiment near pH 9–10 and ammonia wins decisively. So HSAB gets the right answer here largely by accident of pH — proton competition, not orbital matching, does most of the work. This is a general lesson: raw stability constants can point one way while conditional (pH-, ionic-strength-, competing-ligand-dependent) speciation points the other, and the "soft prefers soft" heuristic really applies to the intrinsic constants, not the conditional free-metal outcome.
