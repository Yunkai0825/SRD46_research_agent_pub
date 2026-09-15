# Free Energy Analysis Card

**System**: H, Ni / EDTA, Hydroxide ion
**Metals**: [Ni]2+
**Ligands**: [EDTA]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Ni$+2 | Metal component: [Ni]2+ |
| Ni$+0 | Metal component from Atlas: Ni(s) |
| Ni$+3 | Metal component from Atlas: Ni(+3) |
| Ni$+4 | Metal component from Atlas: Ni(+4) |
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
| Ni$+2 | [Ni]2+ | +2 | Not defined | NIST SRD-46 | metal_112 |
| Ni$+0 | Ni(s) | +0 | 0 | Pourbaix Atlas |  |
| Ni$+3 | Ni(+3) | +3 | 0 | Pourbaix Atlas |  |
| Ni$+4 | Ni(+4) | +4 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [EDTA] | -4 | Not defined | [[H]4[L1]] | NIST SRD-46 | ligand_6277 | O=C(O)CN(CCN(CC(=O)O)CC(=O)O)CC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Ni | Ni$+2 | [Ni]2+ | +2 | true | 4 |
| Ni | Ni$+0 | Ni(s) | +0 | false | 4 |
| Ni | Ni$+3 | Ni(+3) | +3 | false | 4 |
| Ni | Ni$+4 | Ni(+4) | +4 | false | 4 |

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
| Ni$+2 | [Ni]2+ | metal | [Ni]2+(aq) | +0.0000 | R1 | Ni | +2 | true |
| Ni$+0 | Ni(s) | metal | Ni(s)(aq/s) | +45.6056 | RULE 1 | Ni | +0 | false |
| Ni$+3 | Ni(+3) | metal | Ni(+3)(aq/s) | +570.2374 | RULE 1 | Ni | +3 | false |
| Ni$+4 | Ni(+4) | metal | Ni(+4)(aq/s) | +542.0372 | RULE 1 | Ni | +4 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [EDTA] | ligand_canonical | [[H]4[L1]] | +0.0000 | R4 | *** | -4 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [EDTA] | [L1] -> [[H]4[L1]] | 4 | 4 | +20.2500 | +115.5808 | exact |  |

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
| [Ni]2+ + [EDTA] | 25.0 | 0~0.1 | 5023 | 8 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]6[L1]].[z+2] | [[H]6[L1]].[z+2] | [H6EDTA]2+ | +2 | aqueous | +18.8500 | -107.5900 | +7.9908 | +7.9908 | [[H]6[L1]]:+1 | SRD-46 | true | *** |
| [[H]5[L1]].[z+1] | [[H]5[L1]].[z+1] | [H5EDTA]+ | +1 | aqueous | +18.8500 | -107.5900 | +7.9908 | +7.9908 | [[H]5[L1]]:+1 | SRD-46 | true | *** |
| [[H]4[L1]].[z+0] | [[H]4[L1]].[z+0] | [H4EDTA] | +0 | aqueous | +20.2500 | -115.5808 | +0.0000 | +0.0000 | [[H]4[L1]]:+1 | SRD-46 | true | *** |
| [[H]3[L1]].[z-1] | [[H]3[L1]].[z-1] | [H3EDTA]- | -1 | aqueous | +18.2300 | -104.0512 | +11.5295 | +11.5295 | [[H]3[L1]]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z-2] | [[H]2[L1]].[z-2] | [H2EDTA]2- | -2 | aqueous | +15.7100 | -89.6678 | +25.9129 | +25.9129 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z-3] | [[H][L1]].[z-3] | [HEDTA]3- | -3 | aqueous | +9.5200 | -54.3372 | +61.2435 | +61.2435 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-4] | [L1].[z-4] | [EDTA] | -4 | aqueous | +0.0000 | -0.0000 | +115.5808 | +115.5808 | [L1]:+1 | SRD-46 | true | *** |
| Ni$+2.z+2 | Atlas | Ni2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ni$+2:+1 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1] Atlas: Ni2+ |
| [Ni$+2].[z+2] | [M1].[z+2] | [Ni]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ni$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1] *** |
| [Ni$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Ni(OH)]+ | +1 | aqueous | -10.4000 | +59.3600 | +59.3600 | +59.3600 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Ni$+2].[OH]2.[z+0] | [M1].[OH]2.[z+0] | [Ni(OH)2] | +0 | aqueous | -19.0000 | +108.4461 | +108.4461 | +108.4461 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Ni$+2.OH3.z-1 | Atlas | [HNiO2]- | -1 | aqueous | -29.7836 | +169.9959 | +169.9959 | +169.9959 | Ni$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-3] Atlas: [HNiO2]- |
| [Ni$+2].[OH]3.[z-1] | [M1].[OH]3.[z-1] | [Ni(OH)3]- | -1 | aqueous | -30.0000 | +171.2308 | +171.2308 | +171.2308 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1 H:-3] *** |
| [Ni$+2]4.[OH]4.[z+4] | [M1]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | +4 | aqueous | -27.7000 | +158.1031 | +158.1031 | +158.1031 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Ni$+2].[[H][L1]].[z-1] | [M1].[[H][L1]].[z-1] | [Ni(EDTA)H]- | -1 | aqueous | +21.5000 | -122.7154 | -7.1346 | -7.1346 | [Ni$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Ni$+2].[L1].[z-2] | [M1].[L1].[z-2] | [Ni(EDTA)]2- | -2 | aqueous | +18.4000 | -105.0215 | +10.5592 | +10.5592 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Ni$+2].[OH].[L1].[z-3] | [M1].[OH].[L1].[z-3] | [Ni(EDTA)(OH)]3- | -3 | aqueous | +30.3000 | -172.9431 | -57.3623 | -57.3623 | [Ni$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Ni$+2.OH2.z+0(s) | Atlas | Ni(OH)2 | +0 | dissolution | -11.7141 | +66.8603 | +66.8603 | +66.8603 | Ni$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-2] Atlas: Ni(OH)2 |
| Ni$+2.OH2.z+0(s) | Atlas | NiO | +0 | dissolution | -11.9413 | +68.1574 | +68.1574 | +68.1574 | Ni$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-2] Atlas: NiO |
| [Ni$+2].[OH]2.[z+0]_(s) | [M1].[OH]2.[z+0]_(s) | [Ni(OH)2](s) | +0 | dissolution | -12.8000 | +73.0585 | +73.0585 | +73.0585 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1 H:-2] *** |
| Ni$+2(3).OH8.z+0(s) | Atlas | Ni3O4.2H2O | +0 | dissolution | -151.0072 | +861.9040 | +861.9040 | +861.9040 | Ni$+2:+3 H:-8 | Atlas | false | Atlas: Ni3O4.2H2O |
| Ni$+3(2).OH6.z+0(s) | Atlas | Ni2O3.H2O | +0 | dissolution | +99.9067 | -570.2374 | -570.2374 | +570.2374 | Ni$+3:+2 H:-6 | Atlas | false | Atlas: Ni2O3.H2O |
| Ni$+4.OH4.z+0(s) | Atlas | NiO2.2H2O | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +542.0372 | Ni$+4:+1 H:-4 | Atlas | false | Atlas: NiO2.2H2O |
| Ni$+0.z+0(s) | Atlas | Ni | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +45.6056 | Ni$+0:+1 | Atlas | false | Atlas: Ni |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
