# Free Energy Analysis Card

**System**: H, Zn / EDTA, Hydroxide ion
**Metals**: [Zn]2+
**Ligands**: [EDTA]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Zn$+2 | Metal component: [Zn]2+ |
| Zn$+0 | Metal component from Atlas: Zn(s) |
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
| Zn$+2 | [Zn]2+ | +2 | Not defined | NIST SRD-46 | metal_208 |
| Zn$+0 | Zn(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [EDTA] | -4 | Not defined | [[H]4[L1]] | NIST SRD-46 | ligand_6277 | O=C(O)CN(CCN(CC(=O)O)CC(=O)O)CC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Zn | Zn$+2 | [Zn]2+ | +2 | true | 2 |
| Zn | Zn$+0 | Zn(s) | +0 | false | 2 |

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
| Zn$+2 | [Zn]2+ | metal | [Zn]2+(aq) | +0.0000 | R1 | Zn | +2 | true |
| Zn$+0 | Zn(s) | metal | Zn(s)(aq/s) | +147.2099 | RULE 1 | Zn | +0 | false |
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
| [Zn]2+ + [EDTA] | 25.0 | 0~1 | 5057 | 15 |

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
| Zn$+2.z+2 | Atlas | Zn2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Zn$+2:+1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1] Atlas: Zn2+ |
| [Zn$+2].[z+2] | [M1].[z+2] | [Zn]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Zn$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1] *** |
| [Zn$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Zn(OH)]+ | +1 | aqueous | -9.3000 | +53.0815 | +53.0815 | +53.0815 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-1] *** |
| Zn$+2.OH.z+1 | Atlas | [ZnOH]+ | +1 | aqueous | -16.0346 | +91.5208 | +91.5208 | +91.5208 | Zn$+2:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-1] Atlas: [ZnOH]+ |
| [Zn$+2].[OH]2.[z+0] | [M1].[OH]2.[z+0] | [Zn(OH)2] | +0 | aqueous | -15.8000 | +90.1815 | +90.1815 | +90.1815 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Zn$+2].[OH]3.[z-1] | [M1].[OH]3.[z-1] | [Zn(OH)3]- | -1 | aqueous | -28.1000 | +160.3861 | +160.3861 | +160.3861 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-3] *** |
| Zn$+2.OH3.z-1 | Atlas | [HZnO2]- | -1 | aqueous | -28.7823 | +164.2806 | +164.2806 | +164.2806 | Zn$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-3] Atlas: [HZnO2]- |
| Zn$+2.OH4.z-2 | Atlas | [ZnO2]2- | -2 | aqueous | -33.4005 | +190.6398 | +190.6398 | +190.6398 | Zn$+2:+1 H:-4 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-4] Atlas: [ZnO2]2- |
| [Zn$+2].[OH]4.[z-2] | [M1].[OH]4.[z-2] | [Zn(OH)4]2- | -2 | aqueous | -40.5000 | +231.1615 | +231.1615 | +231.1615 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-4] *** |
| [Zn$+2].[[H]2[L1]].[z+0] | [M1].[[H]2[L1]].[z+0] | [Zn(EDTA)H2] | +0 | aqueous | +18.3000 | -104.4508 | +14.9542 | +14.9542 | [Zn$+2]:+1, [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [Zn$+2].[[H][L1]].[z-1] | [M1].[[H][L1]].[z-1] | [Zn(EDTA)H]- | -1 | aqueous | +19.5000 | -111.3000 | +8.1049 | +8.1049 | [Zn$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Zn$+2].[L1].[z-2] | [M1].[L1].[z-2] | [Zn(EDTA)]2- | -2 | aqueous | +16.5000 | -94.1769 | +25.2280 | +25.2280 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Zn$+2].[OH].[L1].[z-3] | [M1].[OH].[L1].[z-3] | [Zn(EDTA)(OH)]3- | -3 | aqueous | +28.1000 | -160.3861 | -40.9812 | -40.9812 | [Zn$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (inactive) | +0 | dissolution | -9.6132 | +54.8690 | +54.8690 | +54.8690 | Zn$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (inactive) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (active) | +0 | dissolution | -10.5368 | +60.1408 | +60.1408 | +60.1408 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (active) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (alpha) | +0 | dissolution | -10.7230 | +61.2036 | +61.2036 | +61.2036 | Zn$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (alpha) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (epsilon) | +0 | dissolution | -10.9502 | +62.5006 | +62.5006 | +62.5006 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (epsilon) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (gamma) | +0 | dissolution | -11.1797 | +63.8102 | +63.8102 | +63.8102 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (gamma) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (beta) | +0 | dissolution | -11.3101 | +64.5549 | +64.5549 | +64.5549 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (beta) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO | +0 | dissolution | -11.5191 | +65.7474 | +65.7474 | +65.7474 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO |
| [Zn$+2].[OH]2.[[z+0(s)[1]]] | [M1].[OH]2.[[z+0(s)[1]]] | [ZnO](s) | +0 | dissolution | -12.0400 | +68.7206 | +68.7206 | +68.7206 | [Zn$+2]:+1, [H]:-2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[2]]] | [M1].[OH]2.[[z+0(s)[2]]] | [Zn(OH)2(s,epsilon)] | +0 | dissolution | -12.2300 | +69.8051 | +69.8051 | +69.8051 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (amorphous) | +0 | dissolution | -12.2492 | +69.9146 | +69.9146 | +69.9146 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (amorphous) |
| [Zn$+2].[OH]2.[[z+0(s)[3]]] | [M1].[OH]2.[[z+0(s)[3]]] | [Zn(OH)2(s,gamma)] | +0 | dissolution | -12.4400 | +71.0037 | +71.0037 | +71.0037 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[4]]] | [M1].[OH]2.[[z+0(s)[4]]] | [Zn(OH)2(s,beta1)] | +0 | dissolution | -12.4600 | +71.1178 | +71.1178 | +71.1178 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[5]]] | [M1].[OH]2.[[z+0(s)[5]]] | [Zn(OH)2(s,beta2)] | +0 | dissolution | -12.5000 | +71.3461 | +71.3461 | +71.3461 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[6]]] | [M1].[OH]2.[[z+0(s)[6]]] | [Zn(OH)2(s,delta)] | +0 | dissolution | -12.5500 | +71.6315 | +71.6315 | +71.6315 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[7]]] | [M1].[OH]2.[[z+0(s)[7]]] | [Zn(OH)2(s,am)] | +0 | dissolution | -13.1800 | +75.2274 | +75.2274 | +75.2274 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+0.z+0(s) | Atlas | Zn | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +147.2099 | Zn$+0:+1 | Atlas | false | Atlas: Zn |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
