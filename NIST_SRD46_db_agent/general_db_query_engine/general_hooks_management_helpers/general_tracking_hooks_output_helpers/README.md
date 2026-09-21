# general_tracking_hooks_output_helpers — Output Writers & Answer Cleaner

Shared output-file writers and answer-cleaning utilities for test
runners.  Produces standardised per-prompt result files, tool traces,
test summaries, and JSON traces.

---

## Modules

| File | Exports | Purpose |
|------|---------|---------|
| `answer_cleaner.py` | `clean_answer(raw) → str` | Strip `<tool_call>`/`<tool_result>` XML, echoed turns, bare JSON artefacts, excessive newlines. Fallback: truncated tail. |
| `output_writers.py` | `get_status()`, `write_result_md()`, `write_history_md()`, `write_summary_md()`, `write_json_trace()` | All file-writing functions for the test harness |
| `__init__.py` | *(re-exports above)* | Package API |

---

## Expected Result Dict

All writers expect a dict with:

| Key | Type | Required |
|-----|------|----------|
| `prompt_id` | `str` | yes |
| `prompt_text` | `str` | yes |
| `answer` | `str` | yes |
| `iterations` | `int` | yes |
| `elapsed_s` | `float` | yes |
| `timed_out` | `bool` | yes |
| `tool_history` | `list[dict]` | yes |
| `error` | `str \| None` | optional |
| `verdict` | `str \| None` | optional |
| `working_memory` | `str \| None` | optional |
| `final_context` | `str \| None` | optional |

---

## Output Files

| Writer | File Pattern | Notes |
|--------|-------------|-------|
| `write_result_md` | `{prompt_id}_result.md` | Stats line + cleaned answer + optional verdict |
| `write_history_md` | `{prompt_id}_run_history.md` | Rich mode: collapsible `<details>` blocks; compact mode: step list |
| `write_summary_md` | `TEST_SUMMARY_{ts}.md` | Multi-prompt table with speedup calc |
| `write_json_trace` | `TEST_TRACE_{ts}.json` | All results; `working_memory`/`final_context` replaced by `*_chars` counts |

---

## Status Derivation

`get_status(result)` returns:

| Status | Condition |
|--------|-----------|
| `'ERROR'` | `result['error']` is truthy |
| `'TIMEOUT'` | `result['timed_out']` is True |
| `'OK'` | Otherwise |
