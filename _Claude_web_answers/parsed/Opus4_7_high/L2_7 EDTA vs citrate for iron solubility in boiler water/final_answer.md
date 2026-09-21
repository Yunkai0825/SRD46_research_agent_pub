---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_7 EDTA vs citrate for iron solubility in boiler water"
conversation: https://claude.ai/chat/3586d647-7834-47bf-bb1e-851dc885fc14
started: 2026-09-17T01:27:54.044831+00:00
finished: 2026-09-17T01:36:32.100265+00:00
stop_reason: end_turn
---
## Setup

At pH 8.5, I = 0.1, 25 °C, work with conditional constants

$$K' = K_{ML}\cdot\alpha_{ML(OH)} / \bigl(\alpha_{M(OH)}\cdot\alpha_{L(H)}\bigr)$$

then solve the mass balance $K'\cdot 10^{-3}(1{-}f)(3{-}f) = f$ for each metal (M_T = 1 mM, L_T = 3 mM), with free [Mⁿ⁺] = M_T(1−f)/α_{M(OH)}.

**Side-reaction factors at pH 8.5:**

| α-term | log α | Origin |
|---|---|---|
| α_{H₄Y}(H) | 1.77 | EDTA protonation (HY³⁻ dominant) |
| α_{H₃Cit}(H) | ≈ 0 | Cit³⁻ dominant (pK₃ = 6.4) |
| α_{Fe(OH)} | 13.05 | Fe(OH)₃(aq) + Fe(OH)₄⁻ overwhelm Fe³⁺ |
| α_{Zn(OH)} | 0.42 | Zn(OH)₂(aq) comparable to Zn²⁺ |
| α_{Ca(OH)}, α_{Mg(OH)} | ≈ 0 | negligible hydrolysis |
| α_{FeY(OH)} | 1.04 | Fe(OH)Y²⁻/FeY⁻ ≈ 10 (pK_a ≈ 7.5) |
| α_{FeCit(OH)} | ≈ 5.5 | Fe(OH)Cit⁻ / Fe(OH)₂Cit²⁻ dominate |

**Conditional log K' (pH 8.5, I = 0.1):**

| Metal | log K'(EDTA) | log K'(citrate) |
|---|---|---|
| Fe(III) | **11.3** | **5.0** |
| Ca(II) | 8.9 | 3.5 |
| Mg(II) | 7.0 | 3.3 |
| Zn(II) | 14.3 | 4.5 |

## Bound fractions and free-metal concentrations

| Metal | f (EDTA) | [Mⁿ⁺]_free (EDTA) | f (citrate) | [Mⁿ⁺]_free (citrate) |
|---|---|---|---|---|
| Fe(III) | 1 − 2.5×10⁻⁹ | ~2×10⁻²⁵ M | **0.995** | ~5×10⁻¹⁹ M |
| Ca(II) | 1 − 6×10⁻⁷ | 7×10⁻¹⁰ M | **0.87** | 1.3×10⁻⁴ M |
| Mg(II) | 1 − 5×10⁻⁵ | 5×10⁻⁸ M | **0.81** | 1.9×10⁻⁴ M |
| Zn(II) | 1 − 3×10⁻¹² | ~10⁻¹⁵ M | **0.98** | 6×10⁻⁶ M |

## Recommendation — citrate

Every EDTA K'·L_T product is ≥ 10⁴, so **EDTA binds all four metals essentially quantitatively (≥99.99%)**. It offers no discrimination in ligand consumption: each mM of Ca²⁺, Mg²⁺, or Zn²⁺ in the feedwater strips a full mM of EDTA before Fe(III) can compete for what remains.

Citrate keeps Fe(III) 99.5% chelated (through the Fe(OH)Cit⁻/Fe(OH)₂Cit²⁻ hydroxo–citrate species) but leaves **13% of Ca²⁺ and 19% of Mg²⁺ unbound** because K'_Ca·L_T and K'_Mg·L_T are only 6 and 4 — right on the boundary of quantitative complexation. Zn(II) still binds ~98%, so Zn is the main "unavoidable" hardness competitor for citrate.

## Margin in free-[M] terms

For citrate, discrimination between free Fe³⁺ and free hardness at 1 mM / 3 mM:

- log([Ca²⁺]/[Fe³⁺]) ≈ **14.5**
- log([Mg²⁺]/[Fe³⁺]) ≈ **14.6**
- log([Zn²⁺]/[Fe³⁺]) ≈ **13.1**

Ligand-consumption margin (real practical metric):

- **EDTA consumes 1.00 mM per mM hardness; citrate consumes 0.81–0.87 mM** — a 13–19% saving per unit hardness in the individual test. In a hardness-loaded stress test (e.g., 3 mM Ca²⁺ vs 3 mM ligand), solving equimolar mass balance gives f_Ca(EDTA) ≈ 1.00 (0 mM ligand spared for Fe) vs f_Ca(citrate) ≈ 0.72 (**~0.85 mM of citrate remains free** to grab Fe). That is the operational selectivity margin.

**Caveat.** The Fe(III) hold with citrate ([Fe³⁺] ≈ 10⁻¹⁹ M) sits ~2.5 log units *above* the amorphous Fe(OH)₃ solubility floor (~10⁻²¹·⁵ M at pH 8.5), so citrate is not a true thermodynamic guarantor of solubility at 3:1 stoichiometry — the system will slowly relax toward Fe(OH)₃(s). If a hard thermodynamic margin is required, either raise the citrate excess (≥10:1) or accept EDTA's ligand waste for the ~10⁶× larger cushion it provides.
