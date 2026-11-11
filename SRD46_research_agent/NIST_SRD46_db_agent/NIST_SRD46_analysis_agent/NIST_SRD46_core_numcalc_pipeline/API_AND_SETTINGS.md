# Numerical calculation API and settings

The public API consumes a thermodynamic card and a calculation card. The calculation card must state the physical conditions, totals, model choices and sweep definition. See [ARCHITECTURE.md](ARCHITECTURE.md) for the execution path.

## Public entry point

```python
run_calculation(card_source, calc_input, *, output_dir=None, debug=False)
```

The function is defined in [SRD46_numcalculator_api.py](SRD46_numcalculator_api.py). `card_source` accepts a `FreeEnergyReport`, an equilibrium-network dictionary, a card file or a directory. `calc_input` accepts a `CalcInput`, dictionary or JSON file path. `output_dir` overrides the calculation card's output location. `debug` controls diagnostic logging.

`load_calc_input(source)` parses a dictionary or JSON file into `CalcInput`; it does not accept an existing `CalcInput`. `run_calculation` accepts that object directly. `dump_calc_input` serializes a parsed card. These input helpers are in [numcalc_input_cards_reader](numcalc_input_cards_reader/README.md).

## Thermodynamic card resolution

[card_md_input_reader.py](numcalc_input_cards_reader/card_md_input_reader.py) resolves the card. A `FreeEnergyReport` is used directly; dictionaries and non-Markdown specification files pass through `compute_free_energy_network`. Markdown cards are parsed as saved thermodynamic reports. Directory lookup checks these names in order, then a Markdown fallback:

1. `free_energy_card_numcalc.md`
2. `free_energy_card_enriched.md`
3. `free_energy_card.md`
4. `free_energy_card_with_include.md`

Use the specific saved card path when several cards are available. The API resolves requested conditions and totals, checks chemical scope, compiles constraints and dispatches the selected sweep.

## Calculation card requirements

[calc_json_input_reader.py](numcalc_input_cards_reader/calc_json_input_reader.py) is the executable input contract. Cards declare:

- `sweep_method`: `pH_sweep`, `pourbaix_sweep`, `freeform_sweep` or `titration_sweep`.
- `sweep_axes`: explicit axes, each with `name`, finite increasing `min`/`max`, and `n_points` of at least two. `range: [min, max]` is accepted; `n` does not replace `n_points`.
- `system_catalog.chemical_system`: declared metals and/or ligands with their identities.
- `grid_refine`: `{"mode":"none"}`, or `{"mode":"boundary","factor":R,"n_layers":L}` with integer `R >= 2` and `L >= 1`.
- Either `constraint_spec` with `constraint_settings`, or `sweep_constraints`.

Physical conditions and analytical totals are resolved from the constraint representation. Top-level temperature, concentration or boolean mirrors do not replace missing declarations there. Required axes have no implicit range or point-count fallback. Temperature must be a finite constant; fixed ionic strength requires an explicit value. The reader and compiler check catalog identities, totals, model compatibility and degrees of freedom before numerical solving.

| Model setting | Accepted choices |
|---|---|
| `activity_model` | `ideal`, `davies` |
| `solids` | `include`, `exclude` |
| `redox_mode` | `axis`, `fixed`, `freeform`, `solve`, `excluded` |
| `ionic_strength_mode` | `fixed`, `auto`, `none` |

Species pins require `constraint_settings.species_pins="allowed"` and compatible native constraints. The compiler checks requested species against the thermodynamic report. Catalog entries are not numerical warm-start guesses. Redox exclusion prohibits a potential binding/axis and treats declared oxidation states as independent components; it is not a calculation at zero potential.

## Sweep handlers

| Method | Inputs and behavior |
|---|---|
| `pH_sweep` | Explicit pH axis; a redox-enabled pH-only calculation requires fixed `E_V`. Produces fraction and concentration profiles. |
| `pourbaix_sweep` | Declared potential/pH axes and optional water-activity dimension; shared N-dimensional grid and topology pipeline. |
| `freeform_sweep` | Explicit scalar or composition axes and compiled constraint bindings. |
| `titration_sweep` | Added-volume dilution model through the freeform handler. Requires explicit `volume_initial_mL`, `titrant_conc` and `fixed_pH`; these have no numerical defaults. |

The titration handler evaluates speciation at a declared fixed pH. It does not implement a free-pH acid/base titration curve. Nernst post-calculation tools have their own [package](../NIST_SRD46_post_calc_tools/README.md).

## Numerical budgets and neighbour states

`POINT_TIMEOUT_S = 10.0` is declared in `solvers_and_topology/solver_settings.py`, `solvers_and_topology/nd_grid/settings.py` and `sweep_pipelines/pourbaix_sweep/pourbaix_sweep_settings.py`. It is the normal phase-search budget per point, not a whole-sweep timeout.

A compatible donor carries aqueous concentrations, active solids and precipitated amounts. `SolidManager` gives donor preparation its own bounded deadline and starts the normal search deadline afterwards. Recovery paths can apply their configured multipliers. The implementation is in [solid_manager.py](solvers_and_topology/numerical_solvers/solid_manager.py); solver and grid settings contain the remaining numerical tolerances and recovery limits.

## Results and files

`run_calculation` preserves the handler result and includes `report`, `sweep_method`, `calc_input` and `output_dir`. `output_paths` identifies generated files. Use these returned paths rather than constructing filenames from chemical names.

- pH results include `built`, `grid`, `topology` and `speciation_curve`.
- Pourbaix results include `built`, `grid` and `all_boundaries`.
- Freeform and titration results include `built`, `grid`, `per_element` and `topologies`.

CSV, JSON and plot exports retain convergence information. Unconverged samples remain marked as such; speciation plots shade unconverged intervals grey. Output stems may be compacted to keep paths within platform limits. Solver results and generated interpretations are separate artifacts.
