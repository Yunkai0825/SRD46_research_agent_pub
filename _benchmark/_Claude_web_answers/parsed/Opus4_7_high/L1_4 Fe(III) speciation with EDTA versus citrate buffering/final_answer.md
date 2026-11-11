---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L1_4 Fe(III) speciation with EDTA versus citrate buffering"
conversation: https://claude.ai/chat/f34b237d-95c9-4362-9798-46623e28a4e8
started: 2026-09-17T07:50:05.266867+00:00
finished: 2026-09-17T07:51:10.894369+00:00
stop_reason: end_turn
---
## Fe(III)–EDTA vs Fe(III)–citrate at [Fe]ₜ = 1 mM, [L]ₜ = 5 mM, I = 0.1, 25 °C

### Key equilibria to keep in mind

Fe(III) hydrolysis is aggressive. For amorphous Fe(OH)₃(s):

$$\log[\text{Fe}^{3+}]_{\text{free}} \approx 3 - 3\,\text{pH}$$

so the "free" ferric activity that a ligand must beat drops by three orders of magnitude per pH unit. Any complexed Fe stays in solution only if the conditional stability constant K′ exceeds what's needed to hold [Fe³⁺]free below the solubility ceiling.

For a ligand L, K′ = K(FeL) · αFe · αL, where αL accounts for protonation of L and αFe for competing Fe hydrolysis.

### EDTA (log K(FeY⁻) ≈ 25.1; FeY(OH)²⁻ with log K ≈ 6.5)

αY(H) is dominated by pKa5 = 6.11 and pKa6 = 10.17:

| pH | log αY(H) | log K′(FeY⁻) after subtracting αY(H) and αFe(OH) |
|----|-----------|--------------------------------------------------|
| 4  | ~8.4      | ~15                                              |
| 6  | ~4.7      | ~19                                              |
| 8  | ~2.3      | ~18 (FeY(OH)²⁻ now dominant)                     |
| 9  | ~1.3      | ~17                                              |

With 5 mM EDTA and only 1 mM Fe, [Y⁴⁻]free is ample. Speciation across pH 4–9 is essentially all FeY⁻ up to ~pH 7, then FeY(OH)²⁻ taking over above ~pH 7.5, with a mixed FeY(OH)₂³⁻ appearing near pH 9. **No Fe(OH)₃(s) forms anywhere in 4–9.** EDTA's own precipitation window for the Fe complex begins only around pH 11–12, well outside your range.

### Citrate (log K(FeCit) ≈ 11.85; log β(Fe(Cit)₂³⁻) ≈ 18–20; dinuclear Fe₂Cit₂(OH)₂²⁻ also significant)

Citrate pKa's = 3.13, 4.76, 6.40, so αCit(H) is still ~10³ at pH 4 and only reaches ~1 above pH 7. Combined with rapidly growing αFe(OH):

| pH | Dominant Fe species                                | Comment                          |
|----|----------------------------------------------------|----------------------------------|
| 4  | FeHCit⁺, FeCit(aq)                                 | Soluble; citrate mostly HCit²⁻   |
| 5  | FeCit(aq), some Fe(Cit)₂³⁻                         | Soluble                          |
| 6  | FeCit(aq), Fe(Cit)₂³⁻, dimer Fe₂Cit₂(OH)₂²⁻       | Soluble; polynuclear grows       |
| 7  | Dimer + Fe(Cit)₂³⁻ dominant                        | Still soluble but K′ marginal    |
| 7.5–8 | Fe(OH)₃(s) begins to nucleate                   | **Precipitation onset**          |
| 9  | Mostly Fe(OH)₃(s) with residual dissolved Fe ~10⁻⁶ M | Precipitated                   |

The plain 1:1 K′ goes negative near pH 7 (11.85 − 0.1 − ~14 ≈ −2), but the 1:2 chelate and the µ-hydroxo dimer extend citrate's grip by roughly 1 pH unit. Above ~pH 7.5–8, however, even the dimer can't compete with the 10⁹-fold hydrolysis penalty. Reported experimental onsets of ferrihydrite precipitation for 5:1 citrate:Fe at ~1 mM Fe are pH ≈ 7.5–8, with visible turbidity by pH 8.

### Bottom line

**EDTA wins decisively.** It keeps Fe(III) fully soluble across the entire pH 4–9 window (and well beyond on both ends). Citrate buffers speciation adequately from pH ~3 to ~7 but loses to Fe(III) hydrolysis in the neutral-to-mildly alkaline range: **Fe(OH)₃(s) reappears at roughly pH 7.5–8** under your conditions and is the dominant Fe form by pH 9.

Two practical caveats: (1) Values shift ~0.3–0.5 log units depending on which citrate polynuclear constants and which Fe(OH)₃(s) phase (amorphous ferrihydrite vs aged goethite) you adopt; using goethite (log*Ks ≈ 0.5) pushes citrate's precipitation onset down to ~pH 7. (2) In real experiments, kinetics matter — freshly mixed Fe/citrate can stay metastably clear an hour or two above the thermodynamic limit before ferrihydrite nucleates.

If you want, I can put together a full speciation plot (e.g., via a Visual MINTEQ–style calculation) so you can see the exact %-species curves side by side.
