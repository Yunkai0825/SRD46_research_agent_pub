## Answer

Based on speciation modelling of Pb(II)/Zn(II)/Ca(II) (1 mM each) with 5 mM chelator across pH 6–8 at I = 0.1 M using SRD-46, **DTPA (diethylenetriaminepentaacetic acid) is the recommended chelator** among candidates that can be numerically evaluated in this database — but with an important caveat: **DTPA delivers massive Pb-over-Ca selectivity (~10⁸) but essentially no Pb-over-Zn selectivity (~0.25, i.e. Zn²⁺ is actually marginally more sequestered than Pb²⁺).**

**Ligand survey outcome:**
- **EDTA** — build failed deterministically at the LC2 stage (missing protonated ML/MHL/MH₂L/MH₃L species in one metal's EDTA ladder); no speciation could be computed in this session.
- **DTPA** — full converged sweep; log β(Pb-DTPA) = +18.80, log β(Zn-DTPA) = +18.20, log β(Ca-DTPA) = +10.75. ΔlogK(Pb–Zn) is only ~0.6, so DTPA does not discriminate the two soft/borderline metals. ΔlogK(Pb–Ca) is ~8, giving the Pb/Ca window.
- **DMSA (meso-2,3-dimercaptosuccinic acid, succimer)** — full converged sweep, but SRD-46 lists only a single unfavourable Pb-DMSA complex (log β([Pb(meso)]²⁻) = −5.56) and no polynuclear or protonated Pb-DMSA analogues. Under these parameters Pb is controlled by hydroxo clusters (Pb₄(OH)₄⁴⁺, Pb₆(OH)₈⁴⁺), not by DMSA. The database — not the chemistry — is the limiting factor: the well-known clinical Pb-succimer affinity is not captured.

**Chemical interpretation.** In near-neutral water, DTPA sits in its H₂DTPA³⁻ ↔ HDTPA⁴⁻ deprotonation regime; each metal competes with H⁺ for the fully deprotonated DTPA⁵⁻ N₃O₅ donor cage. Pb²⁺ and Zn²⁺, being polarisable Lewis acids well-matched to the polyaza-polycarboxylate cavity, are both essentially quantitatively titrated into [M(DTPA)]³⁻ from pH 6 onward, dropping free [M²⁺] to sub-picomolar levels. Ca²⁺, a hard cation with poor affinity for the polyamine backbone, only starts to bind appreciably above pH ~7.5 as the ligand deprotonates through H₂ → H, so free [Ca²⁺] falls only two orders of magnitude across the window and remains 5–7 log units above free [Pb²⁺]. The chemistry of "Pb-over-Ca" selectivity is therefore hard-vs-soft donor matching (Pb/Zn ≫ Ca on aminopolycarboxylates); the failure of Pb-over-Zn selectivity is that Pb and Zn are chemically too similar toward DTPA's donor set — a genuinely Pb-selective ligand would need a thiolate donor with much larger ΔlogK(Pb–Zn).

**Practical recommendation.** For a matrix where Ca²⁺ is the primary interferent and Zn²⁺ is either absent or tolerable to co-remove, DTPA at 5 mM gives near-total Pb sequestration with only ~99.7 % Ca loss. If the goal is truly Pb-over-Zn selectivity (as in clinical decorporation), SRD-46's DTPA data confirms that aminopolycarboxylates cannot deliver it; a soft-donor thiolate ligand is required, but such candidates (DMSA, D-penicillamine) are inadequately parameterized for Pb in the current database and cannot be quantitatively evaluated here.

## Evidence
- **DTPA free-metal concentrations (from `*_log_conc.csv`):**
  - pH 6.0: log[Pb²⁺] = −11.81, log[Zn²⁺] = −11.24, log[Ca²⁺] = −3.92
  - pH 7.0: log[Pb²⁺] = −13.72, log[Zn²⁺] = −13.12, log[Ca²⁺] = −5.68
  - pH 7.5: log[Pb²⁺] = −14.59, log[Zn²⁺] = −13.99, log[Ca²⁺] = −6.54
- **DTPA selectivity ratios [Pb²⁺]/[M²⁺]:**
  - pH 6–8: [Pb²⁺]/[Zn²⁺] ≈ 0.25–0.27 (Zn is marginally *more* bound)
  - pH 6–8: [Pb²⁺]/[Ca²⁺] ≈ 10⁻⁸ (eight orders of magnitude Pb-over-Ca)
- **DTPA dominant species at pH 8.0:** [Pb(DTPA)]³⁻ = 100.0 %, [Zn(DTPA)]³⁻ = 99.9 %, [Ca(DTPA)]³⁻ = 99.7 %. All 41/41 pH points converged; residuals ≤ 2·10⁻¹¹.
- **DTPA log β values (SRD-46):** Pb-DTPA +18.80, Zn-DTPA +18.20, Ca-DTPA +10.75, [Ca(DTPA)H]²⁻ +16.86. ΔlogK(Pb–Zn) = 0.6; ΔlogK(Pb–Ca) = 8.05.
- **DMSA outcome (parameterization limit):** only Pb-DMSA species in SRD-46 is [Pb(meso)]²⁻ with log β = −5.56 (unfavourable); [Pb(meso)²⁻] stays 10⁻¹³–10⁻¹⁵ M across pH 6–8. Free [Pb²⁺]/[Zn²⁺] appears ~0.4–1.0 but reflects Pb₄(OH)₄⁴⁺ / Pb₆(OH)₈⁴⁺ hydrolysis and ZnO(s) precipitation, not chelation. DMSA does not bind Ca (no Ca-L1 species carded).
- **EDTA outcome:** LC2 build error — missing `<M1><H><L1>`, `<M1><H>2<L1>`, `<M1><H>3<L1>` species in an EDTA protonation ladder; no solver output produced. The specific metal owning the failed ladder is not identifiable from the generic `<M1>` template.

## Final deliverables

- [Result 01](final/result_01/answer.md): Evaluate EDTA as a selective Pb(II) chelator versus Zn(II) and Ca(II) in near-neutral water.
- [Result 02](final/result_02/answer.md): Speciation of Pb(II), Zn(II), Ca(II) with DTPA in near-neutral water to assess selective Pb chelation.
- [Result 03](final/result_03/answer.md): Test DMSA (meso-2,3-dimercaptosuccinic acid, succimer) as a soft-donor Pb(II)-selective chelator in a mixed pot with Zn(II) and Ca(II) near neutral pH.
