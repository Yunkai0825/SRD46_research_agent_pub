## Answer

**Silver is much more easily reduced to the metal than copper in 0.1 M chloride at 25 °C under mildly acidic, weakly oxidising conditions.** The two Pourbaix diagrams show it directly: at pH 3–5, Ag(0) is thermodynamically stable up to **E ≈ +0.256 V vs SHE**, whereas Cu(0) is stable only up to **E ≈ +0.096 V vs SHE**. So an oxidant / poised potential anywhere in the ~+0.10 to +0.25 V range will leave Ag metal intact while dissolving Cu metal — a difference of ~160 mV in favour of Ag(0).

**Chemical reason.** The two systems are qualitatively different because chloride does opposite things to the two oxidised states:

- **For Ag(I),** chloride *precipitates* it as AgCl(s). The dissolution constant log β = +10.40 for Ag⁺ + Cl⁻ ⇌ AgCl(s) is so large that at 1 mM Ag / 0.1 M Cl⁻ every soluble Ag(I) form — Ag⁺, AgCl(aq) (log β₁ = +3.45), AgCl₂⁻ (log β₂ = +5.67), AgCl₃²⁻ (log β₃ = +5.20), AgCl₄³⁻ (log β₄ = −5.32) — and even Ag₂O(s) (log β = −12.64) is buried under AgCl(s). The map therefore contains only two fields, Ag(s) and AgCl(s), separated by a single pH-flat redox line at +0.256 V. Because neither half-reaction exchanges protons (Ag⁰ ⇌ Ag⁺, then Ag⁺ + Cl⁻ ⇌ AgCl(s)), the boundary has zero Nernstian pH slope — the same +0.256 V threshold applies across pH 0–14.

- **For Cu(I),** chloride does the opposite: it *solubilises* it as the anionic complex [CuCl₂]⁻ (log β₂ = +6.06 for Cu⁺ + 2 Cl⁻ ⇌ [CuCl₂]⁻). This complexation is strong enough to rescue Cu(I) from disproportionation and push the Cu(0) | Cu(I) boundary down from the standard Cu⁺/Cu potential of ≈ +0.52 V by roughly 0.059·(6.06 − 2·log 10) ≈ 0.24 V, landing it at **+0.0964 V vs SHE**. This boundary is also pH-independent across pH 0–6.46 (Cu(s) + 2 Cl⁻ ⇌ [CuCl₂]⁻ + e⁻ is not proton-coupled), then tilts at higher pH along the classical 1 H⁺/1 e⁻ Cu | Cu₂O couple (−59 mV/pH, from +0.096 V at pH 6.46 to −0.349 V at pH 14). Notably CuCl(s) is included in the card (log β_dis = +6.73) but never wins a field — [CuCl₂]⁻ is more stable at these activities.

**Net comparison.** In mildly acidic chloride, both metals are protected against direct hydroxide/oxide chemistry, but chloride stabilises Cu(I) *as a soluble complex* while stabilising Ag(I) *as an insoluble solid*. Soluble Cu(I) is much easier to form thermodynamically (the boundary sits at only +0.10 V), so metallic copper corrodes readily at potentials that leave silver untouched. Equivalently, in the reverse direction: reducing Ag(I) → Ag(0) requires driving E only below +0.256 V, whereas reducing Cu(I) → Cu(0) requires E below +0.096 V — a much more reducing condition. This is the same physics that makes silver the "nobler" of the two metals in chloride environments and underlies the practical use of the Ag/AgCl reference electrode.

## Evidence

- **Cu(0) upper stability boundary — Cu | [CuCl₂]⁻ (DmsRegEq_2):** flat at **E_V = +0.0964 V vs SHE** from pH 0 to pH 6.46 (identical to within 0.8 mV over 6.46 pH units), confirming a non-proton-coupled 1 e⁻ oxidation Cu(s) + 2 Cl⁻ ⇌ [CuCl₂]⁻ + e⁻.
- **Cu(0) upper boundary in the alkaline branch — Cu | Cu₂O (DmsRegEq_6):** slope of (−0.349 − 0.096)/(14 − 6.46) = **−0.059 V/pH**, the textbook Nernstian slope for 2 Cu + H₂O ⇌ Cu₂O + 2 H⁺ + 2 e⁻.
- **Triple point Cu | Cu₂O | [CuCl₂]⁻:** (pH = 6.46, E = +0.0964 V) — acidic terminus of the Cu(0) ceiling.
- **Ag(0) upper stability boundary — Ag | AgCl(s) (DmsRegEq_1):** flat at **E_V ≈ +0.256 V vs SHE** across the entire pH 0–14 window (label switches between +0.2552 V and +0.256 V along the E-cut at pH 7).
- **Key solver constants (from `thermodynamic_reference_constants.md`):**
  - Cu system: log β₂ = **+6.06** for [CuCl₂]⁻; log β_dis = **+6.73** for CuCl(s) (never dominant); ½Cu₂O(s) dissolution log β = **+0.70**; Cu⁺/Cu on the atlas convention corresponding to E° ≈ +0.52 V vs SHE.
  - Ag system: log β = **+10.40** for AgCl(s); log β₁ = **+3.45** (AgCl_aq), log β₂ = **+5.67** (AgCl₂⁻), log β₃ = **+5.20** (AgCl₃²⁻), log β₄ = **−5.32** (AgCl₄³⁻); Ag₂O(s) log β = **−12.64**; Ag(OH) log β = **−12.00**; Ag(OH)₂⁻ log β = **−24.01**.
- **Numerical difference in reducibility:** ΔE = +0.256 − 0.096 = **~160 mV** in favour of Ag(0) at pH 3–5, i.e. the Ag(I)/Ag(0) couple is easier to drive to metal by 0.16 V than the Cu(I)/Cu(0) couple in this chloride medium.
- **Convergence:** Cu map — 106 028 refined + 5627 coarse-unrefined cells retained, only 479 cells excluded (~0.4 %); Ag map — 1751 × 2126 reference-line samples with no convergence failures reported.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute the Pourbaix diagram of Cu in 0.1 M chloride to assess reduction to Cu(0) under mildly acidic, weakly oxidising conditions.
- [Result 02](final/result_02/answer.md): Compute the Pourbaix diagram of Ag in 0.1 M chloride to assess reduction to Ag(0) under mildly acidic, weakly oxidising conditions.
