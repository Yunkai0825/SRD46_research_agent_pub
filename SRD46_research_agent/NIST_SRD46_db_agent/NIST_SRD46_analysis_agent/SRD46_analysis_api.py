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
from .analysis_reconstruction import analysis_execution

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
    reconstruction_mode: str = "regular",
    reconstruction_source: str | Path | None = None,
    reconstruction_smoke: bool = False,
    reconstruction_boundary: dict | None = None,
    live_api_user: str | None = None,
    live_provider: dict | None = None,
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
    reconstruction_mode : str
        ``regular`` records a fresh run and rejects existing Analysis state. ``reconstruction`` replays a recorded
        run into a fresh folder and resumes live at its authorization denial
        or an explicitly selected request boundary. ``resume`` uses the same strict first-principle engine at a verified
        prepared-solver boundary in its existing folder. Context, cards and
        files must match that boundary; only its numerical checkpoints may advance.
        Missing or mismatched replay evidence stops execution without fallback.
    reconstruction_source : str | Path | None
        Original run folder (or its dedicated reconstruction ledger).
    reconstruction_smoke : bool
        In reconstruction mode, stop at the selected request without live I/O.
    reconstruction_boundary : dict | None
        Explicit manual-stop boundary, e.g. ``{"kind": "interrupted_http",
        "event_id": 1598}``. Only supported in ``reconstruction`` mode with
        a fresh output directory. The selected request must have no saved
        response or committed outcome. Replay all committed context, then
        issue that exact request again; never invent a partial response.
        To rewind before a completed request, explicitly use
        ``{"kind": "restart_before_http", "event_id": ..., "request_sha256": ...}``.
        This verifies the intact ledger and reconstructs only its prior context;
        the selected old response and later work are excluded from the branch.
        The exact request must match before any live call. The original source
        is preserved; this never synthesizes context from final reports.
        Omit this argument to retain the authorization-denial policy.
    live_api_user : str | None
        Optional Argo account for new live requests only. Recorded requests
        retain their original account for exact replay. The native ledger
        records both the logical request and actual sent request when they
        differ; prompts and model settings are unchanged.
    live_provider : dict | None
        Explicit physical provider for new live requests only. Anthropic uses
        an explicit model map and credential environment-variable name. Saved
        requests still replay and compare in their original logical format.
    """
    effective_estimation = resolve_estimate_missing_equilibria(
        estimate_missing_equilibria
    )
    # Announce the session root for passive capture routing (the Anthropic
    # adapter's resolver reads it; env var survives module aliasing/threads).
    _prev_session = os.environ.get("SRD46_ANALYSIS_SESSION_DIR")
    os.environ["SRD46_ANALYSIS_SESSION_DIR"] = str(Path(session_dir).absolute())
    try:
        settings = dict(user_request=user_request, debug=debug,
                        estimate_missing_equilibria=effective_estimation,
                        l0_max_iterations=l0_max_iterations,
                        l0_reasoning_timeout_s=l0_reasoning_timeout_s,
                        round_number=round_number, prev_context=prev_context)
        with analysis_execution(mode=reconstruction_mode, session_dir=session_dir,
                                source=reconstruction_source,
                                stop_at_breakpoint=reconstruction_smoke,
                                boundary=reconstruction_boundary,
                                settings=settings, live_api_user=live_api_user,
                                live_provider=live_provider):
            native_settings = {key: value for key, value in settings.items()
                               if key != 'user_request'}
            return _l0_run(user_request, session_dir=Path(session_dir), **native_settings)
    finally:
        if _prev_session is None:
            os.environ.pop("SRD46_ANALYSIS_SESSION_DIR", None)
        else:
            os.environ["SRD46_ANALYSIS_SESSION_DIR"] = _prev_session


__all__ = ["SRD46_analysis_run"]
