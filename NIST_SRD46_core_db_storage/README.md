# SRD-46 Output Databases

This directory contains four SQLite databases produced by the NIST SRD-46 pipeline.
Together they provide a fully structured, queryable representation of the NIST
**Standard Reference Database 46 — Critically Selected Stability Constants of
Metal Complexes**.

Large databases are distributed as lossless ordinary ZIP archives or independent `.part001-of-NNN.zip` archive collections beside their original paths. The browser launcher and database readers restore missing files automatically, checking the original size and SHA-256 recorded in [`../packaged_files.json`](../packaged_files.json). You can also double-click `Setup_workspace.cmd` or run `python workspace_setup.py` from the repository root. Every ZIP opens directly in Windows File Explorer; files too large for one archive use ordered members in an `<original filename>.__chunks__/` folder, reassembled automatically by the installer. This installs the original bytes; it does not run the parser or rebuild the databases. Existing files are never overwritten.

| Database | Size | Tables | Purpose |
|---|---|---|---|
| `srd46_cards.db` | 188.61 MiB (197,775,360 bytes) | 16 | Primary data: metals, ligands, complexes, stability constants, pKa, and per-measurement literature references |
| `srd46_equilibrium_maps.db` | 28 MB | 12 | Equilibrium grouping: maps measurements into networks that share related equilibrium definitions |
| `srd46_literature.db` | 44 MB | 8 | Full literature catalog: complete citation entities and per-measurement citation links |
| `srd46_ligand_fingerprints.db` | See `packaged_files.json` | — | Molecular fingerprints, pairwise similarities, and generation metadata |

---

## 1 — `srd46_cards.db`  (Primary Cards Database)

The central database. Every metal ion, ligand, and metal–ligand stability
measurement from SRD-46 is stored as a structured "card".

### Entity tables

| Table | Rows | Description |
|---|---|---|
| `metal_card` | 230 | One row per unique metal ion (e.g. `Ag+`, `Fe3+`). Includes symbol, charge, SMILES, InChI, stoichiometry JSON, and classification flags (`is_simple_ion`, `is_organometallic`). |
| `ligand_card` | 5,750 | One row per unique ligand (e.g. Glycine). Includes formula, composition, SMILES, InChI, HxL protonation definition, IUPAC/common synonyms, and figure-definition string. |
| `ligandmetal_card` | 89,824 | One row per VLM measurement entry. Links a `metal_id`, `ligand_id`, and `beta_definition_id` together with denormalized display names. `complex_system_id` is the original SRD-46 VLM identifier. |

### Stability constants

| Table | Rows | Description |
|---|---|---|
| `ligandmetal_stability_measured` | 89,824 | Measured (literature) stability constants. Each row carries the constant type (`K`, `β`, etc.), value, temperature, ionic strength, solvent, electrolyte, and the fully parsed equilibrium equation (`equation_python`, `equation_str`, `equation_tree_json`, LHS/RHS species JSON, reaction type, element-conservation flag). |
| `ligandmetal_stability_estimated` | 0 | Reserved for ML-estimated constants (not yet populated). Schema mirrors `_measured` plus `model_name`, `model_version`, `confidence`, and `uncertainty`. |

### Ligand pKa

| Table | Rows | Description |
|---|---|---|
| `ligand_pka_measured` | 8,801 | Measured pKa values linked to a ligand. Includes bracket transitions (`bracket_from_state` → `bracket_to_state`), pKa type, temperature, ionic strength, solvent, electrolyte, measurement method, quality, and originating VLM IDs (`vlm_ids_json`). |
| `ligand_pka_bracket` | 30,721 | Protonation state "brackets" for each ligand. Each bracket defines a discrete protonation state (charge, formula, HxL form, SMILES, InChI). Brackets with `is_estimated = 1` were predicted by the QupKake ML model and include `model_name`, `model_version`, `confidence`, and `uncertainty`. |

### Reference (citation) tables

Literature references are stored in two tiers:

- **Entity tables** hold unique citation records.
- **Junction tables** (`ref_vlm_*`) link individual VLM measurements to their citations via `vlm_id`.

The `vlm_id` in junction tables corresponds to `ligandmetal_card.complex_system_id`.

| Table | Rows | Description |
|---|---|---|
| `ref_literature_alt` | 16,769 | Primary citation entity (compact format). Each row is a unique citation string with a short-code `shortcut` (e.g. `"00B"`) and a full `citation` text. |
| `ref_literature` | 1 | Structured citation entity (journal-level detail). Contains `paper_id`, `year`, `issue`, `page`, `paper_name`. Only 1 row exists in the SRD-46 source data; the system primarily uses `literature_alt`. |
| `ref_author` | 1 | Author entity. Sparse in SRD-46 source data. |
| `ref_footnote` | 0 | Footnote entity. Defined in schema but no footnotes present in the source export. |
| `ref_vlm_literature_alt` | 721,473 | Junction: VLM → `ref_literature_alt`. The main citation link — each VLM measurement typically maps to multiple citations. |
| `ref_vlm_literature` | 43 | Junction: VLM → `ref_literature`. |
| `ref_vlm_author` | 43 | Junction: VLM → `ref_author`. |
| `ref_vlm_footnote` | 0 | Junction: VLM → `ref_footnote`. |

### Indexes

```
idx_lm_card_metal               ligandmetal_card(metal_id)
idx_lm_card_ligand              ligandmetal_card(ligand_id)
idx_lm_stab_card                ligandmetal_stability_measured(card_id)
idx_ligand_pka_ligand           ligand_pka_measured(ligand_id)
idx_ligand_bracket_ligand       ligand_pka_bracket(ligand_id)
idx_ref_vlm_lit_alt_vlm         ref_vlm_literature_alt(vlm_id)
idx_ref_vlm_lit_vlm             ref_vlm_literature(vlm_id)
idx_ref_vlm_author_vlm          ref_vlm_author(vlm_id)
idx_ref_vlm_footnote_vlm        ref_vlm_footnote(vlm_id)
```

### Key relationships

```
metal_card.metal_id           ← ligandmetal_card.metal_id
ligand_card.ligand_id         ← ligandmetal_card.ligand_id
                              ← ligand_pka_measured.ligand_id
                              ← ligand_pka_bracket.ligand_id
ligandmetal_card.card_id      ← ligandmetal_stability_measured.card_id
                              ← ligandmetal_stability_estimated.card_id
ligandmetal_card.complex_system_id  ≈  ref_vlm_*.vlm_id   (join by convention)
ref_literature_alt.literature_alt_id ← ref_vlm_literature_alt.literature_alt_id
ref_literature.literature_id         ← ref_vlm_literature.literature_id
ref_author.author_id                 ← ref_vlm_author.author_id
ref_footnote.footnote_id             ← ref_vlm_footnote.footnote_id
```

### Example queries

```sql
-- All stability constants for Cu²⁺ + Glycine
SELECT s.constant_type, s.constant_value, s.temperature_c,
       s.ionic_strength_mol_l, s.equation_python
FROM   ligandmetal_card c
JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
WHERE  c.metal_name_SRD = 'Cu^[2+]'
  AND  c.ligand_name_SRD LIKE '%Glycine%';

-- pKa values for a ligand
SELECT p.pKa, p.pKa_type, p.temperature_c, p.ionic_strength_mol_l,
       p.bracket_from_state, p.bracket_to_state
FROM   ligand_pka_measured p
JOIN   ligand_card l ON l.ligand_id = p.ligand_id
WHERE  l.ligand_name_SRD LIKE '%Glycine%';

-- Citations for a specific VLM measurement
SELECT r.shortcut, r.citation
FROM   ref_vlm_literature_alt j
JOIN   ref_literature_alt r ON r.literature_alt_id = j.literature_alt_id
WHERE  j.vlm_id = 93606;
```

---

## 2 — `srd46_equilibrium_maps.db`  (Equilibrium Maps Database)

Groups individual VLM measurements into **equilibrium networks** — sets of
measurements that share overlapping chemical species and can be compared or
combined within a consistent thermodynamic framework.

### Hierarchy

```
eq_map_collection          (1 per metal–ligand pair, 21,348 total)
  └── eq_map               (≥1 per collection; partitioned by T / I conditions)
        ├── eq_network      (connected component of related equilibria)
        │     ├── eq_node           (individual VLM measurement)
        │     │     └── eq_node_species      (species on each side of the equation)
        │     ├── eq_edge           (link between two nodes sharing species)
        │     │     └── eq_edge_species      (shared species on the edge)
        │     └── eq_network_species         (union of all species in the network)
        └── eq_map_stray    (VLMs that could not be assigned to any network)
```

### Tables

| Table | Rows | Description |
|---|---|---|
| `eq_map_collection` | 21,348 | One per unique (metal_id, ligand_id) pair. Aggregated counters: `total_entries`, `total_networks`, `iterations_count`, `unassigned_count`. |
| `eq_map` | 30,213 | Condition-partitioned map within a collection. Stores temperature and ionic-strength ranges, plus entry/network/stray counts. `iteration` tracks refinement passes. |
| `eq_network` | 30,342 | A connected component of VLM nodes. Contains `node_count` and `edge_count`. |
| `eq_node` | 60,540 | One per VLM measurement. Carries `vlm_id`, `beta_definition_id`, `equation_python`, `constant_type`, `constant_value`, temperature, ionic strength, and `is_duplicate` / `used_in_map` flags. |
| `eq_edge` | 47,600 | Link between two nodes that share at least one chemical species. |
| `eq_node_species` | 186,328 | Species participating in a node's equilibrium equation, tagged with `side` (LHS / RHS). |
| `eq_edge_species` | 77,068 | Species shared between two linked nodes. |
| `eq_network_species` | 130,745 | Union of all species appearing in a network. |
| `eq_map_stray` | 5,305 | VLM entries in a map that could not be connected to any network (isolated equilibria). |
| `eq_collection_unassigned` | 0 | VLMs that could not be placed in any map at all (currently empty). |
| `eq_export_metadata` | 19 | Key-value metadata about the export run. |

### Indexes

```
idx_eq_node_vlm_id      eq_node(vlm_id)
idx_eq_node_beta_id     eq_node(beta_definition_id)
```

### Key relationships

```
eq_map_collection.collection_id  ← eq_map.collection_id
                                 ← eq_collection_unassigned.collection_id
eq_map.map_id                    ← eq_network.map_id
                                 ← eq_map_stray.map_id
eq_network.network_db_id         ← eq_node.network_db_id
                                 ← eq_edge.network_db_id
                                 ← eq_network_species.network_db_id
eq_node.node_db_id               ← eq_node_species.node_db_id
eq_edge.edge_db_id               ← eq_edge_species.edge_db_id
```

### Example queries

```sql
-- All networks for Cu²⁺ + Glycine
SELECT n.network_db_id, n.node_count, n.edge_count
FROM   eq_map_collection c
JOIN   eq_map m ON m.collection_id = c.collection_id
JOIN   eq_network n ON n.map_id = m.map_id
WHERE  c.metal_name = 'Cu^[2+]'
  AND  c.ligand_name LIKE '%Glycine%';

-- Equations in a network
SELECT nd.vlm_id, nd.equation_python, nd.constant_type, nd.constant_value
FROM   eq_node nd
WHERE  nd.network_db_id = 42;
```

---

## 3 — `srd46_literature.db`  (Full Literature Catalog)

A standalone, fully normalized citation database generated directly from the
SRD-46 source CSV exports. It contains the complete set of literature entities
and their many-to-many links to VLM measurements, independent of the cards
database.

### Tables

| Table | Rows | Description |
|---|---|---|
| `literature_alt` | 18,297 | Primary citation entity. Each row is a unique bibliographic reference with a `shortcut` code (e.g. `"00A"`) and full `citation` text (e.g. `"S. Arrhenius, Z. Phys. Chem., 1893, 11, 805"`). |
| `literature` | 1 | Structured citation entity linked to a `paper`. Contains `paper_id`, `year`, `issue`, `page`. Sparse in SRD-46 source data. |
| `paper` | 1 | Journal/publication entity: `name`, `publisher`. |
| `author` | 1 | Author entity: `name`, `email`. |
| `footnote` | 135 | Footnote text entries with `shortcut` codes. |
| `verk_literature_author` | 1 | Junction: `literature` → `author`. |
| `vlm_literature` | 79,956 | Ligand–metal level citation link. Links (`ligand_id`, `metal_id`) pairs to `literature_id` and/or `literature_alt_id`. The `not_used` flag marks citations marked as unused in the original source. |
| `vlm_literature_sic` | 721,906 | Per-VLM citation link. Links individual `vlm_id` measurements to `literature_id` and/or `literature_alt_id`. This is the most granular citation mapping. |

### Indexes

```
idx_lit_alt_shortcut          literature_alt(shortcut)
idx_literature_paper          literature(paper_id)
idx_vlm_lit_ligand_metal      vlm_literature(ligand_id, metal_id)
idx_vlm_lit_lit_id            vlm_literature(literature_id)
idx_vlm_lit_lit_alt_id        vlm_literature(literature_alt_id)
idx_vlm_sic_vlm               vlm_literature_sic(vlm_id)
idx_vlm_sic_lit_id            vlm_literature_sic(literature_id)
idx_vlm_sic_lit_alt_id        vlm_literature_sic(literature_alt_id)
idx_vla_lit                   verk_literature_author(literature_id)
idx_vla_author                verk_literature_author(author_id)
```

### Key relationships

```
paper.paper_id                  ← literature.paper_id
literature.literature_id        ← vlm_literature.literature_id
                                ← vlm_literature_sic.literature_id
                                ← verk_literature_author.literature_id
literature_alt.literature_alt_id ← vlm_literature.literature_alt_id
                                 ← vlm_literature_sic.literature_alt_id
author.author_id                ← verk_literature_author.author_id
```

### Example queries

```sql
-- Find citation by shortcut code
SELECT citation FROM literature_alt WHERE shortcut = '62Pc';

-- All citations for a specific VLM measurement
SELECT la.shortcut, la.citation
FROM   vlm_literature_sic s
JOIN   literature_alt la ON la.literature_alt_id = s.literature_alt_id
WHERE  s.vlm_id = 93606;

-- All citations for a metal–ligand pair
SELECT DISTINCT la.shortcut, la.citation
FROM   vlm_literature vl
JOIN   literature_alt la ON la.literature_alt_id = vl.literature_alt_id
WHERE  vl.ligand_id = 5760 AND vl.metal_id = 68;
```

---

## Cross-database joins

The three databases can be joined via shared identifiers:

| Shared Key | Cards DB | Equilibrium DB | Literature DB |
|---|---|---|---|
| `metal_id` | `metal_card.metal_id`, `ligandmetal_card.metal_id` | `eq_map_collection.metal_id`, `eq_node.metal_id` | — |
| `ligand_id` | `ligand_card.ligand_id`, `ligandmetal_card.ligand_id` | `eq_map_collection.ligand_id`, `eq_node.ligand_id` | `vlm_literature.ligand_id` |
| `vlm_id` / `complex_system_id` | `ligandmetal_card.complex_system_id` | `eq_node.vlm_id` | `vlm_literature_sic.vlm_id` |
| `beta_definition_id` | `ligandmetal_card.beta_definition_id` | `eq_node.beta_definition_id` | — |
| `literature_alt_id` | `ref_literature_alt.literature_alt_id` | — | `literature_alt.literature_alt_id` |

To perform cross-database queries in SQLite, attach the databases:

```sql
ATTACH 'srd46_equilibrium_maps.db' AS eqdb;
ATTACH 'srd46_literature.db'       AS litdb;

-- VLM measurement with its network and its citations
SELECT c.metal_name_SRD, c.ligand_name_SRD,
       s.constant_type, s.constant_value, s.equation_python,
       n.network_db_id,
       la.shortcut, la.citation
FROM   ligandmetal_card c
JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
JOIN   eqdb.eq_node nd        ON nd.vlm_id = c.complex_system_id
JOIN   eqdb.eq_network n      ON n.network_db_id = nd.network_db_id
JOIN   litdb.vlm_literature_sic sic ON sic.vlm_id = c.complex_system_id
JOIN   litdb.literature_alt la      ON la.literature_alt_id = sic.literature_alt_id
WHERE  c.complex_system_id = 93606;
```

---

## Notes

- **SRD-46 uses `literature_alt` as the primary citation mechanism.** The `literature` / `author` / `paper` tables have very few rows because the original SRD-46 data stores most citations as compact text strings in `literature_alt`.
- **`vlm_id` bridging:** The `ref_vlm_*` junction tables in `srd46_cards.db` and `vlm_literature_sic` in `srd46_literature.db` both use `vlm_id` to identify individual measurements. This corresponds to `ligandmetal_card.complex_system_id` and `eq_node.vlm_id`.
- **`ligandmetal_stability_estimated`** is a placeholder for future ML-predicted stability constants (currently 0 rows).
- **`citations_json`** in `ligandmetal_stability_measured` is reserved for per-row embedded citation data (currently NULL for all rows).
- **Coverage:** 99.5 % of `ligandmetal_card` entries (89,366 / 89,824) have at least one `ref_vlm_literature_alt` citation link.
- All databases use `INTEGER PRIMARY KEY` (SQLite rowid alias) for auto-incrementing IDs and `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` where applicable.
