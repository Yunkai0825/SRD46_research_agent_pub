"""LC3 — Solver-parameter card-building orchestrator (purpose + tasks +
LC1 catalog + LC2 free-energy card → solver sweep/constraint card).

This is the single top-level entry point for the **LC3** stage of the
calc-input-building pipeline. Its inputs are the L0 ``purpose`` +
``tasks`` contract, the LC1 system-catalog (``lc1_sweep_input.json``),
and the validated LC2 free-energy card.

Pipeline chained here
---------------------
1. **LC3_1** — :func:`run_l3_1` (method decider)
   An LLM picks the solver role (``sweep_method``) and the number of
   sweep axes (``dof``), seeding the single evolving
   ``calc_input_card.json``.
2. **LC3_2** — :func:`run_l3_2` (initial-condition designer)
   An LLM lists what is already **known** or can be **assumed** about the
   starting state (temperature, ionic strength, fixed pH/redox, component
   totals) as a code-style ``inits`` card.  This baseline is handed to
   LC3_3 so the constraint designer inherits the pre-decided pins.
3. **LC3_3** — :func:`run_l3_3` (constraint designer)
   An LLM designs the ``sweep_constraints`` block (axes / lets / binds).
   The emitted card is expand-verified against the solver and folded into
   the evolving ``calc_input_card.json`` as ``constraint_spec``.
4. **LC3_4** — sweep designer
   Assigns numeric grid ranges / point counts and the explicit refinement
   decision, then validates the assembled card through the solver loader.

Each stage first uses its local ReAct loop to correct its own deterministic
validation errors.  A stage may instead request a bounded whole-LC3 restart
when the design premise must change.  An LC3_4 ``FATAL_UPSTREAM`` rejection
always takes that route because no grid-only edit can repair it.

Public API
----------
``configure_lc3_session(session_dir, history, stats, working_memory, debug)``
    Bind the per-session side-channel (called once by the parent / L0).
``run_lc3(purpose, tasks, *, fixed_card_path, system_catalog_path,
          output_dir=None, max_restarts=None, ...) -> dict``
    Run the full LC3 stage.
"""
from __future__ import annotations

import importlib
import hashlib
import json
import logging
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ── Paths (drive-letter form; never .resolve() — UNC long-paths break
#    Python's import machinery on this N: share). Mirror LC2's header so
#    the bare config module + sibling packages resolve identically. ────
_THIS = Path(__file__)
_LC3_ROOT      = _THIS.parents[0]   # LC3_solver_para_card_building/
_PIPELINE_ROOT = _THIS.parents[1]   # NIST_SRD46_calc_input_building_agentic_pipeline/
_ANALYSIS_ROOT = _THIS.parents[2]   # NIST_SRD46_analysis_agent/
_SRD46_ROOT    = _THIS.parents[4]   # SRD46_research_agent/
_NUMCALC_ROOT  = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"

for _p in (_PIPELINE_ROOT, _LC3_ROOT, _NUMCALC_ROOT, _ANALYSIS_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Shared analysis config as a bare top-level module (avoids the heavy
# NIST_SRD46_analysis_agent package __init__ chain).
try:
    from SRD46_analysis_argo_config import AGENT_CONFIG as cfg  # noqa: E402,F401
except Exception:                                # pragma: no cover
    try:
        from SRD46_calc_input_building_config import AGENT_CONFIG as cfg  # noqa: E402,F401
    except Exception:
        cfg = None

# Child stages (built) ---------------------------------------------------
from .LC3_1_method_decider.l3_1_method_agent import (
    configure_l3_1_session,
    run_l3_1,
)
from .LC3_2_initial_condition_designer.l3_2_initial_condition_agent import (
    configure_l3_2_session,
    run_l3_2,
)
from .LC3_3_constraint_designer.l3_3_constraint_agent import (
    configure_l3_3_session,
    run_l3_3,
)

log = logging.getLogger("LC3.orchestrator")


# ════════════════════════════════════════════════════════════════════
#  Optional child-stage discovery (LC3_3 / LC3_4)
# ════════════════════════════════════════════════════════════════════

# Each optional stage: (sub-package, module, run_fn, configure_fn|None).
_OPTIONAL_STAGES: Dict[str, Tuple[str, str, str, Optional[str]]] = {
    "LC3_4": ("LC3_4_sweep_designer", "l3_4_sweep_agent",
              "run_l3_4", "configure_l3_4_session"),
}


def _load_optional_stage(stage: str) -> Optional[Dict[str, Callable]]:
    """Return ``{run, configure}`` for an optional stage, or ``None``.

    The stage is considered available only when its module imports and
    exposes the expected ``run_*`` callable. Any import error (module
    not yet created, empty package) yields ``None`` so the orchestrator
    skips it gracefully.
    """
    subpkg, modname, run_attr, cfg_attr = _OPTIONAL_STAGES[stage]
    dotted = f"{__package__}.{subpkg}.{modname}"
    try:
        mod = importlib.import_module(dotted)
    except Exception as exc:                         # noqa: BLE001
        log.info("%s not available (skipped): %s", stage, exc)
        return None
    run_fn = getattr(mod, run_attr, None)
    if not callable(run_fn):
        log.info("%s module has no %s(): skipped", stage, run_attr)
        return None
    cfg_fn = getattr(mod, cfg_attr, None) if cfg_attr else None
    return {"run": run_fn, "configure": cfg_fn if callable(cfg_fn) else None}


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
    "_lock":          threading.Lock(),
}


def configure_lc3_session(
    *,
    session_dir: Union[str, Path],
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    """Bind the per-session side-channel (called once by the parent)."""
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or (Path.cwd() / "_lc3_adhoc")
    with _SESSION["_lock"]:
        _SESSION["call_index"] += 1
        idx = _SESSION["call_index"]
    out = Path(base) / f"LC3_call_{idx:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _clean_tasks(tasks: Any) -> str:
    """Return the free-text ``tasks`` brief verbatim (no splitting)."""
    if tasks is None:
        return ""
    return str(tasks).strip()


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def _run_lc3_attempt(
    purpose: str,
    tasks: str = "",
    *,
    fixed_card_path: Union[str, Path],
    system_catalog_path: Union[str, Path],
    output_dir: Union[str, Path, None] = None,
    debug: bool = False,
    restart_context: str = "",
    _record_run: bool = False,
) -> Dict[str, Any]:
    """Run one LC3_1 -> LC3_4 attempt.

    The public :func:`run_lc3` wrapper owns bounded whole-pipeline restarts.
    A restart context is advisory evidence from the immediately preceding
    failed attempt; rejected candidates are never used as the input card.

    Parameters
    ----------
    purpose, tasks
        L0 audit contract. ``tasks`` is a single free-text prose string
        (never a list); forwarded verbatim, without splitting.
    fixed_card_path
        The validated LC2 free-energy markdown card.
    system_catalog_path
        The LC1 system-catalog file (``lc1_sweep_input.json``); the bare
        ``system_catalog`` dict or a wrapper carrying it are both
        accepted by LC3_2.
    output_dir
        Base directory for the LC3 artefact tree. Falls back to the
        per-call directory under whatever ``configure_lc3_session``
        bound (or ``./_lc3_adhoc`` if neither is set).
    debug
        Verbose logging for the child agent loops.

    Returns
    -------
    dict
        ``{status, output_dir, purpose, tasks, sweep_method, dof,
        calc_input_card_path, sweep_constraints,
        final_card_path, lc3_1, lc3_2, lc3_3, lc3_4, stages_run,
        stages_skipped, elapsed_s}``.
    """
    t0 = time.perf_counter()
    purpose_clean = (purpose or "").strip()
    tasks_norm = _clean_tasks(tasks)

    fixed_card_path = Path(fixed_card_path)
    system_catalog_path = Path(system_catalog_path)
    if not fixed_card_path.is_file():
        raise FileNotFoundError(f"LC3: fixed_card_path not found: {fixed_card_path}")
    if not system_catalog_path.is_file():
        raise FileNotFoundError(
            f"LC3: system_catalog_path not found: {system_catalog_path}")

    if _SESSION["session_dir"] is None and output_dir is not None:
        configure_lc3_session(session_dir=output_dir, debug=debug)

    call_dir = Path(output_dir) if output_dir is not None else _per_call_dir()
    call_dir.mkdir(parents=True, exist_ok=True)
    debug = bool(debug or _SESSION["debug"])

    history        = _SESSION["history"]
    stats          = _SESSION["stats"]
    working_memory = _SESSION["working_memory"]

    if _record_run and history is not None:
        history.log("LC3_run_start", output_dir=str(call_dir),
                    fixed_card_path=str(fixed_card_path),
                    system_catalog_path=str(system_catalog_path))

    stages_run: List[str] = []
    stages_skipped: List[str] = []
    out: Dict[str, Any] = {
        "status":                  "failed",
        "output_dir":              str(call_dir),
        "purpose":                 purpose_clean,
        "tasks":                   tasks_norm,
        "sweep_method":            None,
        "dof":                     None,
        "calc_input_card_path":    None,
        "initial_condition_card_path": None,
        "initial_conditions":      None,
        "sweep_constraints":       None,
        "final_card_path":         None,
        "lc3_1":                   None,
        "lc3_2":                   None,
        "lc3_3":                   None,
        "lc3_4":                   None,
        "stages_run":              stages_run,
        "stages_skipped":          stages_skipped,
        "elapsed_s":               0.0,
        "failed_stage":            None,
    }

    current_card: Optional[Path] = None

    try:
        # ── 1. LC3_1 — method decider ───────────────────────────────
        lc3_1_dir = call_dir / "LC3_1"
        lc3_1_dir.mkdir(parents=True, exist_ok=True)
        configure_l3_1_session(
            session_dir=lc3_1_dir, history=history, stats=stats,
            working_memory=working_memory, debug=debug,
        )
        if history is not None:
            history.log("LC3_step_start", step="LC3_1")
        lc3_1 = run_l3_1(
            purpose=purpose_clean,
            tasks=tasks_norm,
            fixed_card_path=fixed_card_path,
            output_dir=lc3_1_dir,
            restart_context=restart_context,
        )
        out["lc3_1"] = lc3_1
        if lc3_1.get("status") != "ok":
            detail = lc3_1.get("_error")
            out["failed_stage"] = "LC3_1"
            out["_error"] = "LC3_1 (method decider) failed"
            if detail:
                out["_error"] += f": {detail}"
            if lc3_1.get("restart_request"):
                raise _LC3RestartRequested(out["_error"])
            raise _LC3StageError(out["_error"])
        stages_run.append("LC3_1")
        out["sweep_method"] = lc3_1.get("sweep_method")
        out["dof"]          = lc3_1.get("dof")
        current_card = Path(lc3_1["calc_input_card_path"])
        out["calc_input_card_path"] = str(current_card)

        # ── 2. LC3_2 — initial-condition designer ───────────────────
        lc3_2_dir = call_dir / "LC3_2"
        lc3_2_dir.mkdir(parents=True, exist_ok=True)
        configure_l3_2_session(
            session_dir=lc3_2_dir, history=history, stats=stats,
            working_memory=working_memory, debug=debug,
        )
        if history is not None:
            history.log("LC3_step_start", step="LC3_2")
        lc3_2 = run_l3_2(
            purpose=purpose_clean,
            tasks=tasks_norm,
            calc_input_card_path=current_card,
            system_catalog_path=system_catalog_path,
            fixed_card_path=fixed_card_path,
            output_dir=lc3_2_dir,
            restart_context=restart_context,
        )
        out["lc3_2"] = lc3_2
        if lc3_2.get("status") != "ok":
            detail = lc3_2.get("_error")
            out["failed_stage"] = "LC3_2"
            out["_error"] = "LC3_2 (initial-condition designer) failed"
            if detail:
                out["_error"] += f": {detail}"
            if lc3_2.get("restart_request"):
                raise _LC3RestartRequested(out["_error"])
            raise _LC3StageError(out["_error"])
        stages_run.append("LC3_2")
        initial_conditions_text = lc3_2.get("initial_conditions_text", "") or ""
        constraint_settings = lc3_2.get("constraint_settings")
        out["initial_conditions"] = lc3_2.get("inits")
        out["constraint_settings"] = constraint_settings
        out["initial_condition_card_path"] = lc3_2.get(
            "initial_condition_card_path")
        if lc3_2.get("calc_input_card_path"):
            current_card = Path(lc3_2["calc_input_card_path"])
            out["calc_input_card_path"] = str(current_card)

        # ── 3. LC3_3 — constraint designer ──────────────────────────
        lc3_3_dir = call_dir / "LC3_3"
        lc3_3_dir.mkdir(parents=True, exist_ok=True)
        configure_l3_3_session(
            session_dir=lc3_3_dir, history=history, stats=stats,
            working_memory=working_memory, debug=debug,
        )
        if history is not None:
            history.log("LC3_step_start", step="LC3_3")
        lc3_3 = run_l3_3(
            purpose=purpose_clean,
            tasks=tasks_norm,
            calc_input_card_path=current_card,
            system_catalog_path=system_catalog_path,
            fixed_card_path=fixed_card_path,
            output_dir=lc3_3_dir,
            initial_conditions_text=initial_conditions_text,
            constraint_settings=constraint_settings,
            restart_context=restart_context,
        )
        out["lc3_3"] = lc3_3
        if lc3_3.get("status") != "ok":
            detail = lc3_3.get("_error")
            out["failed_stage"] = "LC3_3"
            out["_error"] = "LC3_3 (constraint designer) failed"
            if detail:
                out["_error"] += f": {detail}"
            if lc3_3.get("restart_request"):
                raise _LC3RestartRequested(out["_error"])
            raise _LC3StageError(out["_error"])
        stages_run.append("LC3_3")
        out["sweep_constraints"] = lc3_3.get("sweep_constraints")
        if lc3_3.get("calc_input_card_path"):
            current_card = Path(lc3_3["calc_input_card_path"])
            out["calc_input_card_path"] = str(current_card)

        # ── 4. Optional LC3_4 (sweep designer; run when implemented) ─
        for stage, run_kwargs in (
            ("LC3_4", dict(
                purpose=purpose_clean, tasks=tasks_norm,
                calc_input_card_path=str(current_card) if current_card else None,
                fixed_card_path=fixed_card_path,
                system_catalog_path=system_catalog_path,
                restart_context=restart_context,
            )),
        ):
            loaded = _load_optional_stage(stage)
            if loaded is None:
                stages_skipped.append(stage)
                continue
            stage_dir = call_dir / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
            if loaded["configure"] is not None:
                loaded["configure"](
                    session_dir=stage_dir, history=history, stats=stats,
                    working_memory=working_memory, debug=debug,
                )
            if history is not None:
                history.log("LC3_step_start", step=stage)
            # Carry forward the latest card path under the conventional kw.
            if current_card is not None:
                run_kwargs["calc_input_card_path"] = str(current_card)
            stage_res = loaded["run"](output_dir=stage_dir, **run_kwargs)
            out[stage.lower()] = stage_res
            if isinstance(stage_res, dict) and stage_res.get("status") != "ok":
                out["failed_stage"] = stage
                out["_error"] = f"{stage} failed"
                if stage_res.get("_error"):
                    out["_error"] += f": {stage_res['_error']}"
                if stage_res.get("restart_request"):
                    raise _LC3RestartRequested(out["_error"])
                raise _LC3StageError(out["_error"])
            stages_run.append(stage)
            # Adopt whatever card the stage advanced, if it reports one.
            if isinstance(stage_res, dict):
                for key in ("calc_input_path", "calc_input_card_path",
                            "card_path", "output_card_path"):
                    val = stage_res.get(key)
                    if val and Path(val).is_file():
                        current_card = Path(val)
                        out["calc_input_card_path"] = str(current_card)
                        break

        out["status"] = "ok"

    except _LC3RestartRequested as exc:
        out["status"] = "restart_requested"
        log.info("LC3 attempt requested a full restart: %s", exc)
    except _LC3StageError as exc:
        out["status"] = "failed"
        log.error("LC3 failed: %s", exc)
    except Exception as exc:                         # noqa: BLE001
        out["status"] = "failed"
        out["_error"] = f"{type(exc).__name__}: {exc}"
        log.exception("LC3 stage raised")

    # ── Final card + summary ────────────────────────────────────────
    elapsed = round(time.perf_counter() - t0, 3)
    out["elapsed_s"] = elapsed
    if out["status"] == "ok" and current_card is not None:
        try:
            final_dst = call_dir / "calc_input_card.json"
            shutil.copyfile(current_card, final_dst)
            out["final_card_path"] = str(final_dst)
        except Exception:                            # pragma: no cover
            out["final_card_path"] = str(current_card)

    if _record_run and working_memory is not None and out.get("final_card_path"):
        try:
            working_memory.set("lc3_final_card_path", out["final_card_path"])
        except Exception as exc:                     # pragma: no cover
            log.warning("LC3 working_memory.set failed: %s", exc)

    if _record_run and stats is not None:
        stats.incr("LC3", "runs", 1)
        stats.incr("LC3", "ok" if out["status"] == "ok" else "failed", 1)

    if _record_run and history is not None:
        history.log("LC3_run_end", status=out["status"],
                    final_card_path=out.get("final_card_path"),
                    stages_run=stages_run, stages_skipped=stages_skipped,
                    elapsed_s=elapsed)

    _write_summary(call_dir, out)
    return out


_RESTARTABLE_STAGE_RESULTS: Tuple[Tuple[str, str], ...] = (
    ("LC3_1", "lc3_1"),
    ("LC3_2", "lc3_2"),
    ("LC3_3", "lc3_3"),
    ("LC3_4", "lc3_4"),
)


def _failed_pass_gallery_notes(attempt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect advisory gallery traces from a rejected LC3 pass.

    These records are restart evidence only. They are deliberately not
    appended to the fresh attempt's evolving card or installed as its current
    gallery state; every restarted stage makes its own new inspection and
    optional recommendation.
    """
    records: List[Dict[str, Any]] = []
    for stage_name, result_key in _RESTARTABLE_STAGE_RESULTS:
        result = attempt.get(result_key)
        if not isinstance(result, dict):
            continue
        note = result.get("freeform_gallery_note")
        if not isinstance(note, dict):
            continue
        records.append({
            "source_attempt": "failed",
            "source_stage": stage_name,
            "source_status": result.get("status"),
            "trust": "advisory_failed_pass",
            "note": note,
        })
    return records


def _restart_request_from_attempt(attempt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a normalized whole-LC3 restart request, if one exists.

    A stage-local agent may explicitly request a restart after receiving a
    deterministic ReAct validation error.  Independently, an L3_4 loader
    failure classified as ``upstream`` always requests a restart: changing
    the grid cannot repair an invalid inherited card.
    """
    for stage_name, result_key in _RESTARTABLE_STAGE_RESULTS:
        stage = attempt.get(result_key)
        if not isinstance(stage, dict):
            continue
        raw = stage.get("restart_request")
        requested = bool(
            isinstance(raw, dict) and raw.get("requested", True)
        )
        automatic_upstream = (
            stage_name == "LC3_4"
            and stage.get("status") != "ok"
            and stage.get("failure_scope") == "upstream"
        )
        if not requested and not automatic_upstream:
            continue
        if raw is None and not automatic_upstream:
            continue

        req = dict(raw) if isinstance(raw, dict) else {}
        error = (
            req.get("validation_error")
            or req.get("exact_tool_error")
            or req.get("error")
            or stage.get("_error")
            or attempt.get("_error")
            or "unknown_stage_validation_error"
        )
        candidate_path = (
            req.get("latest_candidate_path")
            or req.get("latest_artifact_path")
            or req.get("latest_attempt_artifact_path")
            or stage.get("latest_candidate_path")
            or stage.get("latest_artifact_path")
            or stage.get("latest_attempt_artifact_path")
        )
        last_valid = (
            req.get("last_valid_card_path")
            or stage.get("last_valid_card_path")
            or attempt.get("calc_input_card_path")
        )
        req.update({
            "requested": True,
            "restart_from": "LC3_1",
            "requested_by": req.get("requested_by") or stage_name,
            "trigger": req.get("trigger") or (
                "fatal_upstream" if automatic_upstream
                else "react_validation_error"
            ),
            "validation_error": str(error),
            "failure_scope": req.get("failure_scope")
            or stage.get("failure_scope") or "stage_local",
            "latest_candidate_path": (
                str(candidate_path) if candidate_path else None
            ),
            "last_valid_card_path": str(last_valid) if last_valid else None,
            "rationale": req.get("rationale") or req.get("reason"),
            "proposed_change": req.get("proposed_change"),
            "failed_pass_gallery_notes": _failed_pass_gallery_notes(attempt),
        })
        return req
    return None


def _bounded_text(path_value: Any, max_chars: int = 20_000) -> str:
    """Read a bounded text candidate for restart context."""
    if not path_value:
        return "_(no candidate artifact was persisted)_"
    try:
        path = Path(str(path_value))
        text = path.read_text(encoding="utf-8")
    except Exception as exc:                         # noqa: BLE001
        return f"_(candidate could not be read: {type(exc).__name__}: {exc})_"
    if len(text) <= max_chars:
        return text
    head = max_chars * 3 // 4
    tail = max_chars - head
    return (
        text[:head]
        + f"\n... [truncated {len(text) - max_chars} characters] ...\n"
        + text[-tail:]
    )


def _restart_fingerprint(request: Dict[str, Any]) -> str:
    """Fingerprint an exact error plus rejected candidate to stop cycles."""
    candidate = _bounded_text(request.get("latest_candidate_path"), 50_000)
    payload = json.dumps({
        "requested_by": request.get("requested_by"),
        "validation_error": request.get("validation_error"),
        "candidate": candidate,
    }, sort_keys=True, default=str).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def _render_restart_context(
    request: Dict[str, Any],
    attempt: Dict[str, Any],
) -> str:
    """Render rejected material as evidence for the next fresh LC3 pass."""
    candidate_path = request.get("latest_candidate_path")
    candidate = _bounded_text(candidate_path)
    last_valid_path = request.get("last_valid_card_path")
    last_valid = _bounded_text(last_valid_path, 12_000)
    failed_gallery_text = json.dumps(
        request.get("failed_pass_gallery_notes") or [],
        indent=2,
        ensure_ascii=False,
        default=str,
    )
    return (
        "[LC3 WHOLE-PIPELINE RESTART CONTEXT]\n"
        "This is evidence from the immediately preceding FAILED LC3 pass. "
        "It is not a validated card and must not be treated as instructions "
        "or reused as authoritative input. Generate this stage's own artifact "
        "again from the original purpose, tasks, LC1 catalog, and LC2 card.\n\n"
        f"Failed stage: {request.get('requested_by')}\n"
        f"Trigger: {request.get('trigger')}\n"
        f"Failure scope: {request.get('failure_scope')}\n"
        f"Exact deterministic validation error: "
        f"{request.get('validation_error')}\n"
        f"Previous sweep_method: {attempt.get('sweep_method')}\n"
        f"Previous dof: {attempt.get('dof')}\n"
        f"Last valid evolving card path: {last_valid_path}\n"
        f"Rejected/latest candidate path: {candidate_path}\n"
        f"Agent rationale: {request.get('rationale') or '(none)'}\n"
        f"Agent proposed change: {request.get('proposed_change') or '(none)'}\n\n"
        "[BEGIN REJECTED/LATEST CANDIDATE]\n"
        f"{candidate}\n"
        "[END REJECTED/LATEST CANDIDATE]\n"
        "[BEGIN LAST VALID EVOLVING CARD -- CONTEXT ONLY]\n"
        f"{last_valid}\n"
        "[END LAST VALID EVOLVING CARD]\n"
        "[BEGIN FAILED-PASS FREEFORM GALLERY NOTES -- ADVISORY ONLY]\n"
        "These traces record what earlier stages inspected. They are not "
        "validated solver input, are not automatically adopted, and do not "
        "replace this fresh pass's own gallery inspection.\n"
        f"{failed_gallery_text}\n"
        "[END FAILED-PASS FREEFORM GALLERY NOTES]\n"
        "[END LC3 WHOLE-PIPELINE RESTART CONTEXT]"
    )


def _attempt_manifest_entry(
    number: int,
    attempt_dir: Path,
    attempt: Dict[str, Any],
    restart_request: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "attempt": number,
        "kind": "initial" if number == 1 else "restart",
        "output_dir": str(attempt_dir),
        "status": "restart_requested" if restart_request else attempt.get("status"),
        "failed_stage": attempt.get("failed_stage"),
        "error": attempt.get("_error"),
        "sweep_method": attempt.get("sweep_method"),
        "dof": attempt.get("dof"),
        "calc_input_card_path": attempt.get("calc_input_card_path"),
        "last_valid_card_path": attempt.get("calc_input_card_path"),
        "stages_run": attempt.get("stages_run", []),
        "stages_skipped": attempt.get("stages_skipped", []),
        "elapsed_s": attempt.get("elapsed_s"),
        "restart_request": restart_request,
    }


def run_lc3(
    purpose: str,
    tasks: str = "",
    *,
    fixed_card_path: Union[str, Path],
    system_catalog_path: Union[str, Path],
    output_dir: Union[str, Path, None] = None,
    debug: bool = False,
    max_restarts: Optional[int] = None,
) -> Dict[str, Any]:
    """Run LC3 with bounded, whole-pipeline recovery.

    A qualifying restart always begins again at L3_1 and reuses the original
    LC1/LC2 inputs.  Rejected candidates are supplied only as labelled model
    context.  They are never promoted to the next attempt's evolving card.
    """
    t0 = time.perf_counter()
    if max_restarts is None:
        max_restarts = getattr(cfg, "LC3_MAX_RESTARTS", 2)
    if isinstance(max_restarts, bool) or not isinstance(max_restarts, int):
        raise ValueError("LC3 max_restarts must be a non-negative integer")
    restart_limit = max_restarts
    if restart_limit < 0:
        raise ValueError("LC3 max_restarts must be a non-negative integer")

    if _SESSION["session_dir"] is None and output_dir is not None:
        configure_lc3_session(session_dir=output_dir, debug=debug)
    call_dir = Path(output_dir) if output_dir is not None else _per_call_dir()
    call_dir.mkdir(parents=True, exist_ok=True)
    debug = bool(debug or _SESSION["debug"])

    history = _SESSION["history"]
    stats = _SESSION["stats"]
    working_memory = _SESSION["working_memory"]
    if history is not None:
        history.log(
            "LC3_run_start", output_dir=str(call_dir),
            fixed_card_path=str(fixed_card_path),
            system_catalog_path=str(system_catalog_path),
            restart_limit=restart_limit,
        )

    attempts: List[Dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    restart_count = 0
    restart_context = ""
    restart_exhausted = False
    restart_blocked_reason: Optional[str] = None
    final_attempt: Dict[str, Any]

    while True:
        attempt_number = restart_count + 1
        attempt_dir = (
            call_dir if attempt_number == 1
            else call_dir / "restarts" / f"LC3_restart_{restart_count:02d}"
        )
        attempt_dir.mkdir(parents=True, exist_ok=True)
        if restart_context:
            (attempt_dir / "restart_context.md").write_text(
                restart_context, encoding="utf-8")

        attempt = _run_lc3_attempt(
            purpose,
            tasks,
            fixed_card_path=fixed_card_path,
            system_catalog_path=system_catalog_path,
            output_dir=attempt_dir,
            debug=debug,
            restart_context=restart_context,
            _record_run=False,
        )
        request = _restart_request_from_attempt(attempt)
        attempts.append(_attempt_manifest_entry(
            attempt_number, attempt_dir, attempt, request))

        if request is None:
            final_attempt = attempt
            break

        fingerprint = request.get("fingerprint") or _restart_fingerprint(request)
        request["fingerprint"] = fingerprint
        attempts[-1]["restart_request"] = request
        if fingerprint in seen_fingerprints:
            final_attempt = attempt
            restart_blocked_reason = "duplicate_restart_request"
            final_attempt["_error"] = (
                f"{final_attempt.get('_error')}; whole-LC3 restart blocked: "
                "the same validation error and rejected candidate already "
                "triggered a restart"
            )
            break
        if restart_count >= restart_limit:
            final_attempt = attempt
            restart_exhausted = True
            restart_blocked_reason = "restart_limit_reached"
            final_attempt["_error"] = (
                f"{final_attempt.get('_error')}; whole-LC3 restart limit "
                f"reached ({restart_limit})"
            )
            break

        seen_fingerprints.add(fingerprint)
        restart_context = _render_restart_context(request, attempt)
        restart_count += 1
        if history is not None:
            history.log(
                "LC3_restart", restart_number=restart_count,
                requested_by=request.get("requested_by"),
                trigger=request.get("trigger"),
                validation_error=request.get("validation_error"),
            )

    out = dict(final_attempt)
    if restart_blocked_reason and out.get("status") == "restart_requested":
        out["status"] = "failed"
    out["output_dir"] = str(call_dir)
    out["attempts"] = attempts
    out["restart_count"] = restart_count
    out["restart_limit"] = restart_limit
    out["restart_exhausted"] = restart_exhausted
    out["restart_blocked_reason"] = restart_blocked_reason
    out["terminal_attempt"] = len(attempts)
    out["successful_attempt_output_dir"] = (
        final_attempt.get("output_dir") if final_attempt.get("status") == "ok"
        else None
    )

    # Promote only a successfully validated final card to the public root.
    if out.get("status") == "ok" and final_attempt.get("final_card_path"):
        source = Path(str(final_attempt["final_card_path"]))
        destination = call_dir / "calc_input_card.json"
        if source != destination:
            shutil.copyfile(source, destination)
        out["final_card_path"] = str(destination)
        out["calc_input_card_path"] = str(destination)

    out["elapsed_s"] = round(time.perf_counter() - t0, 3)
    manifest_dir = call_dir / "summary"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "LC3_restart_manifest.json"
    out["restart_manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps({
        "terminal_status": out.get("status"),
        "terminal_error": out.get("_error"),
        "terminal_attempt": out.get("terminal_attempt"),
        "final_card_path": out.get("final_card_path"),
        "restart_limit": restart_limit,
        "restart_count": restart_count,
        "restart_exhausted": restart_exhausted,
        "restart_blocked_reason": restart_blocked_reason,
        "attempts": attempts,
    }, indent=2, default=str), encoding="utf-8")

    if working_memory is not None and out.get("final_card_path"):
        try:
            working_memory.set("lc3_final_card_path", out["final_card_path"])
        except Exception as exc:                     # pragma: no cover
            log.warning("LC3 working_memory.set failed: %s", exc)
    if stats is not None:
        stats.incr("LC3", "runs", 1)
        stats.incr("LC3", "ok" if out.get("status") == "ok" else "failed", 1)
        if restart_count:
            stats.incr("LC3", "restarts", restart_count)
    if history is not None:
        history.log(
            "LC3_run_end", status=out.get("status"),
            final_card_path=out.get("final_card_path"),
            restart_count=restart_count,
            restart_exhausted=restart_exhausted,
            elapsed_s=out["elapsed_s"],
        )

    _write_summary(call_dir, out)
    return out


class _LC3StageError(RuntimeError):
    """Internal signal that a chained LC3 stage failed."""


class _LC3RestartRequested(_LC3StageError):
    """Internal signal that a stage requested a fresh LC3_1..LC3_4 pass."""


def _write_summary(call_dir: Path, out: Dict[str, Any]) -> None:
    """Persist a compact LC3 stage summary under ``summary/``."""
    try:
        summary_dir = call_dir / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)

        def _headline(stage: Optional[Dict[str, Any]], keys: tuple) -> Any:
            if not isinstance(stage, dict):
                return None
            return {k: stage.get(k) for k in keys}

        summary = {
            k: v for k, v in out.items()
            if k not in ("lc3_1", "lc3_2", "lc3_3", "lc3_4")
        }
        summary["lc3_1"] = _headline(
            out.get("lc3_1"),
            ("status", "sweep_method", "dof", "calc_input_card_path"),
        )
        summary["lc3_2"] = _headline(
            out.get("lc3_2"),
            ("status", "calc_input_card_path", "n_known", "n_assumed"),
        )
        summary["lc3_3"] = _headline(
            out.get("lc3_3"),
            ("status", "calc_input_card_path", "expand_ok", "n_bindings"),
        )
        summary["lc3_4"] = _headline(
            out.get("lc3_4"),
            ("status", "calc_input_path", "sweep_axes", "grid_refine",
             "n_cells"),
        )
        (summary_dir / "LC3_summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8",
        )
    except Exception:                                # pragma: no cover
        pass


__all__ = [
    "run_lc3",
    "configure_lc3_session",
]
