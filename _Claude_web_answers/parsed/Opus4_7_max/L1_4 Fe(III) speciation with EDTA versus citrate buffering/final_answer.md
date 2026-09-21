---
export: Opus4_7
model: claude-opus-4-7
effort: max
run: effort-max_run1
prompt: "L1_4 Fe(III) speciation with EDTA versus citrate buffering"
conversation: https://claude.ai/chat/4277a296-991d-4b85-b26a-38731db36cb3
started: 2026-09-17T08:54:52.893381+00:00
finished: 2026-09-17T09:06:50.933451+00:00
stop_reason: end_turn
---
![Fe(III) soluble fraction vs pH (1 mM Fe, 5 mM ligand, I=0.1, 25 °C)](chart_1_Fe%28III%29%20soluble%20fraction%20vs%20pH%20%281%20mM%20Fe,%205%20mM%20ligand,%20I=0.1,%2025%20°C%29.png)

**EDTA wins decisively.** With a 5-fold ligand excess, EDTA keeps essentially 100% of the Fe(III) in solution across the whole pH 4–9 window (and in fact well beyond, out past pH 12). Citrate holds Fe(III) fully in solution up to about pH 6.9 and then loses it very abruptly: the model shows ~50% precipitated at pH 7.0, ~99% by pH 7.2, and effectively complete precipitation of Fe(OH)₃(am) by pH 7.5.

The reason is a mismatch between how each ligand competes with hydroxide. EDTA forms a hexadentate FeY⁻ complex with log K ≈ 25.1, and — crucially — it deprotonates a coordinated water to give FeOHY²⁻ (log K ≈ 6.45 from FeY⁻ + OH⁻) rather than releasing Fe³⁺. So the dominant species smoothly shifts from FeY⁻ below pH ~7.5 to FeOHY²⁻ above it, and both stay soluble. Citrate is only tridentate, and its mononuclear FeCit (log K ≈ 11.85) plus the mixed hydroxo forms FeOHCit⁻ and Fe(OH)₂Cit²⁻ are not strong enough to hold Fe against hydrolysis near neutrality. The trinuclear Fe₃(OH)(Cit)₃⁴⁻ cluster (log β ≈ 49) does most of the heavy lifting in the pH 5–7 window, but because it needs three Fe³⁺, its concentration collapses once free Fe³⁺ is pinned to ~10⁻¹⁷·⁵ M by the Fe(OH)₃(s) solubility limit at pH 7 — hence the cliff.

One caveat on the sharpness: real systems soften that transition somewhat. Fresh Fe(OH)₃ is often kinetically slow to nucleate on the minutes-to-hours scale, and additional polynuclear Fe–citrate species (dimers, larger oligomers, and colloidal ferric citrate) that aren't in this minimal model can push the apparent solubility edge up by roughly half a pH unit in freshly prepared solutions. The qualitative conclusion is unchanged: for buffering Fe(III) solubility across the biologically relevant neutral-to-alkaline range, EDTA is the right choice; citrate is only useful up to about pH 7.
