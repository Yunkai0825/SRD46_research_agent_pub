# Query package installation and use

Install this package as part of the standalone repository. Run commands below from the repository root with Python 3.12 or newer:

```bash
python -m pip install -r requirements.txt
python scripts/run_analysis.py --check
python run_browser.py --check
python run_browser.py
```

The root requirements cover the browser, database tools and analysis runtime. The root launchers restore required database packs from `_large_files`; no Git LFS installation or external research harness is needed. To restore database packs explicitly:

```bash
python zip_images/large_file_packs.py --root . unpack
```

The four database files belong in `SRD46_research_agent/NIST_SRD46_core_db_storage`. Browser database views accept `SRD46_DB_DIR`; Query search tools read the sibling storage directory directly. Cards, equilibrium maps, literature and ligand fingerprints support different tool families; verify all four before running the full tool catalog.

## Provider configuration

Use `srd46_analysis_settings.json` at the repository root. Argo requires an authorized API username and access to its configured endpoint. Direct Anthropic and OpenAI providers use an API-key environment variable. The standalone configuration propagates the chosen model to Query helpers. The package's `argo_config.py` defines defaults for native callers that do not apply standalone configuration.

See the root [README](../../../README.md) and `python scripts/run_analysis.py --guide` for provider options, model aliases, reasoning/thinking controls and output settings. Do not place credentials in prompts or checked-in settings.

## Query entry points

The browser's `/agent/` page launches Query jobs and streams logs. Query and Analysis share one browser run slot. From the repository root, the native Query CLI is:

```bash
python SRD46_research_agent/NIST_SRD46_db_agent/NIST_SRD46_query_agent/API_SRD46_Query_UI.py query "List Fe(III) ligands with logK > 20" -m gpt55
```

From the Query package directory, inspect other native entry points with:

```bash
python BATCH_run_scripts/run_batch_SRD46_query_db_subagent.py --help
python BATCH_run_scripts/run_batch_output_claim_eval_subagent.py --help
```

`TEST_PROMPTS.md` contains the Query benchmark questions. Analysis benchmark selection and freeform Analysis runs use the root `scripts/run_analysis.py` and `scripts/run_ff1.py` instead.

## Outputs and checks

Default Query raw outputs are under `_output/Query/_output`; evaluated outputs are under `_output/Query/_output_eval`. Browser inspection of packed published outputs does not require extraction. Editing an Analysis excerpt requires an unpacked run with local `answer.md`.

If imports fail, install the root requirements in the same environment used to launch Python. If a database route fails, verify the corresponding restored database and, for browser views, `SRD46_DB_DIR`. Provider errors require checking the configured endpoint, model and credential/account; they are separate from database availability.
