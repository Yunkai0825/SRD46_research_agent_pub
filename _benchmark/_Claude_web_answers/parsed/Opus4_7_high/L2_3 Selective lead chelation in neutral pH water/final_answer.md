---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_3 Selective lead chelation in neutral pH water"
conversation: https://claude.ai/chat/45fdccc1-fd53-4be6-9f27-aecd02464d00
started: 2026-09-17T08:21:48.320798+00:00
finished: 2026-09-17T08:27:19.464970+00:00
stop_reason: end_turn
---
## Recommendation: **meso-2,3-dimercaptosuccinate (DMSA)**

### 1. SRD‑46 ligand survey (log K, I = 0.1 M, 25 °C)

Ligands with critically evaluated data for all three metals in SRD‑46:

| Ligand | log K(PbL) | log K(ZnL) | log K(CaL) | Donor set | Notes |
|---|---|---|---|---|---|
| EDTA  | 18.04 | 16.44 | 10.61 | N₂O₄ | Clinical Pb chelator (CaNa₂EDTA), depletes Zn |
| DTPA  | 18.87 | 18.29 | 10.75 | N₃O₅ | Higher-K analog; poor Pb/Zn selectivity |
| CDTA  | 19.68 | 19.35 | 12.50 | N₂O₄ | Highest K, worst Pb/Zn (Δ ≈ 0.3) |
| EGTA  | 14.71 | 12.60 | 10.86 | N₂O₄(ether) | Ca-selective — wrong direction here |
| **DMSA** | **17.44 (+8.4 for HL, +6.3 for L₂)** | **6.28** | **~4.0** | S₂O₂ (2 SH, 2 COO⁻) | Approved oral Pb chelator (succimer) |

The pattern is set by donor hardness. Aminopolycarboxylates (EDTA, DTPA, CDTA) present hard N/O donors that bind Pb²⁺ and Ca²⁺ within a few log units of each other; you cannot escape Ca coprecipitation. DMSA’s two soft thiolates give it ≈10¹³× higher affinity for the borderline‑soft Pb²⁺ (6s² lone pair, thiophilic) than for the hard Ca²⁺ – exactly the split needed.

### 2. Speciation at pH 6–8, 1 mM M(II) / 5 mM L, I = 0.1 M

Mass balance solved with all protonation, MHₖLⱼ, and hydrolysis species included (see figure).

**pM values ( −log₁₀[M²⁺]_free )**

| Ligand | pH | pM(Pb) | pM(Zn) | pM(Ca) | [Pb]/[Zn] | [Pb]/[Ca] |
|---|---|---|---|---|---|---|
| **DMSA** | 6.0 | 10.74 | 3.02 | 3.00 | 1.9 × 10⁻⁸ | 1.8 × 10⁻⁸ |
| **DMSA** | 7.0 | 11.76 | 3.08 | 3.00 | **2.1 × 10⁻⁹** | **1.7 × 10⁻⁹** |
| **DMSA** | 8.0 | 12.88 | 3.46 | 3.00 | 3.8 × 10⁻¹⁰ | 1.3 × 10⁻¹⁰ |
| EDTA | 7.0 | 15.40 | 13.80 | 7.97 | 2.5 × 10⁻² | 3.7 × 10⁻⁸ |
| DTPA | 7.0 | 14.29 | 13.72 | 6.20 | 2.7 × 10⁻¹ | 8.2 × 10⁻⁹ |

**Fraction of each metal left as free M²⁺ at pH 7 (essential‑metal sparing):**

| Ligand | Pb free | Zn free | Ca free |
|---|---|---|---|
| **DMSA** | 1.7 × 10⁻⁷ % | **82 %** | **~100 %** |
| EDTA | 4 × 10⁻¹¹ % | 1.6 × 10⁻⁹ % (fully stripped) | 1.1 × 10⁻³ % (fully stripped) |
| DTPA | 5 × 10⁻¹⁰ % | 1.9 × 10⁻⁹ % (fully stripped) | 0.06 % (largely stripped) |

Dominant Pb–DMSA species at pH 7 is **Pb(HL)⁻** (96 %), consistent with one thiolate remaining protonated while the second SH plus both carboxylates coordinate; Pb²⁺’s ability to lower the SH pKₐ on binding is what drives this. Zn cannot achieve the same deprotonation at neutral pH, so it never gets past a weakly-bound MHL / MH₂L (< 20 % total), and Ca simply doesn’t bind the thiols at all.

### 3. Justification via free‑[M²⁺] ratios

The relevant figure of merit is **[Pb²⁺]_free / [Zn²⁺]_free** and **[Pb²⁺]_free / [Ca²⁺]_free** at the same 1 mM/5 mM loading — small numbers mean Pb is preferentially sequestered while the essential metals remain in the free pool.

- DMSA at pH 7 delivers [Pb]/[Zn] ≈ 2 × 10⁻⁹ and [Pb]/[Ca] ≈ 2 × 10⁻⁹, i.e. **~7 orders of magnitude better Pb/Zn selectivity than EDTA** (2.5 × 10⁻²) and **~8 orders better than DTPA** (0.27).
- EDTA and DTPA drive Pb²⁺ to sub-femtomolar levels, but they also strip essentially all Zn²⁺ and, in the DTPA case, most of the Ca²⁺ — the origin of the well-known hypocalcemia/hypozincemia toxicity of aminopolycarboxylate decorporation.
- CDTA is even worse on selectivity; EGTA goes the wrong way (Ca-selective).
- Selectivity improves with pH for DMSA (thiols more deprotonated) — a favorable feature since blood is at pH 7.4.

**Recommendation:** DMSA is the correct choice. It uniquely combines strong Pb²⁺ sequestration (pM ≈ 11.8 at pH 7) with near-complete sparing of Zn²⁺ (82 % free) and Ca²⁺ (~100 % free) — a selectivity pattern impossible to reach with hard-donor aminopolycarboxylates. This is precisely why succimer (racemic meso-DMSA) is the approved oral chelator for pediatric Pb poisoning, and why DMPS (the sulfonate analog, similar donor set) is the European alternative.

Caveats worth flagging: (i) SRD-46 log β for Pb-DMSA proton-mixed species vary ±0.5 across the primary sources — the qualitative picture is robust to that; (ii) thiol autoxidation and Cu(II)-catalyzed disulfide formation are kinetic limits not captured here; (iii) if your application is inside cells or in serum, competition with cysteine/GSH and albumin should be added to the balance.

Files: `/home/claude/work/speciation.py` (constants + solver), `/home/claude/work/pM_survey.png` (plot). Happy to extend to DMPS, penicillamine, or a mixed‐metal competition run if useful.
