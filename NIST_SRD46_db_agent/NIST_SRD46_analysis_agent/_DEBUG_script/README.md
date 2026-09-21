# Analysis development runners

The maintained runners use repository-local output directories. They are not
executed when the browser or analysis API is imported.

## Benchmark prompt runner

`test_analysis_prompts_batch.py` reads `_DEBUG_input/TEST_PROMPTS.md` and writes
one session per label under `_benchmark/Analysis/<label>/`, together with an
aggregate `_batch_summary_<timestamp>.json`.

```powershell
python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch --list
python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch --only L1_4_Fe_EDTA_vs_citrate --keep
```

Omit `--only` to run the full batch. `--keep` preserves existing session folders;
`--no-debug` disables additional diagnostic traces. Running prompts calls the
configured model service and requires its credentials.

## Other maintained tools

- `run_single_analysis_with_watchdog.py` reads one prompt from a UTF-8 file and
  monitors its analysis session. Use `--help` for the required inputs.
- `test_10_chemistry_prompts.py` runs the authored chemistry checks and writes
  diagnostics under `_output/Diagnostics/Analysis/`.
- `edge_case_matrix/driver.py` runs deterministic solver edge cases. Supply
  `--a-card`, `--a-calc`, `--b-card`, and `--b-calc` to select the Fe Pourbaix and
  Cu-ammonia pH-sweep fixtures explicitly. Results are written under
  `_output/Diagnostics/edge_case_matrix/` by default.
- `edge_case_matrix/dump_nonok.py <results.jsonl>` displays unsuccessful cases.

Maintained regression tests also live beside the components they exercise in
`tests/` directories. Historical one-off scripts and generated diagnostic files
are excluded from the publication source tree.

On Windows hosts with legacy path limits, use a short checkout or mapped-drive
path so deeply nested per-call artifacts remain accessible.
