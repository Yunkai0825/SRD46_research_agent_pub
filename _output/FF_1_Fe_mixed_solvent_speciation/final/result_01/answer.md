## Doability
Doable — every requested non-water ligand is present in the final calculation card.

## Result
The solver pipeline completed with estimation status `ok` and 5 materialized query-estimated equilibrium entries.

## Estimation search completeness (authoritative)
- Search status: `complete`
- Reference-only reason: `none`
- Parser failures: 0
- Scope-limit omissions: 0
The enabled estimation search completed for every required scope.

## Modeling coverage (authoritative)
- Coverage status: `complete`
- Requested non-water ligands: DMF
- Modeled non-water ligands in the final card: DMF
- Omitted requested ligands: none
- Final calculation card: `LC3/calc_input_card.json`

All requested non-water ligands are present in the final card.

## Query-estimated stability constants (published supporting data)
These are session-local `SRD46 query estimated values`, not measured reference SRD46 entries.
| Pair | beta definition | log10 K | uncertainty (log10) | T (C) | I (mol/L) |
|---|---:|---:|---:|---:|---:|
| Fe^[3+] / N,N-Dimethylformamide (DMF) | beta_def_812 | 0.8 | 0.5 | 25.0 | 0.1 |
| Fe^[2+] / N,N-Dimethylformamide (DMF) | beta_def_812 | 1.0 | 0.5 | 25.0 | 0.1 |
| Fe^[2+] / N,N-Dimethylformamide (DMF) | beta_def_840 | 1.5 | 0.6 | 25.0 | 0.1 |
| Fe^[2+] / N,N-Dimethylformamide (DMF) | beta_def_872 | 1.8 | 0.7 | 25.0 | 0.1 |
| Fe^[2+] / N,N-Dimethylformamide (DMF) | beta_def_894 | 2.1 | 0.8 | 25.0 | 0.1 |

## Topology summary (authoritative)
The complete topology CSV data contain 7 regions across 1 map(s).

Topology file: `solver/topo_csv_Fe_+_DMF_Fe/topo_regions.csv` (7 regions)

| ID | Species | Measure |
|---:|---|---:|
| 0 | Fe | 5.3278906 |
| 1 | Fe3O4 (anh.) | 2.26875 |
| 2 | [(Fe2O3)0.5(s,alpha)] | 13.929258 |
| 3 | Fe$+2.L1(4).z+2 | 6.2419531 |
| 4 | Fe3O4 (anh.) | 3.90625e-05 |
| 5 | Fe$+6.OH8.z-2 | 6.7570313 |
| 6 | Fe$+3.L1.z+3 | 0.47507813 |

## Analysis limits
The table above is the deterministic full-topology summary. It does not add mechanistic claims beyond the modeled card and solver outputs; inspect the cited artifacts for detailed fields.

## Final deliverables

- [LC1/estimated_equilibrium_map.json](<LC1/estimated_equilibrium_map.json>)
- [LC1/lc1_2_eqmap_card.json](<LC1/lc1_2_eqmap_card.json>)
- [LC1/lc1_sweep_input.json](<LC1/lc1_sweep_input.json>)
- [LC1/status.json](<LC1/status.json>)
- [LC1/working_equilibrium_map.json](<LC1/working_equilibrium_map.json>)
- [LC2/free_energy_card.md](<LC2/free_energy_card.md>)
- [LC2/status.json](<LC2/status.json>)
- [LC2/thermodynamic_reference_constants.md](<LC2/thermodynamic_reference_constants.md>)
- [LC3/calc_input_card.json](<LC3/calc_input_card.json>)
- [LC3/status.json](<LC3/status.json>)
- [LD/answer.md](<LD/answer.md>)
- [LD/verdict.json](<LD/verdict.json>)
- [solver/pourbaix_Fe_+_DMF_Fe.png](<solver/pourbaix_Fe_+_DMF_Fe.png>)
- [solver/pourbaix_map_Fe_+_DMF_Fe.csv](<solver/pourbaix_map_Fe_+_DMF_Fe.csv>)
- [solver/speciation_full_Fe_+_DMF.csv](<solver/speciation_full_Fe_+_DMF.csv>)
- [solver/topo_csv_Fe_+_DMF_Fe/topo_features_0d.csv](<solver/topo_csv_Fe_+_DMF_Fe/topo_features_0d.csv>)
- [solver/topo_csv_Fe_+_DMF_Fe/topo_features_1d.csv](<solver/topo_csv_Fe_+_DMF_Fe/topo_features_1d.csv>)
- [solver/topo_csv_Fe_+_DMF_Fe/topo_metadata.json](<solver/topo_csv_Fe_+_DMF_Fe/topo_metadata.json>)
- [solver/topo_csv_Fe_+_DMF_Fe/topo_regions.csv](<solver/topo_csv_Fe_+_DMF_Fe/topo_regions.csv>)
- [solver/topology_Fe_+_DMF_Fe.json](<solver/topology_Fe_+_DMF_Fe.json>)
- [solver/topology_Fe_+_DMF_Fe_verdict.json](<solver/topology_Fe_+_DMF_Fe_verdict.json>)
- [solver/topology_Fe_+_DMF_Fe_verdict.md](<solver/topology_Fe_+_DMF_Fe_verdict.md>)
- [verdict.json](<verdict.json>)
