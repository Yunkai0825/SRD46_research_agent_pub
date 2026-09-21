# Archived QupKake predictions

`qupkake_results.db` is the parser's SQLite input for existing QupKake predictions. If the database is missing, the first-run self-check or parser reader restores its exact bytes from `qupkake_results.db.zip`, verifies the recorded SHA-256, and installs it at this path. Normal pipeline runs then query the parsed tables directly without extracting or reparsing SDF files.

The bundle preserves all 8,410 original files (131,806,128 bytes), including the primary predictions, alternate `xtb6.7` predictions, parsed CSV, and supporting evidence. Original file bytes, paths, sizes, timestamps, and SHA-256 hashes are retained in `source_files`; the loose copies were removed only after complete verification.

| Table | Rows | Contents |
|---|---:|---|
| `source_files` | 8,410 | Original evidence as byte-exact BLOBs and provenance |
| `sdf_result` | 4,237 | Original active-file order, diagnostics, and skip/filter results |
| `sdf_prediction` | 4,113 | Usable primary SDF predictions and neutral reference fields |
| `sdf_window` | 16,218 | Parsed charge-state formulas, brackets, SMILES, and InChI |
| `archived_prediction` | 4,112 | Original parsed CSV rows with all 122 columns and their order |
| `bundle_metadata` | 14 | Format version, processing versions, source policy, and parser hashes |

The normal stage applies the existing guarded `QUP-01` fallback to these SQL records. It produces 4,114 prediction rows, exactly matching the former loose-file workflow, including values, types, row/column order, correction ledger, and diagnostics. Alternate SDFs remain evidence and do not replace the primary predictions.

For example, query the archived fallback prediction for ligand 10175:

```sql
SELECT ligandennr, formula_Q0, bracket_Q0
FROM archived_prediction
WHERE ligandennr = '10175';
```

From `NIST_SRD46_database_parsing`, verify the retained source bytes and database integrity:

```shell
python -B -m srd46_pipeline.qupkake_bundle verify _input/Qupkake_ligand_pKa_ML/qupkake_results.db
```

The database is distributed as an ordinary ZIP containing the original file bytes, without Git LFS pointers. First-run setup restores the missing database automatically and verifies its SHA-256: `069b9d75f0cf93e59c01780c5fb4df5df03883649b8d84f73937c57636726121`.

See the [parser guide](../../README.md), [converter and loader](../../srd46_pipeline/qupkake_bundle.py); its `verify` command checks bundle integrity, and `verify --source PATH --compare-stage` checks source equivalence. QupKake predictions retain their source/model provenance; the project's [MIT licence](../../../../LICENSE) covers original project software and documentation. [NOTICE](../../../../NOTICE) records the third-party attribution and terms.
