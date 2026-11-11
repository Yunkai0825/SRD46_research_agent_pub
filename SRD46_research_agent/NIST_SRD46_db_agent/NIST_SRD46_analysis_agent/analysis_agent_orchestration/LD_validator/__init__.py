"""LD validator package — LLM quality gate for the L1 analysis sub-agent.

Re-exports the public surface consumed by ``L1_subagent``:

* :func:`validate`
* :func:`format_hints`
"""
from .ld_validator import validate, format_hints

__all__ = ["validate", "format_hints"]
