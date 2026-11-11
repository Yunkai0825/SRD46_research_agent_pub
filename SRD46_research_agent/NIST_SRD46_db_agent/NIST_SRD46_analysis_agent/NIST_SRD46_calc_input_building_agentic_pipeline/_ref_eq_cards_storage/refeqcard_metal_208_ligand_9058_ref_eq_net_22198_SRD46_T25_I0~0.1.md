# Free Energy Analysis Card

**System**: metal_208 + ligand_9058
**Metals**: [Zn]2+
**Ligands**: [Citric acid]
**Generated**: 2026-05-27 20:48:07 UTC

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Zn$+2 | Metal component: [Zn]2+ |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Citric acid] |
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
| Zn$+2 | [Zn]2+ | +2 | 0.001 | NIST SRD-46 | metal_208 |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Citric acid] | -3 | 0.01 | [[H]3[L1]] | NIST SRD-46 | ligand_9058 | O=C(O)CC(O)(CC(=O)O)C(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Zn | Zn$+2 | [Zn]2+ | +2 | true | 1 |

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
| Zn$+2 | [Zn]2+ | metal | [Zn]2+(aq) | +0.0000 | R1 | Zn | +2 | true |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9077 | R3 | *** | -1 | *** |
| L1 | [Citric acid] | ligand_canonical | [[H]3[L1]] | +0.0000 | R4 | *** | -3 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Citric acid] | [L1] -> [[H]3[L1]] | 3 | 1 | +5.6500 | +32.2485 | ladder | vlm_157439 |

### 3.3 Edge Case Notes

- EC-1: Canonical H3L not found in equilibrium map for 'Citric acid'; using H1L (logβ=5.650, vlm_157439) as approximate canonical reference (EC-1 ladder reconstruction).

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
| [Zn]2+ + [Citric acid] | 25.0 | 0.1 | 22198 | 4 |
| [Zn]2+ + [OH]- | 25.0 | 0~0.1 | 27522 | 11 |
| [H]+ + [Citric acid] | 25.0 | 0.1 | 22067 | 3 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by μ°_canon ascending (most stable canonical state first).

### 5.1 Aqueous Species

#### [Citric acid] (protonation). aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [[H][L1]].[z-2] | [HCitric acid]2- | -2 | aqueous | +5.6500 | -32.2485 | +0.0000 | +0.0000 | [[H][L1]]:+1 | vlm_157439 | *** |
| [L1].[z-3] | [Citric acid] | -3 | aqueous | +0.0000 | -0.0000 | +32.2485 | +32.2485 | [L1]:+1 | R4: μ°≡0 (free-ligand ref) | *** |

#### [Zn]2+. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Zn$+2].[z+2] | [Zn]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Zn$+2]:+1 | R1: μ°≡0 (aquo-ion ref) | *** |

#### [Zn]2+ + [Citric acid]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Zn$+2].[L1].[z-1] | [Zn(Citr)]- | -1 | aqueous | +4.7700 | -27.2257 | +5.0228 | +5.0228 | [Zn$+2]:+1, [L1]:+1 | vlm_157746 | *** |
| [Zn$+2].[L1]2.[z-4] | [Zn(Citr)2]4- | -4 | aqueous | +6.8000 | -38.8123 | +25.6846 | +25.6846 | [Zn$+2]:+1, [L1]:+2 | vlm_157752 | *** |
| [Zn$+2]2.[[H]-1[L1]]2.[z-4] | [Zn2(Citr)2(OH)2]4- | -4 | aqueous | -2.9000 | +16.5523 | +81.0492 | +81.0492 | [Zn$+2]:+2, [[H]-1[L1]]:+2 | vlm_157762 | *** |

#### [Zn]2+ + [Hydroxide]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Zn$+2].[OH].[z+1] | [Zn(OH)]+ | +1 | aqueous | -9.3000 | +53.0815 | +53.0815 | +53.0815 | [Zn$+2]:+1, [OH]:+1 | vlm_170929 | *** |
| [Zn$+2].[OH]3.[z-1] | [Zn(OH)3]- | -1 | aqueous | -28.1000 | +160.3861 | +160.3861 | +160.3861 | [Zn$+2]:+1, [OH]:+3 | vlm_170937 | *** |
| [Zn$+2].[OH]2.[z+0] | [Zn(OH)2] | +0 | aqueous | -38.2000 | +218.0338 | +218.0338 | +218.0338 | [Zn$+2]:+1, [OH]:+2 | vlm_170935 | *** |
| [Zn$+2].[OH]4.[z-2] | [Zn(OH)4]2- | -2 | aqueous | -40.5000 | +231.1615 | +231.1615 | +231.1615 | [Zn$+2]:+1, [OH]:+4 | vlm_170939 | *** |

### 5.2 Dissolution / Solid Species

#### [Zn]2+ + [Hydroxide]. solid

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Zn$+2].[OH]2.[z+0(s)[1]] | [Zn(OH)2(s,epsilon)] | +0 | dissolution | -12.2300 | +69.8051 | +69.8051 | +69.8051 | [Zn$+2]:+1, [OH]:+2 | vlm_170956 | *** |
| [Zn$+2].[OH]2.[z+0(s)[2]] | [Zn(OH)2(s,gamma)] | +0 | dissolution | -12.4400 | +71.0037 | +71.0037 | +71.0037 | [Zn$+2]:+1, [OH]:+2 | vlm_170952 | *** |
| [Zn$+2].[OH]2.[z+0(s)[3]] | [Zn(OH)2(s,beta1)] | +0 | dissolution | -12.4600 | +71.1178 | +71.1178 | +71.1178 | [Zn$+2]:+1, [OH]:+2 | vlm_170948 | *** |
| [Zn$+2].[OH]2.[z+0(s)[4]] | [Zn(OH)2(s,beta2)] | +0 | dissolution | -12.5000 | +71.3461 | +71.3461 | +71.3461 | [Zn$+2]:+1, [OH]:+2 | vlm_170950 | *** |
| [Zn$+2].[OH]2.[z+0(s)[5]] | [Zn(OH)2(s,delta)] | +0 | dissolution | -12.5500 | +71.6315 | +71.6315 | +71.6315 | [Zn$+2]:+1, [OH]:+2 | vlm_170954 | *** |
| [Zn$+2].[OH]2.[z+0(s)[6]] | [Zn(OH)2(s,am)] | +0 | dissolution | -13.1800 | +75.2274 | +75.2274 | +75.2274 | [Zn$+2]:+1, [OH]:+2 | vlm_170944 | *** |

### 5.3 Gas Species

(No gas species species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |

## 6. Validation: Equilibrium Map Coverage

### 6.1 Summary

| metric | count |
|--------|-------|
| Total eq-map entries | 18 |
| Included in calculation | 18 |
| Excluded (include_calculation=false) | 0 |
| Resolved → ≥1 species in card | 14 |
| Unresolved (no species in card) | 4 |

### 6.2 Per-Entry Detail

| # | vlm_id | equation | stepwise_logK | T_°C | I_M | included | species_in_card |
|---|--------|----------|---------------|------|-----|----------|-----------------|
| 1 | vlm_157752 | [<Citric acid>]^2 + [<Zn2+>] <=> [<Zn2+><Citric acid>2] | +6.8000 | 25.0 | 0.100 | yes | [Zn(Citr)2]4- |
| 2 | vlm_157762 | [<Citric acid>]^2 + [<Zn2+>]^2 <=> [<H+>]^2 + [<Zn2+>2(<H+>-1<Citric acid>)2] | -2.9000 | 25.0 | 0.100 | yes | [Zn2(Citr)2(OH)2]4- |
| 3 | vlm_157746 | [<Citric acid>] + [<Zn2+>] <=> [<Zn2+><Citric acid>] | +4.7700 | 25.0 | 0.100 | yes | [Zn(Citr)]- |
| 4 | vlm_157757 | [<H+><Citric acid>] + [<Zn2+>] <=> [<Zn2+><H+><Citric acid>] | +2.9700 | 25.0 | 0.100 | yes | — |
| 5 | vlm_170929 | [<OH+->] + [<Zn2+>] <=> [<Zn2+><OH+->] | +4.7000 | 25.0 | 0.100 | yes | [Zn(OH)]+ |
| 6 | vlm_170935 | [<OH+->]^2 + [<Zn2+>] <=> [<Zn2+><OH+->2] | -10.2000 | 25.0 | 0.000 | yes | [Zn(OH)2] |
| 7 | vlm_170937 | [<OH+->]^3 + [<Zn2+>] <=> [<Zn2+><OH+->3] | +13.9000 | 25.0 | 0.000 | yes | [Zn(OH)3]- |
| 8 | vlm_170939 | [<OH+->]^4 + [<Zn2+>] <=> [<Zn2+><OH+->4] | +15.5000 | 25.0 | 0.000 | yes | [Zn(OH)4]2- |
| 9 | vlm_157473 | [<H+>2<Citric acid>] + [<H+>] <=> [<H+>3<Citric acid>] | +2.9000 | 25.0 | 0.100 | yes | — |
| 10 | vlm_157459 | [<H+><Citric acid>] + [<H+>] <=> [<H+>2<Citric acid>] | +4.3500 | 25.0 | 0.100 | yes | — |
| 11 | vlm_157439 | [<H+>] + [<Citric acid>] <=> [<H+><Citric acid>] | +5.6500 | 25.0 | 0.100 | yes | [HCitric acid]2- |
| 12 | vlm_170944 | [<Zn2+><OH+->2(s,am)] <=> [<OH+->]^2 + [<Zn2+>] | -14.8200 | 25.0 | 0.100 | yes | [Zn(OH)2(s,am)] |
| 13 | vlm_170948 | [<Zn2+><OH+->2(s,beta1)] <=> [<OH+->]^2 + [<Zn2+>] | -15.5400 | 25.0 | 0.100 | yes | [Zn(OH)2(s,beta1)] |
| 14 | vlm_170950 | [<Zn2+><OH+->2(s,beta2)] <=> [<OH+->]^2 + [<Zn2+>] | -15.5000 | 25.0 | 0.100 | yes | [Zn(OH)2(s,beta2)] |
| 15 | vlm_170952 | [<Zn2+><OH+->2(s,gamma)] <=> [<OH+->]^2 + [<Zn2+>] | -15.5600 | 25.0 | 0.100 | yes | [Zn(OH)2(s,gamma)] |
| 16 | vlm_170954 | [<Zn2+><OH+->2(s,delta)] <=> [<OH+->]^2 + [<Zn2+>] | -15.4500 | 25.0 | 0.100 | yes | [Zn(OH)2(s,delta)] |
| 17 | vlm_170956 | [<Zn2+><OH+->2(s,epsilon)] <=> [<OH+->]^2 + [<Zn2+>] | -15.7700 | 25.0 | 0.100 | yes | [Zn(OH)2(s,epsilon)] |
| 18 | vlm_170958 | [H+2O] + [<Zn2+>O(s)] <=> [<Zn2+>] + [O<H+>]^2 | -15.9600 | 25.0 | 0.100 | yes | — |

---
*This card was generated by `free_energy_md_card_generation.py`. Speciation should be computed using free energies (μ°), not equilibrium βs directly.*
