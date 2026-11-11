"""LC2_4 repair subagent.

LLM agent that repairs a free-energy card which failed the solver's own
parser, using generic markdown-editing tools and re-validating against
the same solver parser after each edit.
"""
from .lc2_4_repair_agent import run_repair_agent

__all__ = ["run_repair_agent"]
