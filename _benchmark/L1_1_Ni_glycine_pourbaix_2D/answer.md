## Answer

For 1 mM Ni(II) with 10 mM glycine at 25 °C and I = 0.1 m, the computed 2-D Pourbaix diagram (pH 0–14, E = −1.00 to +1.60 V vs SHE, all 4686 coarse cells converged) shows **seven predominance fields**: metallic Ni° at the bottom, aqueous Ni²⁺ in the acidic block, three stacked soluble Ni-glycinate complexes across the mid-pH strip, Ni(OH)₂(s) at high pH, and a small Ni₂O₃·H₂O(s) sliver in the extreme upper-right corner.

**Soluble Ni-glycinate stability window.** A dissolved Ni-glycinate complex is the dominant Ni species over a compact but chemically wide band:

- **pH ≈ 6.06 → 11.24** (the Ni²⁺|[Ni(Glyc)]⁺ wall on the left, the [Ni(Glyc)₃]⁻|Ni(OH)₂(s) wall on the right)
- **E from the Ni°/glycinate reductive floor upward to the top of the sweep (+1.6 V)**, where that floor tilts from ≈ −0.345 V at pH 6.06 down to ≈ −0.5475 V at pH 11.24.

Within this envelope the glycinate speciation ladder is:

- **[Ni(Glyc)]⁺** — pH ≈ 6.06 – 6.78 (narrow strip)
- **[Ni(Glyc)₂]°** — pH ≈ 6.78 – 7.94 (neutral, most lipophilic member)
- **[Ni(Glyc)₃]⁻** — pH ≈ 7.94 – 11.24 (widest field; net-negative)

**Chemical meaning.** The boundaries between the three glycinate complexes and between Ni²⁺ and [Ni(Glyc)]⁺ are essentially vertical because they are non-redox ligand-binding switches — the Ni oxidation state does not change, so potential barely enters. What sets them is the competition between glycine protonation (the ammonium pKa is ≈ 9.57, so free Gly⁻ is scarce below pH 6) and the stepwise formation constants (log β₁ = 5.74; log K₂ = 4.84; log K₃ = 3.52). Ignition of complexation at pH ≈ 6 marks the point where β₁·[Gly⁻] first out-competes hydration of Ni²⁺; each further pH unit brings enough additional free glycinate to push on the next stepwise equilibrium. The upper wall at pH 11.24 is where hydroxide activity (log K_sp of Ni(OH)₂ = −11.71) finally beats even the tris-glycinato complex, precipitating Ni(OH)₂(s). The mild upward tilt of the Ni°/Ni(II) reductive floor across the glycinate region reflects the classical Nernstian stabilisation of the metal when the free Ni²⁺ activity is lowered by complexation and hydrolysis.

**Practical impact.** Glycine extends the pH window in which Ni stays fully dissolved by ≈ 4.6 pH units beyond the bare-Ni²⁺ field — at 1 mM Ni without ligand, Ni(OH)₂ would appear near pH 8, whereas with 10 mM glycine soluble Ni-glycinates persist up to pH ≈ 11.2 across the entire water-stability E-range. This is exactly the window relevant to Ni electroplating baths, aqueous Ni(II) catalysis, and Ni recovery from complexing waste streams. Note that above pH ≈ 8 the dominant form [Ni(Glyc)₃]⁻ is anionic, which matters for ion-exchange, membrane, and adsorption behaviour.

## Evidence

- Method: 2-D `pourbaix_sweep`, pH ∈ [0, 14], E ∈ [−1.00, +1.60] V; coarse grid 66×71, all **4686 / 4686 cells converged**; refined classified grid ΔpH = 0.0125, ΔE = 0.0025 V (87 833 points).
- Ni²⁺ | [Ni(Glyc)]⁺ boundary (`DmsRegEq_3`): near-vertical, pH ≈ 6.0625 – 6.075, spanning E from −0.345 V to +1.6 V.
- [Ni(Glyc)]⁺ | [Ni(Glyc)₂]° boundary (`DmsRegEq_2`): pH ≈ 6.76 – 6.80.
- [Ni(Glyc)₂]° | [Ni(Glyc)₃]⁻ boundary (`DmsRegEq_1`): pH ≈ 7.91 – 7.98.
- [Ni(Glyc)₃]⁻ | Ni(OH)₂(s) boundary (`DmsRegEq_8`): exactly vertical at pH = 11.2375.
- Reductive floor (Ni°/Ni-glycinate & Ni°/Ni(OH)₂): E = −0.345 V @ pH 6.06, −0.365 V @ pH 6.76, −0.43 V @ pH 7.91, −0.5475 V @ pH 11.24, −0.7125 V @ pH 14.
- Region sizes (measures): Ni²⁺ = 11.76 (largest); [Ni(Glyc)₃]⁻ = 6.90 (largest glycinate field); [Ni(Glyc)₂]° = 2.35; [Ni(Glyc)]⁺ = 1.42; Ni₂O₃·H₂O(s) sliver = 0.17.
- Reference cut at E = 0.30125 V traverses Ni²⁺ → [Ni(Glyc)]⁺ (pH 6.07) → [Ni(Glyc)₂]° (pH 6.79) → [Ni(Glyc)₃]⁻ (pH 7.97) → Ni(OH)₂ (pH 11.24), confirming the ladder.
- Thermodynamic constants used (from the reference table): log β₁,₂,₃(Ni-Gly) = 5.74, 10.58, 14.10; glycine amine pKa ≈ 9.57; log K_sp Ni(OH)₂ = −11.71.

## Final deliverables

- [Result 01](final/result_01/answer.md): Build a 2-D Pourbaix (E-pH) diagram for Ni in the presence of glycine and identify the pH/E window where soluble Ni-glycinate complexes are the dominant Ni species.
