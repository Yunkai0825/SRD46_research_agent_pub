# Core database bundle

These four SQLite files are the retained publication snapshot. The browser reads all four together from this directory, or a directory selected by `--db-dir` or `SRD46_DB_DIR`.

| File | Contents |
| --- | --- |
| `srd46_cards.db` | Metal and ligand identities, 79,063 measurement cards, stability constants, pKa, and source references |
| `srd46_equilibrium_maps.db` | Equilibrium collections, networks, equations, and species links |
| `srd46_literature.db` | Bibliographic records and measurement-reference associations |
| `srd46_ligand_fingerprints.db` | Structural fingerprints and pairwise similarity data |

All original database bytes are preserved. See [snapshot checksums and row counts](../docs/validation/database_snapshot.json) and [scientific interpretation](../docs/DATA.md). Database files use Git LFS; fetch their payloads before starting the browser.

Read these databases with SQLite read-only connections. Their source identifiers and provenance remain part of the scientific data. Retain the [NIST attribution and terms](../NOTICE).
