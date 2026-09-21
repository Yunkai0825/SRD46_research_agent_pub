"""
Tool anchor catalog.
====================
All generic tool-domain anchor points are declared here.
"""

from __future__ import annotations

from ..general_argo_engine_helpers.engine_hooks_anchors import define_anchor

SYNC_TOOL_RESULT_RECORDED = define_anchor(
    "sync_tool_result_recorded",
    "tool.sync.result.recorded",
)
SYNC_TOOL_PURPOSE_ERROR_RECORDED = define_anchor(
    "sync_tool_purpose_error_recorded",
    "tool.sync.purpose_error.recorded",
)
SYNC_TOOL_ERROR_RECORDED = define_anchor(
    "sync_tool_error_recorded",
    "tool.sync.error.recorded",
)
SYNC_TOOL_CALL_RECORDED = define_anchor(
    "sync_tool_call_recorded",
    "tool.sync.call.recorded",
)
SYNC_BATCH_SUMMARY_BUILD = define_anchor(
    "sync_batch_summary_build",
    "tool.sync.batch_summary.build",
)
SYNC_BATCH_PRE_VALIDATE = define_anchor(
    "sync_batch_pre_validate",
    "tool.sync.batch_pre_validate",
)
SYNC_TOOL_GUIDANCE_CHECK = define_anchor(
    "sync_tool_guidance_check",
    "tool.sync.tool_guidance.check",
)
SYNC_TOOL_VALIDATION_BLOCKED = define_anchor(
    "sync_tool_validation_blocked",
    "tool.sync.validation_blocked",
)
SYNC_STAGE_COMPACTION_BUILD = define_anchor(
    "sync_stage_compaction_build",
    "tool.sync.stage_compaction.build",
)
SYNC_STAGE_COMPACTION_RECORDED = define_anchor(
    "sync_stage_compaction_recorded",
    "tool.sync.stage_compaction.recorded",
)
SYNC_TOOL_CALLS_MEMORY_COMPACT = define_anchor(
    "sync_tool_calls_memory_compact",
    "tool.sync.tool_calls_memory.compact",
)
SYNC_TOOL_RESULT_INJECT = define_anchor(
    "sync_tool_result_inject",
    "tool.sync.tool_result.inject",
)

ASYNC_TOOL_RESULT_RECORDED = define_anchor(
    "async_tool_result_recorded",
    "tool.async.result.recorded",
)
ASYNC_TOOL_PURPOSE_ERROR_RECORDED = define_anchor(
    "async_tool_purpose_error_recorded",
    "tool.async.purpose_error.recorded",
)
ASYNC_TOOL_ERROR_RECORDED = define_anchor(
    "async_tool_error_recorded",
    "tool.async.error.recorded",
)
ASYNC_TOOL_CALL_RECORDED = define_anchor(
    "async_tool_call_recorded",
    "tool.async.call.recorded",
)
ASYNC_TOOL_CALLS_MEMORY_COMPACT = define_anchor(
    "async_tool_calls_memory_compact",
    "tool.async.tool_calls_memory.compact",
)
ASYNC_TOOL_RESULT_INJECT = define_anchor(
    "async_tool_result_inject",
    "tool.async.tool_result.inject",
)

SUBAGENT_DELEGATE = define_anchor(
    "subagent_delegate",
    "tool.subagent.delegate",
)

TOOL_EXEC_ANCHORS = (
    SYNC_TOOL_RESULT_RECORDED,
    SYNC_TOOL_PURPOSE_ERROR_RECORDED,
    SYNC_TOOL_ERROR_RECORDED,
    SYNC_TOOL_CALL_RECORDED,
    SYNC_BATCH_PRE_VALIDATE,
    SYNC_TOOL_GUIDANCE_CHECK,
    SYNC_TOOL_VALIDATION_BLOCKED,
    ASYNC_TOOL_RESULT_RECORDED,
    ASYNC_TOOL_PURPOSE_ERROR_RECORDED,
    ASYNC_TOOL_ERROR_RECORDED,
    ASYNC_TOOL_CALL_RECORDED,
)
TOOL_COMPACTION_ANCHORS = (
    SYNC_BATCH_SUMMARY_BUILD,
    SYNC_STAGE_COMPACTION_BUILD,
    SYNC_STAGE_COMPACTION_RECORDED,
    SYNC_TOOL_CALLS_MEMORY_COMPACT,
    SYNC_TOOL_RESULT_INJECT,
    ASYNC_TOOL_CALLS_MEMORY_COMPACT,
    ASYNC_TOOL_RESULT_INJECT,
)
SUBAGENT_ANCHORS = (SUBAGENT_DELEGATE,)
TOOL_ANCHORS = (*TOOL_EXEC_ANCHORS, *TOOL_COMPACTION_ANCHORS, *SUBAGENT_ANCHORS)

TOOL_EXEC_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in TOOL_EXEC_ANCHORS)
TOOL_COMPACTION_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in TOOL_COMPACTION_ANCHORS)
SUBAGENT_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in SUBAGENT_ANCHORS)
TOOL_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in TOOL_ANCHORS)

__all__ = [
    "SYNC_TOOL_RESULT_RECORDED",
    "SYNC_TOOL_PURPOSE_ERROR_RECORDED",
    "SYNC_TOOL_ERROR_RECORDED",
    "SYNC_TOOL_CALL_RECORDED",
    "SYNC_BATCH_PRE_VALIDATE",
    "SYNC_BATCH_SUMMARY_BUILD",
    "SYNC_STAGE_COMPACTION_BUILD",
    "SYNC_STAGE_COMPACTION_RECORDED",
    "SYNC_TOOL_CALLS_MEMORY_COMPACT",
    "SYNC_TOOL_RESULT_INJECT",
    "SYNC_TOOL_GUIDANCE_CHECK",
    "SYNC_TOOL_VALIDATION_BLOCKED",
    "ASYNC_TOOL_RESULT_RECORDED",
    "ASYNC_TOOL_PURPOSE_ERROR_RECORDED",
    "ASYNC_TOOL_ERROR_RECORDED",
    "ASYNC_TOOL_CALL_RECORDED",
    "ASYNC_TOOL_CALLS_MEMORY_COMPACT",
    "ASYNC_TOOL_RESULT_INJECT",
    "SUBAGENT_DELEGATE",
    "TOOL_EXEC_ANCHORS",
    "TOOL_COMPACTION_ANCHORS",
    "SUBAGENT_ANCHORS",
    "SUBAGENT_ANCHOR_TYPES",
    "TOOL_ANCHOR_TYPES",
]
