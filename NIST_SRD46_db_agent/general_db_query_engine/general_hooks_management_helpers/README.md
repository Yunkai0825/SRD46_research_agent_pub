# general_hooks_management_helpers — Shared Hook Infrastructure

Parent package for cross-agent hook modules: context hooks, memory
management, output/tracking helpers, and tool-result instrumentation.
All child packages live **under this directory** and are imported via
fully-qualified paths:

```python
from ..general_hooks_management_helpers.general_context_hooks.time_budget_reminder_hooks import ...
from ..general_hooks_management_helpers.general_memory_management_tools_hooks_helpers import ...
```

---

## Child Packages

| Package | Purpose |
|---------|---------|
| `general_context_hooks/` | Runtime hooks — time-budget, compaction, history/stats recorders (with internal error logging), reasoning capture, anchor catalog |
| `general_memory_management_tools_hooks_helpers/` | File-backed working memory (8 MCP tool wrappers), `BaseWorkingMemory`, `SessionManager`, memory anchor catalog, **`memory_tool_result_instrumentation_helper.py`** (shared tool-result wrapper) |
| `general_tracking_hooks_output_helpers/` | Output-file writers (`write_result_md`, `write_summary_md`, `write_json_trace`) and `clean_answer()` |

---

## Shared Tool-Result Instrumentation

`general_memory_management_tools_hooks_helpers/memory_tool_result_instrumentation_helper.py`
provides `make_instrumented_wrapper()` — a factory that wraps any tool
callable so that:

1. The result is stored in working memory via `record_tool_result()`.
2. String results are JSON-parsed when possible so that structured data
   (`id_updates`, `blocks_found`, compound details, etc.) feeds into the
   stats recorder.
3. The `AGENT_RECORD_REFERENCES` anchor is **NOT** fired here — it is
   fired exclusively from `react_loop.py` to prevent double-counting.

Used by both the **Analysis Agent** and **Main Agent** orchestrators.

---

## Anchor Point Integration

Two of the three anchor-point catalogs live under this directory:

| Catalog | Location | Types |
|---------|----------|-------|
| Context anchors (31 types) | `general_context_hooks/_context_hooks_anchors_catalog.py` | PROMPT (8), ANSWER (8), TIME_BUDGET (5), COMPACTION (10) |
| Memory anchors (10 types) | `general_memory_management_tools_hooks_helpers/_memory_hooks_anchors_catalog.py` | WORKING_MEMORY (3), MEMORY_APPEND (7) |

The third catalog (tool anchors, 19 types) lives in `general_tool_management_helpers/`.
