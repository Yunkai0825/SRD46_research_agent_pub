# Free Energy Analysis Card

**System**: H, Cd, Zn / Chloride, Ammonia, Hydroxide ion
**Metals**: [Cd]2+, [Zn]2+
**Ligands**: [Ammonia], [Chloride ion]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Cd$+2 | Metal component: [Cd]2+ |
| Cd$+0 | Metal component from Atlas: Cd(s) |
| Zn$+2 | Metal component: [Zn]2+ |
| Zn$+0 | Metal component from Atlas: Zn(s) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Ammonia] |
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
| Cd$+2 | [Cd]2+ | +2 | Not defined | NIST SRD-46 | metal_26 |
| Cd$+0 | Cd(s) | +0 | 0 | Pourbaix Atlas |  |
| Zn$+2 | [Zn]2+ | +2 | Not defined | NIST SRD-46 | metal_208 |
| Zn$+0 | Zn(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Ammonia] | +0 | Not defined | [[L1]] | NIST SRD-46 | ligand_10103 | N |
| L2 | [Chloride ion] | -1 | Not defined | [[L2]] | NIST SRD-46 | ligand_10163 | *** |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Cd | Cd$+2 | [Cd]2+ | +2 | true | 2 |
| Cd | Cd$+0 | Cd(s) | +0 | false | 2 |
| Zn | Zn$+2 | [Zn]2+ | +2 | true | 2 |
| Zn | Zn$+0 | Zn(s) | +0 | false | 2 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [Ammonia] | N | N | [-3] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Cd$+2 | [Cd]2+ | metal | [Cd]2+(aq) | +0.0000 | R1 | Cd | +2 | true |
| Cd$+0 | Cd(s) | metal | Cd(s)(aq/s) | +77.7387 | RULE 1 | Cd | +0 | false |
| Zn$+2 | [Zn]2+ | metal | [Zn]2+(aq) | +0.0000 | R1 | Zn | +2 | true |
| Zn$+0 | Zn(s) | metal | Zn(s)(aq/s) | +147.2099 | RULE 1 | Zn | +0 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Ammonia] | ligand_canonical | [[L1]] | +0.0000 | R4 | *** | +0 | *** |
| L2 | [Chloride ion] | ligand_canonical | [[L2]] | +0.0000 | R4 | *** | -1 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Ammonia] | [L1] -> [[L1]] | 0 | 0 | +0.0000 | +0.0000 | exact | R4a: canonical_H=0; shift≡0 |
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
| *** + [Ammonia] | 25.0 | 0.1 | *** | 1 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Cd]2+ + [Chloride ion] | 25.0 | 0~3 | 29910 | 11 |
| [Cd]2+ + [Ammonia] | 25.0 | 0~0.1 | 28286 | 4 |
| [Zn]2+ + [Chloride ion] | 25.0 | 0~0.1 | 29904 | 13 |
| [Zn]2+ + [Ammonia] | 25.0 | 0~0.1 | 28282 | 4 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z+1] | [[H][L1]].[z+1] | [HAmmonia]+ | +1 | aqueous | +9.2600 | -52.8532 | -52.8532 | -52.8532 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z+0] | [L1].[z+0] | [Ammonia] | +0 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L1]:+1 | SRD-46 | true | *** |
| [L2].[z-1] | [L2].[z-1] | [Chloride ion] | -1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L2]:+1 | SRD-46 | true | *** |
| Cd$+2.z+2 | Atlas | Cd2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Cd$+2:+1 | Atlas | false | [DUPLICATE GROUP: Cd$+2:1] Atlas: Cd2+ |
| [Cd$+2].[z+2] | [M1].[z+2] | [Cd]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Cd$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cd$+2:1] *** |
| [Cd$+2]2.[OH].[z+3] | [M1]2.[OH].[z+3] | [Cd2(OH)]3+ | +3 | aqueous | -9.4000 | +53.6523 | +53.6523 | +53.6523 | [Cd$+2]:+2, [OH]:+1 | SRD-46 | true | *** |
| [Cd$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Cd(OH)]+ | +1 | aqueous | -10.0000 | +57.0769 | +57.0769 | +57.0769 | [Cd$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Cd$+2].[OH]2.[z+0] | [M1].[OH]2.[z+0] | [Cd(OH)2] | +0 | aqueous | -20.3000 | +115.8661 | +115.8661 | +115.8661 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Cd$+2].[OH]3.[z-1] | [M1].[OH]3.[z-1] | [Cd(OH)3]- | -1 | aqueous | -31.7000 | +180.9338 | +180.9338 | +180.9338 | [Cd$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Cd$+2:1 H:-3] *** |
| Cd$+2.OH3.z-1 | Atlas | [HCdO2]- | -1 | aqueous | -55.3595 | +315.9757 | +315.9757 | +315.9757 | Cd$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Cd$+2:1 H:-3] Atlas: [HCdO2]- |
| [Cd$+2]4.[OH]4.[z+4] | [M1]4.[OH]4.[z+4] | [Cd4(OH)4]4+ | +4 | aqueous | -32.8000 | +187.2123 | +187.2123 | +187.2123 | [Cd$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Cd$+2].[OH]4.[z-2] | [M1].[OH]4.[z-2] | [Cd(OH)4]2- | -2 | aqueous | -64.7000 | +369.2877 | +369.2877 | +369.2877 | [Cd$+2]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Cd$+2].[L1]4.[z+2] | [M1].[L1]4.[z+2] | [Cd(Ammo)4]2+ | +2 | aqueous | +6.7200 | -38.3557 | -38.3557 | -38.3557 | [Cd$+2]:+1, [L1]:+4 | SRD-46 | true | *** |
| [Cd$+2].[L1]3.[z+2] | [M1].[L1]3.[z+2] | [Cd(Ammo)3]2+ | +2 | aqueous | +5.9000 | -33.6754 | -33.6754 | -33.6754 | [Cd$+2]:+1, [L1]:+3 | SRD-46 | true | *** |
| [Cd$+2].[L1]2.[z+2] | [M1].[L1]2.[z+2] | [Cd(Ammo)2]2+ | +2 | aqueous | +4.5600 | -26.0271 | -26.0271 | -26.0271 | [Cd$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Cd$+2].[L1].[z+2] | [M1].[L1].[z+2] | [Cd(Ammo)]2+ | +2 | aqueous | +2.5700 | -14.6688 | -14.6688 | -14.6688 | [Cd$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Cd$+2].[L2]3.[z-1] | [M1].[L2]3.[z-1] | [Cd(Chlo)3]- | -1 | aqueous | +2.4000 | -13.6985 | -13.6985 | -13.6985 | [Cd$+2]:+1, [L2]:+3 | SRD-46 | true | *** |
| [Cd$+2].[L2]2.[z+0] | [M1].[L2]2.[z+0] | [Cd(Chlo)2] | +0 | aqueous | +2.0500 | -11.7008 | -11.7008 | -11.7008 | [Cd$+2]:+1, [L2]:+2 | SRD-46 | true | *** |
| [Cd$+2].[L2].[z+1] | [M1].[L2].[z+1] | [Cd(Chlo)]+ | +1 | aqueous | +1.5200 | -8.6757 | -8.6757 | -8.6757 | [Cd$+2]:+1, [L2]:+1 | SRD-46 | true | *** |
| Zn$+2.z+2 | Atlas | Zn2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Zn$+2:+1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1] Atlas: Zn2+ |
| [Zn$+2].[z+2] | [M2].[z+2] | [Zn]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Zn$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1] *** |
| [Zn$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Zn(OH)]+ | +1 | aqueous | -9.3000 | +53.0815 | +53.0815 | +53.0815 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-1] *** |
| Zn$+2.OH.z+1 | Atlas | [ZnOH]+ | +1 | aqueous | -16.0346 | +91.5208 | +91.5208 | +91.5208 | Zn$+2:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-1] Atlas: [ZnOH]+ |
| [Zn$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Zn(OH)2] | +0 | aqueous | -15.8000 | +90.1815 | +90.1815 | +90.1815 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Zn$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Zn(OH)3]- | -1 | aqueous | -28.1000 | +160.3861 | +160.3861 | +160.3861 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-3] *** |
| Zn$+2.OH3.z-1 | Atlas | [HZnO2]- | -1 | aqueous | -28.7823 | +164.2806 | +164.2806 | +164.2806 | Zn$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-3] Atlas: [HZnO2]- |
| Zn$+2.OH4.z-2 | Atlas | [ZnO2]2- | -2 | aqueous | -33.4005 | +190.6398 | +190.6398 | +190.6398 | Zn$+2:+1 H:-4 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-4] Atlas: [ZnO2]2- |
| [Zn$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Zn(OH)4]2- | -2 | aqueous | -40.5000 | +231.1615 | +231.1615 | +231.1615 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-4] *** |
| [Zn$+2].[L1]4.[z+2] | [M2].[L1]4.[z+2] | [Zn(Ammo)4]2+ | +2 | aqueous | +8.8900 | -50.7414 | -50.7414 | -50.7414 | [Zn$+2]:+1, [L1]:+4 | SRD-46 | true | *** |
| [Zn$+2].[L1]3.[z+2] | [M2].[L1]3.[z+2] | [Zn(Ammo)3]2+ | +2 | aqueous | +6.8600 | -39.1548 | -39.1548 | -39.1548 | [Zn$+2]:+1, [L1]:+3 | SRD-46 | true | *** |
| [Zn$+2].[L1]2.[z+2] | [M2].[L1]2.[z+2] | [Zn(Ammo)2]2+ | +2 | aqueous | +4.5000 | -25.6846 | -25.6846 | -25.6846 | [Zn$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Zn$+2].[L1].[z+2] | [M2].[L1].[z+2] | [Zn(Ammo)]2+ | +2 | aqueous | +2.3300 | -13.2989 | -13.2989 | -13.2989 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Zn$+2].[L2].[z+1] | [M2].[L2].[z+1] | [Zn(Chlo)]+ | +1 | aqueous | -0.3000 | +1.7123 | +1.7123 | +1.7123 | [Zn$+2]:+1, [L2]:+1 | SRD-46 | true | *** |
| [Zn$+2].[L2]2.[z+0] | [M2].[L2]2.[z+0] | [Zn(Chlo)2] | +0 | aqueous | -0.3000 | +1.7123 | +1.7123 | +1.7123 | [Zn$+2]:+1, [L2]:+2 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Cd$+2].[OH]2.[[z+0(s)[1]]] | [M1].[OH]2.[[z+0(s)[1]]] | [Cd(OH)2(s,beta)] | +0 | dissolution | -13.6500 | +77.9100 | +77.9100 | +77.9100 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Cd$+2:1 H:-2] *** |
| Cd$+2.OH2.z+0(s) | Atlas | Cd(OH)2 (inactive) | +0 | dissolution | -13.8032 | +78.7847 | +78.7847 | +78.7847 | Cd$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cd$+2:1 H:-2] Atlas: Cd(OH)2 (inactive) |
| [Cd$+2].[OH]2.[[z+0(s)[2]]] | [M1].[OH]2.[[z+0(s)[2]]] | [Cd(OH)2(s,gamma)] | +0 | dissolution | -13.9000 | +79.3369 | +79.3369 | +79.3369 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Cd$+2:1 H:-2] *** |
| Cd$+2.OH2.z+0(s) | Atlas | Cd(OH)2 (active) | +0 | dissolution | -14.3823 | +82.0901 | +82.0901 | +82.0901 | Cd$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cd$+2:1 H:-2] Atlas: Cd(OH)2 (active) |
| Cd$+2.OH2.z+0(s) | Atlas | CdO | +0 | dissolution | -15.7458 | +89.8723 | +89.8723 | +89.8723 | Cd$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Cd$+2:1 H:-2] Atlas: CdO |
| Cd$+0.z+0(s) | Atlas | Cd | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +77.7387 | Cd$+0:+1 | Atlas | true | Atlas: Cd |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (inactive) | +0 | dissolution | -9.6132 | +54.8690 | +54.8690 | +54.8690 | Zn$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (inactive) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (active) | +0 | dissolution | -10.5368 | +60.1408 | +60.1408 | +60.1408 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (active) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (alpha) | +0 | dissolution | -10.7230 | +61.2036 | +61.2036 | +61.2036 | Zn$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (alpha) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (epsilon) | +0 | dissolution | -10.9502 | +62.5006 | +62.5006 | +62.5006 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (epsilon) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (gamma) | +0 | dissolution | -11.1797 | +63.8102 | +63.8102 | +63.8102 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (gamma) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (beta) | +0 | dissolution | -11.3101 | +64.5549 | +64.5549 | +64.5549 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (beta) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO | +0 | dissolution | -11.5191 | +65.7474 | +65.7474 | +65.7474 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO |
| [Zn$+2].[OH]2.[[z+0(s)[1]]] | [M2].[OH]2.[[z+0(s)[1]]] | [ZnO](s) | +0 | dissolution | -12.0400 | +68.7206 | +68.7206 | +68.7206 | [Zn$+2]:+1, [H]:-2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[2]]] | [M2].[OH]2.[[z+0(s)[2]]] | [Zn(OH)2(s,epsilon)] | +0 | dissolution | -12.2300 | +69.8051 | +69.8051 | +69.8051 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (amorphous) | +0 | dissolution | -12.2492 | +69.9146 | +69.9146 | +69.9146 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (amorphous) |
| [Zn$+2].[OH]2.[[z+0(s)[3]]] | [M2].[OH]2.[[z+0(s)[3]]] | [Zn(OH)2(s,gamma)] | +0 | dissolution | -12.4400 | +71.0037 | +71.0037 | +71.0037 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[4]]] | [M2].[OH]2.[[z+0(s)[4]]] | [Zn(OH)2(s,beta1)] | +0 | dissolution | -12.4600 | +71.1178 | +71.1178 | +71.1178 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[5]]] | [M2].[OH]2.[[z+0(s)[5]]] | [Zn(OH)2(s,beta2)] | +0 | dissolution | -12.5000 | +71.3461 | +71.3461 | +71.3461 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[6]]] | [M2].[OH]2.[[z+0(s)[6]]] | [Zn(OH)2(s,delta)] | +0 | dissolution | -12.5500 | +71.6315 | +71.6315 | +71.6315 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[7]]] | [M2].[OH]2.[[z+0(s)[7]]] | [Zn(OH)2(s,am)] | +0 | dissolution | -13.1800 | +75.2274 | +75.2274 | +75.2274 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+0.z+0(s) | Atlas | Zn | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +147.2099 | Zn$+0:+1 | Atlas | true | Atlas: Zn |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
