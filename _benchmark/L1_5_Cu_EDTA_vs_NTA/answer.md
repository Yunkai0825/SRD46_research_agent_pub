## Answer

Under identical conditions (1 mM Cu(II), 5 mM ligand, 25 °C, I = 0.1 M), **EDTA suppresses free Cu²⁺ far more aggressively than NTA does across the entire pH 3–10 window**, and neither complex undergoes any real dissociation inside this range — but the two systems have qualitatively different structures.

**Cu–EDTA** is a one-species story. The SRD-46 card puts essentially 100 % of the copper into the ternary hydroxo-chelate **[Cu(EDTA)(OH)]³⁻** from pH 3 all the way to pH 10, with no crossovers on the Cu axis. Free Cu²⁺ is 21 orders of magnitude below the chelated pool even at the acidic edge (~1.7 × 10⁻²⁴ M at pH 3, and lower as pH rises). No dissociation is seen anywhere in pH 3–10 — onset of free Cu²⁺ lies well below pH 3. This is driven by an unusually large log β(+30.18) that the LC2 card assigns to the mixed hydroxo-EDTA complex, which beats the plain [Cu(EDTA)]²⁻ chelate (log β = 18.78) by more than 11 log units and dwarfs any competing hydrolysis or protonated-EDTA species. The hexadentate EDTA cavity plus a coordinated hydroxide simply out-binds everything else at every pH.

**Cu–NTA** is a two-chelate story with a clean handoff. Below pH ≈ 5.93 the 1:1 chelate **[Cu(NTA)]⁻** dominates (peak ~99 % near pH 3.6), and above that crossover the 1:2 chelate **[Cu(NTA)₂]⁴⁻** takes over (peak ~99 % near pH 8.8). The transition is set by NTA protonation: below pH ~5, NTA is largely held as HNTA²⁻ (79 % of ligand at pH 4.3), so only one NTA fits per Cu; as pH rises, free NTA³⁻ becomes available and the second chelate ring closes. Free Cu²⁺ reaches its highest fraction at the acidic end — **0.069 % of total Cu (~7 × 10⁻⁷ M) at pH 3** — falling by roughly ×3 per 0.1 pH unit, dropping below 10⁻⁶ fraction by pH 6 and negligible above. NTA never lets free Cu²⁺ exceed 1 % anywhere in 3–10, and true dissociation to appreciable free Cu²⁺ would require pH well below 3 (successive NTA pKa 2.52).

**Which ligand keeps [Cu²⁺] lower?** EDTA wins by an enormous margin: at pH 3, EDTA gives [Cu²⁺] ≈ 10⁻²⁴ M vs NTA's ~10⁻⁶ M — roughly **18 orders of magnitude tighter** control. This reflects both EDTA's higher denticity (hexadentate vs tetradentate) and the extra stabilisation from the ternary hydroxo complex the SRD-46 card credits it with. NTA is still a very effective masking agent (no Cu hydroxide precipitation, no free Cu²⁺ above 10⁻⁶ M anywhere above pH 4), but it is chemically outmatched by EDTA.

**Where does each complex begin to dissociate at low pH?** Neither dissociates within pH 3–10:
- **Cu–EDTA:** no measurable dissociation anywhere in the window; onset would be below pH 3.
- **Cu–NTA:** first detectable free Cu²⁺ (~0.07 %) at pH 3.0, but genuine breakdown requires pH < 3 (where H₂NTA⁻ and H₃NTA form).

In neither system does Cu(OH)₂(s), CuO(s), or Cu₂O(s) precipitate — both chelators fully mask copper against hydroxide across the biologically relevant range.

## Evidence
- **Cu–EDTA (call 1):** "[Cu(EDTA)(OH)]³⁻ carries essentially 100 % of the Cu at every sampled pH (fraction = 1.000000 to six decimals from pH 3.0 through pH 9.0+)". Free Cu²⁺ fractions: pH 3.0 → 1.68 × 10⁻²¹; pH 5.0 → 1.90 × 10⁻²⁷; pH 7.0 → 4.35 × 10⁻³²; pH 9.0 → 6.12 × 10⁻³⁶. Ratio [Cu-EDTA]:[Cu²⁺] ≥ 10²¹ everywhere.
- **Cu–EDTA constants:** log β([Cu(EDTA)]²⁻) = +18.78; log β([Cu(EDTA)(OH)]³⁻) = +30.18.
- **Cu–NTA (call 2):** "[Cu(NTA)]⁻ dominates from pH 3.0 to ≈5.93 (peak 98.9 % near pH 3.6), and [Cu(NTA)₂]⁴⁻ dominates from ≈5.93 to 10.0 (peak 99.4 % near pH 8.8)". Free Cu²⁺ fractions: pH 3.0 → 6.90 × 10⁻⁴; pH 4.0 → 6.30 × 10⁻⁵; pH 5.0 → 5.75 × 10⁻⁶; <10⁻⁹ by pH 7.
- **Cu–NTA constants:** log β₁([Cu(NTA)]⁻) = 12.7; log β₂([Cu(NTA)₂]⁴⁻) = 17.4.
- **No solid precipitation** in either system across pH 3–10 (all solid columns identically 0 in both `frac_metal.csv` files).
- **Convergence:** 71/71 samples converged in both runs; all evidence is fully sampled.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute Cu(II) speciation with EDTA to see how strongly EDTA suppresses free Cu2+ across pH 3-10.
- [Result 02](final/result_02/answer.md): Compute Cu(II) speciation with NTA (nitrilotriacetate) to see how strongly NTA suppresses free Cu2+ across pH 3-10, for comparison with the Cu-EDTA case already computed.
