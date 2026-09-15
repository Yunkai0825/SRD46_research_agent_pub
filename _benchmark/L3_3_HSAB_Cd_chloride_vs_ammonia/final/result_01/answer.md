## Doability
Doable — Cd(II) with chloride at fixed pH is well within SRD-46 scope; the pipeline built the full Cd–OH / Cd–Cl ladder and one solid, and converged 51/51 samples on the pH sweep.

## Result
System: Cd$^{2+}$ 1.00 mM + Cl$^-$ 0.100 M in aqueous solution at 25.0 °C, ionic strength fixed at 0.1 M, redox excluded (Cd(0) suppressed at total = 0). Method: `pH_sweep` from pH 2 to 12, 51 points. Convergence: 51/51. The requested condition (pH 7) sits well inside the fully converged, sub-saturated regime (β-Cd(OH)$_2$(s) first precipitates only at pH ≈ 8.8).

## Analysis
### Cd(II) speciation at pH 7 (from `frac_metal.csv`)
At the pH 7 grid point, the Cd(II) mass balance (fractions of total Cd) is:

| Species | Fraction | [species] (M) |
|---|---:|---:|
| [Cd(Chlo)]$^+$ (CdCl$^+$) | 0.3861 | 3.86 × 10$^{-4}$ |
| Cd$^{2+}$ (free aquo) | 0.3153 | 3.15 × 10$^{-4}$ |
| [Cd(Chlo)$_2$] (CdCl$_2^0$) | 0.2809 | 2.81 × 10$^{-4}$ |
| [Cd(Chlo)$_3$]$^-$ (CdCl$_3^-$) | 0.01754 | 1.75 × 10$^{-5}$ |
| [Cd(OH)]$^+$ | 1.53 × 10$^{-4}$ | 1.53 × 10$^{-7}$ |
| [Cd(OH)$_2$]$^0$ | 9.66 × 10$^{-8}$ | 9.66 × 10$^{-11}$ |
| all other hydroxo forms | < 10$^{-11}$ | negligible |

**Free [Cd$^{2+}$] ≈ 3.15 × 10$^{-4}$ M (≈ 31.5 % of total Cd).** The chloro-complexes together account for ~68 % of the metal, split almost evenly between the mono- (CdCl$^+$, 38.6 %) and the neutral bis- (CdCl$_2^0$, 28.1 %) complexes, with only ~1.8 % as CdCl$_3^-$ and essentially no CdCl$_4^{2-}$ (not in the included set for this card).

### Why this distribution
The SRD-46 constants driving the result are the cumulative Cd–Cl formation constants quoted in `LC2/thermodynamic_reference_constants.md`: log β$_1$ = +1.52 (CdCl$^+$), log β$_2$ = +2.60 (CdCl$_2^0$), log β$_3$ = +2.40 (CdCl$_3^-$). At [Cl$^-$] = 0.1 M the effective loadings are β$_1$·[Cl] ≈ 10$^{0.52}$ ≈ 3.3, β$_2$·[Cl]$^2$ ≈ 10$^{0.60}$ ≈ 4.0, β$_3$·[Cl]$^3$ ≈ 10$^{-0.60}$ ≈ 0.25 relative to free Cd$^{2+}$, which reproduces the CdCl$^+$ ≳ Cd$^{2+}$ ≈ CdCl$_2^0$ ≫ CdCl$_3^-$ ordering seen above. The third chloride is only weakly bound (β$_3$ < β$_2$, i.e. K$_3$ < 1), so climbing to CdCl$_3^-$ costs free energy and CdCl$_4^{2-}$ never appears in appreciable amount at 0.1 M Cl$^-$ — consistent with Cd(II) being a *borderline* HSAB acid: it accepts Cl$^-$ readily (the soft-side signature), but is not chloride-avid enough to saturate its coordination shell at seawater-level chloride, which is why a substantial free-aquo pool (>30 %) survives.

Hydrolysis is entirely inactive here. The relevant hydrolysis constants (log β for Cd$^{2+}$ + OH$^-$ ⇌ CdOH$^+$ = –10.10 corresponds to the first hydrolysis pK$_{a1}$ ≈ 10.1 for Cd(H$_2$O)$_n^{2+}$; log β for Cd(OH)$_2^0$ = –20.30) place any noticeable hydrolysis well above pH 8. At pH 7 the CdOH$^+$ fraction is 1.5 × 10$^{-4}$ and Cd(OH)$_2^0$ is 10$^{-7}$, so hydroxo chemistry is 3–7 orders of magnitude below chloride chemistry and can be ignored when reasoning about the free-Cd pool.

### Practical implication (HSAB test)
At fixed pH 7, 0.1 M Cl$^-$ knocks the free Cd$^{2+}$ activity down by only ~0.5 log unit (from a nominal 10$^{-3}$ M with no complexation to 3.15 × 10$^{-4}$ M), a modest attenuation. The bulk of the metal is carried on chloro-species, dominated by CdCl$^+$ and neutral CdCl$_2^0$. Any downstream reactivity assay that senses free Cd$^{2+}$ (adsorption, ISE, biouptake) will therefore see roughly one-third of the total; any assay that senses total dissolved Cd(II) will still see essentially the full millimolar (no precipitation until pH ≈ 8.8, where β-Cd(OH)$_2$(s) begins to sequester the metal and reaches full dominance by pH ≈ 10). These conclusions hold only at the stated totals, 25 °C, and I = 0.1 M.

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
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_concentrations.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_concentrations.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_envelope_Cd$+2.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_envelope_Cd$+2.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_envelope_L1.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_envelope_L1.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_Cd.png](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_Cd.png>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_L1.png](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_L1.png>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_ligand.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_ligand.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_metal.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_frac_metal.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_log_conc.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_log_conc.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_log_conc.png](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_log_conc.png>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_phase_balance_Cd.png](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_phase_balance_Cd.png>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_run_params.json](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_run_params.json>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_state_metrics.csv](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_state_metrics.csv>)
- [solver/Cd$+2_+_Cd$+0_+_Chloride_ion_verdict.md](<solver/Cd$+2_+_Cd$+0_+_Chloride_ion_verdict.md>)
- [solver/topology_Cd$+2_+_Cd$+0_+_Chloride_ion_Cd.json](<solver/topology_Cd$+2_+_Cd$+0_+_Chloride_ion_Cd.json>)
- [verdict.json](<verdict.json>)
