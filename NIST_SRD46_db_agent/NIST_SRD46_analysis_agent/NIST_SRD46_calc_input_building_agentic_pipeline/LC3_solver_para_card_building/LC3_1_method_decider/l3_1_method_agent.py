"""L3_1 — LLM output/calculation-type (sweep-method) picker.

Receives the L0 ``purpose / tasks`` plus the list of available
output/calculation options *automatically parsed from the solver*
(:mod:`sweep_pipelines.sweep_method_registry_api`).  An LLM picks ONE
solver role — speciation (1-D), predominance / Pourbaix (2-D, optionally
3-D), titration, or a generic freeform N-D sweep — and declares the
number of independent **degrees of freedom** (``dof``) for that role,
bounded by what the chosen solver actually supports.

This stage builds ONLY two fields:

* ``sweep_method`` — the registry id of the chosen solver,
* ``dof``          — the integer axis count, auto-bounded per method,

plus a free-text ``_notes`` capturing the rationale.  It deliberately
does NOT build ``sweep_axes`` (axis ranges / point counts),
``sweep_constraints`` or ``system_catalog`` — those are downstream
stages' responsibility.

Public API
----------
configure_l3_1_session(session_dir, history, stats, working_memory, debug)
run_l3_1(purpose, tasks, fixed_card_path, output_dir) -> dict
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .....general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
    AgentTurnResult,
)
from .....general_db_query_engine.general_subagent_skill_schema_and_parser import (
    parse_workflow,
)
from .....general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from ....analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from ....analysis_agent_argo_engine.argo_client import SRD46AnalysisClient
from ....SRD46_analysis_argo_config import AGENT_CONFIG as cfg
from ....analysis_agent_toolbox.calc_wrappers import _require_purpose_tasks

# ── path bootstrap so the numcalc solver registry imports cleanly ────
# NOTE: do NOT call ``.resolve()`` on Windows mapped drives that point at
# a UNC share -- it rewrites the path into the \\server\share form and
# Python's package finder then fails sub-package imports.  Use
# ``.absolute()`` and keep the mapped-drive root.
_HERE = Path(__file__).absolute()
_WORKFLOW_PATH = _HERE.parent / "L3_1_method_workflow.md"
_NUMCALC_ROOT = _HERE.parents[3] / "NIST_SRD46_core_numcalc_pipeline"
_SRD46_ROOT = _HERE.parents[5]          # SRD46_research_agent/ (holds NIST_SRD46_db_agent)
for _p in (_NUMCALC_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sweep_pipelines.sweep_method_registry_api import (  # noqa: E402
    list_sweep_methods,
    get_sweep_info,
)
from numcalc_input_cards_reader.calc_json_input_reader import (  # noqa: E402
    _RECOGNISED_AXES,
)

log = logging.getLogger("Analysis.L3_1")


# ════════════════════════════════════════════════════════════════════
#  Degrees-of-freedom bounds (auto-fetched from the solver)
# ════════════════════════════════════════════════════════════════════

def _allowed_dof(method: str) -> Optional[int]:
    """Return the maximum DOF the solver allows for ``method``.

    Derived from the solver's recognised-axis table.  ``freeform_sweep``
    accepts any axis count, so ``None`` (unbounded) is returned.
    """
    axes = _RECOGNISED_AXES.get(method)
    if not axes:                      # freeform_sweep (empty tuple) or unknown
        return None
    return len(axes)


def _minimum_dof(method: str) -> int:
    """Return the loader-required minimum axis count for a sweep method."""
    # The standard Pourbaix card requires both pH and E_V. Water activity is
    # the optional third recognised coordinate. Other registered methods have
    # one required coordinate; freeform also requires at least one.
    return 2 if method == "pourbaix_sweep" else 1


# ════════════════════════════════════════════════════════════════════
#  Session state
# ════════════════════════════════════════════════════════════════════

_SESSION: Dict[str, Any] = {
    "session_dir":    None,
    "history":        None,
    "stats":          None,
    "working_memory": None,
    "debug":          False,
    "call_index":     0,
}


def configure_l3_1_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or Path.cwd()
    _SESSION["call_index"] += 1
    out = Path(base) / f"L3_1_call_{_SESSION['call_index']:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ════════════════════════════════════════════════════════════════════
#  Tool surface
# ════════════════════════════════════════════════════════════════════

_FINAL_SLOT: Dict[str, Any] = {
    "method": None,
    "dof": None,
    "notes": "",
    "error": None,
    "latest_attempt": None,
    "restart_request": None,
}


def _finalize_method(sweep_method: str = "", dof: Any = None,
                     notes: str = "") -> str:
    """Record the chosen solver role + its degrees of freedom.

    ``sweep_method`` must be a registry id; ``dof`` is the integer axis
    count, validated against the solver's allowed maximum (unbounded for
    ``freeform_sweep``).
    """
    if _FINAL_SLOT.get("restart_request") is not None:
        return (
            "RESTART_LOCKED: an LC3 restart is already requested. Do not "
            "call `finalize_method` again; end this stage now."
        )
    _FINAL_SLOT["latest_attempt"] = {
        "tool": "finalize_method",
        "arguments": {
            "sweep_method": sweep_method,
            "dof": dof,
            "notes": notes,
        },
    }
    m = (sweep_method or "").strip()
    valid = list_sweep_methods()
    if m not in valid:
        _FINAL_SLOT["error"] = f"unknown_method:{m!r}"
        return (f"ERROR: sweep_method={m!r} not in {list(valid.keys())}. "
                f"Re-call `finalize_method`.")

    try:
        dof_int = int(dof)
    except (TypeError, ValueError):
        _FINAL_SLOT["error"] = f"bad_dof:{dof!r}"
        return (f"ERROR: dof={dof!r} is not an integer. "
                f"Re-call `finalize_method` with an integer dof >= 1.")

    min_dof = _minimum_dof(m)
    if dof_int < min_dof:
        _FINAL_SLOT["error"] = f"dof_too_low:{dof_int}<{min_dof}"
        return (f"ERROR: sweep_method={m!r} requires dof >= {min_dof}, "
                f"but dof={dof_int}. "
                f"Re-call `finalize_method`.")

    max_dof = _allowed_dof(m)
    if max_dof is not None and dof_int > max_dof:
        _FINAL_SLOT["error"] = f"dof_out_of_range:{dof_int}>{max_dof}"
        return (f"ERROR: sweep_method={m!r} supports at most {max_dof} "
                f"degree(s) of freedom, but dof={dof_int}. "
                f"Re-call `finalize_method` with dof <= {max_dof}.")
    if max_dof is None and dof_int > 4:
        log.warning("L3_1: freeform_sweep with unusually high dof=%d", dof_int)

    _FINAL_SLOT["method"] = m
    _FINAL_SLOT["dof"]    = dof_int
    _FINAL_SLOT["notes"]  = (notes or "").strip()
    _FINAL_SLOT["error"]  = None
    _FINAL_SLOT["restart_request"] = None
    return f"OK — sweep_method = {m}, dof = {dof_int}"


def _request_lc3_restart(reason: str = "") -> str:
    """Ask the LC3 orchestrator to begin a fresh L3_1..L3_4 attempt.

    The action is available only after ``finalize_method`` has returned a
    deterministic error.  The exact error is copied from stage state rather
    than accepted from the agent, so downstream recovery cannot rewrite its
    provenance.
    """
    if _FINAL_SLOT.get("restart_request") is not None:
        return (
            "ERROR: an LC3 restart is already requested; duplicate restart "
            "requests are forbidden. End this stage now."
        )
    error = _FINAL_SLOT.get("error")
    latest_attempt = _FINAL_SLOT.get("latest_attempt")
    why = (reason or "").strip()
    if not error:
        return (
            "ERROR: an LC3 restart can be requested only after "
            "`finalize_method` has returned an error in this run."
        )
    if latest_attempt is None:
        return (
            "ERROR: no directly emitted `finalize_method` attempt is "
            "available to attach to the restart request."
        )
    if not why:
        return "ERROR: `reason` must explain why local correction is insufficient."
    _FINAL_SLOT["restart_request"] = {
        "requested_by": "LC3_1",
        "error": str(error),
        "reason": why,
    }
    return (
        "OK_RESTART_REQUESTED: end this stage now. The orchestrator will "
        "start LC3 again with this error and the latest attempted method "
        "declaration as recovery context."
    )


# ════════════════════════════════════════════════════════════════════
#  Dispatcher
# ════════════════════════════════════════════════════════════════════

def _render_restart_context(restart_context: Any = None) -> str:
    if restart_context in (None, "", {}):
        return ""
    if isinstance(restart_context, (dict, list)):
        rendered = json.dumps(restart_context, indent=2, default=str)
    else:
        rendered = str(restart_context).strip()
    return (
        "\n\n[LC3 RESTART CONTEXT -- evidence from the latest failed LC3 "
        "attempt]\n"
        f"{rendered}\n"
        "Generate a fresh L3_1 decision. Treat the prior artifact and exact "
        "error as diagnostic evidence; retain unaffected user requirements."
    )


def _build_user_message(purpose: str, tasks: str,
                        options_summary: str,
                        restart_context: Any = None) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n"
        f"[Available output / calculation options (parsed from the solver)]\n"
        f"{options_summary}"
        f"{_render_restart_context(restart_context)}"
    )


def _build_options_summary() -> str:
    """Compose the solver-parsed option list + per-method DOF bounds."""
    lines = [get_sweep_info(), "", "Degrees-of-freedom bounds per method:"]
    for sid in list_sweep_methods():
        max_dof = _allowed_dof(sid)
        min_dof = _minimum_dof(sid)
        bound = (f"any (>={min_dof})" if max_dof is None
                 else (str(min_dof) if min_dof == max_dof
                       else f"{min_dof}..{max_dof}"))
        lines.append(f"  - {sid}: dof {bound}")
    return "\n".join(lines)


def run_l3_1(
    *,
    purpose: str,
    tasks: str,
    fixed_card_path: str | Path,
    output_dir: str | Path,
    restart_context: Any = None,
) -> Dict[str, Any]:
    """Run the L3_1 output/calculation-type picker.

    Inputs are the L0 ``purpose`` / ``tasks`` and the list of available
    solver options (auto-parsed from the sweep-method registry).  The
    ``fixed_card_path`` is accepted for call-signature compatibility and
    record-keeping; this stage does NOT parse the card.

    Returns
    -------
    dict
        ``status``, ``output_dir``, ``sweep_method``, ``dof``,
        ``calc_input_card_path`` (path to the seed ``calc_input_card.json``
        the downstream stages grow), ``elapsed_s``, ``report``.
    """
    purpose, tasks_text = _require_purpose_tasks(purpose, tasks)

    if _SESSION["session_dir"] is None:
        configure_l3_1_session(session_dir=Path.cwd() / "_l3_1_adhoc_session")

    call_dir = _per_call_dir()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fixed_card_path = Path(fixed_card_path)

    options_summary = _build_options_summary()

    history = _SESSION["history"]
    stats   = _SESSION["stats"]
    if history is not None:
        history.log("L3_1_dispatch_start",
                    call_index=_SESSION["call_index"],
                    fixed_card_path=str(fixed_card_path),
                    available_methods=list(list_sweep_methods().keys()))

    _FINAL_SLOT["method"] = None
    _FINAL_SLOT["dof"]    = None
    _FINAL_SLOT["notes"]  = ""
    _FINAL_SLOT["error"]  = None
    _FINAL_SLOT["latest_attempt"] = None
    _FINAL_SLOT["restart_request"] = None

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    tools: Dict[str, Callable] = {
        "finalize_method": _finalize_method,
        "request_lc3_restart": _request_lc3_restart,
    }
    system_prompt += "\n\n" + build_tool_instructions(tools)

    user_message = _build_user_message(
        purpose, tasks_text, options_summary, restart_context)
    client = SRD46AnalysisClient.for_l1()
    _engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "", guidance_hooks=[],
    )

    t0 = time.time()
    try:
        result: AgentTurnResult = agent_turn(
            user_message,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=cfg.MAX_TOOL_ITERATIONS,
            timeout=cfg.MAX_TURN_SECONDS,
            required_tools={"finalize_method"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        log.error("L3_1 agent_turn raised: %s", exc, exc_info=_SESSION["debug"])
        return {
            "status":                   "failed",
            "_error":                   f"agent_turn_exception: {exc!r}",
            "restart_request":          None,
            "latest_attempt_artifact_path": None,
            "output_dir":               str(call_dir),
            "sweep_method":             None,
            "dof":                      None,
            "calc_input_card_path":     None,
            "elapsed_s":                round(elapsed, 3),
            "report":                   f"agent_turn_exception: {exc!r}",
        }

    elapsed = time.time() - t0
    method = _FINAL_SLOT["method"]
    dof    = _FINAL_SLOT["dof"]
    notes  = _FINAL_SLOT["notes"]
    error  = _FINAL_SLOT["error"]
    latest_attempt = _FINAL_SLOT["latest_attempt"]
    restart_request = _FINAL_SLOT["restart_request"]

    latest_attempt_path: Optional[Path] = None
    if latest_attempt is not None:
        latest_attempt_path = call_dir / "latest_attempt.json"
        latest_attempt_path.write_text(
            json.dumps(latest_attempt, indent=2, default=str), encoding="utf-8")
    if restart_request is not None:
        restart_request = dict(restart_request)
        restart_request["latest_attempt_artifact_path"] = (
            str(latest_attempt_path) if latest_attempt_path else None)
        (call_dir / "restart_request.json").write_text(
            json.dumps(restart_request, indent=2), encoding="utf-8")

    # Seed of the single evolving calc-input card. Each later LC3 stage
    # reads this file, appends its own slice, and rewrites it -- the card
    # is built up gradually and never regenerated from scratch.
    card = {
        "sweep_method": method,
        "_meta": {"dof": dof, "stage": "LC3_1", "notes": notes},
    }
    card_path = call_dir / "calc_input_card.json"
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")

    (call_dir / "input.json").write_text(
        json.dumps({"purpose": purpose, "tasks": tasks_text,
                    "fixed_card_path": str(fixed_card_path),
                    "restart_context": restart_context}, indent=2,
                   default=str),
        encoding="utf-8",
    )

    rows = [
        "# L3_1 Tool Calls",
        "",
        "| # | iter | tool | args | result_chars | elapsed_s |",
        "|--:|----:|------|------|-------------:|----------:|",
    ]
    for i, c in enumerate(result.tool_history, start=1):
        rows.append(
            f"| {i} | {c.get('iteration','')} | {c.get('tool','?')} "
            f"| {json.dumps(c.get('arguments',{}))[:120]} "
            f"| {c.get('result_chars','')} | {c.get('elapsed_s','')} |"
        )
    (call_dir / "l3_1_tool_calls.md").write_text("\n".join(rows) + "\n",
                                                 encoding="utf-8")

    # Raw text the agent emitted (final answer + last context), for debugging.
    (call_dir / "agent_response.md").write_text(
        "# L3_1 agent response\n\n"
        "## Final answer (text emitted by the agent)\n\n"
        f"{result.answer or '_(empty)_'}\n\n"
        "## Final context\n\n"
        f"{result.final_context or '_(empty)_'}\n",
        encoding="utf-8",
    )

    report_lines = [
        f"# L3_1 dispatch report (call {_SESSION['call_index']:02d})",
        "",
        f"- output_dir: `{call_dir}`",
        f"- elapsed_s: {elapsed:.2f}",
        f"- sweep_method: **{method}**" if method else f"- sweep_method: FAILED ({error})",
        f"- dof: {dof}" if dof is not None else "- dof: —",
        "",
        "## Notes",
        "",
        notes or "_(none)_",
        "",
        f"- calc_input_card_path: `{card_path}`",
    ]
    if restart_request is not None and method is None:
        report_lines.extend([
            "",
            "## LC3 restart requested",
            f"- exact_error: `{restart_request['error']}`",
            f"- reason: {restart_request['reason']}",
            f"- latest_attempt: `{latest_attempt_path}`",
        ])
    report = "\n".join(report_lines)
    (call_dir / "report.md").write_text(report, encoding="utf-8")

    if stats is not None:
        stats.incr("L3_1", "dispatch_calls", 1)
        stats.incr("L3_1", "llm_iterations", result.iterations)
        stats.incr("L3_1", "tool_calls",     len(result.tool_history))
        stats.incr("L3_1", "ok" if method else "failed", 1)

    if _SESSION["working_memory"] is not None and method is not None:
        try:
            _SESSION["working_memory"].set("sweep_method", method)
            _SESSION["working_memory"].set("dof",          dof)
            _SESSION["working_memory"].set("calc_input_card_path",
                                            str(card_path))
        except Exception as exc:                    # pragma: no cover
            log.warning("working_memory.set failed: %s", exc)

    if history is not None:
        history.log("L3_1_dispatch_end",
                    call_index=_SESSION["call_index"],
                    elapsed_s=elapsed,
                    sweep_method=method,
                    dof=dof,
                    error=error or "")

    status = ("ok" if method else
              "restart_requested" if restart_request is not None else
              "failed")
    return {
        "status":                   status,
        "_error":                   None if method else (error or "no_payload"),
        "restart_request":          restart_request,
        "latest_attempt_artifact_path": (
            str(latest_attempt_path) if latest_attempt_path else None),
        "output_dir":               str(call_dir),
        "sweep_method":             method,
        "dof":                      dof,
        "calc_input_card_path":     str(card_path),
        "elapsed_s":                round(elapsed, 3),
        "report":                   report,
    }
