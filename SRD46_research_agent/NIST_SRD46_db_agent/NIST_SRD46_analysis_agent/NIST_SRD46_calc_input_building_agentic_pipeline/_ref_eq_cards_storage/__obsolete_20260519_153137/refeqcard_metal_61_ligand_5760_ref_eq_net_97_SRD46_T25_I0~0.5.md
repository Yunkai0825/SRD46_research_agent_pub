# Free Energy Analysis Card

**System**: metal_61 + ligand_5760
**Metals**: [Fe]3+
**Ligands**: [Glycine]
**Generated**: 2026-05-15 16:56:48 UTC

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Fe$+3 | Metal component: [Fe]3+ |
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
| Fe$+3 | [Fe]3+ | +3 | 0.001 | NIST SRD-46 | metal_61 |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Glycine] | -1 | 0.01 | [[H][L1]] | NIST SRD-46 | ligand_5760 | NCC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Fe | Fe$+3 | [Fe]3+ | +3 | true | 1 |

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
| Fe$+3 | [Fe]3+ | metal | [Fe]3+(aq) | +0.0000 | R1 | Fe | +3 | true |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9077 | R3 | *** | -1 | *** |
| L1 | [Glycine] | ligand_canonical | [[H][L1]] | +0.0000 | R4 | *** | -1 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Glycine] | [L1] -> [[H][L1]] | 1 | 1 | +9.5700 | +54.6226 | exact | vlm_93606 |

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
| [Fe]3+ + [Glycine] | 25.0 | 0.5 | 97 | 2 |
| [Fe]3+ + [OH]- | 25.0 | 0~0.1 | 27465 | 8 |
| [H]+ + [Glycine] | 25.0 | 0.1 | 1 | 2 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by μ°_canon ascending (most stable canonical state first).

### 5.1 Aqueous Species

#### [Glycine] (protonation). aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [[H][L1]].[z+0] | [HGlycine] | +0 | aqueous | +9.5700 | -54.6226 | +0.0000 | +0.0000 | [[H][L1]]:+1 | vlm_93606 | *** |
| [L1].[z-1] | [Glycine] | -1 | aqueous | +0.0000 | -0.0000 | +54.6226 | +54.6226 | [L1]:+1 | R4: μ°≡0 (free-ligand ref) | *** |

#### [Fe]3+. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+3].[z+3] | [Fe]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+3]:+1 | R1: μ°≡0 (aquo-ion ref) | *** |

#### [Fe]3+ + [Glycine]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+3].[L1].[z+2] | [Fe(Glyc)]2+ | +2 | aqueous | -8.5700 | +48.9149 | +103.5375 | +103.5375 | [Fe$+3]:+1, [L1]:+1 | vlm_93880 | *** |

#### [Fe]3+ + [Hydroxide]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+3].[OH].[z+2] | [Fe(OH)]2+ | +2 | aqueous | -2.7300 | +15.5820 | +15.5820 | +15.5820 | [Fe$+3]:+1, [OH]:+1 | vlm_170791 | *** |
| [Fe$+3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | +4 | aqueous | -2.8600 | +16.3240 | +16.3240 | +16.3240 | [Fe$+3]:+2, [OH]:+2 | vlm_170814 | *** |
| [Fe$+3].[OH]2.[z+1] | [Fe(OH)2]+ | +1 | aqueous | -4.6000 | +26.2554 | +26.2554 | +26.2554 | [Fe$+3]:+1, [OH]:+2 | vlm_170807 | *** |
| [Fe$+3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | +5 | aqueous | -6.3000 | +35.9585 | +35.9585 | +35.9585 | [Fe$+3]:+3, [OH]:+4 | vlm_170821 | *** |
| [Fe$+3].[OH]4.[z-1] | [Fe(OH)4]- | -1 | aqueous | -21.6000 | +123.2861 | +123.2861 | +123.2861 | [Fe$+3]:+1, [OH]:+4 | vlm_170808 | *** |

### 5.2 Dissolution / Solid Species

#### [Fe]3+ + [Hydroxide]. solid

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Fe$+3].[OH]3.[z+0]_(s) | [Fe(OH)3](s) | +0 | dissolution | -3.2000 | +18.2646 | +18.2646 | +18.2646 | [Fe$+3]:+1, [OH]:+3 | vlm_170825 | *** |

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
| Total eq-map entries | 12 |
| Included in calculation | 12 |
| Excluded (include_calculation=false) | 0 |
| Resolved → ≥1 species in card | 8 |
| Unresolved (no species in card) | 4 |

### 6.2 Per-Entry Detail

| # | vlm_id | equation | stepwise_logK | T_°C | I_M | included | species_in_card |
|---|--------|----------|---------------|------|-----|----------|-----------------|
| 1 | vlm_93880 | [<Glycine>] + [<Fe3+>] <=> [<Fe3+><Glycine>] | -8.5700 | 25.0 | 0.500 | yes | [Fe(Glyc)]2+ |
| 2 | vlm_93882 | [<H+><Glycine>] + [<Fe3+>] <=> [<Fe3+><H+><Glycine>] | +1.7700 | 25.0 | 0.500 | yes | — |
| 3 | vlm_170821 | [<OH+->]^4 + [<Fe3+>]^3 <=> [<Fe3+>3<OH+->4] | +49.7000 | 25.0 | 0.000 | yes | [Fe3(OH)4]5+ |
| 4 | vlm_170791 | [<OH+->] + [<Fe3+>] <=> [<Fe3+><OH+->] | +11.2700 | 25.0 | 0.100 | yes | [Fe(OH)]2+ |
| 5 | vlm_170807 | [<OH+->]^2 + [<Fe3+>] <=> [<Fe3+><OH+->2] | +23.4000 | 25.0 | 0.000 | yes | [Fe(OH)2]+ |
| 6 | vlm_170808 | [<OH+->]^4 + [<Fe3+>] <=> [<Fe3+><OH+->4] | +34.4000 | 25.0 | 0.000 | yes | [Fe(OH)4]- |
| 7 | vlm_170814 | [<OH+->]^2 + [<Fe3+>]^2 <=> [<Fe3+>2<OH+->2] | +25.1400 | 25.0 | 0.000 | yes | [Fe2(OH)2]4+ |
| 8 | vlm_93627 | [<H+><Glycine>] + [<H+>] <=> [<H+>2<Glycine>] | +2.3300 | 25.0 | 0.100 | yes | — |
| 9 | vlm_93606 | [<H+>] + [<Glycine>] <=> [<H+><Glycine>] | +9.5700 | 25.0 | 0.100 | yes | [HGlycine] |
| 10 | vlm_170825 | [<Fe3+><OH+->3(s)] <=> [<OH+->]^3 + [<Fe3+>] | -38.8000 | 25.0 | 0.000 | yes | [Fe(OH)3](s) |
| 11 | vlm_170827 | [H+2O] + [<Fe3+>OO<H+>(s,alpha)] <=> [<Fe3+>] + [O<H+>]^3 | -41.5000 | 25.0 | 0.000 | yes | — |
| 12 | vlm_170828 | [(<Fe3+>2O3)0.5(s,alpha)] + [H+2O] <=> [<Fe3+>] + [O<H+>]^3 | -42.7000 | 25.0 | 0.000 | yes | — |

---
*This card was generated by `free_energy_md_card_generation.py`. Speciation should be computed using free energies (μ°), not equilibrium βs directly.*
