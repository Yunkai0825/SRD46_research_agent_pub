# SRD-46 Analysis

A standalone SRD-46 Analysis runner and database browser. It includes the native
Analysis and embedded Query agents, numerical solver, model-call provenance,
source databases, and the analysis-results interface. No research master
application or personal account configuration is required.

Use Python 3.12 or newer, install `requirements.txt`, then run:

```powershell
python scripts/run_analysis.py --check
python run_browser.py --check
python run_browser.py
```

The browser opens at `http://127.0.0.1:5046`. Startup restores the packed source
databases from `_large_files` when needed. Keep those packs in the repository.

## Settings and credentials

Edit `srd46_analysis_settings.json`, or override its settings on the command
line. Generated analyses go under `_output`; published examples stay under
`_benchmark`. The API account is independent of the output location. Neither
folder names nor settings require a personal username.

Set `SRD46_ANALYSIS_ARGO_API_USER` to your authorized Argo account, or pass
`--api-user`. Direct providers read `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` from
the environment. `--api-key-env` accepts an environment-variable name, never a
credential. Do not put credentials in JSON, source files, or commands.

All Analysis roles, embedded Query roles, and Query subprocess helpers use the
selected model. The defaults leave reasoning effort and thinking mode
unspecified in provider requests. The Argo interface supports this default
only; explicit effort requires a direct API. Direct OpenAI uses a separate
32,000-token total completion allowance, including reasoning and visible
output, configurable with `--openai-max-completion-tokens`. Direct Anthropic
supports explicit `--thinking-mode` and `--reasoning-effort` fields. An endpoint
may reject settings or models it does not support; there is no model fallback.
The Sonnet 4.7 preset is an unverified example.

## Run benchmarks

Use `scripts/run_analysis.py` for single answers and benchmark batches. Select
a model/provider combination with `--preset`, or use explicit settings flags.
Without `--run`, it only prints the resolved settings, prompts, and destinations.

```powershell
python scripts/run_analysis.py --preset opus47_no_topo --prompt-group L1
python scripts/run_analysis.py --preset opus47 --prompts L1_4 L1_5 --api-user YOUR_ACCOUNT --run
python scripts/run_analysis.py --preset gpt55_openai --prompt-group L1 --reasoning-effort high --run
python scripts/run_analysis.py --preset gpt6sol_openai --prompts L1_6 --output-root D:/SRD46_runs --run
python scripts/run_analysis.py --preset opus55_anthropic --prompt-group L1 --order speciation-first --run
```

The launcher calls the native `SRD46_analysis_run` API. It does not supply extra
scientific instructions, repair model decisions, or generate scientific
reports itself. Every run uses a fresh process and a fresh output folder;
an existing destination is rejected. Native reports, cards, solver outputs,
and provenance remain together in the run folder. The launcher captures
console logging in `_run.log`.

Use `--jobs` for concurrent complete runs (default 1). This is process
scheduling, not an artificial pause inside a scientific component. `--stop-file`
prevents new dispatches while allowing active runs to finish. There is no
mid-run spending gate. Run `python scripts/run_analysis.py --guide` for the
complete preset table, prompt groups, settings overrides, and output rules;
`--help` lists all flags. FF_1 keeps its separate `scripts/run_ff1.py` entry point
and uses the same runner. Its question and run metadata are in
[examples/FF_1.md](examples/FF_1.md), using YAML frontmatter. The `user_prompt: |` field comes after `layer` and
before `settings`. Its parsed string is the model question; the other fields
are not included in model context.
All metadata fields are listed. Fixed FF_1 defaults are explicit; `default` marks
provider/environment-selected values. FF_1 uses Argo/Opus 4.7, estimation on,
14 L0 iterations and a 1,200-second L0 reasoning timeout, with topology cleanup
on and LV artifact writing off. Presets and command-line flags override these
settings without editing the Markdown.
Use `--prompt-file` for other Markdown or plain-text questions.

For custom direct endpoints, use `--api-url` (the full Chat Completions or Messages
URL), `--api-model` (physical model ID), and `--api-timeout`. Keep `--model` as a
compatible native model-family alias. Both runners accept `--api-param FIELD=JSON`
and `--api-params-file` for other compatible request fields, plus named sampling,
effort, thinking and token-budget flags. `--api-header-env NAME=ENV` reads custom
header values from the environment; use `--api-header` only for non-secret values.
The native interface requires a single non-streaming text response and owns the
conversation and tool framing. These options do not change that protocol.

OpenAI `--max-completion-tokens` includes reasoning and visible output; effort
is separate, with no independent reasoning-token cap. Anthropic
`--anthropic-max-tokens` includes thinking and visible output. Explicit manual
thinking uses `--thinking-mode enabled --thinking-budget-tokens 4096` with a
larger total allowance; adaptive thinking uses `--thinking-mode adaptive` and
optional `--reasoning-effort`, without a manual budget. Omitting these flags
preserves the existing provider-default requests. The endpoint validates model
support. See `--guide` for precedence and examples, and the
[OpenAI Chat reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
and [Anthropic Messages reference](https://platform.claude.com/docs/en/api/messages/create)
for provider fields.

## Inspect results

The browser provides per-run answers and solver artifacts, a prompt/model
matrix, side-by-side answer comparison, reference-answer selection, and
excerpts where supplied. It reads both `_benchmark` and `_output`, including
model subfolders. Reference choices are saved in `_output`. An absent `LV`
folder is expected when `lv_write_artifacts` is false; native verdicts and
manifest status still describe the review outcome.

Published run files are stored in `_output_archives` as ZIP parts smaller than
95 MB. ZIP parts follow the original hierarchy, for example
`_output_archives/zips/_benchmark/GPT-5.5/L1_8_20261109/`.
Keep the archive folder's `runs`, `compartments`, and `zips` directories together.
The browser reads archived files directly, including files split across parts.
An unpacked file at its original `_benchmark` or `_output` path takes precedence;
missing files still come from the archive. Viewing results does not extract them.

The Raw/Eval toggle follows the saved excerpt state. Unpacked runs with a local
`answer.md` can create, edit, and delete excerpts, including runs that have no
existing excerpts. Edits are saved under the run’s `_eval/excerpts.json`;
concurrent changes require a refresh before saving. ZIP-only runs remain readable
but cannot be edited. Unpack the answer first to enable editing. Existing ZIP
content is not rewritten by an edit; repack the run to update its archive.

The browser launcher opens the webpage automatically. Use `python run_browser.py --no-open`
to start only the server. At startup, a background metadata check looks for missing
unpacked output files without reading or hashing their contents. A popup offers
extraction only when something is missing; fully unpacked outputs need no popup.
Choosing **Read from ZIPs** leaves them compressed. **Unpack missing files**
extracts in the background, verifies the data, and preserves existing files.
The existing webharness ZIPs are included in this option; their extracted files
live beside each ZIP in a folder named after it. Unpacking can require substantial
disk space. Restarting the browser offers the choice again if files remain packed.

To unpack without the browser, run `python unpack_outputs.py` from the repository
root, or invoke that script by its full path from another folder. It verifies the
archives and preserves existing files. `python unpack_outputs.py --check` performs
only the metadata check (exit status 1 means files still need unpacking).

Analysis-run times exclude recorded solver execution. Overlapping solver intervals
count once; unavailable timings are left blank. The detailed diagnostic timeline
retains wall-clock time. Saved web timing estimates and upper bounds are identified
in the timing tooltips. API account names are not displayed in the navigation.

To package another completed run with the shared `zip_images` writer:

```powershell
python -m zip_images.output_zips.output_packs _output/ModelName/L1_4_YYYYMMDD
```

This command verifies the ZIPs and reconstructed file hashes and keeps the
original files. On subsequent calls it rewrites affected ZIP parts in place;
unchanged parts retain their names and bytes, and unchanged members are copied
without recompression. It creates no version or update ZIPs. Extra parts are
needed only when changed or added data exceeds the existing capacity.

Loose files overlay the archived inventory, so a partial unpack does not delete
other archived files. Use `--delete path/inside/run` to explicitly remove a file or directory
from an existing archive. Replacements are verified before publication, with
rollback if replacement fails. Run the same command again to recover an
interrupted replacement. The command does not run agents or solvers. Use
`--all-benchmark` to package all model/run directories under `_benchmark`.

Published benchmark traces are anonymized inspection copies. Their scientific
values are retained, but historical hashes do not verify edited text and these
copies are not exact-replay inputs.

The topology switch controls the current native topology-cleanup option.
Turning it off does not recreate an older solver version. Other solver
improvements remain active.

Offline checks, requiring no model credentials:

```powershell
python scripts/run_analysis.py --check
python run_browser.py --check
```

## License and citation

The original software and documentation are Copyright (c) 2026 Yunkai Sun,
released under the [MIT License](LICENSE). Source data and third-party
components retain their respective terms; see [NOTICE](NOTICE) and the
preserved [NIST data terms](docs/licenses/NIST_SRD46_README.txt).
Use [CITATION.cff](CITATION.cff) to cite the software, and cite NIST SRD 46
and the original scientific sources for the constants used.
