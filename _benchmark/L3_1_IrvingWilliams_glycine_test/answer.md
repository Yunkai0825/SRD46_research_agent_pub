## Answer

**Hypothesis (falsifiable form).** The Irving–Williams series predicts that, for a fixed divalent first-row 3d metal M(II) with the same donor ligand at the same pH, temperature, and ionic strength, complex stability rises as Mn(II) < Fe(II) < Co(II) < Ni(II) < Cu(II) and then falls at Zn(II) — so Cu(II) > Zn(II). Operationally: under identical totals (1 mM M, 10 mM glycine) at pH 7, 25 °C, I = 0.1 m, the free aquo [M²⁺] left in solution must satisfy

[Co²⁺] > [Ni²⁺] > [Cu²⁺]  and  [Zn²⁺] > [Cu²⁺]

(equivalently, the pM = −log[M²⁺]_free ordering Co < Ni < Cu > Zn). If any of these inequalities reverses in the SRD‑46 calculation the hypothesis is falsified.

**Test — computed free [M²⁺] at pH 7, 1 mM M, 10 mM glycine, 25 °C, I = 0.1 m:**

| Rank (most suppressed → least) | Metal | free [M²⁺] (M) | pM = −log[M²⁺] | % of M_T left as aquo |
|---:|:--|---:|---:|---:|
| 1 | **Cu(II)** | 2.81 × 10⁻⁹ | **8.55** | 2.8 × 10⁻⁴ % |
| 2 | Ni(II) | 4.62 × 10⁻⁵ | 4.34 | 4.6 % |
| 3 | Zn(II) | 3.37 × 10⁻⁴ | 3.47 | 33.7 % |
| 4 | Co(II) | 5.43 × 10⁻⁴ | 3.27 | 54.3 % |

Ordered by binding strength (largest pM = strongest sequestration):

**Cu(II) ≫ Ni(II) > Zn(II) > Co(II)**

**Verdict: the Irving–Williams hypothesis is confirmed.**
- The predicted rise Co < Ni < Cu is satisfied: pM climbs 3.27 → 4.34 → 8.55, i.e. Cu suppresses free metal ~10⁵× more than Ni and ~10⁵·³× more than Co.
- The predicted fall at Zn is also satisfied: [Zn²⁺] = 3.37 × 10⁻⁴ M is five orders of magnitude larger than [Cu²⁺], so Zn binds glycinate far more weakly than Cu — exactly the Cu > Zn drop that defines the series' maximum at Cu.
- The only nuance is that Zn slightly out-binds Co here (pM 3.47 vs 3.27, a factor of ~1.6 in free metal). This does not violate the canonical series, which places Zn between Co and Ni for most O/N donors and, for a mixed N,O amino-acid ligand like glycinate, typically has Zn ≈ Co with Zn marginally stronger — consistent with what the SRD‑46 constants deliver.

**Chemical interpretation.** All four metals see the same low free-glycinate pool at pH 7 (glycine's ammonium pKa is 9.57, so [Gly⁻] is only ~10⁻⁴·⁵ of the 10 mM total ligand). The differences in [M²⁺]_free therefore reflect the intrinsic Lewis-acid strength of the M²⁺ centre toward the amino-carboxylate donor:

- **Cu(II)** wins overwhelmingly because Jahn–Teller stabilisation of its d⁹ configuration and the very short Cu–N,O bonds it forms give log β₂(CuGly₂) = 15.10 — the largest bis-amino-acid formation constant of the first-row divalents. Even against the tiny [Gly⁻] pool, this is enough to drive >99 % of Cu into the neutral bis‑chelate [Cu(Gly)₂] and leave only nanomolar free Cu²⁺. This is the Irving–Williams maximum in action.
- **Ni(II)** (d⁸, high crystal-field stabilisation for its octahedral aqua/glycinate complexes, log β₂ = 10.58) is next: 95 % of Ni is complexed and free [Ni²⁺] is buffered down to ~46 µM — an order of magnitude smaller than Co/Zn but still four orders larger than Cu.
- **Zn(II)** (d¹⁰, no CFSE, log β₂ = 9.19) and **Co(II)** (high-spin d⁷, small CFSE for octahedral, log β₂ = 8.46) sit at the tail: with a 10-fold ligand excess they can only pull ~2/3 (Zn) or ~1/2 (Co) of the metal into glycinate complexes, and the free aquo ion remains the largest or second-largest species. Zn's marginally stronger binding than Co is consistent with its slightly higher effective nuclear charge and smaller ionic radius, which compensates for its lack of ligand-field stabilisation.

The chemistry the numbers tell us is unambiguous: as one moves along the 3d row with glycine, the free-metal reservoir collapses by ~10⁵ from Co to Cu and then rebounds by ~10⁵ back at Zn — the "up-then-down" trace across Co → Ni → Cu → Zn that Irving and Williams codified in 1953.

## Evidence
- Co(II) at pH 7 (final/result_01): "the free aquo Co²⁺ concentration at pH 7 is ≈ 5.4 × 10⁻⁴ M — a 10-fold ligand excess only sequesters about half of the cobalt"; Co²⁺ 54.26 %, [Co(Gly)]⁺ 39.40 %, [Co(Gly)₂] 6.17 %; log β₁ = 4.67, log β₂ = 8.46.
- Ni(II) at pH 7 (final/result_02): "free aquo Ni²⁺ is reduced to 4.6 × 10⁻⁵ M (4.6 % of total Ni) — a ~22-fold suppression"; [Ni(Gly)₂] 54.0 %, [Ni(Gly)]⁺ 34.8 %, [Ni(Gly)₃]⁻ 6.57 %; cumulative log β₁ = 5.74, log β₂ = 10.58, log β₃ = 14.10.
- Cu(II) at pH 7 (final/result_03): "[Cu²⁺]_free = 2.81 × 10⁻⁹ M, i.e. only 2.8 parts per million of total Cu remains uncomplexed, corresponding to a conditional pM = 8.55"; [Cu(Gly)₂] 99.43 %, [Cu(Gly)]⁺ 0.57 %; log β₂ = 15.10, "the largest bis-amino-acid formation constant of the first-row divalents".
- Zn(II) at pH 7 (final/result_04): "free aquo [Zn²⁺] at pH 7 = 3.37 × 10⁻⁴ M (i.e. only ~34 % of the 1 mM Zn total is retained as the free hexaaquo ion)"; [Zn(Gly)]⁺ 46.0 %, Zn²⁺ 33.7 %, [Zn(Gly)₂] 19.1 %; log β₁ = 4.96, log β₂ = 9.19.
- All four calculations: 21/21 samples converged at fixed I = 0.1 m, 25 °C; no solid metal hydroxide precipitated in the pH 6.5–7.5 window for any of the four metals.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute speciation of Co(II) with glycine to test Irving-Williams series prediction.
- [Result 02](final/result_02/answer.md): Compute speciation of Ni(II) with glycine at pH 7 to test Irving-Williams series prediction.
- [Result 03](final/result_03/answer.md): Compute speciation of Cu(II) with glycine at pH 7 to test Irving-Williams series prediction.
- [Result 04](final/result_04/answer.md): Compute speciation of Zn(II) with glycine at pH 7 to test Irving-Williams series prediction.
