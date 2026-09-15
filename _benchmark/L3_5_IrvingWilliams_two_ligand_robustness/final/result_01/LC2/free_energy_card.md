# Free Energy Analysis Card

**System**: H, Co / Glycine, Hydroxide ion
**Metals**: [Co]3+, [Co]2+
**Ligands**: [Glycine]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Co$+2 | Metal component: [Co]2+ |
| Co$+0 | Metal component from Atlas: Co(s) |
| Co$+3 | Metal component: [Co]3+ |
| Co$+4 | Metal component from Atlas: Co(+4) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Glycine] |
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
| Co$+2 | [Co]2+ | +2 | Not defined | NIST SRD-46 | metal_33 |
| Co$+0 | Co(s) | +0 | 0 | Pourbaix Atlas |  |
| Co$+3 | [Co]3+ | +3 | Not defined | NIST SRD-46 | metal_34 |
| Co$+4 | Co(+4) | +4 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Glycine] | -1 | Not defined | [[H][L1]] | NIST SRD-46 | ligand_5760 | NCC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Co | Co$+2 | [Co]2+ | +2 | true | 4 |
| Co | Co$+0 | Co(s) | +0 | false | 4 |
| Co | Co$+3 | [Co]3+ | +3 | false | 4 |
| Co | Co$+4 | Co(+4) | +4 | false | 4 |

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
| Co$+2 | [Co]2+ | metal | [Co]2+(aq) | +0.0000 | R1 | Co | +2 | true |
| Co$+0 | Co(s) | metal | Co(s)(aq/s) | +53.5552 | RULE 1 | Co | +0 | false |
| Co$+3 | [Co]3+ | metal | [Co]3+(aq) | +174.4728 | R1 | Co | +3 | false |
| Co$+4 | Co(+4) | metal | Co(+4)(aq/s) | +478.3986 | RULE 1 | Co | +4 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Glycine] | ligand_canonical | [[H][L1]] | +0.0000 | R4 | *** | -1 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Glycine] | [L1] -> [[H][L1]] | 1 | 1 | +9.5700 | +54.6226 | exact |  |

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
| *** + [Glycine] | 25.0 | 0.1 | *** | 2 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Co]3+ + *** | 25.0 | 0 | *** | 1 |
| [Co]2+ + [Glycine] | 25.0 | 0~0.1 | 70 | 11 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z+1] | [[H]2[L1]].[z+1] | [H2Glycine]+ | +1 | aqueous | +11.9000 | -67.9215 | -13.2989 | -13.2989 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z+0] | [[H][L1]].[z+0] | [HGlycine] | +0 | aqueous | +9.5700 | -54.6226 | +0.0000 | +0.0000 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-1] | [L1].[z-1] | [Glycine] | -1 | aqueous | +0.0000 | -0.0000 | +54.6226 | +54.6226 | [L1]:+1 | SRD-46 | true | *** |
| Co$+2.z+2 | Atlas | Co2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Co$+2:+1 | Atlas | false | [DUPLICATE GROUP: Co$+2:1] Atlas: Co2+ |
| [Co$+2].[z+2] | [M2].[z+2] | [Co]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Co$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Co$+2:1] *** |
| [Co$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Co(OH)]+ | +1 | aqueous | -9.7000 | +55.3646 | +55.3646 | +55.3646 | [Co$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Co$+2]2.[OH].[z+3] | [M2]2.[OH].[z+3] | [Co2(OH)]3+ | +3 | aqueous | -11.0000 | +62.7846 | +62.7846 | +62.7846 | [Co$+2]:+2, [OH]:+1 | SRD-46 | true | *** |
| [Co$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Co(OH)2] | +0 | aqueous | -18.8000 | +107.3046 | +107.3046 | +107.3046 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Co$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Co(OH)3]- | -1 | aqueous | -31.5000 | +179.7923 | +179.7923 | +179.7923 | [Co$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Co$+2:1 H:-3] *** |
| Co$+2.OH3.z-1 | Atlas | [HCoO2]- | -1 | aqueous | -31.6749 | +180.7906 | +180.7906 | +180.7906 | Co$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Co$+2:1 H:-3] Atlas: [HCoO2]- |
| [Co$+2]4.[OH]4.[z+4] | [M2]4.[OH]4.[z+4] | [Co4(OH)4]4+ | +4 | aqueous | -30.5000 | +174.0846 | +174.0846 | +174.0846 | [Co$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Co$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Co(OH)4]2- | -2 | aqueous | -46.3000 | +264.2661 | +264.2661 | +264.2661 | [Co$+2]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Co$+2].[L1].[z+1] | [M2].[L1].[z+1] | [Co(Glyc)]+ | +1 | aqueous | +4.6700 | -26.6549 | +27.9677 | +27.9677 | [Co$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Co$+2].[L1]2.[z+0] | [M2].[L1]2.[z+0] | [Co(Glyc)2] | +0 | aqueous | +8.4600 | -48.2871 | +60.9581 | +60.9581 | [Co$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Co$+2].[L1]3.[z-1] | [M2].[L1]3.[z-1] | [Co(Glyc)3]- | -1 | aqueous | +10.9000 | -62.2138 | +101.6540 | +101.6540 | [Co$+2]:+1, [L1]:+3 | SRD-46 | true | *** |
| [Co$+2].[OH].[L1].[z+0] | [M2].[OH].[L1].[z+0] | [Co(Glyc)(OH)] | +0 | aqueous | -5.4200 | +30.9357 | +85.5583 | +85.5583 | [Co$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true | *** |
| Co$+3.z+3 | Atlas | Co3+ | +3 | aqueous | -0.0000 | +0.0000 | +0.0000 | +174.4728 | Co$+3:+1 | Atlas | false | [DUPLICATE GROUP: Co$+3:1] Atlas: Co3+ |
| [Co$+3].[z+3] | [M1].[z+3] | [Co]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +174.4728 | [Co$+3]:+1 | SRD-46 | true | [DUPLICATE GROUP: Co$+3:1] *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Co$+2.OH2.z+0(s) | Atlas | CoO hyd. (Co(OH)2) | +0 | dissolution | +28.9626 | -165.3098 | -165.3098 | -165.3098 | Co$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Co$+2:1 H:-2] Atlas: CoO hyd. (Co(OH)2) |
| [Co$+2].[OH]2.[z+0]_(s) | [M2].[OH]2.[z+0]_(s) | [Co(OH)2](s) | +0 | dissolution | -13.1000 | +74.7708 | +74.7708 | +74.7708 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Co$+2:1 H:-2] *** |
| Co$+2.OH2.z+0(s) | Atlas | CoO | +0 | dissolution | -15.0201 | +85.7302 | +85.7302 | +85.7302 | Co$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Co$+2:1 H:-2] Atlas: CoO |
| Co$+2(3).OH8.z+0(s) | Atlas | Co3O4 | +0 | dissolution | -71.3436 | +407.2078 | +407.2078 | +407.2078 | Co$+2:+3 H:-8 | Atlas | false | Atlas: Co3O4 |
| [Co$+3].[OH]3.[z+0]_(s) | [M1].[OH]3.[z+0]_(s) | [Co(OH)3](s) | +0 | dissolution | +2.3000 | -13.1277 | -13.1277 | +161.3451 | [Co$+3]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Co$+3:1 H:-3] *** |
| Co$+3(2).OH6.z+0(s) | Atlas | Co2O3 hyd. (Co(OH)3) | +0 | dissolution | +2.0965 | -11.9662 | -11.9662 | +336.9794 | Co$+3:+2 H:-6 | Atlas | false | [DUPLICATE GROUP: Co$+3:1 H:-3] Atlas: Co2O3 hyd. (Co(OH)3) |
| Co$+4.OH4.z+0(s) | Atlas | CoO2 | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +478.3986 | Co$+4:+1 H:-4 | Atlas | false | Atlas: CoO2 |
| Co$+0.z+0(s) | Atlas | Co | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +53.5552 | Co$+0:+1 | Atlas | false | Atlas: Co |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
