# general_argo_engine_helpers — Shared ReAct Engine

> Reusable ReAct engine infrastructure used by the Analysis runtime and its
> agent-specific client wrappers.

---

## Purpose

This package provides the core ReAct agentic loop infrastructure:

- **`EngineConfig`** base dataclass (required fields, no defaults) — defines the
  configuration shape that every agent must satisfy.
- **Singleton pattern** — `load_config()` / `get_config()` — each agent
  registers its own `EngineConfig` subclass once at import time; the
  engine modules read it via `get_config()` with zero circular imports.
- **`ArgoClient`** — sync `call()` + async `acall()` for the Argo REST API,
  with factory methods (`for_verdict()`, `for_planner()`) that pull
  parameters from the active config.
- **`agent_turn()`** — synchronous ReAct loop (tool-call parse → execute →
  append → compact cycle).
- **`async_agent_turn()`** — async variant for L2 leaf evaluators.
- **Anchor-point dispatch** — `AnchorPoint` / `anchor()` / `AgentHookCollection`
  — catalog-driven hook firing with error isolation and `log_internal_error`.
- **Agent lifecycle bindings** — `build_agent_lifecycle_bindings()` — shared
  start-tracking / finalize / record-references / verdict / save-context
  pattern with **singleton patching** so shared modules route to the
  currently-active agent's recorders.

---

## Lazy `__init__.py`

To break circular imports between agent config modules and the engine,
`__init__.py` eagerly exports configuration and anchor symbols. Its configuration exports include:

```python
from .engine_config import EngineConfig, load_config, get_config
```

Heavyweight symbols (`ArgoClient`, `agent_turn`, `async_agent_turn`,
`AgentTurnResult`, `truncate_result`, `_normalize_args`, `_PARAM_ALIASES`)
are **lazy-loaded** via `__getattr__` on first access.

---

## Modules

| File | Purpose |
|------|---------|
| `engine_config.py` | `EngineConfig` base dataclass + `load_config()`/`get_config()` singleton |
| `argo_client_caller.py` | `ArgoClient` dataclass — HTTP calls to Argo API; factory methods read `get_config()` |
| `provider_request_options.py` | Validates and applies explicit physical-provider request options |
| `openAI_argo_adapter.py` | Explicit Argo-shaped request / direct OpenAI response translation, with an independent total completion allowance |
| `engine_hooks_anchors.py` | `AnchorPoint`, `AnchorCollection`, `AgentAnchorCollection`, `AgentHookCollection`, `anchor()` dispatch, `build_agent_lifecycle_bindings()`, `compile_hooks()` — the full anchor-point architecture |
| `async_runner.py` | `fan_out()`, `run_phase()`, `run_workflow()` — async parallel task dispatch with semaphore-based concurrency |
| `argo_agent_terminal_ui.py` | Terminal UI helpers for interactive agent sessions |
| `_argo_engine_entry_point.py` | Re-exports all public symbols (used by lazy `__init__`) |

### Direct OpenAI adapter

Direct OpenAI transports call `openAI_argo_adapter.translate(payload, config)`
before HTTP dispatch and `response(body, payload, config)` on the saved physical
response. This module does no HTTP I/O or credential handling. Its config declares
`logical_user`, `openai_model_map` (e.g. `{"gpt55": "gpt-5.5"}` or
`{"gpt6astra": "gpt-6-astra"}`), and
`openai_compatibility={"temperature": "omit", "top_p": "omit", "stop": "local"}`.
`openai_max_completion_tokens` defaults to **32,000 total tokens**, independently
of the unchanged Argo `max_tokens` variable. Reasoning effort is omitted by default. An explicit configured
`reasoning_effort` is forwarded to the provider. This allowance covers reasoning and
visible output together, without reserving a particular split. The adapter never
clips text to enforce a visible-output quota. Existing native stop delimiters are
applied to delivered text and reported in normalization metadata; transports keep
the full physical response and token usage. Argo and Anthropic calls bypass this
module. See the [OpenAI token-limit definition](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

The synchronous loop's optional `tool_completion_check` receives only the current
batch's receipts, after tool execution and memory/history recording. A validated
stage result returns normally before any acknowledgment or compaction call.
LC3_1 uses this for a successful `finalize_method`, retaining its normal card,
reports, statistics and working memory. Invalid finalizations continue through
the existing repair path. This option adds no turns or reminders; other stages
retain their existing completion rules.

Explicit provider options can override physical request sampling, reasoning and token fields without changing the native Argo parameter definitions. Standalone flags and JSON settings are documented in the root README and `scripts/run_analysis.py --guide`.

### `engine_react_helpers/` — ReAct Loop Subsystem

| File | Purpose |
|------|---------|
| `react_loop.py` | `agent_turn()` — synchronous ReAct loop; JSON fast-path guard before `AGENT_RECORD_REFERENCES`; module-level `_hr_mod` import for singleton routing |
| `react_loop_async.py` | `async_agent_turn()` — async variant; reads `L2_MAX_ITERATIONS`, `L2_MAX_SECONDS` |
| `react_helpers.py` | `AgentTurnResult`, `truncate_result()`, `_normalize_args()`; reads `TOOL_RESULT_CHAR_LIMIT`, `COMPACTION_TRIGGER_CHARS` |

### `engine_tool_interface_helpers/` — Tool Interface

| File | Purpose |
|------|---------|
| `tool_call_parser.py` | Parses LLM tool-call XML into structured invocations |
| `tool_menu_agent_interface.py` | Builds the tool menu XML fragment for the system prompt |

---

## Configuration Flow

```
Analysis agent startup
    │
    ├─ from ..SRD46_analysis_argo_config import AGENT_CONFIG
    │       ↓
    │   SRD46AnalysisAgentConfig(EngineConfig)  ← dataclass with all defaults
    │
    ├─ load_config(AGENT_CONFIG)        ← registers singleton
    │
    └─ Engine modules call get_config() at runtime
           ↓
       _active_config → SRD46AnalysisAgentConfig instance
```

Each agent's `{agent}_argo_engine/__init__.py` performs the
`load_config()` call, then re-exports its own `ArgoClient` subclass.

---

## Anchor-Point Architecture (`engine_hooks_anchors.py`)

The **anchor-point system** dispatches registered callbacks at declared execution boundaries.
`engine_hooks_anchors.py` defines the core primitives:

- **`AnchorPoint`** — frozen dataclass with `name` + `anchor_types` tuple.
- **`AnchorCollection`** — named collection of anchor points declared by
  per-domain catalogs.
- **`AgentAnchorCollection`** — 5 agent-lifecycle anchor points.
- **`HookBinding`** — callback + anchor types it applies to.
- **`AgentHookCollection`** — mutable agent-level collection with compiled
  `engine_hooks`, lifecycle slots (history, stats, reasoning), and
  a `build_engine_hooks()` method for subclass overrides.
- **`anchor()`** — dispatch function: iterates callbacks for the given
  anchor type, catches exceptions per-callback and calls
  `log_internal_error()` for post-mortem inspection.

```python
from ..general_argo_engine_helpers.engine_hooks_anchors import (
    AnchorPoint, anchor, AGENT_RECORD_REFERENCES,
)

# Fire an anchor — all registered hooks execute in order;
# failures are logged via log_internal_error, never propagated.
result = anchor(AGENT_RECORD_REFERENCES, hooks, tool_name="search_stability", raw_result=parsed)
```

### Agent-Level Anchor Points (5)

These are defined at module scope and collected in `AgentAnchorCollection`:

| Constant | Purpose |
|----------|---------|
| `AGENT_START_TRACKING` | Initialise HistoryRecorder, StatsRecorder, reasoning tracker; **patches `_hr_mod.history_recorder` singleton** |
| `AGENT_FINALIZE_TRACKING` | Flush & reset all recorders; clear active singletons |
| `AGENT_RECORD_REFERENCES` | Extract entity + DOI + block references from a tool result |
| `AGENT_SAVE_FINAL_CONTEXT` | Write full final context to `final_full_context.md` |
| `AGENT_RUN_VERDICT` | Run post-job LLM verdict evaluation |

### Singleton Patching Pattern

When `AGENT_START_TRACKING` fires, the `_start_tracking()` callback
patches `_hr_mod.history_recorder` to point to the current agent's
recorder instance.  This ensures that `log_internal_error()` calls
from deep in `react_loop.py` and `anchor()` — which use the
module-level import `_hr_mod` — route to the correct agent session:

```python
# In _start_tracking() inside build_agent_lifecycle_bindings():
if history is not None and history_out_path is not None:
    history.start_run(agent=agent, prompt=prompt, out_path=str(history_out_path))
    _hr_mod.history_recorder = history  # ← singleton patching
```

### Per-Domain Anchor Catalogs

Three catalogs define which anchor types each domain consumes:

| Catalog | Location | Types |
|---------|----------|-------|
| Context | `general_hooks_management_helpers/general_context_hooks/_context_hooks_anchors_catalog.py` | Lifecycle + compaction + subagent |
| Memory | `general_hooks_management_helpers/general_memory_management_tools_hooks_helpers/_memory_hooks_anchors_catalog.py` | Working-memory and memory-append bindings |
| Tool | `general_tool_management_helpers/_tool_hooks_anchors_catalog.py` | All TOOL_* + ON_PURPOSE_ERROR + TOOL_RESULT_INJECT |

### Error Isolation in `anchor()`

Every callback is wrapped in try/except.  Failures are logged via
`log_internal_error()` on the active `HistoryRecorder` and the anchor
continues to fire remaining callbacks:

```python
except Exception as exc:
    _hr_mod.history_recorder.log_internal_error(
        source="engine_hooks",
        error_type="anchor_callback",
        tool_name=f"{anchor_type}/{_cb_name}",
        message=f"{type(exc).__name__}: {exc}",
        context_preview=repr(kwargs)[:500],
    )
    continue  # other callbacks still fire
```

---

## JSON Fast-Path Guard (`react_loop.py`)

Before firing `AGENT_RECORD_REFERENCES`, the ReAct loop applies a
fast-path guard that skips JSON parsing when the tool result clearly
isn't a JSON object (starts with neither `{` nor `[`):

```python
if one_result.lstrip()[:1] in ('{', '['):
    try:
        _raw_dict = json.loads(one_result)
    except (json.JSONDecodeError, ValueError):
        _raw_dict = None
        _hr_mod.history_recorder.log_internal_error(...)
    if isinstance(_raw_dict, dict):
        anchor(AGENT_RECORD_REFERENCES, hooks, tool_name=name, raw_result=_raw_dict)
```

This prevents wasted `json.loads()` calls on the common case of
markdown-formatted tool results (for example, compacted database search results).

---

## EngineConfig Fields

All fields are defined without defaults in the base class.
Agent subclasses provide concrete values.

| Group | Fields | Consumed By |
|-------|--------|-------------|
| API connection | `API_URL`, `API_USER`, `HEADERS` | `ArgoClient.call()` |
| Model names | `MODEL`, `VERDICT_MODEL`, `PLANNER_MODEL` | `ArgoClient` factory methods |
| Generation | `TEMPERATURE`, `TOP_P`, `MAX_TOKENS`, `HTTP_TIMEOUT` | `ArgoClient.call()` |
| L0 loop | `MAX_TOOL_ITERATIONS` (hard turn cap), `MAX_TURN_SECONDS` (reminder scale) | `react_loop.agent_turn()` |
| L2 async | `L2_MAX_ITERATIONS` (hard turn cap), `L2_MAX_SECONDS` (reminder scale) | `react_loop_async.async_agent_turn()` |
| Time warnings | `WARN_THRESHOLDS`, `MAX_WRAP_WARNINGS`, `MAX_EMPTY_WAITS` | `TimeBudgetTracker` (via react_loop) |
| Truncation | `TOOL_RESULT_CHAR_LIMIT`, `TOOL_RESULT_HEAD_CHARS`, `TOOL_RESULT_TAIL_CHARS` | `react_helpers.truncate_result()` |
| Compaction | `COMPACTION_TRIGGER_CHARS`, `SUMMARY_MAX_CHARS`, `GUIDANCE_MAX_TOKENS` | `react_helpers`, compaction hooks |
| Verdict client | `VERDICT_TEMPERATURE`, `VERDICT_MAX_TOKENS` | `ArgoClient.for_verdict()` |
| Compactor client | `COMPACTOR_TEMPERATURE`, `COMPACTOR_MAX_TOKENS` | compaction sub-agent |
| Planner client | `PLANNER_TEMPERATURE`, `PLANNER_MAX_TOKENS` | `ArgoClient.for_planner()` |

---

## Key Design Patterns

### Module-Level `_hr_mod` Import

`react_loop.py` and `engine_hooks_anchors.py` both import the
`history_tracking_hooks` module (not the class) at module scope:

```python
from ...general_hooks_management_helpers.general_context_hooks import (
    history_tracking_hooks as _hr_mod,
)
```

This gives them access to `_hr_mod.history_recorder`, which is
**singleton-patched** by `_start_tracking()` at session start.
The same pattern applies to `StatsRecorder` via `set_active_recorder()`.

### AGENT_RECORD_REFERENCES — Single Call-Site

`AGENT_RECORD_REFERENCES` is fired by the synchronous or asynchronous ReAct loop after
every tool execution, keeping reference statistics at a single collection point:

```
react_loop.py → tool execution → JSON fast-path guard →
  anchor(AGENT_RECORD_REFERENCES, hooks, tool_name=..., raw_result=...)
```

### Preserving a tool result in parallel batches

The synchronous `agent_turn()` accepts an optional `uncompacted_tools`
set. When a parallel batch contains any exact tool name from this set, the
engine retains the batch's normal combined results instead of replacing them
through a batch-summary hook or the generic stage-compaction table:

```python
agent_turn(
    message,
    system_prompt=prompt,
    tools=tools,
    memory=memory,
    uncompacted_tools={"run_analysis_pipeline"},
)
```

The setting is deliberately narrow. It does not change single-tool execution,
per-tool result handling, or later whole-context compaction. Omitting it (or
passing `None` or an empty set) uses the standard batch-compaction behavior.
