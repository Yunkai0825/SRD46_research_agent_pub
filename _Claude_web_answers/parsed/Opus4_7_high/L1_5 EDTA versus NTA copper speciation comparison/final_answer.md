---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L1_5 EDTA versus NTA copper speciation comparison"
conversation: https://claude.ai/chat/ce2e5a3b-8481-434f-b295-1b4038ba76b2
started: 2026-09-17T07:54:53.969958+00:00
finished: 2026-09-17T07:56:39.372627+00:00
stop_reason: end_turn
---
Both chelators lock up Cu(II) strongly across pH 3–10, but they do so by very different margins. Here's how the numbers fall out at I = 0.1 M, 25 °C, with 1 mM Cu and 5 mM ligand.

**Key formation constants (log K, I = 0.1)**
- Cu–EDTA (CuY²⁻): log K₁ ≈ 18.78, with minor CuHY⁻ (log K ≈ 3.0) protonated form at low pH
- Cu–NTA (CuT⁻): log K₁ ≈ 12.96, plus a bis complex Cu(T)₂⁴⁻ with log β₂ ≈ 17.4 that matters when ligand is in excess and the ligand is well-deprotonated

**Ligand protonation (competes with Cu binding)**
- EDTA pKₐ ≈ 2.0, 2.67, 6.16, 10.26
- NTA pKₐ ≈ 1.9, 2.5, 9.7

The conditional constant is K′ = K/αH, where αH accounts for the fraction of ligand tied up as protonated forms. Because EDTA has a much higher intrinsic K and a similar αH profile above pH 4, the EDTA complex wins comfortably. With ~4 mM free ligand buffering the system, the pCu values work out roughly as:

![pCu vs pH for 1 mM Cu(II), 5 mM ligand, I=0.1 M, 25 °C](chart_1_pCu%20vs%20pH%20for%201%20mM%20Cu%28II%29,%205%20mM%20ligand,%20I=0.1%20M,%2025%20°C.png)

**Which ligand wins.** EDTA keeps free [Cu²⁺] lower everywhere in the range — by ~2 log units at pH 3, widening to ~4–5 log units through the middle pH range, then narrowing again above pH 8 as NTA gets help from the bis complex Cu(T)₂⁴⁻. The bis complex is not a minor species: with 4 mM excess NTA, it grows from ~20% of Cu at pH 7 to >95% by pH 9, which is what pulls the NTA curve down more sharply above pH 8. Even so, Cu–EDTA remains the tighter chelate throughout because a single molecule of EDTA is hexadentate and its ligand α is more favorable in the neutral–basic range.

**Neither system runs into hydroxide problems.** Free Cu²⁺ never gets high enough for Cu(OH)₂(s) precipitation, and hydroxide complexes (CuOH⁺, Cu(OH)₂⁰, Cu(OH)₃⁻, Cu(OH)₄²⁻) stay well below the chelated forms across pH 3–10.

**Onset of dissociation at low pH.** Both are still overwhelmingly complexed at pH 3, but they're not equally close to the edge.

- Cu–EDTA: essentially quantitative down to pH 3 (<10⁻³% free Cu²⁺). Around pH 2, ~1% of the Cu is free; you also start populating the protonated CuHY⁻ form. Meaningful dissociation begins ~pH 2, and by pH 1 the complex is largely broken up (K′ ≈ 10^1.7).
- Cu–NTA: at pH 3, still ~99.98% bound, but sitting on a shallower cliff. By pH 2, roughly 5–10% of the Cu is free; by pH 1, K′ drops near 10^1 and the complex is essentially dissociated.

Practical takeaway: if the goal is minimizing free Cu²⁺ activity (metal buffering, toxicity, or catalytic control), EDTA gives you an extra ~4–5 orders of magnitude in the pH 5–8 window that matters most for natural and biological waters. NTA is a reasonable substitute above pH 7 (where its bis complex kicks in) but noticeably weaker below pH 5, and it loses its grip a full pH unit earlier on the acid side.
