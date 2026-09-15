## Answer

In a single pot holding 1 mM Fe(III), 1 mM Cu(II), 5 mM citrate, and 0.1 M Cl⁻ (25 °C, I = 0.1 m), citrate is the dominant complexing agent for both metals across almost the entire pH 2–10 window, while chloride only matters for Cu(I) in an acidic, mildly-oxidizing corner. The two metals do not really "compete" for citrate at these stoichiometries — there is a 2.5-fold molar excess of citrate over the combined metals, so both are held as citrate complexes wherever citrate can deprotonate. Chloride only takes over Cu speciation transiently, and only as a Cu(I) stabilizer, because the Cu(I)-chloride complexes are far stronger than the Cu(II)-chloride ones.

**Cu speciation, region by region**
- **pH 2–3.3, E > 0.375 V (small oxidized wedge):** free **Cu²⁺** is dominant. Citrate is too protonated (H₃L/H₂L⁻; stepwise pKₐ 2.90, 4.35, 5.65 from the card) to complex Cu efficiently, and the Cu(II)-Cl complex is weak (log β [CuCl]⁺ = +0.20).
- **pH 2–5.9, 0.075 V < E < ~0.375 V:** **[Cu(Cl)₂]⁻ (Cu(I))** dominates. Chloride pulls Cu(II) down to Cu(I) because the Cu(I)-chloride complexes are strong (log β = +3.10, +6.06, +5.39 for the mono-, di-, and tri-chloro Cu(I) species), depressing the Cu(II)/Cu(I) couple far below the ~+0.16 V of the aquo pair.
- **pH 3.3–4.1 (narrow slab):** the mono-hydroxo dimer **[Cu₂(Citr)₂(OH)]³⁻** (log β = +11.20) appears as a transition band.
- **pH ≳ 4.1, E > ~0.1 V (the largest Cu field, region measure 6.71):** **[Cu₂(Citr)₂(OH)₂]⁴⁻** (log β = +6.34 from Cu²⁺ + [H₋₁L]) is dominant. Citrate keeps Cu(II) fully in solution across the entire neutral-alkaline oxidized range; tenorite CuO(s) (log β = −7.65) and Cu(OH)₂(s) (−8.68) are present in the model but never win, i.e. citrate suppresses hydrolytic precipitation.
- **E < ~0.075 V:** metallic **Cu(s)** across most of the pH range, with a small **cuprite [(Cu₂O)₀.₅](s)** field appearing above pH ~7.3 (log β = +0.70). The triple junction at (pH 7.3, E 0.075 V) is the Cu-metal / cuprite / Cu-citrate-dimer point — effectively the corrosion/passivation crossover for Cu in this bath.

**Fe speciation, region by region**
- **pH < 4.5, E below the Fe(III)/Fe(II) line:** free **Fe²⁺** dominates. Below pH 4.5 the [L]³⁻ fraction is too small (citrate still mostly H₂L⁻/HL²⁻), so aqua Fe²⁺ wins even though [Fe(Citr)H₂]⁺ (log β = +11.10) and [Fe(Citr)H] (+8.55) exist as minors.
- **pH 4.5–~9, E < ~−0.3 V:** **[Fe(Citr)]⁻** (log β = +4.40 from Fe²⁺ + L³⁻) sweeps the reduced field. A very thin sliver of the Fe(II) dimer **[Fe₂(Citr)₂(OH)₂]⁴⁻** (log β = −5.40) shows up at pH 7.7–9.5 at strongly reducing E (region measure only 0.24).
- **pH 2–4.5, oxidized:** the Fe(III) citrate dimer **[Fe₂(Citr)₂(OH)₂]²⁻** (log β = +21.20) is dominant. The Fe²⁺ / Fe(III)-citrate-dimer redox line runs from (pH 4.5, E 0.275 V) to (pH 2, E 0.675 V) — a striking depression from the aquo Fe³⁺/Fe²⁺ couple at +0.77 V, showing how strongly citrate stabilizes the Fe(III) oxidation state.
- **pH > ~4.5, oxidized (the largest Fe field, measure 8.05):** **goethite α-FeO(OH)(s)** dominates. Fe(III) precipitates as goethite despite the citrate, because the Fe(III)-citrate binding, though strong, cannot hold 1 mM Fe(III) in solution against goethite at near-neutral to alkaline pH. This is the classic behavior of Fe(III)–citrate at moderate ligand excess: full solubility only in acidic, oxidized conditions.

**How Fe and Cu "partition"**
- Chloride is essentially a Cu-only actor here; Fe does not form any chloride complex strong enough to compete with citrate or with goethite.
- Citrate is used by both metals, but with different fates: Cu(II) stays dissolved as a hydroxo-citrate dimer throughout the oxidized neutral-alkaline region, whereas Fe(III) is only kept dissolved as the citrate dimer in an acidic oxidized wedge, precipitating as goethite above pH ~4.5.
- With 5 mM citrate against 2 mM total metal, both metals have ample ligand — the observed differences reflect thermodynamics (goethite stability, Cu(I)–Cl affinity), not stoichiometric competition.

## Evidence
- Cu regions (from the Cu verdict): DmsReg_3 {[Cu(Cl)₂]⁻} low-pH oxidized field; DmsReg_6 {Cu²⁺} wedge with corners (pH 2, 0.375 V), (3.3, 0.375 V), (3.3, 1.2 V); DmsReg_4 {[Cu₂(Citr)₂(OH)₂]⁴⁻} largest region, measure 6.71; DmsReg_1 {Cu(s)} reduced field below E ≈ 0.075 V; DmsReg_2 {[(Cu₂O)₀.₅](s), cuprite} alkaline reduced wedge.
- Fe regions (from the Fe verdict): DmsReg_2 {Fe²⁺} bounded by pH 4.5 vertical from E = −0.5 V to 0.275 V; DmsReg_3 {[Fe(Citr)]⁻} reduced pH 4.5–7.8; DmsReg_5 {[Fe₂(Citr)₂(OH)₂]²⁻} acidic oxidized; DmsReg_1 {α-FeO(OH)(s), goethite} largest field, measure 8.05.
- Cu(I)-chloride log β from the card: +3.10 ([CuCl]), +6.06 ([Cu(Cl)₂]⁻), +5.39 ([Cu(Cl)₃]²⁻); Cu(II)-chloride: log β = +0.20 for [CuCl]⁺.
- Cu(II)-citrate log β: +11.20 for [Cu₂(Citr)₂(OH)]³⁻, +6.34 for [Cu₂(Citr)₂(OH)₂]⁴⁻, +9.26 for [Cu(Citr)H], +14.50 for [Cu₂(Citr)₂]²⁻.
- Cu hydroxides/solids (present but non-dominant): CuO(s) log β = −7.65, Cu(OH)₂(s) = −8.68, cuprite formation log β = +0.70 (Cu⁺ + H⁻ → 0.5 Cu₂O).
- Fe(II)-citrate log β: +4.40 for [Fe(Citr)]⁻, +11.10 for [Fe(Citr)H₂]⁺, +8.55 for [Fe(Citr)H], −5.40 for the Fe(II) dimer.
- Fe(III)-citrate log β: +21.20 for [Fe₂(Citr)₂(OH)₂]²⁻, +11.19 for [Fe(Citr)], +12.35 for [Fe(Citr)H]⁺, +8.49 for [Fe(Citr)(OH)]⁻.
- Citrate stepwise pKₐ: 2.90, 4.35, 5.65 (fully deprotonated L³⁻ fraction > 50% only above pH ~5.7).
- Reference aquo couple E° for Fe³⁺/Fe²⁺ = +0.77 V; the citrate-shifted Fe boundary in this pot lies at E = 0.275–0.675 V across pH 4.5–2.
- Grid statistics: 1435 coarse cells, dpH = 0.2, dE = 0.05 V, 0 excluded, 0 refined-only, no disconnected labels, no parser failures.

## Final deliverables

- [Result 01](final/result_01/answer.md): Build a joint E-pH (Pourbaix) speciation picture for a single pot containing Fe(III), Cu(II), citrate, and chloride, and show how Fe and Cu partition between citrate and chloride complexation across pH 2-10.
