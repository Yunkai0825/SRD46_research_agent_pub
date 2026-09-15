# Free Energy Analysis Card

**System**: H, Co, Ni, Cu / Glycine, Hydroxide ion
**Metals**: [Co]3+, [Co]2+, [Ni]2+, [Cu]2+, [Cu]+
**Ligands**: [Glycine]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Co$+2 | Metal component: [Co]2+ |
| Co$+0 | Metal component from Atlas: Co(s) |
| Co$+3 | Metal component: [Co]3+ |
| Co$+4 | Metal component from Atlas: Co(+4) |
| Cu$+1 | Metal component: [Cu]+ |
| Cu$+0 | Metal component from Atlas: Cu(s) |
| Cu$+2 | Metal component: [Cu]2+ |
| Ni$+2 | Metal component: [Ni]2+ |
| Ni$+0 | Metal component from Atlas: Ni(s) |
| Ni$+3 | Metal component from Atlas: Ni(+3) |
| Ni$+4 | Metal component from Atlas: Ni(+4) |
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
| Cu$+1 | [Cu]+ | +1 | Not defined | NIST SRD-46 | metal_42 |
| Cu$+0 | Cu(s) | +0 | 0 | Pourbaix Atlas |  |
| Cu$+2 | [Cu]2+ | +2 | Not defined | NIST SRD-46 | metal_41 |
| Ni$+2 | [Ni]2+ | +2 | Not defined | NIST SRD-46 | metal_112 |
| Ni$+0 | Ni(s) | +0 | 0 | Pourbaix Atlas |  |
| Ni$+3 | Ni(+3) | +3 | 0 | Pourbaix Atlas |  |
| Ni$+4 | Ni(+4) | +4 | 0 | Pourbaix Atlas |  |

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
| Cu | Cu$+1 | [Cu]+ | +1 | true | 3 |
| Cu | Cu$+0 | Cu(s) | +0 | false | 3 |
| Cu | Cu$+2 | [Cu]2+ | +2 | false | 3 |
| Ni | Ni$+2 | [Ni]2+ | +2 | true | 4 |
| Ni | Ni$+0 | Ni(s) | +0 | false | 4 |
| Ni | Ni$+3 | Ni(+3) | +3 | false | 4 |
| Ni | Ni$+4 | Ni(+4) | +4 | false | 4 |

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
| Cu$+1 | [Cu]+ | metal | [Cu]+(aq) | +0.0000 | R1 | Cu | +1 | true |
| Cu$+0 | Cu(s) | metal | Cu(s)(aq/s) | -50.2080 | RULE 1 | Cu | +0 | false |
| Cu$+2 | [Cu]2+ | metal | [Cu]2+(aq) | +14.7695 | R1 | Cu | +2 | false |
| Ni$+2 | [Ni]2+ | metal | [Ni]2+(aq) | +0.0000 | R1 | Ni | +2 | true |
| Ni$+0 | Ni(s) | metal | Ni(s)(aq/s) | +45.6056 | RULE 1 | Ni | +0 | false |
| Ni$+3 | Ni(+3) | metal | Ni(+3)(aq/s) | +570.2374 | RULE 1 | Ni | +3 | false |
| Ni$+4 | Ni(+4) | metal | Ni(+4)(aq/s) | +542.0372 | RULE 1 | Ni | +4 | false |
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
| [Ni]2+ + [Glycine] | 25.0 | 0~0.1 | 77 | 8 |
| [Cu]2+ + [Glycine] | 25.0 | 0~0.1 | 86 | 8 |
| [Cu]+ + [Glycine] | 25.0 | 0~0.1 | 100 | 2 |

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
| Cu$+1.z+1 | Atlas | Cu+ | +1 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Cu$+1:+1 | Atlas | false | [DUPLICATE GROUP: Cu$+1:1] Atlas: Cu+ |
| [Cu$+1].[z+1] | [M5].[z+1] | [Cu]+ | +1 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Cu$+1]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1] *** |
| [Cu$+1].[L1]2.[z-1] | [M5].[L1]2.[z-1] | [Cu(Glyc)2]- | -1 | aqueous | +10.1000 | -57.6477 | +51.5975 | +51.5975 | [Cu$+1]:+1, [L1]:+2 | SRD-46 | true | *** |
| Cu$+2.z+2 | Atlas | Cu2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +14.7695 | Cu$+2:+1 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1] Atlas: Cu2+ |
| [Cu$+2].[z+2] | [M4].[z+2] | [Cu]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +14.7695 | [Cu$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1] *** |
| [Cu$+2].[OH].[z+1] | [M4].[OH].[z+1] | [Cu(OH)]+ | +1 | aqueous | -7.9000 | +45.0908 | +45.0908 | +59.8603 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Cu$+2]2.[OH]2.[z+2] | [M4]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | +2 | aqueous | -11.2000 | +63.9261 | +63.9261 | +93.4651 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true | *** |
| [Cu$+2].[OH]2.[z+0] | [M4].[OH]2.[z+0] | [Cu(OH)2] | +0 | aqueous | -16.2000 | +92.4646 | +92.4646 | +107.2341 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Cu$+2.OH3.z-1 | Atlas | [HCuO2]- | -1 | aqueous | -26.7048 | +152.4231 | +152.4231 | +167.1926 | Cu$+2:+1 H:-3 | Atlas | true | Atlas: [HCuO2]- |
| [Cu$+2]3.[OH]4.[z+2] | [M4]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | +2 | aqueous | -22.5000 | +128.4231 | +128.4231 | +172.7316 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true | *** |
| Cu$+2.OH4.z-2 | Atlas | [CuO2]2- | -2 | aqueous | -39.8410 | +227.4004 | +227.4004 | +242.1699 | Cu$+2:+1 H:-4 | Atlas | true | Atlas: [CuO2]2- |
| [Cu$+2].[L1].[z+1] | [M4].[L1].[z+1] | [Cu(Glyc)]+ | +1 | aqueous | +8.1900 | -46.7460 | +7.8766 | +22.6461 | [Cu$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Cu$+2].[L1]2.[z+0] | [M4].[L1]2.[z+0] | [Cu(Glyc)2] | +0 | aqueous | +15.1000 | -86.1861 | +23.0591 | +37.8286 | [Cu$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| Ni$+2.z+2 | Atlas | Ni2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Ni$+2:+1 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1] Atlas: Ni2+ |
| [Ni$+2].[z+2] | [M3].[z+2] | [Ni]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Ni$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1] *** |
| [Ni$+2].[OH].[z+1] | [M3].[OH].[z+1] | [Ni(OH)]+ | +1 | aqueous | -10.4000 | +59.3600 | +59.3600 | +59.3600 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Ni$+2].[OH]2.[z+0] | [M3].[OH]2.[z+0] | [Ni(OH)2] | +0 | aqueous | -19.0000 | +108.4461 | +108.4461 | +108.4461 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| Ni$+2.OH3.z-1 | Atlas | [HNiO2]- | -1 | aqueous | -29.7836 | +169.9959 | +169.9959 | +169.9959 | Ni$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-3] Atlas: [HNiO2]- |
| [Ni$+2].[OH]3.[z-1] | [M3].[OH]3.[z-1] | [Ni(OH)3]- | -1 | aqueous | -30.0000 | +171.2308 | +171.2308 | +171.2308 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1 H:-3] *** |
| [Ni$+2]4.[OH]4.[z+4] | [M3]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | +4 | aqueous | -27.7000 | +158.1031 | +158.1031 | +158.1031 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true | *** |
| [Ni$+2].[L1].[z+1] | [M3].[L1].[z+1] | [Ni(Glyc)]+ | +1 | aqueous | +5.7400 | -32.7622 | +21.8605 | +21.8605 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true | *** |
| [Ni$+2].[L1]2.[z+0] | [M3].[L1]2.[z+0] | [Ni(Glyc)2] | +0 | aqueous | +10.5800 | -60.3874 | +48.8578 | +48.8578 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true | *** |
| [Ni$+2].[L1]3.[z-1] | [M3].[L1]3.[z-1] | [Ni(Glyc)3]- | -1 | aqueous | +14.1000 | -80.4785 | +83.3894 | +83.3894 | [Ni$+2]:+1, [L1]:+3 | SRD-46 | true | *** |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Co$+2.OH2.z+0(s) | Atlas | CoO hyd. (Co(OH)2) | +0 | dissolution | +28.9626 | -165.3098 | -165.3098 | -165.3098 | Co$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Co$+2:1 H:-2] Atlas: CoO hyd. (Co(OH)2) |
| [Co$+2].[OH]2.[z+0]_(s) | [M2].[OH]2.[z+0]_(s) | [Co(OH)2](s) | +0 | dissolution | -13.1000 | +74.7708 | +74.7708 | +74.7708 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Co$+2:1 H:-2] *** |
| Co$+2.OH2.z+0(s) | Atlas | CoO | +0 | dissolution | -15.0201 | +85.7302 | +85.7302 | +85.7302 | Co$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Co$+2:1 H:-2] Atlas: CoO |
| Co$+2(3).OH8.z+0(s) | Atlas | Co3O4 | +0 | dissolution | -71.3436 | +407.2078 | +407.2078 | +407.2078 | Co$+2:+3 H:-8 | Atlas | true | Atlas: Co3O4 |
| [Co$+3].[OH]3.[z+0]_(s) | [M1].[OH]3.[z+0]_(s) | [Co(OH)3](s) | +0 | dissolution | +2.3000 | -13.1277 | -13.1277 | +161.3451 | [Co$+3]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Co$+3:1 H:-3] *** |
| Co$+3(2).OH6.z+0(s) | Atlas | Co2O3 hyd. (Co(OH)3) | +0 | dissolution | +2.0965 | -11.9662 | -11.9662 | +336.9794 | Co$+3:+2 H:-6 | Atlas | false | [DUPLICATE GROUP: Co$+3:1 H:-3] Atlas: Co2O3 hyd. (Co(OH)3) |
| Co$+4.OH4.z+0(s) | Atlas | CoO2 | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +478.3986 | Co$+4:+1 H:-4 | Atlas | true | Atlas: CoO2 |
| Co$+0.z+0(s) | Atlas | Co | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +53.5552 | Co$+0:+1 | Atlas | true | Atlas: Co |
| [Cu$+1].[OH].[z+0]_(s) | [M5].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | -3.9954 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true | [DUPLICATE GROUP: Cu$+1:1 H:-1] *** |
| Cu$+1(2).OH2.z+0(s) | Atlas | Cu2O | +0 | dissolution | -0.5205 | +2.9706 | +2.9706 | +2.9706 | Cu$+1:+2 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+1:1 H:-1] Atlas: Cu2O |
| [Cu$+2].[OH]2.[[z+0(s)[1]]] | [M4].[OH]2.[[z+0(s)[1]]] | [CuO](s) | +0 | dissolution | -7.6500 | +43.6638 | +43.6638 | +58.4333 | [Cu$+2]:+1, [H]:-2 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] *** |
| Cu$+2.OH2.z+0(s) | Atlas | CuO | +0 | dissolution | -7.8876 | +45.0199 | +45.0199 | +59.7894 | Cu$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: CuO |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [M4].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | +0 | dissolution | -8.6800 | +49.5428 | +49.5428 | +64.3123 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Cu$+2:1 H:-2] *** |
| Cu$+2.OH2.z+0(s) | Atlas | Cu(OH)2 | +0 | dissolution | -9.1997 | +52.5092 | +52.5092 | +67.2787 | Cu$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Cu$+2:1 H:-2] Atlas: Cu(OH)2 |
| Cu$+0.z+0(s) | Atlas | Cu | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | -50.2080 | Cu$+0:+1 | Atlas | true | Atlas: Cu |
| Ni$+2.OH2.z+0(s) | Atlas | Ni(OH)2 | +0 | dissolution | -11.7141 | +66.8603 | +66.8603 | +66.8603 | Ni$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Ni$+2:1 H:-2] Atlas: Ni(OH)2 |
| Ni$+2.OH2.z+0(s) | Atlas | NiO | +0 | dissolution | -11.9413 | +68.1574 | +68.1574 | +68.1574 | Ni$+2:+1 H:-2 | Atlas | true | [DUPLICATE GROUP: Ni$+2:1 H:-2] Atlas: NiO |
| [Ni$+2].[OH]2.[z+0]_(s) | [M3].[OH]2.[z+0]_(s) | [Ni(OH)2](s) | +0 | dissolution | -12.8000 | +73.0585 | +73.0585 | +73.0585 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Ni$+2:1 H:-2] *** |
| Ni$+2(3).OH8.z+0(s) | Atlas | Ni3O4.2H2O | +0 | dissolution | -151.0072 | +861.9040 | +861.9040 | +861.9040 | Ni$+2:+3 H:-8 | Atlas | true | Atlas: Ni3O4.2H2O |
| Ni$+3(2).OH6.z+0(s) | Atlas | Ni2O3.H2O | +0 | dissolution | +99.9067 | -570.2374 | -570.2374 | +570.2374 | Ni$+3:+2 H:-6 | Atlas | true | Atlas: Ni2O3.H2O |
| Ni$+4.OH4.z+0(s) | Atlas | NiO2.2H2O | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +542.0372 | Ni$+4:+1 H:-4 | Atlas | true | Atlas: NiO2.2H2O |
| Ni$+0.z+0(s) | Atlas | Ni | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +45.6056 | Ni$+0:+1 | Atlas | true | Atlas: Ni |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
