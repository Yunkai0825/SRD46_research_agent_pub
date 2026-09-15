## Answer

**Recommendation: use EDTA, not citrate, as the primary antiscale ligand at pH 8.5 — but recognise that neither ligand at only 3:1 loading actually holds Fe(III) soluble.** The screen produces a clear split. EDTA is the better choice on Fe-solubility grounds (it keeps at least ~19 % of Fe(III) as a soluble chelate versus effectively 0 % for citrate), and its "wasting" of ligand on Ca/Mg/Zn is not really waste at all — it is the same property that gives Fe-vs-hardness *selectivity in free-metal terms* many orders of magnitude larger than citrate can achieve. Citrate is chemically the wrong tool: at boiler pH it lets Fe(III) collapse to ferric oxide, gives essentially no Zn control (ZnO precipitates), and only modestly touches Ca/Mg. Its one virtue — leaving hardness free — is precisely a failure of hardness sequestration.

**Why chemically.** EDTA is a hexadentate polyaminocarboxylate whose fully deprotonated EDTA⁴⁻ wraps every 2+ hardness cation and Fe(III) in a stable octahedral cage; its log β values (Ca 10.65, Mg ≈ 8.7 as read from the crossover, Zn 16.5 + a very strong mixed-hydroxo ternary at 28.1, Fe(III) 25.1) mean that at pH 8.5 — where HEDTA³⁻/EDTA⁴⁻ are the free-ligand forms — the chelate collects all four metals essentially quantitatively (Ca, Mg, Zn all ≥99.99 % bound). Fe(III) is the exception only because α-goethite is *itself* extraordinarily insoluble; even a 25-log-unit chelate cannot beat FeOOH at only 3× ligand excess once [OH⁻] climbs into the 10⁻⁵.⁵ range. Citrate, by contrast, is a small α-hydroxy-tricarboxylate: its Ca (log β = 3.45) and Mg (3.43) affinities are one-fifth those of EDTA on a log scale, and even for Fe(III) the citrate complexes (log β ≈ 8–12) sit far above α-Fe₂O₃'s dissolution log β of +0.70 — hematite therefore takes essentially 100 % of the Fe from pH 2 upward. Zn under citrate falls victim to ZnO precipitation above pH 7.1. Thus the chemistry cleanly separates the two ligands: EDTA wins by *outcompeting hydroxide precipitation for three of the four metals*; citrate loses because on the hard-Lewis-acid axis (Fe³⁺) it cannot beat the oxide, and on the soft/borderline axis (Zn²⁺) it cannot beat ZnO either.

**Metal-bound fractions at pH 8.5, 25 °C, I = 0.1 M, 1 mM M / 3 mM L (each pair its own beaker):**

| Metal | EDTA bound frac. | free [M] (EDTA) | Citrate bound frac. | free [M] (citrate) |
|---|---:|---:|---:|---:|
| Fe(III) | 0.190 (rest precipitates as α-FeOOH) | 4.4 × 10⁻²⁵ M | ~1.6 × 10⁻¹⁰ (rest is α-Fe₂O₃) | 2.8 × 10⁻²⁶ M |
| Ca(II) | 0.999994 | 4.5 × 10⁻⁹ M | 0.285 | 7.2 × 10⁻⁴ M |
| Mg(II) | 0.9999 | 7.9 × 10⁻¹¹ M | 0.276 | 7.2 × 10⁻⁴ M |
| Zn(II) | 1.000 (as [Zn(EDTA)(OH)]³⁻) | 1.2 × 10⁻³⁵ M | 0.0029 (rest is ZnO(s)) | 6.7 × 10⁻⁸ M |

**Selectivity margin in free-[M] terms.** The right figure of merit for antiscale duty is the ratio (or log-difference) between free hardness [M²⁺] and free [Fe³⁺] — small free hardness means you *are* controlling scale, small free Fe³⁺ means you *are* holding iron soluble. However, because in both ligand systems most of the Fe(III) is actually in an oxide solid and only a small aqueous chelate pool is truly "held", the operationally meaningful selectivity is the aqueous-Fe(III) yield weighted against the free-hardness suppression:

- **EDTA** achieves ~19 % soluble Fe(III) (0.19 mM as Fe–EDTA + Fe–EDTA-OH) while simultaneously driving free Ca²⁺ to 4.5 × 10⁻⁹ M, Mg²⁺ to 7.9 × 10⁻¹¹ M, and Zn²⁺ to 1.2 × 10⁻³⁵ M. Free-hardness suppression is 5–8 orders of magnitude, and for Zn is 27 orders of magnitude.
- **Citrate** achieves essentially 0 % soluble Fe(III) (~10⁻¹⁰ fraction, i.e. ~10⁻¹³ M) while leaving free Ca²⁺ and Mg²⁺ at ~7 × 10⁻⁴ M (only ~28 % complexed) and free Zn²⁺ at 6.7 × 10⁻⁸ M (Zn precipitates as ZnO).

So EDTA's advantage on the Fe leg alone is ~9 orders of magnitude in *soluble-Fe(III) recovery* (aqueous Fe-chelate concentration ratio ~10⁹). On the hardness leg, EDTA's free-Ca²⁺ and free-Mg²⁺ are ~10⁵ smaller than citrate's, and free-Zn²⁺ is ~10²⁷ smaller. The composite margin — soluble Fe kept up × free hardness kept down — favours EDTA by at least fifteen orders of magnitude, and that is the quantitative answer the question asks for.

**Two caveats the screen exposes.** (i) Neither 3:1 ligand loading is enough to keep Fe(III) fully soluble at pH 8.5; EDTA needs a substantially higher ratio (or a lower pH) to overcome goethite, and citrate cannot in principle beat hematite at any accessible loading. (ii) The "wasted ligand" framing in the question favours citrate on a bookkeeping basis (citrate consumes only ~9 % of its pool on Ca and <0.2 % on Zn, versus EDTA committing ~1 mM per hardness metal), but a ligand that consumes little because it *binds nothing* is not a chemistry win — it is a diagnosis that the ligand is too weak for the job. The relevant metric is free [M], and on free [M] EDTA is superior on every metal.

## Run status: timed out

The L0 orchestration reached its iteration or reasoning-time limit. This text is a partial synthesis and must not be treated as a completed or validated run. The structured API result and manifest also set `timed_out: true` and `completion_status: timed_out`.

## Evidence

- **Fe(III) + EDTA at pH 8.5:** "[Fe(EDTA)]- = 5.367e-6 M; [Fe(EDTA)(OH)]2- = 1.851e-4 M; Σ Fe–EDTA (aq) = 1.905e-4 M → metal-bound fraction = 19.0 % … FeO(OH)(s,α) = 8.095e-4 M → 80.9 % of Fe has precipitated as goethite. Free [Fe3+] = 4.38e-25 M."
- **Fe(III) + citrate at pH 8.5:** "Total Fe-citrate fraction ≈ 1.58e-10 of total Fe … Σ[Fe–citrate] ≈ 1.6e-13 M — effectively zero. Free [Fe3+]_free ≈ 2.8e-26 M. Hematite accounts for essentially 100.000 % of the Fe inventory."
- **Ca(II) + EDTA at pH 8.5:** "[Ca²⁺]_free = 4.51 × 10⁻⁹ M; [Ca(EDTA)]²⁻ = 1.000 × 10⁻³ M … Ca-bound fraction = 99.9994 %."
- **Ca(II) + citrate at pH 8.5:** "Ca²⁺ (free) fraction 0.71493 → 7.15 × 10⁻⁴ M; total Ca-bound-to-citrate = 28.51 % ≈ 2.85 × 10⁻⁴ M."
- **Mg(II) + EDTA at pH 8.5:** "Fraction as [Mg(EDTA)]²⁻ = 0.999886 … free Mg²⁺ = 1.026e-4 fraction … Free [Mg²⁺] ≈ 7.9 × 10⁻¹¹ M."
- **Mg(II) + citrate at pH 8.5:** "Free Mg²⁺ mole fraction 0.7232 → [Mg²⁺] = 7.23 × 10⁻⁴ M … Mg-bound (sum of Mg–citrate) ≈ 27.6 %."
- **Zn(II) + EDTA at pH 8.5:** "[Zn(EDTA)(OH)]³⁻ = 1.000 × 10⁻³ M ⇒ Zn-bound fraction = 1.000 (100 %) … Free [Zn²⁺] = 1.15 × 10⁻³⁵ M." No precipitation across pH 2–12.
- **Zn(II) + citrate at pH 8.5:** "Free [Zn²⁺] = 6.71 × 10⁻⁸ M … Zn-bound total ≈ 0.29 % … ≈ 99.6 % of the Zn is locked in ZnO(s)."
- **Ligand accounting under EDTA:** each 1 mM hardness metal ties up 1 mM EDTA, so a 3 mM EDTA dose against a 1 Ca + 1 Mg + 1 Zn + 1 Fe(III) mix at 1 mM each is stoichiometrically insufficient — Fe(III) would be the loser under joint conditions.
- **Convergence:** every one of the eight pair runs reports 101/101 samples converged; all quoted numbers are from converged grid points.

## Final deliverables

- [Result 01](final/result_01/answer.md): Assess Fe(III)-EDTA binding at pH 8.5 for boiler-water antiscale ligand screening.
- [Result 02](final/result_02/answer.md): Assess Fe(III)-citrate binding at pH 8.5 for boiler-water antiscale ligand screening.
- [Result 03](final/result_03/answer.md): Assess Ca(II)-EDTA binding at pH 8.5 for boiler-water antiscale ligand screening (hardness competition).
- [Result 04](final/result_04/answer.md): Assess Ca(II)-citrate binding at pH 8.5 for boiler-water antiscale ligand screening (hardness competition).
- [Result 05](final/result_05/answer.md): Assess Mg(II)-EDTA binding at pH 8.5 for boiler-water antiscale ligand screening (hardness competition).
- [Result 06](final/result_06/answer.md): Assess Mg(II)-citrate binding at pH 8.5 for boiler-water antiscale ligand screening (hardness competition).
- [Result 07](final/result_07/answer.md): Assess Zn(II)-EDTA binding at pH 8.5 for boiler-water antiscale ligand screening (hardness competition).
- [Result 08](final/result_08/answer.md): Assess Zn(II)-citrate binding at pH 8.5 for boiler-water antiscale ligand screening (hardness competition).
