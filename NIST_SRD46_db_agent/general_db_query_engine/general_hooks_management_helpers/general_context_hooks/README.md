# general_context_hooks — Cross-Agent Runtime Hooks

> Passive observers that inject context, log history, and track
> statistics across the **Query Agent**, **Analysis Agent**, and **Main Agent**.

---

## Purpose

Every module in this package exposes **hook functions** that are called
by the ReAct loop (`react_loop.agent_turn` / `react_loop_async.async_agent_turn`)
at well-defined points (pre-turn, post-tool, post-compaction, wrap-up).
Hooks never modify tool results or LLM responses — they only **append**
context messages or **write** to output files.

---

## Design Principles

| Principle | Detail |
|-----------|--------|
| **Agent-agnostic** | Each hook receives the caller's `cfg` module; no hard import of any agent config |
| **Thread-safe** | `HistoryRecorder` and `StatsRecorder` are `threading.local()` singletons |
| **Passive** | Hooks observe — they never block, retry, or alter the data path |
| **Configurable** | Thresholds, caps, and format strings come from the active `EngineConfig` |

---

## Modules

| File | Class / Entry Point | Role |
|------|---------------------|------|
| `time_budget_reminder_hooks.py` | `TimeBudgetTracker` | Tracks effective agent time after credited tool exclusions and injects graduated reminders at `WARN_THRESHOLDS`. It never halts the loop or suppresses tools. |
| `self_compactor_interactive_hooks.py` | `run_compaction()`, `guidance_hook()` | Three-phase LLM compaction (SELECT → COMPRESS → VALIDATE). Fires when accumulated message chars exceed `COMPACTION_TRIGGER_CHARS`. Also injects a mid-turn guidance nudge. |
| `history_tracking_hooks.py` | `HistoryRecorder` | Thread-local singleton. Logs every tool call, sub-agent dispatch, and compaction event to `run_history.md`. Also provides **internal error logging** (`log_internal_error()`) and **Internal Errors** rendering. Provides `get_recorder()` accessor. |
| `stats_references_tracking_hooks.py` | `StatsRecorder` | Thread-local singleton. Accumulates Argo API token counts, tool result sizes, compaction metrics, and **entity/DOI/block references** → `reference_stats.md`. Handles **polymorphic** tool-result summaries (str vs dict). Provides `get_recorder()` / `set_active_recorder()` / `clear_active_recorder()` accessors. |
| `postjob_verdict_hooks.py` | *(placeholder — empty)* | Reserved for post-job verdict logging. Not yet implemented. |
| `reasoning_token_tracking_hooks.py` | `capture_reasoning_tokens()` | Strips `<reasoning>…</reasoning>` blocks from LLM responses and writes them to `reasoning_tokens_stripped.md`. Provides `set_active_reasoning_tracker()` / `clear_active_reasoning_tracker()`. Wired to `ON_REASONING` anchor. |
| `context_cleanup_compactor_hooks.py` | `StageCompactor`, `extract_note()`, `compact_short_args()`, `compact_tool_calls_for_memory()`, `stage_compact_batch()`, `trim_old_tool_results()` | Deterministic (non-LLM) context cleanup and compaction utilities. |
| `_context_hooks_anchors_catalog.py` | `CONTEXT_ANCHOR_TYPES` (set of 31 anchor-type strings: prompt 8, answer 8, time-budget 5, compaction 10) | Declares which anchor types this package consumes — used by `build_engine_hooks()` to validate wiring. |

---

## Internal Error Logging (`history_tracking_hooks.py`)

The `HistoryRecorder` provides a **non-fatal error logging** mechanism.
Errors caught deep in the engine (e.g. failed JSON parse in `react_loop.py`,
failed anchor callback in `engine_hooks_anchors.py`) are logged via
`log_internal_error()` and batch-rendered in `run_history.md` at flush time.
This avoids swallowing errors silently while keeping the agent pipeline alive.

### `_InternalError` Dataclass

```python
@dataclass
class _InternalError:
    source: str          # e.g. "react_loop", "engine_hooks"
    error_type: str      # e.g. "json_parse", "anchor_callback"
    tool_name: str       # tool or anchor that failed
    message: str         # exception message
    context_preview: str # first 500 chars of the failing data
    timestamp: str       # ISO timestamp
```

### `log_internal_error()` Method

```python
recorder.log_internal_error(
    source="react_loop",
    error_type="json_parse",
    tool_name="query_thermoml",
    message="Expecting value: line 1 column 1 (char 0)",
    context_preview="## Parallel Query Results\n...",
)
```

### Rendering in `run_history.md`

At flush time, if `internal_errors` is non-empty, an **"## Internal Errors"**
section is appended with a summary table and detailed context previews:

```markdown
## Internal Errors

| # | Source | Type | Tool | Message |
|---|--------|------|------|---------|
| 1 | react_loop | json_parse | query_thermoml_parallel | Expecting value … |

### Error 1 Detail
- **Timestamp**: 2026-04-07T22:58:12
- **Context preview** (500 chars):
  ## Parallel Query Results …
```

---

## Hook Injection Points (Anchor-Based)

Since v5.0, hooks are wired through the **anchor-point architecture**
(`AnchorPoint` + `anchor()` dispatch in `engine_hooks_anchors.py`).
The legacy injection-point names are shown alongside their anchor equivalents:

```
agent_turn() loop iteration
   │
   ├─ LLM_CALL_BEFORE ────────── TimeBudgetTracker.check()
   │                               → injects "[TIME WARNING]" system message
   │
   ├─ ON_REASONING ────────────── capture_reasoning_tokens()
   │                               → strips <reasoning> blocks → .md file
   │
   ├─ ON_TOOL_RESULT ──────────── HistoryRecorder.log_tool_call()
   │                               StatsRecorder.log_tool_result()
   │
   ├─ AGENT_RECORD_REFERENCES ── StatsRecorder.log_entity_references()
   │  (from react_loop.py)         StatsRecorder.log_doi_block_references()
   │                               StatsRecorder.log_raw_counters()
   │
   ├─ ON_COMPACTION ───────────── HistoryRecorder.log_compaction()
   │                               StatsRecorder.log_compaction()
   │
   ├─ COMPACTION_GUIDANCE ─────── guidance_hook()
   │                               → appends mid-turn steering prompt
   │
   └─ FINAL_ANSWER_AFTER ─────── HistoryRecorder.flush()
                                  StatsRecorder.flush()
```

---

## Polymorphic Summary Handling (`stats_references_tracking_hooks.py`)

The `StatsRecorder.log_entity_references()` method handles results from
multiple tool types that return **different shapes**:

| Shape | Source | Handling |
|-------|--------|----------|
| `dict` with `summary` key | `query_thermoml` (single) | Extract entity counts from structured summary dict |
| `dict` with `resolved_compounds` list | Raw JSON results | Extract compound details from list of dicts |
| `str` (plain markdown) | `query_thermoml_parallel` | No entity extraction — markdown text has no parseable structure |
| `dict` with `blocks_found` list | L1 block results | Extract DOI, block_number, n_datapoints per block |

All extraction methods use `isinstance` guards to silently skip
malformed entries, ensuring entity tracking never crashes the pipeline.

---

## Config Fields Consumed

| Hook Module | Config Fields |
|-------------|--------------|
| `TimeBudgetTracker` | `WARN_THRESHOLDS`, `MAX_WRAP_WARNINGS`, `MAX_TURN_SECONDS` |
| `self_compactor` | `COMPACTION_TRIGGER_CHARS`, `SUMMARY_MAX_CHARS`, `GUIDANCE_MAX_TOKENS`, `COMPACTOR_TEMPERATURE`, `COMPACTOR_MAX_TOKENS` |
| `HistoryRecorder` | *(none — writes unconditionally)* |
| `StatsRecorder` | *(none — writes unconditionally)* |
