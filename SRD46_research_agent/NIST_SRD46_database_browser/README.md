# SRD-46 database and results browser

The Flask browser provides read-only database searches, Query and Analysis launch forms, and inspection of native and web-harness results. It runs locally and shares the standalone configuration in `srd46_analysis_settings.json`.

## Launch

Run these commands from the repository root after installing the root requirements:

```bash
python run_browser.py --check
python run_browser.py
```

The launcher restores required database packs and opens the local webpage automatically. Use `--no-open` to suppress automatic opening. See the root [mounting guide](../../MOUNTING.md) for installation and [README](../../README.md) for provider settings.

## Routes and implementation

| Module | Purpose |
|---|---|
| `app.py` | Application creation, blueprint registration and dashboard |
| `db.py`, `request_dbs.py` | Read-only SQLite access and request-scoped connections |
| `routes/metals.py`, `ligands.py`, `stability.py`, `pka.py` | Chemical identities and measured constants |
| `routes/equilibrium.py`, `literature.py`, `similarity.py` | Equilibrium networks, citations and ligand similarity |
| `routes/pourbaix.py` | Auxiliary stored Pourbaix data, when available |
| `routes/agent.py` | Query launch form at `/agent/`, status and streamed logs |
| `routes/analysis_agent.py` | Analysis launch form and run status |
| `routes/analysis.py` | Analysis results, comparisons, web-harness views and excerpts |
| `routes/evaluation.py` | Query evaluation views at `/eval/` and `/eval/freeform/` |

Database paths use `SRD46_DB_DIR` when configured, otherwise the sibling `NIST_SRD46_core_db_storage` directory. Required databases are cards, equilibrium maps, literature and ligand fingerprints. Optional Pourbaix CSV data may be absent.

## Launching agents

The Query and Analysis forms use the configured provider and model. Argo requires an authorized account; direct Anthropic and OpenAI providers use credentials from the configured environment variable. The standalone browser reserves one shared run slot for Query or Analysis. The run settings are applied for that job and restored when it finishes.

The forms launch real pipeline jobs and stream their logs. There is no visible simulation toggle. Internal simulation support is intended for explicit offline checks. Browser access should be limited to a trusted local environment.

## Output locations and archives

New runs use the configured output root, `_output` by default. Query raw and evaluated outputs use `Query/_output` and `Query/_output_eval` below that root. Published examples are under `_benchmark` or its archive index. Analysis result views include the comparison matrix and web-harness outputs; the standalone navigation does not expose a Main Agent or paper-excerpt overview tab.

The browser reads packed runs directly from `_output_archives`. If a run is unpacked, its loose files take precedence; absent members can still be read from its ZIP. At each application startup, a quick archive check determines whether extraction is needed. The extraction popup is shown only when packed outputs remain to be unpacked. Extraction is also available without the browser:

```bash
python unpack_outputs.py
```

ZIP parts retain the benchmark directory structure. Repacking rewrites affected existing parts and preserves unaffected parts. It does not create successive update archives. See the root README for `zip_images.output_zips.output_packs` commands and explicit deletion handling.

## Answer and excerpt views

Raw displays the answer without excerpt highlighting. Eval displays saved `_eval/excerpts.json` labels; for an unpacked run without excerpts it opens the editor. Runs with saved excerpts open in Eval by default unless Raw is explicitly requested.

Excerpt editing requires a physical run folder and local `answer.md`, whether or not excerpts already exist. ZIP-only runs are read-only. Saves use an atomic replacement and reject version conflicts; linked paths are not editable. Editor writes affect loose files. Repack the affected run to publish the saved excerpts in its ZIP.

Analysis elapsed-time displays exclude recorded solver intervals. Missing timing evidence remains blank. Full run timelines retain wall-clock timing.
