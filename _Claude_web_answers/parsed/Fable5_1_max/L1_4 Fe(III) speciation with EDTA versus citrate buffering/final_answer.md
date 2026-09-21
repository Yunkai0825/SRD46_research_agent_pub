---
export: Fable5_1
model: claude-fable-5-1
effort: max
run: effort-max_run1
prompt: "L1_4 Fe(III) speciation with EDTA versus citrate buffering"
conversation: https://claude.ai/chat/7012f212-cd2d-444f-bd97-b31e1faef6ee
started: 2026-09-17T06:51:08.232336+00:00
finished: 2026-09-17T07:04:27.143822+00:00
stop_reason: end_turn
---
![Ligand-buffered pFe vs Fe(OH)3 solubility (1 mM Fe, 5 mM L, 25 °C, I = 0.1)](chart_1_Ligand-buffered%20pFe%20vs%20Fe%28OH%293%20solubility%20%281%20mM%20Fe,%205%20mM%20L,%2025%20°C,%20I%20=.png)

**Buffering.** EDTA pins pFe from 17.4 (pH 4) to 26.2 (pH 9), rising ~1.8 units per pH unit (EDTA deprotonation plus FeY⁻ → Fe(OH)Y²⁻ hydrolysis). Citrate starts far weaker (pFe 13.4 at pH 4) but climbs ~3.7 units per pH unit up to pH 5.5, because Cit³⁻ is still being deprotonated *and* the coordinated alcohol group ionizes; above pH 6 both alkoxides are off and the slope settles at 2. The Fe(OH)₃ solubility line has slope 3, so it eventually overtakes both ligands — the crossing pH is where the solid "reappears."

**Dominant species** (H₋₁Cit = citrate with the alkoxide deprotonated):

| pH | EDTA | Citrate |
|---|---|---|
| 4–5 | FeY⁻ ≥ 99.7% | Fe(Cit)(H₋₁Cit)⁴⁻ 76–83%, Fe(Cit)₂³⁻ 22% → 2% |
| 6 | FeY⁻ 97%, Fe(OH)Y²⁻ 3% | Fe(H₋₁Cit)₂⁵⁻ 64%, Fe(Cit)(H₋₁Cit)⁴⁻ 36% |
| 7 | FeY⁻ 75%, Fe(OH)Y²⁻ 24% | Fe(H₋₁Cit)₂⁵⁻ 95% |
| 8 | Fe(OH)Y²⁻ 71%, FeY⁻ 22%, (FeY)₂O⁴⁻ 4%, Fe(OH)₂Y³⁻ 3% | Fe(H₋₁Cit)₂⁵⁻ 99% |
| 9 | Fe(OH)Y²⁻ 67%, Fe(OH)₂Y³⁻ 27%, (FeY)₂O⁴⁻ 4% | Fe(H₋₁Cit)₂⁵⁻ ~100% |

**Where Fe(OH)₃(s) reappears** (first pH with SI > 0, extrapolating the model above pH 9):

| Solid (log *Ksp at I = 0) | EDTA | Citrate, bis-alkoxide model | Citrate, 1:1-only model |
|---|---|---|---|
| Fresh Fe(OH)₃(am), 4.89 | never ≤ 9 (SI −4.7 at pH 9; not even by pH 14) | never ≤ 9 (SI −4.5 at pH 9) | ≈ pH 9.3 |
| Aged ferrihydrite, 3.2 | ≈ pH 12.7 | ≈ pH 11.9 | ≈ pH 7.6 |
| Goethite, −1.0 | ≈ pH 7.9 | ≈ pH 7.6 | supersaturated already at pH 4 |

So EDTA keeps Fe(III) soluble over the widest range in every column, and it has the larger safety margin at all pH ≤ 7. In the window you asked about, the honest thermodynamic answer for a *fresh* amorphous hydroxide is "no precipitate in either system"; what actually reappears at pH 8–9 in aged Fe–citrate solutions is the more crystalline, less soluble oxide that both systems are supersaturated against above ~pH 7.6–7.9 — citrate simply gets there ~0.3 pH units earlier, and its complexes are far more labile, so it nucleates first.

**Why two citrate models.** The older 1:1-only constants (the set most speciation databases carry) come from work like Field et al., who measured Fe(III)–citrate in 0.1 M KNO₃ and found only 1:1 stoichiometry; those studies were mostly done in acidic solution to avoid Fe(III) hydroxide precipitation and treated citric acid as a triprotic acid. Crystallography shows the citrate alcohol is deprotonated on coordination, and mass spectrometry/EPR identify a mono-iron dicitrate species plus di- and trinuclear oligomers as the relevant complexes, with the dicitrate species dominating at physiological pH and citrate excess. My primary citrate set uses the constants from the voltammetric/spectrophotometric revision — FeLH log β 25.69, FeL₂H₂³⁻ 48.06, FeL₂H⁴⁻ 44.60, FeL₂⁵⁻ 38.85 (L = Cit⁴⁻) — converted to a Cit³⁻ basis with the alcohol pKa of 14.4. That bis-alkoxide complex is why citrate catches up with EDTA above pH 7.

**Other assumptions:** NIST constants at I = 0.1 (FeY⁻ log K 25.1, FeHY 1.4, Fe(OH)Y²⁻ pKa 7.49, Fe(OH)₂Y³⁻ pKa ≈ 9.4, dimer log K 1.6); Fe hydrolysis and *Ksp values moved from I = 0 to 0.1 with Davies, so pH here is −log[H⁺] (NBS pH ≈ 0.1 lower). Polynuclear Fe–citrate species were left out for lack of I = 0.1 constants; including them would only lower free Fe³⁺ further, so the citrate results are conservative. No competing Ca²⁺/Mg²⁺ or phosphate was included — in a real medium those would degrade EDTA's performance above pH ~6.5 much more than anything in this calculation.
