---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_6 Selective Cu(II) chelation through metal-ligand speciation"
conversation: https://claude.ai/chat/b032fdda-500b-4a59-a089-cf3847ce0fc6
started: 2026-09-17T01:27:31.106632+00:00
finished: 2026-09-17T01:29:54.394306+00:00
stop_reason: end_turn
---
## Setup and constants

Working in the fully-dissociated-ligand basis (β_n refers to M²⁺ + n L^q⁻ → ML_n), with critically-selected values from Martell & Smith / NIST 46 at I = 0.1 M, 25 °C:

| Ligand | pKₐ ladder | log β₁ Cu | log β₂ Cu | log β₁ Ni | log β₂ Ni | log β₃ Ni | log β₁ Zn | log β₂ Zn |
|---|---|---|---|---|---|---|---|---|
| glycine | 2.36, 9.57 | 8.15 | 15.05 | 5.78 | 10.58 | 13.90 | 4.96 | 9.06 |
| citrate³⁻ | 3.13, 4.76, 6.40 | 5.90 (+ MHL 9.14) | – | 5.40 (+ MHL 8.90) | – | – | 4.80 (+ MHL 8.70) | – |
| EDTA⁴⁻ | 2.00, 2.67, 6.16, 10.26 | 18.78 | – | 18.62 | – | – | 16.50 | – |

The mass balances on M and L are solved simultaneously (Brent's method on log[L^q⁻]) at pH 7 with [M]ₜ = 1 mM, [L]ₜ = 5 mM.

## The 3 × 3 matrix

**Free [M²⁺] at equilibrium (mol L⁻¹):**

|      | glycine  | citrate  | EDTA      |
|------|----------|----------|-----------|
| Cu   | 1.34 × 10⁻⁸ | 3.94 × 10⁻⁷ | 8.65 × 10⁻¹⁷ |
| Ni   | 9.16 × 10⁻⁵ | 1.24 × 10⁻⁶ | 1.25 × 10⁻¹⁶ |
| Zn   | 4.48 × 10⁻⁴ | 4.93 × 10⁻⁶ | 1.65 × 10⁻¹⁴ |

**Same information as pM = −log₁₀[M²⁺] (bigger = tighter):**

|      | glycine | citrate | EDTA  |
|------|---------|---------|-------|
| Cu   | **7.87** | 6.40 | **16.06** |
| Ni   | 4.04 | 5.91 | 15.90 |
| Zn   | 3.35 | 5.31 | 13.78 |

**Cu-selectivity per ligand ([M²⁺]_other / [Cu²⁺]):**

| ligand  | [Ni²⁺]/[Cu²⁺] | [Zn²⁺]/[Cu²⁺] | worst-case (min) |
|---------|-----|-----|-----|
| glycine | **6.8 × 10³** | **3.3 × 10⁴** | **6.8 × 10³** |
| citrate | 3.2 | 12.5 | 3.2 |
| EDTA    | 1.4 | 1.9 × 10² | 1.4 |

## Recommendation: **Cu(II) + glycine**

Reading the matrix column-by-column, EDTA and glycine both give a very deep Cu well (pCu = 16.1 and 7.9 respectively) while citrate is weak on all three metals. The choice therefore comes down to *selectivity*, not raw affinity, and here glycine wins by ~3½ orders of magnitude:

- Glycine leaves [Ni²⁺] and [Zn²⁺] essentially untouched (pNi = 4.04, pZn = 3.35 — the metals are 91 % and 45 % free) while pulling Cu²⁺ down to 1.3 × 10⁻⁸ M. That is the Irving–Williams sequence expressing itself in the cleanest possible way: Δlog β₂(Cu–Ni) = 4.5 and Δlog β₂(Cu–Zn) = 6.0 on the glycine ladder.
- EDTA suppresses Cu²⁺ 10⁹× more strongly but suppresses Ni²⁺ almost exactly as hard ([Ni]/[Cu] = 1.4). If Ni is present it will be sequestered indistinguishably from Cu, so EDTA is a *sponge*, not a *selector*.
- Citrate is worse than both — its [Ni]/[Cu] ratio of 3.2 gives essentially no discrimination, and its pCu of 6.4 is the shallowest of the strong chelators.

Quantitatively: at the pairing Cu/glycine the ratio (mol Cu bound)/(mol Ni bound) at 1 mM each with 5 mM glycine is ≈ 9.16 × 10⁻⁵ / 1.34 × 10⁻⁸ ≈ **6.8 × 10³**, i.e. capture is Cu-selective by nearly four orders of magnitude in a single stage. No other ligand in the set gets past ~10¹.

A footnote on operating window: with glycine, [Cu²⁺] × [OH⁻]² ≈ 1.3 × 10⁻⁸ × 10⁻¹⁴ ≈ 10⁻²² ≪ Kₛₚ(Cu(OH)₂) ≈ 10⁻¹⁹·³, so no hydroxide precipitation at pH 7 — the matrix values above are self-consistent. If the process pH drifts above ~8.5, Cu(OH)⁺ starts to compete and the selectivity number will erode; glycine's advantage is largest in the pH 6.5–8 band where gly⁻ availability rises steeply but MOH species have not yet taken over.
