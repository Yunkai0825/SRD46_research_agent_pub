# `analysis_agent_context_hooks/`

Session-scoped context plumbing for the analysis agent: working memory,
event/stat recording, verdict emission, and (stub) context compaction.
Everything is keyed to a `session_dir` and persisted as small JSON/JSONL
files so any layer (or a debugger) can reconstruct the run.

## Public surface (re-exported from `hook_catalog.py`)

| Export | Module | Purpose |
|--------|--------|---------|
| `AnalysisWorkingMemory` | `memory_hooks/working_memory_hooks.py` | JSON-backed session scratch dict (`working_memory.json`): `get/set/update/append`, `render()` for LLM re-injection, `as_dict()`. |
| `DEFAULT_MEMORY_FILENAME` | `hook_catalog.py` | `"working_memory.json"`. |
| `AnalysisHistoryRecorder` | `tracking_hooks/tracking_hooks.py` | Append-only JSONL event log (`run_history.jsonl`): `log(event_type, **payload)`, `log_phase_start/end`, `log_checkpoint`, `log_tool_call`. |
| `AnalysisStatsRecorder` | `tracking_hooks/tracking_hooks.py` | Phase-keyed counters (`run_stats.json`): `incr(phase_id, key)`, `save()`, `as_dict()`. |
| `run_verdict(session_dir)` | `verdict_hooks/verdict_hooks.py` | Deterministic manifest check → `{verdict: pass \| partial \| skipped_some \| fail, notes, …}`. |
| `save_final_context(session_dir, verdict)` | `verdict_hooks/verdict_hooks.py` | Writes the verdict dict to `session_dir/verdict.json`; returns the path. |
| `compact_tool_result(tool_name, result)` | `compactor_hooks/compactor_hooks.py` | Pass-through stub (reserved for LLM-context compaction). |
| `compact_phase_artifact(phase_id, artifact)` | `compactor_hooks/compactor_hooks.py` | Pass-through stub. |

## Typical session lifecycle

```python
mem   = AnalysisWorkingMemory(session_dir)
hist  = AnalysisHistoryRecorder(session_dir)
stats = AnalysisStatsRecorder(session_dir)
# … agent loop: hist.log_tool_call(...), stats.incr(...), mem.set(...) …
stats.save()
verdict = run_verdict(session_dir)
save_final_context(session_dir, verdict)
```

## Architecture rules

- No LLM calls and no solver imports here — pure session-state I/O.
- All files live directly under the session dir so the artifacts ship
  with the run (see the artifact table in the
  [analysis-agent README](../README.md)).
