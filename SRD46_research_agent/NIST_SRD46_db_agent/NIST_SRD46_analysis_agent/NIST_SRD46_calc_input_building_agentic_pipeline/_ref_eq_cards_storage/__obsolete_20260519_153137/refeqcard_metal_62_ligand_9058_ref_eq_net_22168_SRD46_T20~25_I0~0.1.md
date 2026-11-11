# Free Energy Analysis Card

**System**: metal_62 + ligand_9058
**Metals**: [Fe]2+
**Ligands**: [Citric acid]
**Generated**: 2026-05-15 16:56:51 UTC

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Fe$+2 | Metal component: [Fe]2+ |
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
| Fe$+2 | [Fe]2+ | +2 | 0.001 | NIST SRD-46 | metal_62 |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Citric acid] | -3 | 0.01 | [[H]3[L1]] | NIST SRD-46 | ligand_9058 | O=C(O)CC(O)(CC(=O)O)C(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Fe | Fe$+2 | [Fe]2+ | +2 | true | 1 |

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
| Fe$+2 | [Fe]2+ | metal | [Fe]2+(aq) | +0.0000 | R1 | Fe | +2 | true |
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
| [Fe]2+ + [Citric acid] | 20.0~25.0 | 0.1 | 22168 | 2 |
| [Fe]2+ + [OH]- | 25.0 | 0~0.1 | 27433 | 5 |
| [H]+ + [Citric acid] | 25.0 | 0.1 | 22067 | 3 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by μ°_canon ascending (most stable canonical state first).

### 5.1 Aqueous Species

#### [Citric acid] (protonation). aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [[H][L1]].[z-2] | [HCitric acid]2- | -2 | aqueous | +5.6500 | -32.2485 | +0.0000 | +0.0000 | [[H][L1]]:+1 | vlm_157439 | *** |
| [L1].[z-3] | [Citric acid] | -3 | aqueous | +0.0000 | -0.0000 | +32.2485 | +32.2485 | [L1]:+1 | R4: μ°≡0 (free-ligand ref) | *** |

#### [Fe]2+. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+2].[z+2] | [Fe]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+2]:+1 | R1: μ°≡0 (aquo-ion ref) | *** |

#### [Fe]2+ + [Citric acid]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+2].[L1].[z-1] | [Fe(Citr)]- | -1 | aqueous | +4.5600 | -26.0271 | +6.2214 | +6.2214 | [Fe$+2]:+1, [L1]:+1 | vlm_median(157619,157621,157622) | *** |

#### [Fe]2+ + [Hydroxide]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+2].[OH].[z+1] | [Fe(OH)]+ | +1 | aqueous | -9.8000 | +55.9354 | +55.9354 | +55.9354 | [Fe$+2]:+1, [OH]:+1 | vlm_170672 | *** |
| [Fe$+2].[OH]3.[z-1] | [Fe(OH)3]- | -1 | aqueous | -29.0000 | +165.5231 | +165.5231 | +165.5231 | [Fe$+2]:+1, [OH]:+3 | vlm_170680 | *** |
| [Fe$+2].[OH]2.[z+0] | [Fe(OH)2] | +0 | aqueous | -35.5000 | +202.6231 | +202.6231 | +202.6231 | [Fe$+2]:+1, [OH]:+2 | vlm_170677 | *** |
| [Fe$+2].[OH]4.[z-2] | [Fe(OH)4]2- | -2 | aqueous | -46.0000 | +262.5538 | +262.5538 | +262.5538 | [Fe$+2]:+1, [OH]:+4 | vlm_170683 | *** |

### 5.2 Dissolution / Solid Species

#### [Fe]2+ + [Hydroxide]. solid

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | +0 | dissolution | -13.5700 | +77.4534 | +77.4534 | +77.4534 | [Fe$+2]:+1, [OH]:+2 | vlm_170684 | *** |

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
| Total eq-map entries | 10 |
| Included in calculation | 10 |
| Excluded (include_calculation=false) | 0 |
| Resolved → ≥1 species in card | 6 |
| Unresolved (no species in card) | 4 |

### 6.2 Per-Entry Detail

| # | vlm_id | equation | stepwise_logK | T_°C | I_M | included | species_in_card |
|---|--------|----------|---------------|------|-----|----------|-----------------|
| 1 | vlm_median(157619,157621,157622) | [<Citric acid>] + [<Fe2+>] <=> [<Fe2+><Citric acid>] | +4.5600 | 20.0 | 0.100 | yes | — |
| 2 | vlm_157623 | [<H+><Citric acid>] + [<Fe2+>] <=> [<Fe2+><H+><Citric acid>] | +2.9000 | 25.0 | 0.100 | yes | — |
| 3 | vlm_170672 | [<OH+->] + [<Fe2+>] <=> [<Fe2+><OH+->] | +4.2000 | 25.0 | 0.100 | yes | [Fe(OH)]+ |
| 4 | vlm_170677 | [<OH+->]^2 + [<Fe2+>] <=> [<Fe2+><OH+->2] | -7.5000 | 25.0 | 0.000 | yes | [Fe(OH)2] |
| 5 | vlm_170680 | [<OH+->]^3 + [<Fe2+>] <=> [<Fe2+><OH+->3] | +13.0000 | 25.0 | 0.000 | yes | [Fe(OH)3]- |
| 6 | vlm_170683 | [<OH+->]^4 + [<Fe2+>] <=> [<Fe2+><OH+->4] | +10.0000 | 25.0 | 0.000 | yes | [Fe(OH)4]2- |
| 7 | vlm_157473 | [<H+>2<Citric acid>] + [<H+>] <=> [<H+>3<Citric acid>] | +2.9000 | 25.0 | 0.100 | yes | — |
| 8 | vlm_157459 | [<H+><Citric acid>] + [<H+>] <=> [<H+>2<Citric acid>] | +4.3500 | 25.0 | 0.100 | yes | — |
| 9 | vlm_157439 | [<H+>] + [<Citric acid>] <=> [<H+><Citric acid>] | +5.6500 | 25.0 | 0.100 | yes | [HCitric acid]2- |
| 10 | vlm_170684 | [<Fe2+><OH+->2(s)] <=> [<OH+->]^2 + [<Fe2+>] | -14.4300 | 25.0 | 0.000 | yes | [Fe(OH)2](s) |

---
*This card was generated by `free_energy_md_card_generation.py`. Speciation should be computed using free energies (μ°), not equilibrium βs directly.*
