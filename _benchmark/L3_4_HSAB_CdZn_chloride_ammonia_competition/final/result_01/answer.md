## Doability
Doable: both metals, both ligands, and pH 7 fall inside SRD-46's Cd/Zn hydroxo/chloro/ammine catalog, and a fixed-pH freeform_sweep is a supported route.

## Result
- System: 1 mM Cd(II) + 1 mM Zn(II) with 0.1 M Cl- and 0.1 M NH3 (total), 25 C, I = 0.1 m, pH held at 7 (narrow band 6.9-7.1 sampled).
- Method: freeform_sweep, joint equilibrium with all Cd and Zn aqueous species from the reference table plus Cd/Zn hydroxide/oxide solids allowed to precipitate.
- Convergence: all 3 pH samples converged=1 with residual ~1e-12 (cells.csv), so the numbers below are trusted evidence.
- Predominance verdict (pH 6.9-7.1): Cd verdict names [Cd(Chlo)]+ (Dms_1) as the dominant Cd form across the whole band; Zn verdict names ZnO(inactive) (Dms_1) as the dominant Zn form across the whole band. The frac_*.csv columns print as 0.0 because total-Zn is dominated by a solid and the frac writer normalises against the aqueous basis; the quantitative distributions below are read directly from the converged log-concentrations and solid moles in cells.csv (basis 1e-3 mol of each metal).

## Analysis
**Cadmium (stays fully aqueous, chloride wins).** At pH 7 the log-concentrations for Cd species (cells.csv, pH=7) give, after antilog and summation of aqueous Cd (~1.04e-3 mol/L, matching the 1 mM budget):
- Chloro complexes: [Cd(Chlo)]+ 4.5e-4, [Cd(Chlo)2] 9.1e-5, [Cd(Chlo)3]- 2.0e-5 -> sum ~5.6e-4, i.e. ~54% of total Cd.
- Aquo Cd2+: 3.6e-4, ~35%.
- Ammine complexes: [Cd(NH3)]2+ 7.4e-5, [Cd(NH3)2]2+ 3.9e-6, [Cd(NH3)3]2+ 4.7e-8, [Cd(NH3)4]2+ 1.7e-10 -> sum ~7.8e-5, ~7.5%.
- Hydroxo: [Cd(OH)]+ ~2e-7 and all higher hydroxo/oxo species below 1e-9; no Cd(OH)2 or CdO precipitates (n_s columns are 0). 
So Cd is essentially all aqueous, and among the aqueous forms chloro-complexes outnumber ammines by roughly 7:1 and are the single largest fraction; the free-hydrated Cd2+ is the next largest pool while ammines are minor. This is exactly what the log-betas in the reference table predict: even though log_beta4 for Cd(NH3)4 (+6.72) is nominally larger than for the mononuclear chlorides, the effective free ammonia at pH 7 is only ~5.5e-4 M (because NH3 is >95% protonated to NH4+ given pKa 9.26) whereas free Cl- is ~0.1 M, so the mass-action product beta*[L]^n favours the chloro ladder.

**Zinc (mostly precipitates; the little that stays dissolved goes to ammine/aquo, not chloride).** The solver puts n_s[ZnO(inactive)] = 9.22e-4 mol at pH 7 (cells.csv), i.e. ~92% of the 1 mM Zn budget drops out as a Zn oxide/hydroxide solid; the Zn(OH)2(alpha) alternative stays at 0 mol, so ZnO is the thermodynamic sink chosen against the Zn(OH)2 log_beta -10.72 vs ZnO -9.61. The aqueous ~8% that remains is distributed:
- Zn2+ 6.8e-5 (~7% of total Zn, ~87% of the aqueous Zn pool).
- Ammine: [Zn(NH3)]+ 7.8e-6, [Zn(NH3)2]2+ 6.3e-7, [Zn(NH3)3]2+ 7.9e-8, [Zn(NH3)4]2+ 4.7e-9 -> sum ~8.5e-6 (~11% of dissolved Zn).
- Hydroxo (aq): [Zn(OH)]+ 2.0e-7, [Zn(OH)2] 6.5e-7 -> ~1% of dissolved Zn.
- Chloro: [Zn(Chlo)]+ 1.25e-6, [Zn(Chlo)2] 7.6e-8 -> ~1.7% of dissolved Zn.
So within the dissolved Zn pool, ammines (~11%) outrank chlorides (~1.7%) by roughly 7:1, even though Cl- is 200x more abundant than free NH3 in solution. This inversion is exactly what the log-betas force: log_beta1(ZnCl+) = -0.30 while log_beta1(Zn(NH3)+) = +2.33, i.e. Zn(II) binds NH3 more than 400x more strongly (per ligand) than Cl-.

**HSAB verdict — confirmed.** The two metals partition ligands in opposite senses. Cd(II) — the softer d10 cation — sinks its aqueous budget into the chloro ladder ([Cd(Chlo)]+ is the single dominant species, and the summed chloro fraction dominates the ammine fraction ~7:1) and hardly touches ammonia despite the ligand being present in large excess. Zn(II) — the harder d10 cation — behaves oppositely: what remains in solution prefers ammonia and water over chloride by the same ~7:1 factor, and the bulk of Zn removes itself as a hard-oxygen-donor precipitate (ZnO) instead of forming stable Zn-Cl complexes. The result is a clean HSAB split: soft Cl- clings to Cd(II), hard N (NH3) and O (OH-/oxide) donors take Zn(II), so in a mixed pot Cd chemistry is dominated by chloro complexes while Zn chemistry is dominated by hydroxo/oxide precipitation with residual ammine character — precisely the qualitative pattern HSAB predicts.

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
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_cells.csv](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_cells.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Cd.csv](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Cd.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Cd.png](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Cd.png>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_lig_Ammonia.png](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_lig_Ammonia.png>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_lig_Chloride ion.png](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_lig_Chloride ion.png>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Zn.csv](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Zn.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Zn.png](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_frac_Zn.png>)
- [solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_run_params.json](<solver/Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_run_params.json>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Cd.json](<solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Cd.json>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Cd_verdict.json](<solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Cd_verdict.json>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Cd_verdict.md](<solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Cd_verdict.md>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Zn.json](<solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Zn.json>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Zn_verdict.json](<solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Zn_verdict.json>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Zn_verdict.md](<solver/topology_Cd$+2_+_Cd$+0_+_Zn$+2_+_Zn$+0_+_Ammonia_+_Chloride_ion_Zn_verdict.md>)
- [verdict.json](<verdict.json>)
