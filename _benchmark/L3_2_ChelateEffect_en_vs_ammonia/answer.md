## Answer

**Hypothesis (falsifiable form).** If the chelate effect is real, then a solution of Ni(II) with the bidentate ligand ethylenediamine (en) should leave a significantly lower free [Ni²⁺] at equilibrium than a solution containing an equivalent (or greater) total amount of the monodentate analog ammonia, at the same pH, temperature and ionic strength. Concretely: at pH 7, 25 °C, I = 0.1 M, 1 mM Ni(II) total, compare 10 mM en (20 mM N-donor equivalents) against 20 mM NH₃ (also 20 mM N-donor equivalents). The chelate effect predicts free [Ni²⁺]_en ≪ free [Ni²⁺]_NH₃.

**Result: the chelate effect is confirmed, and the magnitude is ~330×.**

| System (pH 7, 1 mM Ni, 25 °C, I = 0.1 M) | Free [Ni²⁺] | Fraction of total Ni as free aquo |
|---|---|---|
| 10 mM ethylenediamine | **2.87 × 10⁻⁶ M** | 0.29 % |
| 20 mM ammonia | **9.44 × 10⁻⁴ M** | 94.4 % |

Ethylenediamine suppresses free Ni²⁺ by a factor of **~329** (≈2.5 orders of magnitude) relative to ammonia, even though the ammonia system has the same number of donor nitrogens.

**Chemical interpretation.** Two effects combine, both classic components of what is loosely called "the chelate effect":

1. *Ligand availability at pH 7.* Ammonia is a strong base (pKa(NH₄⁺) = 9.26), so at pH 7 only ~0.55 % of the 20 mM total is present as free NH₃ (≈1.1 × 10⁻⁴ M). Ethylenediamine's second amine has pKa ≈ 7.1, so a much larger fraction of "en" character is available near neutral pH.
2. *Entropy / cooperative binding per binding event.* Each en molecule delivers two donors in one association step, so β₂([Ni(en)₂]²⁺) = 10¹³·⁴⁴ produces a heavily populated chelate ring even when free [en] is only ~3 µM. Ammonia must bind independently; β₂([Ni(NH₃)₂]²⁺) = 10⁴·⁸⁹ and β₆ = 10⁸·³⁰ are numerically inadequate at [NH₃] ≈ 10⁻⁴ M, so β_n·[NH₃]ⁿ collapses rapidly with n.

The consequence is dramatic: in en, Ni(II) exists as **[Ni(en)₂]²⁺ (78.7 %) + [Ni(en)]²⁺ (18.1 %) + [Ni(en)₃]²⁺ (2.9 %)**, and only 0.29 % remains as the labile hexaaquo ion. In ammonia, Ni(II) is essentially **still Ni(H₂O)₆²⁺ (94.4 %)** with only a small [Ni(NH₃)]²⁺ shoulder (5.5 %); the higher ammines never exceed 0.1 %. Hydrolysis and Ni(OH)₂(s) are chemically irrelevant in both cases at pH 7 — the two ligand systems compete only with water for the Ni coordination sphere, not with hydroxide.

**Verdict.** The computation **supports** the chelate effect, quantitatively: with matched donor-nitrogen totals, en outperforms NH₃ as a Ni(II) sequestrant by ~330-fold in free [Ni²⁺] at pH 7. This is exactly why en (and polyamines generally) are the preferred masking ligands for divalent 3d metals near neutral pH — ammonia would require pH ≥ 9–10 (i.e. above its ammonium pKa) to release enough free NH₃ to be competitive.

## Evidence

- **en system (Call 1, pH 7.00):** "Free Ni²⁺ = 2.87 × 10⁻⁶ M (≈0.29 % of total Ni); [Ni(en)₂]²⁺ = 7.87 × 10⁻⁴ M (≈78.7 % — dominant); [Ni(en)]²⁺ = 1.81 × 10⁻⁴ M (≈18.1 %); [Ni(en)₃]²⁺ = 2.92 × 10⁻⁵ M (≈2.9 %)." Formation constants log β₁ = 7.30, log β₂ = 13.44, log β₃ = 17.51. All 11/11 samples converged; Ni(OH)₂(s) undersaturated everywhere.
- **NH₃ system (Call 2, pH 7.00):** "Ni²⁺ (free, aquo) = 0.9437 → [Ni²⁺] = 9.44 × 10⁻⁴ M; [Ni(NH₃)]²⁺ = 5.52 × 10⁻² → 5.52 × 10⁻⁵ M; [Ni(NH₃)₂]²⁺ = 8.70 × 10⁻⁷ M." Free [NH₃] ≈ 1.1 × 10⁻⁴ M (only ~0.55 % of the 20 mM total, because pKa(NH₄⁺) = 9.26). 21/21 samples converged; Ni(OH)₂(s) undersaturated everywhere.
- **Head-to-head ratio:** free [Ni²⁺]_NH₃ / free [Ni²⁺]_en = 9.44 × 10⁻⁴ / 2.87 × 10⁻⁶ ≈ **329**, i.e. ~2.5 orders of magnitude of extra Ni²⁺ suppression by en at matched donor-N loading.

## Final deliverables

- [Result 01](final/result_01/answer.md): Test the chelate effect by computing Ni(II) speciation with ethylenediamine at pH 7.
- [Result 02](final/result_02/answer.md): Test the chelate effect by computing Ni(II) speciation with ammonia at pH 7 for comparison against ethylenediamine.
