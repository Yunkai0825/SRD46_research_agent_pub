---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L3_5 The Irving-Williams series pre"
conversation: https://claude.ai/chat/ebf9cb8d-4aed-41e0-8e3d-37ff3a4a7ed3
started: 2026-09-17T02:01:13.869473+00:00
finished: 2026-09-17T02:02:53.993740+00:00
stop_reason: end_turn
---
## Hypothesis (falsifiable form)

**H₁ (Irving–Williams, strong form):** For any ligand L that binds through hard-N/O donors, the 1:1 M(II) complex stability constants of the first-row divalent transition metals order as Mn < Fe < Co < Ni < Cu > Zn, with **Cu(II) as the unique maximum**, and this ordering is invariant under change of donor set.

**Falsifier:** at fixed pH, ionic strength, and metal-to-ligand ratio, compute the free [M²⁺] in each system. If Cu(II) is *not* the most suppressed metal, or if some non-Cu metal has a larger log β than Cu, H₁ is falsified. If the Cu(II) peak survives one donor set but another interior element swaps rank, the strong form fails but the "Cu peak" sub-claim survives.

## Speciation model

Total mass balances at fixed pH (I=0.1 m, 25 °C) with stepwise log Kₙ from Martell–Smith/NIST:

Glycine — pKₐ = 2.35, 9.78; α(L⁻) at pH 7 = 1.66 × 10⁻³
| M(II) | log K₁ | log β₂ (log β₃) | [M²⁺] (M) | % free | log([M²⁺]/C_M) |
|---|---|---|---|---|---|
| Co | 4.64 | 8.46 | 5.7 × 10⁻⁴ | 56.8 % | −0.25 |
| Ni | 5.78 | 10.58 (13.98) | 5.7 × 10⁻⁵ | 5.70 % | −1.24 |
| **Cu** | **8.15** | **15.03** | **5.2 × 10⁻⁹** | **0.001 %** | **−5.28** |
| Zn | 4.96 | 9.20 (12.10) | 3.6 × 10⁻⁴ | 36.1 % | −0.44 |

Suppression order (most-suppressed first): **Cu ≪ Ni < Zn < Co**

Ethylenediamine — pKₐ = 7.08, 9.89; α(L) at pH 7 = 5.85 × 10⁻⁴
| M(II) | log K₁ | log β₂ (log β₃) | [M²⁺] (M) | % free | log([M²⁺]/C_M) |
|---|---|---|---|---|---|
| Co | 5.89 | 10.72 (13.82) | 1.5 × 10⁻⁴ | 15.4 % | −0.81 |
| Ni | 7.35 | 13.55 (18.10) | 9.9 × 10⁻⁷ | 0.099 % | −3.00 |
| **Cu** | **10.55** | **19.60** | **1.1 × 10⁻¹²** | **~0 %** | **−8.94** |
| Zn | 5.71 | 10.87 (12.73) | 1.8 × 10⁻⁴ | 17.8 % | −0.75 |

Suppression order (most-suppressed first): **Cu ≪ Ni < Co < Zn**

## Verdict

The **Cu(II) maximum holds for both donor sets.** In each case Cu(II) suppresses free [M²⁺] by 3–6 orders of magnitude more than the next metal (Ni), so the peak is robust — even after allowing for the fact that only ~10⁻³ of the total ligand is deprotonated at pH 7, and that Cu(II) never forms a bis- or tris-chelate as easily as Ni(II) does because of Jahn–Teller destabilisation of the apical positions.

The **strict full ordering, however, does not survive the swap.** With ethylenediamine the classical Co < Ni < Cu > Zn falls out (Zn barely below Co on the descending limb). With glycine the *interior* order inverts: Zn(II) is *more* stable than Co(II) (log β₂ = 9.20 vs 8.46), so free [Zn²⁺] < free [Co²⁺]. This is a well-known "glycinate anomaly" tied to the extra chelate stabilisation Zn(II) gets from the α-amino-carboxylate O-donor, and it is one of the standard counterexamples to the strong form of H₁.

So the narrow Cu-peak hypothesis passes this two-ligand test; the strong "ordering is fully ligand-independent" hypothesis is falsified by the Co/Zn swap between glycinate and ethylenediamine.
