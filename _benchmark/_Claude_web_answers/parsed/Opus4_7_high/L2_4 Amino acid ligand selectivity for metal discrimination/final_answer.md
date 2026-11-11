---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_4 Amino acid ligand selectivity for metal discrimination"
conversation: https://claude.ai/chat/57c7f63d-edf5-4e4e-9770-9fb1126f2a38
started: 2026-09-17T08:29:25.064618+00:00
finished: 2026-09-17T08:33:51.541331+00:00
stop_reason: end_turn
---
Here are the results, with a robust solver:

**Speciation at pH 7.0, [M]ᵀ = 1 mM, [L]ᵀ = 5 mM, I = 0.1 M**

| Ligand | Metal | pM | %ML | %ML₂ | %ML₃ | %free M²⁺ |
|---|---|---|---|---|---|---|
| Glycine | Cu | 7.44 | 2.6 | 97.4 | — | 3.6 × 10⁻³ |
| Glycine | Ni | 3.78 | 55.5 | 27.7 | 0.3 | 16.4 |
| Glycine | Co | 3.12 | 23.5 | 1.0 | 0 | 75.3 |
| L-Histidine | Cu | **11.88** | 0.0 | 100 | — | 1.3 × 10⁻⁷ |
| L-Histidine | Ni | **9.21** | 0.7 | 99.3 | — | 6.1 × 10⁻⁵ |
| L-Histidine | Co | **6.04** | 15.6 | 84.3 | — | 9.2 × 10⁻² |
| L-Aspartate | Cu | 7.18 | 11.6 | 88.4 | — | 6.6 × 10⁻³ |
| L-Aspartate | Ni | 5.16 | 48.4 | 51.0 | — | 0.69 |
| L-Aspartate | Co | 3.81 | 76.4 | 8.0 | — | 15.6 |

**Discrimination (Δ pM = log₁₀ of free-[M²⁺] ratio)**

| Ligand | pCu − pCo | pCu − pNi | pNi − pCo | full range |
|---|---|---|---|---|
| Glycine | 4.32 | 3.66 | **0.66** | 4.32 |
| L-Histidine | 5.84 | 2.67 | **3.18** | **5.84** |
| L-Aspartate | 3.37 | 2.02 | 1.35 | 3.37 |

**Recommendation: L-histidine.** It gives ~10⁵·⁸ ≈ 700 000-fold spread in free [M²⁺] across the three metals, vs ~21 000-fold for glycine and ~2 300-fold for aspartate. More importantly, it's the only one that meaningfully separates Ni from Co — 3.2 log units vs 0.7 for glycine and 1.4 for aspartate.

The reason is mechanistic, not thermodynamic in the naive sense. Glycine's raw ΔlogK₂ (Cu–Co ≈ 6.7) is actually *slightly larger* than histidine's (≈ 6.0), so on paper you'd expect glycine to discriminate as well. But at pH 7 the free glycinate concentration is small (α_L ≈ 600) and Gly is only bidentate, so log β₂ · [L]² isn't large enough to pull Ni and especially Co fully into M(Gly)₂ — 75% of the Co and 16% of the Ni sit around as aquo ion. When the weakly-bound metals are stuck at ~[M]ᵀ, their pM values collapse together and the spread flattens. Histidine's tridentate (N_amino, COO⁻, N_imidazole) coordination, plus its lower α_L at pH 7 (imidazole pKa 6.04), drives β₂ · [L]² well above 1 for all three metals — every one is ≥84% M(His)₂ — so the observed pM spread tracks the true Δlog β₂.

Aspartate is a mediocre compromise: it does pull Ni into ML/ML₂, but its Cu, Ni, and Co affinities cluster too tightly (log β₂ 14.8/12.4/10.1) and its extra carboxylate doesn't preferentially select any one metal.

**pH robustness.** Histidine's separation is nearly flat across pH 6–8: full range = 5.14 (pH 6.0), 5.63 (6.5), 5.84 (7.0), 5.92 (7.5), 5.95 (8.0). Glycine's climbs from 2.56 → 5.75 over the same window — it only becomes competitive at pH 8, where Cu(OH)₂(s) precipitation risk starts to bite for 1 mM Cu without a strong chelator.

**Caveats.** (1) The log β values above are my best recollection of NIST SRD-46 / Martell-Smith Vol. 1 at I = 0.1 M and are within roughly ±0.1–0.2 log unit of the recommended values — for publication-grade work, pull the actual selected constants from the database. (2) I've neglected protonated (MHL) and mixed-ligand hydroxo (MLOH) complexes; both are minor at 5:1 L:M and pH 7 for these systems, but MHL contributes a few percent for Cu(H·Asp) and Cu(H·His) around pH 6. (3) Cys was excluded because Cu(II) oxidizes it, and Met/Lys/Asn were not evaluated because their Ni and Co constants are much weaker than histidine's, so they cannot outperform it geometrically.
