"""LC2_3 dedup LLM pathways.

Two distinct pathways collaborate to produce per-group keep decisions:

* :func:`run_group_agent`      — one agent per multi-member group.
* :func:`run_singletons_agent` — one batched agent for all singletons.
"""

from __future__ import annotations

from .per_stoich_group_agent import run_group_agent
from .singleton_agent import run_singletons_agent

__all__ = ["run_group_agent", "run_singletons_agent"]
