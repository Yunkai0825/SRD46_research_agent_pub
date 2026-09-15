## Doability
Doable — SRD-46 provides Co(II), Ni(II), Cu(II), and L-histidine equilibria; a fixed-I pH_sweep is the appropriate method for a joint one-pot speciation.

## Result
- System: Co(II) 1.0 mM + Ni(II) 1.0 mM + Cu(II) 1.0 mM + L-histidine 5.0 mM (5:1 total L:M).
- Method: 1-D pH_sweep, pH 4.0–10.0 in 0.1 steps (61 points).
- Conditions: T = 25 °C, ionic strength fixed at I = 0.1 M, redox excluded.
- Convergence: 61/61 samples converged for every metal (Co, Ni, Cu) and for ligand L1. Calculated I stayed 5.8e-4 – 7.0e-3 M (below the fixed target — activity corrections use I = 0.1 M as declared).
- Precipitation: the only solid detected in the whole scan is Co(OH)2(s) at pH 10.00 (8.18e-6 M, i.e. <1% of total Co); Cu(OH)2(s) and Ni(OH)2(s) never saturate in the pH 4–10 window at these totals (log[Cu(OH)2(s)] and log[Ni(OH)2(s)] remain −50 throughout, meaning the aqueous complexes keep the metals in solution well below Ksp).

## Analysis

### Free [M²⁺] at pH 6, 7, 8 (from `*_log_conc.csv`)

| pH | log[Co²⁺] | log[Cu²⁺] | log[Ni²⁺] | [Co²⁺] (M) | [Cu²⁺] (M) | [Ni²⁺] (M) |
|---:|---:|---:|---:|---:|---:|---:|
| 6.0 | −3.560 | −8.332 | −5.088 | 2.8e−4 | 4.7e−9 | 8.2e−6 |
| 7.0 | −4.563 | −9.969 | −5.990 | 2.7e−5 | 1.1e−10 | 1.0e−6 |
| 8.0 | −5.518 | −11.117 | −6.575 | 3.0e−6 | 7.6e−12 | 2.7e−7 |

Against 1.0 mM total this means the fraction of each metal left as aquo M²⁺ collapses on going pH 6 → 8 from 28% → 0.3% for Co, 0.8% → 0.03% for Ni, and 5e−6 → 8e−9 for Cu — Cu is essentially entirely sequestered by histidine, while a substantial pool of aquo Co²⁺ still survives at pH 6.

### Dominant complexes at pH 6, 7, 8 (from verdict speciation blocks)
- **Cu(II).** Already at pH 6 the ML₂ complex **[Cu(Hist)₂]** is dominant (crossover [Cu(Hist)₂H]⁺ ↔ [Cu(Hist)₂] at pH ≈ 5.76). By pH 7 and 8 [Cu(Hist)₂] is essentially the sole Cu species (peaks 99.4% at pH 8.4). This reflects Cu²⁺'s combination of the highest log β for ML₂ in the table (log β([Cu(Hist)₂]) = 18.07 vs 12.38 for Co and −15.77 for Ni's ML₂ in this card) and, in the protonated regime, the additional MHL and M(HL)₂ chelates (log β([Cu(Hist)H]²⁺) = 14.20; log β([Cu(Hist)₂H₂]²⁺) = 27.23), which is why Cu(II) grabs histidine at the lowest pH of the three.
- **Ni(II).** Dominant species across pH 6, 7, 8 is **[Ni(Hist)]⁺** (Ni²⁺ ↔ [Ni(Hist)]⁺ crossover at pH ≈ 4.65; [Ni(Hist)]⁺ peaks 100% at pH 9.2). The card's ML₂ Ni-histidine value (log β = −15.77) is so low that Ni(Hist)₂ never appears — Ni is effectively locked into 1:1 chelation. Note that this SRD-46 value for Ni(Hist)₂ is anomalously low relative to the classical literature (~log β ≈ 15–16 for Ni-bis-histidinate); with the card as loaded, only [Ni(Hist)]⁺ is available to accept Ni.
- **Co(II).** At pH 6 the dominant form is still **[Co(Hist)]⁺** (Co²⁺ ↔ [Co(Hist)]⁺ crossover at pH ≈ 5.77); by pH 7 the ML → ML₂ crossover ([Co(Hist)]⁺ ↔ [Co(Hist)₂] at pH ≈ 6.92) has just occurred, so at pH 7 and 8 **[Co(Hist)₂]** dominates. This later ML→ML₂ handover than Cu reflects the smaller ML₂ formation constant of Co(II) with histidine (log β = 12.38 vs 18.07 for Cu).

### log(free [M²⁺]) separation across pH 6–8
Defining Δlog = log[Ma²⁺] − log[Mb²⁺] (larger negative value = more strongly sequestered):

| pH | log[Cu]−log[Co] | log[Cu]−log[Ni] | log[Ni]−log[Co] |
|---:|---:|---:|---:|
| 6.0 | −4.77 | −3.24 | −1.53 |
| 7.0 | −5.41 | −3.98 | −1.43 |
| 8.0 | −5.60 | −4.54 | −1.06 |

Interpretation:
- **Cu vs Co** widens from ~4.8 to ~5.6 decades between pH 6 and 8 — Cu is ≈10⁵-fold more strongly held than Co over this window. Chemically, once histidine is deprotonated enough to form ML₂, Cu takes both a glycinate-like N,O and an imidazole donor giving the classical Irving–Williams maximum, whereas Co(II) only reaches Co(Hist)₂ near pH 7 and still leaves several µM aquo Co.
- **Cu vs Ni** widens from 3.2 to 4.5 decades — Ni(II) is meaningfully complexed but limited to Ni(Hist)⁺ in this card, so it cannot follow Cu into the very stable ML₂ regime.
- **Ni vs Co** is only ~1.1–1.5 decades and slightly narrows toward pH 8 as Co finally forms Co(Hist)₂; discrimination between Ni and Co on free-M²⁺ alone is therefore poor across pH 6–8.

### Practical implication
The pot is an excellent discriminator of Cu(II) from the other two (Δlog ≥ ~3 across the whole physiological window and growing with pH), a reasonable Cu/Ni separator (Δlog ~4–4.5 at pH 7–8), but only a modest Ni/Co separator — Co and Ni free-ion pools stay within roughly one order of magnitude. Histidine (5 mM, i.e. only ~1.7 equiv per metal) is largely consumed by Cu(Hist)₂ over pH 6–9 (the [Cu(Hist)₂] ligand-fraction peak is 39.8% at pH 8.4; [Co(Hist)₂] peaks 37.5% only near pH 9.9), so any assay that relies on free [M²⁺] contrast at pH 7–8 will read out Cu²⁺ suppression sharply while Co/Ni respond more gradually. Solid formation is not a concern in this window: only trace Co(OH)₂(s) appears at pH 10 and Cu/Ni hydroxides remain undersaturated because the histidinate complexes hold [Cu²⁺] and [Ni²⁺] far below their Ksp thresholds.

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
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_concentrations.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_concentrations.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_Co$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_Co$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_Cu$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_Cu$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_L1.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_L1.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_Ni$+2.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_envelope_Ni$+2.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_Cu.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_Cu.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_L1.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_L1.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_ligand.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_ligand.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_metal.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_metal.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_Ni.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_frac_Ni.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_log_conc.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_log_conc.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_log_conc.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_log_conc.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_phase_balance_Co.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_phase_balance_Co.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_phase_balance_Cu.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_phase_balance_Cu.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_phase_balance_Ni.png](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_phase_balance_Ni.png>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_run_params.json](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_run_params.json>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_state_metrics.csv](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_state_metrics.csv>)
- [solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_verdict.md](<solver/Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_verdict.md>)
- [solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_Co.json](<solver/topology_Co$+2_+_Co$+0_+_Co$+3_+_Co$+4_+_Cu$+1_+_Cu$+0_+_Cu$+2_+_Ni$+2_+_Ni$+0_+_Ni$+3_+_Ni$+4_+_Histidine_Co.json>)
- [verdict.json](<verdict.json>)
