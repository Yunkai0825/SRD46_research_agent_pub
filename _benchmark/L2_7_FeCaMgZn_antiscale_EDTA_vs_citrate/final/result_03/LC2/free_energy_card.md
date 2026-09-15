# Free Energy Analysis Card

**System**: H, Ca / EDTA, Hydroxide ion
**Metals**: [Ca]2+
**Ligands**: [EDTA]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Ca$+2 | Metal component: [Ca]2+ |
| Ca$+0 | Metal component from Atlas: Ca(s) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [EDTA] |
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
| L1 | [EDTA] | -4 | Not defined | [[H]4[L1]] | NIST SRD-46 | ligand_6277 | O=C(O)CN(CCN(CC(=O)O)CC(=O)O)CC(=O)O |

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
| L1 | [EDTA] | O=C(O)CN(CCN(CC(=O)O)CC(=O)O)CC(=O)O | C | [-1, -1, -1, -1, -1, -1, 3, 3, 3, 3] | true |
| L1 | [EDTA] | O=C(O)CN(CCN(CC(=O)O)CC(=O)O)CC(=O)O | N | [-3, -3] | false |
| L1 | [EDTA] | O=C(O)CN(CCN(CC(=O)O)CC(=O)O)CC(=O)O | O | [-2, -2, -2, -2, -2, -2, -2, -2] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Ca$+2 | [Ca]2+ | metal | [Ca]2+(aq) | +0.0000 | R1 | Ca | +2 | true |
| Ca$+0 | Ca(s) | metal | Ca(s)(aq/s) | +553.0411 | RULE 1 | Ca | +0 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [EDTA] | ligand_canonical | [[H]4[L1]] | +0.0000 | R4 | *** | -4 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [EDTA] | [L1] -> [[H]4[L1]] | 4 | 4 | +20.9200 | +119.4049 | exact |  |

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
| *** + [EDTA] | 25.0 | 1 | *** | 6 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Ca]2+ + [EDTA] | 25.0 | 0~0.1 | 4938 | 4 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]6[L1]].[z+2] | [[H]6[L1]].[z+2] | [H6EDTA]2+ | +2 | aqueous | +19.5200 | -111.4141 | +7.9908 | +7.9908 | [[H]6[L1]]:+1 | SRD-46 | true | *** |
| [[H]5[L1]].[z+1] | [[H]5[L1]].[z+1] | [H5EDTA]+ | +1 | aqueous | +19.5200 | -111.4141 | +7.9908 | +7.9908 | [[H]5[L1]]:+1 | SRD-46 | true | *** |
| [[H]4[L1]].[z+0] | [[H]4[L1]].[z+0] | [H4EDTA] | +0 | aqueous | +20.9200 | -119.4049 | +0.0000 | +0.0000 | [[H]4[L1]]:+1 | SRD-46 | true | *** |
| [[H]3[L1]].[z-1] | [[H]3[L1]].[z-1] | [H3EDTA]- | -1 | aqueous | +18.9000 | -107.8754 | +11.5295 | +11.5295 | [[H]3[L1]]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z-2] | [[H]2[L1]].[z-2] | [H2EDTA]2- | -2 | aqueous | +16.3800 | -93.4920 | +25.9129 | +25.9129 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z-3] | [[H][L1]].[z-3] | [HEDTA]3- | -3 | aqueous | +10.1900 | -58.1614 | +61.2435 | +61.2435 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-4] | [L1].[z-4] | [EDTA] | -4 | aqueous | +0.0000 | -0.0000 | +119.4049 | +119.4049 | [L1]:+1 | SRD-46 | true | *** |
| Ca$+2.z+2 | Atlas | Ca2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ca$+2:+1 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1] Atlas: Ca2+ |
| [Ca$+2].[z+2] | [M1].[z+2] | [Ca]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ca$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Ca$+2:1] *** |
| [Ca$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Ca(OH)]+ | +1 | aqueous | -13.0400 | +74.4283 | +74.4283 | +74.4283 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Ca$+2].[[H][L1]].[z-1] | [M1].[[H][L1]].[z-1] | [Ca(EDTA)H]- | -1 | aqueous | +13.7500 | -78.4808 | +40.9242 | +40.9242 | [Ca$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Ca$+2].[L1].[z-2] | [M1].[L1].[z-2] | [Ca(EDTA)]2- | -2 | aqueous | +10.6500 | -60.7869 | +58.6180 | +58.6180 | [Ca$+2]:+1, [L1]:+1 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Ca$+2].[OH]2.[z+0]_(s) | [M1].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | +0 | dissolution | -22.8100 | +130.1925 | +130.1925 | +130.1925 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ca$+2:1 H:-2] *** |
| Ca$+2.OH2.z+0(s) | Atlas | Ca(OH)2 | +0 | dissolution | -22.8930 | +130.6663 | +130.6663 | +130.6663 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: Ca(OH)2 |
| Ca$+2.OH2.z+0(s) | Atlas | CaO | +0 | dissolution | -32.5985 | +186.0625 | +186.0625 | +186.0625 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: CaO |
| Ca$+2.OH4.z+0(s) | Atlas | CaO2 | +0 | dissolution | -75.1811 | +429.1110 | +429.1110 | +429.1110 | Ca$+2:+1 H:-4 | Atlas | false | Atlas: CaO2 |
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
