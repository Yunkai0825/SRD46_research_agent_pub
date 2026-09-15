## Answer

**HSAB prediction.** Cd(II) is a classic *borderline-to-soft* Lewis acid (large, polarisable, filled d-shell). Chloride is a **soft** base — polarisable, low charge density, forms covalent-flavoured bonds. Ammonia (through N) is a **borderline / hard-leaning** base — smaller, less polarisable, and, crucially at pH 7, mostly protonated to the non-donor NH₄⁺ (pKa 9.26). HSAB therefore predicts that at pH 7 chloride should hold Cd(II) more tightly than ammonia and suppress the free-aquo Cd²⁺ pool to a greater extent.

**Computational test.** At 1 mM Cd, pH 7, 25 °C, I = 0.1 M:

| Ligand system | Free [Cd²⁺] | Fraction of total Cd remaining as free aquo |
|---|---:|---:|
| 0.1 M Cl⁻ | **3.15 × 10⁻⁴ M** | 31.5 % |
| 0.1 M NH₃(tot) | **8.24 × 10⁻⁴ M** | 82.4 % |

Chloride removes ~68 % of the Cd(II) from the free-aquo pool (into CdCl⁺, CdCl₂⁰, and a little CdCl₃⁻), while 0.1 M total ammonia removes only ~18 % (mostly as the mono-ammine Cd(NH₃)²⁺). Free [Cd²⁺] is **~2.6× lower with chloride than with ammonia**. **The computation confirms the HSAB prediction.**

**Chemical interpretation.** Two effects, both aligned with HSAB, drive the outcome:

1. *Intrinsic soft-soft affinity.* The Cd–Cl bond has appreciable covalent character; even modest cumulative constants (log β₁ = 1.52, log β₂ = 2.60) are enough at 0.1 M Cl⁻ to make CdCl⁺ and CdCl₂⁰ each competitive with the aquo ion. Chloride does not need to deprotonate to bind — it is already the active donor at any pH.
2. *Ammonia's basicity works against it near neutrality.* At pH 7 only ~0.5 % of the 0.1 M ammonia is present as the actual donor NH₃; the rest is spectator NH₄⁺. The effective Cd–N binding term K₁·[NH₃] ≈ 10^2.57 × 5×10⁻⁴ ≈ 0.19 exactly reproduces the observed [Cd(NH₃)²⁺]/[Cd²⁺] ≈ 0.20. The higher ammines (which do have larger β) need [NH₃]ⁿ and stay dormant until pH > 8, by which point hydroxide precipitation takes over anyway.

So near neutral pH the ranking free-[Cd²⁺] suppression: **Cl⁻ > NH₃**, which reflects both the intrinsic HSAB match (soft acid prefers soft base) *and* the acid–base fact that a borderline N-donor is largely silenced by protonation two pH units below its pKa. Chloride wins on both counts.

## Evidence
- Cd/Cl at pH 7 (from Call 1 `frac_metal.csv`): CdCl⁺ 38.6 %, Cd²⁺ 31.5 %, CdCl₂⁰ 28.1 %, CdCl₃⁻ 1.75 %; **free [Cd²⁺] = 3.15 × 10⁻⁴ M**.
- Cd/NH₃ at pH 7 (from Call 2 `frac_metal.csv`): Cd²⁺ 82.4 %, Cd(NH₃)²⁺ 16.7 %, Cd(NH₃)₂²⁺ 0.89 %; **free [Cd²⁺] = 8.24 × 10⁻⁴ M**.
- Free-NH₃ fraction at pH 7 = 10^(7−9.26) ≈ 0.55 %, so only ~5 × 10⁻⁴ M of the 0.1 M ammonia total is actually available to coordinate.
- SRD-46 constants used (from `thermodynamic_reference_constants.md`): Cd–Cl log β₁,₂,₃ = 1.52, 2.60, 2.40; Cd–NH₃ log β₁…₄ = 2.57, 4.56, 5.90, 6.72; NH₄⁺/NH₃ pKa = 9.26.
- Both runs fully converged (Cl: 51/51 samples; NH₃: 101/101 samples) and both are sub-saturated at pH 7 (Cd(OH)₂(s) onset at pH ≈ 8.8 and 9.9 respectively).

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute Cd(II) speciation with chloride to determine free [Cd2+] under HSAB test conditions.
- [Result 02](final/result_02/answer.md): Compute Cd(II) speciation with ammonia to determine free [Cd2+] under HSAB test conditions.
