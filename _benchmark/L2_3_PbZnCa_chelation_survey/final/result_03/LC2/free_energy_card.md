# Free Energy Analysis Card

**System**: H, Pb, Zn, Ca / meso-Dithiotartaric acid, Hydroxide ion
**Metals**: [Pb]2+, [Zn]2+, [Ca]2+
**Ligands**: [meso-Dithiotartaric acid]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Ca$+2 | Metal component: [Ca]2+ |
| Ca$+0 | Metal component from Atlas: Ca(s) |
| Pb$+2 | Metal component: [Pb]2+ |
| Pb$+0 | Metal component from Atlas: Pb(s) |
| Pb$+3 | Metal component from Atlas: Pb(+3) |
| Pb$+4 | Metal component from Atlas: Pb(+4) |
| Zn$+2 | Metal component: [Zn]2+ |
| Zn$+0 | Metal component from Atlas: Zn(s) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [meso-Dithiotartaric acid] |
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
| Pb$+2 | [Pb]2+ | +2 | Not defined | NIST SRD-46 | metal_125 |
| Pb$+0 | Pb(s) | +0 | 0 | Pourbaix Atlas |  |
| Pb$+3 | Pb(+3) | +3 | 0 | Pourbaix Atlas |  |
| Pb$+4 | Pb(+4) | +4 | 0 | Pourbaix Atlas |  |
| Zn$+2 | [Zn]2+ | +2 | Not defined | NIST SRD-46 | metal_208 |
| Zn$+0 | Zn(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [meso-Dithiotartaric acid] | -4 | Not defined | [[H]4[L1]] | NIST SRD-46 | ligand_8997 | O=C(O)[C@@H](S)[C@@H](S)C(=O)O |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Ca | Ca$+2 | [Ca]2+ | +2 | true | 2 |
| Ca | Ca$+0 | Ca(s) | +0 | false | 2 |
| Pb | Pb$+2 | [Pb]2+ | +2 | true | 4 |
| Pb | Pb$+0 | Pb(s) | +0 | false | 4 |
| Pb | Pb$+3 | Pb(+3) | +3 | false | 4 |
| Pb | Pb$+4 | Pb(+4) | +4 | false | 4 |
| Zn | Zn$+2 | [Zn]2+ | +2 | true | 2 |
| Zn | Zn$+0 | Zn(s) | +0 | false | 2 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [meso-Dithiotartaric acid] | O=C(O)[C@@H](S)[C@@H](S)C(=O)O | C | [0, 0, 3, 3] | true |
| L1 | [meso-Dithiotartaric acid] | O=C(O)[C@@H](S)[C@@H](S)C(=O)O | O | [-2, -2, -2, -2] | false |
| L1 | [meso-Dithiotartaric acid] | O=C(O)[C@@H](S)[C@@H](S)C(=O)O | S | [-2, -2] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Ca$+2 | [Ca]2+ | metal | [Ca]2+(aq) | +0.0000 | R1 | Ca | +2 | true |
| Ca$+0 | Ca(s) | metal | Ca(s)(aq/s) | +553.0411 | RULE 1 | Ca | +0 | false |
| Pb$+2 | [Pb]2+ | metal | [Pb]2+(aq) | +0.0000 | R1 | Pb | +2 | true |
| Pb$+0 | Pb(s) | metal | Pb(s)(aq/s) | +24.3090 | RULE 1 | Pb | +0 | false |
| Pb$+3 | Pb(+3) | metal | Pb(+3)(aq/s) | +348.4142 | RULE 1 | Pb | +3 | false |
| Pb$+4 | Pb(+4) | metal | Pb(+4)(aq/s) | +326.8122 | RULE 1 | Pb | +4 | false |
| Zn$+2 | [Zn]2+ | metal | [Zn]2+(aq) | +0.0000 | R1 | Zn | +2 | true |
| Zn$+0 | Zn(s) | metal | Zn(s)(aq/s) | +147.2099 | RULE 1 | Zn | +0 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [meso-Dithiotartaric acid] | ligand_canonical | [[H]4[L1]] | +0.0000 | R4 | *** | -4 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [meso-Dithiotartaric acid] | [L1] -> [[H]4[L1]] | 4 | 4 | +4.0000 | +22.8308 | exact |  |

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
| *** + [meso-Dithiotartaric acid] | 25.0 | 0.1 | *** | 4 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Pb]2+ + [meso-Dithiotartaric acid] | 25.0 | 0.1~3 | 21600 | 8 |
| [Zn]2+ + [meso-Dithiotartaric acid] | 20.0~25.0 | 0~0.1 | 21597 | 16 |
| [Ca]2+ + *** | 25.0 | 0~0.1 | *** | 2 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]4[L1]].[z+0] | [[H]4[L1]].[z+0] | [H4meso-Dithiotartaric acid] | +0 | aqueous | +4.0000 | -22.8308 | +0.0000 | +0.0000 | [[H]4[L1]]:+1 | SRD-46 | true | *** |
| [[H]3[L1]].[z-1] | [[H]3[L1]].[z-1] | [H3meso-Dithiotartaric acid]- | -1 | aqueous | +1.6000 | -9.1323 | +13.6985 | +13.6985 | [[H]3[L1]]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z-2] | [[H]2[L1]].[z-2] | [H2meso-Dithiotartaric acid]2- | -2 | aqueous | -1.8600 | +10.6163 | +33.4471 | +33.4471 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z-3] | [[H][L1]].[z-3] | [Hmeso-Dithiotartaric acid]3- | -3 | aqueous | -11.5000 | +65.6385 | +88.4692 | +88.4692 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z-4] | [L1].[z-4] | [meso-Dithiotartaric acid] | -4 | aqueous | +0.0000 | -0.0000 | +22.8308 | +22.8308 | [L1]:+1 | SRD-46 | true | *** |
| Ca$+2.z+2 | Atlas | Ca2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ca$+2:+1 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1] Atlas: Ca2+ |
| [Ca$+2].[z+2] | [M3].[z+2] | [Ca]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ca$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Ca$+2:1] *** |
| [Ca$+2].[OH].[z+1] | [M3].[OH].[z+1] | [Ca(OH)]+ | +1 | aqueous | -13.0400 | +74.4283 | +74.4283 | +74.4283 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| Pb$+2.z+2 | Atlas | Pb2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Pb$+2:+1 | Atlas | false | [DUPLICATE GROUP: Pb$+2:1] Atlas: Pb2+ |
| [Pb$+2].[z+2] | [M1].[z+2] | [Pb]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Pb$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Pb$+2:1] *** |
| [Pb$+2]2.[OH].[z+3] | [M1]2.[OH].[z+3] | [Pb2(OH)]3+ | +3 | aqueous | -6.4000 | +36.5292 | +36.5292 | +36.5292 | [Pb$+2]:+2, [OH]:+1 | SRD-46 | true | *** |
| [Pb$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Pb(OH)]+ | +1 | aqueous | -8.0000 | +45.6615 | +45.6615 | +45.6615 | [Pb$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Pb$+2].[OH]2.[z+0] | [M1].[OH]2.[z+0] | [Pb(OH)2] | +0 | aqueous | -17.1000 | +97.6015 | +97.6015 | +97.6015 | [Pb$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Pb$+2.OH3.z-1 | Atlas | [HPbO2]- | -1 | aqueous | -27.9950 | +159.7870 | +159.7870 | +159.7870 | Pb$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Pb$+2:1 H:-3] Atlas: [HPbO2]- |
| [Pb$+2].[OH]3.[z-1] | [M1].[OH]3.[z-1] | [Pb(OH)3]- | -1 | aqueous | -28.1000 | +160.3861 | +160.3861 | +160.3861 | [Pb$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Pb$+2:1 H:-3] *** |
| [Pb$+2]4.[OH]4.[z+4] | [M1]4.[OH]4.[z+4] | [Pb4(OH)4]4+ | +4 | aqueous | -18.5000 | +105.5923 | +105.5923 | +105.5923 | [Pb$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Pb$+2]3.[OH]4.[z+2] | [M1]3.[OH]4.[z+2] | [Pb3(OH)4]2+ | +2 | aqueous | -23.9000 | +136.4138 | +136.4138 | +136.4138 | [Pb$+2]:+3, [OH]:+4 | SRD-46 | true | *** |
| [Pb$+2]6.[OH]8.[z+4] | [M1]6.[OH]8.[z+4] | [Pb6(OH)8]4+ | +4 | aqueous | -40.7000 | +232.3031 | +232.3031 | +232.3031 | [Pb$+2]:+6, [OH]:+8 | SRD-46 | true | *** |
| [Pb$+2].[L1].[z-2] | [M1].[L1].[z-2] | [Pb(meso)]2- | -2 | aqueous | -5.5600 | +31.7348 | +54.5655 | +54.5655 | [Pb$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| Pb$+4.z+4 | Atlas | Pb4+ | +4 | aqueous | -0.0000 | +0.0000 | +0.0000 | +326.8122 | Pb$+4:+1 | Atlas | false | Atlas: Pb4+ |
| Pb$+4.OH6.z-2 | Atlas | [PbO3]2- | -2 | aqueous | -23.0396 | +131.5032 | +131.5032 | +458.3154 | Pb$+4:+1 H:-6 | Atlas | false | Atlas: [PbO3]2- |
| Pb$+4.OH8.z-4 | Atlas | [PbO4]4- | -4 | aqueous | -63.8035 | +364.1712 | +364.1712 | +690.9834 | Pb$+4:+1 H:-8 | Atlas | false | Atlas: [PbO4]4- |
| Zn$+2.z+2 | Atlas | Zn2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Zn$+2:+1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1] Atlas: Zn2+ |
| [Zn$+2].[z+2] | [M2].[z+2] | [Zn]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Zn$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1] *** |
| [Zn$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Zn(OH)]+ | +1 | aqueous | -9.3000 | +53.0815 | +53.0815 | +53.0815 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-1] *** |
| Zn$+2.OH.z+1 | Atlas | [ZnOH]+ | +1 | aqueous | -16.0346 | +91.5208 | +91.5208 | +91.5208 | Zn$+2:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-1] Atlas: [ZnOH]+ |
| [Zn$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Zn(OH)2] | +0 | aqueous | -15.8000 | +90.1815 | +90.1815 | +90.1815 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Zn$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Zn(OH)3]- | -1 | aqueous | -28.1000 | +160.3861 | +160.3861 | +160.3861 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-3] *** |
| Zn$+2.OH3.z-1 | Atlas | [HZnO2]- | -1 | aqueous | -28.7823 | +164.2806 | +164.2806 | +164.2806 | Zn$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-3] Atlas: [HZnO2]- |
| Zn$+2.OH4.z-2 | Atlas | [ZnO2]2- | -2 | aqueous | -33.4005 | +190.6398 | +190.6398 | +190.6398 | Zn$+2:+1 H:-4 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-4] Atlas: [ZnO2]2- |
| [Zn$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Zn(OH)4]2- | -2 | aqueous | -40.5000 | +231.1615 | +231.1615 | +231.1615 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-4] *** |
| [Zn$+2].[[H][L1]].[z-1] | [M2].[[H][L1]].[z-1] | [Zn(meso)H]- | -1 | aqueous | -1.6600 | +9.4748 | +32.3055 | +32.3055 | [Zn$+2]:+1, [[H][L1]]:+1 | SRD-46 | true | *** |
| [Zn$+2]2.[L1]2.[H].[z-3] | [M2]2.[L1]2.[H].[z-3] | [Zn2(meso)2H]3- | -3 | aqueous | -6.4200 | +36.6434 | +82.3049 | +82.3049 | [Zn$+2]:+2, [L1]:+2, [H]:+1 | SRD-46 | true | *** |
| [Zn$+2]2.[L1]2.[z-4] | [M2]2.[L1]2.[z-4] | [Zn2(meso)2]4- | -4 | aqueous | -12.3200 | +70.3188 | +115.9803 | +115.9803 | [Zn$+2]:+2, [L1]:+2 | SRD-46 | true | *** |
| [Zn$+2].[L1]2.[z-6] | [M2].[L1]2.[z-6] | [Zn(meso)2]6- | -6 | aqueous | -26.8500 | +153.2515 | +198.9131 | +198.9131 | [Zn$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Zn$+2]2.[OH].[L1]2.[z-5] | [M2]2.[OH].[L1]2.[z-5] | [Zn2(meso)2(OH)]5- | -5 | aqueous | -22.6200 | +129.1080 | +174.7695 | +174.7695 | [Zn$+2]:+2, [OH]:+1, [L1]:+2 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Ca$+2].[OH]2.[z+0]_(s) | [M3].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | +0 | dissolution | -22.8100 | +130.1925 | +130.1925 | +130.1925 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ca$+2:1 H:-2] *** |
| Ca$+2.OH2.z+0(s) | Atlas | Ca(OH)2 | +0 | dissolution | -22.8930 | +130.6663 | +130.6663 | +130.6663 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: Ca(OH)2 |
| Ca$+2.OH2.z+0(s) | Atlas | CaO | +0 | dissolution | -32.5985 | +186.0625 | +186.0625 | +186.0625 | Ca$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ca$+2:1 H:-2] Atlas: CaO |
| Ca$+2.OH4.z+0(s) | Atlas | CaO2 | +0 | dissolution | -75.1811 | +429.1110 | +429.1110 | +429.1110 | Ca$+2:+1 H:-4 | Atlas | false | Atlas: CaO2 |
| Ca$+0.z+0(s) | Atlas | Ca | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +553.0411 | Ca$+0:+1 | Atlas | false | Atlas: Ca |
| Pb$+2(3).OH8.z+0(s) | Atlas | Pb3O4 | +0 | dissolution | -71.2446 | +406.6430 | +406.6430 | +406.6430 | Pb$+2:+3 H:-8 | Atlas | false | Atlas: Pb3O4 |
| Pb$+3(2).OH6.z+0(s) | Atlas | Pb2O3 | +0 | dissolution | +61.0428 | -348.4142 | -348.4142 | +348.4142 | Pb$+3:+2 H:-6 | Atlas | false | Atlas: Pb2O3 |
| Pb$+4.OH4.z+0(s) | Atlas | PbO2 | +0 | dissolution | +8.2541 | -47.1118 | -47.1118 | +279.7004 | Pb$+4:+1 H:-4 | Atlas | false | Atlas: PbO2 |
| Pb$+0.z+0(s) | Atlas | Pb | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +24.3090 | Pb$+0:+1 | Atlas | false | Atlas: Pb |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (inactive) | +0 | dissolution | -9.6132 | +54.8690 | +54.8690 | +54.8690 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (inactive) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (active) | +0 | dissolution | -10.5368 | +60.1408 | +60.1408 | +60.1408 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (active) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (alpha) | +0 | dissolution | -10.7230 | +61.2036 | +61.2036 | +61.2036 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (alpha) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (epsilon) | +0 | dissolution | -10.9502 | +62.5006 | +62.5006 | +62.5006 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (epsilon) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (gamma) | +0 | dissolution | -11.1797 | +63.8102 | +63.8102 | +63.8102 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (gamma) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (beta) | +0 | dissolution | -11.3101 | +64.5549 | +64.5549 | +64.5549 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (beta) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO | +0 | dissolution | -11.5191 | +65.7474 | +65.7474 | +65.7474 | Zn$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO |
| [Zn$+2].[OH]2.[[z+0(s)[1]]] | [M2].[OH]2.[[z+0(s)[1]]] | [ZnO](s) | +0 | dissolution | -12.0400 | +68.7206 | +68.7206 | +68.7206 | [Zn$+2]:+1, [H]:-2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[2]]] | [M2].[OH]2.[[z+0(s)[2]]] | [Zn(OH)2(s,epsilon)] | +0 | dissolution | -12.2300 | +69.8051 | +69.8051 | +69.8051 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (amorphous) | +0 | dissolution | -12.2492 | +69.9146 | +69.9146 | +69.9146 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (amorphous) |
| [Zn$+2].[OH]2.[[z+0(s)[3]]] | [M2].[OH]2.[[z+0(s)[3]]] | [Zn(OH)2(s,gamma)] | +0 | dissolution | -12.4400 | +71.0037 | +71.0037 | +71.0037 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[4]]] | [M2].[OH]2.[[z+0(s)[4]]] | [Zn(OH)2(s,beta1)] | +0 | dissolution | -12.4600 | +71.1178 | +71.1178 | +71.1178 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[5]]] | [M2].[OH]2.[[z+0(s)[5]]] | [Zn(OH)2(s,beta2)] | +0 | dissolution | -12.5000 | +71.3461 | +71.3461 | +71.3461 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[6]]] | [M2].[OH]2.[[z+0(s)[6]]] | [Zn(OH)2(s,delta)] | +0 | dissolution | -12.5500 | +71.6315 | +71.6315 | +71.6315 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[7]]] | [M2].[OH]2.[[z+0(s)[7]]] | [Zn(OH)2(s,am)] | +0 | dissolution | -13.1800 | +75.2274 | +75.2274 | +75.2274 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+0.z+0(s) | Atlas | Zn | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +147.2099 | Zn$+0:+1 | Atlas | false | Atlas: Zn |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
