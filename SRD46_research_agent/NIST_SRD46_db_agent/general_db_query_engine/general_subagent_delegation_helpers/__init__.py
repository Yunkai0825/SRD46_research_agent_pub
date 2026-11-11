"""
Shared subagent delegation helpers.
=====================================
Reusable primitives for any agent that delegates work to another
agent's public API.

- **Session nesting** — ``SubagentSessionManager``
- **Question building** — ``build_full_question``
- **Result extraction** — ``extract_run_result``
- **Parallel dispatch** — ``dispatch_parallel``
- **Tracking combination** — ``merge_subagent_tracking``
"""

from ._session_nesting import SubagentSessionManager
from ._question_builder import build_full_question
from ._result_extractor import extract_run_result
from ._parallel_dispatch import dispatch_parallel
from ._tracking_combiner import merge_subagent_tracking

__all__ = [
    "SubagentSessionManager",
    "build_full_question",
    "extract_run_result",
    "dispatch_parallel",
    "merge_subagent_tracking",
]
