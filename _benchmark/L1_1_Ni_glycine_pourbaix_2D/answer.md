## Answer

The 2-D Pourbaix diagram for 1 mM Ni + 10 mM glycine (25 °C, I = 0.1 m, pH 0–14, E = −1 to +1.6 V vs SHE) resolves into **nine dominant-species regions**: metallic Ni⁰(s) along the reducing floor, aqueous Ni²⁺ across the acidic Ni(II) band, three successive Ni-glycinate complexes in a near-neutral–to-alkaline vertical staircase, β-Ni(OH)₂ as a small alkaline wedge, and mixed Ni₃O₄·2H₂O, Ni₂O₃·H₂O, NiO₂·2H₂O solids climbing the upper (oxidising) part of the map.

**Soluble Ni-glycinate stability windows** (each spans essentially the full Ni(II) E-band because these are non-redox ligand-exchange complexes):

| Complex | pH window | E window (V vs SHE) |
|---|---|---|
| [Ni(Glyc)]⁺ | ≈ 6.07 → 6.76 | ≈ −0.35 up to +0.87 |
| [Ni(Glyc)₂]⁰ | ≈ 6.76 → 7.92 | ≈ −0.37 up to +0.69–0.77 |
| [Ni(Glyc)₃]⁻ | ≈ 7.92 → 11.24 | ≈ −0.43 up to +0.26–0.69 |

**Chemical meaning.** Below pH ~6, glycine is mostly zwitterionic (HGlycine, pK_a2 ≈ 9.57) so [Glyc⁻] is too low to displace water from the Ni(II) aqua ion — Ni²⁺(aq) dominates. As pH rises, deprotonation feeds free glycinate into solution, and the successive stepwise formation constants (log K₁ = 5.74, log K₂ = 4.84, log K₃ = 3.52) drive the 1:1 → 1:2 → 1:3 crossovers at pH 6.07, 6.76, and 7.92. The bis-glycinate [Ni(Glyc)₂]⁰ is the biologically relevant species near neutral pH; the tris-chelate [Ni(Glyc)₃]⁻ is the widest field and, crucially, **suppresses Ni(OH)₂ precipitation between pH ~8 and 11** — in pure Ni–water Ni(OH)₂ would already deposit near pH 8. This is exactly the chelation service glycine provides: it keeps ~1 mM Ni soluble across almost the entire water-stability potential window up to pH ~11.

Above pH ≈ 11.24, even the tris-glycinate loses to β-Ni(OH)₂(s), and above E ≈ +0.7 V (near neutral) Ni(II) is oxidised out of solution into the mixed Ni(II,III) oxide Ni₃O₄·2H₂O, then Ni₂O₃·H₂O (Ni(III)) and NiO₂·2H₂O (Ni(IV)) as E climbs further — the classic Nernstian slopes (e.g. the Ni²⁺/Ni₂O₃·H₂O boundary tilting from (pH 5.36, +1.013 V) to (pH 4.13, +1.227 V), a 2 e⁻ / 6 H⁺ couple) match textbook expectations. On the reducing side, the Ni⁰(s) floor sits near E ≈ −0.33 V in acid, sagging to −0.71 V at pH 14 as hydroxide/oxide screening lowers the Ni²⁺ activity.

## Evidence
- 66 450/66 450 refined cells converged (`speciation_full_Ni_+_Glycine.csv` header `n_refined: 66450, n_coarse_unrefined: 0`); topology has 9 labels, 9 connected regions, 18 boundary manifolds, 10 internal + 6 sweep-limit junctions.
- Aqueous Ni(II) region measures: Ni²⁺ = 10.11, [Ni(Glyc)]⁺ = 0.84, [Ni(Glyc)₂] = 1.31, [Ni(Glyc)₃]⁻ = 3.47.
- Glycinate crossover junctions: `DmsRegEqJnc_3` at (pH 6.06, −0.345 V), `DmsRegEqJnc_2` at (pH 6.764, −0.365 V), `DmsRegEqJnc_1` at (pH 7.916, −0.429 V), `DmsRegEqJnc_9` at (pH 11.236, −0.549 V).
- Formation constants used (from reference table): log β₁ = 5.74, log β₂ = 10.58, log β₃ = 14.10; glycine pK_a2 = 9.57.
- Redox caps of the Ni(II) aqueous band: [Ni(Glyc)]⁺ → Ni₃O₄·2H₂O at +0.87 V; [Ni(Glyc)₂] → +0.69–0.77 V; [Ni(Glyc)₃]⁻ → +0.26–0.69 V.
- Ni²⁺|Ni₂O₃·H₂O redox line from (pH 5.36, +1.013 V) to (pH 4.13, +1.227 V) — Nernstian 2 e⁻/6 H⁺ slope. Ni⁰|Ni(OH)₂ line from (pH 11.236, −0.549 V) to (pH 14, −0.711 V).

## Final deliverables

- [Result 01](final/result_01/answer.md): Build a 2-D Pourbaix diagram (E vs pH) for nickel in the presence of glycine and identify the stability window of soluble Ni-glycinate complexes.
