# Canonical Schema — Speciation Card

**File name on disk**: `free_energy_card.md` (LC2 final; the numcalc reader
also accepts `free_energy_card_numcalc.md` > `free_energy_card_enriched.md` >
`free_energy_card.md` > `free_energy_card_with_include.md`, in that priority).
**Producer**: LC2 stages `LC2_1` (init from SRD-46 ref cards) → `LC2_2`
(external-DB / Pourbaix-Atlas merge) → `LC2_3` (LLM dedup) → `LC2_4`
(validate / repair).
**Consumer**: `NIST_SRD46_core_numcalc_pipeline/numcalc_input_cards_reader/card_md_input_reader.resolve_card_source`
→ `FreeEnergyReport` → `PourbaixPointSolver` / `NDGridSolver`.
**Format**: GitHub-flavoured Markdown. Section headers are STRUCTURAL — do not rename or reorder. Tables are pipe-delimited; column headers are STRUCTURAL.

> The legacy JSON form (`02_*_input_speciation_card.json` with `<M_n>`/`<L_n>` `spec_id` placeholders, `target_concentrations`, `target_species`, and `equations` blocks) is **OBSOLETE and FORBIDDEN**.

---

## Top-level layout

```
# Free Energy Analysis Card
<header block>

## 1. Notation Conventions
## 2. Components
    ### 2.1 Solvent
    ### 2.2 Metals
    ### 2.3 Ligands
    ### 2.4 Metal Valence Alignment
    ### 2.5 Ligand Micro-Valence Analysis      (optional)
## 3. Canonical Reference States
    ### 3.1 Component Reference Declarations
    ### 3.2 Ligand Canonical Resolution
## 4. Settings
    ### 4.1 Common Settings
    ### 4.2 Per Metal–Ligand Pair Conditions
## 5. Standard Chemical Potentials
    ### 5.1 Aqueous Species
    ### 5.2 Dissolution / Solid Species
    ### 5.3 Gas Species                         (optional)
    ### 5.4 Supportive Thermodynamic Data
## 6. Provenance / Audit                        (optional, S2/S2.5 appends)
```

---

## Header block (free text, immediately after `# Free Energy Analysis Card`)

| field        | example                              | required |
|--------------|--------------------------------------|----------|
| `**System**` | `06 FeCu glycine citrate`            | yes |
| `**Metals**` | `[Cu]2+, [Cu]+, [Fe]3+, [Fe]2+`      | yes |
| `**Ligands**`| `[Glycine], [Citric acid]`           | yes |
| `**Generated**` | UTC timestamp                     | yes |

---

## §2.1 Solvent — `S0: Water`

Two sub-tables (both required):

**Properties table**
| property | value |
|----------|-------|
| name | Water |
| formula | H2O |
| self_dissociation | true |
| dissociation_reaction | `H2O ⇌ H⁺ + OH⁻` |
| pK | 14.00 |
| K_log10 | -14.00 |

**Component table**
| internal_id | name | charge | stoich_coeff | db_id |
|-------------|------|--------|--------------|-------|
| `M0` | `[H]+`  | `+1` | `+1` | `metal_68`   |
| `L0` | `[OH]-` | `-1` | `+1` | `ligand_10076` |

`M0` and `L0` are RESERVED and MUST appear.

---

## §2.2 Metals

| column        | type     | notes |
|---------------|----------|-------|
| `internal_id` | str      | Pattern `<Element>$<signed-int>`, e.g. `Cu$+2`, `Fe$+0`, `Cu$-1`. **No `M1`/`M2` placeholders.** |
| `name`        | str      | Display label, e.g. `[Cu]2+`, `Cu(s)`. |
| `charge`      | signed int| `+2`, `-1`, `+0`. |
| `total_M`     | float ≥ 0| Analytical total in mol/L. `0` ⇒ valence kept for redox bookkeeping but not titrated. |
| `db_source`   | enum     | `NIST SRD-46` or `Pourbaix Atlas`. |
| `db_id`       | str      | `metal_<id>` for SRD-46 rows, blank for Atlas. |

**Example (multi-metal, multi-valence — Cu + Fe):**

| internal_id | name | charge | total_M | db_source | db_id |
|-------------|------|--------|---------|-----------|-------|
| `Cu$+2` | `[Cu]2+` | `+2` | `0.001` | NIST SRD-46 | `metal_41` |
| `Cu$+1` | `[Cu]+`  | `+1` | `0.001` | NIST SRD-46 | `metal_42` |
| `Cu$+0` | `Cu(s)`  | `+0` | `0`     | Pourbaix Atlas | |
| `Fe$+3` | `[Fe]3+` | `+3` | `0.005` | NIST SRD-46 | `metal_61` |
| `Fe$+2` | `[Fe]2+` | `+2` | `0.005` | NIST SRD-46 | `metal_62` |
| `Fe$+0` | `Fe(s)`  | `+0` | `0`     | Pourbaix Atlas | |

## §2.3 Ligands

| column          | type     | notes |
|-----------------|----------|-------|
| `internal_id`   | str      | `L1`, `L2`, … (ordinal, NOT a placeholder). |
| `name`          | str      | Display label, `[Glycine]`. |
| `charge`        | signed int | Charge of the **fully deprotonated** form. |
| `total_M`       | float ≥ 0| mol/L. |
| `canonical_HxL` | str      | Reference protonation, e.g. `[[H][L1]]`, `[[H]3[L2]]`. |
| `db_source`     | enum     | `NIST SRD-46` or `Pourbaix Atlas`. |
| `db_id`         | str      | `ligand_<id>` or blank. |
| `smiles`        | str      | Canonical SMILES. |

**Example (multi-ligand — glycine + citrate):**

| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |
|-------------|------|--------|---------|---------------|-----------|-------|--------|
| `L1` | `[Glycine]`     | `-1` | `0.025` | `[[H][L1]]`  | NIST SRD-46 | `ligand_5760` | `C(C(=O)O)N` |
| `L2` | `[Citric acid]` | `-3` | `0.025` | `[[H]3[L2]]` | NIST SRD-46 | `ligand_9058` | `O=C(O)CC(O)(CC(=O)O)C(=O)O` |

## §2.4 Metal Valence Alignment  (REQUIRED)

| column        | type        | notes |
|---------------|-------------|-------|
| `element`     | str         | `Cu`, `Fe`. |
| `internal_id` | str         | Matches §2.2. |
| `name`        | str         | |
| `charge`      | signed int  | |
| `is_reference`| bool        | Exactly ONE row per element is `true`. The reference is the row with charge closest to 0, then +1, −1, +2, −2, … |
| `n_valences`  | int         | Total valence rows for this element. |

This section is the audit surface for **C2 valence pruning**: rows with `total_M = 0` AND not the reference may be dropped by C2 if user did not request the redox couple.

**Example (two redox-active elements; one `is_reference = true` per element):**

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Cu | `Cu$+1` | `[Cu]+`  | +1 | true  | 3 |
| Cu | `Cu$+0` | `Cu(s)`  | +0 | false | 3 |
| Cu | `Cu$+2` | `[Cu]2+` | +2 | false | 3 |
| Fe | `Fe$+2` | `[Fe]2+` | +2 | true  | 3 |
| Fe | `Fe$+0` | `Fe(s)`  | +0 | false | 3 |
| Fe | `Fe$+3` | `[Fe]3+` | +3 | false | 3 |

(Atlas-injected zero-valence solids participate in `n_valences` but the
reference is elected among the aqueous SRD-46 valences.)

## §2.5 Ligand Micro-Valence Analysis  (OPTIONAL)

Per-atom oxidation states from electronegativity assignment. Used only when a ligand redox couple is in scope.

---

## §3.1 Component Reference Declarations

| column        | type      | enum / notes |
|---------------|-----------|--------------|
| `component_id`| str       | One of `M0`, `L0`, `<Element>$<n>`, `L<k>`. |
| `name`        | str       | |
| `type`        | enum      | `proton` \| `metal` \| `hydroxide` \| `ligand_canonical` |
| `reference_form` | str    | e.g. `[Cu]2+(aq)`, `[OH]-(aq) from Kw`, `[[H][L1]]`. |
| `mu0_ref_kJ`  | signed float | kJ/mol. |
| `rule`        | enum      | `R1`–`R5` (see §1) or `RULE 1` (Atlas-injected). |
| `element`     | str or `***` | |
| `charge`      | signed int | |
| `is_valence_ref` | bool / `***` | Mirrors §2.4. |

**Example (one declaration per component — both metals, both ligands):**

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|--------------|------|------|----------------|------------|------|---------|--------|----------------|
| `M0`    | `[H]+`          | proton           | `[H]+(aq)`           | 0.0  | R1 | H   | +1 | `***` |
| `L0`    | `[OH]-`         | hydroxide        | `[OH]-(aq) from Kw`  | 79.9 | R2 | `***` | -1 | `***` |
| `Cu$+1` | `[Cu]+`         | metal            | `[Cu]+(aq)`          | 0.0  | R3 | Cu  | +1 | true |
| `Fe$+2` | `[Fe]2+`        | metal            | `[Fe]2+(aq)`         | 0.0  | R3 | Fe  | +2 | true |
| `L1`    | `[Glycine]`     | ligand_canonical | `[[H][L1]]`          | 0.0  | R4 | `***` | -1 | `***` |
| `L2`    | `[Citric acid]` | ligand_canonical | `[[H]3[L2]]`         | 0.0  | R4 | `***` | -3 | `***` |

(`mu0_ref_kJ` for `L0` ≈ `2.303·RT·pKw`; non-reference valences `Cu$+2`,
`Cu$+0`, `Fe$+3`, `Fe$+0` get their μ° from §2.4 alignment, not from a
declaration row here.)

## §3.2 Ligand Canonical Resolution

Documents how `μ°(HₓL) ≡ 0` was anchored. Required columns: `ligand_id`, `ligand_name`, `rebase`, `declared_H`, `resolved_H`, `log_beta_HxL`, `mu_shift_kJ`, `strategy` (`exact` | `ladder` | `vlm`), `vlm_source`.

---

## §4.1 Common Settings

Required rows (case-sensitive `parameter` column):
`Kw_log10`, `2.303RT`, `RT`. Units: `-`, `kJ/mol`, `kJ/mol`.

## §4.2 Per Metal–Ligand Pair Conditions

| column        | type   | notes |
|---------------|--------|-------|
| `pair`        | str    | `<metal_name> + <ligand_name>` |
| `T_source (°C)` | str  | scalar or `min~max` |
| `I_source (mol/L)` | str | scalar or `min~max` |
| `ref_eq_net`  | int    | DB equilibrium id |
| `vlm_count`   | int    | |

---

## §5.1 / §5.2 / §5.3  Species tables (identical column schema)

| column           | type        | notes |
|------------------|-------------|-------|
| `species_id`     | str         | Bracket-tokenised canonical id, e.g. `[Cu$+2].[L1].[z+1]`, `Fe$+3.OH.z+2`, `[Cu(OH)2](s)`. Solids end in `_(s)` or `(s)`. |
| `original_id`    | str         | Pre-rebase id or `Atlas`. |
| `label`          | str         | Human label, e.g. `[Cu(Glyc)]+`. |
| `charge`         | signed int  | |
| `phase`          | enum        | `aqueous` \| `dissolution` \| `gas` |
| `log_beta`       | signed float | log₁₀ of cumulative β. |
| `mu0_free_kJ`    | signed float | Free-component frame. |
| `mu0_canon_kJ`   | signed float | Canonical-HₓL frame. |
| `mu_aligned_kJ`  | signed float | After §2.4 valence alignment. |
| `stoich`         | str         | Comma-list `<comp>:<int>` referencing §2 internal_ids; `+` and `−` allowed (e.g. `[[H]-1[L1]]:+1`). |
| `source`         | enum        | `SRD-46` \| `Atlas` |
| `include`        | bool        | `true` to feed solver; `false` to mute (kept for audit). |
| `additional_notes`| str        | Free text; `[DUPLICATE GROUP: …]` markers added by S2 dedup. |

> **No estimated-row schema yet.** `AgentEstimate`/`AnalogueEstimate`,
> uncertainty, evidence IDs, transfer method, and applicability ranges are not
> currently canonical fields. Do not label an inferred value as `SRD-46` or
> insert it into a production card via free text. For the current supported estimation workflow, see the
> [current LC1.3 estimation module](LC1_SRD46_eq_card_alignment/LC1_3_estimate_eq_stability_dispatch/README.md).

`§5.2 Dissolution / Solid Species` is REQUIRED to be present (may be empty body) so the solver knows there are zero solids. `§5.3` is OPTIONAL.

**Example rows (§5.1 — multi-metal × multi-ligand; μ° columns elided):**

| species_id | label | charge | phase | log_beta | stoich | source | include | additional_notes |
|------------|-------|--------|-------|----------|--------|--------|---------|------------------|
| `[Cu$+2].[L1].[z+1]`       | `[Cu(Gly)]+`      | +1 | aqueous | 8.6  | `Cu$+2:+1, [[H]-1[L1]]:+1`                 | SRD-46 | true | |
| `[Cu$+2].[L1]2.[z+0]`      | `[Cu(Gly)2]`      | 0  | aqueous | 15.6 | `Cu$+2:+1, [[H]-1[L1]]:+2`                 | SRD-46 | true | |
| `[Fe$+3].[L2].[z+0]`       | `[Fe(Cit)]`       | 0  | aqueous | 13.1 | `Fe$+3:+1, [[H]-3[L2]]:+1`                 | SRD-46 | true | |
| `[Fe$+3].[L1].[L2].[z-1]`  | `[Fe(Gly)(Cit)]-` | -1 | aqueous | …    | `Fe$+3:+1, [[H]-1[L1]]:+1, [[H]-3[L2]]:+1` | SRD-46 | true | mixed-ligand ternary |
| `[Cu$+2].[OH].[z+1]`       | `[CuOH]+`         | +1 | aqueous | …    | `Cu$+2:+1, L0:+1`                          | Atlas  | true | |
| `[Fe$+3].[L2].[H].[z+1]`   | `[FeH(Cit)]+`     | +1 | aqueous | …    | `Fe$+3:+1, [[H]-3[L2]]:+1, M0:+1`          | SRD-46 | true | protonated complex |

**Example rows (§5.2 — solids from both elements):**

| species_id | label | charge | phase | stoich | source | include |
|------------|-------|--------|-------|--------|--------|---------|
| `[Cu(OH)2](s)` | `Cu(OH)2(s)` | 0 | dissolution | `Cu$+2:+1, L0:+2` | Atlas | true |
| `[Fe(OH)3](s)` | `Fe(OH)3(s)` | 0 | dissolution | `Fe$+3:+1, L0:+3` | Atlas | true |

## §5.4 Supportive Thermodynamic Data

Required rows: `S0 / pKw`, `e- / charge`, `e- / F_over_RT_ln10`, `e- / nernst_factor`. Columns: `entity_id`, `property`, `value`, `unit`, `derived_mu0_kJ`, `notes`.

---

## §6 Provenance / Audit  (OPTIONAL)

Free-form Markdown appended by S2/S2.5 listing merge decisions, dropped duplicates, Atlas injections. Not parsed by the solver.

---

## Hard invariants (LD validator)

1. `M0` and `L0` rows are present in §2.1 with the exact internal_ids shown.
2. Every `internal_id` referenced inside any §5 `stoich` cell appears in §2 (or is `H` / `OH`).
3. Exactly one `is_reference = true` row per element in §2.4.
4. Every metal/ligand `internal_id` referenced in §3.1 exists in §2.
5. `total_M` ≥ 0 everywhere; sum of metal `total_M` > 0 AND sum of ligand `total_M` > 0 (else solver has nothing to titrate).
6. `phase ∈ {aqueous, dissolution, gas}` for every §5 row.
7. `species_id` is unique within the union of §5.1+§5.2+§5.3 (pre-`include` filter).
8. No legacy tokens: `<M_n>`, `<L_n>`, `M\d+`, `L\d+` may NOT appear inside `species_id` or `stoich` (only `M0`/`L0` reserved). The new `internal_id` form `<Element>$<n>` replaces all `M_n` placeholders.

---

## Worked skeleton — most complicated case (pseudocode)

Two redox-active metals (3 valences each, Atlas solids injected), two
ligands, mixed-ligand ternaries, protonated complexes, hydroxo species,
solids and a gas. Condensed card outline:

```text
# Free Energy Analysis Card
**System**: FeCu glycine citrate          **Metals**: [Cu]2+, [Cu]+, [Fe]3+, [Fe]2+
**Ligands**: [Glycine], [Citric acid]     **Generated**: <UTC>

## 1. Notation Conventions                 # rulebook R1–R5 prose
## 2. Components
   ### 2.1 Solvent      → M0 = [H]+ (metal_68), L0 = [OH]- (ligand_10076)   # RESERVED
   ### 2.2 Metals       → Cu$+2, Cu$+1, Cu$+0(Atlas), Fe$+3, Fe$+2, Fe$+0(Atlas)
   ### 2.3 Ligands      → L1 = glycine (ligand_5760), L2 = citrate (ligand_9058)
   ### 2.4 Valence align→ per element: exactly one is_reference=true (Cu$+1, Fe$+2)
   ### 2.5 Micro-valence→ per-atom OS for L1/L2 (only if ligand redox in scope)
## 3. Canonical Reference States
   ### 3.1 Declarations → M0, L0, Cu$+1, Fe$+2, L1, L2   (μ°ref anchors)
   ### 3.2 Ligand resolution → μ°(HxL) ≡ 0 anchoring per ligand (exact|ladder|vlm)
## 4. Settings
   ### 4.1 Common       → Kw_log10, 2.303RT, RT
   ### 4.2 Pair conditions → 4 metal×ligand pairs + hydroxide pairs:
        (Cu,L1) (Cu,L2) (Fe,L1) (Fe,L2) … each with T_source, I_source, ref_eq_net
## 5. Standard Chemical Potentials
   ### 5.1 Aqueous      → binaries  [Cu$+2].[L1].[z+1], [Fe$+3].[L2].[z+0], …
                          bis/tris  [Cu$+2].[L1]2.[z+0], …
                          ternaries [Fe$+3].[L1].[L2].[z-1]      # mixed-ligand
                          protonated [Fe$+3].[L2].[H].[z+1]      # M0 in stoich
                          hydroxo   [Cu$+2].[OH].[z+1]           # L0 in stoich
   ### 5.2 Solids       → [Cu(OH)2](s), [Fe(OH)3](s), Cu$+0/Fe$+0 dissolutions
   ### 5.3 Gas          → e.g. [H]2(g) (optional)
   ### 5.4 Supportive   → S0/pKw, e-/charge, e-/F_over_RT_ln10, e-/nernst_factor
## 6. Provenance       → LC2_2 Atlas merge + LC2_3 dedup decisions (audit only)
```

Every §5 `stoich` token must resolve into §2 (`Cu$+2`, `[[H]-1[L1]]`,
`M0`, `L0`, …); every element has exactly one valence reference; both
metal and ligand totals must be > 0 in aggregate — these are the
invariants the LD validator enforces above.
