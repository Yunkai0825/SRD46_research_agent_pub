# SRD-46 Data and Results

Core databases, a local read-only browser, Pourbaix species lists, and final scientific results derived from the archived **NIST Critically Selected Stability Constants of Metal Complexes Database (SRD 46)**.

## Quick start

Use Python 3.11 or newer. In a Git clone, fetch the database payloads with Git LFS before launching:

```sh
git lfs install
git lfs pull
python -m pip install -r requirements.txt
python launch_srd46_browser.py
```

The launcher serves `http://127.0.0.1:5046/` and opens your browser when ready. If the default port is busy, it chooses an available local port. Press **Ctrl+C** in the terminal to stop.

```sh
python launch_srd46_browser.py --check
python launch_srd46_browser.py --port 5047
python launch_srd46_browser.py --no-browser
```

## Contents

| Path | Contents |
| --- | --- |
| `NIST_SRD46_core_db_storage/` | Four SQLite databases containing source records and derived chemical data |
| `NIST_SRD46_database_browser/` | Read-only database and final-result browser |
| `Pourbaix_atlas_database/` | Species lists |
| `_benchmark/` | Final answers, verdicts, and scientific deliverables for benchmark cases |
| `_output/` | Final answers, verdicts, and scientific deliverables for the saved output case |
| `docs/` | Installation, data, results, and publication guidance |

Each saved case has `answer.md`, `verdict.json`, and available scientific files under `final/`. Independent calculations stay separate. Each calculation retains final stage outputs in `LC1/`, `LC2/`, `LC3/`, and `LD/`, with final numerical outputs, diagrams, and topology results alongside them.

All four databases are selected together from `NIST_SRD46_core_db_storage/`. Use `--db-dir PATH` or `SRD46_DB_DIR` for another complete bundle. No model backend is needed to view the data or results.

## Documentation

- [Installation](docs/INSTALLATION.md) and [usage](docs/USAGE.md)
- [Data and scientific interpretation](docs/DATA.md)
- [Benchmarks](docs/BENCHMARKS.md) and [publication contents](docs/PUBLICATION.md)
- [Architecture](docs/ARCHITECTURE.md) and [development](docs/DEVELOPMENT.md)

## Attribution

Cite NIST SRD 46 using [DOI 10.18434/M32154](https://doi.org/10.18434/M32154), retain the original measurement references, and identify the database snapshot and release used. See [CITATION.cff](CITATION.cff).

Original software and documentation use the [MIT License](LICENSE). Data and third-party materials retain their separate terms in [NOTICE](NOTICE) and the preserved NIST source notice. This is an independent transformation of the NIST archive.
