# Free Energy Analysis Card

**System**: H, Fe / Chloride, Hydroxide ion
**Metals**: [Fe]3+, [Fe]2+
**Ligands**: [Chloride ion]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Fe$+2 | Metal component: [Fe]2+ |
| Fe$+0 | Metal component from Atlas: Fe(s) |
| Fe$+3 | Metal component: [Fe]3+ |
| Fe$+6 | Metal component from Atlas: Fe(+6) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Chloride ion] |
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
| Fe$+2 | [Fe]2+ | +2 | Not defined | NIST SRD-46 | metal_62 |
| Fe$+0 | Fe(s) | +0 | 0 | Pourbaix Atlas |  |
| Fe$+3 | [Fe]3+ | +3 | Not defined | NIST SRD-46 | metal_61 |
| Fe$+6 | Fe(+6) | +6 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Chloride ion] | -1 | Not defined | [[L1]] | NIST SRD-46 | ligand_10163 | *** |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Fe | Fe$+2 | [Fe]2+ | +2 | true | 4 |
| Fe | Fe$+0 | Fe(s) | +0 | false | 4 |
| Fe | Fe$+3 | [Fe]3+ | +3 | false | 4 |
| Fe | Fe$+6 | Fe(+6) | +6 | false | 4 |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Fe$+2 | [Fe]2+ | metal | [Fe]2+(aq) | +0.0000 | R1 | Fe | +2 | true |
| Fe$+0 | Fe(s) | metal | Fe(s)(aq/s) | +84.9352 | RULE 1 | Fe | +0 | false |
| Fe$+3 | [Fe]3+ | metal | [Fe]3+(aq) | +74.3497 | R1 | Fe | +3 | false |
| Fe$+6 | Fe(+6) | metal | Fe(+6)(aq/s) | +566.4090 | RULE 1 | Fe | +6 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Chloride ion] | ligand_canonical | [[L1]] | +0.0000 | R4 | *** | -1 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Chloride ion] | [L1] -> [[L1]] | 0 | 0 | +0.0000 | +0.0000 | exact | R4a: canonical_H=0; shift≡0 |

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
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Fe]3+ + [Chloride ion] | 25.0 | 0~0.1 | 29854 | 10 |
| [Fe]2+ + [Chloride ion] | 25.0 | 0~0.1 | 29830 | 6 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [L1].[z-1] | [L1].[z-1] | [Chloride ion] | -1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L1]:+1 | SRD-46 | true | *** |
| Fe$+2.z+2 | Atlas | Fe2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Fe$+2:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1] Atlas: Fe2+ |
| [Fe$+2].[z+2] | [M2].[z+2] | [Fe]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1] *** |
| [Fe$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Fe(OH)]+ | +1 | aqueous | -9.8000 | +55.9354 | +55.9354 | +55.9354 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Fe$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Fe(OH)2] | +0 | aqueous | -35.5000 | +202.6231 | +202.6231 | +202.6231 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Fe$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Fe(OH)3]- | -1 | aqueous | -29.0000 | +165.5231 | +165.5231 | +165.5231 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-3] *** |
| Fe$+2.OH3.z-1 | Atlas | [HFeO2]- | -1 | aqueous | -31.5598 | +180.1338 | +180.1338 | +180.1338 | Fe$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-3] Atlas: [HFeO2]- |
| [Fe$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Fe(OH)4]2- | -2 | aqueous | -46.0000 | +262.5538 | +262.5538 | +262.5538 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+2].[L1].[z+1] | [M2].[L1].[z+1] | [Fe(Chlo)]+ | +1 | aqueous | -0.2000 | +1.1415 | +1.1415 | +1.1415 | [Fe$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| Fe$+3.z+3 | Atlas | Fe3+ | +3 | aqueous | -0.0000 | +0.0000 | +0.0000 | +74.3497 | Fe$+3:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1] Atlas: Fe3+ |
| [Fe$+3].[z+3] | [M1].[z+3] | [Fe]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +74.3497 | [Fe$+3]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1] *** |
| Fe$+3.OH.z+2 | Atlas | [FeOH]2+ | +2 | aqueous | -2.4264 | +13.8490 | +13.8490 | +88.1987 | Fe$+3:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-1] Atlas: [FeOH]2+ |
| [Fe$+3].[OH].[z+2] | [M1].[OH].[z+2] | [Fe(OH)]2+ | +2 | aqueous | -2.7300 | +15.5820 | +15.5820 | +89.9317 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3]2.[OH]2.[z+4] | [M1]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | +4 | aqueous | -2.8600 | +16.3240 | +16.3240 | +165.0234 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3].[OH]2.[z+1] | [M1].[OH]2.[z+1] | [Fe(OH)2]+ | +1 | aqueous | -4.6000 | +26.2554 | +26.2554 | +100.6051 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-2] *** |
| Fe$+3.OH2.z+1 | Atlas | [Fe(OH)2]+ | +1 | aqueous | -7.1179 | +40.6266 | +40.6266 | +114.9763 | Fe$+3:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-2] Atlas: [Fe(OH)2]+ |
| [Fe$+3]3.[OH]4.[z+5] | [M1]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | +5 | aqueous | -6.3000 | +35.9585 | +35.9585 | +259.0076 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[OH]4.[z-1] | [M1].[OH]4.[z-1] | [Fe(OH)4]- | -1 | aqueous | -21.6000 | +123.2861 | +123.2861 | +197.6358 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[L1]2.[z+1] | [M1].[L1]2.[z+1] | [Fe(Chlo)2]+ | +1 | aqueous | +2.1300 | -12.1574 | -12.1574 | +62.1923 | [Fe$+3]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Fe$+3].[L1].[z+2] | [M1].[L1].[z+2] | [Fe(Chlo)]2+ | +2 | aqueous | +0.7800 | -4.4520 | -4.4520 | +69.8977 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true | *** |
| Fe$+6.OH8.z-2 | Atlas | [FeO4]2- | -2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +566.4090 | Fe$+6:+1 H:-8 | Atlas | true | Atlas: [FeO4]2- |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Fe$+2.OH2.z+0(s) | Atlas | Fe(OH)2 (hydr.) | +0 | dissolution | -13.2754 | +75.7722 | +75.7722 | +75.7722 | Fe$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-2] Atlas: Fe(OH)2 (hydr.) |
| [Fe$+2].[OH]2.[z+0]_(s) | [M2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | +0 | dissolution | -13.5700 | +77.4534 | +77.4534 | +77.4534 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-2] *** |
| Fe$+2.Fe$+3(2).OH8.z+0(s) | Atlas | Fe3O4 (anh.) | +0 | dissolution | -7.1252 | +40.6684 | +40.6684 | +189.3678 | Fe$+2:+1 Fe$+3:+2 H:-8 | Atlas | true | Atlas: Fe3O4 (anh.) |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [M1].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | +70.3543 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [M1].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | +0 | dissolution | -0.5000 | +2.8538 | +2.8538 | +77.2035 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [M1].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | +0 | dissolution | -3.2000 | +18.2646 | +18.2646 | +92.6143 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| Fe$+3.OH3.z+0(s) | Atlas | Fe(OH)3 (hydr.) | +0 | dissolution | -4.8381 | +27.6144 | +27.6144 | +101.9641 | Fe$+3:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe(OH)3 (hydr.) |
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
