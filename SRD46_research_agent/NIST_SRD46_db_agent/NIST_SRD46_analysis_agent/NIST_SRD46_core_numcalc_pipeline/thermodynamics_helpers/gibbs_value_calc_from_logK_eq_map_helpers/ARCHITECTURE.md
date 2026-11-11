# gibbs_value_calc_from_logK_eq_map_helpers/ — Architecture

> **μ° network computation, canonical reference states, and micro-valence analysis.**

## Overview

This package computes the complete thermodynamic free-energy network from an
equilibrium-constant map (JSON input card). It transforms `logK` values into
standard chemical potentials (μ°) under both free-component and canonical
reference frames, detects metal valence groups, extracts redox couples, and
computes per-atom oxidation states for organic ligands.

## Directory Layout

```
gibbs_value_calc_from_logK_eq_map_helpers/
├── free_energy_network_calc_helper.py     ← μ° computation, 10 dataclasses, FreeEnergyReport
├── canonical_standard_state_rulebook.py   ← strict canonical ref-state rules (RULE 1–5, EC-3–4)
├── micro_valence_calculator.py            ← RDKit atom oxidation-state assignment
└── __init__.py
```

---

## Module: `free_energy_network_calc_helper.py`

Central module computing standard chemical potentials for every species from the equilibrium network.

### Dataclasses (10)

| Class | Key Fields | Purpose |
|---|---|---|
| `SpeciesEnergy` | `species_id`, `original_id`, `label`, `stoich`, `charge`, `phase`, `log_beta`, `app_log_beta`, `mu0_free`, `mu0_canonical`, `include`, `additional_notes` | μ° for one species |
| `ReactionEnergy` | `eq_id`, `label`, `species_id`, `original_sp_id`, `log_beta`, `delta_G0`, `delta_G0_can`, `include`, `additional_notes` | ΔG° for one cumulative formation reaction |
| `ComponentMeta` | `internal_id`, `name`, `comp_type`, `charge`, `total`, `db_source`, `db_id`, `smiles`, `inchi`, `canonical_HOL` | Metadata for one component (metal/ligand) |
| `EquilibriumMeta` | `equation_str`, `log_K`, `constant_type`, `T_source_C`, `I_source_M`, `db_source`, `db_id`, `include`, `metal_system`, `ligand_system`, `additional_notes` | Raw equilibrium metadata from input card |
| `SolventMeta` | `internal_id`, `name`, `formula`, `db_id`, `self_dissociation`, `dissociation_species`, `dissociation_reaction`, `pK`, `K_log10` | Solvent metadata (water + self-dissociation) |
| `ValenceGroupEntry` | `internal_id`, `name`, `charge`, `is_reference` | One metal in a valence-alignment group |
| `ValenceGroup` | `element`, `entries`, `reference_id`, `n_valences` | Same-element metals grouped by oxidation state |
| `RedoxCouple` | `couple_id`, `element`, `oxidized_id/name`, `reduced_id/name`, `n_electrons`, `E0_V_SHE`, `logK`, `delta_G0_kJ`, `half_reaction`, `source` | Half-reaction linking two oxidation states |
| `LigandMicroValence` | `ligand_id`, `ligand_name`, `smiles`, `atom_os_summary`, `dynamic_atoms` | Per-atom oxidation-state summary for an organic ligand |
| `FreeEnergyReport` | (see below) | **Central data container** for the complete free-energy analysis |

### `FreeEnergyReport` — Central Data Container

| Field Category | Fields |
|---|---|
| **Temperature** | `temperature_K`, `temperature_C`, `RT`, `factor`, `Kw_log` |
| **Species & Reactions** | `species: List[SpeciesEnergy]`, `reactions: List[ReactionEnergy]` |
| **Canonical** | `canonical_info: str`, `rulebook: CanonicalRuleBook` |
| **Components** | `metal_ids`, `metal_names`, `ligand_ids`, `ligand_names`, `total_metals`, `total_ligands` |
| **Ionic** | `ionic_strength`, `ionic_mode`, `metal_charges`, `ligand_charges` |
| **Consistency** | `consistency_ok: bool`, `inconsistencies: List[str]` |
| **Metadata** | `component_meta`, `equilibrium_meta`, `excluded_species`, `solvents`, `notes` |
| **Pourbaix extensions** | `valence_groups`, `redox_couples`, `ligand_micro_valences` |

### Public Functions

| Function | Signature | Purpose |
|---|---|---|
| `compute_free_energy_network` | `(source, *, temperature_K=298.15) → FreeEnergyReport` | **Main entry point.** JSON → parse → canonical rulebook → μ° for every species → Davies corrections → valence groups → redox couples → micro-valences → consistency checks |
| `update_report_ionic_strength` | `(report, new_I) → None` | **In-place** recalculation of `app_log_beta` for all species at a new ionic strength (called by Gibbs solver's auto-I loop) |
| `mu_eff_at_pH` | `(report, pH, *, reference="free") → List[Tuple]` | Effective μ° at a given pH: `μ°_eff = μ° + r × 2.303RT × pH` |
| `format_report` | `(report, *, include_pH=None) → str` | Human-readable text report of the full network |

### Internal Functions

| Function | Purpose |
|---|---|
| `_build_stoich(sp)` | Build stoich dict from parsed `Species` object |
| `_stoich_str(stoich)` | Compact display string for stoich dict |
| `_make_comp_id(stoich, charge, phase)` | Generate component-based species ID (e.g. `M1.L1.OH.z-3`) |
| `_extract_component_meta(raw, parsed)` | Extract `ComponentMeta` list from raw JSON |
| `_extract_equilibrium_meta(raw)` | Extract `EquilibriumMeta` list from raw JSON |
| `_element_from_name(metal_name)` | Extract element symbol from ion name (`"Fe3+"` → `"Fe"`) |
| `_reference_sort_key(charge)` | Sort key for selecting reference oxidation state (closest to 0) |
| `_detect_valence_groups(component_meta)` | Group real metals by element, pick reference oxidation state |
| `_extract_redox_couples(raw, component_meta, factor)` | Extract explicit redox half-reactions from input JSON |
| `_compute_ligand_micro_valences(component_meta)` | Compute per-atom OS summaries for organic ligands via RDKit |

### Module Constants

| Constant | Value | Purpose |
|---|---|---|
| `R_kJ` | `8.314e-3` | Gas constant in kJ/(mol·K) |
| `LN10` | `math.log(10)` | Natural log of 10 |
| `_F_C_MOL` | `96485.3329` | Faraday constant (C/mol) |
| `_ELEMENT_RE` | regex | For extracting element symbol from ion names |

### Reference State Conventions

- **Metals / H⁺** → μ° = 0 (free aquo ion)
- **Ligands** → canonical HₓL form → μ° = 0 (shift via RULE 4)
- **OH⁻** → derived from Kw: μ°(OH⁻) = 2.303RT × |Kw|
- **Species IDs** → component-based dot-notation with charge suffixes (e.g. `M1.L1(2).H(-1).z-3`)

---

## Module: `canonical_standard_state_rulebook.py`

Resolves canonical chemical potential reference states for ligands.

### Dataclasses

| Class | Key Fields | Purpose |
|---|---|---|
| `CanonicalRef` | `ligand_idx`, `ligand_name`, `canonical_H`, `resolved_H`, `log_beta_HxL`, `mu_shift_kJ`, `strategy`, `warning` | Canonical reference state for one ligand |
| `CanonicalRuleBook` | `refs: Dict[int, CanonicalRef]`, `temperature_K`, `factor`, `notes` | All resolved canonical references |

### Rules

| Rule | Description |
|---|---|
| **RULE 1** | Metal reference: μ°(Mᵢ) = 0 for free aquo ion |
| **RULE 2** | Proton reference: μ°(H⁺) = 0 |
| **RULE 3** | Hydroxide derived: μ°(OH⁻) = 2.303RT × |Kw| |
| **RULE 4** | Ligand canonical reference (HₓL form): shift = 2.303RT × logβ(HₓLⱼ) |
| **RULE 5** | μ°_canon = μ°_free + Σⱼ qⱼ × shift(Lⱼ) |
| **Missing HₓL** | Hard error: the exact declared canonical protonation state must be present and resolvable |
| **EC-3** | Hyperprotonation beyond canonical (expected, not error) |
| **EC-4** | Multi-metal species (canonical shift depends only on ligand stoichiometry) |

### Public Functions

| Function | Purpose |
|---|---|
| `build_canonical_references(*, canonical_H_map, ligand_name_to_idx, parsed_species, parsed_equilibria, temperature_K)` | Build the rulebook from the exact declared HₓL state; missing states raise instead of changing the reference frame |
| `compute_canonical_mu(mu0_free, stoich, rulebook)` | Apply RULE 5: `μ°_canon = μ°_free + Σⱼ qⱼ × shift(Lⱼ)` |
| `check_protonation_consistency(parsed_species, parsed_equilibria, rulebook)` | Validate protonation ladder monotonicity; distinguish real violations from EC-3 hyperprotonation |

---

## Module: `micro_valence_calculator.py`

RDKit-based per-atom oxidation-state assignment for organic ligands using electronegativity-partitioned bonding electrons.

### Public Functions

| Function | Signature | Returns | Purpose |
|---|---|---|---|
| `compute_atom_oxidation_states` | `(smiles: str) → Optional[List[Tuple]]` | `[(atom_idx, element, OS), …]` or `None` | Assign oxidation states to every heavy atom |
| `summarise_oxidation_states` | `(smiles: str) → Optional[Tuple[Dict, List]]` | `(os_by_element, dynamic_atoms)` or `None` | Per-element OS summary + list of redox-active atoms |

### Module Constants

| Constant | Purpose |
|---|---|
| `_HAS_RDKIT` | Whether RDKit is available (graceful degradation) |
| `_EN` | Comprehensive Pauling electronegativity table (75+ elements) |
| `_DYNAMIC_CANDIDATES` | Elements considered potentially redox-active: `{C, N, S, P, Se, As}` |

### Algorithm

1. Parse SMILES → RDKit `Mol` (with explicit Hs)
2. For each bond: assign both bonding electrons to the more electronegative atom (equal EN → split)
3. Oxidation state = (group valence electrons) − (assigned electron count)
4. Dynamic atoms = those with >1 distinct OS across the molecule, in `_DYNAMIC_CANDIDATES`

---

## Dependencies

| Import | Source |
|---|---|
| `CanonicalRuleBook`, `build_canonical_references`, `compute_canonical_mu`, `check_protonation_consistency` | `canonical_standard_state_rulebook` (used by `free_energy_network_calc_helper`) |
| `compute_atom_oxidation_states`, `summarise_oxidation_states` | `micro_valence_calculator` (used by `free_energy_network_calc_helper`) |
| `Species`, `Equilibrium`, `Kw_LOG` | `obsolete_fix_import_within)_NIST_SRD46_core_calc_tools.speciation_dataclasses` (lazy import) |
| `compute_all_apparent_logK`, `davies_log_gamma` | `obsolete_fix_import_within)_NIST_SRD46_core_calc_tools.solution_activity_models` |
| `parse_speciation_json` | `obsolete_fix_import_within)_NIST_SRD46_core_calc_tools.speciation_io_modules` |
| `rdkit.Chem` | External, optional |
