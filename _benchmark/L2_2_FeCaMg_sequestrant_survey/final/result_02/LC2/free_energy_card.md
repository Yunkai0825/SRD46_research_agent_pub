# Free Energy Analysis Card

**System**: H, Fe, Ca, Mg / HEDTA, Hydroxide ion
**Metals**: [Fe]3+, [Fe]2+, [Ca]2+, [Mg]2+
**Ligands**: [HEDTA]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Ca$+2 | Metal component: [Ca]2+ |
| Ca$+0 | Metal component from Atlas: Ca(s) |
| Fe$+2 | Metal component: [Fe]2+ |
| Fe$+0 | Metal component from Atlas: Fe(s) |
| Fe$+3 | Metal component: [Fe]3+ |
| Fe$+6 | Metal component from Atlas: Fe(+6) |
| Mg$+2 | Metal component: [Mg]2+ |
| Mg$+0 | Metal component from Atlas: Mg(s) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [HEDTA] |
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
| Fe$+2 | [Fe]2+ | +2 | Not defined | NIST SRD-46 | metal_62 |
| Fe$+0 | Fe(s) | +0 | 0 | Pourbaix Atlas |  |
| Fe$+3 | [Fe]3+ | +3 | Not defined | NIST SRD-46 | metal_61 |
| Fe$+6 | Fe(+6) | +6 | 0 | Pourbaix Atlas |  |
| Mg$+2 | [Mg]2+ | +2 | Not defined | NIST SRD-46 | metal_92 |
| Mg$+0 | Mg(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [HEDTA] | -3 | Not defined | [[H]3[L1]] | NIST SRD-46 | ligand_6275 | O=C(O)CN(CCO)CCN(CC(=O)O)CC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Ca | Ca$+2 | [Ca]2+ | +2 | true | 2 |
| Ca | Ca$+0 | Ca(s) | +0 | false | 2 |
| Fe | Fe$+2 | [Fe]2+ | +2 | true | 4 |
| Fe | Fe$+0 | Fe(s) | +0 | false | 4 |
| Fe | Fe$+3 | [Fe]3+ | +3 | false | 4 |
| Fe | Fe$+6 | Fe(+6) | +6 | false | 4 |
| Mg | Mg$+2 | [Mg]2+ | +2 | true | 2 |
| Mg | Mg$+0 | Mg(s) | +0 | false | 2 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [HEDTA] | O=C(O)CN(CCO)CCN(CC(=O)O)CC(=O)O | C | [-1, -1, -1, -1, -1, -1, -1, 3, 3, 3] | true |
| L1 | [HEDTA] | O=C(O)CN(CCO)CCN(CC(=O)O)CC(=O)O | N | [-3, -3] | false |
| L1 | [HEDTA] | O=C(O)CN(CCO)CCN(CC(=O)O)CC(=O)O | O | [-2, -2, -2, -2, -2, -2, -2] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Ca$+2 | [Ca]2+ | metal | [Ca]2+(aq) | +0.0000 | R1 | Ca | +2 | true |
| Ca$+0 | Ca(s) | metal | Ca(s)(aq/s) | +553.0411 | RULE 1 | Ca | +0 | false |
| Fe$+2 | [Fe]2+ | metal | [Fe]2+(aq) | +0.0000 | R1 | Fe | +2 | true |
| Fe$+0 | Fe(s) | metal | Fe(s)(aq/s) | +84.9352 | RULE 1 | Fe | +0 | false |
| Fe$+3 | [Fe]3+ | metal | [Fe]3+(aq) | +74.3497 | R1 | Fe | +3 | false |
| Fe$+6 | Fe(+6) | metal | Fe(+6)(aq/s) | +566.4090 | RULE 1 | Fe | +6 | false |
| Mg$+2 | [Mg]2+ | metal | [Mg]2+(aq) | +0.0000 | R1 | Mg | +2 | true |
| Mg$+0 | Mg(s) | metal | Mg(s)(aq/s) | +451.8720 | RULE 1 | Mg | +0 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [HEDTA] | ligand_canonical | [[H]3[L1]] | +0.0000 | R4 | *** | -3 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [HEDTA] | [L1] -> [[H]3[L1]] | 3 | 3 | +17.7850 | +101.5113 | exact |  |

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
| *** + [HEDTA] | 25.0 | 1 | *** | 4 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Fe]3+ + [HEDTA] | 25.0 | 0~0.1 | 4876 | 12 |
| [Fe]2+ + [HEDTA] | 25.0 | 0~0.1 | 4867 | 7 |
| [Ca]2+ + [HEDTA] | 25.0 | 0~0.1 | 4820 | 3 |
| [Mg]2+ + [HEDTA] | 25.0 | 0.1~3 | 4819 | 5 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]4[L1]].[z+1] | [[H]4[L1]].[z+1] | [H4HEDTA]+ | +1 | aqueous | +16.1850 | -92.3790 | +9.1323 | +9.1323 | [[H]4[L1]]:+1 | SRD-46 | true | *** |
| [[H]3[L1]].[z+0] | [[H]3[L1]].[z+0] | [H3HEDTA] | +0 | aqueous | +17.7850 | -101.5113 | +0.0000 | +0.0000 | [[H]3[L1]]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z-1] | [[H]2[L1]].[z-1] | [H2HEDTA]- | -1 | aqueous | +15.1650 | -86.5571 | +14.9542 | +14.9542 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z-2] | [[H][L1]].[z-2] | [HHEDTA]2- | -2 | aqueous | +9.7850 | -55.8498 | +45.6615 | +45.6615 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-3] | [L1].[z-3] | [HEDTA] | -3 | aqueous | +0.0000 | -0.0000 | +101.5113 | +101.5113 | [L1]:+1 | SRD-46 | true | *** |
| Ca$+2.z+2 | Atlas | Ca2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ca$+2:+1 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1] Atlas: Ca2+ |
| [Ca$+2].[z+2] | [M3].[z+2] | [Ca]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ca$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Ca$+2:1] *** |
| [Ca$+2].[OH].[z+1] | [M3].[OH].[z+1] | [Ca(OH)]+ | +1 | aqueous | -13.0400 | +74.4283 | +74.4283 | +74.4283 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Ca$+2].[L1].[z-1] | [M3].[L1].[z-1] | [Ca(HEDT)]- | -1 | aqueous | +8.1000 | -46.2323 | +55.2790 | +55.2790 | [Ca$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| Fe$+2.z+2 | Atlas | Fe2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Fe$+2:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1] Atlas: Fe2+ |
| [Fe$+2].[z+2] | [M2].[z+2] | [Fe]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1] *** |
| [Fe$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Fe(OH)]+ | +1 | aqueous | -9.8000 | +55.9354 | +55.9354 | +55.9354 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | false | *** |
| [Fe$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Fe(OH)2] | +0 | aqueous | -35.5000 | +202.6231 | +202.6231 | +202.6231 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | false | *** |
| [Fe$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Fe(OH)3]- | -1 | aqueous | -29.0000 | +165.5231 | +165.5231 | +165.5231 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-3] *** |
| Fe$+2.OH3.z-1 | Atlas | [HFeO2]- | -1 | aqueous | -31.5598 | +180.1338 | +180.1338 | +180.1338 | Fe$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-3] Atlas: [HFeO2]- |
| [Fe$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Fe(OH)4]2- | -2 | aqueous | -46.0000 | +262.5538 | +262.5538 | +262.5538 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | false | *** |
| [Fe$+2].[[H][L1]].[z+0] | [M2].[[H][L1]].[z+0] | [Fe(HEDT)H] | +0 | aqueous | +14.9050 | -85.0731 | +16.4382 | +16.4382 | [Fe$+2]:+1, [[H][L1]]:+1 | SRD-46 | false | *** |
| [Fe$+2].[L1].[z-1] | [M2].[L1].[z-1] | [Fe(HEDT)]- | -1 | aqueous | +12.2000 | -69.6338 | +31.8775 | +31.8775 | [Fe$+2]:+1, [L1]:+1 | SRD-46 | false | *** |
| Fe$+3.z+3 | Atlas | Fe3+ | +3 | aqueous | -0.0000 | +0.0000 | +0.0000 | +74.3497 | Fe$+3:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1] Atlas: Fe3+ |
| [Fe$+3].[z+3] | [M1].[z+3] | [Fe]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +74.3497 | [Fe$+3]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1] *** |
| Fe$+3.OH.z+2 | Atlas | [FeOH]2+ | +2 | aqueous | -2.4264 | +13.8490 | +13.8490 | +88.1987 | Fe$+3:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-1] Atlas: [FeOH]2+ |
| [Fe$+3].[OH].[z+2] | [M1].[OH].[z+2] | [Fe(OH)]2+ | +2 | aqueous | -2.7300 | +15.5820 | +15.5820 | +89.9317 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3]2.[OH]2.[z+4] | [M1]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | +4 | aqueous | -2.8600 | +16.3240 | +16.3240 | +165.0234 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3].[OH]2.[z+1] | [M1].[OH]2.[z+1] | [Fe(OH)2]+ | +1 | aqueous | -4.6000 | +26.2554 | +26.2554 | +100.6051 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-2] *** |
| Fe$+3.OH2.z+1 | Atlas | [Fe(OH)2]+ | +1 | aqueous | -7.1179 | +40.6266 | +40.6266 | +114.9763 | Fe$+3:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-2] Atlas: [Fe(OH)2]+ |
| [Fe$+3]3.[OH]4.[z+5] | [M1]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | +5 | aqueous | -6.3000 | +35.9585 | +35.9585 | +259.0076 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[OH]4.[z-1] | [M1].[OH]4.[z-1] | [Fe(OH)4]- | -1 | aqueous | -21.6000 | +123.2861 | +123.2861 | +197.6358 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[L1].[z+0] | [M1].[L1].[z+0] | [Fe(HEDT)] | +0 | aqueous | +19.7000 | -112.4415 | -10.9302 | +63.4195 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Fe$+3].[OH].[L1].[z-1] | [M1].[OH].[L1].[z-1] | [Fe(HEDT)(OH)]- | -1 | aqueous | +15.8200 | -90.2957 | +11.2156 | +85.5653 | [Fe$+3]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Fe$+3].[OH]2.[L1].[z-2] | [M1].[OH]2.[L1].[z-2] | [Fe(HEDT)(OH)2]2- | -2 | aqueous | +6.9900 | -39.8968 | +61.6145 | +135.9642 | [Fe$+3]:+1, [OH]:+2, [L1]:+1 | SRD-46 | true | *** |
| [Fe$+3].[OH]3.[L1].[z-3] | [M1].[OH]3.[L1].[z-3] | [Fe(HEDT)(OH)3]3- | -3 | aqueous | -3.0100 | +17.1802 | +118.6915 | +193.0412 | [Fe$+3]:+1, [OH]:+3, [L1]:+1 | SRD-46 | true | *** |
| Fe$+6.OH8.z-2 | Atlas | [FeO4]2- | -2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +566.4090 | Fe$+6:+1 H:-8 | Atlas | false | Atlas: [FeO4]2- |
| Mg$+2.z+2 | Atlas | Mg2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Mg$+2:+1 | Atlas | false | [DUPLICATE GROUP: Mg$+2:1] Atlas: Mg2+ |
| [Mg$+2].[z+2] | [M4].[z+2] | [Mg]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Mg$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Mg$+2:1] *** |
| [Mg$+2].[OH].[z+1] | [M4].[OH].[z+1] | [Mg(OH)]+ | +1 | aqueous | -11.4000 | +65.0677 | +65.0677 | +65.0677 | [Mg$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Mg$+2]2.[OH].[z+3] | [M4]2.[OH].[z+3] | [Mg2(OH)]3+ | +3 | aqueous | -11.7000 | +66.7800 | +66.7800 | +66.7800 | [Mg$+2]:+2, [OH]:+1 | SRD-46 | true | *** |
| [Mg$+2]4.[OH]4.[z+4] | [M4]4.[OH]4.[z+4] | [Mg4(OH)4]4+ | +4 | aqueous | -39.9000 | +227.7369 | +227.7369 | +227.7369 | [Mg$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Mg$+2].[L1].[z-1] | [M4].[L1].[z-1] | [Mg(HEDT)]- | -1 | aqueous | +7.0000 | -39.9538 | +61.5575 | +61.5575 | [Mg$+2]:+1, [L1]:+1 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Ca$+2].[OH]2.[z+0]_(s) | [M3].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | +0 | dissolution | -22.8100 | +130.1925 | +130.1925 | +130.1925 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ca$+2:1 H:-2] *** |
| Ca$+2.OH2.z+0(s) | Atlas | Ca(OH)2 | +0 | dissolution | -22.8930 | +130.6663 | +130.6663 | +130.6663 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: Ca(OH)2 |
| Ca$+2.OH2.z+0(s) | Atlas | CaO | +0 | dissolution | -32.5985 | +186.0625 | +186.0625 | +186.0625 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: CaO |
| Ca$+2.OH4.z+0(s) | Atlas | CaO2 | +0 | dissolution | -75.1811 | +429.1110 | +429.1110 | +429.1110 | Ca$+2:+1 H:-4 | Atlas | false | Atlas: CaO2 |
| Ca$+0.z+0(s) | Atlas | Ca | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +553.0411 | Ca$+0:+1 | Atlas | false | Atlas: Ca |
| Fe$+2.OH2.z+0(s) | Atlas | Fe(OH)2 (hydr.) | +0 | dissolution | -13.2754 | +75.7722 | +75.7722 | +75.7722 | Fe$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-2] Atlas: Fe(OH)2 (hydr.) |
| [Fe$+2].[OH]2.[z+0]_(s) | [M2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | +0 | dissolution | -13.5700 | +77.4534 | +77.4534 | +77.4534 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-2] *** |
| Fe$+2.Fe$+3(2).OH8.z+0(s) | Atlas | Fe3O4 (anh.) | +0 | dissolution | -7.1252 | +40.6684 | +40.6684 | +189.3678 | Fe$+2:+1 Fe$+3:+2 H:-8 | Atlas | false | Atlas: Fe3O4 (anh.) |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [M1].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | +70.3543 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [M1].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | +0 | dissolution | -0.5000 | +2.8538 | +2.8538 | +77.2035 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [M1].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | +0 | dissolution | -3.2000 | +18.2646 | +18.2646 | +92.6143 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| Fe$+3.OH3.z+0(s) | Atlas | Fe(OH)3 (hydr.) | +0 | dissolution | -4.8381 | +27.6144 | +27.6144 | +101.9641 | Fe$+3:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe(OH)3 (hydr.) |
| Fe$+3(2).OH6.z+0(s) | Atlas | Fe2O3 (anh.) | +0 | dissolution | +1.4441 | -8.2425 | -8.2425 | +140.4569 | Fe$+3:+2 H:-6 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe2O3 (anh.) |
| Fe$+0.z+0(s) | Atlas | Fe | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +84.9352 | Fe$+0:+1 | Atlas | false | Atlas: Fe |
| [Mg$+2].[OH]2.[z+0]_(s) | [M4].[OH]2.[z+0]_(s) | [Mg(OH)2(s,brucite)] | +0 | dissolution | -16.8500 | +96.1746 | +96.1746 | +96.1746 | [Mg$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Mg$+0.z+0(s) | Atlas | Mg | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +451.8720 | Mg$+0:+1 | Atlas | false | Atlas: Mg |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
