# Free Energy Analysis Card

**System**: H, Fe, Cu / Citric acid, Chloride, Hydroxide ion
**Metals**: [Fe]3+, [Fe]2+, [Cu]2+, [Cu]+
**Ligands**: [Citric acid], [Chloride ion]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Cu$+1 | Metal component: [Cu]+ |
| Cu$+0 | Metal component from Atlas: Cu(s) |
| Cu$+2 | Metal component: [Cu]2+ |
| Fe$+2 | Metal component: [Fe]2+ |
| Fe$+0 | Metal component from Atlas: Fe(s) |
| Fe$+3 | Metal component: [Fe]3+ |
| Fe$+6 | Metal component from Atlas: Fe(+6) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Citric acid] |
| L2 | Ligand component: [Chloride ion] |
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
- Collision disambiguation: `{1}`, `{2}` (log_beta descending)

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
| Cu$+1 | [Cu]+ | +1 | Not defined | NIST SRD-46 | metal_42 |
| Cu$+0 | Cu(s) | +0 | 0 | Pourbaix Atlas |  |
| Cu$+2 | [Cu]2+ | +2 | Not defined | NIST SRD-46 | metal_41 |
| Fe$+2 | [Fe]2+ | +2 | Not defined | NIST SRD-46 | metal_62 |
| Fe$+0 | Fe(s) | +0 | 0 | Pourbaix Atlas |  |
| Fe$+3 | [Fe]3+ | +3 | Not defined | NIST SRD-46 | metal_61 |
| Fe$+6 | Fe(+6) | +6 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Citric acid] | -3 | Not defined | [[H]3[L1]] | NIST SRD-46 | ligand_9058 | O=C(O)CC(O)(CC(=O)O)C(=O)O |
| L2 | [Chloride ion] | -1 | Not defined | [[L2]] | NIST SRD-46 | ligand_10163 | *** |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Cu | Cu$+1 | [Cu]+ | +1 | true | 3 |
| Cu | Cu$+0 | Cu(s) | +0 | false | 3 |
| Cu | Cu$+2 | [Cu]2+ | +2 | false | 3 |
| Fe | Fe$+2 | [Fe]2+ | +2 | true | 4 |
| Fe | Fe$+0 | Fe(s) | +0 | false | 4 |
| Fe | Fe$+3 | [Fe]3+ | +3 | false | 4 |
| Fe | Fe$+6 | Fe(+6) | +6 | false | 4 |

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
| Cu$+1 | [Cu]+ | metal | [Cu]+(aq) | +0.0000 | R1 | Cu | +1 | true |
| Cu$+0 | Cu(s) | metal | Cu(s)(aq/s) | -50.2080 | RULE 1 | Cu | +0 | false |
| Cu$+2 | [Cu]2+ | metal | [Cu]2+(aq) | +14.7695 | R1 | Cu | +2 | false |
| Fe$+2 | [Fe]2+ | metal | [Fe]2+(aq) | +0.0000 | R1 | Fe | +2 | true |
| Fe$+0 | Fe(s) | metal | Fe(s)(aq/s) | +84.9352 | RULE 1 | Fe | +0 | false |
| Fe$+3 | [Fe]3+ | metal | [Fe]3+(aq) | +74.3497 | R1 | Fe | +3 | false |
| Fe$+6 | Fe(+6) | metal | Fe(+6)(aq/s) | +566.4090 | RULE 1 | Fe | +6 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Citric acid] | ligand_canonical | [[H]3[L1]] | +0.0000 | R4 | *** | -3 | *** |
| L2 | [Chloride ion] | ligand_canonical | [[L2]] | +0.0000 | R4 | *** | -1 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Citric acid] | [L1] -> [[H]3[L1]] | 3 | 3 | +12.9000 | +73.6292 | exact |  |
| L2 | [Chloride ion] | [L2] -> [[L2]] | 0 | 0 | +0.0000 | +0.0000 | exact | R4a: canonical_H=0; shift≡0 |

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
| [Fe]3+ + [Citric acid] | 20.0~25.0 | 0~0.1 | 22182 | 12 |
| [Fe]3+ + [Chloride ion] | 25.0 | 0~0.1 | 29854 | 2 |
| [Fe]2+ + [Citric acid] | 25.0~37.0 | 0~0.15 | 22169 | 10 |
| [Fe]2+ + [Chloride ion] | 25.0 | 0 | 29830 | 1 |
| [Cu]2+ + [Citric acid] | 25.0 | 0~0.1 | 22180 | 11 |
| [Cu]2+ + [Chloride ion] | 25.0 | 0 | 29839 | 1 |
| [Cu]+ + [Chloride ion] | 25.0 | 0~5 | 29869 | 6 |

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
| [L2].[z-1] | [L2].[z-1] | [Chloride ion] | -1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L2]:+1 | SRD-46 | true | *** |
| Cu$+1.z+1 | Atlas | Cu+ | +1 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Cu$+1:+1 | Atlas | false | [DUPLICATE GROUP: Cu$+1:1] Atlas: Cu+ |
| [Cu$+1].[z+1] | [M4].[z+1] | [Cu]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Cu$+1]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1] *** |
| [Cu$+1]2.[L2]4.[z-2] | [M4]2.[L2]4.[z-2] | [Cu2(Chlo)4]2- | -2 | aqueous | +13.0000 | -74.2000 | -74.2000 | -74.2000 | [Cu$+1]:+2, [L2]:+4 | SRD-46 | true | *** |
| [Cu$+1].[L2]2.[z-1] | [M4].[L2]2.[z-1] | [Cu(Chlo)2]- | -1 | aqueous | +6.0600 | -34.5886 | -34.5886 | -34.5886 | [Cu$+1]:+1, [L2]:+2 | SRD-46 | true | *** |
| [Cu$+1].[L2]3.[z-2] | [M4].[L2]3.[z-2] | [Cu(Chlo)3]2- | -2 | aqueous | +5.3900 | -30.7645 | -30.7645 | -30.7645 | [Cu$+1]:+1, [L2]:+3 | SRD-46 | true | *** |
| [Cu$+1].[L2].[z+0] | [M4].[L2].[z+0] | [Cu(Chlo)] | +0 | aqueous | +3.1000 | -17.6938 | -17.6938 | -17.6938 | [Cu$+1]:+1, [L2]:+1 | SRD-46 | true | *** |
| Cu$+2.z+2 | Atlas | Cu2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +14.7695 | Cu$+2:+1 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1] Atlas: Cu2+ |
| [Cu$+2].[z+2] | [M3].[z+2] | [Cu]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +14.7695 | [Cu$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1] *** |
| [Cu$+2].[OH].[z+1] | [M3].[OH].[z+1] | [Cu(OH)]+ | +1 | aqueous | -7.9000 | +45.0908 | +45.0908 | +59.8603 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Cu$+2]2.[OH]2.[z+2] | [M3]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | +2 | aqueous | -11.2000 | +63.9261 | +63.9261 | +93.4651 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true | *** |
| [Cu$+2].[OH]2.[z+0] | [M3].[OH]2.[z+0] | [Cu(OH)2] | +0 | aqueous | -16.2000 | +92.4646 | +92.4646 | +107.2341 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Cu$+2.OH3.z-1 | Atlas | [HCuO2]- | -1 | aqueous | -26.7048 | +152.4231 | +152.4231 | +167.1926 | Cu$+2:+1 H:-3 | Atlas | true | Atlas: [HCuO2]- |
| [Cu$+2]3.[OH]4.[z+2] | [M3]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | +2 | aqueous | -22.5000 | +128.4231 | +128.4231 | +172.7316 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true | *** |
| Cu$+2.OH4.z-2 | Atlas | [CuO2]2- | -2 | aqueous | -39.8410 | +227.4004 | +227.4004 | +242.1699 | Cu$+2:+1 H:-4 | Atlas | true | Atlas: [CuO2]2- |
| [Cu$+2].[[H][L1]].[z+0] | [M3].[[H][L1]].[z+0] | [Cu(Citr)H] | +0 | aqueous | +9.2600 | -52.8532 | +20.7760 | +35.5455 | [Cu$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Cu$+2]2.[L1]2.[z-2] | [M3]2.[L1]2.[z-2] | [Cu2(Citr)2]2- | -2 | aqueous | +14.5000 | -82.7615 | +64.4969 | +94.0359 | [Cu$+2]:+2, [L1]:+2 | SRD-46 | true | *** |
| [Cu$+2]2.[[H]-1[L1]].[z+0] | [M3]2.[[H]-1[L1]].[z+0] | [Cu2(Citr)(OH)] | +0 | aqueous | +4.8600 | -27.7394 | +45.8898 | +75.4288 | [Cu$+2]:+2, [[H]-1[L1]]:+1 | SRD-46 | true | *** |
| [Cu$+2]2.[[H]-1[L1]].[L1].[z-3] | [M3]2.[[H]-1[L1]].[L1].[z-3] | [Cu2(Citr)2(OH)]3- | -3 | aqueous | +11.2000 | -63.9261 | +83.3323 | +112.8713 | [Cu$+2]:+2, [[H]-1[L1]]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Cu$+2]2.[[H]-1[L1]]2.[z-4] | [M3]2.[[H]-1[L1]]2.[z-4] | [Cu2(Citr)2(OH)2]4- | -4 | aqueous | +6.3400 | -36.1868 | +111.0717 | +140.6107 | [Cu$+2]:+2, [[H]-1[L1]]:+2 | SRD-46 | true | *** |
| [Cu$+2].[L2].[z+1] | [M3].[L2].[z+1] | [Cu(Chlo)]+ | +1 | aqueous | +0.2000 | -1.1415 | -1.1415 | +13.6280 | [Cu$+2]:+1, [L2]:+1 | SRD-46 | true | *** |
| Fe$+2.z+2 | Atlas | Fe2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Fe$+2:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1] Atlas: Fe2+ |
| [Fe$+2].[z+2] | [M2].[z+2] | [Fe]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1] *** |
| [Fe$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Fe(OH)]+ | +1 | aqueous | -9.8000 | +55.9354 | +55.9354 | +55.9354 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Fe$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Fe(OH)2] | +0 | aqueous | -35.5000 | +202.6231 | +202.6231 | +202.6231 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Fe$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Fe(OH)3]- | -1 | aqueous | -29.0000 | +165.5231 | +165.5231 | +165.5231 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-3] *** |
| Fe$+2.OH3.z-1 | Atlas | [HFeO2]- | -1 | aqueous | -31.5598 | +180.1338 | +180.1338 | +180.1338 | Fe$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-3] Atlas: [HFeO2]- |
| [Fe$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Fe(OH)4]2- | -2 | aqueous | -46.0000 | +262.5538 | +262.5538 | +262.5538 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+2].[[H]2[L1]].[z+1] | [M2].[[H]2[L1]].[z+1] | [Fe(Citr)H2]+ | +1 | aqueous | +11.1000 | -63.3554 | +10.2738 | +10.2738 | [Fe$+2]:+1, [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [Fe$+2].[[H][L1]].[z+0] | [M2].[[H][L1]].[z+0] | [Fe(Citr)H] | +0 | aqueous | +8.5500 | -48.8008 | +24.8285 | +24.8285 | [Fe$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Fe$+2].[L1]2.[H].[z-3] | [M2].[L1]2.[H].[z-3] | [Fe(Citr)2H]3- | -3 | aqueous | +11.7400 | -67.0083 | +80.2501 | +80.2501 | [Fe$+2]:+1, [L1]:+2, [H]:+1 | SRD-46 | true | *** |
| [Fe$+2].[L1].[z-1] | [M2].[L1].[z-1] | [Fe(Citr)]- | -1 | aqueous | +4.4000 | -25.1138 | +48.5154 | +48.5154 | [Fe$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Fe$+2]2.[[H]-1[L1]]2.[z-4] | [M2]2.[[H]-1[L1]]2.[z-4] | [Fe2(Citr)2(OH)2]4- | -4 | aqueous | -5.4000 | +30.8215 | +178.0800 | +178.0800 | [Fe$+2]:+2, [[H]-1[L1]]:+2 | SRD-46 | true | *** |
| [Fe$+2].[L2].[z+1] | [M2].[L2].[z+1] | [Fe(Chlo)]+ | +1 | aqueous | -0.2000 | +1.1415 | +1.1415 | +1.1415 | [Fe$+2]:+1, [L2]:+1 | SRD-46 | true | *** |
| Fe$+3.z+3 | Atlas | Fe3+ | +3 | aqueous | -0.0000 | +0.0000 | +0.0000 | +74.3497 | Fe$+3:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1] Atlas: Fe3+ |
| [Fe$+3].[z+3] | [M1].[z+3] | [Fe]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +74.3497 | [Fe$+3]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1] *** |
| Fe$+3.OH.z+2 | Atlas | [FeOH]2+ | +2 | aqueous | -2.4264 | +13.8490 | +13.8490 | +88.1987 | Fe$+3:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-1] Atlas: [FeOH]2+ |
| [Fe$+3].[OH].[z+2] | [M1].[OH].[z+2] | [Fe(OH)]2+ | +2 | aqueous | -2.7300 | +15.5820 | +15.5820 | +89.9317 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3]2.[OH]2.[z+4] | [M1]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | +4 | aqueous | -2.8600 | +16.3240 | +16.3240 | +165.0234 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3].[OH]2.[z+1] | [M1].[OH]2.[z+1] | [Fe(OH)2]+ | +1 | aqueous | -4.6000 | +26.2554 | +26.2554 | +100.6051 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-2] *** |
| Fe$+3.OH2.z+1 | Atlas | [Fe(OH)2]+ | +1 | aqueous | -7.1179 | +40.6266 | +40.6266 | +114.9763 | Fe$+3:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-2] Atlas: [Fe(OH)2]+ |
| [Fe$+3]3.[OH]4.[z+5] | [M1]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | +5 | aqueous | -6.3000 | +35.9585 | +35.9585 | +259.0076 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[OH]4.[z-1] | [M1].[OH]4.[z-1] | [Fe(OH)4]- | -1 | aqueous | -21.6000 | +123.2861 | +123.2861 | +197.6358 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[[H][L1]].[z+1] | [M1].[[H][L1]].[z+1] | [Fe(Citr)H]+ | +1 | aqueous | +12.3500 | -70.4900 | +3.1392 | +77.4889 | [Fe$+3]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Fe$+3].[L1].[z+0] | [M1].[L1].[z+0] | [Fe(Citr)] | +0 | aqueous | +11.1900 | -63.8691 | +9.7602 | +84.1099 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Fe$+3].[OH].[L1].[z-1] | [M1].[OH].[L1].[z-1] | [Fe(Citr)(OH)]- | -1 | aqueous | +8.4900 | -48.4583 | +25.1709 | +99.5206 | [Fe$+3]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Fe$+3]2.[OH]2.[L1]2.[z-2] | [M1]2.[OH]2.[L1]2.[z-2] | [Fe2(Citr)2(OH)2]2- | -2 | aqueous | +21.2000 | -121.0031 | +26.2554 | +174.9548 | [Fe$+3]:+2, [OH]:+2, [L1]:+2 | SRD-46 | true | *** |
| [Fe$+3].[L2]2.[z+1] | [M1].[L2]2.[z+1] | [Fe(Chlo)2]+ | +1 | aqueous | +2.1300 | -12.1574 | -12.1574 | +62.1923 | [Fe$+3]:+1, [L2]:+2 | SRD-46 | true | *** |
| [Fe$+3].[L2].[z+2] | [M1].[L2].[z+2] | [Fe(Chlo)]2+ | +2 | aqueous | +0.7800 | -4.4520 | -4.4520 | +69.8977 | [Fe$+3]:+1, [L2]:+1 | SRD-46 | true | *** |
| Fe$+6.OH8.z-2 | Atlas | [FeO4]2- | -2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +566.4090 | Fe$+6:+1 H:-8 | Atlas | false | Atlas: [FeO4]2- |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Cu$+1].[OH].[z+0]_(s) | [M4].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | -3.9954 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1 H:-1] *** |
| Cu$+1(2).OH2.z+0(s) | Atlas | Cu2O | +0 | dissolution | -0.5205 | +2.9706 | +2.9706 | +2.9706 | Cu$+1:+2 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+1:1 H:-1] Atlas: Cu2O |
| [Cu$+1].[L2].[z+0]_(s) | [M4].[L2].[z+0]_(s) | [Cu(Chloride ion)](s) | +0 | dissolution | +6.7300 | -38.4128 | -38.4128 | -38.4128 | [Cu$+1]:+1, [L2]:+1 | SRD-46 | true | *** |
| [Cu$+2].[OH]2.[[z+0(s)[1]]] | [M3].[OH]2.[[z+0(s)[1]]] | [CuO](s) | +0 | dissolution | -7.6500 | +43.6638 | +43.6638 | +58.4333 | [Cu$+2]:+1, [H]:-2 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] *** |
| Cu$+2.OH2.z+0(s) | Atlas | CuO | +0 | dissolution | -7.8876 | +45.0199 | +45.0199 | +59.7894 | Cu$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: CuO |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [M3].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | +0 | dissolution | -8.6800 | +49.5428 | +49.5428 | +64.3123 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] *** |
| Cu$+2.OH2.z+0(s) | Atlas | Cu(OH)2 | +0 | dissolution | -9.1997 | +52.5092 | +52.5092 | +67.2787 | Cu$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: Cu(OH)2 |
| Cu$+0.z+0(s) | Atlas | Cu | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | -50.2080 | Cu$+0:+1 | Atlas | true | Atlas: Cu |
| Fe$+2.OH2.z+0(s) | Atlas | Fe(OH)2 (hydr.) | +0 | dissolution | -13.2754 | +75.7722 | +75.7722 | +75.7722 | Fe$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-2] Atlas: Fe(OH)2 (hydr.) |
| [Fe$+2].[OH]2.[z+0]_(s) | [M2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | +0 | dissolution | -13.5700 | +77.4534 | +77.4534 | +77.4534 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-2] *** |
| Fe$+2.Fe$+3(2).OH8.z+0(s) | Atlas | Fe3O4 (anh.) | +0 | dissolution | -7.1252 | +40.6684 | +40.6684 | +189.3678 | Fe$+2:+1 Fe$+3:+2 H:-8 | Atlas | false | Atlas: Fe3O4 (anh.) |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [M1].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | +70.3543 | [Fe$+3]:+1, [H]:-3 | SRD-46 | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [M1].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | +0 | dissolution | -0.5000 | +2.8538 | +2.8538 | +77.2035 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [M1].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | +0 | dissolution | -3.2000 | +18.2646 | +18.2646 | +92.6143 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| Fe$+3.OH3.z+0(s) | Atlas | Fe(OH)3 (hydr.) | +0 | dissolution | -4.8381 | +27.6144 | +27.6144 | +101.9641 | Fe$+3:+1 H:-3 | Atlas | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe(OH)3 (hydr.) |
| Fe$+3(2).OH6.z+0(s) | Atlas | Fe2O3 (anh.) | +0 | dissolution | +1.4441 | -8.2425 | -8.2425 | +140.4569 | Fe$+3:+2 H:-6 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe2O3 (anh.) |
| Fe$+0.z+0(s) | Atlas | Fe | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +84.9352 | Fe$+0:+1 | Atlas | true | Atlas: Fe |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
