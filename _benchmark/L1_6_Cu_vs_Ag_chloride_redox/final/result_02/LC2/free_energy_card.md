# Free Energy Analysis Card

**System**: H, Ag / Chloride, Hydroxide ion
**Metals**: [Ag]+
**Ligands**: [Chloride ion]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Ag$+1 | Metal component: [Ag]+ |
| Ag$+0 | Metal component from Atlas: Ag(s) |
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
| Ag$+1 | [Ag]+ | +1 | Not defined | NIST SRD-46 | metal_2 |
| Ag$+0 | Ag(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Chloride ion] | -1 | Not defined | [[L1]] | NIST SRD-46 | ligand_10163 | *** |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Ag | Ag$+1 | [Ag]+ | +1 | true | 2 |
| Ag | Ag$+0 | Ag(s) | +0 | false | 2 |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Ag$+1 | [Ag]+ | metal | [Ag]+(aq) | +0.0000 | R1 | Ag | +1 | true |
| Ag$+0 | Ag(s) | metal | Ag(s)(aq/s) | -77.1111 | RULE 1 | Ag | +0 | false |
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

### 3.3 Edge Case Notes

- SRD-SRD duplicates kept for LC2_3 adjudication: 3 identity collision(s); see [srd-dup ...] markers in additional_notes.

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
| [Ag]+ + [Chloride ion] | 20.0~25.0 | 0~4 | 29873 | 8 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [L1].[z-1] | [L1].[z-1] | [Chloride ion] | -1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L1]:+1 | SRD-46 | true | *** |
| Ag$+1.z+1 | Atlas | Ag+ | +1 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ag$+1:+1 | Atlas | true | [DUPLICATE GROUP: Ag$+1:1] Atlas: Ag+ |
| [Ag$+1].[z+1] | [M1].[z+1] | [Ag]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ag$+1]:+1 | SRD-46 | false | [DUPLICATE GROUP: Ag$+1:1] *** |
| [Ag$+1].[OH].[z+0].[dup2] | [M1].[OH].[z+0].[dup2] | [Ag(OH)] @20C | +0 | aqueous | -12.0000 | +67.3437 | +67.3437 | +67.3437 | [Ag$+1]:+1, [OH]:+1 | SRD-46 | false | [srd_1 2/2 frame] |
| [Ag$+1].[OH].[z+0].[dup1] | [M1].[OH].[z+0].[dup1] | [Ag(OH)] @25C | +0 | aqueous | -12.0000 | +68.4923 | +68.4923 | +68.4923 | [Ag$+1]:+1, [OH]:+1 | SRD-46 | true | [srd_1 1/2 frame] |
| [Ag$+1].[OH]2.[z-1].[dup2] | [M1].[OH]2.[z-1].[dup2] | [Ag(OH)2]- @20C | -1 | aqueous | -24.0100 | +134.7435 | +134.7435 | +134.7435 | [Ag$+1]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Ag$+1:1 H:-2] [srd_2 2/2 frame] |
| [Ag$+1].[OH]2.[z-1].[dup1] | [M1].[OH]2.[z-1].[dup1] | [Ag(OH)2]- @25C | -1 | aqueous | -24.0100 | +137.0417 | +137.0417 | +137.0417 | [Ag$+1]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ag$+1:1 H:-2] [srd_2 1/2 frame] |
| Ag$+1.OH2.z-1 | Atlas | [AgO]- | -1 | aqueous | -27.9730 | +159.6614 | +159.6614 | +159.6614 | Ag$+1:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ag$+1:1 H:-2] Atlas: [AgO]- |
| [Ag$+1].[L1]2.[z-1] | [M1].[L1]2.[z-1] | [Ag(Chlo)2]- | -1 | aqueous | +5.6700 | -31.8199 | -31.8199 | -31.8199 | [Ag$+1]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Ag$+1].[L1]3.[z-2] | [M1].[L1]3.[z-2] | [Ag(Chlo)3]2- | -2 | aqueous | +5.2000 | -29.1823 | -29.1823 | -29.1823 | [Ag$+1]:+1, [L1]:+3 | SRD-46 | true | *** |
| [Ag$+1].[L1].[z+0] | [M1].[L1].[z+0] | [Ag(Chlo)] | +0 | aqueous | +3.4500 | -19.3613 | -19.3613 | -19.3613 | [Ag$+1]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Ag$+1].[L1]4.[z-3] | [M1].[L1]4.[z-3] | [Ag(Chlo)4]3- | -3 | aqueous | -5.3200 | +29.8557 | +29.8557 | +29.8557 | [Ag$+1]:+1, [L1]:+4 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Ag$+1].[OH].[z+0].[dup2]_(s) | [M1].[OH].[z+0].[dup2]_(s) | [(Ag2O)0.5](s) @20C | +0 | dissolution | -6.6300 | +37.2074 | +37.2074 | +37.2074 | [Ag$+1]:+1, [H]:-1 | SRD-46 | false | [DUPLICATE GROUP: Ag$+1:1 H:-1] [srd_3 2/2 frame] |
| [Ag$+1].[OH].[z+0].[dup1]_(s) | [M1].[OH].[z+0].[dup1]_(s) | [(Ag2O)0.5](s) @25C | +0 | dissolution | -6.6300 | +37.8420 | +37.8420 | +37.8420 | [Ag$+1]:+1, [H]:-1 | SRD-46 | false | [DUPLICATE GROUP: Ag$+1:1 H:-1] [srd_3 1/2 frame] |
| Ag$+1(2).OH2.z+0(s) | Atlas | Ag2O | +0 | dissolution | -12.6406 | +72.1489 | +72.1489 | +72.1489 | Ag$+1:+2 H:-2 | Atlas | true | [DUPLICATE GROUP: Ag$+1:1 H:-1] Atlas: Ag2O |
| [Ag$+1].[L1].[z+0]_(s) | [M1].[L1].[z+0]_(s) | [Ag(Chloride ion)](s) | +0 | dissolution | +10.4000 | -58.3645 | -58.3645 | -58.3645 | [Ag$+1]:+1, [L1]:+1 | SRD-46 | true | *** |
| Ag$+0.z+0(s) | Atlas | Ag | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | -77.1111 | Ag$+0:+1 | Atlas | true | Atlas: Ag |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
