---
export: Opus4_7
model: claude-opus-4-7
effort: max
run: effort-max_run1
prompt: "L1_5 EDTA versus NTA copper speciation comparison"
conversation: https://claude.ai/chat/86403a89-781c-45e1-b7b9-8b95377edf0b
started: 2026-09-17T09:10:04.822077+00:00
finished: 2026-09-17T09:17:28.328105+00:00
stop_reason: end_turn
---
![pCu vs pH: 1 mM Cu(II) with 5 mM ligand (25°C, I = 0.1 M)](chart_1_pCu%20vs%20pH_%201%20mM%20Cu%28II%29%20with%205%20mM%20ligand%20%2825°C,%20I%20=%200.1%20M%29.png)

The calculation uses log K values from Martell & Smith / NIST 46 at 25°C, I = 0.1 M. For EDTA (H₄Y): protonation log K = 10.19, 6.13, 2.69, 2.00; log K(CuY²⁻) = 18.78, with CuHY⁻ (log K = 3.0) and Cu(OH)Y³⁻ (log K = 2.5). For NTA (H₃T): protonation log K = 9.65, 2.52, 1.81; log K(CuT⁻) = 12.96 and log β₂(Cu(T)₂⁴⁻) = 17.40. Cu(II) hydrolysis is included as Cu(OH)ₙ⁽²⁻ⁿ⁾ (log \*β₁..₄ = -8.0, -16.2, -26.3, -39.6). The system is solved by iterating the coupled Cu and ligand mass balances.

**EDTA keeps free [Cu²⁺] lower at every pH from 3 to 10**, by roughly 2.4 log units at pH 3, widening to a maximum gap of about 5.2 log units near pH 7, then narrowing back to ~4 log units by pH 10:

| pH | pCu (EDTA) | pCu (NTA) | dominant Cu species |
|---|---|---|---|
| 3 | 9.18 | 6.80 | CuY²⁻ ; CuT⁻ |
| 5 | 13.03 | 8.91 | CuY²⁻ ; CuT⁻ |
| 7 | 16.14 | 10.98 | CuY²⁻ ; CuT⁻ (Cu(T)₂ ≈ 19%) |
| 8 | 17.18 | 12.30 | CuY²⁻ ; Cu(T)₂⁴⁻ crosses over (67%) |
| 10 | 18.99 | 15.05 | CuY²⁻ ; Cu(T)₂⁴⁻ (98%) |

Two features shape the curves. First, both plots rise nearly linearly with pH because the fully deprotonated ligand fraction α_L climbs by roughly one decade per pH unit through the middle of each ligand's protonation range — so the *conditional* stability constant K′ = K·α_L grows in step. EDTA sits ~5.8 log units higher in raw K, and that offset carries through the whole range. Second, the NTA curve actually *steepens* between pH 7 and 9 (roughly 0.5 log per 0.1 pH) because the 1:2 complex Cu(T)₂⁴⁻ begins to dominate: with 4 mM free NTA, β₂[T³⁻]² grows sharply once the amine (pKa 9.65) starts deprotonating, and the second NTA soaks up additional Cu even as the first one is already bound. That's why the NTA curve bends up and the EDTA advantage narrows at high pH — but it never inverts, and by pH 10 EDTA still binds Cu ~10⁴ tighter.

For the low-pH question, both complexes are essentially intact across pH 3-10. Even at pH 3, ~99.9998% of the Cu is chelated by EDTA and ~99.98% by NTA. Dissociation of Cu²⁺ becomes noticeable well below the requested range: I set a 1%-free threshold and got **pH ≈ 1.23 for Cu-EDTA and pH ≈ 1.85 for Cu-NTA**. The mechanism differs: for EDTA the free-Cu rise below pH 2 is driven by protonation of the carboxylates (K₂ = 10⁶·¹³, K₁ = 10¹⁰·¹⁹ dominate below pH 3), moderated by the protonated ternary CuHY⁻ that still holds Cu bound; for NTA the amine (pKa 9.65) is already protonated across the entire acid range, so the whole burden falls on the three carboxylates, and once two of them protonate below pH ~2.5 the complex collapses quickly.

A few caveats worth flagging: (i) polynuclear Cu(II) hydroxides (Cu₂(OH)₂²⁺) are negligible here because the strong chelators keep [Cu²⁺] far below the polymerization threshold; (ii) Cu(OH)₂(s) undersaturation should be checked at high pH — with EDTA the ion product is ~10⁻²⁶ ≪ Ksp, and even with NTA at pH 10 the product is ~10⁻²³ (still undersaturated for fresh Cu(OH)₂, Ksp ≈ 10⁻¹⁹·⁷); (iii) reported I = 0.1 M constants already carry the activity correction, so no further Davies correction is applied; (iv) if the medium contained CO₂ or Cl⁻ at meaningful levels, competing Cu-carbonate or chloro-complexes would raise free Cu somewhat above these values, more so for NTA than EDTA.
