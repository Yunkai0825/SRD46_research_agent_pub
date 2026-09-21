"""SRD46 calc-input-building pipeline — public end-to-end API.

This module is the single front door to the *calc-input-building* agentic
pipeline.  It exposes two complementary halves:

**Building half** — turn a natural-language ``purpose`` + ``tasks`` brief
into a solver-ready calc-input card by chaining the three agent layers::

    run_lc1   (eq-card alignment ........ system catalog + eq-map card)
        │
        ▼
    run_lc2   (free-energy card building . validated ΔG markdown card)
        │
        ▼
    run_lc3   (solver-para card building . calc_input_card.json)

``build_calc_input_card`` drives that chain and returns the path of the
final ``calc_input_card.json`` (plus every intermediate artefact).

**Calculation half** — the readers / runner the numeric solver consumes,
re-exported verbatim from
``NIST_SRD46_core_numcalc_pipeline`` so callers only ever import from one
place:

    load_calc_input, dump_calc_input, resolve_card_source,
    run_calculation, SUPPORTED_SWEEP_METHODS, CalcInput

``run_pipeline`` stitches both halves together: brief → cards → (optional)
numeric sweep.

Public API
----------
build_calc_input_card(purpose, tasks, *, output_dir, ...) -> dict
run_pipeline(purpose, tasks, *, output_dir, run_solver=False, ...) -> dict
load_calc_input, dump_calc_input, resolve_card_source
run_calculation, SUPPORTED_SWEEP_METHODS, CalcInput
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from NIST_SRD46_db_agent.general_db_query_engine.general_checkpointing import (
    CheckpointError,
    DurableCheckpointStore,
    artifact_receipts,
    file_sha256,
    identity_sha256,
    validate_artifact_receipts,
)

# ── path bootstrap ───────────────────────────────────────────────────
# NOTE: use ``.absolute()`` — never ``.resolve()`` — on the Windows
# mapped drive that points at a UNC share; ``.resolve()`` rewrites the
# path into the ``\\server\share`` form and Python's package finder then
# fails the namespace sub-package imports.
_HERE = Path(__file__).absolute()
_PIPELINE_ROOT = _HERE.parent                       # calc_input_building pipeline
_ANALYSIS_ROOT = _PIPELINE_ROOT.parent              # NIST_SRD46_analysis_agent
_NUMCALC_ROOT = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"
_SRD46_ROOT = _HERE.parents[3]                      # SRD46_research_agent/ (holds NIST_SRD46_db_agent)
for _p in (_NUMCALC_ROOT, _SRD46_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ── calculation half — re-exported from the numcalc pipeline ─────────
from numcalc_input_cards_reader import (            # noqa: E402
    CalcInput,
    SUPPORTED_SWEEP_METHODS,
    load_calc_input,
    dump_calc_input,
    resolve_card_source,
)
from SRD46_numcalculator_api import run_calculation  # noqa: E402

# ── building half — the three agent-layer orchestrators ──────────────
from .LC1_SRD46_eq_card_alignment.LC1_eq_card_alignment_orchestrator import (  # noqa: E402
    run_lc1,
    configure_lc1_session,
)
from .LC2_free_energy_card_building.LC2_free_energy_card_orchestrator import (  # noqa: E402
    run_lc2,
    configure_lc2_session,
)
from .LC3_solver_para_card_building.LC3_solver_para_card_orchestrator import (  # noqa: E402
    run_lc3,
    configure_lc3_session,
)
from .SRD46_calc_input_building_config import (  # noqa: E402
    resolve_estimate_missing_equilibria,
)

__all__ = [
    # building half
    "build_calc_input_card",
    "run_pipeline",
    "run_lc1",
    "run_lc2",
    "run_lc3",
    # calculation half (re-exported)
    "load_calc_input",
    "dump_calc_input",
    "resolve_card_source",
    "run_calculation",
    "SUPPORTED_SWEEP_METHODS",
    "CalcInput",
]


def _is_exact_sha256(value: Any) -> bool:
    """Return whether *value* is an exact lowercase SHA-256 receipt."""

    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _stage_input_sha256(
    stage: str,
    *,
    purpose: str,
    tasks: str,
    settings: Dict[str, Any],
    upstream_paths: List[str | Path] | None = None,
) -> str:
    """Bind a stage checkpoint to its exact brief, settings and inputs."""

    upstream = []
    for value in upstream_paths or []:
        path = Path(value)
        upstream.append({
            "path": str(path.absolute()),
            "sha256": file_sha256(path) if path.is_file() else None,
        })
    return identity_sha256({
        "stage": stage,
        "purpose": (purpose or "").strip(),
        "tasks": (tasks or "").strip(),
        "settings": settings,
        "upstream": upstream,
    })


def _stage_checkpoint_result(
    store: DurableCheckpointStore | None,
    stage: str,
    *,
    input_sha256: str,
) -> Optional[Dict[str, Any]]:
    """Return a fully validated completed result or fail closed."""

    if store is None:
        return None
    payload = store.get_pickle("build-stage", stage, None)
    if not isinstance(payload, dict):
        return None
    if payload.get("status") != "complete":
        return None
    if payload.get("input_sha256") != input_sha256:
        store.event(
            "stage_checkpoint_rejected",
            stage=stage,
            reason="input_sha256_mismatch",
        )
        return None
    if not validate_artifact_receipts(payload.get("artifacts") or []):
        store.event(
            "stage_checkpoint_rejected",
            stage=stage,
            reason="artifact_receipt_mismatch",
        )
        return None
    result = payload.get("result")
    if not isinstance(result, dict) or result.get("status") != "ok":
        return None
    store.event("stage_checkpoint_reused", stage=stage)
    return result


def _commit_stage_checkpoint(
    store: DurableCheckpointStore | None,
    stage: str,
    *,
    input_sha256: str,
    result: Dict[str, Any],
    artifact_paths: List[str | Path],
) -> None:
    if store is None or result.get("status") != "ok":
        return
    receipts = artifact_receipts(artifact_paths)
    if not receipts:
        raise CheckpointError(
            f"refusing to commit {stage}: no durable artifacts were found"
        )
    store.put_pickle("build-stage", stage, {
        "status": "complete",
        "input_sha256": input_sha256,
        "result": result,
        "artifacts": receipts,
        "committed_at": time.time(),
    })
    store.event(
        "stage_checkpoint_committed",
        stage=stage,
        artifact_count=len(receipts),
    )


def _mark_stage_running(
    store: DurableCheckpointStore | None,
    stage: str,
    *,
    input_sha256: str,
) -> None:
    if store is None:
        return
    store.put_json("build-stage-status", stage, {
        "status": "running",
        "input_sha256": input_sha256,
        "started_at": time.time(),
        "pid": os.getpid(),
    })
    store.event("stage_started", stage=stage)


# ════════════════════════════════════════════════════════════════════
#  Building half — purpose/tasks → solver-ready calc-input card
# ════════════════════════════════════════════════════════════════════

def build_calc_input_card(
    purpose: str,
    tasks: str = "",
    *,
    output_dir: Union[str, Path],
    request_T_C: float = 25.0,
    request_I_M: float = 0.1,
    water_system: bool = True,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    resume: bool = True,
) -> Dict[str, Any]:
    """Drive LC1 → LC2 → LC3 and emit a solver-ready calc-input card.

    Parameters
    ----------
    purpose, tasks
        The L0 audit contract.  ``tasks`` is a single free-text prose
        string (never a list); it is forwarded to every layer verbatim,
        without splitting, normalisation, or templating.
    output_dir
        Base directory for the run.  Each layer writes under a dedicated
        sub-tree: ``<output_dir>/LC1``, ``.../LC2``, ``.../LC3``.
    request_T_C, request_I_M
        Default temperature (°C) and ionic strength (M) handed to LC1 so
        the system-catalog skeleton carries sensible environment values.
        The modelling regime (activity model, solids, redox/ionic-strength
        mode) is decided by the LC3_2 initial-condition designer and
        inherited by LC3_3 — it is **not** set here.
    water_system
        When ``True`` (default), the aqueous self-system proton H⁺
        (``metal_68``) and hydroxide OH⁻ (``ligand_10076``) are injected
        into the LC1_1 system catalog as first-class entries so the rest
        of the pipeline treats them as ordinary system species (and, in
        particular, ligand-protonation equilibria flow through the
        validated LC1_2 eq-map). Set ``False`` for a non-aqueous system.
    debug
        Verbose child-agent logging.
    estimate_missing_equilibria
        Optional per-run override for query-assisted missing-equilibrium
        support. ``None`` inherits the shared default-false setting.
    resume
        Reuse identity-bound, checksummed LC stage checkpoints under
        ``<output_dir>/_checkpoints``. A completed stage is reused only when
        its exact inputs and all required output artifacts still match.

    Returns
    -------
    dict
        ``{status, output_dir, purpose, tasks, calc_input_card_path,
        system_catalog_path, eq_map_card_path, free_energy_card_path,
        lc1, lc2, lc3, elapsed_s}``.  ``status`` is ``"ok"`` only when
        every layer succeeded and the final card exists.
    """
    effective_estimation = resolve_estimate_missing_equilibria(
        estimate_missing_equilibria
    )
    forward_explicit_estimation_disable = (
        estimate_missing_equilibria is False
        and resolve_estimate_missing_equilibria() is True
    )

    t0 = time.perf_counter()
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)

    checkpoint_store: DurableCheckpointStore | None = None
    checkpoint_error: Optional[str] = None
    if resume:
        try:
            checkpoint_store = DurableCheckpointStore(
                base / "_checkpoints" / "build_pipeline.sqlite3",
                identity={
                    "contract": "calc-input-build/v1",
                    "purpose": (purpose or "").strip(),
                    "tasks": (tasks or "").strip(),
                    "request_T_C": float(request_T_C),
                    "request_I_M": float(request_I_M),
                    "water_system": bool(water_system),
                    "estimate_missing_equilibria": bool(
                        effective_estimation
                    ),
                },
            )
        except CheckpointError as exc:
            # Never reuse a checkpoint whose identity cannot be proven.  The
            # calculation may still proceed from scratch, with the reason
            # visible in its returned audit metadata.
            checkpoint_error = f"{type(exc).__name__}: {exc}"

    out: Dict[str, Any] = {
        "status": "failed",
        "output_dir": str(base),
        "purpose": (purpose or "").strip(),
        "tasks": (tasks or "").strip(),
        "calc_input_card_path": None,
        "system_catalog_path": None,
        "eq_map_card_path": None,
        "free_energy_card_path": None,
        "lc1": None,
        "lc2": None,
        "lc3": None,
        "elapsed_s": 0.0,
        "checkpoint": {
            "enabled": checkpoint_store is not None,
            "path": (
                str(checkpoint_store.path)
                if checkpoint_store is not None else None
            ),
            "resume_requested": bool(resume),
            "reused_stages": [],
            "error": checkpoint_error,
        },
    }

    try:
        # ── LC1 — eq-card alignment → system catalog + eq-map card ───
        lc1_dir = base / "LC1"
        lc1_input_sha256 = _stage_input_sha256(
            "LC1",
            purpose=purpose,
            tasks=tasks,
            settings={
                "request_T_C": float(request_T_C),
                "request_I_M": float(request_I_M),
                "water_system": bool(water_system),
                "estimate_missing_equilibria": bool(
                    effective_estimation
                ),
            },
        )
        lc1 = _stage_checkpoint_result(
            checkpoint_store,
            "LC1",
            input_sha256=lc1_input_sha256,
        )
        if lc1 is not None:
            out["checkpoint"]["reused_stages"].append("LC1")
        else:
            _mark_stage_running(
                checkpoint_store,
                "LC1",
                input_sha256=lc1_input_sha256,
            )
            if effective_estimation:
                lc1 = run_lc1(
                    purpose, tasks,
                    output_dir=lc1_dir,
                    request_T_C=request_T_C,
                    request_I_M=request_I_M,
                    water_system=water_system,
                    debug=debug,
                    estimate_missing_equilibria=True,
                )
            elif forward_explicit_estimation_disable:
                lc1 = run_lc1(
                    purpose, tasks,
                    output_dir=lc1_dir,
                    request_T_C=request_T_C,
                    request_I_M=request_I_M,
                    water_system=water_system,
                    debug=debug,
                    estimate_missing_equilibria=False,
                )
            else:
                lc1 = run_lc1(
                    purpose, tasks,
                    output_dir=lc1_dir,
                    request_T_C=request_T_C,
                    request_I_M=request_I_M,
                    water_system=water_system,
                    debug=debug,
                )
        out["lc1"] = lc1
        if lc1.get("status") != "ok":
            detail = str(lc1.get("_error") or "").strip()
            out["_error"] = f"LC1 failed: {detail}" if detail else "LC1 failed"
            return _finalize(out, t0)

        # LC1 persists the system-catalog skeleton and a copy of the
        # eq-map card at the call-dir root.
        system_catalog_path = lc1_dir / "lc1_sweep_input.json"
        eq_map_card_path = lc1_dir / "lc1_2_eqmap_card.json"
        if not eq_map_card_path.is_file():
            # Fall back to the raw path LC1 reported.
            raw = lc1.get("eq_map_card_path")
            eq_map_card_path = Path(raw) if raw else eq_map_card_path
        out["system_catalog_path"] = str(system_catalog_path)
        out["eq_map_card_path"] = str(eq_map_card_path)
        if not system_catalog_path.is_file():
            out["_error"] = f"LC1 system catalog not found: {system_catalog_path}"
            return _finalize(out, t0)
        if "LC1" not in out["checkpoint"]["reused_stages"]:
            lc1_artifacts: List[str | Path] = [
                system_catalog_path,
                eq_map_card_path,
            ]
            for key in (
                "support_eq_map_path",
                "session_working_map_path",
                "manifest_path",
            ):
                value = lc1.get(key)
                if value:
                    lc1_artifacts.append(value)
            _commit_stage_checkpoint(
                checkpoint_store,
                "LC1",
                input_sha256=lc1_input_sha256,
                result=lc1,
                artifact_paths=lc1_artifacts,
            )

        # ── LC2 — free-energy card building → validated ΔG card ─────
        lc2_dir = base / "LC2"
        support_eq_map_path = lc1.get("support_eq_map_path")
        lc2_upstream_paths: List[str | Path] = [
            system_catalog_path,
            eq_map_card_path,
        ]
        if support_eq_map_path:
            lc2_upstream_paths.append(support_eq_map_path)
        if lc1.get("session_working_map_path"):
            lc2_upstream_paths.append(lc1["session_working_map_path"])
        lc2_input_sha256 = _stage_input_sha256(
            "LC2",
            purpose=purpose,
            tasks=tasks,
            settings={"support_enabled": support_eq_map_path is not None},
            upstream_paths=lc2_upstream_paths,
        )
        lc2 = _stage_checkpoint_result(
            checkpoint_store,
            "LC2",
            input_sha256=lc2_input_sha256,
        )
        if lc2 is not None:
            out["checkpoint"]["reused_stages"].append("LC2")
        else:
            _mark_stage_running(
                checkpoint_store,
                "LC2",
                input_sha256=lc2_input_sha256,
            )

        if lc2 is None and support_eq_map_path is not None:
            expected_support_session_id = lc1.get("support_session_id")
            expected_support_eq_map_sha256 = lc1.get("support_eq_map_sha256")
            session_working_map_path = lc1.get("session_working_map_path")
            expected_session_working_map_sha256 = lc1.get(
                "session_working_map_sha256"
            )
            if (
                not str(support_eq_map_path).strip()
                or not isinstance(expected_support_session_id, str)
                or not expected_support_session_id.strip()
                or not _is_exact_sha256(expected_support_eq_map_sha256)
            ):
                out["_error"] = (
                    "LC1 support eq_map handoff is missing its path, expected "
                    "session ID, or exact SHA-256 binding"
                )
                return _finalize(out, t0)
            if (
                session_working_map_path is None
                or not str(session_working_map_path).strip()
                or not _is_exact_sha256(
                    expected_session_working_map_sha256
                )
            ):
                out["_error"] = (
                    "LC1 support eq_map is missing its session working map "
                    "path or exact SHA-256 binding"
                )
                return _finalize(out, t0)
            lc2 = run_lc2(
                purpose, tasks,
                system_catalog_path=str(system_catalog_path),
                lc1_2_eqmap_card_path=str(eq_map_card_path),
                output_dir=lc2_dir,
                debug=debug,
                support_eq_map_path=support_eq_map_path,
                expected_support_session_id=expected_support_session_id,
                expected_support_eq_map_sha256=expected_support_eq_map_sha256,
                session_working_map_path=session_working_map_path,
                expected_session_working_map_sha256=(
                    expected_session_working_map_sha256
                ),
            )
        elif lc2 is None:
            lc2 = run_lc2(
                purpose, tasks,
                system_catalog_path=str(system_catalog_path),
                lc1_2_eqmap_card_path=str(eq_map_card_path),
                output_dir=lc2_dir,
                debug=debug,
            )
        out["lc2"] = lc2
        if lc2.get("status") != "ok":
            out["_error"] = str(lc2.get("_error") or "LC2 failed")
            return _finalize(out, t0)
        free_energy_card_path = lc2.get("final_card_path")
        out["free_energy_card_path"] = free_energy_card_path
        if not free_energy_card_path or not Path(free_energy_card_path).is_file():
            out["_error"] = f"LC2 free-energy card not found: {free_energy_card_path}"
            return _finalize(out, t0)
        if "LC2" not in out["checkpoint"]["reused_stages"]:
            _commit_stage_checkpoint(
                checkpoint_store,
                "LC2",
                input_sha256=lc2_input_sha256,
                result=lc2,
                artifact_paths=[free_energy_card_path],
            )

        # ── LC3 — solver-para card building → calc_input_card.json ──
        lc3_dir = base / "LC3"
        lc3_input_sha256 = _stage_input_sha256(
            "LC3",
            purpose=purpose,
            tasks=tasks,
            settings={},
            upstream_paths=[free_energy_card_path, system_catalog_path],
        )
        lc3 = _stage_checkpoint_result(
            checkpoint_store,
            "LC3",
            input_sha256=lc3_input_sha256,
        )
        if lc3 is not None:
            out["checkpoint"]["reused_stages"].append("LC3")
        else:
            _mark_stage_running(
                checkpoint_store,
                "LC3",
                input_sha256=lc3_input_sha256,
            )
            lc3 = run_lc3(
                purpose, tasks,
                fixed_card_path=str(free_energy_card_path),
                system_catalog_path=str(system_catalog_path),
                output_dir=lc3_dir,
                debug=debug,
            )
        out["lc3"] = lc3
        if lc3.get("status") != "ok":
            out["_error"] = str(lc3.get("_error") or "LC3 failed")
            return _finalize(out, t0)
        calc_card = lc3.get("final_card_path")
        out["calc_input_card_path"] = calc_card
        if not calc_card or not Path(calc_card).is_file():
            out["_error"] = f"LC3 calc-input card not found: {calc_card}"
            return _finalize(out, t0)
        if "LC3" not in out["checkpoint"]["reused_stages"]:
            _commit_stage_checkpoint(
                checkpoint_store,
                "LC3",
                input_sha256=lc3_input_sha256,
                result=lc3,
                artifact_paths=[calc_card],
            )

        out["status"] = "ok"
    except Exception as exc:                         # noqa: BLE001
        out["_error"] = f"{type(exc).__name__}: {exc}"

    return _finalize(out, t0)


def _finalize(out: Dict[str, Any], t0: float) -> Dict[str, Any]:
    out["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return out


# ════════════════════════════════════════════════════════════════════
#  Full pipeline — brief → cards → (optional) numeric sweep
# ════════════════════════════════════════════════════════════════════

def run_pipeline(
    purpose: str,
    tasks: str = "",
    *,
    output_dir: Union[str, Path],
    run_solver: bool = False,
    request_T_C: float = 25.0,
    request_I_M: float = 0.1,
    water_system: bool = True,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    resume: bool = True,
) -> Dict[str, Any]:
    """Build the calc-input card, then optionally run the numeric solver.

    With ``run_solver=False`` (default) this is exactly
    :func:`build_calc_input_card`.  With ``run_solver=True`` the resulting
    ``calc_input_card.json`` (together with the LC2 free-energy markdown
    card it points at) is handed to :func:`run_calculation`, and the
    solver result dict is attached under the ``solver`` key.

    Returns
    -------
    dict
        The :func:`build_calc_input_card` payload, plus ``solver`` (the
        :func:`run_calculation` result, or ``None`` when ``run_solver`` is
        ``False`` or the build failed).
    """
    effective_estimation = resolve_estimate_missing_equilibria(
        estimate_missing_equilibria
    )
    built = build_calc_input_card(
        purpose, tasks,
        output_dir=output_dir,
        request_T_C=request_T_C,
        request_I_M=request_I_M,
        water_system=water_system,
        debug=debug,
        estimate_missing_equilibria=effective_estimation,
        resume=resume,
    )
    built["solver"] = None

    if run_solver and built.get("status") == "ok":
        calc_card = built["calc_input_card_path"]
        card_source = built["free_energy_card_path"]
        solver_dir = Path(output_dir) / "solver"
        solver_store: DurableCheckpointStore | None = None
        if resume:
            try:
                solver_store = DurableCheckpointStore(
                    Path(output_dir) / "_checkpoints" / "solver_result.sqlite3",
                    identity={
                        "contract": "solver-result/v1",
                        "calc_input_card_sha256": file_sha256(calc_card),
                        "free_energy_card_sha256": file_sha256(card_source),
                    },
                )
            except CheckpointError as exc:
                built.setdefault("checkpoint", {})["solver_error"] = (
                    f"{type(exc).__name__}: {exc}"
                )
        cached_solver = (
            solver_store.get_pickle("solver", "result", None)
            if solver_store is not None else None
        )
        if (
            isinstance(cached_solver, dict)
            and isinstance(cached_solver.get("result"), dict)
            and validate_artifact_receipts(
                cached_solver.get("artifacts") or []
            )
        ):
            built["solver"] = cached_solver["result"]
            built.setdefault("checkpoint", {})["solver_reused"] = True
            solver_store.event("solver_checkpoint_reused")
        else:
            if solver_store is not None:
                solver_store.event("solver_started")
            built["solver"] = run_calculation(
                card_source=card_source,
                calc_input=calc_card,
                output_dir=str(solver_dir),
                debug=debug,
            )
            output_paths = list(
                (built.get("solver") or {}).get("output_paths") or []
            )
            receipts = artifact_receipts(output_paths)
            if solver_store is not None and receipts:
                solver_store.put_pickle("solver", "result", {
                    "result": built["solver"],
                    "artifacts": receipts,
                    "committed_at": time.time(),
                })
                solver_store.event(
                    "solver_checkpoint_committed",
                    artifact_count=len(receipts),
                )
            built.setdefault("checkpoint", {})["solver_reused"] = False

    return built
