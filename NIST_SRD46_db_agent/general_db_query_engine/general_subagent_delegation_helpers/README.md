# general_subagent_delegation_helpers — Shared Subagent Delegation Patterns

Reusable primitives for any agent that delegates work to another
agent's public API.  Extracted from the main agent's
`subagent_delegation_tools.py` so that both the **Main Agent** and the
**Analysis Agent** (and any future agent) share identical session
nesting, question enrichment, result extraction, parallel dispatch,
and tracking-file combination logic.

---

## Dependency Injection Pattern

`SubagentSessionManager` takes a `get_session` callable (zero-arg →
`SessionManager | None`) so this package **never imports agent-specific
code**.  The caller supplies its own hook catalog's session accessor:

```python
from ...general_db_query_engine.general_subagent_delegation_helpers import (
    SubagentSessionManager,
)
_sessions = SubagentSessionManager(
    get_session=lambda: hook_catalog.session_manager  # injected
)
```

---

## Public Exports

All five symbols are re-exported from `__init__.py`.

| Symbol | Module | Signature | Purpose |
|--------|--------|-----------|---------|
| `SubagentSessionManager` | `_session_nesting.py` | `(get_session: Callable[[], SessionManager \| None])` | Thread-safe nested session dirs (`<parent>/<agent>_runs/run_<N>/`) |
| `build_full_question` | `_question_builder.py` | `(question, purpose="", tasks="", context="") -> str` | Injects `[Purpose:]`, `[Tasks:]`, `[Context:]` markers |
| `extract_run_result` | `_result_extractor.py` | `(result, agent_type, question="", session_dir=None, *, extra=None) -> dict` | Flat dict from any `RunResult`-like object |
| `dispatch_parallel` | `_parallel_dispatch.py` | `(tasks_json, runner_fn, *, max_workers=3, ...) -> dict` | `ThreadPoolExecutor` with label mgmt, error capture, ordered results |
| `merge_subagent_tracking` | `_tracking_combiner.py` | `(main_dir, subagent_dir, agent_type, label="") -> None` | Parses + merges `reference_stats.md`, `run_history.md`, `reasoning_tokens_stripped.md` with Source tagging |

---

## Module Details

### `_session_nesting.py` — `SubagentSessionManager`

Thread-safe manager that creates nested subdirectories inside a parent
agent's active session so that each subagent run's output is co-located.

- `get_subagent_session_dir(agent_type)` → `Path | None`
- `get_parent_session_dir()` → `Path | None`

### `_question_builder.py` — `build_full_question()`

Prepends / appends structured markers to a question string before
dispatching it to a subagent.

### `_result_extractor.py` — `extract_run_result()`

Extracts a standardised flat dict (`answer`, `iterations`,
`elapsed_seconds`, `tool_count`, `timed_out`, `agent`, …) from any
`RunResult`-like object returned by an agent's public API.

### `_parallel_dispatch.py` — `dispatch_parallel()`

Wraps `ThreadPoolExecutor` with JSON task-array parsing, per-task
kwargs extraction, error capture, and ordered result collection.
Returns `{"n_tasks": N, "results": [...]}`.

### `_tracking_combiner.py` — `merge_subagent_tracking()`

Parses markdown tables from subagent tracking files, adds a **Source**
column to every data row, and writes/updates combined files in the
parent's session directory.  Also includes generic table-parsing helpers
(`_extract_tables`, `_recompute_total`, `_render_table`).

---

## Consumers

| Agent | Module | Imports |
|-------|--------|---------|
| Main Agent | `main_agent_toobox/subagent_delegation_tools.py` | All 5 exports |
| Analysis Agent | `analysis_agent_toolbox/sibling_agent_delegation_tools/query_agent_tool.py` | All 5 exports |
