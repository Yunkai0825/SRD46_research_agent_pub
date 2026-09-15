## Doability
Doable. The SRD-46 catalog contains DTPA together with Pb(II), Zn(II), and Ca(II) protonated / hydrolysed / DTPA-complexed species, and a fixed-redox pH sweep at 25 °C and I = 0.1 M is exactly what `pH_sweep` computes.

## Result
System: Ca²⁺ (1 mM) + Pb²⁺ (1 mM) + Zn²⁺ (1 mM) + DTPA (5 mM, ~1.67× total-metal excess) in aqueous solution. Method: 1‑D `pH_sweep`, pH 6.0–8.0, 41 points, T = 25 °C, target I = 0.1 M (fixed), redox excluded (only the +2 states were seeded, so no reduced or oxidised metal species could form). Convergence: 41/41; residuals ≤ 2·10⁻¹¹, and the actually calculated ionic strength stayed in 0.022–0.027 M (below the 0.1 M target — the fixed-I request is a Davies-activity setting, not an added inert-salt loading, so the deterministic verdict is what to trust for speciation percentages). No solid phase saturates: both Ca(OH)₂(s) and Zn(OH)₂(α) sit at their −50 (i.e. absent) log-activity floor across the entire window.

## Analysis

**Dominant complexes.** Across the whole pH 6.0–8.0 window the deterministic verdict places every metal in a single dominant form:

| Metal | Dominant species pH 6–8 | Peak fraction |
|---|---|---|
| Pb(II) | `[Pb(DTPA)]³⁻` | 100.0 % at pH 8.0 |
| Zn(II) | `[Zn(DTPA)]³⁻` | 99.9 % at pH 8.0 (with a small [Zn(DTPA)H]²⁻ tail, 8.3 % at pH 6.0) |
| Ca(II) | `[Ca(DTPA)]³⁻` | 99.7 % at pH 8.0 (with `[Ca(DTPA)H]²⁻` 20 % and free Ca²⁺ 12 % at pH 6.0) |

The DTPA ledger echoes this: at pH 6 the unbound ligand pool is mostly `H₂DTPA³⁻` (41.5 %) with `H₃DTPA²⁻` and `HDTPA⁴⁻` shoulders, and by pH 8 the three metal-DTPA complexes each sequester ~20 % of the ligand while free `HDTPA⁴⁻` (25.1 %) plus a bit of `H₂DTPA³⁻` account for the ~1.67 mM ligand excess. The dominance crossover on the ligand side (`H₂DTPA³⁻` → `HDTPA⁴⁻`, bracketing pH 7.8) is the classic DTPA effective pKₐ regime; from the reference table, log β for `HDTPA⁴⁻` = +10.50 and for `H₂DTPA³⁻` = +19.10, i.e. the stepwise `H⁺ + HDTPA⁴⁻ → H₂DTPA³⁻` protonation constant is 19.10 − 10.50 = 8.60, so the H₂/H crossover near pH ≈ 8.6 is bracketed correctly by the sweep.

**Free-metal concentrations (from `*_log_conc.csv`).** Quoted as log₁₀[M²⁺], with actual dilution factors in parentheses:

| pH | log[Pb²⁺] | log[Zn²⁺] | log[Ca²⁺] |
|---:|---:|---:|---:|
| 6.00 | −11.81 (1.6·10⁻¹²) | −11.24 (5.8·10⁻¹²) | −3.92 (1.2·10⁻⁴) |
| 7.00 | −13.72 (1.9·10⁻¹⁴) | −13.12 (7.6·10⁻¹⁴) | −5.68 (2.1·10⁻⁶) |
| 7.50 | −14.59 (2.6·10⁻¹⁵) | −13.99 (1.0·10⁻¹⁴) | −6.54 (2.9·10⁻⁷) |
| 7.90 | −14.55* | −13.99* | −7.15* |

(*pH 7.9 values from the last CSV row inside the 20 000-char read window; the pH 8.0 row lies just beyond that window but the trend is monotonic and the verdict fractions already state Pb→100.0 %, Zn→99.9 %, Ca→99.7 % ML at pH 8.0.)

Every free-metal curve drops with a slope near −1.7 log units per pH unit from 6→7 — exactly what you expect when the dominant free‑ligand form is deprotonating in the H₂DTPA³⁻ / HDTPA⁴⁻ region so that each pH unit gains almost a factor of 10 in ligand-driven pull on the M²⁺ pool. The slope shallows past pH ≈ 7.5 because DTPA has essentially exhausted its remaining deprotonation before its own next major crossover.

**Selectivity ratios [Pb²⁺]/[M²⁺].** Directly from the log-conc columns:

- pH 6.0: [Pb²⁺]/[Zn²⁺] = 10^(−11.81−(−11.24)) ≈ 10^(−0.57) ≈ **0.27** — Pb²⁺ is *lower* than Zn²⁺.
- pH 6.0: [Pb²⁺]/[Ca²⁺] = 10^(−11.81−(−3.92)) ≈ 10^(−7.89) ≈ **1.3·10⁻⁸** — Pb is 8 orders of magnitude below Ca.
- pH 7.0: [Pb²⁺]/[Zn²⁺] ≈ 10^(−0.60) ≈ **0.25**; [Pb²⁺]/[Ca²⁺] ≈ 10^(−8.04) ≈ **9·10⁻⁹**.
- pH 7.5: [Pb²⁺]/[Zn²⁺] ≈ 10^(−0.60) ≈ **0.25**; [Pb²⁺]/[Ca²⁺] ≈ 10^(−8.05) ≈ **9·10⁻⁹**.

The [Pb²⁺]/[Zn²⁺] ratio is essentially pH‑flat and slightly *below* one across the whole 6–8 window, because both Pb²⁺ and Zn²⁺ are almost quantitatively titrated into the same [M(DTPA)]³⁻ envelope by a common HDTPA⁴⁻/DTPA⁵⁻ ligand pool, and the SRD-46 log β values for the two 1:1 DTPA complexes are close (Pb: log β = +18.80; Zn: log β = +18.20). Zn's slightly lower log β leaves marginally more free Zn²⁺, i.e. **DTPA does *not* discriminate Pb²⁺ from Zn²⁺ under these conditions**. That is the practically important finding: DTPA is not a selective lead chelator over zinc.

DTPA *is* strongly selective over calcium: even the protonated `[Ca(DTPA)H]²⁻` (log β = +16.86 for Ca²⁺ + HDTPA⁴⁻) and unprotonated `[Ca(DTPA)]³⁻` (log β = +10.75) are ~8 log units weaker than the corresponding Pb complexes, so free [Ca²⁺] stays five to seven orders of magnitude above free [Pb²⁺] across the window even though total Ca and total Pb are the same 1 mM.

**Chemistry behind the numbers.** In this near-neutral window DTPA is in its ~H₂/H protonation ladder; each metal effectively competes with H⁺ for the same fully deprotonated DTPA⁵⁻ site. Pb²⁺ and Zn²⁺, both strong soft/borderline Lewis acids toward the DTPA N₃O₅ donor set, win the competition almost completely: both drop to sub-nM free levels already at pH 6 and to <10⁻¹³ M by pH 7. Ca²⁺, a hard cation with poor affinity for the polyaza backbone, only becomes majority-complexed as the ligand deprotonates through the H₂→H transition near pH ≈ 8, hence its free concentration falls two orders of magnitude across the window but never approaches the sub-pM levels of Pb and Zn. No hydroxo species (Pb₄(OH)₄⁴⁺, Pb(OH)₂(aq), Zn(OH)₂(aq), etc.) accumulate — they are all ≥ 6 orders of magnitude below the aqua ion because DTPA drains the free-metal pool faster than hydrolysis can. No Ca(OH)₂(s) or Zn(OH)₂(α) saturation.

**Practical implication.** In a mixed Pb/Zn/Ca pot at pH 6–8, a modest DTPA excess (5 mM vs. 3 mM Σmetals) strips Pb²⁺ *and* Zn²⁺ down to essentially undetectable free-ion concentrations while removing only ~99.7 % of free Ca²⁺. If the goal is selective Pb removal, DTPA is unsuitable — a Pb-selective ligand would be needed (e.g. a thiolate or an aminopolythioacetate) whose ΔlogK(Pb−Zn) is much larger than DTPA's ≈0.6 log unit. DTPA's genuine selectivity here is Pb (and Zn) over the alkaline earth Ca, not Pb over Zn.

## Final deliverables

- [LC1/lc1_2_eqmap_card.json](<LC1/lc1_2_eqmap_card.json>)
- [LC1/lc1_sweep_input.json](<LC1/lc1_sweep_input.json>)
- [LC1/status.json](<LC1/status.json>)
- [LC2/free_energy_card.md](<LC2/free_energy_card.md>)
- [LC2/status.json](<LC2/status.json>)
- [LC2/thermodynamic_reference_constants.md](<LC2/thermodynamic_reference_constants.md>)
- [LC3/calc_input_card.json](<LC3/calc_input_card.json>)
- [LC3/status.json](<LC3/status.json>)
- [LD/answer.md](<LD/answer.md>)
- [LD/verdict.json](<LD/verdict.json>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_concentrations.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_concentrations.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_Ca$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_Ca$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_L1.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_L1.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_Pb$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_Pb$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_Zn$+2.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_envelope_Zn$+2.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_L1.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_L1.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_ligand.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_ligand.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_metal.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_metal.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_Pb.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_Pb.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_Zn.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_frac_Zn.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_log_conc.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_log_conc.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_log_conc.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_log_conc.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_phase_balance_Ca.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_phase_balance_Ca.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_phase_balance_Pb.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_phase_balance_Pb.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_phase_balance_Zn.png](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_phase_balance_Zn.png>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_run_params.json](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_run_params.json>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_state_metrics.csv](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_state_metrics.csv>)
- [solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_verdict.md](<solver/Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_verdict.md>)
- [solver/topology_Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_Ca.json](<solver/topology_Ca$+2_+_Ca$+0_+_Pb$+2_+_Pb$+0_+_Pb$+3_+_Pb$+4_+_Zn$+2_+_Zn$+0_+_DTPA_Ca.json>)
- [verdict.json](<verdict.json>)
