## Answer

For 1 mM Cu in 0.1 M total ammonia at 25 °C and I = 0.1 m (hydroxide solids preferred), the computed E–pH diagram shows that **soluble Cu(II)-ammine complexes dominate over both Cu(OH)₂(s) and metallic Cu in a well-defined "ammoniacal leach" window centered around pH 8–10.3 at oxidising potentials**. Concretely, three contiguous Cu(II)-ammine fields exist:

- **[Cu(NH₃)₄]²⁺** — the main window: **pH ≈ 8.20 – 10.32**, from E ≈ +0.14 V (rising with decreasing pH to ~+0.26 V) up to the top of the diagram (+1.4 V).
- **[Cu(NH₃)₃]²⁺** — a narrow transitional strip on the acidic edge: **pH ≈ 7.996 – 8.204**, E ≈ +0.27 to +1.4 V.
- **[Cu(NH₃)]²⁺** — a very thin sliver just above the Cu²⁺ field: **pH ≈ 6.16 – 6.42**, E ≥ +0.284 V.

The chemistry behind this shape is straightforward. Free NH₃ is controlled by the NH₄⁺/NH₃ acid–base equilibrium (pKₐ ≈ 9.26), so below pH ~9 most of the 0.1 M total ammonia is protonated NH₄⁺ and unavailable as a ligand — which is why the higher ammine complexes only become dominant near and above pH 8, and why the lower-n ammines appear only as narrow slivers on the acidic side. Once free NH₃ rises above pH ~9, the very stable [Cu(NH₃)₄]²⁺ (log β₄ ≈ +12.3) outcompetes Cu(OH)₂ precipitation: the [Cu(NH₃)₄]²⁺/Cu(OH)₂(s) boundary is essentially vertical at pH ≈ 10.14 above E ≈ +0.28 V, meaning ammonia pushes the onset of Cu(OH)₂ precipitation about 3–4 pH units higher than in a pure hydroxide system — the classic "ammoniacal dissolution of copper hydroxide."

Below the Cu(II)-ammine fields, the Cu(I) complex **[Cu(NH₃)₂]⁺** (log β₂ ≈ +9.9) forms a large soluble wedge from pH ≈ 7.05 to 11.47 at moderately reducing potentials (from the Cu(s)/[Cu(NH₃)₂]⁺ line up to ~+0.27 V). This is also a soluble Cu-ammine field but Cu(I), not Cu(II); it stabilises Cu(I) in solution and depresses the Cu(s)/Cu(I) couple from ~+0.24 V (bare Cu/Cu²⁺, pH < 5) to as low as ~−0.14 V at pH > 11, which is precisely why electrodeposition of copper from ammoniacal baths requires much more negative potentials than from acid sulfate.

The remaining topology is consistent with this picture: two small Cu₂O lobes fill the gaps where neither NH₃ (protonated) nor OH⁻ can solubilise Cu(I); a low-pH Cu(OH)₂ lobe appears above the ammine wedge; and a CuO₂²⁻ field opens only for pH > 13.58, bounded by a vertical (electron-free) Cu(OH)₂/CuO₂²⁻ acid–base line. Vertical boundaries in the diagram are pH-only equilibria; diagonal ones are proton-coupled redox reactions with the expected ~−59 mV/pH slopes modified by ligand stoichiometry.

## Evidence

- Domain and resolution: pH [0, 14], E [−1.0, +1.4] V; final classified grid ΔpH = 0.008 V, ΔE = 0.0016 V (1751 × 1501 samples). 9 unique dominant-species labels, 11 connected regions, 21 boundary curves, no unconverged samples.
- **[Cu(NH₃)₄]²⁺ region (DmsReg_7):** "pH ≈ 8.20 – 10.32, E from ~+0.14 up to +1.4 V. Left boundary is the vertical [Cu(NH₃)₄]²⁺/[Cu(NH₃)₃]²⁺ line at pH = 8.204; right boundary is [Cu(NH₃)₄]²⁺/Cu(OH)₂(s) essentially vertical at pH ≈ 10.14 above E ≈ +0.28."
- **[Cu(NH₃)₃]²⁺ region (DmsReg_10):** "thin vertical strip pH 7.996 – 8.204 from E ≈ +0.27 to +1.4 V."
- **[Cu(NH₃)]²⁺ region (DmsReg_11):** "narrow vertical sliver, pH 6.164 – 6.42, E from +0.284 up to the top (1.4 V)."
- Triple points bounding the [Cu(NH₃)₂]⁺ wedge (Cu(I) ammine): (7.052, +0.1192), (11.468, −0.1432), (11.468, −0.0152), (10.324, +0.1352), (8.204, +0.2616), (7.996, +0.2712).
- Cu(s)/Cu²⁺ line at E ≈ +0.239 V for pH 0 – 5.05; Cu/[Cu(NH₃)₂]⁺ diagonal from (7.05, +0.119) to (11.47, −0.143) — quantifies the ammonia-induced depression of the copper deposition potential.
- Cu(OH)₂/CuO₂²⁻ vertical boundary at pH = 13.58 (pure acid–base, no electrons).
- Reference constants used: pKₐ(NH₄⁺) = 9.26; log β₄(Cu(II)-tetraammine) = +12.30; log β₂(Cu(I)-diammine) = +9.92; Cu(OH)₂(s) card constant = −8.68.
- Cu(OH)₂(s) was included in preference to CuO(s) as requested; Cu₂O retained as the Cu(I) solid.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute a 2-D Pourbaix (E-pH) diagram for Cu in the presence of ammonia, and identify the region where soluble Cu-ammine complexes dominate over Cu(OH)2(s) and Cu(s).
