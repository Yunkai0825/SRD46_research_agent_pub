"""
Context anchor catalog.
=======================
All generic context-domain anchor points are declared here. Each
anchor point owns a unique anchor type so the engine can identify
behavioural call sites without hardcoded hook semantics.
"""

from __future__ import annotations

from ...general_argo_engine_helpers.engine_hooks_anchors import define_anchor

SYNC_TIME_BUDGET_TRACKER_CREATE = define_anchor(
    "sync_time_budget_tracker_create",
    "context.sync.time_budget.tracker.create",
)
SYNC_TIME_BUDGET_WARNINGS_APPLY = define_anchor(
    "sync_time_budget_warnings_apply",
    "context.sync.time_budget.warnings.apply",
)
SYNC_TIME_BUDGET_HARD_STOP_CHECK = define_anchor(
    "sync_time_budget_hard_stop_check",
    "context.sync.time_budget.hard_stop.check",
)
SYNC_TIME_BUDGET_CREDIT_TOOL = define_anchor(
    "sync_time_budget_credit_tool",
    "context.sync.time_budget.credit.tool",
)
SYNC_TIME_BUDGET_ALL_WARNINGS_CHECK = define_anchor(
    "sync_time_budget_all_warnings_check",
    "context.sync.time_budget.all_warnings.check",
)
SYNC_TIME_BUDGET_FINAL_MESSAGE_BUILD = define_anchor(
    "sync_time_budget_final_message_build",
    "context.sync.time_budget.final_message.build",
)

SYNC_FLAT_PROMPT_BUILD = define_anchor(
    "sync_flat_prompt_build",
    "context.sync.flat_prompt.build",
)
SYNC_SYSTEM_PROMPT_READY = define_anchor(
    "sync_system_prompt_ready",
    "context.sync.system_prompt.ready",
)
SYNC_USER_MESSAGE_READY = define_anchor(
    "sync_user_message_ready",
    "context.sync.user_message.ready",
)
SYNC_LLM_CALL_BEFORE = define_anchor(
    "sync_llm_call_before",
    "context.sync.llm.call.before",
)
SYNC_LLM_RESPONSE_AFTER = define_anchor(
    "sync_llm_response_after",
    "context.sync.llm.response.after",
)
SYNC_REQUIRED_TOOLS_NOTE_APPEND = define_anchor(
    "sync_required_tools_note_append",
    "context.sync.required_tools.note.append",
)
SYNC_FINAL_ANSWER_BEFORE = define_anchor(
    "sync_final_answer_before",
    "context.sync.final_answer.before",
)
SYNC_FINAL_ANSWER_AFTER = define_anchor(
    "sync_final_answer_after",
    "context.sync.final_answer.after",
)
SYNC_WARNING_FINAL_ANSWER_AFTER = define_anchor(
    "sync_warning_final_answer_after",
    "context.sync.warning_final_answer.after",
)
SYNC_HARD_STOP_FINAL_ANSWER_AFTER = define_anchor(
    "sync_hard_stop_final_answer_after",
    "context.sync.hard_stop.final_answer.after",
)
SYNC_FINAL_CONTEXT_CAPTURED = define_anchor(
    "sync_final_context_captured",
    "context.sync.final_context.captured",
)

SYNC_COMPACTION_REMINDER_BUILD = define_anchor(
    "sync_compaction_reminder_build",
    "context.sync.compaction.reminder.build",
)
SYNC_COMPACTION_GUIDANCE_RESPONSE = define_anchor(
    "sync_compaction_guidance_response",
    "context.sync.compaction.guidance.response",
)
SYNC_COMPACTION_GUIDANCE_PARSE = define_anchor(
    "sync_compaction_guidance_parse",
    "context.sync.compaction.guidance.parse",
)
SYNC_COMPACTION_EXECUTE = define_anchor(
    "sync_compaction_execute",
    "context.sync.compaction.execute",
)
SYNC_COMPACTION_RECORDED = define_anchor(
    "sync_compaction_recorded",
    "context.sync.compaction.recorded",
)
SYNC_COMPACTION_STATS_RECORDED = define_anchor(
    "sync_compaction_stats_recorded",
    "context.sync.compaction.stats.recorded",
)
SYNC_COMPACTION_SKIPPED = define_anchor(
    "sync_compaction_skipped",
    "context.sync.compaction.skipped",
)
SYNC_COMPACTION_TRIM_FALLBACK = define_anchor(
    "sync_compaction_trim_fallback",
    "context.sync.compaction.trim_fallback",
)

ASYNC_FLAT_PROMPT_BUILD = define_anchor(
    "async_flat_prompt_build",
    "context.async.flat_prompt.build",
)
ASYNC_LLM_CALL_BEFORE = define_anchor(
    "async_llm_call_before",
    "context.async.llm.call.before",
)
ASYNC_LLM_RESPONSE_AFTER = define_anchor(
    "async_llm_response_after",
    "context.async.llm.response.after",
)
ASYNC_FINAL_ANSWER_BEFORE = define_anchor(
    "async_final_answer_before",
    "context.async.final_answer.before",
)
ASYNC_FINAL_ANSWER_AFTER = define_anchor(
    "async_final_answer_after",
    "context.async.final_answer.after",
)
ASYNC_COMPACTION_EXECUTE = define_anchor(
    "async_compaction_execute",
    "context.async.compaction.execute",
)
ASYNC_COMPACTION_TRIM_FALLBACK = define_anchor(
    "async_compaction_trim_fallback",
    "context.async.compaction.trim_fallback",
)

PROMPT_ANCHORS = (
    SYNC_SYSTEM_PROMPT_READY,
    SYNC_USER_MESSAGE_READY,
    SYNC_FLAT_PROMPT_BUILD,
    SYNC_LLM_CALL_BEFORE,
    SYNC_LLM_RESPONSE_AFTER,
    ASYNC_FLAT_PROMPT_BUILD,
    ASYNC_LLM_CALL_BEFORE,
    ASYNC_LLM_RESPONSE_AFTER,
)
ANSWER_ANCHORS = (
    SYNC_REQUIRED_TOOLS_NOTE_APPEND,
    SYNC_FINAL_ANSWER_BEFORE,
    SYNC_FINAL_ANSWER_AFTER,
    SYNC_WARNING_FINAL_ANSWER_AFTER,
    SYNC_HARD_STOP_FINAL_ANSWER_AFTER,
    SYNC_FINAL_CONTEXT_CAPTURED,
    ASYNC_FINAL_ANSWER_BEFORE,
    ASYNC_FINAL_ANSWER_AFTER,
)
TIME_BUDGET_ANCHORS = (
    SYNC_TIME_BUDGET_TRACKER_CREATE,
    SYNC_TIME_BUDGET_WARNINGS_APPLY,
    SYNC_TIME_BUDGET_HARD_STOP_CHECK,
    SYNC_TIME_BUDGET_CREDIT_TOOL,
    SYNC_TIME_BUDGET_ALL_WARNINGS_CHECK,
    SYNC_TIME_BUDGET_FINAL_MESSAGE_BUILD,
)
COMPACTION_ANCHORS = (
    SYNC_COMPACTION_REMINDER_BUILD,
    SYNC_COMPACTION_GUIDANCE_RESPONSE,
    SYNC_COMPACTION_GUIDANCE_PARSE,
    SYNC_COMPACTION_EXECUTE,
    SYNC_COMPACTION_RECORDED,
    SYNC_COMPACTION_STATS_RECORDED,
    SYNC_COMPACTION_SKIPPED,
    SYNC_COMPACTION_TRIM_FALLBACK,
    ASYNC_COMPACTION_EXECUTE,
    ASYNC_COMPACTION_TRIM_FALLBACK,
)
CONTEXT_ANCHORS = (
    *TIME_BUDGET_ANCHORS,
    *PROMPT_ANCHORS,
    *ANSWER_ANCHORS,
    *COMPACTION_ANCHORS,
)

PROMPT_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in PROMPT_ANCHORS)
ANSWER_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in ANSWER_ANCHORS)
TIME_BUDGET_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in TIME_BUDGET_ANCHORS)
COMPACTION_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in COMPACTION_ANCHORS)
CONTEXT_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in CONTEXT_ANCHORS)

__all__ = [
    "SYNC_TIME_BUDGET_TRACKER_CREATE",
    "SYNC_TIME_BUDGET_WARNINGS_APPLY",
    "SYNC_TIME_BUDGET_HARD_STOP_CHECK",
    "SYNC_TIME_BUDGET_CREDIT_TOOL",
    "SYNC_TIME_BUDGET_ALL_WARNINGS_CHECK",
    "SYNC_TIME_BUDGET_FINAL_MESSAGE_BUILD",
    "SYNC_FLAT_PROMPT_BUILD",
    "SYNC_SYSTEM_PROMPT_READY",
    "SYNC_USER_MESSAGE_READY",
    "SYNC_LLM_CALL_BEFORE",
    "SYNC_LLM_RESPONSE_AFTER",
    "SYNC_REQUIRED_TOOLS_NOTE_APPEND",
    "SYNC_FINAL_ANSWER_BEFORE",
    "SYNC_FINAL_ANSWER_AFTER",
    "SYNC_WARNING_FINAL_ANSWER_AFTER",
    "SYNC_HARD_STOP_FINAL_ANSWER_AFTER",
    "SYNC_FINAL_CONTEXT_CAPTURED",
    "SYNC_COMPACTION_REMINDER_BUILD",
    "SYNC_COMPACTION_GUIDANCE_RESPONSE",
    "SYNC_COMPACTION_GUIDANCE_PARSE",
    "SYNC_COMPACTION_EXECUTE",
    "SYNC_COMPACTION_RECORDED",
    "SYNC_COMPACTION_STATS_RECORDED",
    "SYNC_COMPACTION_SKIPPED",
    "SYNC_COMPACTION_TRIM_FALLBACK",
    "ASYNC_FLAT_PROMPT_BUILD",
    "ASYNC_LLM_CALL_BEFORE",
    "ASYNC_LLM_RESPONSE_AFTER",
    "ASYNC_FINAL_ANSWER_BEFORE",
    "ASYNC_FINAL_ANSWER_AFTER",
    "ASYNC_COMPACTION_EXECUTE",
    "ASYNC_COMPACTION_TRIM_FALLBACK",
    "PROMPT_ANCHORS",
    "ANSWER_ANCHORS",
    "TIME_BUDGET_ANCHORS",
    "COMPACTION_ANCHORS",
    "CONTEXT_ANCHORS",
    "PROMPT_ANCHOR_TYPES",
    "ANSWER_ANCHOR_TYPES",
    "TIME_BUDGET_ANCHOR_TYPES",
    "COMPACTION_ANCHOR_TYPES",
    "CONTEXT_ANCHOR_TYPES",
]
