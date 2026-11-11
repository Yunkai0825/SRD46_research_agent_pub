---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L4_6 In a single solution containin"
conversation: https://claude.ai/chat/d7f7725d-b150-4e55-9536-595bd73af5bf
started: 2026-09-17T02:06:20.158759+00:00
finished: 2026-09-17T02:08:27.902802+00:00
stop_reason: end_turn
---
## Kinetics of the Cu²⁺/Zn²⁺/glycine/EDTA system at pH 6, 25 °C

**Short answer:** individual complex formation is essentially instantaneous (sub-millisecond). The genuinely rate-limiting process is the Cu/Zn *sorting* on EDTA, and that takes on the order of seconds to a few minutes.

### Formation rate constants (μ ≈ 0.1 M, 25 °C)

The Eigen–Wilkins mechanism (outer-sphere pre-equilibrium × water-loss rate) gives near-diffusion-limited values for Cu(II) (k_ex(H₂O) ≈ 2 × 10⁹ s⁻¹, Jahn–Teller-accelerated) and ~100× slower for Zn(II) (k_ex(H₂O) ≈ 3 × 10⁷ s⁻¹):

| Reaction | k_f (M⁻¹ s⁻¹) |
|---|---|
| Cu²⁺ + Gly⁻ → CuGly⁺ | ≈ 4 × 10⁹ |
| Zn²⁺ + Gly⁻ → ZnGly⁺ | ≈ 1 × 10⁷ |
| Cu²⁺ + Y⁴⁻ → CuY²⁻ | ≈ 3 × 10⁹ |
| Cu²⁺ + HY³⁻ → CuHY⁻ (→ CuY²⁻) | ≈ 2 × 10⁸ |
| Zn²⁺ + Y⁴⁻ → ZnY²⁻ | ≈ 3 × 10⁸ |
| Zn²⁺ + HY³⁻ → ZnHY⁻ | ≈ 3 × 10⁶ |

### Speciation of the free ligands at pH 6

- **EDTA** (pKa's 2.68 / 6.16 / 10.26): αH₂Y²⁻ ≈ 0.41, αHY³⁻ ≈ 0.59, αY⁴⁻ ≈ 4 × 10⁻⁵. The HY³⁻ path dominates the flux.
- **Glycine** (pKa₂ = 9.78): αGly⁻ ≈ 1.6 × 10⁻⁴, so [Gly⁻] ≈ 1.6 μM out of 10 mM.

### Half-lives for initial complex formation

Pseudo-first-order rates for a free aquo-metal encountering the *ligand pool* actually present:

- Cu²⁺ + glycinate: k[Gly⁻] ≈ 4 × 10⁹ × 1.6 × 10⁻⁶ ≈ 6 × 10³ s⁻¹ ⇒ **t½ ≈ 0.1 ms**
- Cu²⁺ + EDTA: ≈ 2 × 10⁸ × 6 × 10⁻⁴ ≈ 10⁵ s⁻¹ ⇒ **t½ ≈ 6 μs**
- Zn²⁺ + glycinate: ≈ 1 × 10⁷ × 1.6 × 10⁻⁶ ≈ 16 s⁻¹ ⇒ **t½ ≈ 40 ms**
- Zn²⁺ + EDTA: ≈ 3 × 10⁶ × 6 × 10⁻⁴ ≈ 2 × 10³ s⁻¹ ⇒ **t½ ≈ 0.3 ms**

So within about a millisecond every metal is chelated somewhere.

### The rate-limiting step: Cu/Zn redistribution

Thermodynamically the answer is unambiguous — with only 1 mM EDTA and 2 mM total metal, and log K(CuY) − log K(ZnY) ≈ 18.8 − 16.5 ≈ 2.3, essentially all the EDTA must end up on Cu and Zn is pushed onto glycine (log β₂(ZnGly₂) ≈ 9.2, which easily holds Zn at 10 mM glycine). But since Zn²⁺ and EDTA also combine rapidly, some ZnEDTA forms in the first millisecond and Cu must displace it.

The direct metal-exchange reaction

  Cu²⁺ + ZnY²⁻ → CuY²⁻ + Zn²⁺

has k ≈ 10⁻⁵ – 10⁻⁴ M⁻¹ s⁻¹ at pH 6 (Margerum et al.), which by itself would be far too slow. In this mixture the exchange is accelerated by two things: (i) a small proton-catalyzed dissociation path for ZnY²⁻, and (ii) a *ligand-assisted* path in which glycine attacks ZnY²⁻ to open up the chelate, allowing Cu²⁺ (from CuGly complexes) to enter. With ~1 μM glycinate and ~mM CuGly complexes, this gives an effective first-order rate on ZnY of roughly 10⁻² to 10⁻¹ s⁻¹.

**Half-life for full Cu/Zn sorting: roughly seconds to a couple of minutes.** In practice a mixture like this looks visually equilibrated almost immediately (the light-blue Cu(Gly) color is replaced by the deeper CuEDTA blue in well under a minute), and a stopped-flow or spectrophotometric measurement will show that Cu is >99 % on EDTA within a few minutes at pH 6.

### Summary picture

1. **~10⁻⁶ – 10⁻³ s:** every M²⁺ grabs whichever ligand it collides with first; both CuGly-complexes/CuEDTA and ZnGly-complexes/ZnEDTA are present.
2. **~10⁻¹ – 10² s:** ZnEDTA is slowly attacked by glycine and Cu, the metals swap, and the system relaxes to the thermodynamic minimum with Cu on EDTA and Zn on glycine.

If you need a single number to quote for "how fast does the system reach equilibrium," a half-life of **~10 s at pH 6** is a reasonable middle-of-the-road estimate for the redistribution; the individual complexation events themselves are effectively instantaneous on any laboratory time scale.
