# Free Energy Analysis Card

**System**: 06 FeCu glycine citrate
**Metals**: [Cu]2+, [Cu]+, [Fe]3+, [Fe]2+
**Ligands**: [Glycine], [Citric acid]
**Generated**: 2026-05-05 17:41:32 UTC

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Cu$+1 | Metal component: [Cu]+ |
| Cu$-1 | Metal component from Atlas: Cu(-1) |
| Cu$+0 | Metal component from Atlas: Cu(s) |
| Cu$+2 | Metal component: [Cu]2+ |
| Fe$+2 | Metal component: [Fe]2+ |
| Fe$+0 | Metal component from Atlas: Fe(s) |
| Fe$+3 | Metal component: [Fe]3+ |
| Fe$+6 | Metal component from Atlas: Fe(+6) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Glycine] |
| L2 | Ligand component: [Citric acid] |
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
| Cu$+1 | [Cu]+ | +1 | 0.001 | NIST SRD-46 | metal_42 |
| Cu$-1 | Cu(-1) | -1 | 0 | Pourbaix Atlas |  |
| Cu$+0 | Cu(s) | +0 | 0 | Pourbaix Atlas |  |
| Cu$+2 | [Cu]2+ | +2 | 0.001 | NIST SRD-46 | metal_41 |
| Fe$+2 | [Fe]2+ | +2 | 0.001 | NIST SRD-46 | metal_62 |
| Fe$+0 | Fe(s) | +0 | 0 | Pourbaix Atlas |  |
| Fe$+3 | [Fe]3+ | +3 | 0.001 | NIST SRD-46 | metal_61 |
| Fe$+6 | Fe(+6) | +6 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Glycine] | -1 | 0.01 | [[H][L1]] | NIST SRD-46 | ligand_5760 | NCC(=O)O |
| L2 | [Citric acid] | -3 | 0.01 | [[H]3[L2]] | NIST SRD-46 | ligand_9058 | O=C(O)CC(O)(CC(=O)O)C(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Cu | Cu$+1 | [Cu]+ | +1 | true | 4 |
| Cu | Cu$-1 | Cu(-1) | -1 | false | 4 |
| Cu | Cu$+0 | Cu(s) | +0 | false | 4 |
| Cu | Cu$+2 | [Cu]2+ | +2 | false | 4 |
| Fe | Fe$+2 | [Fe]2+ | +2 | true | 4 |
| Fe | Fe$+0 | Fe(s) | +0 | false | 4 |
| Fe | Fe$+3 | [Fe]3+ | +3 | false | 4 |
| Fe | Fe$+6 | Fe(+6) | +6 | false | 4 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [Glycine] | NCC(=O)O | C | [-1, 3] | true |
| L1 | [Glycine] | NCC(=O)O | N | [-3] | false |
| L1 | [Glycine] | NCC(=O)O | O | [-2, -2] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Cu$+1 | [Cu]+ | metal | [Cu]+(aq) | +0.0000 | R1 | Cu | +1 | true |
| Cu$-1 | Cu(-1) | metal | Cu(-1)(aq/s) | -8.3680 | RULE 1 | Cu | -1 | false |
| Cu$+0 | Cu(s) | metal | Cu(s)(aq/s) | -50.2080 | RULE 1 | Cu | +0 | false |
| Cu$+2 | [Cu]2+ | metal | [Cu]2+(aq) | +14.7695 | R1 | Cu | +2 | false |
| Fe$+2 | [Fe]2+ | metal | [Fe]2+(aq) | +0.0000 | R1 | Fe | +2 | true |
| Fe$+0 | Fe(s) | metal | Fe(s)(aq/s) | +84.9352 | RULE 1 | Fe | +0 | false |
| Fe$+3 | [Fe]3+ | metal | [Fe]3+(aq) | +74.3497 | R1 | Fe | +3 | false |
| Fe$+6 | Fe(+6) | metal | Fe(+6)(aq/s) | +544.7986 | RULE 1 | Fe | +6 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Glycine] | ligand_canonical | [[H][L1]] | +0.0000 | R4 | *** | -1 | *** |
| L2 | [Citric acid] | ligand_canonical | [[H]3[L2]] | +0.0000 | R4 | *** | -3 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Glycine] | [L1] -> [[H][L1]] | 1 | 1 | +9.5700 | +54.6226 | exact |  |
| L2 | [Citric acid] | [L2] -> [[H]3[L2]] | 3 | 1 | +5.6500 | +32.2485 | ladder |  |

## 4. Settings

### 4.1 Common Settings

| parameter | value | unit |
|-----------|-------|------|
| Kw_log10 | -14.00 | - |
| 2.303RT | 5.7077 | kJ/mol |
| RT | 2.478819 | kJ/mol |

### 4.2 Per Metal–Ligand Pair Conditions

| pair | T_source (°C) | I_source (mol/L) | ref_eq_net | vlm_count |
|------|---------------|------------------|------------|-----------|
| [Cu]2+ + [Glycine] | 25.0 | 0~0.1 | 86 | 10 |
| [Cu]2+ + [Citric acid] | 25.0 | 0.1 | 22180 | 8 |
| [Cu]+ + [Glycine] | 25.0 | 0~0.1 | 100 | 2 |
| [Fe]3+ + [Glycine] | 25.0 | 0.5 | 97 | 7 |
| [Fe]3+ + [Citric acid] | 20.0~25.0 | 0~0.1 | 22182 | 12 |
| [Fe]2+ + [Glycine] | 25.0 | 0~0.1 | 63 | 7 |
| [Fe]2+ + [Citric acid] | 25.0 | 0.1 | 22168 | 2 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by μ°_canon ascending (most stable canonical state first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Fe$+3].[L2].[z+0] | [M3].[L2].[z+0] | [Fe(Citr)] | +0 | aqueous | +11.1900 | -63.8691 | -31.6206 | +42.7291 | [Fe$+3]:+1, [L2]:+1 | SRD-46 | true |  |
| [Cu$+2]2.[L2]2.[z-2] | [M1]2.[L2]2.[z-2] | [Cu2(Citr)2]2- | -2 | aqueous | +14.5000 | -82.7615 | -18.2646 | +11.2744 | [Cu$+2]:+2, [L2]:+2 | SRD-46 | true |  |
| [[H]2[L1]].[z+1] | [[H]2[L1]].[z+1] | [H2Glycine]+ | +1 | aqueous | +11.9300 | -68.0928 | -13.6414 | -13.6414 | [[H]2[L1]]:+1 | SRD-46 | true |  |
| Cu$+1.z+1 | Atlas | Cu+ | +1 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Cu$+1:+1 | Atlas | true | [DUPLICATE GROUP: Cu$+1:1] Atlas: Cu+ |
| [Cu$+1].[z+1] | [M2].[z+1] | [Cu]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Cu$+1]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1] |
| Cu$+2.z+2 | Atlas | Cu2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +14.7695 | Cu$+2:+1 | Atlas | true | [DUPLICATE GROUP: Cu$+2:1] Atlas: Cu2+ |
| [Cu$+2].[z+2] | [M1].[z+2] | [Cu]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +14.7695 | [Cu$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1] |
| Fe$+2.z+2 | Atlas | Fe2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Fe$+2:+1 | Atlas | true | [DUPLICATE GROUP: Fe$+2:1] Atlas: Fe2+ |
| [Fe$+2].[z+2] | [M4].[z+2] | [Fe]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1] |
| Fe$+3.z+3 | Atlas | Fe3+ | +3 | aqueous | -0.0000 | +0.0000 | +0.0000 | +74.3497 | Fe$+3:+1 | Atlas | true | [DUPLICATE GROUP: Fe$+3:1] Atlas: Fe3+ |
| [Fe$+3].[z+3] | [M3].[z+3] | [Fe]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +74.3497 | [Fe$+3]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1] |
| Fe$+6.OH8.z-2 | Atlas | [FeO4]2- | -2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +544.7986 | Fe$+6:+1 H:-8 | Atlas | true | Atlas: [FeO4]2- |
| [[H][L1]].[z+0] | [[H][L1]].[z+0] | [HGlycine] | +0 | aqueous | +9.5700 | -54.6226 | +0.0000 | +0.0000 | [[H][L1]]:+1 | SRD-46 | true |  |
| [[H][L1]].[z-2] | [[H][L1]].[z-2] | [HCitric acid]2- | -2 | aqueous | +5.6500 | -32.2485 | +0.0000 | +0.0000 | [[H][L2]]:+1 | SRD-46 | true |  |
| [Cu$+2]2.[[H]-1[L1]].[L2].[z-3] | [M1]2.[[H]-1[L1]].[L2].[z-3] | [Cu2(Citr)2(OH)]3- | -3 | aqueous | +11.2000 | -63.9261 | +0.5708 | +30.1098 | [Cu$+2]:+2, [[H]-1[L2]]:+1, [L2]:+1 | SRD-46 | true |  |
| [Cu$+2]2.[[H]-1[L1]].[z+0] | [M1]2.[[H]-1[L1]].[z+0] | [Cu2(Citr)(OH)] | +0 | aqueous | +4.8600 | -27.7394 | +4.5091 | +34.0481 | [Cu$+2]:+2, [[H]-1[L2]]:+1 | SRD-46 | true |  |
| [Cu$+2].[L1].[z+1] | [M1].[L1].[z+1] | [Cu(Glyc)]+ | +1 | aqueous | +8.1900 | -46.7460 | +7.8766 | +22.6461 | [Cu$+2]:+1, [L1]:+1 | SRD-46 | true |  |
| Fe$+3.OH.z+2 | Atlas | [FeOH]2+ | +2 | aqueous | -2.9468 | +16.8197 | +16.8197 | +91.1694 | Fe$+3:+1 H:-1 | Atlas | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] Atlas: [FeOH]2+ |
| [Fe$+3].[OH].[z+2] | [M3].[OH].[z+2] | [Fe(OH)]2+ | +2 | aqueous | -2.9500 | +16.8377 | +16.8377 | +91.1874 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] |
| [Fe$+3]2.[OH]2.[z+4] | [M3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | +4 | aqueous | -3.5000 | +19.9769 | +19.9769 | +168.6763 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] |
| [Cu$+2].[L1]2.[z+0] | [M1].[L1]2.[z+0] | [Cu(Glyc)2] | +0 | aqueous | +15.1000 | -86.1861 | +23.0591 | +37.8286 | [Cu$+2]:+1, [L1]:+2 | SRD-46 | true |  |
| [Cu$+2]2.[[H]-1[L1]]2.[z-4] | [M1]2.[[H]-1[L1]]2.[z-4] | [Cu2(Citr)2(OH)2]4- | -4 | aqueous | +6.3400 | -36.1868 | +28.3102 | +57.8492 | [Cu$+2]:+2, [[H]-1[L2]]:+2 | SRD-46 | true |  |
| [L2].[z-3] | [L2].[z-3] | [Citric acid] | -3 | aqueous | +0.0000 | -0.0000 | +32.2485 | +32.2485 | [L2]:+1 | SRD-46 | true |  |
| [Fe$+3].[OH]2.[z+1] | [M3].[OH]2.[z+1] | [Fe(OH)2]+ | +1 | aqueous | -6.2000 | +35.3877 | +35.3877 | +109.7374 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-2] |
| [Fe$+3]3.[OH]4.[z+5] | [M3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | +5 | aqueous | -6.3000 | +35.9585 | +35.9585 | +259.0076 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true |  |
| Fe$+3.OH2.z+1 | Atlas | [Fe(OH)2]+ | +1 | aqueous | -7.1179 | +40.6266 | +40.6266 | +114.9763 | Fe$+3:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Fe$+3:1 H:-2] Atlas: [Fe(OH)2]+ |
| [Cu$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Cu(OH)]+ | +1 | aqueous | -7.9000 | +45.0908 | +45.0908 | +59.8603 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true |  |
| [Cu$+1].[L1]2.[z-1] | [M2].[L1]2.[z-1] | [Cu(Glyc)2]- | -1 | aqueous | +10.1000 | -57.6477 | +51.5975 | +51.5975 | [Cu$+1]:+1, [L1]:+2 | SRD-46 | true |  |
| [L1].[z-1] | [L1].[z-1] | [Glycine] | -1 | aqueous | +0.0000 | -0.0000 | +54.6226 | +54.6226 | [L1]:+1 | SRD-46 | true |  |
| [Fe$+2].[OH].[z+1] | [M4].[OH].[z+1] | [Fe(OH)]+ | +1 | aqueous | -9.8000 | +55.9354 | +55.9354 | +55.9354 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true |  |
| [Fe$+2].[L2].[z-1] | [M4].[L2].[z-1] | [Fe(Citr)]- | -1 | aqueous | +4.8000 | -27.3969 | +4.8516 | +4.8516 | [Fe$+2]:+1, [L2]:+1 | SRD-46 (vlm_157620 sign corrected) | true | Manual sign fix: SRD46 vlm_157620 stores -4.80 but neighbouring vlm_157619=+4.40, vlm_157621=+4.56, vlm_157622=+4.70 confirm true value is +4.80. |
| [Cu$+2]2.[OH]2.[z+2] | [M1]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | +2 | aqueous | -11.2000 | +63.9261 | +63.9261 | +93.4651 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true |  |
| [Fe$+2].[L1].[z+1] | [M4].[L1].[z+1] | [Fe(Glyc)]+ | +1 | aqueous | -4.1300 | +23.5728 | +78.1954 | +78.1954 | [Fe$+2]:+1, [L1]:+1 | SRD-46 | true |  |
| [Cu$+2].[OH]2.[z+0] | [M1].[OH]2.[z+0] | [Cu(OH)2] | +0 | aqueous | -16.2000 | +92.4646 | +92.4646 | +107.2341 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |  |
| [Fe$+3].[L1].[z+2] | [M3].[L1].[z+2] | [Fe(Glyc)]2+ | +2 | aqueous | -8.5700 | +48.9149 | +103.3663 | +177.7160 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true |  |
| [Fe$+3].[OH]4.[z-1] | [M3].[OH]4.[z-1] | [Fe(OH)4]- | -1 | aqueous | -21.6000 | +123.2861 | +123.2861 | +197.6358 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true |  |
| [Cu$+2]3.[OH]4.[z+2] | [M1]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | +2 | aqueous | -22.5000 | +128.4231 | +128.4231 | +172.7316 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true |  |
| Cu$+2.OH3.z-1 | Atlas | [HCuO2]- | -1 | aqueous | -26.7048 | +152.4231 | +152.4231 | +167.1926 | Cu$+2:+1 H:-3 | Atlas | true | Atlas: [HCuO2]- |
| [Fe$+2].[L1]2.[z+0] | [M4].[L1]2.[z+0] | [Fe(Glyc)2] | +0 | aqueous | -7.6500 | +43.6638 | +152.9091 | +152.9091 | [Fe$+2]:+1, [L1]:+2 | SRD-46 | true |  |
| [Fe$+2].[OH]3.[z-1] | [M4].[OH]3.[z-1] | [Fe(OH)3]- | -1 | aqueous | -29.0000 | +165.5231 | +165.5231 | +165.5231 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-3] |
| Fe$+2.OH3.z-1 | Atlas | [HFeO2]- | -1 | aqueous | -31.5598 | +180.1338 | +180.1338 | +180.1338 | Fe$+2:+1 H:-3 | Atlas | true | [DUPLICATE GROUP: Fe$+2:1 H:-3] Atlas: [HFeO2]- |
| [Fe$+2].[OH]2.[z+0] | [M4].[OH]2.[z+0] | [Fe(OH)2] | +0 | aqueous | -35.5000 | +202.6231 | +202.6231 | +202.6231 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |  |
| Cu$+2.OH4.z-2 | Atlas | [CuO2]2- | -2 | aqueous | -39.8410 | +227.4004 | +227.4004 | +242.1699 | Cu$+2:+1 H:-4 | Atlas | true | Atlas: [CuO2]2- |
| [Fe$+2].[OH]4.[z-2] | [M4].[OH]4.[z-2] | [Fe(OH)4]2- | -2 | aqueous | -46.0000 | +262.5538 | +262.5538 | +262.5538 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true |  |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Fe$+3(2).OH6.z+0(s) | Atlas | Fe2O3 | +0 | dissolution | +1.4441 | -8.2425 | -8.2425 | +140.4569 | Fe$+3:+2 H:-6 | Atlas | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe2O3 |
| Cu$+0.z+0(s) | Atlas | Cu | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | -50.2080 | Cu$+0:+1 | Atlas | true | Atlas: Cu |
| Fe$+0.z+0(s) | Atlas | Fe | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +84.9352 | Fe$+0:+1 | Atlas | true | Atlas: Fe |
| Cu$+1(2).OH2.z+0(s) | Atlas | Cu2O | +0 | dissolution | -0.5205 | +2.9706 | +2.9706 | +2.9706 | Cu$+1:+2 H:-2 | Atlas | true | Atlas: Cu2O |
| [Fe$+3].[OH]3.[z+0]_(s) | [M3].[OH]3.[z+0]_(s) | [Fe(OH)3](s) | +0 | dissolution | -3.2000 | +18.2646 | +18.2646 | +92.6143 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] |
| Fe$+3.OH3.z+0(s) | Atlas | Fe(OH)3 (hydr.) | +0 | dissolution | -4.8381 | +27.6144 | +27.6144 | +101.9641 | Fe$+3:+1 H:-3 | Atlas | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe(OH)3 (hydr.) |
| Cu$+2.OH2.z+0(s) | Atlas | CuO | +0 | dissolution | -7.8876 | +45.0199 | +45.0199 | +59.7894 | Cu$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: CuO |
| [Cu$+2].[OH]2.[z+0]_(s) | [M1].[OH]2.[z+0]_(s) | [Cu(OH)2](s) | +0 | dissolution | -8.6800 | +49.5428 | +49.5428 | +64.3123 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] |
| Cu$+2.OH2.z+0(s) | Atlas | Cu(OH)2 | +0 | dissolution | -9.1997 | +52.5092 | +52.5092 | +67.2787 | Cu$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: Cu(OH)2 |
| Fe$+2.OH2.z+0(s) | Atlas | Fe(OH)2 (hydr.) | +0 | dissolution | -11.0690 | +63.1784 | +63.1784 | +63.1784 | Fe$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Fe$+2:1 H:-2] Atlas: Fe(OH)2 (hydr.) |
| [Fe$+2].[OH]2.[z+0]_(s) | [M4].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | +0 | dissolution | -13.5700 | +77.4534 | +77.4534 | +77.4534 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-2] |

### 5.3 Gas Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Cu$-1.H.z+0 | Atlas | CuH | +0 | gas | -0.0000 | +0.0000 | +0.0000 | -8.3680 | Cu$-1:+1 H:+1 | Atlas | true | Atlas: CuH |

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
