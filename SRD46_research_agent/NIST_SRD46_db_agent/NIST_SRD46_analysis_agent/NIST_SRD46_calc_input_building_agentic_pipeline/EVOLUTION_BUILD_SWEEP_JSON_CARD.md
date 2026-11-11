# Calculation-card construction through LC3

LC3 builds a solver-ready `calc_input_card.json` from the validated LC2 thermodynamic card and LC1 system catalog. Each stage records its own decisions and artifacts while extending the calculation card.

| Stage | Responsibility | Principal artifacts |
|---|---|---|
| LC3_1 | Select method and sweep degrees of freedom | Method decision, report and calculation card |
| LC3_2 | Declare initial conditions and model settings | Initial-condition card, values, brief and variable catalog |
| LC3_3 | Construct and validate constraint algebra | Constraint specification, payload, expanded bindings and snapshot |
| LC3_4 | Declare axis bounds, sample counts and refinement | Sweep axes, refinement settings and report |
| Orchestrator | Assemble the accepted stage outputs | Final calculation card and stage summary |

## Inputs and model choices

The LC2 card supplies the realized species and thermodynamics. The system catalog supplies chemical identities. Catalog normalization reconciles those identities with the report before compilation. Variable names come from the authoritative catalog rather than guessed spellings.

LC3_2 selects activity, solids, redox and ionic-strength modes. LC3_3 inherits those settings and constructs compatible constraints. Species values recorded only as initial-condition context are not solver warm starts or soft priors. Exact species pins require explicit opt-in and native compilation; unsupported expressions cannot be treated as enforced conditions.

## Validation and final card

The constraint-card syntax is parsed as data. Front-end validation checks names, expressions and degrees of freedom. The native compiler then checks whether those constraints are supported by the actual thermodynamic system. Passing syntax checks alone does not establish a runnable calculation.

The final card declares the method, system catalog, constraints, axes and refinement. Every required axis has explicit increasing bounds and `n_points >= 2`; missing axes do not fall back to default grids. Refinement is `{"mode":"none"}` or `{"mode":"boundary","factor":R,"n_layers":L}` with `R >= 2` and `L >= 1`.

A validated card is passed through `load_calc_input` and `run_calculation`. Use saved cards from the intended run as complete examples. See the [LC3 guide](LC3_solver_para_card_building/README.md) and [numerical API contract](../NIST_SRD46_core_numcalc_pipeline/API_AND_SETTINGS.md).
