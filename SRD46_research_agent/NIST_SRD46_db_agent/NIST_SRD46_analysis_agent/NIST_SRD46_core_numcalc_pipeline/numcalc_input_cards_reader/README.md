# Calculation-card input readers

This package resolves the two inputs consumed by `SRD46_numcalculator_api.run_calculation`.

| Reader | Input | Output |
|---|---|---|
| `card_md_input_reader.py` | Saved thermodynamic card, network specification or report | `FreeEnergyReport` |
| `calc_json_input_reader.py` | Calculation-card JSON file or dictionary | Validated `CalcInput` |

The public exports include `resolve_card_source`, `load_calc_input`, `dump_calc_input`, `CalcInput`, `SweepAxis`, `IonicStrengthSpec`, `GridRefineSpec` and `SUPPORTED_SWEEP_METHODS`. `load_calc_input` accepts a dictionary or file path; the top-level calculation API also accepts an already parsed `CalcInput` directly.

## Thermodynamic cards

Directory resolution checks `free_energy_card_numcalc.md`, `free_energy_card_enriched.md`, `free_energy_card.md`, then `free_energy_card_with_include.md`, followed by a Markdown fallback. Specify a file explicitly when several cards exist. Dictionaries and JSON/network specifications pass through `compute_free_energy_network`.

## Calculation cards

Load the saved LC3 card belonging to the selected thermodynamic card. A complete card declares `sweep_method`, `sweep_axes`, `system_catalog`, `grid_refine`, and either `constraint_spec` with `constraint_settings` or `sweep_constraints`.

Conditions, analytical totals and model choices must be explicit in the constraint representation. Required axes declare a name, finite increasing bounds and `n_points >= 2`. There is no implicit axis range or grid size. Refinement is explicitly disabled with `{"mode":"none"}` or configured with boundary `factor >= 2` and `n_layers >= 1`.

The native reader and compiler validate dimensions, identities, totals and physical/model compatibility. `CalcInput.validate()` reports issues and `load_calc_input` raises on invalid required inputs. Card resolution leaves the source unchanged; the calculation API applies the resolved settings to its working report.

See the [API reference](../API_AND_SETTINGS.md) and [reader implementation](calc_json_input_reader.py) for details.
