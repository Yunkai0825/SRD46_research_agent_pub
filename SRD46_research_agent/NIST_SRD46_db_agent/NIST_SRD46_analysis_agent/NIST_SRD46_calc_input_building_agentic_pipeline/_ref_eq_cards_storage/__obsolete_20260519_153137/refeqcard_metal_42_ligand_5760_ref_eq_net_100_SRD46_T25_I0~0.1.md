# Free Energy Analysis Card

**System**: metal_42 + ligand_5760
**Metals**: [Cu]+
**Ligands**: [Glycine]
**Generated**: 2026-05-15 16:56:46 UTC

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Cu$+1 | Metal component: [Cu]+ |
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
| Cu$+1 | [Cu]+ | +1 | 0.001 | NIST SRD-46 | metal_42 |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Glycine] | -1 | 0.01 | [[H][L1]] | NIST SRD-46 | ligand_5760 | NCC(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Cu | Cu$+1 | [Cu]+ | +1 | true | 1 |

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
| [Cu]+ + [Glycine] | 25.0 | 0.1 | 100 | 1 |
| [H]+ + [Glycine] | 25.0 | 0.1 | 1 | 2 |
| [Cu]+ + [OH]- | 25.0 | 0 | 27492 | 1 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by μ°_canon ascending (most stable canonical state first).

### 5.1 Aqueous Species

#### [Glycine] (protonation). aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [[H][L1]].[z+0] | [HGlycine] | +0 | aqueous | +9.5700 | -54.6226 | +0.0000 | +0.0000 | [[H][L1]]:+1 | vlm_93606 | *** |
| [L1].[z-1] | [Glycine] | -1 | aqueous | +0.0000 | -0.0000 | +54.6226 | +54.6226 | [L1]:+1 | R4: μ°≡0 (free-ligand ref) | *** |

#### [Cu]+. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Cu$+1].[z+1] | [Cu]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Cu$+1]:+1 | R1: μ°≡0 (aquo-ion ref) | *** |

#### [Cu]+ + [Glycine]. aqueous

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|------------------|
| [Cu$+1].[L1]2.[z-1] | [Cu(Glyc)2]- | -1 | aqueous | +10.1000 | -57.6477 | +51.5975 | +51.5975 | [Cu$+1]:+1, [L1]:+2 | vlm_93899 | *** |

### 5.2 Dissolution / Solid Species

(No dissolution / solid species species in this system.)

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
| Total eq-map entries | 4 |
| Included in calculation | 4 |
| Excluded (include_calculation=false) | 0 |
| Resolved → ≥1 species in card | 2 |
| Unresolved (no species in card) | 2 |

### 6.2 Per-Entry Detail

| # | vlm_id | equation | stepwise_logK | T_°C | I_M | included | species_in_card |
|---|--------|----------|---------------|------|-----|----------|-----------------|
| 1 | vlm_93899 | [<Glycine>]^2 + [<Cu+>] <=> [<Cu+><Glycine>2] | +10.1000 | 25.0 | 0.100 | yes | [Cu(Glyc)2]- |
| 2 | vlm_93627 | [<H+><Glycine>] + [<H+>] <=> [<H+>2<Glycine>] | +2.3300 | 25.0 | 0.100 | yes | — |
| 3 | vlm_93606 | [<H+>] + [<Glycine>] <=> [<H+><Glycine>] | +9.5700 | 25.0 | 0.100 | yes | [HGlycine] |
| 4 | vlm_170869 | [(<Cu+>2O)0.5(s)] + [H+2O]^0 <=> [<Cu+>] + [O<H+>] | -14.7000 | 25.0 | 0.000 | yes | — |

---
*This card was generated by `free_energy_md_card_generation.py`. Speciation should be computed using free energies (μ°), not equilibrium βs directly.*
