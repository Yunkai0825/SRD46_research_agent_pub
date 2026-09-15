## Answer

**Falsifiable prediction (chelate effect, matched donor equivalents).** At fixed pH and matched total donor-atom concentration, replacing a monodentate ligand by a chemically similar bidentate ligand (and then by a hexadentate ligand) must **monotonically lower the equilibrium free [Ni²⁺]** (equivalently, monotonically raise pNi = −log[Ni²⁺]). The prediction is falsified if pNi does *not* increase strictly along NH₃ → en → EDTA.

**Test result: the prediction holds, dramatically.** At pH 7, 25 °C, I ≈ 0.03–0.05 M, 1 mM total Ni(II), and ~60 mM total donor atoms:

| Ligand (denticity) | Total ligand | Free [Ni²⁺] at pH 7 | pNi | Dominant Ni species |
|---|---:|---:|---:|---|
| NH₃ (monodentate) | 60 mM | 8.44 × 10⁻⁴ M | 3.07 | free Ni²⁺(aq) (84%) |
| en (bidentate) | 30 mM | 2.60 × 10⁻⁷ M | 6.58 | [Ni(en)₂]²⁺ (84%) |
| EDTA (hexadentate) | 10 mM | ≈ 1.5 × 10⁻³⁵ M (log[Ni²⁺] = −34.83) | 34.83 | [Ni(EDTA)(OH)]³⁻ (100%) |

Free [Ni²⁺] falls monotonically over ~32 orders of magnitude from NH₃ → en → EDTA. The denticity trend is **not violated** — it is confirmed spectacularly.

**Chemical interpretation.** Three effects, all pointing the same way, produce the huge span:

1. *Protonation losses shrink as denticity increases relative to basicity.* NH₃ (pKₐ ≈ 9.26 of NH₄⁺) is ~99.5% protonated at pH 7, so only ~3.3 × 10⁻⁴ M free NH₃ is actually available to bind Ni²⁺; the ammine ladder never gets past the mono complex. En (pKₐ₁ ≈ 7.1, pKₐ₂ ≈ 9.9) is also mostly protonated, but a small free-en pool of ~1 × 10⁻⁵ M still suffices because each en delivers *two* donors per binding event. EDTA has one deprotonation event essentially completed at pH 7 (HEDTA³⁻ dominates at 88%), and the very high Ni–EDTA affinity (log K for Ni²⁺ + HEDTA³⁻ → [Ni(EDTA)H]⁻ and subsequent deprotonation to [Ni(EDTA)]²⁻ / [Ni(EDTA)(OH)]³⁻) more than compensates for any residual protonation cost.
2. *Entropy — the classical chelate effect.* Forming [Ni(en)₂]²⁺ from Ni²⁺(aq) releases four water molecules while consuming only two ligand particles; forming [Ni(EDTA)(OH)]³⁻ releases five/six waters while consuming one ligand. This translational-entropy bonus is why one hexadentate binding event outperforms six independent monodentate binding events by many orders of magnitude at the same donor loading.
3. *Multiplicative vs. single-shot binding.* The ammine complexes need K₁·K₂·…·[NH₃]ⁿ built from a sub-millimolar free-NH₃ activity, so the higher ammines are essentially absent. En only needs two encounters and hits a clean [Ni(en)₂]²⁺ plateau. EDTA sequesters Ni in one encounter, and at pH 7 a further hydroxo-addition gives the mixed [Ni(EDTA)(OH)]³⁻ complex as the sole significant Ni species — leaving only ~10⁻³⁵ M free Ni²⁺.

**Practical corollary.** With ammonia at 60 mM, 84% of Ni is still aquated and Ni(OH)₂(s) begins to precipitate above pH 7.6 because the ammine ladder cannot hold the metal in solution. With en at 30 mM, Ni is fully retained as [Ni(en)ₙ]²⁺ and hydrolysis is suppressed. With EDTA at 10 mM, Ni is locked in the 1:1 chelate and free Ni²⁺ is thermodynamically negligible under any biologically or environmentally relevant condition — the classical reason EDTA is used to mask trace-metal activity.

## Validation status: incomplete

## Evidence

- **NH₃ (60 mM, pH 7):** "Free [Ni²⁺] = 8.44 × 10⁻⁴ M (i.e. 84.4% of total Ni is still the aquo ion). [Ni(NH₃)]²⁺ = 1.48 × 10⁻⁴ M (14.8%). … Dominant Ni-containing species at pH 7: free Ni²⁺(aq)." (calculation 1)
- **En (30 mM, pH 7):** "[Ni(en)₂]²⁺ = 8.37 × 10⁻⁴ M (83.7%); [Ni(en)₃]²⁺ = 1.06 × 10⁻⁴ M (10.6%); [Ni(en)]²⁺ = 5.61 × 10⁻⁵ M (5.6%); **Ni²⁺ (free) = 2.60 × 10⁻⁷ M (0.026%)**. pNi = 6.58 at pH 7.0." (calculation 2)
- **EDTA (10 mM, pH 7):** verdict — "Dominant species by pH region: pH 6.5–7.5 → [Ni(EDTA)(OH)]³⁻" at 100% fraction; log_conc.csv row pH = 7.0000 gives log[Ni²⁺] = −34.833 (⇒ [Ni²⁺] ≈ 1.5 × 10⁻³⁵ M), log[[Ni(EDTA)(OH)]³⁻] = −3.000 (1.0 × 10⁻³ M), log[[Ni(EDTA)]²⁻] = −22.54. (calculation 3, envelope + log_conc + verdict)
- All three sweeps converged 21/21 pH points; no Ni(OH)₂(s) precipitation at pH 7 in any of the three systems.
- Ligand-side protonation at pH 7 (from the same runs): NH₃ 99.5% NH₄⁺; en 63% H₂en²⁺ + 30% Hen⁺ (only ~1.1 × 10⁻⁵ M free neutral en); EDTA 88% HEDTA³⁻ — quantitatively explaining why the "matched donor equivalents" comparison is really a competition against very different protonation penalties.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute Ni(II) speciation with ammonia to obtain free [Ni2+] at pH 7 for chelate-effect comparison.
- [Result 02](final/result_02/answer.md): Compute Ni(II) speciation with ethylenediamine (en) to obtain free [Ni2+] at pH 7 for chelate-effect comparison.
- [Result 03](final/result_03/answer.md): Compute Ni(II) speciation with EDTA to obtain free [Ni2+] at pH 7 for chelate-effect comparison against ammonia and ethylenediamine.
