"""
Compactor hook — trim verbose tool output before it lands in an LLM prompt.

For now, a no-op: the deterministic L0/L1/L2 don't run an LLM context
window, so compaction is unnecessary. Stub kept for symmetry with the
query agent so a future LLM swap-in only needs to fill in the body.
"""

from __future__ import annotations

from typing import Any, Dict


def compact_tool_result(tool_name: str, result: Any) -> Any:
    """Default pass-through compactor."""
    return result


def compact_phase_artifact(phase_id: str, artifact: Any) -> Any:
    """Default pass-through compactor for a per-phase artifact dict."""
    return artifact


__all__ = ["compact_tool_result", "compact_phase_artifact"]
