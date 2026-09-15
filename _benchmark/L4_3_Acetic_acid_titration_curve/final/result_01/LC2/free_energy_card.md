# Free Energy Analysis Card

**System**: H, Na / Acetic acid, Hydroxide ion
**Metals**: [Na]+
**Ligands**: [Acetic acid]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Na$+1 | Metal component: [Na]+ |
| Na$+0 | Metal component from Atlas: Na(s) |
| Na$+2 | Metal component from Atlas: Na(+2) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Acetic acid] |
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
| Na$+1 | [Na]+ | +1 | Not defined | NIST SRD-46 | metal_106 |
| Na$+0 | Na(s) | +0 | 0 | Pourbaix Atlas |  |
| Na$+2 | Na(+2) | +2 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Acetic acid] | -1 | Not defined | [[H][L1]] | NIST SRD-46 | ligand_8465 | CC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Na | Na$+1 | [Na]+ | +1 | true | 3 |
| Na | Na$+0 | Na(s) | +0 | false | 3 |
| Na | Na$+2 | Na(+2) | +2 | false | 3 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [Acetic acid] | CC(=O)O | C | [-3, 3] | true |
| L1 | [Acetic acid] | CC(=O)O | O | [-2, -2] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Na$+1 | [Na]+ | metal | [Na]+(aq) | +0.0000 | R1 | Na | +1 | true |
| Na$+0 | Na(s) | metal | Na(s)(aq/s) | +261.8724 | RULE 1 | Na | +0 | false |
| Na$+2 | Na(+2) | metal | Na(+2)(aq/s) | +568.0115 | RULE 1 | Na | +2 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Acetic acid] | ligand_canonical | [[H][L1]] | +0.0000 | R4 | *** | -1 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Acetic acid] | [L1] -> [[H][L1]] | 1 | 1 | +4.5600 | +26.0271 | exact |  |

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
| *** + [Acetic acid] | 25.0 | 0.1 | *** | 1 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Na]+ + [Acetic acid] | 25.0 | 0.1 | 17043 | 2 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z+0] | [[H][L1]].[z+0] | [HAcetic acid] | +0 | aqueous | +4.5600 | -26.0271 | +0.0000 | +0.0000 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-1] | [L1].[z-1] | [Acetic acid] | -1 | aqueous | +0.0000 | -0.0000 | +26.0271 | +26.0271 | [L1]:+1 | SRD-46 | true | *** |
| Na$+1.z+1 | Atlas | Na+ | +1 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Na$+1:+1 | Atlas | false | [DUPLICATE GROUP: Na$+1:1] Atlas: Na+ |
| [Na$+1].[z+1] | [M1].[z+1] | [Na]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Na$+1]:+1 | SRD-46 | true | [DUPLICATE GROUP: Na$+1:1] *** |
| [Na$+1].[OH].[z+0] | [M1].[OH].[z+0] | [Na(OH)] | +0 | aqueous | -14.1000 | +80.4785 | +80.4785 | +80.4785 | [Na$+1]:+1, [OH]:+1 | SRD-46 | false | *** |
| [Na$+1].[L1].[z+0] | [M1].[L1].[z+0] | [Na(Acet)] | +0 | aqueous | -0.2700 | +1.5411 | +27.5682 | +27.5682 | [Na$+1]:+1, [L1]:+1 | SRD-46 | false | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Na$+1.OH.z+0(s) | Atlas | NaOH | +0 | dissolution | -21.3895 | +122.0849 | +122.0849 | +122.0849 | Na$+1:+1 H:-1 | Atlas | true | Atlas: NaOH |
| Na$+1(2).OH2.z+0(s) | Atlas | Na2O | +0 | dissolution | -67.3434 | +384.3757 | +384.3757 | +384.3757 | Na$+1:+2 H:-2 | Atlas | false | Atlas: Na2O |
| Na$+2(2).OH4.z+0(s) | Atlas | Na2O2 | +0 | dissolution | +99.5167 | -568.0115 | -568.0115 | +568.0115 | Na$+2:+2 H:-4 | Atlas | false | Atlas: Na2O2 |
| Na$+0.z+0(s) | Atlas | Na | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +261.8724 | Na$+0:+1 | Atlas | false | Atlas: Na |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
