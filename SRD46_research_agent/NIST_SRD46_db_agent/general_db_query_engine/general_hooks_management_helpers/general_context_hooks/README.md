# Shared context hooks

These hooks provide time reminders, history/statistics recording, visible reasoning-tag capture, post-job review and context compaction for native agent loops. Callers supply their configuration and lifecycle bindings.

## Modules

| Module | Entry points and behavior |
|---|---|
| `time_budget_reminder_hooks.py` | `TimeBudgetTracker` tracks effective agent time with credited tool exclusions and issues configured reminders. |
| `history_tracking_hooks.py` | `HistoryRecorder` and the `history_recorder` singleton record calls, compaction and internal errors. |
| `stats_references_tracking_hooks.py` | `StatsRecorder` accumulates API usage, tool sizes, references and compaction statistics. |
| `reasoning_token_tracking_hooks.py` | `ReasoningTokenTracker.log_reasoning_from_response` records visible `<reasoning>`/`<thought>` text without modifying the supplied response. It does not expose provider-hidden reasoning. |
| `self_compactor_interactive_hooks.py` | `InteractiveCompactor`, `compact_memory`, `build_compaction_reminder` and `parse_compaction_guidance` implement context selection, compression, validation and guidance. |
| `postjob_verdict_hooks.py` | `build_tool_trace`, `run_verdict_core` and `save_final_context` support final review and context saving. |
| `context_cleanup_compactor_hooks.py` | Deterministic tool/history cleanup and compaction helpers. |
| `_context_hooks_anchors_catalog.py` | Declares supported context-hook anchor types. |

## Lifecycle

Native wrappers bind hooks at agent startup, before model calls, after tools, during compaction and at completion. History and statistics recorders observe execution and write audit files. Context compaction is active: it can invoke selection/compression/validation calls and replace the supplied conversation history. It must not be described as passive logging.

`HistoryRecorder.log_internal_error` retains caught engine/hook errors for inspection. Lifecycle bindings route shared singleton access to the active agent's recorders. Output paths and effective configuration belong to the caller; a recorder does not choose a model, provider or scientific question.

Time/compaction settings are read from the active engine configuration. Visible reasoning tags are text delimiters, separate from provider API reasoning-effort and thinking-budget settings.
