"""
Memory anchor catalog.
======================
All generic memory-domain anchor points are declared here.
"""

from __future__ import annotations

from ...general_argo_engine_helpers.engine_hooks_anchors import define_anchor

SYNC_USER_MESSAGE_APPEND = define_anchor(
    "sync_user_message_append",
    "memory.sync.user_message.append",
)
SYNC_PRIOR_CONTEXT_APPEND = define_anchor(
    "sync_prior_context_append",
    "memory.sync.prior_context.append",
)
SYNC_WORKING_MEMORY_RENDER = define_anchor(
    "sync_working_memory_render",
    "memory.sync.working_memory.render",
)
SYNC_WORKING_MEMORY_RECORD = define_anchor(
    "sync_working_memory_record",
    "memory.sync.working_memory.record",
)
SYNC_MEMORY_RESULT_STORE = define_anchor(
    "sync_memory_result_store",
    "memory.sync.result.store",
)
SYNC_MEMORY_HISTORY_APPEND = define_anchor(
    "sync_memory_history_append",
    "memory.sync.history.append",
)
SYNC_ASSISTANT_MESSAGE_APPEND = define_anchor(
    "sync_assistant_message_append",
    "memory.sync.assistant_message.append",
)

ASYNC_USER_MESSAGE_APPEND = define_anchor(
    "async_user_message_append",
    "memory.async.user_message.append",
)
ASYNC_WORKING_MEMORY_RENDER = define_anchor(
    "async_working_memory_render",
    "memory.async.working_memory.render",
)
ASYNC_ASSISTANT_MESSAGE_APPEND = define_anchor(
    "async_assistant_message_append",
    "memory.async.assistant_message.append",
)

WORKING_MEMORY_ANCHORS = (
    SYNC_WORKING_MEMORY_RENDER,
    SYNC_WORKING_MEMORY_RECORD,
    ASYNC_WORKING_MEMORY_RENDER,
)
MEMORY_APPEND_ANCHORS = (
    SYNC_USER_MESSAGE_APPEND,
    SYNC_PRIOR_CONTEXT_APPEND,
    SYNC_MEMORY_RESULT_STORE,
    SYNC_MEMORY_HISTORY_APPEND,
    SYNC_ASSISTANT_MESSAGE_APPEND,
    ASYNC_USER_MESSAGE_APPEND,
    ASYNC_ASSISTANT_MESSAGE_APPEND,
)
MEMORY_ANCHORS = (*WORKING_MEMORY_ANCHORS, *MEMORY_APPEND_ANCHORS)

WORKING_MEMORY_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in WORKING_MEMORY_ANCHORS)
MEMORY_APPEND_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in MEMORY_APPEND_ANCHORS)
MEMORY_ANCHOR_TYPES = frozenset(anchor.anchor_type for anchor in MEMORY_ANCHORS)

__all__ = [
    "SYNC_USER_MESSAGE_APPEND",
    "SYNC_PRIOR_CONTEXT_APPEND",
    "SYNC_WORKING_MEMORY_RENDER",
    "SYNC_WORKING_MEMORY_RECORD",
    "SYNC_MEMORY_RESULT_STORE",
    "SYNC_MEMORY_HISTORY_APPEND",
    "SYNC_ASSISTANT_MESSAGE_APPEND",
    "ASYNC_USER_MESSAGE_APPEND",
    "ASYNC_WORKING_MEMORY_RENDER",
    "ASYNC_ASSISTANT_MESSAGE_APPEND",
    "WORKING_MEMORY_ANCHORS",
    "MEMORY_APPEND_ANCHORS",
    "MEMORY_ANCHORS",
    "WORKING_MEMORY_ANCHOR_TYPES",
    "MEMORY_APPEND_ANCHOR_TYPES",
    "MEMORY_ANCHOR_TYPES",
]
