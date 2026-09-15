## Doability
Doable — Cu(II), Ni(II), Zn(II) and ethylenediamine (en) are all in the SRD-46 catalog with the needed 1:1, 1:2 (and 1:3 for Ni, Zn) complexes and hydrolysis species; a joint pH-sweep at fixed I is directly supported.

## Result
Joint aqueous pot: Cu²⁺=Ni²⁺=Zn²⁺=1.00 mM, en_total=5.00 mM, T=25 °C, I=0.1 M (fixed), pH 6.0→8.0, 21 points, converged 21/21. Redox excluded (only +2 subtotals populated). All hydroxo mononuclear + polynuclear species and Cu(OH)₂(s), Ni(OH)₂(s), Zn(OH)₂(s,ε) were included; no solid phase saturates anywhere in the window (all four solid columns are 0 across the CSV), so this is a fully aqueous competition.

## Analysis
**Ligand budget and Cu dominance.** The free-en fraction is tiny (Ethylenediamine peaks at only 3.9 µM out of 5 mM at pH 8): the ligand pool is split between the diprotonated H₂en²⁺ (pKa₁≈9.92, pKa₂ derived from cumulative log β₂=17.03 ⇒ pKa₂≈7.11 — from the reference table) and the metal complexes. Across the whole 6–8 window, [Cu(en)₂]²⁺ is the single largest en sink (40 % of total en at pH 8), consistent with Cu's exceptionally strong log β₂ = 19.60 versus 13.44 (Ni) and 10.64 (Zn).

**Per-metal speciation.**
- **Cu(II):** [Cu(en)₂]²⁺ is dominant across the entire 6.0–8.0 range (peak 100 % at pH 8.0; already ~95 % at pH 6.0 with the balance as [Cu(en)]²⁺ ≈ 4.8 %). No hydrolysis species reaches even 10⁻⁸ M. Cu locks up two en per metal essentially quantitatively.
- **Ni(II):** three regions — Ni²⁺ dominates pH 6.0–6.3, [Ni(en)]²⁺ dominates pH 6.3–7.2 (crossover Ni²⁺↔[Ni(en)]²⁺ at pH ≈ 6.30), then [Ni(en)₂]²⁺ takes over pH 7.2–8.0 (crossover at pH ≈ 7.10; peak 81 % at pH 8.0). [Ni(en)₃]²⁺ is minor here (3.8 % of Ni at pH 8) because free en is depleted by Cu.
- **Zn(II):** almost fully uncomplexed as Zn²⁺ from pH 6.0 to 7.6; only above pH 7.6 does [Zn(en)]²⁺ become dominant (crossover Zn²⁺↔[Zn(en)]²⁺ at pH ≈ 7.59). At pH 8.0 Zn is still only ~44 % [Zn(en)]²⁺ + 15 % [Zn(en)₂]²⁺ + 21 % [Zn(OH)₂]°, with 22 % remaining as Zn²⁺. Zn is the weakest binder and also the first to feel neutral-hydrolysis competition.

**Free metal concentrations (from concentrations.csv):**

| pH | [Cu²⁺] (M) | [Ni²⁺] (M) | [Zn²⁺] (M) | [Ni²⁺]/[Cu²⁺] | [Zn²⁺]/[Cu²⁺] |
|---:|---:|---:|---:|---:|---:|
| 6.0 | 1.03e−7 | 7.63e−4 | 9.92e−4 | 7.4 × 10³ | 9.6 × 10³ |
| 7.0 | 8.42e−11 | 4.96e−5 | 7.73e−4 | 5.9 × 10⁵ | 9.2 × 10⁶ |
| 8.0 | 1.61e−12 | 1.89e−6 | 2.17e−4 | 1.2 × 10⁶ | 1.3 × 10⁸ |

**Fraction of each metal bound to en** (1 − free/total): Cu — 99.99 % (pH 6), ≥99.99999 % (pH 7–8); Ni — 24 % (pH 6), 95 % (pH 7), 99.8 % (pH 8); Zn — 0.8 % (pH 6), 23 % (pH 7), 78 % (pH 8).

**Chemical interpretation.** Cu(II) is the classic Irving–Williams peak: its d⁹ Jahn–Teller-stabilised square-planar bis-en complex has log β₂ ≈ 6 orders of magnitude above Zn's and 6 above Ni's per-en. The consequence in one competing pot is dramatic. Even at pH 6, where only ~0.3 % of total en is present as the free diamine (most is H₂en²⁺), Cu wins the ligand and its free-ion concentration drops four orders of magnitude while Ni and Zn are barely touched. Raising pH deprotonates more en (pKa₂≈7.11) and Cu, already saturated, cannot benefit further, so the newly liberated en spills over first to Ni(II) (larger log β than Zn) and only above pH 7.6 to Zn(II). This ordering — Cu ≫ Ni > Zn — is the Irving–Williams series in operation. The [Zn²⁺]/[Cu²⁺] selectivity climbs from ~10⁴ at pH 6 to >10⁸ at pH 8 because Cu's free ion falls faster with pH than Zn's does. **Practical implication:** en at 5× stoichiometric excess is an excellent Cu(II) mask in the presence of Ni(II) and Zn(II) already at pH 6, and becomes essentially perfectly selective at pH 7–8 (Ni/Cu ≈ 10⁶, Zn/Cu ≈ 10⁷–10⁸), all without any precipitation.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_Ni$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_Ni$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_Zn$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_envelope_Zn$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_Ni.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_Ni.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_frac_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_phase_balance_Ni.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_phase_balance_Ni.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_phase_balance_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_phase_balance_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Zn$+2_+_Zn$+0_+_Ethylenediamine_Cu.json>)
- [verdict.json](<verdict.json>)
