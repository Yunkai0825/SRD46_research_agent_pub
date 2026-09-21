---
export: Fable5_1
model: claude-fable-5-1
effort: max
run: effort-max_run1
prompt: "L1_1 Nickel-glycine Pourbaix diagram and complex stability"
conversation: https://claude.ai/chat/f9fbd3ca-47f8-4716-9453-ec85f3d90474
started: 2026-09-17T02:47:50.090299+00:00
finished: 2026-09-17T03:06:13.232637+00:00
stop_reason: end_turn
---
[Ni–glycine Pourbaix diagram (1 mM Ni, 10 mM Gly, 25 °C, I = 0.1 m)](ni-glycine-pourbaix.html)

The diagram is published above. It was built by solving the full Ni/glycine mass balance at every pH (free Ni²⁺ and free glycinate, with the glycine bound to Ni depleting the pool), then testing each solid for saturation at every (E, pH); hovering gives the predominant species and the Ni(II) distribution at that point.

**Stability window of the soluble glycinate complexes** (1 mM Ni, 10 mM Gly, 25 °C, I = 0.1 m)

| Complex | pH range where it predominates | Peak fraction of Ni |
|---|---|---|
| NiGly⁺ | 5.8 – 6.8 | 61 % at pH 6.3 |
| NiGly₂ | 6.8 – 8.3 | 71 % at pH 7.6 |
| NiGly₃⁻ | 8.3 – 10.9 | 94 % at pH 10.5 |

Boundaries of the combined window:

- Acid side, pH ≈ 5.8: glycine is protonated (pKₐ 9.57 for the amine), free Gly⁻ collapses and Ni²⁺(aq) takes over.
- Alkaline side, pH 10.86: crystalline β-Ni(OH)₂ saturates at 1 mM Ni. If the hydroxide is freshly precipitated (log *Kₛ₀ ≈ 12.7 instead of 11.0) this moves to pH ≈ 11.7 (dotted line on the plot), so in practice NiGly₃⁻ often persists to pH ~11.5.
- Lower potential, Ni deposition: −0.35 V (pH 5.8) → −0.38 V (pH 7) → −0.45 V (pH 8.3) → −0.55 V (pH 10) → −0.56 V (pH 10.9), all vs SHE. Complexation pulls the Ni/Ni(II) line down at 30, 59 and 89 mV per pH unit through the NiGly⁺, NiGly₂ and NiGly₃⁻ fields, flattening once glycine is fully deprotonated near pH 9.6. It sits only ~40–50 mV above the H₂ line, so hydrogen evolution competes with deposition throughout.
- Upper potential, oxidation to β-NiOOH: +1.15 V (pH 5.8) → +1.00 V (pH 7) → +0.92 V (pH 8.3) → +0.80 V (pH 10) → +0.67 V (pH 10.9). Complexation raises this boundary by up to ~0.45 V relative to the uncomplexed Ni(OH)₂/NiOOH couple, and it lies above the O₂/H₂O line everywhere in the window — the complexes are stable across the entire water stability field between pH 5.8 and 10.9.

**Data and conventions** (the full table is on the page): E°(Ni²⁺/Ni) = −0.237 V; β-Ni(OH)₂ log *Kₛ₀ = 11.0; Ni²⁺ hydrolysis from Baes & Mesmer; β-NiOOH anchored to the experimental nickel-electrode couple (0.49 V vs SHE at a(OH⁻) = 1); glycine log K = 9.57 / 2.35 and Ni–glycinate log β₁₋₃ = 5.78 / 10.58 / 14.0 at I = 0.1 M (Martell & Smith / IUPAC). Infinite-dilution constants were corrected to I = 0.1 with the Davies equation; pH is −log[H⁺]. Sensitivity checks: ±0.1 in the glycinate constants shifts the Ni²⁺/NiGly⁺ boundary by ±0.1 pH and the precipitation edge by ±0.05 pH; using E° = −0.257 V instead lowers the deposition line by 20 mV.

Two caveats worth knowing: Ni₃O₄, Ni₂O₃ and NiO₂ from the Pourbaix Atlas were deliberately omitted because their tabulated free energies are inconsistent with the observed Ni(OH)₂/NiOOH couple (they would predict Ni(OH)₂ oxidising at ~0.1–0.3 V at pH 14), so the top of the Ni²⁺ field in strong acid is open-ended on this diagram; and glycine's own oxidation is thermodynamically possible above ~+0.5 V but kinetically slow, so it is ignored as in standard ligand Pourbaix diagrams. If you want the diagram at other Ni/glycine ratios or with a different hydroxide solubility, I can regenerate it.
