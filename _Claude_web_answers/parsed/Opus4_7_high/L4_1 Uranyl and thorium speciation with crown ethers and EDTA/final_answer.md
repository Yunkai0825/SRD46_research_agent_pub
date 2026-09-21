---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L4_1 Uranyl and thorium speciation with crown ethers and EDTA"
conversation: https://claude.ai/chat/2a1b756e-6a79-43e3-a7f5-b98f32630995
started: 2026-09-17T02:02:44.705981+00:00
finished: 2026-09-17T02:03:57.187083+00:00
stop_reason: end_turn
---
At pH 5 with these concentrations, EDTA wins the competition decisively for both actinides, and 18-crown-6 is essentially a spectator. Here's why, and what the speciation looks like.

**Why crown ether loses**

18-crown-6 is a hard neutral O-donor macrocycle that binds cations that fit its ~2.6–3.2 Å cavity (K⁺ is the textbook match). In water, its complexes with hard, highly-charged actinide aquo ions are very weak — log K for UO₂²⁺·(18C6) and Th⁴⁺·(18C6) in aqueous solution is on the order of ≤1 (the equatorial coordination sphere of UO₂²⁺ and the tightly held hydration shell of Th⁴⁺ both disfavor macrocyclic wrapping in H₂O). EDTA, by contrast, is a hexadentate anionic chelator with log K₁ ≈ 13–14 for UO₂Y²⁻ and log K₁ ≈ 23 for ThY (NIST/Martell, 25 °C, I = 0.1). Even after accounting for EDTA protonation at pH 5 (αY⁴⁻ ≈ 3 × 10⁻⁷, so log αY ≈ −6.5), the conditional constants remain ~10⁶·⁵ for UO₂ and ~10¹⁶·⁵ for Th — many orders of magnitude larger than anything the crown can offer.

**Dominant species (mole fractions of each total)**

Uranyl (C_U = 1 mM):
- UO₂(EDTA)²⁻ (i.e., UO₂Y²⁻), with a minor UO₂(HY)⁻ contribution at pH 5 — together ≳ 99.9%
- Free UO₂²⁺ and hydrolysis products (UO₂)₂(OH)₂²⁺ etc.: negligible (EDTA suppresses hydrolysis)
- UO₂·(18C6) adducts: < 0.01%

Thorium (C_Th = 1 mM):
- Th(EDTA) (ThY, neutral): ≳ 99.99%. A small Th(OH)Y⁻ mixed complex may appear but at pH 5 it is minor
- Free Th⁴⁺ and Th(OH)ₙ: negligible
- Th·(18C6): < 0.001%

EDTA (C_EDTA = 5 mM), mass balance:
- ~1 mM tied up as UO₂Y²⁻/UO₂(HY)⁻
- ~1 mM tied up as ThY
- ~3 mM free, distributed at pH 5 (pKa₅ ≈ 6.1, pKa₆ ≈ 10.2) as roughly 90–93% H₂Y²⁻ and 7–10% HY³⁻, with H₃Y⁻ and Y⁴⁻ traces

18-crown-6 (C_L = 5 mM):
- ~100% as free, uncomplexed 18C6 in solution (aside from any weak outer-sphere association with background Na⁺/K⁺ from I = 0.1 m adjustment, which was unspecified)

**Bottom line**

The "uranyl-crown" and "thorium-crown" complexes you might expect are essentially absent in aqueous solution at pH 5; both actinides are quantitatively sequestered by EDTA. To see meaningful crown-ether coordination to UO₂²⁺ or Th⁴⁺ you would need to either (a) remove/mask EDTA (e.g., far lower pH where EDTA is fully protonated, or a competing metal that sequesters EDTA), or (b) move to a low-water medium (methanol, acetonitrile, or the solid state), where 18-crown-6·UO₂(H₂O)ₙ²⁺ and Th·crown adducts are well characterized.

If you want, I can run this through a proper equilibrium solver (e.g., a Newton–Raphson mass-action calculation with the NEA-TDB constants for hydrolysis and both EDTA and crown-ether equilibria) and give you the actual percentages and free-ligand activities to 3–4 sig figs — just say the word and I'll set it up.
