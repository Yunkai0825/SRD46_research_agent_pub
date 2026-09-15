# Free Energy Analysis Card

**System**: H, Ca / Citric acid, Hydroxide ion
**Metals**: [Ca]2+
**Ligands**: [Citric acid]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Ca$+2 | Metal component: [Ca]2+ |
| Ca$+0 | Metal component from Atlas: Ca(s) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Citric acid] |
| H | Net proton count (H⁺); negative values denote hydroxide (OH⁻) contributions |
| μ°_free | Standard chemical potential (kJ/mol) with free-component reference (metal aquo ion, free ligand) |
| μ°_canon | Standard chemical potential (kJ/mol) with canonical HₓL ligand reference |
| μ°_eff | Effective chemical potential at a given pH: μ°_canon + r × 2.303RT × pH |
| stoich | Stoichiometry dictionary mapping component keys to integer coefficients |
| log_beta | Cumulative formation constant log₁₀(β) from free components |
| (s) | Solid/dissolution phase |

### Species ID Convention

Species IDs are dot-separated bracket-tokenized component keys:

- Each component wrapped in brackets: `[Cu$+2]`, `[L1]`, `[H]`, `[OH]`
- Count > 1 after closing bracket: `[Cu$+2]2`, `[L1]3`, `[OH]2`
- Negative H rendered as OH: `[OH]`, `[OH]2`, `[OH]3`
- Charge in brackets: `[z+2]`, `[z-1]`, `[z+0]`
- Solids: `_(s)` suffix
- Collision disambiguation: `[1]`, `[2]` (log_beta descending); cross-card SRD-SRD duplicates: `.dup1`, `.dup2` id suffix + label `@<T>C` frame tag + `[srd_<set> r/n frame|data]` note (full trace in srd_srd_duplicates.json)

### Reference State Rules

| Rule | Description |
|------|-------------|
| R1 | Metal reference: μ°(Mᵢ) = 0 for free aquo ion |
| R2 | Proton reference: μ°(H⁺) = 0 |
| R3 | Hydroxide: μ°(OH⁻) = 2.303RT × \|Kw\| (derived from water) |
| R4 | Ligand canonical: μ°(HₓLⱼ) = 0 where x = declared canonical_H |
| R5 | μ°_canon = μ°_free + Σⱼ qⱼ × 2.303RT × logβ(HₓLⱼ) |

## 2. Components

### 2.1 Solvent

#### S0: Water (db_id: solvent_1)

| property | value |
|----------|-------|
| name | Water |
| formula | H2O |
| self_dissociation | true |
| dissociation_reaction | H2O ⇌ H⁺ + OH⁻ |
| pK | 14.00 |
| K_log10 | -14.00 |

| internal_id | name | charge | stoich_coeff | db_id |
|-------------|------|--------|-------------|-------|
| M0 | [H]+ | +1 | +1 | metal_68 |
| L0 | [OH]- | -1 | +1 | ligand_10076 |

### 2.2 Metals

| internal_id | name | charge | total_M | db_source | db_id |
|-------------|------|--------|---------|-----------|-------|
| Ca$+2 | [Ca]2+ | +2 | Not defined | NIST SRD-46 | metal_25 |
| Ca$+0 | Ca(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Citric acid] | -3 | Not defined | [[H]3[L1]] | NIST SRD-46 | ligand_9058 | O=C(O)CC(O)(CC(=O)O)C(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Ca | Ca$+2 | [Ca]2+ | +2 | true | 2 |
| Ca | Ca$+0 | Ca(s) | +0 | false | 2 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [Citric acid] | O=C(O)CC(O)(CC(=O)O)C(=O)O | C | [-2, -2, 1, 3, 3, 3] | true |
| L1 | [Citric acid] | O=C(O)CC(O)(CC(=O)O)C(=O)O | O | [-2, -2, -2, -2, -2, -2, -2] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Ca$+2 | [Ca]2+ | metal | [Ca]2+(aq) | +0.0000 | R1 | Ca | +2 | true |
| Ca$+0 | Ca(s) | metal | Ca(s)(aq/s) | +553.0411 | RULE 1 | Ca | +0 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Citric acid] | ligand_canonical | [[H]3[L1]] | +0.0000 | R4 | *** | -3 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Citric acid] | [L1] -> [[H]3[L1]] | 3 | 3 | +12.9000 | +73.6292 | exact |  |

## 4. Settings

### 4.1 Common Settings

| parameter | value | unit |
|-----------|-------|------|
| ionic_strength | Not defined | mol/L |
| ionic_strength_mode | Not defined | - |
| Kw_log10 | -14.00 | - |
| 2.303RT | 5.7077 | kJ/mol |
| RT | 2.478819 | kJ/mol |

### 4.2 Per Metal–Ligand Pair Conditions

| pair | T_source (°C) | I_source (mol/L) | ref_eq_net | vlm_count |
|------|---------------|------------------|------------|-----------|
| *** + [Citric acid] | 25.0 | 0.1 | *** | 3 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Ca]2+ + [Citric acid] | 25.0 | 0~0.1 | 22102 | 7 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]3[L1]].[z+0] | [[H]3[L1]].[z+0] | [H3Citric acid] | +0 | aqueous | +12.9000 | -73.6292 | +0.0000 | +0.0000 | [[H]3[L1]]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z-1] | [[H]2[L1]].[z-1] | [H2Citric acid]- | -1 | aqueous | +10.0000 | -57.0769 | +16.5523 | +16.5523 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z-2] | [[H][L1]].[z-2] | [HCitric acid]2- | -2 | aqueous | +5.6500 | -32.2485 | +41.3808 | +41.3808 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-3] | [L1].[z-3] | [Citric acid] | -3 | aqueous | +0.0000 | -0.0000 | +73.6292 | +73.6292 | [L1]:+1 | SRD-46 | true | *** |
| Ca$+2.z+2 | Atlas | Ca2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ca$+2:+1 | Atlas | true | [DUPLICATE GROUP: Ca$+2:1] Atlas: Ca2+ |
| [Ca$+2].[z+2] | [M1].[z+2] | [Ca]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ca$+2]:+1 | SRD-46 | false | [DUPLICATE GROUP: Ca$+2:1] *** |
| [Ca$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Ca(OH)]+ | +1 | aqueous | -13.0400 | +74.4283 | +74.4283 | +74.4283 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Ca$+2].[[H]2[L1]].[z+1] | [M1].[[H]2[L1]].[z+1] | [Ca(Citr)H2]+ | +1 | aqueous | +11.0000 | -62.7846 | +10.8446 | +10.8446 | [Ca$+2]:+1, [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [Ca$+2].[[H][L1]].[z+0] | [M1].[[H][L1]].[z+0] | [Ca(Citr)H] | +0 | aqueous | +7.7200 | -44.0634 | +29.5658 | +29.5658 | [Ca$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Ca$+2].[L1].[z-1] | [M1].[L1].[z-1] | [Ca(Citr)]- | -1 | aqueous | +3.4500 | -19.6915 | +53.9377 | +53.9377 | [Ca$+2]:+1, [L1]:+1 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Ca$+2].[OH]2.[z+0]_(s) | [M1].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | +0 | dissolution | -22.8100 | +130.1925 | +130.1925 | +130.1925 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] *** |
| Ca$+2.OH2.z+0(s) | Atlas | Ca(OH)2 | +0 | dissolution | -22.8930 | +130.6663 | +130.6663 | +130.6663 | Ca$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: Ca(OH)2 |
| Ca$+2.OH2.z+0(s) | Atlas | CaO | +0 | dissolution | -32.5985 | +186.0625 | +186.0625 | +186.0625 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: CaO |
| Ca$+2.OH4.z+0(s) | Atlas | CaO2 | +0 | dissolution | -75.1811 | +429.1110 | +429.1110 | +429.1110 | Ca$+2:+1 H:-4 | Atlas | false | Atlas: CaO2 |
| [Ca$+2].[[H][L1]].[z+0]_(s) | [M1].[[H][L1]].[z+0]_(s) | [CaH(Citric acid)](s) | +0 | dissolution | +11.3900 | -65.0106 | +8.6186 | +8.6186 | [Ca$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Ca$+2]3.[L1]2.[z+0]_(s) | [M1]3.[L1]2.[z+0]_(s) | [Ca3(Citric acid)2](s) | +0 | dissolution | +17.0300 | -97.2020 | +50.0565 | +50.0565 | [Ca$+2]:+3, [L1]:+2 | SRD-46 | true | *** |
| Ca$+0.z+0(s) | Atlas | Ca | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +553.0411 | Ca$+0:+1 | Atlas | false | Atlas: Ca |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
