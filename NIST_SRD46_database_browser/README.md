# SRD-46 database browser

This standalone Flask application provides read-only views of the core SRD-46 databases and published final results. It has no research-service dependencies.

## Run

From the repository root:

```sh
python -m pip install -r requirements.txt
python launch_srd46_browser.py
```

The launcher opens the local browser after startup. Use `--check` to validate database paths and pages, `--db-dir` to select another core bundle, and `--no-browser` to suppress automatic opening. Direct launch with `python NIST_SRD46_database_browser/app.py` is also supported.

## Pages

| Route | Purpose |
| --- | --- |
| `/` | Database dashboard |
| `/metals/` | Metals and related measurements |
| `/ligands/` | Ligands, protonation records, and metal partners |
| `/stability/` | Stability measurements and source equations |
| `/pka/` | Protonation data |
| `/equilibrium/` | Equilibrium collections and networks |
| `/literature/` | Scientific references |
| `/similarity/` | Stored ligand structural similarity |
| `/results/` | Opens the Benchmark tab |
| `/results/benchmark/` | Published benchmarks |
| `/results/output/` | Published output |

## Data locations

The browser reads all four SQLite files from `NIST_SRD46_core_db_storage/` at the repository root. `SRD46_DB_DIR` or the launcher's `--db-dir` selects another directory. SQLite connections use read-only mode.

Published cases live under `_benchmark/<case>/` and `_output/<case>/`. Each case contains `answer.md`, `verdict.json`, and optional `final/` deliverables. Independent scientific results can have their own answer and verdict under `final/result_01/`, `final/result_02/`, and so on. Each result preserves available final LC1, LC2, LC3, and LD outputs in separate folders, with final numerical files under `solver/`. Result pages group those final outputs by stage, display the available answers and verdicts, link scientific deliverables, and preview raster figures. The original table and two-column result layout are retained, with exactly two saved-result tabs: Benchmark and Output. Approved final deliverables, root answers/verdicts, and published cost images/CSVs are available read-only. No computation or file editing occurs when a result is viewed.

Benchmark shows the stacked `cost_per_prompt.png` below the prompt table, preserving the original chart layout with neutral cost labels. Output has no overview chart. Each case shows detailed cost decomposition in `cost_distribution.png` after its final results, with all 14 worker substep amounts available in the corresponding CSV.

The old `/analysis/` and `/eval/` entry points redirect to benchmarks; their `/freeform/` counterparts redirect to output.

## Interpretation

Similarity scores compare stored molecular structures; they are not metal-affinity predictions. Protonation and stereochemical conventions affect structural comparisons. Measurement pages retain recorded conditions, source references, tentative indicators, and unresolved-equation status. Log K summaries use K-type constants; H/S values remain separate.

See [NOTICE](../NOTICE) for attribution and data-use terms.
