# `thermodynamics_helpers/`

Pure thermodynamic primitives shared by every layer of the pipeline.
No solver, no I/O, no plotting — just the math and the reference data
that drive μ°, ΔG°, activity coefficients, and the `FreeEnergyReport`
container.

## Folder map

```
thermodynamics_helpers/
├── thermodynamic_constants.py            ← R, F, NERNST_FACTOR, Kw, TEMPERATURE_*
│
├── electrolyte_activity_models/          § activity coefficients
│   ├── activity_model.py                   compute_ionic_strength, recompute_activity_at_I
│   ├── solution_models_activity_coeff.py   Davies / Debye–Hückel / ideal
│   └── ARCHITECTURE.md
│
└── gibbs_value_calc_from_logK_eq_map_helpers/  § FreeEnergyReport + canonical μ°
    ├── free_energy_network_calc_helper.py    ★ FreeEnergyReport dataclass +
    │                                           compute_free_energy_network()
    ├── canonical_standard_state_rulebook.py  canonical μ° / reference-state rules
    ├── micro_valence_calculator.py           optional RDKit valence analysis
    └── ARCHITECTURE.md
```

## Public surface

| Symbol                                | From                                                                                       |
|---------------------------------------|--------------------------------------------------------------------------------------------|
| `FreeEnergyReport`                    | `gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper`                |
| `compute_free_energy_network(spec,…)` | same                                                                                       |
| `compute_ionic_strength(...)`         | `electrolyte_activity_models.activity_model`                                               |
| `recompute_activity_at_I(...)`        | same                                                                                       |
| `R_CONST`, `F_CONST`, `NERNST_FACTOR`, `Kw_LOG`, `LN10`, `TEMPERATURE_C/K` | `thermodynamic_constants`                                       |

Solver code reaches the activity helpers **only** through
`solvers_and_topology/support_TD_helpers/activity_model_entry_point.py`
and `TD_constants_entry_point.py` — never via direct imports.

## I/O contract

- Input: equilibrium-network spec (dict / JSON) or in-memory reactions.
- Output: `FreeEnergyReport` — central container of species, μ°, logβ,
  stoichiometry, components (metals/ligands), valence groups, redox
  couples, total concentrations, ionic strength, temperature.

Detailed math + dataclass layouts:
- [gibbs_value_calc_from_logK_eq_map_helpers/ARCHITECTURE.md](gibbs_value_calc_from_logK_eq_map_helpers/ARCHITECTURE.md)
- [electrolyte_activity_models/ARCHITECTURE.md](electrolyte_activity_models/ARCHITECTURE.md)
