"""LV validator package — LLM review of the L0 orchestrator's final answer.

Re-exports the public surface consumed by ``L0_orchestrator``:

* :func:`review` — one reviewer turn; returns the verdict record
* :func:`host_checks` — deterministic flags fed to the reviewer; those in
  :data:`SCREENING_FLAGS` return the turn to L0 unless the reviewer waives
  them (:func:`screening_checks` selects them)
* :func:`bounce_notice` / :func:`call_skeleton` — the host turn that gives
  L0 the turn back after an ``execution_failure``
* :func:`strip_system_prompt`
* :data:`EXECUTION_FAILURE`
"""
from .lv_validator import (
    EXECUTION_FAILURE,
    EXECUTION_INCOMPLETE_TAG,
    SCREENING_FLAGS,
    bounce_notice,
    call_skeleton,
    host_checks,
    review,
    screening_checks,
    strip_system_prompt,
)

__all__ = [
    "review", "host_checks", "screening_checks", "bounce_notice", "call_skeleton",
    "strip_system_prompt", "EXECUTION_FAILURE", "EXECUTION_INCOMPLETE_TAG",
    "SCREENING_FLAGS",
]
