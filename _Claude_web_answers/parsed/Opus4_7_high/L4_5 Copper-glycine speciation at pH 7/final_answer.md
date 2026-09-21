---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L4_5 Copper-glycine speciation at pH 7"
conversation: https://claude.ai/chat/45a7c6a8-bebe-4efd-bf85-187172e6eec0
started: 2026-09-17T02:04:27.393538+00:00
finished: 2026-09-17T02:06:11.341926+00:00
stop_reason: end_turn
---
## System and constants

At 25 °C, I = 0.1 M (typical NaClO₄-medium literature values):

**Glycine protonation** (Gly⁻ = ⁻OOC-CH₂-NH₂):
- log K(HGly/Gly⁻·H⁺) = 9.57 (amine)
- log K(H₂Gly⁺/HGly·H⁺) = 2.36 (carboxyl)

**Cu(II)–glycinate** (cumulative, referenced to Gly⁻):
- log β₁ (CuGly⁺) = 8.16
- log β₂ (Cu(Gly)₂) = 15.04
- log β₃ (Cu(Gly)₃⁻) = 16.2 *(weak, only appears at high pH/ligand)*

**Cu(II) hydrolysis** (Cu²⁺ + n OH⁻ ⇌ Cu(OH)ₙ²⁻ⁿ): log K = 6.3, 11.8, 14.5, 16.4 (n = 1–4), and pKsp Cu(OH)₂(s) = 19.66.

Mass balances were solved simultaneously (Newton/bisection) at each pH for C_Cu = 1 mM, C_Gly = 10 mM.

![Cu(II) speciation with 10 mM glycine, 1 mM Cu, I=0.1 M, 25 °C](chart_1_Cu%28II%29%20speciation%20with%2010%20mM%20glycine,%201%20mM%20Cu,%20I=0.1%20M,%2025%20°C.png)

## Regimes across pH

- **pH ≲ 3:** free aquo Cu²⁺ dominates because glycine is fully protonated (α(Gly⁻) is only ~10⁻⁷ at pH 3).
- **pH ≈ 4–5:** CuGly⁺ takes over, peaking near pH 4 at ~68%.
- **pH ≈ 5.5:** crossover — Cu(Gly)₂ becomes the majority species.
- **pH 6.5–10:** Cu(Gly)₂ plateau (>95%).
- **pH > 10:** Cu(Gly)₃⁻ begins to appear (~10% at pH 12); Cu hydroxo species stay negligible in the glycinate buffer.

## Dominant species at pH 7

| Species | Concentration | % of total Cu |
|---|---|---|
| **Cu(Gly)₂ (neutral, bis-glycinato)** | **9.94 × 10⁻⁴ M** | **99.36 %** |
| CuGly⁺ | 6.1 × 10⁻⁶ M | 0.61 % |
| Cu(Gly)₃⁻ | 3.1 × 10⁻⁷ M | 0.03 % |
| free Cu²⁺ | 2.0 × 10⁻⁹ M | ~10⁻⁶ % |
| CuOH⁺ and other hydroxo | ≤ 4 × 10⁻¹⁰ M | negligible |

Free glycinate [Gly⁻] ≈ 2.15 × 10⁻⁵ M; the bulk of glycine sits as the zwitterion HGly (~8 mM). Saturation index for Cu(OH)₂(s) at pH 7 is −3.05, so **no precipitation** — glycine keeps Cu solubilized.

At physiological pH, Cu(II)/glycine is effectively a single-species system: **bis(glycinato-N,O)copper(II)**, the familiar trans-planar CuN₂O₂ chelate.
