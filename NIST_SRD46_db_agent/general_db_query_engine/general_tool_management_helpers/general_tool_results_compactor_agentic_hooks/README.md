# general_tool_results_compactor_agentic_hooks — Tool-Result Triage

Two-layer pipeline that compresses every tool result before it enters
the conversation context: hardcoded dict→markdown compaction followed
by an LLM subagent KEEP/DISCARD decision.

---

## Purpose

Shared by the query agent, analysis agent, and main agent.  Each
caller passes its own `client_factory` and `cfg`; the pipeline logic
is agent-agnostic.

---

## Modules

| File | Exports | Purpose |
|------|---------|---------|
| `_search_tool_results_compact_subagent.py` | `ToolResult`, `ToolResultCompactor`, `call_tool_subagent()`, `parse_subagent_response()` | All implementation |
| `__init__.py` | *(re-exports above)* | Package API |

---

## Two-Layer Pipeline

```
raw dict ──▶ Layer 1: compact_tool_result() ──▶ markdown
               │  per-tool compactor_fn from AgentToolCatalog
               │  fallback: truncated JSON
               ▼
           Layer 2: call_tool_subagent()
               │  ReAct LLM subagent
               │  emits <thought>, <action>KEEP|DISCARD</action>
               ▼
           ToolResult(.raw, .text, .discarded)
```

### Guards

| Condition | Behaviour |
|-----------|-----------|
| Compact markdown > `SUBAGENT_CHAR_LIMIT` | Subagent skipped; structured stats+preview returned |
| LLM call fails | Raw compacted markdown returned with `[Subagent unavailable]` header |

---

## ToolResult dataclass

| Field | Type | Description |
|-------|------|-------------|
| `raw` | `dict` | Original tool output for working memory |
| `text` | `str` | Subagent-processed text for conversation context |
| `discarded` | `bool` | `True` when subagent chose DISCARD |

`__str__` returns `.text`, so the engine can call `str(result)` seamlessly.

---

## Side-Logging

Every verdict (KEEP / DISCARD / OVERSIZED / FALLBACK) is logged to
`history_recorder` and `stats_recorder` hooks.
