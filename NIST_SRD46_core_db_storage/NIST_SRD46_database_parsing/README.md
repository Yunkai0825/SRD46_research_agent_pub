# NIST SRD 46 database parsing

This pipeline converts a local SRD 46 export, curated molecular structures, and archived enrichment results into four SQLite databases for the SRD 46 browser and research tools. Source measurements, parser corrections, and predicted properties retain separate provenance.

From this directory, install the parser dependencies and inspect the workflow:

```console
python -m pip install -r ../../requirements.txt
python -B run_srd46_pipeline.py --list-stages
python -B run_srd46_pipeline.py --list-rules
```

Rebuild with archived PubChem results and existing QupKake predictions:

```console
python -B run_srd46_pipeline.py --pubchem cache-only
```

This requires the original MySQL `.sql` schema files and matching `.txt` data files in [`_input/SRD46_SQL/`](<_input/SRD46_SQL/SRD 46 README.md>), plus the enrichment inputs under `_input/PubChem_cache_seeds/` and the [QupKake bundle](_input/Qupkake_ligand_pKa_ML/README.md). The runner does not use `_input/SRD46_SQL_and_CSV/` or `_input/pip1_parsed_individual_SRD46/`; those historical folders can be removed if you use this runner. Curated beta-definition corrections and beta/metal/solvent notation changes are preserved in guarded parser rules; original measurement values remain authoritative. Run without `--resume` after upgrading from the CSV-based pipeline. Generated databases are written under `_output/pip2c_cards_sql/`:

| Database | Contents |
|---|---|
| `srd46_cards.db` | Metal, ligand, measurement, and protonation cards |
| `srd46_equilibrium_maps.db` | Equilibrium collections, species, and reaction links |
| `srd46_literature.db` | Bibliographic records and measurement/reference links |
| `srd46_ligand_fingerprints.db` | Molecular fingerprints, pairwise similarities, and generation metadata |

The distributed final databases are kept in [the parent storage directory](../). Parser `_output/` is disposable local build output and is not a second distributed database bundle. A rebuild creates `_output/srd46_pipeline_staging.db` for stage status, intermediate tables, cached lookups, and the correction ledger; keep that work file only while resuming or partially rebuilding a run.

Useful commands:

```console
python -B run_srd46_pipeline.py --status
python -B run_srd46_pipeline.py --resume --pubchem cache-only
python -B run_srd46_pipeline.py --stages descriptors,verify
```

QupKake predictions are read directly from `_input/Qupkake_ligand_pKa_ML/qupkake_results.db`. The bundle contains parsed prediction tables, the original archived CSV rows, and every original evidence file as a hashed BLOB; normal runs neither extract files nor reparse SDFs. `--qupkake-input-db PATH` selects another bundle. Explicit `--qupkake-sdf-dir`, `QUPKAKE_SDF_DIR`, or `--qupkake-parsed-csv` retains the legacy input workflow.

Use `--qupkake off` to omit archived machine-learning predictions. The runner does not perform new QupKake inference. Use a separate `--output-dir` for limited smoke runs so they do not replace a complete database bundle.

See the [source-data provenance](<_input/SRD46_SQL/SRD 46 README.md>), [runner and validation stages](srd46_pipeline/runner.py), and [chemical-rule library](srd46_pipeline/chem_rules_lib/README.md). Source-data attribution and redistribution terms are recorded in the repository [NOTICE](../../NOTICE).
