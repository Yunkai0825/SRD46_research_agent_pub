---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L3_2 Chelate effect verification for nickel ethylenediamine complexati"
conversation: https://claude.ai/chat/1b6fdcbd-fb45-46d9-997e-98ffbd8c0c74
started: 2026-09-17T01:59:49.979579+00:00
finished: 2026-09-17T02:01:47.178281+00:00
stop_reason: end_turn
---
## Method

I used stepwise stability constants from the standard tables (Martell & Smith, 25 °C, low ionic strength):

- **Ni²⁺/NH₃:** log β₁…β₆ = 2.80, 5.04, 6.77, 7.96, 8.71, 8.74
- **Ni²⁺/en:** log β₁, β₂, β₃ = 7.51, 13.86, 18.28
- **Protonation:** pKₐ(NH₄⁺) = 9.25; pKₐ₁, pKₐ₂ (en) = 7.08, 9.89

Both mass balances must hold self-consistently, including the fact that at pH 7 most nitrogen is protonated and unavailable — a critical detail the raw β values conceal. I solved the coupled equations by root-finding on the free neutral-ligand concentration.

## Results

At pH 7, the neutral (metal-binding) form is a small fraction of the total pool:

| Ligand pool | Fraction as free binding form at pH 7 | Free binding-form conc. |
|---|---|---|
| 20 mM NH₃/NH₄⁺ | α(NH₃) = 5.6 × 10⁻³ | [NH₃] = 1.1 × 10⁻⁴ M |
| 10 mM en species | α(en⁰) = 5.8 × 10⁻⁴ | [en] = 4.7 × 10⁻⁶ M |

**Ammonia system:** free [Ni²⁺] = **9.3 × 10⁻⁴ M (933 µM)** — 93% of Ni is still uncomplexed. Only Ni(NH₃)²⁺ (~6.6%) and a trace of Ni(NH₃)₂²⁺ form. Protonation of NH₃ has starved the reaction of donor.

**Ethylenediamine system:** free [Ni²⁺] = **5.2 × 10⁻⁷ M (0.52 µM)** — 82% of Ni sits as Ni(en)₂²⁺, with 10% as Ni(en)₃²⁺ and 8% as Ni(en)²⁺.

## Conclusion — the chelate effect is supported, strongly

$$\frac{[\text{Ni}^{2+}]_{\text{NH}_3}}{[\text{Ni}^{2+}]_{\text{en}}} = \frac{9.3\times 10^{-4}}{5.2\times 10^{-7}} \approx 1{,}800$$

Free Ni²⁺ is **~1,800× lower (Δlog[Ni²⁺] ≈ 3.3)** with en than with the same total number of donor N atoms as NH₃. The hypothesis H₁ is supported; H₀ is refuted decisively.

Two things worth noting about *why* the gap is so large in this specific test:

1. **Intrinsic chelate effect.** Even ignoring protonation, comparing β₂(en) = 10¹³·⁸⁶ against β₄(NH₃) = 10⁷·⁹⁶ (both being four-nitrogen-donor complexes) gives ~10⁶ in favor of en — that's the textbook chelate effect from the entropy of releasing fewer bound waters per ligand added.

2. **pH-dependent amplification.** At pH 7, NH₃ is much more protonated (only 0.56% neutral) than the *first* deprotonation of en gives access to (an enH⁺ arm can still bind while the other N is protonated — though I've used the fully-deprotonated β values here, which is the more conservative accounting). This means the ammonia system is doubly disadvantaged at physiological pH.

If you rerun the calculation at pH 10 (where both ligands are largely deprotonated), the ratio shrinks but en still wins — that residual difference is the pure chelate effect. The 1,800× at pH 7 combines the intrinsic chelate advantage with a protonation penalty on ammonia.
