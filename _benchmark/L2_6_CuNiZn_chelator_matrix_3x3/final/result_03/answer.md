## Doability
Doable — Cu(II) and citrate are both catalogued (5 Cu–citrate complexes in the SRD-46 free-energy card), and a pH_sweep at fixed I is exactly what the pipeline supports.

## Result
- **System:** 1.00 mM Cu(II)_total + 5.00 mM citrate_total, T = 25.0 °C, fixed I = 0.1 M, redox excluded (Cu(0) and Cu(+I) totals = 0).
- **Method:** 1-D pH speciation sweep, pH 2.0 → 12.0, 101 points, all 101 samples converged.
- **Active free-energy card:** log β for [Cu(Citr)H] = 9.26; [Cu2(Citr)2]2− = 14.5; [Cu2(Citr)(OH)] = 4.86; [Cu2(Citr)2(OH)]3− = 11.2; [Cu2(Citr)2(OH)2]4− = 6.34; Cu(II) hydrolysis β1 for [Cu(OH)]+ = −7.9 and Ksp of Cu(OH)2(s) = 10^{−8.68}; citrate single-protonation log β = 5.65, cumulative log β2 = 10.00, log β3 = 12.90 (values quoted from the run's `LC2/thermodynamic_reference_constants.md`; only the first-protonation constant equals the pKa, so the ligand pKas as read from the card are pKa3 = 5.65, pKa2 = 10.00 − 5.65 = 4.35, pKa1 = 12.90 − 10.00 = 2.90).

**Free [Cu2+] and dominant complexes at pH 7.00** (from `..._log_conc.csv`, exact grid point):

| Species | log10 [M] | [M] | fraction of Cu_total |
|---|---:|---:|---:|
| [Cu2(Citr)2(OH)2]4− | −3.301 | 5.00e−4 | ≈100 % (each complex carries 2 Cu, so 2×5.00e−4 = 1.00e−3 M Cu) |
| Cu2+ (free) | −10.105 | 7.85e−11 | 7.9e−8 |
| [Cu(OH)]+ | −15.395 | 4.03e−16 | 4.0e−13 |
| [Cu(OH)2](aq) | −14.696 | 2.01e−15 | 2.0e−12 |
| [Cu2(Citr)2(OH)]3− | −6.297 | 5.05e−7 | 1.0e−3 |
| [Cu(Citr)H] | −10.630 | 2.34e−11 | 2.3e−8 |

No solid phase is present at pH 7 (Cu(OH)2(s) first precipitates only at pH ≈ 10.9, per the verdict Precipitation block).

## Analysis
**Dominance ladder (from the verdict).** Below pH ≈ 3.3 the metal is essentially uncomplexed Cu2+ (99.4 % at pH 2.0), because the citrate is still locked up as H3Cit / H2Cit− (dominant to pH 2.7 and 4.0 respectively) and cannot coordinate efficiently. Once the third carboxylate begins to deprotonate (card pKa3 = 5.65), a rapid handover occurs through the citrate-bridged dimer series: Cu2+ ↔ [Cu2(Citr)2(OH)]3− at pH ≈ 3.32, then [Cu2(Citr)2(OH)]3− ↔ [Cu2(Citr)2(OH)2]4− at pH ≈ 4.00. From pH 4.1 all the way to 11.1 the metal sits almost exclusively in the doubly hydroxo-bridged dinuclear citrate complex **[Cu2(Citr)2(OH)2]4−**, which reaches 100 % at its peak (pH 9.6). Only above pH ≈ 11.1 does the excess hydroxide finally strip citrate off and precipitate Cu(OH)2(s) (98.9 % at pH 12.0).

**Free [Cu2+] at pH 7.** At the exact pH 7.00 grid point log[Cu2+] = −10.105, i.e. **[Cu2+]_free = 7.85 × 10^{−11} M** — about 8 × 10^{−8} of the 1 mM total. The dominant Cu species is unambiguously **[Cu2(Citr)2(OH)2]4−** (log[complex] = −3.301, ≈ 5.0 × 10^{−4} M; because it carries two Cu, it accounts for essentially the full 1.00 mM copper inventory). The next-most-abundant Cu-bearing species is the mono-hydroxo dimer [Cu2(Citr)2(OH)]3− at only 5 × 10^{−7} M (≈ 0.1 % of total Cu), and every Cu(II)-hydrolysis product ([Cu(OH)]+, [Cu(OH)2], dimeric/trimeric hydroxides) sits below 10^{−14} M. 

**Chemical interpretation.** The huge suppression of free Cu2+ at pH 7 — five orders of magnitude below the total, and roughly seven orders below the hydrolytic [Cu(OH)]+ that would dominate in a citrate-free system near neutrality — is the practical signature of citrate as a Cu(II) buffer/chelator. It works via a *dinuclear, doubly-deprotonated–plus-hydroxo-bridged* motif in which two citrates hold two Cu(II) centres and two bridging hydroxides complete the coordination sphere (net charge −4). Two features conspire to make this species so dominant: (i) the 5:1 excess of citrate over Cu guarantees that citrate is not limiting even after protonation losses, and (ii) the hydroxo bridges are pre-formed at physiological pH, so the ΔG of forming [Cu2(Citr)2(OH)2]4− actually improves as pH rises through the neutral range (each extra OH− drives log β further to the right of the reference reaction). The same hydroxo-bridged stabilisation is why Cu(OH)2(s) precipitation is pushed from its citrate-free onset (~pH 5–6 at 1 mM Cu) all the way up to pH 10.9 here — citrate keeps copper soluble across the entire biologically relevant window.

**Consequence for the selectivity matrix.** For a metal–ligand selectivity table entry at pH 7, the operative Cu(II) activity to compare against other ligands is 7.85 × 10^{−11} M (pCu ≈ 10.1), not the 1 mM analytical total. Any competing ligand whose Cu2+-conditional binding at pH 7 does not exceed this pCu will be *out-competed* by 5 mM citrate.

**Caveats (per the method briefing).** These numbers hold at the card's fixed totals (1 mM Cu, 5 mM citrate) and I = 0.1 M, 25 °C; changing the citrate:Cu ratio will shift the dinuclear/mononuclear balance because the dominant complex is second-order in both Cu and citrate. Redox chemistry (Cu(I), Cu(0)) is deliberately excluded — nothing here speaks to reduction by ascorbate, thiols, etc. Crossover pH values are quoted at the 0.1 pH-unit grid resolution.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Citric_acid_Cu.json>)
- [verdict.json](<verdict.json>)
