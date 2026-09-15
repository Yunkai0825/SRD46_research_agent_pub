## Doability
Doable. Cu(II)/Zn(II) with glycine and ammonia is a canonical mixed-ligand SRD-46 speciation problem; solved as a 1-D pH sweep with hydroxide solids allowed.

## Result
- **System:** 1 mM Cu(II) + 1 mM Zn(II), 10 mM glycine (L1), 0.1 M ammonia (L2), 25 °C, ionic strength 0.1 m, hydroxide solids enabled.
- **Method:** `pH_sweep` from pH 2.0 to 12.0 in 101 steps (Δ = 0.1). Converged: **101/101** (verdict Convergence line and `state_metrics.csv`). Calculated I range 0.0044–0.0574 M (fixed I mode).
- **Products opened:** `..._verdict.md`, `..._frac_metal.csv`, `..._frac_ligand.csv`, `..._envelope_Cu$+2.csv`, `..._envelope_Zn$+2.csv`, plus the deterministic reference-constants projection.

## Analysis

### Dominant Cu(II) species vs pH (verdict "Cu2+ speciation" block)
- pH 2.0 – 3.7 → **Cu²⁺(aq)** (99.2 % at pH 2.0)
- pH 3.7 – 4.8 → **[Cu(Glyc)]⁺** (peak 62.9 % at pH 4.2)
- pH 4.8 – 11.6 → **[Cu(Glyc)₂]** (peak 99.9 % at pH 8.2)
- pH 11.6 – 12.0 → **Cu(OH)₂(s)** (92.1 % at pH 12.0)

Crossovers (grid-bracketed, verdict): Cu²⁺↔[Cu(Glyc)]⁺ ≈ pH 3.64; [Cu(Glyc)]⁺↔[Cu(Glyc)₂] ≈ pH 4.73; [Cu(Glyc)₂]↔Cu(OH)₂(s) ≈ pH 11.54. Chemistry: the bidentate glycinate chelate on Cu(II) is very strong (log β₂ = +15.10 for Cu(Glyc)₂ vs +12.30 for Cu(Ammo)₄; reference-constants table), so as HGlycine deprotonates above pKa ≈ 9.57 enough free Glyc⁻ is generated—even from a small residual pool—to keep the bis-glycinate intact until deep hydrolysis at pH ≈ 11.5.

### Dominant Zn(II) species vs pH (verdict "Zn2+ speciation" block)
- pH 2.0 – 7.0 → **Zn²⁺(aq)** (100 % at pH 2.0)
- pH 7.0 – 7.5 → **[Zn(Glyc)]⁺** (peak 43.9 % at pH 7.2)
- pH 7.5 – 7.6 → **[Zn(Glyc)₂]** (peak 29.3 % at pH 7.7)
- pH 7.6 – 12.0 → **Zn(OH)₂(α, s)** (peak 99.0 % at pH 11.2)

The verdict "Precipitation" block lists Zn(OH)₂(α) already present at pH 7.40 (1.39×10⁻⁴ M) and essentially quantitative by pH 11.40 (9.89×10⁻⁴ M of a 10⁻³ M total). Zn(II) forms glycinate complexes that are far weaker than Cu(II)'s (log β₂ = +9.19 vs +15.10), so hydrolysis (log β for Zn(OH)₂ dissolution = −10.72 in the reference table) beats the ligand near neutrality and only a narrow glycinate window (pH ≈ 7.0–7.6) is ever dominant.

### Ligand partitioning between glycinate and ammine complexes (from `frac_metal.csv`)
For Cu(II) at pH 8.2 (Cu(Glyc)₂ peak): fraction Cu bound as **[Cu(Glyc)₂] ≈ 0.999**, as **[Cu(Ammo)₄]²⁺ ≈ 5×10⁻⁴**, all other Cu(Ammo)ₙ < 10⁻³. Even at the ammine "best case" pH ≈ 9.3 where free NH₃ appears (ammonia dominance shifts NH₄⁺→NH₃ at pH 9.3 per the L2 block), the row shows [Cu(Ammo)₄]²⁺ never rises above ~10⁻³ of total Cu while [Cu(Glyc)₂] stays >0.99. For Zn(II) at pH 9.3 the row shows [Zn(Ammo)₄]²⁺ ≈ 0.12 (peak 12.3 % in the verdict) versus Zn(OH)₂(α) already the majority phase and [Zn(Glyc)₃]⁻ peaking at only 9.3 %.

So across the whole pH 2–12 range **neither metal is ever dominated by an ammine complex**. The dominant complexed forms are glycinate chelates for both metals; Cu(II)'s ammines are outcompeted by glycinate everywhere despite ammonia being 10× more concentrated, because chelation more than pays for the concentration gap (β₂(Cu-Glyc)/β₄(Cu-Ammo) ≈ 10^2.8). Zn(II)'s ammines briefly reach ~12 % near pH 9.3 but never take the lead: hydrolysis to solid Zn(OH)₂ intervenes first.

### Which metal owns each ligand (from `frac_ligand.csv`, values expressed as fraction of the ligand pool)
- **Glycine.** At pH 4–8 the only metal-bound glycine species with appreciable share are Cu's: [Cu(Glyc)]⁺ peaks at ~6.3 % of total glycine (pH 4.2) and [Cu(Glyc)₂] peaks at ~20 % of total glycine (pH 8.2, verdict L1 block). Zn-glycinates never exceed ~5.9 % of the glycine pool (pH 7.7). **Cu(II) dominates the glycine sink** across every pH where glycine is complexed at all. This is a consequence of stoichiometry (Cu takes 2 Glyc per metal at only 1 mM, i.e. 2 mM of the 10 mM pool) plus much higher affinity.
- **Ammonia.** The ammonia pool is overwhelmingly HAmmonia⁺/Ammonia (>99.9 %); the metal-ammine share is negligible. Where any metal-ammine is present, Zn wins numerically: at pH ≈ 9.3, [Zn(Ammo)₄]²⁺ ≈ 1.2×10⁻³ of total NH₃ pool vs [Cu(Ammo)₄]²⁺ ≈ 5×10⁻⁶ (frac_ligand row at pH 9.3). So **Zn(II) is the (very minor) principal user of ammonia**, precisely because Cu is locked up in glycinate and unavailable to compete for NH₃.

### Precipitation windows (verdict "Precipitation" block + saturation columns)
- **Zn(OH)₂(α):** first stable at **pH 7.40** (1.4×10⁻⁴ M, ~14 % of Zn), becomes dominant Zn phase from **pH 7.6 upward**, essentially quantitative by pH 11.2 (99 %).
- **Cu(OH)₂:** does not appear until **pH ≈ 11.5**; dominant only for **pH 11.6 – 12.0**. The soluble bis-glycinate suppresses Cu hydrolysis by ~4 pH units relative to Zn.

Practical reading: in a shared pot, glycine acts as a Cu-selective mask (Cu stays soluble as [Cu(Glyc)₂] up to pH ~11.5 while Zn drops out as hydroxide above pH 7.4), and ammonia—despite being in 10-fold excess over glycine—is chemically irrelevant to the metal speciation because the chelate effect of glycinate dominates for Cu and hydrolysis dominates for Zn before ammine complexes can compete.

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
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_concentrations.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_concentrations.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_Cu$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_Cu$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_L1.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_L1.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_L2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_L2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_Zn$+2.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_envelope_Zn$+2.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_L1.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_L1.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_L2.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_L2.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_ligand.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_ligand.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_metal.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_metal.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_frac_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_log_conc.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_log_conc.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_log_conc.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_log_conc.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_phase_balance_Cu.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_phase_balance_Cu.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_phase_balance_Zn.png](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_phase_balance_Zn.png>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_run_params.json](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_run_params.json>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_state_metrics.csv](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_state_metrics.csv>)
- [solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_verdict.md](<solver/Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_verdict.md>)
- [solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_Cu.json](<solver/topology_Cu$+1_+_Cu$+0_+_Cu$+2_+_Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia_Cu.json>)
- [verdict.json](<verdict.json>)
