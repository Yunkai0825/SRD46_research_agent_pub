# Free Energy Analysis Card

**System**: H, Fe / Acetonitrile, Hydroxide ion
**Metals**: [Fe]3+, [Fe]2+
**Ligands**: [Acetonitrile]

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H⁺ (proton reference, pH-controlled) |
| Fe$+2 | Metal component: [Fe]2+ |
| Fe$+0 | Metal component from Atlas: Fe(s) |
| Fe$+3 | Metal component: [Fe]3+ |
| Fe$+6 | Metal component from Atlas: Fe(+6) |
| L0 | Always OH⁻ (derived from Kw) |
| L1 | Ligand component: [Acetonitrile] |
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
| Fe$+2 | [Fe]2+ | +2 | Not defined | NIST SRD-46 | metal_62 |
| Fe$+0 | Fe(s) | +0 | 0 | Pourbaix Atlas |  |
| Fe$+3 | [Fe]3+ | +3 | Not defined | NIST SRD-46 | metal_61 |
| Fe$+6 | Fe(+6) | +6 | 0 | Pourbaix Atlas |  |

### 2.3 Ligands

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| L1 | [Acetonitrile] | +0 | Not defined | [[L1]] | NIST SRD-46 | ligand_9825 | CC#N |

### 2.4 Metal Valence Alignment

Groups metals of the same element by oxidation state. The reference state (μ° ≡ 0) is the charge closest to 0, then +1, −1, +2, −2, …  Editable: change `is_reference` to reassign the reference oxidation state.

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Fe | Fe$+2 | [Fe]2+ | +2 | true | 4 |
| Fe | Fe$+0 | Fe(s) | +0 | false | 4 |
| Fe | Fe$+3 | [Fe]3+ | +3 | false | 4 |
| Fe | Fe$+6 | Fe(+6) | +6 | false | 4 |

### 2.5 Ligand Micro-Valence Analysis

Per-atom oxidation-state analysis of organic ligands (via electronegativity assignment). Dynamic atoms have multiple distinct OS values and may participate in redox reactions.

| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |
|-----------|-------------|--------|-------------|------------------|------------|
| L1 | [Acetonitrile] | CC#N | C | [-3, 3] | true |
| L1 | [Acetonitrile] | CC#N | N | [-3] | false |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| Fe$+2 | [Fe]2+ | metal | [Fe]2+(aq) | +0.0000 | R1 | Fe | +2 | true |
| Fe$+0 | Fe(s) | metal | Fe(s)(aq/s) | +84.9352 | RULE 1 | Fe | +0 | false |
| Fe$+3 | [Fe]3+ | metal | [Fe]3+(aq) | +74.3497 | R1 | Fe | +3 | false |
| Fe$+6 | Fe(+6) | metal | Fe(+6)(aq/s) | +566.4090 | RULE 1 | Fe | +6 | false |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |
| L1 | [Acetonitrile] | ligand_canonical | [[L1]] | +0.0000 | R4 | *** | +0 | *** |

### 3.2 Ligand Canonical Resolution

Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.
The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).
mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):
μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).

| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |
|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|
| L1 | [Acetonitrile] | [L1] -> [[L1]] | 0 | 0 | +0.0000 | +0.0000 | exact | R4a: canonical_H=0; shift≡0 |

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
| [Fe]3+ + *** | 25.0 | 0~0.1 | *** | 8 |
| [Fe]2+ + *** | 25.0 | 0~0.1 | *** | 5 |
| [Fe]3+ + [Acetonitrile] | 25.0 | 0.1 | *** | 3 |
| [Fe]2+ + [Acetonitrile] | 25.0 | 0.1 | *** | 1 |

## 5. Standard Chemical Potentials

All values in kJ/mol. Sorted by element (proton/ligand systems first), then valence (reference state first), ligand, and protonation (canonical HₓL reference first).

### 5.1 Aqueous Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| [H].[OH].[z+0] | [H].[OH].[z+0] | [?] | +0 | aqueous | -0.2200 | +1.2557 | +1.2557 | +1.2557 | [H]:+1, [OH]:+1 | SRD-46 | true | *** |
| [L1].[z+0] | [L1].[z+0] | [Acetonitrile] | +0 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [L1]:+1 | SRD-46 | true | *** |
| Fe$+2.z+2 | Atlas | Fe2+ | +2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +0.0000 | Fe$+2:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1] Atlas: Fe2+ |
| [Fe$+2].[z+2] | [M2].[z+2] | [Fe]2+ | +2 | aqueous | +0.0000 | -0.0000 | +0.0000 | +0.0000 | [Fe$+2]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1] *** |
| [Fe$+2].[OH].[z+1] | [M2].[OH].[z+1] | [Fe(OH)]+ | +1 | aqueous | -9.8000 | +55.9354 | +55.9354 | +55.9354 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true | *** |
| [Fe$+2].[OH]2.[z+0] | [M2].[OH]2.[z+0] | [Fe(OH)2] | +0 | aqueous | -35.5000 | +202.6231 | +202.6231 | +202.6231 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | *** |
| [Fe$+2].[OH]3.[z-1] | [M2].[OH]3.[z-1] | [Fe(OH)3]- | -1 | aqueous | -29.0000 | +165.5231 | +165.5231 | +165.5231 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-3] *** |
| Fe$+2.OH3.z-1 | Atlas | [HFeO2]- | -1 | aqueous | -31.5598 | +180.1338 | +180.1338 | +180.1338 | Fe$+2:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-3] Atlas: [HFeO2]- |
| [Fe$+2].[OH]4.[z-2] | [M2].[OH]4.[z-2] | [Fe(OH)4]2- | -2 | aqueous | -46.0000 | +262.5538 | +262.5538 | +262.5538 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+2].[L1].[z+2] | [M2].[L1].[z+2] | [Fe(Acet)]2+ | +2 | aqueous | -0.3000 | +1.7123 | +1.7123 | +1.7123 | [Fe$+2]:+1, [L1]:+1 | SRD46 query estimated values | true | {"eq_nodes":[{"assumptions":["(i) aqueous phase only — in real water–MeCN mixed solvent, apparent stability is much larger because bulk MeCN activity is high and the aqua-ion reference state shifts; the constants above apply to dilute aqueous conditions relevant to the aqueous-side Pourbaix.","(ii) No hydrolysis coupling.","(iii) High-spin octahedral [Fe(H2O)6−n(MeCN)n]²⁺; no spin-state change.","(iv) Ionic-strength adjustment from ammonia I=0 baseline to I=0.1 M is small (≤ 0.1 log unit)."],"beta_definition_id":812,"beta_definition_name":"[ML]/[M][L]","estimation_method":"Chemistry-informed route:\n1. Donor-strength calibration on Fe(II) itself using the two simplest neutral monodentate N donors in SRD-46: pyridine (vlm_38961: log K1 = 0.7; vlm_38962: log β2 = 0.9) and ammonia (vlm_73753: log K1 = 1.4; vlm_73761: log β2 = 2.25; vlm_73769: log β3 = 2.68; vlm_73777: log β4 = 2.75). Both are weak-binding, consistent with Fe(II) being poorly matched to neutral σ-donors in water.\n2. Basicity scaling: MeCN protonation pKa ≈ −10 vs. pyridine 5.24 (from auto-enriched bracket on ligand_7890) and NH3 9.26 (ligand_10103). MeCN is dramatically weaker as a Brønsted/σ base. Empirical σ-donor scaling for first-row M(II) suggests log K1(MeCN) is 0.5–1.5 units below pyridine.\n3. Cross-metal check: For Ag+, log K1(MeCN) = 0.42 (vlm_168275). Fe(II) has stronger aquation but no MeCN-favoring soft/π factor; expected to fall near or below Ag+ value, i.e. ≤ 0.\n4. Successive-K decrement: For weak monodentate binding in water, stepwise Kn typically decreases by ~0.5–0.8 log units per step (statistical + electrostatic), as seen in Fe(II)–NH3 (ΔlogK ≈ 0.5–0.6 per step at I=0).","evidence_citation_ids":[],"evidence_network_ids":[],"evidence_vlm_ids":["vlm_168275"],"rationale":"Now the key chemistry: Fe(II) is a borderline-hard 3d⁶ divalent cation, and acetonitrile is a very weak σ-donor with essentially no ligand basicity (pKa of CH3CNH+ ≈ –10). It is a much poorer donor to a hard/borderline first-row M(II) than pyridine or NH3. Even for soft d10 ions where MeCN binds reasonably (Ag+, Cu+, Pd2+), the acetonitrile constants are already tiny (Cu+ β2 = 4.35 in vlm_168274 is anomalously large due to soft-soft π-backbonding into the C≡N π*; Ag+ log K1 = 0.42 in vlm_168275; Pd2+ log K1 = 1.19 in vlm_168277 at I=1 M — and these are the *soft* metals that MeCN prefers).","source":"SRD46 query estimated values","uncertainty_log10":0.5}],"source":"SRD46 query estimated values"} |
| Fe$+3.z+3 | Atlas | Fe3+ | +3 | aqueous | -0.0000 | +0.0000 | +0.0000 | +74.3497 | Fe$+3:+1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1] Atlas: Fe3+ |
| [Fe$+3].[z+3] | [M1].[z+3] | [Fe]3+ | +3 | aqueous | +0.0000 | -0.0000 | +0.0000 | +74.3497 | [Fe$+3]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1] *** |
| Fe$+3.OH.z+2 | Atlas | [FeOH]2+ | +2 | aqueous | -2.4264 | +13.8490 | +13.8490 | +88.1987 | Fe$+3:+1 H:-1 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-1] Atlas: [FeOH]2+ |
| [Fe$+3].[OH].[z+2] | [M1].[OH].[z+2] | [Fe(OH)]2+ | +2 | aqueous | -2.7300 | +15.5820 | +15.5820 | +89.9317 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3]2.[OH]2.[z+4] | [M1]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | +4 | aqueous | -2.8600 | +16.3240 | +16.3240 | +165.0234 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-1] *** |
| [Fe$+3].[OH]2.[z+1] | [M1].[OH]2.[z+1] | [Fe(OH)2]+ | +1 | aqueous | -6.2000 | +35.3877 | +35.3877 | +109.7374 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-2] *** |
| Fe$+3.OH2.z+1 | Atlas | [Fe(OH)2]+ | +1 | aqueous | -7.1179 | +40.6266 | +40.6266 | +114.9763 | Fe$+3:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-2] Atlas: [Fe(OH)2]+ |
| [Fe$+3]3.[OH]4.[z+5] | [M1]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | +5 | aqueous | -6.3000 | +35.9585 | +35.9585 | +259.0076 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[OH]4.[z-1] | [M1].[OH]4.[z-1] | [Fe(OH)4]- | -1 | aqueous | -21.6000 | +123.2861 | +123.2861 | +197.6358 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true | *** |
| [Fe$+3].[L1].[z+3] | [M1].[L1].[z+3] | [Fe(Acet)]3+ | +3 | aqueous | -0.5000 | +2.8538 | +2.8538 | +77.2035 | [Fe$+3]:+1, [L1]:+1 | SRD46 query estimated values | true | {"eq_nodes":[{"assumptions":["conditions applied to all three entries: temperature_c = 25.0, ionic_strength_mol_l = 0.1, solvent = water (aqueous convention; the ML species is the inner-sphere complex expressed relative to Fe(H2O)6^3+ + L(aq)), electrolyte unspecified (NaClO4 or NaCl typical for SRD-46 Fe3+ records).","CH3CN cannot outcompete H2O on a per-donor basis. Any inner-sphere occupancy of CH3CN on Fe3+ in aqueous solution is therefore negligible; the ~ logK1 ≈ −0.5 estimate reflects mostly the outer-sphere/statistical association."],"beta_definition_id":812,"beta_definition_name":"[ML]/[M][L]","estimation_method":"estimates from chemistry judgment anchored on the SRD-46 Fe3+ analogue set","evidence_citation_ids":[],"evidence_network_ids":[],"evidence_vlm_ids":["vlm_139320","vlm_139321","vlm_139322","vlm_172282","vlm_172303","vlm_173624","vlm_173630","vlm_173634","vlm_171933","vlm_168274","vlm_168275","vlm_168276","vlm_168277","vlm_168280"],"rationale":"In water the effective reaction is Fe(H2O)6^3+ + CH3CN ⇌ Fe(H2O)5(NCCH3)^3+ + H2O. Because H2O is a strong donor to Fe3+ (Fe3+ is highly oxophilic) and CH3CN's proton basicity is ~15 orders of magnitude lower than H2O's O basicity toward H+, CH3CN cannot outcompete H2O on a per-donor basis. Any inner-sphere occupancy of CH3CN on Fe3+ in aqueous solution is therefore negligible; the ~ logK1 ≈ −0.5 estimate reflects mostly the outer-sphere/statistical association.","source":"SRD46 query estimated values","uncertainty_log10":0.7}],"source":"SRD46 query estimated values"} |
| [Fe$+3].[L1]2.[z+3] | [M1].[L1]2.[z+3] | [Fe(Acet)2]3+ | +3 | aqueous | -1.5000 | +8.5615 | +8.5615 | +82.9112 | [Fe$+3]:+1, [L1]:+2 | SRD46 query estimated values | true | {"eq_nodes":[{"assumptions":["conditions applied to all three entries: temperature_c = 25.0, ionic_strength_mol_l = 0.1, solvent = water (aqueous convention; the ML species is the inner-sphere complex expressed relative to Fe(H2O)6^3+ + L(aq)), electrolyte unspecified (NaClO4 or NaCl typical for SRD-46 Fe3+ records).","assume ΔlogK per step ≈ −1 (statistical + electrostatic screening + water competition)"],"beta_definition_id":840,"beta_definition_name":"[ML<sub>2</sub>]/[M][L]<sup>2</sup>","estimation_method":"estimates from chemistry judgment anchored on the SRD-46 Fe3+ analogue set","evidence_citation_ids":[],"evidence_network_ids":[],"evidence_vlm_ids":["vlm_139320","vlm_139321","vlm_139322","vlm_172282","vlm_172303","vlm_173624","vlm_173630","vlm_173634","vlm_171933","vlm_168274","vlm_168275","vlm_168276","vlm_168277","vlm_168280"],"rationale":"For M3+ hexaaqua ions, second- and third-step logK are typically 0.5–1.5 units below the previous step even for good ligands (see Fe3+/phen: logK1=6.5, logK2=4.9, logK3=2.7 from vlm_139320/321/322). Applying ΔlogK ≈ −1 per step to a nearly non-binding first step gives the ML2, ML3 estimates.","source":"SRD46 query estimated values","uncertainty_log10":1.0}],"source":"SRD46 query estimated values"} |
| [Fe$+3].[L1]3.[z+3] | [M1].[L1]3.[z+3] | [Fe(Acet)3]3+ | +3 | aqueous | -3.0000 | +17.1231 | +17.1231 | +91.4728 | [Fe$+3]:+1, [L1]:+3 | SRD46 query estimated values | true | {"eq_nodes":[{"assumptions":["conditions applied to all three entries: temperature_c = 25.0, ionic_strength_mol_l = 0.1, solvent = water (aqueous convention; the ML species is the inner-sphere complex expressed relative to Fe(H2O)6^3+ + L(aq)), electrolyte unspecified (NaClO4 or NaCl typical for SRD-46 Fe3+ records).","Applying ΔlogK ≈ −1 per step to a nearly non-binding first step gives the ML2, ML3 estimates."],"beta_definition_id":872,"beta_definition_name":"[ML<sub>3</sub>]/[M][L]<sup>3</sup>","estimation_method":"estimates from chemistry judgment anchored on the SRD-46 Fe3+ analogue set","evidence_citation_ids":[],"evidence_network_ids":[],"evidence_vlm_ids":["vlm_139320","vlm_139321","vlm_139322","vlm_172282","vlm_172303","vlm_173624","vlm_173630","vlm_173634","vlm_171933","vlm_168274","vlm_168275","vlm_168276","vlm_168277","vlm_168280"],"rationale":"For M3+ hexaaqua ions, second- and third-step logK are typically 0.5–1.5 units below the previous step even for good ligands (see Fe3+/phen: logK1=6.5, logK2=4.9, logK3=2.7 from vlm_139320/321/322). Applying ΔlogK ≈ −1 per step to a nearly non-binding first step gives the ML2, ML3 estimates.","source":"SRD46 query estimated values","uncertainty_log10":1.2}],"source":"SRD46 query estimated values"} |
| Fe$+6.OH8.z-2 | Atlas | [FeO4]2- | -2 | aqueous | -0.0000 | +0.0000 | +0.0000 | +566.4090 | Fe$+6:+1 H:-8 | Atlas | true | Atlas: [FeO4]2- |

### 5.2 Dissolution / Solid Species

| species_id | original_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | source | include | additional_notes |
|------------|-------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|--------|---------|------------------|
| Fe$+2.OH2.z+0(s) | Atlas | Fe(OH)2 (hydr.) | +0 | dissolution | -13.2754 | +75.7722 | +75.7722 | +75.7722 | Fe$+2:+1 H:-2 | Atlas | false | [DUPLICATE GROUP: Fe$+2:1 H:-2] Atlas: Fe(OH)2 (hydr.) |
| [Fe$+2].[OH]2.[z+0]_(s) | [M2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | +0 | dissolution | -13.5700 | +77.4534 | +77.4534 | +77.4534 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true | [DUPLICATE GROUP: Fe$+2:1 H:-2] *** |
| Fe$+2.Fe$+3(2).OH8.z+0(s) | Atlas | Fe3O4 (anh.) | +0 | dissolution | -7.1252 | +40.6684 | +40.6684 | +189.3678 | Fe$+2:+1 Fe$+3:+2 H:-8 | Atlas | true | Atlas: Fe3O4 (anh.) |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [M1].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | +0 | dissolution | +0.7000 | -3.9954 | -3.9954 | +70.3543 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [M1].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | +0 | dissolution | -0.5000 | +2.8538 | +2.8538 | +77.2035 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [M1].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | +0 | dissolution | -3.2000 | +18.2646 | +18.2646 | +92.6143 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true | [DUPLICATE GROUP: Fe$+3:1 H:-3] *** |
| Fe$+3.OH3.z+0(s) | Atlas | Fe(OH)3 (hydr.) | +0 | dissolution | -4.8381 | +27.6144 | +27.6144 | +101.9641 | Fe$+3:+1 H:-3 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe(OH)3 (hydr.) |
| Fe$+3(2).OH6.z+0(s) | Atlas | Fe2O3 (anh.) | +0 | dissolution | +1.4441 | -8.2425 | -8.2425 | +140.4569 | Fe$+3:+2 H:-6 | Atlas | false | [DUPLICATE GROUP: Fe$+3:1 H:-3] Atlas: Fe2O3 (anh.) |
| Fe$+0.z+0(s) | Atlas | Fe | +0 | dissolution | -0.0000 | +0.0000 | +0.0000 | +84.9352 | Fe$+0:+1 | Atlas | true | Atlas: Fe |

### 5.3 Gas Species

(No gas species in this system.)

### 5.4 Supportive Thermodynamic Data

| entity_id | property | value | unit | derived_mu0_kJ | notes |
|-----------|----------|-------|------|----------------|-------|
| S0 | pKw | 14.00 | - | +79.9077 | water self-dissociation |
| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |
| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ | - | F/(2.303RT) at 25°C |
| e- | nernst_factor | 0.05916 | V | - | 2.303RT/F at 25°C |
