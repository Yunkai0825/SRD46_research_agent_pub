## Doability
Doable. Co(II), Ni(II), Cu(II), and L-cysteine are all in the SRD-46 catalog; the request is a fixed-redox pH-speciation sweep, natively supported.

## Result
System: Co(II) + Ni(II) + Cu(II), each 1.0 mM, with L-cysteine 5.0 mM (ligand/total metal = 5:3 ≈ 1.67:1, or 5 per individual metal). Method: 1-D pH_sweep, pH 4.0–10.0 in 0.1 steps (61 points), T = 25 °C, I = 0.1 M fixed, redox excluded. Convergence: 61/61 for every element. One precipitate forms: Cu(OH)2(s), first flagged at pH 6.00 (2.06e-4 M) and rising to essentially 1.00e-3 M by pH 7. No Co(OH)2(s) or Ni(OH)2(s) form anywhere in-range.

## Analysis
**Free [M2+] at the target pH values (from the concentrations CSV, M):**

| pH  | [Co2+]   | [Cu2+] (aq) | [Ni2+]   |
|-----|----------|-------------|----------|
| 6.0 | 9.22e-4  | 7.83e-4     | 4.51e-6  |
| 7.0 | 5.51e-5  | 7.83e-6     | 1.82e-9  |
| 8.0 | 2.35e-7  | 7.83e-8     | 1.33e-12 |

**Dominant species per metal.** From the verdict's dominance intervals and the fraction table:
- **Ni(II):** Ni2+ dominates only up to pH 5.36; from pH 5.4 to 10.0 the field belongs to **[Ni(Cyst)2]2−** (peaks at 100 % at pH 10). This is the earliest and cleanest metal–cysteine takeover. At pH 6.0 [Ni(Cyst)2]2− is already ~91 % of Ni; at pH 7 it is 99.8 %; at pH 8 essentially 100 %.
- **Co(II):** Co2+ still dominates through pH 6.7; a narrow succession follows — [Co(Cyst)] (6.7–6.8), then the polynuclear [Co3(Cyst)4]2− (6.8–7.2), [Co2(Cyst)3]2− (7.2–7.5), and finally **[Co(Cyst)2]2−** from pH 7.5 to 10. At pH 6.0 free Co2+ is still 92 % of total Co; at pH 7.0 it is only 5.5 %, with [Co3(Cyst)4]2−, [Co2(Cyst)3]2− and [Co(Cyst)2]2− carrying most of the mass; at pH 8.0 [Co(Cyst)2]2− is the dominant form (~67 % of Co).
- **Cu(II):** No aqueous cysteine complex appears — the card contains only Cu–OH species plus Cu(OH)2(s). Cu2+ dominates to pH 6.10, then **Cu(OH)2(s)** takes over and holds the field to pH 10. At pH 6 already 21 % of Cu is precipitated; ≥99 % of Cu is bound in the hydroxide solid by pH 6.5 and effectively all of it by pH 7.

**Why the ladder looks this way.** Cysteine is a triprotic ligand (H3L+ / H2L / HL− / L2−); the LC2 card gives cumulative log β_H = 16.58, 18.48, 10.30 for the H3, H2, H1 forms of L2−, so the two side-chain pKa values are ≈ 6.28 (thiol/ammonium H+ off H2L→HL−) and ≈ 10.30 (final H+ off HL−→L2−). Below pH ~6 the free L2− pool is vanishingly small, which is why complexation only 'turns on' near pH 6 for Co and Cu-competent chemistry, and near pH 5.4 for Ni (which additionally uses a mixed [Ni(Cyst)H]+ pathway with log β = 14.64 that lets it grab HL− before full deprotonation). This is the origin of the Ni-early / Co-mid ordering.

The metal–cysteine formation constants (log β from the reference table) are: Ni(Cyst)2 = 19.90 > Co(Cyst)2 = 14.48; the higher Ni bis-cysteinate stability, plus the extra Ni(Cyst)H protonated route, pulls Ni2+ down by ~5 orders of magnitude relative to Co2+ across pH 6–8. Cu(II) *would* form the strongest cysteinates chemically (real Cu(II)–thiolate log β values are much higher), but the SRD-46 card used here contains no aqueous Cu–cysteine species; the free-energy competition is therefore between Cu2+, Cu-hydroxo species, and Cu(OH)2(s) (log K_sp corresponding to log β_dissol = −8.68). Above pH 6.1 the solid wins decisively, so 'free Cu2+' is limited by hydroxide solubility rather than by cysteine binding.

**Discrimination via free [M2+].** Comparing free-ion pools at pH 7.0 (the most useful analytical window): [Co2+] : [Cu2+] : [Ni2+] ≈ 5.5e−5 : 7.8e−6 : 1.8e−9, i.e. Co is ~30× above Cu and ~30 000× above Ni. At pH 8.0 the spread is even larger: Co ≈ 3× Cu ≈ 1.8e5 × Ni. So cysteine provides very strong Ni-vs-others discrimination through pure aqueous chelation, while its apparent Cu suppression here is actually a hydroxide-precipitation artifact of the card's Cu–cysteine gap — the true selectivity against Cu2+ in solution would be even stronger with the Cu(II)–thiolate complexes that this dataset does not contain.

Compared with glycine (weaker donor, no thiol, log β_ML2 ~10 for Ni) and histidine (imidazole + amine, log β_ML2 ~15 for Ni, ~14 for Cu, ~9 for Co), cysteine's key discriminator is the ~10^5 collapse of free Ni2+ by pH 7 driven by the exceptionally stable [Ni(Cyst)2]2− (log β = 19.9). Glycine at the same totals would leave free Ni2+ orders of magnitude higher, and histidine — while strong for Cu and Ni — does not open the same 5-decade Ni/Co gap that cysteine's soft-donor thiolate gives. Cysteine is therefore the best of the three at selectively depleting Ni2+, moderate at depleting Co2+, and (in this dataset) reduces Cu2+ mainly by precipitating Cu(OH)2 rather than by chelation.

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
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_concentrations.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_concentrations.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_Co$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_Co$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_Cu$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_Cu$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_L1.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_L1.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_Ni$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_envelope_Ni$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_Cu.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_Cu.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_L1.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_L1.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_ligand.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_ligand.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_metal.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_metal.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_Ni.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_frac_Ni.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_log_conc.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_log_conc.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_log_conc.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_log_conc.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_phase_balance_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_phase_balance_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_phase_balance_Cu.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_phase_balance_Cu.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_phase_balance_Ni.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_phase_balance_Ni.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_run_params.json](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_run_params.json>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_state_metrics.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_state_metrics.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_verdict.md](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_verdict.md>)
- [solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_Co.json](<solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Cysteine_Co.json>)
- [verdict.json](<verdict.json>)
