---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_5 Nickel hydroxide scaling prevention with ligands"
conversation: https://claude.ai/chat/aa08a3fa-52c6-40de-b394-e75313862796
started: 2026-09-17T01:27:04.368873+00:00
finished: 2026-09-17T01:29:32.093556+00:00
stop_reason: end_turn
---
## Setup

At pH 9, [OH⁻] = 10⁻⁵ M. Using the "fresh" Ni(OH)₂ solubility (log Kₛₚ ≈ −15.2, appropriate for scale onset rather than aged β-Ni(OH)₂ at −17.2), the free-ion ceiling before precipitation starts is

$$[\text{Ni}^{2+}]_{\text{sat}} = K_{sp}/[\text{OH}^-]^2 \approx 6\times10^{-6}\,\text{M}$$

With 1 mM total Ni, we need a side-reaction coefficient α_Ni(L) ≥ ~170 just to break even. The relevant log β values (I = 0.1 M, 25 °C, from Martell–Smith):

| Ligand (pKₐ's) | Ni–L cumulative log β |
|---|---|
| Gly⁻ (2.35, 9.78) | β₁ 5.78, β₂ 10.58, β₃ 13.90 |
| Cit³⁻ (3.13, 4.76, 6.40) | β₁ 5.4, β₂ 7.1 |
| NH₃ (9.25) | β₁–β₆: 2.72, 4.89, 6.55, 7.67, 8.34, 8.31 |

## Step 1 — Free ligand at pH 9 (10 mM total)

**Glycine:** α_Gly⁻ = 1/(1 + 10^(9.78−9) + …) ≈ 0.14. After iterating mass balance (Ni pulls ~2.7 Gly on average), free [Gly⁻] ≈ 1.0 × 10⁻³ M.

**Citrate:** fully deprotonated at pH 9 (α_Cit³⁻ ≈ 0.998), so [Cit³⁻] ≈ 9 × 10⁻³ M after Ni uptake.

**Ammonia:** pH 9 sits just below pKₐ, so α_NH₃ = 1/(1 + 10^0.25) ≈ 0.36 and [NH₃] ≈ 3.6 × 10⁻³ M.

## Step 2 — α_Ni for each ligand

**Glycine** ([Gly⁻] = 1.0 × 10⁻³):
- β₁[L] = 6.0 × 10² 
- β₂[L]² = 4.1 × 10⁴
- β₃[L]³ = 8.9 × 10⁴ ← dominant  
α_Ni ≈ **1.3 × 10⁵**; Ni is ~70 % NiGly₃⁻ / 30 % NiGly₂.

**Citrate** ([Cit³⁻] = 9 × 10⁻³):
- β₁[L] = 2.3 × 10³ (NiCit⁻ dominant)
- β₂[L]² = 1.0 × 10³  
α_Ni ≈ **3.3 × 10³**. (Including a mixed hydroxo-citrate species Ni(OH)Cit²⁻, log β ≈ 11.5, would add ~3 × 10⁴ more — a real but literature-dependent boost. I've left it out to stay conservative.)

**Ammonia** ([NH₃] = 3.6 × 10⁻³):
Terms in Σβₙ[NH₃]ⁿ: 1.9, 1.0, 0.17, 0.008, …  
α_Ni ≈ **4.1**. The upper amines never populate because [NH₃] is far too low to overcome the βₙ gap.

## Step 3 — Free [Ni²⁺] and scaling verdict

| Ligand | α_Ni | [Ni²⁺] if all 1 mM dissolves | Precipitate? |
|---|---|---|---|
| Glycine | 1.3 × 10⁵ | **7 × 10⁻⁹ M** | No (10³× below saturation) |
| Citrate | 3.3 × 10³ | **3 × 10⁻⁷ M** | No (~20× below saturation) |
| Ammonia | 4.1 | 2.5 × 10⁻⁴ M → capped by Kₛₚ at **6 × 10⁻⁶ M** | Yes; only ~25 μM Ni stays soluble |

## Ranking and why

**Glycine < citrate ≪ ammonia** for free [Ni²⁺] remaining.

*Glycine wins* because it's a bidentate N,O chelator forming two 5-membered rings, and the tris-glycinate NiGly₃⁻ is accessible even though only 14 % of the ligand pool is deprotonated at pH 9 — the [L]³ dependence gets amplified by β₃ = 10¹³·⁹. The chelate effect pays off twice (per ring, per additional ligand).

*Citrate is a solid second* because the ligand is fully anionic (Cit³⁻) at pH 9, so [L] is essentially the analytical concentration. But citrate binds Ni through carboxylates and an alkoxide — donors of modest basicity — so per-ligand log K₁ ~ 5.4 is roughly one log unit below glycine, and the bis-complex is weak (K₂ ~ 1.7). It clears the scaling threshold with ~20× margin, and mixed hydroxo-citrate species (real but with scattered reported constants) push that margin higher.

*Ammonia fails* for two compounding reasons at pH 9: (i) the ligand is 64 % protonated as NH₄⁺, dropping [NH₃] to 3.6 mM, and (ii) each Ni–N bond is worth only ~2.7 log units, so you need Ni(NH₃)₄–₆ populations to compete with Ni(OH)₂, which requires [NH₃] ≥ 0.5–1 M. At 10 mM total, α_Ni is nowhere near the ~170 needed, so Ni(OH)₂(s) precipitates and only micromolar Ni stays in solution. Ammonia becomes a viable anti-scalant only at much higher concentrations (buffer strengths of ~1 M, e.g., ammoniacal leaching) or higher pH where the NH₃/NH₄⁺ balance flips.

Practical takeaway: **glycine at 10 mM completely suppresses Ni(OH)₂ scaling; citrate does so with a modest margin; ammonia at this loading does not.**
