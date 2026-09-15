## Answer

Within the SRD-46 thermodynamic database used by this pipeline, the mixed-ligand ternary complex **Ni(glycine)(ammonia)⁺ is not catalogued as a species**, so its computed abundance at pH 8 is **0 % of total Ni by construction** — not because equilibrium disfavors it, but because no formation constant exists in the underlying card to include it in the equilibrium set.

The chemistry behind why this outcome is unsurprising (and why the "real" ternary fraction would be modest even if included): at pH 8, glycinate overwhelmingly outcompetes ammonia for the Ni(II) coordination sphere. Glycine is a bidentate N,O chelator with stepwise log K values 5.74 / 4.84 / 3.52, and although only ~6.5 % of total glycine is deprotonated to the reactive Gly⁻ form at pH 8 (pKa = 9.57), that is still enough — combined with the chelate effect — to fill the coordination sphere with two or three glycinates. Ammonia, by contrast, is monodentate with weaker stepwise constants (log K₁ = 2.73, K₂ = 2.16, …), and only ~5 % of the ammonia pool is present as the reactive NH₃ neutral (pKa NH₄⁺ = 9.26). The result at pH 8 is that Ni(II) sits essentially inside a glycinate-only regime:

- Ni(Gly)₂ (neutral bis-chelate): **62.3 %**
- Ni(Gly)₃⁻: **25.1 %**
- Ni(Gly)⁺: **12.1 %**
- Free Ni²⁺: 0.5 %
- All Ni-ammine species combined: ≤ 0.07 %
- Ni(OH)₂(s): not saturated

The Ni(Gly)₂ ↔ Ni(Gly)₃⁻ crossover sits at pH ≈ 8.48, so pH 8 falls just inside the bis-glycinate plateau. Because ammine binding is already three to four orders of magnitude below glycinate binding, any ternary Ni(Gly)(NH₃)⁺ would draw primarily from the small Ni(Gly)⁺ pool (12 %) — literature log K values (Sigel/Martell, ~3–4 for Ni²⁺ + Gly⁻ + NH₃ ⇌ Ni(Gly)(NH₃)⁺) suggest a few-percent population would be plausible, but that estimate is **external to this SRD-46 run** and cannot be quantified without adding the ternary formation constant to the database and rerunning.

**Bottom line: within SRD-46, Ni(glycine)(ammonia)⁺ = 0 % of total Ni at pH 8.** A positive quantitative answer requires an extended thermodynamic database that includes the ternary constant.

## Validation status: incomplete

## Evidence

- "The SRD-46 catalog compiled into this run's free-energy card does not contain any mixed-ligand Ni–glycinate–ammine complex … the computed abundance of Ni(Gly)(NH₃)⁺ is exactly 0 % of total Ni."
- Ni(II) speciation at pH 8.0 (from `frac_metal.csv`): Ni(Glyc)₂ 62.27 %, Ni(Glyc)₃⁻ 25.06 %, Ni(Glyc)⁺ 12.11 %, Ni²⁺ 0.49 %, Ni(Ammo)²⁺ 0.068 %, Ni(Ammo)₂²⁺ 2.6e-3 %, Ni(OH)⁺ 1.2e-3 %, Ni(OH)₂(aq) 3.0e-4 %.
- Convergence: 41/41 pH samples converged for every element channel; Ni(OH)₂(s) not saturated.
- Ni–glycinate cumulative log β: 5.74, 10.58, 14.10; Ni–ammine stepwise log K: 2.73, 2.16, 1.65, …; glycine amine pKa = 9.57; NH₄⁺ pKa = 9.26.
- Ni(Gly)₂ ↔ Ni(Gly)₃⁻ crossover at pH ≈ 8.48.
- Literature log K ≈ 3–4 for the ternary Ni(Gly)(NH₃)⁺ is cited from Sigel/Martell as external context and is **not** part of the SRD-46 evidence for this run.

## Final deliverables

- [Result 01](final/result_01/answer.md): Determine the abundance of the ternary mixed-ligand complex Ni(glycine)(ammonia) in a solution containing Ni(II), glycine and ammonia at pH 8.
