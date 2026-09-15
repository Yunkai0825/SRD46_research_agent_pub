# Free Energy Analysis Card

**System**: H, Cu, Ni, Zn / Ethylenediamine, Hydroxide ion
**Metals**: [Cu]2+, [Cu]+, [Ni]2+, [Zn]2+
**Ligands**: [Ethylenediamine]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Cu$+1 | Metal component: [Cu]+ |
| Cu$+0 | Metal component from Atlas: Cu(s) |
| Cu$+2 | Metal component: [Cu]2+ |
| Ni$+2 | Metal component: [Ni]2+ |
| Ni$+0 | Metal component from Atlas: Ni(s) |
| Ni$+3 | Metal component from Atlas: Ni(+3) |
| Ni$+4 | Metal component from Atlas: Ni(+4) |
| Zn$+2 | Metal component: [Zn]2+ |
| Zn$+0 | Metal component from Atlas: Zn(s) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Ethylenediamine] |
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
| Cu$+1 | [Cu]+ | +1 | Not defined | NIST SRD-46 | metal_42 |
| Cu$+0 | Cu(s) | +0 | 0 | Pourbaix Atlas |  |
| Cu$+2 | [Cu]2+ | +2 | Not defined | NIST SRD-46 | metal_41 |
| Ni$+2 | [Ni]2+ | +2 | Not defined | NIST SRD-46 | metal_112 |
| Ni$+0 | Ni(s) | +0 | 0 | Pourbaix Atlas |  |
| Ni$+3 | Ni(+3) | +3 | 0 | Pourbaix Atlas |  |
| Ni$+4 | Ni(+4) | +4 | 0 | Pourbaix Atlas |  |
| Zn$+2 | [Zn]2+ | +2 | Not defined | NIST SRD-46 | metal_208 |
| Zn$+0 | Zn(s) | +0 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Ethylenediamine] | +0 | Not defined | [[L1]] | NIST SRD-46 | ligand_7029 | NCCN |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Cu | Cu$+1 | [Cu]+ | +1 | true | 3 |
| Cu | Cu$+0 | Cu(s) | +0 | false | 3 |
| Cu | Cu$+2 | [Cu]2+ | +2 | false | 3 |
| Ni | Ni$+2 | [Ni]2+ | +2 | true | 4 |
| Ni | Ni$+0 | Ni(s) | +0 | false | 4 |
| Ni | Ni$+3 | Ni(+3) | +3 | false | 4 |
| Ni | Ni$+4 | Ni(+4) | +4 | false | 4 |
| Zn | Zn$+2 | [Zn]2+ | +2 | true | 2 |
| Zn | Zn$+0 | Zn(s) | +0 | false | 2 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [Ethylenediamine] | NCCN | C | [-1, -1] | false |
| L1 | [Ethylenediamine] | NCCN | N | [-3, -3] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Cu$+1 | [Cu]+ | metal | [Cu]+(aq) | +0.0000 | R1 | Cu | +1 | true |
| Cu$+0 | Cu(s) | metal | Cu(s)(aq/s) | -50.2080 | RULE 1 | Cu | +0 | false |
| Cu$+2 | [Cu]2+ | metal | [Cu]2+(aq) | +14.7695 | R1 | Cu | +2 | false |
| Ni$+2 | [Ni]2+ | metal | [Ni]2+(aq) | +0.0000 | R1 | Ni | +2 | true |
| Ni$+0 | Ni(s) | metal | Ni(s)(aq/s) | +45.6056 | RULE 1 | Ni | +0 | false |
| Ni$+3 | Ni(+3) | metal | Ni(+3)(aq/s) | +570.2374 | RULE 1 | Ni | +3 | false |
| Ni$+4 | Ni(+4) | metal | Ni(+4)(aq/s) | +542.0372 | RULE 1 | Ni | +4 | false |
| Zn$+2 | [Zn]2+ | metal | [Zn]2+(aq) | +0.0000 | R1 | Zn | +2 | true |
| Zn$+0 | Zn(s) | metal | Zn(s)(aq/s) | +147.2099 | RULE 1 | Zn | +0 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Ethylenediamine] | ligand_canonical | [[L1]] | +0.0000 | R4 | *** | +0 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Ethylenediamine] | [L1] -> [[L1]] | 0 | 0 | +0.0000 | +0.0000 | exact | R4a: canonical_H=0; shift≡0 |

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
| *** + [Ethylenediamine] | 25.0 | 0.1 | *** | 2 |
| *** + *** | 25.0 | 0.1 | *** | 1 |
| [Cu]2+ + [Ethylenediamine] | 25.0 | 0~0.1 | 9598 | 8 |
| [Cu]+ + [Ethylenediamine] | 25.0 | 0~0.5 | 9615 | 2 |
| [Ni]2+ + [Ethylenediamine] | 25.0 | 0~0.1 | 9591 | 8 |
| [Zn]2+ + [Ethylenediamine] | 25.0 | 0~0.1 | 9625 | 14 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [[H]2[L1]].[z+2] | [[H]2[L1]].[z+2] | [H2Ethylenediamine]2+ | +2 | aqueous | +17.0300 | -97.2020 | -97.2020 | -97.2020 | [[H]2[L1]]:+1 | SRD-46 | true | *** |
| [[H][L1]].[z+1] | [[H][L1]].[z+1] | [HEthylenediamine]+ | +1 | aqueous | +9.9200 | -56.6203 | -56.6203 | -56.6203 | [[H][L1]]:+1 | SRD-46 | true | *** |
| [L1].[z+0] | [L1].[z+0] | [Ethylenediamine] | +0 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L1]:+1 | SRD-46 | true | *** |
| Cu$+1.z+1 | Atlas | Cu+ | +1 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Cu$+1:+1 | Atlas | false | [DUPLICATE GROUP: Cu$+1:1] Atlas: Cu+ |
| [Cu$+1].[z+1] | [M2].[z+1] | [Cu]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Cu$+1]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1] *** |
| [Cu$+1].[L1]2.[z+1] | [M2].[L1]2.[z+1] | [Cu(Ethy)2]+ | +1 | aqueous | +11.2000 | -63.9261 | -63.9261 | -63.9261 | [Cu$+1]:+1, [L1]:+2 | SRD-46 | false | *** |
| Cu$+2.z+2 | Atlas | Cu2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +14.7695 | Cu$+2:+1 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1] Atlas: Cu2+ |
| [Cu$+2].[z+2] | [M1].[z+2] | [Cu]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +14.7695 | [Cu$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1] *** |
| [Cu$+2].[OH].[z+1] | [M1].[OH].[z+1] | [Cu(OH)]+ | +1 | aqueous | -7.9000 | +45.0908 | +45.0908 | +59.8603 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Cu$+2]2.[OH]2.[z+2] | [M1]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | +2 | aqueous | -11.2000 | +63.9261 | +63.9261 | +93.4651 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true | *** |
| [Cu$+2].[OH]2.[z+0] | [M1].[OH]2.[z+0] | [Cu(OH)2] | +0 | aqueous | -16.2000 | +92.4646 | +92.4646 | +107.2341 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Cu$+2.OH3.z-1 | Atlas | [HCuO2]- | -1 | aqueous | -26.7048 | +152.4231 | +152.4231 | +167.1926 | Cu$+2:+1 H:-3 | Atlas | true | Atlas: [HCuO2]- |
| [Cu$+2]3.[OH]4.[z+2] | [M1]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | +2 | aqueous | -22.5000 | +128.4231 | +128.4231 | +172.7316 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true | *** |
| Cu$+2.OH4.z-2 | Atlas | [CuO2]2- | -2 | aqueous | -39.8410 | +227.4004 | +227.4004 | +242.1699 | Cu$+2:+1 H:-4 | Atlas | true | Atlas: [CuO2]2- |
| [Cu$+2].[L1]2.[z+2] | [M1].[L1]2.[z+2] | [Cu(Ethy)2]2+ | +2 | aqueous | +19.6000 | -111.8708 | -111.8708 | -97.1013 | [Cu$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Cu$+2].[L1].[z+2] | [M1].[L1].[z+2] | [Cu(Ethy)]2+ | +2 | aqueous | +10.4900 | -59.8737 | -59.8737 | -45.1042 | [Cu$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| Ni$+2.z+2 | Atlas | Ni2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ni$+2:+1 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1] Atlas: Ni2+ |
| [Ni$+2].[z+2] | [M3].[z+2] | [Ni]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ni$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1] *** |
| [Ni$+2].[OH].[z+1] | [M3].[OH].[z+1] | [Ni(OH)]+ | +1 | aqueous | -10.4000 | +59.3600 | +59.3600 | +59.3600 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Ni$+2].[OH]2.[z+0] | [M3].[OH]2.[z+0] | [Ni(OH)2] | +0 | aqueous | -19.0000 | +108.4461 | +108.4461 | +108.4461 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Ni$+2.OH3.z-1 | Atlas | [HNiO2]- | -1 | aqueous | -29.7836 | +169.9959 | +169.9959 | +169.9959 | Ni$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-3] Atlas: [HNiO2]- |
| [Ni$+2].[OH]3.[z-1] | [M3].[OH]3.[z-1] | [Ni(OH)3]- | -1 | aqueous | -30.0000 | +171.2308 | +171.2308 | +171.2308 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1 H:-3] *** |
| [Ni$+2]4.[OH]4.[z+4] | [M3]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | +4 | aqueous | -27.7000 | +158.1031 | +158.1031 | +158.1031 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Ni$+2].[L1]3.[z+2] | [M3].[L1]3.[z+2] | [Ni(Ethy)3]2+ | +2 | aqueous | +17.5100 | -99.9417 | -99.9417 | -99.9417 | [Ni$+2]:+1, [L1]:+3 | SRD-46 | true | *** |
| [Ni$+2].[L1]2.[z+2] | [M3].[L1]2.[z+2] | [Ni(Ethy)2]2+ | +2 | aqueous | +13.4400 | -76.7114 | -76.7114 | -76.7114 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Ni$+2].[L1].[z+2] | [M3].[L1].[z+2] | [Ni(Ethy)]2+ | +2 | aqueous | +7.3000 | -41.6662 | -41.6662 | -41.6662 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| Zn$+2.z+2 | Atlas | Zn2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Zn$+2:+1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1] Atlas: Zn2+ |
| [Zn$+2].[z+2] | [M4].[z+2] | [Zn]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Zn$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1] *** |
| [Zn$+2].[OH].[z+1] | [M4].[OH].[z+1] | [Zn(OH)]+ | +1 | aqueous | -9.3000 | +53.0815 | +53.0815 | +53.0815 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-1] *** |
| Zn$+2.OH.z+1 | Atlas | [ZnOH]+ | +1 | aqueous | -16.0346 | +91.5208 | +91.5208 | +91.5208 | Zn$+2:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-1] Atlas: [ZnOH]+ |
| [Zn$+2].[OH]2.[z+0] | [M4].[OH]2.[z+0] | [Zn(OH)2] | +0 | aqueous | -15.8000 | +90.1815 | +90.1815 | +90.1815 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Zn$+2].[OH]3.[z-1] | [M4].[OH]3.[z-1] | [Zn(OH)3]- | -1 | aqueous | -28.1000 | +160.3861 | +160.3861 | +160.3861 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-3] *** |
| Zn$+2.OH3.z-1 | Atlas | [HZnO2]- | -1 | aqueous | -28.7823 | +164.2806 | +164.2806 | +164.2806 | Zn$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-3] Atlas: [HZnO2]- |
| Zn$+2.OH4.z-2 | Atlas | [ZnO2]2- | -2 | aqueous | -33.4005 | +190.6398 | +190.6398 | +190.6398 | Zn$+2:+1 H:-4 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-4] Atlas: [ZnO2]2- |
| [Zn$+2].[OH]4.[z-2] | [M4].[OH]4.[z-2] | [Zn(OH)4]2- | -2 | aqueous | -40.5000 | +231.1615 | +231.1615 | +231.1615 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-4] *** |
| [Zn$+2].[L1]3.[z+2] | [M4].[L1]3.[z+2] | [Zn(Ethy)3]2+ | +2 | aqueous | +13.0000 | -74.2000 | -74.2000 | -74.2000 | [Zn$+2]:+1, [L1]:+3 | SRD-46 | true | *** |
| [Zn$+2].[L1]2.[z+2] | [M4].[L1]2.[z+2] | [Zn(Ethy)2]2+ | +2 | aqueous | +10.6400 | -60.7298 | -60.7298 | -60.7298 | [Zn$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Zn$+2].[L1].[z+2] | [M4].[L1].[z+2] | [Zn(Ethy)]2+ | +2 | aqueous | +5.6900 | -32.4768 | -32.4768 | -32.4768 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [Cu$+1].[OH].[z+0]_(s) | [M2].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | -3.9954 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1 H:-1] *** |
| Cu$+1(2).OH2.z+0(s) | Atlas | Cu2O | +0 | dissolution | -0.5205 | +2.9706 | +2.9706 | +2.9706 | Cu$+1:+2 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+1:1 H:-1] Atlas: Cu2O |
| [Cu$+2].[OH]2.[[z+0(s)[1]]] | [M1].[OH]2.[[z+0(s)[1]]] | [CuO](s) | +0 | dissolution | -7.6500 | +43.6638 | +43.6638 | +58.4333 | [Cu$+2]:+1, [H]:-2 | SRD-46 | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] *** |
| Cu$+2.OH2.z+0(s) | Atlas | CuO | +0 | dissolution | -7.8876 | +45.0199 | +45.0199 | +59.7894 | Cu$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: CuO |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [M1].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | +0 | dissolution | -8.6800 | +49.5428 | +49.5428 | +64.3123 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] *** |
| Cu$+2.OH2.z+0(s) | Atlas | Cu(OH)2 | +0 | dissolution | -9.1997 | +52.5092 | +52.5092 | +67.2787 | Cu$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: Cu(OH)2 |
| Cu$+0.z+0(s) | Atlas | Cu | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | -50.2080 | Cu$+0:+1 | Atlas | false | Atlas: Cu |
| Ni$+2.OH2.z+0(s) | Atlas | Ni(OH)2 | +0 | dissolution | -11.7141 | +66.8603 | +66.8603 | +66.8603 | Ni$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-2] Atlas: Ni(OH)2 |
| Ni$+2.OH2.z+0(s) | Atlas | NiO | +0 | dissolution | -11.9413 | +68.1574 | +68.1574 | +68.1574 | Ni$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-2] Atlas: NiO |
| [Ni$+2].[OH]2.[z+0]_(s) | [M3].[OH]2.[z+0]_(s) | [Ni(OH)2](s) | +0 | dissolution | -12.8000 | +73.0585 | +73.0585 | +73.0585 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1 H:-2] *** |
| Ni$+2(3).OH8.z+0(s) | Atlas | Ni3O4.2H2O | +0 | dissolution | -151.0072 | +861.9040 | +861.9040 | +861.9040 | Ni$+2:+3 H:-8 | Atlas | false | Atlas: Ni3O4.2H2O |
| Ni$+3(2).OH6.z+0(s) | Atlas | Ni2O3.H2O | +0 | dissolution | +99.9067 | -570.2374 | -570.2374 | +570.2374 | Ni$+3:+2 H:-6 | Atlas | false | Atlas: Ni2O3.H2O |
| Ni$+4.OH4.z+0(s) | Atlas | NiO2.2H2O | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +542.0372 | Ni$+4:+1 H:-4 | Atlas | false | Atlas: NiO2.2H2O |
| Ni$+0.z+0(s) | Atlas | Ni | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +45.6056 | Ni$+0:+1 | Atlas | false | Atlas: Ni |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (inactive) | +0 | dissolution | -9.6132 | +54.8690 | +54.8690 | +54.8690 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (inactive) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO (active) | +0 | dissolution | -10.5368 | +60.1408 | +60.1408 | +60.1408 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO (active) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (alpha) | +0 | dissolution | -10.7230 | +61.2036 | +61.2036 | +61.2036 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (alpha) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (epsilon) | +0 | dissolution | -10.9502 | +62.5006 | +62.5006 | +62.5006 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (epsilon) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (gamma) | +0 | dissolution | -11.1797 | +63.8102 | +63.8102 | +63.8102 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (gamma) |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (beta) | +0 | dissolution | -11.3101 | +64.5549 | +64.5549 | +64.5549 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (beta) |
| Zn$+2.OH2.z+0(s) | Atlas | ZnO | +0 | dissolution | -11.5191 | +65.7474 | +65.7474 | +65.7474 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: ZnO |
| [Zn$+2].[OH]2.[[z+0(s)[1]]] | [M4].[OH]2.[[z+0(s)[1]]] | [ZnO](s) | +0 | dissolution | -12.0400 | +68.7206 | +68.7206 | +68.7206 | [Zn$+2]:+1, [H]:-2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[2]]] | [M4].[OH]2.[[z+0(s)[2]]] | [Zn(OH)2(s,epsilon)] | +0 | dissolution | -12.2300 | +69.8051 | +69.8051 | +69.8051 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| Zn$+2.OH2.z+0(s) | Atlas | Zn(OH)2 (amorphous) | +0 | dissolution | -12.2492 | +69.9146 | +69.9146 | +69.9146 | Zn$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] Atlas: Zn(OH)2 (amorphous) |
| [Zn$+2].[OH]2.[[z+0(s)[3]]] | [M4].[OH]2.[[z+0(s)[3]]] | [Zn(OH)2(s,gamma)] | +0 | dissolution | -12.4400 | +71.0037 | +71.0037 | +71.0037 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[4]]] | [M4].[OH]2.[[z+0(s)[4]]] | [Zn(OH)2(s,beta1)] | +0 | dissolution | -12.4600 | +71.1178 | +71.1178 | +71.1178 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[5]]] | [M4].[OH]2.[[z+0(s)[5]]] | [Zn(OH)2(s,beta2)] | +0 | dissolution | -12.5000 | +71.3461 | +71.3461 | +71.3461 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[6]]] | [M4].[OH]2.[[z+0(s)[6]]] | [Zn(OH)2(s,delta)] | +0 | dissolution | -12.5500 | +71.6315 | +71.6315 | +71.6315 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
| [Zn$+2].[OH]2.[[z+0(s)[7]]] | [M4].[OH]2.[[z+0(s)[7]]] | [Zn(OH)2(s,am)] | +0 | dissolution | -13.1800 | +75.2274 | +75.2274 | +75.2274 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | false | [DUPLICATE GROUP: Zn$+2:1 H:-2] *** |
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
