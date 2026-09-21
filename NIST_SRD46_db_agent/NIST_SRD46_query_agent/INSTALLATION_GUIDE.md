# SRD-46 Query Agent Installation Guide

This guide covers the query agent, its MCP server, the shared database browser, and query-run evaluation. Run every command below from the repository root, the directory containing `launch_srd46_browser.py` and the single `requirements.txt`.

## Prerequisites

- Python 3.11 or newer.
- The supplied database files and their complete ZIP archive collections in `NIST_SRD46_core_db_storage/`.
- Access to the configured Argo API for live agent runs and LLM-based claim evaluation. Browsing saved results, database searches, and extracting saved tool results do not require an Argo request.

Database files and output archives must contain their original bytes. Git LFS pointers, pointer stubs, and placeholder files are not allowed. Missing packaged databases are restored automatically from the local ZIPs; no database regeneration is needed. You can run `python workspace_setup.py --verify` or double-click `Setup_workspace.cmd` from the repository root to check the installation.

## Install dependencies

Install the complete dependency set from [the repository-root requirements.txt](../../requirements.txt):

```powershell
python -m pip install -r requirements.txt
```

An optional virtual environment can be created first:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The root requirements include the browser, MCP transport, SQL parser, chemical search, and scientific calculation dependencies. There is no separate query-agent requirements file.

## Verify database files and the browser

The canonical database directory is [NIST_SRD46_core_db_storage](../../NIST_SRD46_core_db_storage/):

| File | Purpose |
|---|---|
| `srd46_cards.db` | Metals, ligands, measured stability constants, and pKa data |
| `srd46_equilibrium_maps.db` | Equilibrium maps and networks |
| `srd46_literature.db` | Literature records and citation mappings |
| `srd46_ligand_fingerprints.db` | Ligand similarity fingerprints |

Run the local browser check:

```powershell
python -B launch_srd46_browser.py --check
```

For browser-only use, an alternate database directory can be supplied explicitly:

```powershell
python launch_srd46_browser.py --db-dir C:/path/to/databases
```

The browser also accepts `SRD46_DB_DIR`. The shared query tools read the canonical repository directory directly; changing the browser database option does not relocate the query-agent databases.

## Configure Argo access

Shared query-agent settings are defined in [argo_config.py](./argo_config.py). Set the API identity before starting an agent or the browser:

```powershell
$env:ARGO_API_USER = "your.username"
```

On a POSIX shell, use `export ARGO_API_USER="your.username"`. There is no hardcoded personal username. If your deployment uses a different endpoint, set `ARGO_API_URL` before launch. Use model names available in that deployment; the query CLI accepts `-m` / `--model`.

## Launch the browser

The root launcher starts the local application and opens the default web browser:

```powershell
python launch_srd46_browser.py
```

Useful options:

```powershell
python launch_srd46_browser.py --port 5046
python launch_srd46_browser.py --no-browser
```

The default address is `http://127.0.0.1:5046`. If the default port is occupied, the launcher prints its selected address. The browser provides database search, agent pages, and saved benchmark/freeform results under `/results/benchmark/` and `/results/output/`.

The query package also exposes a browser subcommand:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.API_SRD46_Query_UI serve --host 127.0.0.1 --port 5046
```

## Run a freeform query

Use the qualified module entry point from the repository root:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.API_SRD46_Query_UI query "Compare Cu(II) and Zn(II) binding to EDTA" -m gpt54
```

A prompt file can be passed as `@path/to/prompt.txt`. Optional `--no-enrich` and `--skip-claim-validation` flags control post-run processing; `--help` lists the remaining options:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.API_SRD46_Query_UI query --help
```

Freeform runs from every user share `_output/Query/`. Their extracted answers and claim-evaluation artifacts are stored in `_output/Query/_evaluation/`.

## Start the MCP server or terminal agent

For an MCP client using stdio:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.main
```

For SSE transport:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.main --sse
```

For the interactive terminal agent:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime
```

The server imports its database functions from [NIST_SRD46_core_db_search_tools](../../NIST_SRD46_core_db_search_tools/), the same canonical implementation used by the analysis agent and browser normalization helpers.

## Run query benchmarks

The maintained prompt catalog is [TEST_PROMPTS.md](./TEST_PROMPTS.md). The batch runner accepts prompt IDs, a section, models, repeat counts, and concurrency options:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.BATCH_run_scripts.run_batch_SRD46_query_db_subagent 1.1.1
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.BATCH_run_scripts.run_batch_SRD46_query_db_subagent --section 3 -m gpt54 -r 1 -j 1
```

Omitting IDs and `--section` runs the full catalog. Results are written under `_benchmark/Query/`, organized by model and question. These commands make live model requests.

## Evaluate saved query runs

Extract saved tool results without making model requests:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher_orchestrator --extract-only
```

Run claim evaluation for a selected saved run:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher_orchestrator --model gpt54 --question Qfree_REPLACE_WITH_RUN_ID --workers 1
```

The default input is `_output/Query/`, and the default evaluation directory is `_output/Query/_evaluation/`. To process benchmark outputs explicitly:

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher_orchestrator --output-root _benchmark/Query --eval-root _benchmark/Query/_evaluation --model gpt54 --question Q1.1.1 --workers 1
```

Claim evaluation requires Argo access unless `--extract-only` is supplied. Evaluation writes derived answer, tool-result, claim, and validation artifacts; it does not regenerate the databases.

## Troubleshooting

| Problem | Check |
|---|---|
| Missing third-party Python module | Use the intended Python environment and install the root `requirements.txt`. |
| Missing repository package | Run the qualified `python -m ...` commands from the repository root. |
| Database-dependent view or query fails | Run `python workspace_setup.py --verify` and keep every packaged ZIP part together in `NIST_SRD46_core_db_storage/`. |
| Live agent request fails | Check `ARGO_API_USER`, the configured endpoint, network access, and model availability. |
| Browser opens on a different port | Use the address printed by the root launcher, or specify an available `--port`. |

See the [root README](../../README.md) for the wider research-agent workspace and [TOOLS_REFERENCE.md](./SRD46_tools/TOOLS_REFERENCE.md) for the query-tool contracts.
