"""
Public entry point for the NIST SRD-46 analysis agent.

The analysis agent is a 3-tier LLM stack over deterministic pipelines::

    L0 (LLM orchestrator)            ← analysis_agent_orchestration/L0_orchestrator/
        │   sole tool entry point: dispatch_l1_pipeline (one per chemical system)
        ▼
    L1 sub-agent (LLM)               ← analysis_agent_orchestration/L1_subagent/
        │   drives the deterministic build-and-solve pipeline:
        │   LC1→LC2→LC3 card building  ← NIST_SRD46_calc_input_building_agentic_pipeline/
        │   numeric solver sweeps      ← NIST_SRD46_core_numcalc_pipeline/
        ▼
    LD validator (LLM quality gate)  ← analysis_agent_orchestration/LD_validator/
            verdict ∈ {supported, contradicted, inconclusive};
            only "contradicted" triggers an L1 retry

L0 is *not* deterministic. It receives the user's natural-language
analysis request and decides — turn by turn — whether to call the
L1 sub-agent (its sole tool entry point) and how to phrase the
``purpose`` and ``tasks`` it passes down. The L1 sub-agent then runs
the deterministic card-building + solver pipeline. This module is just
the thin synchronous wrapper that exposes L0 to external callers.

Usage
-----
>>> from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import SRD46_analysis_run
>>> result = SRD46_analysis_run(
...     "Pourbaix diagram of Cu in glycine",
...     session_dir="./_run_001",
... )
>>> result["answer"]                 # final L0 prose
>>> result["session_dir"]            # where artifacts live
>>> result["timed_out"]              # severe completion gate
>>> result["completion_status"]      # "complete" or "timed_out"
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .analysis_agent_orchestration.L0_orchestrator import run as _l0_run
from .SRD46_analysis_argo_config import resolve_estimate_missing_equilibria

log = logging.getLogger("SRD46.analysis.api")


def SRD46_analysis_run(
    user_request: str,
    *,
    session_dir: str | Path,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    l0_max_iterations: Optional[int] = None,
    l0_reasoning_timeout_s: Optional[float] = None,
    round_number: int = 1,
    prev_context: str = "",
) -> Dict[str, Any]:
    """Drive one end-to-end analysis turn under the LLM-driven L0.

    Parameters
    ----------
    user_request : str
        Natural-language description of the analysis to perform.
    session_dir : str | Path
        Output root for this run. ``answer.md``, ``run_history.md``,
        ``manifest.json`` and any per-pipeline-call sub-directories
        ``L1_call_NN/`` are written here.
    debug : bool
        Forwarded to the L1 sub-agent for full tracebacks on failure.
    estimate_missing_equilibria : bool | None
        Optional per-run override for query-assisted missing-equilibrium
        support. ``None`` inherits the default-false shared setting. The
        resolved value is fixed before L0 or L1 can make an LLM decision.
    l0_max_iterations : int | None
        Optional per-run cap on L0 LLM turns.  This override is scoped to
        L0 and does not mutate or enlarge LC1/LC2/LC3 agent budgets.
    l0_reasoning_timeout_s : float | None
        Optional per-run L0 effective-reasoning-time budget in seconds.
        Time spent inside ``dispatch_l1_pipeline`` remains excluded by the
        ReAct engine.  Callers that require a whole-run wall-clock limit
        must enforce one independently.
    round_number : int
        1-based round index inside a multi-round conversation.
    prev_context : str
        Cleaned full context from the previous round, pre-seeded into L0
        memory (rounds after the first also drop the forced L1 dispatch).
    """
    effective_estimation = resolve_estimate_missing_equilibria(
        estimate_missing_equilibria
    )
    # Announce the session root for passive capture routing (the Anthropic
    # adapter's resolver reads it; env var survives module aliasing/threads).
    _prev_session = os.environ.get("SRD46_ANALYSIS_SESSION_DIR")
    os.environ["SRD46_ANALYSIS_SESSION_DIR"] = str(Path(session_dir).absolute())
    try:
        return _l0_run(
            user_request,
            session_dir=Path(session_dir),
            debug=debug,
            estimate_missing_equilibria=effective_estimation,
            l0_max_iterations=l0_max_iterations,
            l0_reasoning_timeout_s=l0_reasoning_timeout_s,
            round_number=round_number,
            prev_context=prev_context,
        )
    finally:
        if _prev_session is None:
            os.environ.pop("SRD46_ANALYSIS_SESSION_DIR", None)
        else:
            os.environ["SRD46_ANALYSIS_SESSION_DIR"] = _prev_session


__all__ = ["SRD46_analysis_run"]
