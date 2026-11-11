"""
Pass-through compactor hooks for tool results and per-phase artifacts.

Both hooks return their input unchanged.
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
