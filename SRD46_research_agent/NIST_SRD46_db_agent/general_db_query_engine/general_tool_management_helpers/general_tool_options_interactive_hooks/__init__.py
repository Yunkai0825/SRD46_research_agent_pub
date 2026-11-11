"""
Shared pre-execution guidance — tool-option auto-fill framework.
================================================================
Provides a base ``PreExecutionGuidance`` dataclass that agent-specific
hooks can subclass.  The subclass implements ``check_and_fill()`` which
inspects a tool's call kwargs, auto-fills missing params when possible,
and returns a guidance string to block execution when auto-fill fails.

Also provides ``ToolCallGuidance`` — a generic two-tier validation hook
that catches tool-name typos and kwargs mistakes before execution.
Agents supply a ``registry_provider`` callback to their own tool menu.

Public API
----------
PreExecutionGuidance  — base dataclass (subclass per agent)
ToolCallGuidance      — generic two-tier (name + kwargs) validation hook
block_msg             — reusable "BLOCKED" message formatter
validate_batch_args   — generic malformed-arg batch validator
                        (bind at SYNC_BATCH_PRE_VALIDATE)
"""

from ._pre_execution_guidance import (
    PreExecutionGuidance,
    block_msg,
)
from ._tool_call_guidance import ToolCallGuidance
from ._arg_schema_validator import validate_batch_args

__all__ = [
    "PreExecutionGuidance",
    "ToolCallGuidance",
    "block_msg",
    "validate_batch_args",
]
