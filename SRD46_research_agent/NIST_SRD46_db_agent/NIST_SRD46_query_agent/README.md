# SRD-46 Query agent

This package supplies the Query runtime, its MCP tools, terminal entry points and claim-evaluation helpers. It is part of the standalone SRD-46 Analysis repository. Installation, provider configuration and archive restoration are described in the root [README](../../../README.md) and [mounting guide](../../../MOUNTING.md).

## Components

| Component | Role |
|---|---|
| [query_agent.py](query_agent.py) | Query conversation and tool execution |
| [freeform_runner.py](freeform_runner.py) | One-question runner and native output generation |
| [API_SRD46_Query_UI.py](API_SRD46_Query_UI.py) | Package CLI for Query and browser entry points |
| [main.py](main.py), [server.py](server.py) | FastMCP stdio/SSE server and tool registration |
| [argo_client.py](argo_client.py), [argo_config.py](argo_config.py) | Query transport and native defaults |
| [SRD46_tools](SRD46_tools/) | Tool normalization, planning and wrappers |
| [SRD46_query_output_eval_pipeline](SRD46_query_output_eval_pipeline/) | Extraction, claim grounding and reporting |
| [BATCH_run_scripts](BATCH_run_scripts/) | Native Query benchmark helpers |

The database tools live in [NIST_SRD46_core_db_search_tools](../../NIST_SRD46_core_db_search_tools/). The sibling [browser](../../NIST_SRD46_database_browser/README.md) reads databases directly for browsing and invokes the native Query runtime for agent jobs.

## Running

From the repository root, launch the publication browser with:

```bash
python run_browser.py
```

For the package-specific Query CLI, use its full path from the repository root:

```bash
python SRD46_research_agent/NIST_SRD46_db_agent/NIST_SRD46_query_agent/API_SRD46_Query_UI.py query "Compare Cu(II) and Zn(II) EDTA stability" -m gpt55
```

The Query CLI accepts `@path` to read a UTF-8 prompt file, `--max-turns`, `--timeout`, `--no-enrich`, `--skip-claim-validation` and `--disable-sql`. Its `-m` argument is a native model alias. Use the standalone browser/settings for configured direct-provider jobs; the package CLI is not the shared Analysis benchmark launcher.

From this package directory, `python main.py` starts MCP over stdio and `python main.py --sse` selects SSE. `python agent_runtime.py` opens the terminal runtime. These commands can invoke paid services when used with an agent client.

## Tools and context

The MCP tool catalog includes entity resolution, system catalogs, stability and pKa searches, equilibrium networks, citations, ligand similarity, card inspection, aggregate queries and read-only SQL. Discovery and search-planning tools coordinate standalone Query exploration. Embedded estimation conversations are governed by their native Analysis dispatch context. See [TOOLS_REFERENCE.md](SRD46_tools/TOOLS_REFERENCE.md) for tool signatures.

The unconfigured package defaults are declared in `argo_config.py`. Standalone configuration binds the selected model and provider across Query helpers. Argo identity comes from configuration or `ARGO_API_USER`; there is no bundled personal account. Direct-provider keys are read from environment variables, not prompt text.

## Outputs

With the default standalone output root, raw Query runs are stored in `_output/Query/_output`, and extracted answers and claim results in `_output/Query/_output_eval`. Freeform question directories use a `Qfree_` prefix under the selected model. Published Query examples use the corresponding `_benchmark` roots and can be read from archives by the browser.

Raw files include result, history and reference-ID Markdown. The evaluation pipeline writes extracted answer/tool Markdown, claim JSON and validation reports when those stages are enabled. These are Query-specific products, separate from Analysis solver artifacts and LD/LV validation.

Database files are restored from the repository's `_large_files` packs. Git LFS is not required. Schema details are in the [database storage guide](../../NIST_SRD46_core_db_storage/README.md).
