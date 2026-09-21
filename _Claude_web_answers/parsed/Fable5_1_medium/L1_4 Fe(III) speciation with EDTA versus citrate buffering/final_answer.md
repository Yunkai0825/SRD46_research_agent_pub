---
export: Fable5_1
model: claude-fable-5-1
effort: medium
run: effort-medium_run1
prompt: "L1_4 Fe(III) speciation with EDTA versus citrate buffering"
conversation: https://claude.ai/chat/ed24a83c-f635-4515-ba06-d760c13f59a3
started: 2026-09-17T06:46:22.685264+00:00
finished: 2026-09-17T06:47:34.265299+00:00
stop_reason: end_turn
---
**Short answer:** EDTA, by a wide margin. With 5 mM EDTA, 1 mM Fe(III) stays in solution across the entire pH 4–9 window (and to ~pH 10–11); with 5 mM citrate, thermodynamics says ferrihydrite reappears around pH 7–8, well inside the window. Both hold Fe easily at the acid end.

**Why the ligands behave differently**

The "buffer" against precipitation is the free Fe³⁺ activity the complex maintains versus the ceiling set by Fe(OH)₃(s): log[Fe³⁺]ₘₐₓ ≈ log *Ks0 − 3 pH (≈ 3.2 − 3pH for ferrihydrite; ~1.5 units higher for fresh amorphous Fe(OH)₃). That ceiling falls 3 log units per pH unit, so the question is how fast each complex's Fe³⁺ buffering falls with pH.

- **EDTA** (log K FeY⁻ ≈ 25.1; FeY⁻ → Fe(OH)Y²⁻ pKa ≈ 7.5, → Fe(OH)₂Y³⁻ pKa ≈ 9.4). Two things work in its favor: the very large K, and the fact that free Y⁴⁻ keeps rising ~10×/pH unit up to pKa₄ ≈ 10.2, which partly offsets the OH⁻ competition. Net: the buffered log[Fe³⁺] drops only ~1.5–2 units per pH unit between pH 7 and 9.
- **Citrate** (log β FeCit ≈ 11.4; FeCit hydrolyzes at pKa ≈ 2.7 and again ≈ 6.4). K is 14 orders of magnitude weaker, and free Cit³⁻ stops increasing above pH ~6 (pKa₃ ≈ 5.7), so there is nothing to offset the pH³ pull of hydroxide. The Fe(OH)ₓ–citrate ternary species are what keep it in solution at all in the neutral region.

**Approximate saturation index (SI = log[Fe³⁺]ₐcₜᵤₐₗ − log[Fe³⁺]ₘₐₓ, ferrihydrite; negative = soluble)**

| pH | EDTA | Citrate |
|---|---|---|
| 4 | ≈ −8 | ≈ −2.3 |
| 6 | ≈ −6 | ≈ −0.5 |
| 7 | ≈ −4.5 | ≈ +0.9 |
| 8 | ≈ −3.5 | ≈ +2 |
| 9 | ≈ −2 | ≈ +3 |

Dominant species along the way: EDTA is FeY⁻ (with a little FeHY at pH 4) until ~pH 7.5, then Fe(OH)Y²⁻, with Fe(OH)₂Y³⁻ taking over above ~9.4. Citrate is Fe(OH)Cit⁻ from ~pH 3 to 6.5, then Fe(OH)₂Cit²⁻ (plus some Fe(Cit)₂³⁻ and polynuclear Fe₃-citrate species with the 5-fold excess).

**Where Fe(OH)₃(s) reappears**

- **EDTA:** not within pH 4–9. Extrapolating, SI crosses zero near pH 10–10.5 for ferrihydrite, closer to 11 for fresh amorphous Fe(OH)₃, and the crossover moves down if Ca²⁺/Mg²⁺ are present to compete for EDTA.
- **Citrate:** onset ≈ pH 7 for ferrihydrite, ≈ pH 8–8.5 if you use the more soluble freshly precipitated phase. In practice 1:5 Fe:citrate solutions often look clear to pH ~9 because precipitation is slow and the Fe forms citrate-stabilized colloidal ferrihydrite and Fe₃-citrate clusters rather than a visible solid, but thermodynamically the solid is favored from about pH 7–8 upward, and it ages toward goethite (lower solubility), which pushes the onset lower still.

The numbers above carry roughly ±0.5 pH unit uncertainty from the choice of hydrolysis constants and *Ks0, but the ranking and the roughly 3-pH-unit advantage of EDTA are robust. If you want, I can run a full mass-balance speciation model (e.g., PHREEQC-style in Python) with a specific constant set to produce the exact distribution curves.
