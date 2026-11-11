# Working memory and tool-result instrumentation

This package provides file-backed Markdown working memory, session paths and wrappers that record tool results. Recorders for full run history and statistics live in the sibling `general_context_hooks` package.

## Memory tools

`memory_local_storage_io.WorkingMemory` manages an ID catalog, history and indexed results. `memory_management_MCP_tools` exposes read, append, catalog, result, compaction and reset operations.

```python
from pathlib import Path
from SRD46_research_agent.NIST_SRD46_db_agent.general_db_query_engine.general_hooks_management_helpers.general_memory_management_tools_hooks_helpers import memory_management_MCP_tools as mem_tools

mem_tools.init(Path("working_memories/example.md"))
```

The ID catalog is protected from compaction. `memory_compact` requires the replacement summary text; it does not call an LLM to invent a summary. A caller that wants model-assisted summarization must obtain that summary before calling the memory tool.

## Modules

| Module | Responsibility |
|---|---|
| `memory_local_storage_io.py` | Structured Markdown storage |
| `memory_management_MCP_tools.py` | Memory tool wrappers |
| `general_memory_hooks.py` | Working-memory base and hook bindings |
| `memory_tool_result_instrumentation_helper.py` | Instrumented tool wrapper |
| `memory_merger_helpers_and_agent.py` | Memory-merging helpers |
| `session_manager_output_storage.py` | Session directory and output management |
| `_memory_hooks_anchors_catalog.py` | Memory anchor declarations |

## Tool-result capture

`make_instrumented_wrapper` executes the original tool, obtains its raw dictionary or text, and records it through the supplied working-memory hooks. JSON object strings retain structured fields alongside the original text. Other strings remain text.

Reference-statistics collection belongs to the synchronous or asynchronous ReAct loop, not this wrapper. Keeping that collection at the loop boundary avoids counting the same tool result twice. Each caller supplies its own session and recorders.

Memory tool bindings are thread-local. Each worker must initialize its own path; concurrent asynchronous sessions sharing a thread are not isolated by this binding alone.
