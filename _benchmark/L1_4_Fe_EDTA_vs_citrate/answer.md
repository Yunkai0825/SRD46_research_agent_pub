## Answer

**EDTA wins decisively.** With a 5:1 ligand:Fe(III) ratio at 25 °C and I = 0.1 M:

- **EDTA keeps Fe(III) fully soluble across the entire pH 4–9 window.** Fe(OH)₃(s) never forms. The metal simply switches between two Fe–EDTA chelates: [Fe(EDTA)]⁻ dominates pH 4.0–6.96 (99.9 % at pH 4.0), and [Fe(EDTA)(OH)]²⁻ dominates pH 6.96–9.0 (99.1 % at pH 9.0). The crossover at pH ≈ 6.96 is deprotonation of an axial water on the chelate, *not* Fe hydrolysis.
- **Citrate holds Fe(III) soluble only up to pH ≈ 6.0.** Below that, iron is carried almost entirely as the dinuclear μ-hydroxo dicitrate [Fe₂(Citr)₂(OH)₂]²⁻ (≈87 %) with [Fe(Citr)(OH)]⁻ (≈13 %). **Fe(OH)₃(s) reappears at pH ≈ 6.10**, capturing 30 % of Fe already at that point, 92 % by pH 6.4, and >99 % by pH 6.8. It never redissolves within the scanned range.

**Chemical interpretation.** EDTA is a hexadentate chelator with log β([Fe(EDTA)]⁻) = +25.10 — large enough that the conditional Fe³⁺ activity stays orders of magnitude below the Fe(OH)₃(s) solubility limit (log K_s0 = −3.20) at every pH from 4 to 9, even after the cost of stripping protons off H₂EDTA²⁻/HEDTA³⁻. Rising pH is absorbed by proton loss from a coordinated water on the intact chelate rather than by iron dropping out as an oxide.

Citrate is a much weaker, only tridentate ligand (log β ≈ +11 for [Fe(Citr)] and +21 for the dinuclear, versus +25 for Fe–EDTA). Its μ-OH-bridged dimer works up to ≈ pH 6 because bridging hydroxides do part of the stabilization, but above pH 6 the dimer dissociates as its bridging OHs are consumed and free Citr³⁻ can no longer suppress [Fe³⁺]·[OH⁻]³ below K_s0 — ferrihydrite precipitates. This is the classical reason why citrate is inadequate for keeping Fe(III) in solution at physiological/near-neutral pH and why stronger chelators (EDTA, siderophores) are used above pH 7.

**Widest solubility window:** EDTA (all of pH 4–9, no precipitation).
**Fe(OH)₃(s) reappearance:** EDTA — never within pH 4–9; Citrate — pH ≈ 6.10.

## Validation status: incomplete

## Evidence

- Fe(III)/EDTA verdict: "Dominant species by pH region: pH 4.0–7.0 → [Fe(EDTA)]⁻; pH 7.0–9.0 → [Fe(EDTA)(OH)]²⁻. Crossover pH ≈ 6.96." 51/51 grid points converged. No Fe(OH)₃(s) entry in the precipitation report.
- Fe(III)/EDTA calculation: "Across the entire pH 4–9 window, essentially 100% of the iron is held in solution as Fe(III)–EDTA complexes; Fe(OH)₃(s) is never predicted to precipitate."
- Fe(III)/citrate verdict, Precipitation section: "pH 6.10: [Fe(OH)3](s) (2.99e-04 M)."
- Fe(III)/citrate verdict crossovers: "[Fe(Citr)(OH)]⁻ ↔ Fe(OH)₃(s) at pH ≈ 6.04; [Fe₂(Citr)₂(OH)₂]²⁻ ↔ Fe(OH)₃(s) at pH ≈ 6.15."
- Fe(III)/citrate calculation: "Solid fraction climbs to 91.6 % at pH 6.4, 95.8 % at pH 6.5, 99.3 % at pH 6.8, and ≥99.9 % from pH 7.5 onward."
- Reference constants: log β([Fe(EDTA)]⁻) = +25.10; log β([Fe(EDTA)(OH)]²⁻) = +17.71; log β([Fe(Citr)]) ≈ +11.2; log β([Fe₂(Citr)₂(OH)₂]²⁻) ≈ +21.2; log K_s0(Fe(OH)₃(s)) = −3.20.
- Both runs: 51/51 grid points converged at target I = 0.1 M, T = 25 °C.

## Final deliverables

- [Result 01](final/result_01/answer.md): Assess Fe(III)-EDTA speciation and Fe(OH)3(s) solubility window over pH 4-9.
- [Result 02](final/result_02/answer.md): Assess Fe(III)-citrate speciation and Fe(OH)3(s) solubility window over pH 4-9.
