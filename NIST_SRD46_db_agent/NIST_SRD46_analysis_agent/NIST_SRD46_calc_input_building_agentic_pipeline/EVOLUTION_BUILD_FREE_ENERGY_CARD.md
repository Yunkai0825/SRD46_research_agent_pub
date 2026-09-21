# Evolution — Free-Energy Card Through LC2

How the free-energy markdown card evolves stage by stage inside
`LC2_free_energy_card_building/` (schema:
`SCHEMA_FREE_ENERGY_CARD.md`). Each stage rewrites/extends the card and
leaves an auditable per-call artefact tree.

| Stage | Module | Input | Output artefact | What changes |
|-------|--------|-------|-----------------|--------------|
| LC2_1 — card initializer | `LC2_1_card_initializer/` | LC1 `lc1_sweep_input.json` + per-pair SRD-46 ref-eq cards (`_ref_cards/`, `_eq_maps/`) | `LC2_1/<call>/free_energy_card.md` + `lc2_1_manifest.json` | Initial card assembled from the SRD-46 reference equilibria: components, reference states, μ° tables. |
| LC2_2 — external-DB merger | `LC2_2_card_db_merger/` | LC2_1 card | `LC2_2/<call>/free_energy_card.md` + `deduplication_check.md` | Pourbaix-Atlas (and other external DB) species merged in; provenance appended. **Skipped** when no external DB rows apply. |
| LC2_3 — deduplicator | `LC2_3_card_deduplicator/` | LC2_2 (or LC2_1) card | `LC2_3/free_energy_card_deduplicated.md` + per-group subagent logs | LLM dedup of stoichiometry-equivalent rows (per stoich group + singletons); conflicting duplicates resolved. **Skipped** when nothing to dedup. |
| LC2_4 — validator / repair | `LC2_4_card_validator/` | LC2_3 card | `LC2_4/free_energy_card_validated.md` + `LC2_4_call_NN/report.md` | Structural + numerical validation; repair subagent patches fixable issues. |
| final | `LC2_free_energy_card_orchestrator.py` | LC2_4 card | `LC2/free_energy_card.md` + `summary/LC2_summary.json` | Validated card copied to the stage root — this is the card LC3 and the numcalc reader consume. |

> **Planned, not implemented:** a default-off query-estimation lane should run
> from `LC1_3_estimate_eq_stability_dispatch`, interposed after the LC1_2
> authoritative fetch and before LC1_2 system eq-map review. Accepted supporting
> entries must join the materialized reaction network inside LC2_1, before
> stability constants are converted to free energies. See the
> [current LC1.3 estimation module](LC1_SRD46_eq_card_alignment/LC1_3_estimate_eq_stability_dispatch/README.md).

Conditional flow: the orchestrator runs LC2_2/LC2_3 only when needed;
`stages_run` / `stages_skipped` in the return dict record the actual path
taken. See `LC2_free_energy_card_building/README.md` for the flow diagram
and return-dict reference.

---

## Worked example — most complicated case, step by step

System: **Cu + Fe (both redox-active) × glycine + citrate**, hot/unusual
conditions so Atlas merge, dedup *and* repair all fire. Schema details in
`SCHEMA_FREE_ENERGY_CARD.md`.

### Step 0 — input from LC1

`lc1_sweep_input.json` declares the system catalog
(`Cu$+2/Cu$+1/Cu$+0`, `Fe$+3/Fe$+2/Fe$+0/Fe$+6`, `ligand_5760`,
`ligand_9058`) and `lc1_2_eqmap_card.json` carries one validated eq-map
per (metal, ligand) pair — 4 pairs + hydroxide pairs — each with
`patch_notes` LC2 must hardcode.

### Step 1 — LC2_1 card initializer

For every pair, the per-pair SRD-46 ref-eq cards are pulled/rendered into
`LC2_1/<call>/_ref_cards/` (+ `_eq_maps/` with `ids_v0/maps_v0/
augmented_networks_v0`). They are assembled into the first
`free_energy_card.md`:

- §2.1 reserved `M0`/`L0`; §2.2 six metal valences; §2.3 two ligands with
  `canonical_HxL` (`[[H][L1]]`, `[[H]3[L2]]`).
- §2.4 elects one `is_reference=true` per element (`Cu$+1`, `Fe$+2`).
- §3.2 anchors μ°(HxL) ≡ 0 per ligand (strategy `exact`/`ladder`/`vlm`).
- §5.1 fills binaries, bis-complexes, protonated complexes and the
  mixed-ligand ternary `[Fe$+3].[L1].[L2].[z-1]` with
  `log_beta → mu0_free_kJ → mu0_canon_kJ → mu_aligned_kJ` per row.

### Step 2 — LC2_2 external-DB merger (conditional — fires here)

The Pourbaix Atlas contributes what SRD-46 lacks: `Cu$+0`/`Fe$+0` solid
dissolutions, `Fe$+6` species, hydroxo aqueous rows
(`[Cu$+2].[OH].[z+1]`), and solids `[Cu(OH)2](s)`, `[Fe(OH)3](s)`.
Merged rows get `source = Atlas`, `db_source = Pourbaix Atlas`, and §6
provenance lines. Overlapping rows are *flagged*, not silently dropped —
`deduplication_check.md` lists every collision.

### Step 3 — LC2_3 LLM deduplicator (conditional — fires here)

Collisions are grouped by identical stoichiometry
(`group_01_aqueous_Fe_3_1_H_-1`, …); one subagent per group plus a
`singletons` pass decide keep/mute using T/I proximity to the request.
Losers stay in the card with `include = false` and a
`[DUPLICATE GROUP: …]` marker in `additional_notes` — the audit trail in
`free_energy_card_deduplicated.md` / `dedup_plan.md`.

### Step 4 — LC2_4 validator / repair

Validates the hard invariants (reserved `M0`/`L0`, one valence reference
per element, every `stoich` token resolvable into §2, unique
`species_id`, `phase` enum, totals > 0). A failed check (e.g. a ternary
`stoich` referencing `[[H]-1[L2]]` where the canonical frame is
`[[H]3[L2]]`) is handed to the repair subagent, which patches the row and
re-validates → `free_energy_card_validated.md` + `LC2_4_call_NN/report.md`.

### Step 5 — final

The validated card is copied to `LC2/free_energy_card.md`;
`summary/LC2_summary.json` records
`stages_run = [LC2_1, LC2_2, LC2_3, LC2_4]`, `stages_skipped = []`. This
card is what LC3's variable catalog and the numcalc reader
(`resolve_card_source`) consume.

*(Simple contrast: a single-metal single-ligand system with no Atlas rows
and no collisions runs LC2_1 → LC2_4 only, with
`stages_skipped = [LC2_2, LC2_3]`.)*
