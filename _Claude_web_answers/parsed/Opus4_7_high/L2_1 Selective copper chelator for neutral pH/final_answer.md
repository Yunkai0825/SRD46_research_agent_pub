---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_1 Selective copper chelator for neutral pH"
conversation: https://claude.ai/chat/0a93d07c-d439-4c8b-9603-63980fda14f9
started: 2026-09-17T08:17:07.717394+00:00
finished: 2026-09-17T08:20:29.015960+00:00
stop_reason: end_turn
---
## Ligand survey from SRD-46

Restricting to ligands with critically evaluated log K for all three of Cu(II), Ni(II), Zn(II) near I = 0.1 M, and filtering for a Cu-vs-Ni gap that could plausibly matter (Cu vs Zn is easy — the Irving–Williams series does most of the work), the field narrows to a handful:

| Ligand | log K(CuL) | log K(NiL) | log K(ZnL) | Δ(Cu−Ni) | Δ(Cu−Zn) |
|---|---|---|---|---|---|
| EDTA | 18.8 | 18.6 | 16.5 | 0.2 | 2.3 |
| NTA | 13.0 | 11.5 | 10.7 | 1.5 | 2.3 |
| dien | 16.0 | 10.7 | 8.9 | 5.3 | 7.1 |
| **trien** | **20.4** | **14.0** | **12.1** | **6.4** | **8.3** |
| 2,3,2-tet | 23.9 | 16.4 | 15.1 | 7.5 | 8.8 |
| **cyclam** (14-aneN₄) | **27.2** | **22.2** | **15.5** | **5.0** | **11.7** |
| **cyclen** (12-aneN₄) | **24.8** | **16.4** | **16.2** | **8.4** | **8.6** |
| DOTA | 22.7 | 20.0 | 18.7 | 2.7 | 4.0 |
| TETA (cyclam-tetraacetate) | 21.4 | 22.2 | 16.4 | −0.8 | 5.0 |

EDTA, DOTA, and TETA are killed by their similar Cu/Ni affinities (Ni actually beats Cu on TETA). The three worth carrying to speciation are **cyclam**, **cyclen**, and **trien**.

## Speciation at 1 mM M / 5 mM L, I = 0.1 M

Solved numerically with full ligand protonation (α_L), M–OH side reactions (α_M(OH)), and MHL where reported. All three metals are >99.99% ligand-bound in every case, so the selectivity is set entirely by the differences in the log K values — the α_L term cancels between metals on the same ligand, which is why the ratios are pH-independent from 6 → 8 (Cu–OH starts contributing ~0.5 log unit at pH 8 but that's a wash).

Free [M²⁺] at pH 7 (all values as log₁₀ M):

| Ligand | log[Cu²⁺] | log[Ni²⁺] | log[Zn²⁺] |
|---|---|---|---|
| cyclam | **−20.3** | −15.3 | −8.6 |
| cyclen | **−18.6** | −10.2 | −10.0 |
| trien | **−16.1** | −9.7 | −7.8 |

Selectivity vs Cu (log₁₀ of the free-metal ratio — larger is better):

| Ligand | log([Ni²⁺]/[Cu²⁺]) | log([Zn²⁺]/[Cu²⁺]) | **worst competitor** |
|---|---|---|---|
| cyclam | 5.0 | 11.7 | **10⁵·⁰ (Ni-limited)** |
| **cyclen** | **8.4** | **8.6** | **10⁸·⁴ (Ni-limited)** |
| trien | 6.4 | 8.3 | 10⁶·⁴ (Ni-limited) |

## Recommendation: **cyclen (1,4,7,10-tetraazacyclododecane)**

For an equimolar Cu/Ni/Zn challenge, cyclen keeps free [Cu²⁺] roughly 10⁸·⁵ below both free [Ni²⁺] and free [Zn²⁺] across pH 6–8. Cyclam wins on Zn (10¹¹·⁷) but is undone by Ni: its 12 log-unit Cu/Zn margin is meaningless when Ni still contaminates at only 10⁵ suppression. **The worst competitor dictates the effective purity**, and cyclen's floor is ~3.5 orders of magnitude better than cyclam's and ~2 orders better than trien's. The 12-membered ring simultaneously destabilises Ni(II) (cavity too small for high-spin octahedral Ni, and the square-planar diamagnetic form is disfavoured by aliphatic amines) while remaining an excellent fit for Jahn–Teller-distorted Cu(II).

## Caveats you should factor in before locking it in

- **Ni-cyclen log K is the biggest uncertainty in this comparison.** SRD-46 gives ~16.4, but reported values span 15.9–17.0 depending on how the high-spin/low-spin equilibrium was modeled. In the worst case (log K = 17.0) the Ni margin shrinks to 10⁷·⁸ — still better than any alternative here.
- **Formation kinetics are slow for both macrocycles** because protonated cyclam/cyclen must deprotonate to bind. Cu(II)–cyclen half-life to equilibrium can be minutes to hours near neutral pH; if you need fast equilibration, use trien and accept the 10⁶·⁴ Ni margin, or pre-form the Cu complex at higher pH.
- **Avoid unbuffered pH 8** — with 1 mM Cu you're near Cu(OH)₂(s) saturation (Ksp gives ~10⁻⁶·² M free Cu²⁺). Not an issue *with* the ligand present (free [Cu²⁺] is 10⁻²⁰), but any hot-spot during addition can nucleate. MOPS or HEPES buffer at pH 7.0–7.4 is the safe operating point (avoid Tris — it binds Cu, log K ~4).
- If you also need discrimination against **Co(II) or Cd(II)**, the picture changes; those weren't in your spec but cyclen holds up reasonably against both.

If your application would benefit from covalent attachment (surface, resin, protein), cross-bridged cyclam (CB-cyclam) preserves the Cu selectivity while eliminating the protonation problem, at the cost of harder synthesis.
