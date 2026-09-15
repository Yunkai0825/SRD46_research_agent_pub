## Answer

The joint E–pH sweep over pH 0–14 and E = −1.0 to +1.5 V (71×51 fully converged grid) resolves **9 dominant Cu regions and 10 dominant Fe regions** in one shared solution. The two metals barely share ligands: Fe(III) locks up citrate and oxidizes into hematite over almost the entire oxidizing half of the field, which **frees citrate and glycine to carry Cu(II)** through the mid-pH belt. Ammonia and chloride, though present at 0.1 M, play only minor cameo roles.

**Copper partitioning** — from acidic-oxidizing corner clockwise:
- Free **Cu²⁺** occupies the small strong-acid/oxidizing corner (pH ≲ 3.3, E ≳ +0.375 V). Cu(II) hydrolysis is too weak (log β(CuOH⁺) = −7.9) to compete lower down.
- A thin **[CuCl₂]⁻** (Cu(I)) band (pH 0–5.7, E ≈ +0.075–0.375 V) sits just above the Cu(0) floor, stabilized by log β = +6.06 at [Cl⁻] = 0.1 M.
- Citrate takes over at pH 3.3–7.5: **[Cu₂(Cit)₂(OH)]³⁻** in a narrow 3.3 < pH < 4.1 strip and then **[Cu₂(Cit)₂(OH)₂]⁴⁻** (log β = +6.34) as a large region (pH 4.1–7.5, all the way to +1.5 V). These dimers dominate because Fe(III) has already precipitated as hematite in this pH window, releasing the citrate pool to Cu.
- **[Cu(Gly)₂]** (log β = +15.1) takes the neutral band pH 7.5–10.7 across essentially the entire oxidized potential range — the chelate effect wins once glycine deprotonates (pKa₂ = 9.57).
- **CuO(s)** (log Ks = −7.65) covers pH ≳ 10.9 at oxidizing E; **Cu₂O(s)** appears as a thin band beneath it (pH 10.9–14, E ≈ −0.05 to +0.025 V), giving the classical Cu / Cu₂O / CuO staircase.
- **Cu(0) metal** is the reducing floor across the whole pH range below E ≈ −0.1 to +0.075 V (the single largest Cu region, 14.0 sq-units). A **razor-thin [Cu(NH₃)₂]⁺** Cu(I)-ammine sliver (0.31 sq-units, pH 7.9–10.7, E ≈ −0.1 to 0 V) is the only place ammonia dominates for either metal.

Key Cu junctions all cluster along the ligand-competition seam just above the Cu/Cu(I) redox line: (5.7, +0.075 V) Cu | Cu₂Cit₂(OH)₂⁴⁻ | CuCl₂⁻; (7.5, +0.025 V) Cu | Cu₂Cit₂(OH)₂⁴⁻ | Cu(Gly)₂; (7.9, +0.025 V) Cu | Cu(NH₃)₂⁺ | Cu(Gly)₂; (10.7, +0.025 V) Cu₂O | Cu(NH₃)₂⁺ | Cu(Gly)₂; (10.9, +0.025 V) Cu₂O | CuO | Cu(Gly)₂.

**Iron partitioning** — Fe spans four oxidation states (0, +II, +III, +VI):
- **Fe(0)** is the reducing floor across all pH, entered by the Fe/Fe²⁺ couple near E ≈ −0.55 V at low pH sloping to E ≈ −0.9 V at pH 14.
- **Fe²⁺(aq)** dominates the acid mid-potential window (pH 0–4, E ≈ −0.52 to +0.28 V), bounded above by the Fe²⁺/hematite couple with the characteristic −0.177 V/pH slope of the 2e⁻/6H⁺ half-reaction and to the right by the pH-4.1 vertical to Fe(II)-citrate.
- **[Fe(Cit)]⁻** (Fe(II)-citrate, log β = +4.40) forms a wedge pH ≈ 4.1–7.7 between free Fe²⁺, hematite, and magnetite. Two thin disconnected slivers of **[Fe₂(Cit)₂(OH)₂]⁴⁻** (log β = −5.4) sit near pH 7.7–9.1, E ≈ −0.58 V.
- **Fe₃O₄ (magnetite)** covers the alkaline-reducing block above pH ≈ 9, E ≈ −0.87 to −0.18 V (log Ks = −7.13, Atlas).
- **α-Fe₂O₃ (hematite)** is the single largest region in the whole field (13.16 sq-units), spanning virtually the entire oxidizing half above pH ≈ 1 up to the ferrate lid, governed by the dissolution log β = +0.70 for Fe³⁺ + 3 H₂O.
- **Fe³⁺(aq)** occupies only a tiny corner (pH < 1.1, E > 0.775 V) — Fe(III) hydrolyzes too strongly (log β(FeOH²⁺) = −2.73) to persist as the free cation.
- **FeO₄²⁻ (ferrate)** forms the high-E lid, sloping from E ≈ +0.33 V at pH 14 to +1.5 V at pH ≈ 2.
- **A tiny [Fe(OH)₃]⁻** corner appears at pH 14, E ≈ −0.9 V.

**Cross-metal chemistry.** Citrate binds Fe(III) very strongly (log β = +11.19 for [Fe(Cit)]) so Fe would seem to monopolize it, but hematite is even more stable — so Fe(III) precipitates and hands citrate back to Cu(II) in the pH 4–7.5 window. Ammonia and chloride at 0.1 M can't out-chelate citrate or glycine for Cu(II) and are far too weak against hydrolysis for Fe (Fe-NH₃ log β ≤ +2.75; Fe-Cl ≤ +2.13). The net picture is that **both metals are almost fully sequestered**: Fe into hematite/magnetite plus a small citrate wedge, Cu into citrate/glycine complexes plus oxide solids, with essentially no free divalent aquo species anywhere the ligands are deprotonated.

## Validation status: incomplete

## Evidence
- Grid: 71 × 51 = 3621 cells, ΔpH = 0.2, ΔE = 0.05 V; `n_coarse_unrefined = 3621`, `n_coarse_excluded = 0` — every cell converged.
- Cu topology: 9 dominant labels, 9 connected regions, 16 boundaries, 16 junctions (8 internal triple points + 8 sweep-limit).
- Fe topology: 9 dominant labels, 10 connected regions (Fe₂(Cit)₂(OH)₂⁴⁻ is disconnected), 18 boundaries, 17 junctions.
- Constants used verbatim from `thermodynamic_reference_constants.md`: log β Cu(Gly)₂ = +15.1, Cu(NH₃)₄²⁺ = +12.3, Cu₂(Cit)₂(OH)₂⁴⁻ = +6.34, [CuCl₂]⁻ = +6.06, CuO(s) log Ks = −7.65, Cu₂O(s) = +0.70; Fe(Cit) = +11.19, [Fe(Cit)]⁻(II) = +4.40, α-Fe₂O₃ = +0.70, Fe₃O₄ = −7.13, FeOH²⁺ = −2.73, Fe(OH)₄⁻ = −21.60; citrate pKa₁,₂,₃ ≈ 2.90/4.35/5.65; glycine pKa₁,₂ ≈ 2.33/9.57; NH₄⁺ pKa = 9.26.
- Fe²⁺/hematite boundary from (pH 4.1, +0.275 V) to (pH 1.1, +0.775 V) — slope −0.177 V/pH matches 2 e⁻ / 6 H⁺.
- Fe²⁺/Fe³⁺ couple horizontal at E = +0.775 V, as expected pH-independent.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute the joint two-dimensional E-pH Pourbaix diagram for a single solution containing Cu(II) and Fe(III) with citrate, glycine, chloride, and ammonia, and characterize how the two metals partition among aqueous complexes and solids across the field.
