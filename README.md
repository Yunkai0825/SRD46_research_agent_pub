# SRD-46 Research Agents, Data, and Results

Research agents, shared database search tools, a local browser, and scientific results derived from the archived **NIST Critically Selected Stability Constants of Metal Complexes Database (SRD 46)**.

## Quick start

Use Python 3.11 or newer. Install the shared requirements from the repository root:

```sh
python -m pip install -r requirements.txt
python launch_srd46_browser.py
```

On the first run, the launcher checks `packaged_files.json` and restores missing database files from their local ZIP archives before loading the browser. It verifies the original size and SHA-256 before installing each file at its declared path. Existing files are left unchanged; no database is regenerated and no download is needed. Keep each archive collection (`name.part001-of-NNN.zip`, `name.part002-of-NNN.zip`, ...) together in its original directory. Each file is an ordinary ZIP that opens directly in Windows File Explorer.

The launcher serves `http://127.0.0.1:5046/` and opens your browser when ready. If the default port is busy, it chooses an available local port. Press **Ctrl+C** in the terminal to stop.

```sh
python launch_srd46_browser.py --check
python launch_srd46_browser.py --port 5047
python launch_srd46_browser.py --no-browser
```

On Windows, double-click **`Setup_workspace.cmd`** to run the installation self-check; its window stays open to show the result. It uses the local `.venv` when available, otherwise Python 3.11+ on your PATH or the Windows Python launcher. It installs no dependencies and makes no network requests.

To run the same self-check in a terminal, or verify all installed packaged assets:

```sh
python workspace_setup.py
python workspace_setup.py --verify
```

A missing or damaged archive stops restoration with a clear error; an incomplete file is never installed. The manifest can also declare other required packaged files using a repository-relative `path`, `archive`, original byte `size`, and `sha256` (plus `member` when its ZIP member differs from the target basename). Only those listed assets are expanded. Benchmark and freeform archives remain compressed and are read directly by the browser, including collections of independent `.part001-of-NNN.zip` archives. Most archived items remain ordinary files within those ZIPs. Individual files that exceed the archive size budget use ordered pieces inside an `<original filename>.__chunks__/` folder; the browser and installer reconstruct their original bytes automatically. Large restored files are local installations; their ZIP payloads are the repository files, with no Git LFS pointers.

## Contents

| Path | Contents |
| --- | --- |
| `NIST_SRD46_core_db_storage/` | Four SQLite databases containing source records and derived chemical data; large files are restored from packaged ZIP assets |
| `NIST_SRD46_database_browser/` | Database browser, live agent pages, and benchmark/freeform catalog |
| `NIST_SRD46_db_agent/` | Query and Analysis agents, prompts, and evaluation/calculation pipelines |
| `NIST_SRD46_core_db_search_tools/` | Shared search implementations used by the agents and browser |
| `Auxillary_dbs_storage/Pourbaix_atlas_database/` | Pourbaix species lists and reference material |
| `_benchmark/` | Saved benchmark runs grouped into ZIPs by consecutive prompt IDs within each level, and scientific deliverables |
| `_output/` | Shared freeform runs, answers, and scientific deliverables |
| `_Claude_web_answers/` | Preserved `parsed/` tree and one complete archive per reference model: `Opus4_7.zip` and `Fable5_1.zip`, with every run's figures and supporting files inside its prompt folder |

The benchmark catalog keeps Analysis, Query, and Main in separate tabs, with one column per available mode. Canonical results are labelled **Full framework**. Query prompts come from the [Query prompt table](NIST_SRD46_db_agent/NIST_SRD46_query_agent/TEST_PROMPTS.md); Analysis prompts come from the [Analysis prompt table](NIST_SRD46_db_agent/NIST_SRD46_analysis_agent/_DEBUG_input/TEST_PROMPTS.md). Prompts without outputs remain visible as **No saved run**.

The catalog reads flat run folders and ZIP members directly, without extraction. It supports current raw-run folders and the published `final/result_*` layout. New freeform runs are written under `_output/Query/` and `_output/Analysis/`; Query benchmark batches use `_benchmark/Query/`.

Published Analysis benchmarks under `_benchmark/` group consecutive prompts from the same level into ZIPs of at most 95 MiB, keeping each example whole where it fits. Filenames show the inclusive prompt ranges, for example `L1_1-L1_5.zip`. A `+` explicitly combines ranges when an oversized prompt is packaged separately: `L4_1+L4_3-L4_7.zip` contains L4_1 and L4_3 through L4_7, while L4_2 has its own collection. The original descriptive run folders and every file remain inside each archive, and the browser lists each example separately.

For the oversized L1_11, L4_2, and FF_1 examples, open `<full-run-name>.part001-of-003.outputs.zip` to find the complete answers, figures, tables, reports, code, manifests, and logs together. The two `.checkpoints.zip` companions preserve solver checkpoint state. Every part is an ordinary ZIP that opens in Windows File Explorer. Keep all three parts together for the browser to read the complete example without extraction. Only an individually oversized checkpoint uses ordered `.__chunks__/` members; the archive reader reconstructs its original bytes. All files are preserved in these repository archives; no external release download or Git LFS is needed.

All four databases are selected together from `NIST_SRD46_core_db_storage/`. Use `--db-dir PATH` or `SRD46_DB_DIR` for another complete bundle. No model backend is needed to view the data or results.

## Documentation

- [Local publication checks and no-pointer policy](docs/PUBLISHING.md)
- [Reference-answer archives and artifact locations](_Claude_web_answers/README.md)
- [Browser usage and routes](NIST_SRD46_database_browser/README.md)
- [Query agent setup](NIST_SRD46_db_agent/NIST_SRD46_query_agent/INSTALLATION_GUIDE.md) and [tools](NIST_SRD46_core_db_search_tools/README.md)
- [Analysis agent](NIST_SRD46_db_agent/NIST_SRD46_analysis_agent/README.md)
- [Database storage](NIST_SRD46_core_db_storage/README.md) and [parser](NIST_SRD46_core_db_storage/NIST_SRD46_database_parsing/README.md)

## Attribution

Cite NIST SRD 46 using [DOI 10.18434/M32154](https://doi.org/10.18434/M32154), retain the original measurement references, and identify the database snapshot and release used. See [CITATION.cff](CITATION.cff).

Original software and documentation use the [MIT License](LICENSE). Data and third-party materials retain their separate terms in [NOTICE](NOTICE) and the preserved NIST source notice. This is an independent transformation of the NIST archive.
