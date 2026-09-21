# Memory Management MCP Tools

File-backed structured-markdown working memory, session management,
tool-result instrumentation, and run-level observability hooks.

## Files

| File | Purpose |
|------|----------|
| `memory_local_storage_io.py` | `WorkingMemory` class — read/write structured markdown |
| `memory_management_MCP_tools.py` | 8 MCP tool functions callable from agent loops |
| `memory_tool_result_instrumentation_helper.py` | `make_instrumented_wrapper()` — wraps tool callables with WM recording + JSON parsing |
| `general_memory_hooks.py` | `BaseWorkingMemory` abstract base with `record_tool_result()`, WM anchor hooks |
| `memory_merger_helpers_and_agent.py` | Memory merging utilities for multi-session workflows |
| `session_manager_output_storage.py` | `SessionManager` — creates session directories, manages output paths |
| `_memory_hooks_anchors_catalog.py` | Declares `WORKING_MEMORY_LOAD` and `WORKING_MEMORY_RENDER` anchor types |
| `__init__.py` | Package init |

## Memory Structure

Each agent session creates a `.md` file with three sections:

```markdown
# Working Memory

## ID Catalog (PROTECTED — never auto-compacted)
| type | num_id | id | name |
|------|--------|----|------|
| comp | 12 | hexane | hexane |
| prop | 3 | activity_coefficient_<comp_id> | Activity coefficient |

## History (append-only, compactable)
- [L1-query] searched blocks for hexane+ethanol VLE → 4 blocks found
- [L0] stored result_1 from L1 dispatch

## Results (indexed, compactable)
### result_1
block: 10.1016/j.fluid.2014.11.020 #3
finding: 45 blocks, 6498 points, 49 properties
```

## MCP Tool Signatures

| Tool | Signature | Purpose |
|------|-----------|---------|
| `memory_read` | `(section=None) → str` | Read full memory or specific section |
| `memory_append_history` | `(line) → str` | Append to History section |
| `memory_add_result` | `(key, body) → str` | Add indexed result to Results section |
| `memory_catalog_add` | `(type, num_id, id, name) → str` | Add row to ID Catalog |
| `memory_catalog_remove` | `(type, num_id) → str` | Remove from ID Catalog |
| `memory_catalog_list` | `() → str` | List all catalog entries as JSON |
| `memory_compact` | `(section) → str` | Trigger compaction of a section |
| `memory_reset` | `() → str` | Re-initialise to empty template |

## Initialisation

```python
from memory_management_MCP_tools import memory_management_MCP_tools as mem_tools

mem_tools.init(Path("working_memories/Q1.1_memory.md"))
# Now all tool functions operate on that file
```

## Design Rules

- **ID Catalog is PROTECTED** — never compacted, never truncated
- **History** — append-only log; compactable via LLM summarisation
- **Results** — indexed findings; compactable via LLM summarisation
- Thread-safe: each agent session gets its own file

---

## Observability Hooks

The run-level observability recorders (`HistoryRecorder`, `StatsRecorder`) have
been migrated to `general_context_hooks/`:

| Recorder | Module | Output File |
|----------|--------|-------------|
| `HistoryRecorder` | `general_context_hooks/history_tracking_hooks.py` | `run_history.md` |
| `StatsRecorder` | `general_context_hooks/stats_references_tracking_hooks.py` | `reference_stats.md` |

These are passive observers called from the anchor-point system.
See `../general_context_hooks/` for full API details.

---

## Tool-Result Instrumentation (`memory_tool_result_instrumentation_helper.py`)

`make_instrumented_wrapper(name, fn, *, working_mem, agent_hooks, anchor_fn, mem_anchor_record)`

Returns a wrapped version of `fn` that:

1. Executes the original tool function.
2. Determines the result shape (`.raw` dict, plain dict, JSON string, or plain string).
3. For string results, attempts `json.loads()` — if successful, passes `{**parsed_dict, "text": original_string}` to working memory so that structured data (entity IDs, block counts, etc.) is preserved alongside the display text.
4. Fires the `SYNC_WORKING_MEMORY_RECORD` anchor to store the result.
5. Calls `working_mem.record_tool_result(name, stored_result)`.

**Important:** The wrapper does **not** fire `AGENT_RECORD_REFERENCES` — that
anchor is fired exclusively by `react_loop.py` to prevent double-counting.

### Result Shape Handling

| Input Type | JSON Parse | Stored As |
|------------|-----------|-----------|
| Object with `.raw` dict attr | — | `raw` dict directly |
| `dict` | — | Dict directly |
| `str` → valid JSON dict | ✓ | `{**parsed_dict, "text": original_string}` |
| `str` → not JSON | — | `{"text": original_string}` |
| Other | — | `{"text": str(result)}` |

### HistoryRecorder (`general_context_hooks/history_tracking_hooks.py`)

Full chronological event log flushed to `run_history.md`.

| Method | Purpose |
|--------|----------|
| `start_run(agent, prompt, out_path)` | Open new run |
| `log_tool_call(name, params, raw, text, discarded, elapsed_s)` | Record one tool invocation |
| `log_error(name, error)` | Record tool error |
| `log_subagent_event(tool, verdict, char_counts)` | Record subagent KEEP/DISCARD |
| `log_compaction(step, before, after)` | Record LLM compaction |
| `log_stage_compaction(stage, before, after)` | Record deterministic compaction |
| `log_oversized_guard(name, original, truncated)` | Record oversized-result truncation |
| `flush(path=None)` | Write `run_history.md` |

### StatsRecorder (`general_context_hooks/stats_references_tracking_hooks.py`)

Quantitative summary flushed to `reference_stats.md` with 6 sections:

| Section | Content |
|---------|----------|
| 1. Argo Call Summary | Per-model call counts, char volumes, token estimates |
| 2. Data Complexity Summary | Unique compounds, properties, variables, constraints; aggregate DOI/block/datapoint counts |
| 3. DOI & Block References | Deduplicated DOI × block table with datapoint counts |
| 4. Tool Results | Pre-compaction tool result char sizes |
| 5. Compaction Events | Before/after char sizes per compaction step |
| 6. Argo Call Detail Log | Per-call timestamps, char volumes, durations |

| Method | Purpose |
|--------|----------|
| `start_run(agent_label)` | Open new run |
| `log_tool_result(name, raw_chars, text_chars, discarded)` | Record tool result size |
| `log_subagent_verdict(tool, verdict, sent, received)` | Record subagent char flow |
| `log_argo_call(model, role, sent_chars, resp_chars, elapsed_s)` | Record one LLM call |
| `log_compaction(step, before_chars, after_chars)` | Record compaction event |
| `log_entity_references(tool_name, raw_result)` | Extract & store entity refs (compounds, properties, variables, constraints) from raw tool output |
| `log_doi_block_references(tool_name, raw_result)` | Extract DOI + block_number + n_datapoints from raw tool output |
| `flush(output_path)` | Write `reference_stats.md` |
