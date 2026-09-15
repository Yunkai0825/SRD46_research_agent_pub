## Answer

In this shared pot, **glycine is a Cu-selective ligand and ammonia is chemically irrelevant to both metals** — even at 10× the glycine concentration.

**Cu(II)** stays soluble as a glycinate chelate almost the whole pH range: aquo Cu²⁺ dominates below pH 3.7, the mono-glycinate [Cu(Glyc)]⁺ takes over between pH 3.7–4.8, and the very stable bis-glycinate [Cu(Glyc)₂] then dominates all the way from pH 4.8 to 11.6, where it finally gives way to Cu(OH)₂(s). The chelate effect (log β₂(Cu-Glyc) ≈ 15.1 vs log β₄(Cu-Ammo) ≈ 12.3) more than pays for ammonia's 10× concentration advantage, so [Cu(Ammo)₄]²⁺ never exceeds ~10⁻³ of total Cu anywhere.

**Zn(II)** behaves completely differently: its glycinate complexes are much weaker (log β₂(Zn-Glyc) ≈ 9.2), so Zn²⁺(aq) persists up to pH ~7, glycinate species only briefly poke through around pH 7.0–7.6, and then **Zn(OH)₂(α) precipitates and dominates from pH 7.6 all the way to pH 12**. Zn's ammine [Zn(Ammo)₄]²⁺ manages a small ~12 % share near pH 9.3 but never leads, because hydrolysis intervenes first.

**Ligand ownership**
- **Glycine → Cu.** Cu(II) is the dominant sink for glycine wherever glycine is complexed at all; [Cu(Glyc)₂] alone consumes ~20 % of the total glycine pool at pH 8.2 (2 mM of the 10 mM pool, since Cu takes 2 Glyc per metal). Zn-glycinates never exceed ~6 % of the glycine pool.
- **Ammonia → Zn (barely).** The ammonia pool is >99.9 % NH₄⁺/NH₃; the metal-ammine share is tiny. Where any appears, Zn wins numerically (~1.2×10⁻³ of NH₃ as [Zn(Ammo)₄]²⁺ at pH 9.3) simply because Cu is locked away in glycinate and unavailable.

**Hydroxide-solid takeover windows**
- **Zn(OH)₂(α):** first stable at **pH 7.40**, dominant from **pH ~7.6**, essentially quantitative by pH 11.2 — glycinate/ammine complexes give way to the solid at pH ≈ 7.5–7.6.
- **Cu(OH)₂:** does not appear until **pH ≈ 11.5**; dominant only over **pH 11.6–12.0**. Glycine masks Cu against hydrolysis by roughly 4 pH units compared to Zn.

## Evidence
- Convergence: 101/101 pH steps in [2.0, 12.0], I calc range 0.0044–0.0574 M.
- Cu(II) verdict: Cu²⁺ (pH 2.0–3.7), [Cu(Glyc)]⁺ peak 62.9 % at pH 4.2, [Cu(Glyc)₂] peak 99.9 % at pH 8.2, Cu(OH)₂(s) 92.1 % at pH 12.0.
- Cu crossovers: Cu²⁺↔[Cu(Glyc)]⁺ ≈ pH 3.64; [Cu(Glyc)]⁺↔[Cu(Glyc)₂] ≈ pH 4.73; [Cu(Glyc)₂]↔Cu(OH)₂(s) ≈ pH 11.54.
- Zn(II) verdict: Zn²⁺ (pH 2.0–7.0), [Zn(Glyc)]⁺ peak 43.9 % at pH 7.2, [Zn(Glyc)₂] peak 29.3 % at pH 7.7, Zn(OH)₂(α) peak 99.0 % at pH 11.2.
- Zn(OH)₂(α) first stable at pH 7.40 (1.39×10⁻⁴ M); 9.89×10⁻⁴ M of a 10⁻³ M total by pH 11.40.
- Ammine shares: [Cu(Ammo)₄]²⁺ ≤ ~5×10⁻⁴ of total Cu at its best pH; [Zn(Ammo)₄]²⁺ peaks ~12.3 % at pH 9.3 but is never dominant.
- Ligand ownership: [Cu(Glyc)₂] ≈ 20 % of glycine pool at pH 8.2; Zn-glycinates ≤ ~5.9 %. Ammonia pool >99.9 % as NH₄⁺/NH₃ throughout.
- Reference stability constants: log β₂(Cu-Glyc) = +15.10 vs log β₄(Cu-Ammo) = +12.30; log β₂(Zn-Glyc) = +9.19.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute joint pH 2-12 speciation for a single solution containing Cu(II), Zn(II), glycine, and ammonia, and determine how the two metals partition between glycinate and ammine complexes and where hydroxide solids take over.
