---
export: Opus4_7
model: claude-opus-4-7
effort: max
run: effort-max_run1
prompt: "L1_2 Fe(III) and Cu(II) speciation with citrate and chloride"
conversation: https://claude.ai/chat/6dcde149-5113-4b76-b86e-b610aa83578c
started: 2026-09-17T08:53:38.744788+00:00
finished: 2026-09-17T09:10:59.087631+00:00
stop_reason: end_turn
---
[Fe/Cu/citrate/chloride E–pH speciation](speciation_report.html)

The full report is published above. Here's the shortest possible tour of what it shows and why:

**The setup.** 1 mM Fe(III), 1 mM Cu(II), 5 mM citrate, 0.1 M Cl⁻, 25 °C, I = 0.1 M, pH 2–10, E −0.4 to +1.0 V. The solver enforces the two mass balances plus Nernst on the Fe³⁺/Fe²⁺ (E° = +0.771 V) and Cu²⁺/Cu⁺ (E° = +0.153 V) couples on a 81 × 71 grid; ferrihydrite, Cu(OH)₂(s), CuCl(s), and Cu(s) are tested for saturation and cap the free-ion activity when they form.

**How the competition actually plays out** (oxic, E = +0.60 V):

| pH | Fe verdict | Cu verdict |
|---|---|---|
| 2–3 | FeHCit⁺ (100 %) — log K = 12.3 with HCit²⁻ crushes FeCl_n | Cu²⁺ + CuCl⁺ (~99 %); citrate too protonated |
| 4–5 | FeHCit⁺ still (~99 %) | CuCit⁻ takes over (~88 %) |
| 6–7 | **Ferrihydrite** — Fe abandons citrate | CuCit⁻ / CuCit₂⁴⁻ (~50/50) |
| 8+ | ferrihydrite | **Cu(OH)₂(s)** — Cu drops out too |

The two metals **never actually fight over citrate**: 5 mM citrate is plenty for 2 mM total metal at 1:1, and the geometry of the Pourbaix diagram means that whenever one metal is bound to citrate, the other is either still there with room to spare (pH 4–5), already lost to a solid (Fe above pH 5.5), or freed by protonation (Cu below pH 4). Peak simultaneous citrate binding is at pH 5, where Fe holds ~20 % of the pool and Cu another ~20 %, leaving ~60 % free.

**Chloride's real job** is on the reduced side. It's a bit-player for Fe(III) (FeCl_n beaten by citrate by ~10 orders of magnitude) and marginal for Cu(II) (~20 % as CuCl⁺ at pH 2). But log β₂ = 5.5 for CuCl₂⁻ warps the Cu(II)/Cu(I) potential downward by ~330 mV, opening a large CuCl₂⁻ wedge between the Cu(s) line and the citrate belt (Figure 2 and Figure 4b).

**Every log K, log β, log \*K_s and E° the solver actually consumed** is in §2 of the report, with the primary source cited (Baes & Mesmer 1976 for hydrolysis, NIST 46 for chloride, Königsberger et al. 2000 and Silva et al. 2009 for Fe–citrate, Bard–Parsons–Jordan 1985 for potentials, Cornell & Schwertmann 2003 for ferrihydrite). §8 lists the biggest caveats — ferrihydrite solubility uncertainty, polynuclear Fe(III)–citrate species I omitted, and what happens if CO₂ is admitted — so you can see exactly which assumptions to relax if your system differs.
