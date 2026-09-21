"""LC1 — Eq-card alignment orchestrator (purpose + tasks → validated eq-map card).

This is the single top-level entry point for the **LC1** stage of the
calc-input-building pipeline. Its input is a ``purpose`` + ``tasks``
contract; everything else (the chemical system, the eq-map card, the
per-node patches) is derived downstream.

Pipeline chained here
---------------------
1. **LC1_1** — :func:`align_chemical_system`
   Resolves ``purpose`` + ``tasks`` into a canonical SRD-46
   ``chemical_system`` ``{metals:[...], ligands:[...]}`` (LLM
   ID-alignment agent + deterministic DB enrichment).
2. **LC1_2** — :func:`fetch_lc1_2_eq_map_card` + :func:`review_lc1_2_eq_map_card`
   For every ``(metal, ligand)`` pair, fetches and validates the
   eq-map, persisting parseable ``patch_notes`` into an augmented
   eq-map card (``lc1_2_eqmap_card.json``).  Between fetch and review,
   :func:`pair_coverage` compares the requested metal x ligand grid with
   the fetched card; on reference-only runs a requested metal or ligand
   with no SRD-46 partner data fails the stage (``coverage_gate_error``).

Public API
----------
``configure_lc1_session(session_dir, history, stats, working_memory, debug)``
    Bind the per-session side-channel and mirror it into both child
    stages (called once by the parent layer / L0).
``run_lc1(purpose, tasks=None, *, output_dir=None, ...) -> dict``
    Run the full LC1 stage from a ``purpose`` + ``tasks`` contract.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Child stages (sibling sub-packages) ------------------------------------
from .LC1_1_SRD46_eq_map_ID_alignment import (
    align_chemical_system,
    configure_lc1_1_session,
)
from .LC1_1_SRD46_eq_map_ID_alignment.id_enrichment_helpers import (
    sibling_metal_rows,
)
from .LC1_2_SRD46_eq_map_node_validator.LC1_2_eq_map_validator_orchestrator import (
    configure_lc1_2_session,
    fetch_lc1_2_eq_map_card,
    review_lc1_2_eq_map_card,
)
from ..SRD46_calc_input_building_config import (
    AGENT_CONFIG,
    resolve_estimate_missing_equilibria,
)

log = logging.getLogger("LC1.orchestrator")


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


def configure_lc1_session(
    *,
    session_dir: str | Path,
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
    base = _SESSION["session_dir"] or (Path.cwd() / "_lc1_adhoc")
    with _SESSION["_lock"]:
        _SESSION["call_index"] += 1
        idx = _SESSION["call_index"]
    out = Path(base) / f"LC1_call_{idx:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _clean_tasks(tasks: Any) -> str:
    """Return the free-text ``tasks`` brief verbatim.

    ``tasks`` is a single prose string passed end to end unchanged; only
    surrounding whitespace is trimmed (never split or templated).
    """
    if tasks is None:
        return ""
    return str(tasks).strip()


_AQUEOUS_SELF_IDS = {"metal_68", "ligand_10076"}   # H+ / OH-
_DB_ID_NUM_RE = re.compile(r"(\d+)$")


def _db_id_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    mo = _DB_ID_NUM_RE.search(str(value or ""))
    return int(mo.group(1)) if mo else None


def _is_water_species(entry: Dict[str, Any]) -> bool:
    return bool(entry.get("water_species")) or (
        str(entry.get("db_id") or "") in _AQUEOUS_SELF_IDS
    )


def pair_coverage(
    chemical_system: Dict[str, Any],
    eq_map_card: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare the requested metal x ligand grid with the fetched eq-map card.

    Water self-system entries (H+, OH-) are not "requested" chemistry.  A
    metal element counts as covered by a ligand when ANY of its redox states
    carries an eq_network for that ligand.  ``uncovered_ligands`` /
    ``uncovered_metals`` are requested entries with no data against any
    requested partner — the SRD-46 "not in database" premise failure.
    """
    metals = [
        m for m in (chemical_system.get("metals") or [])
        if isinstance(m, dict) and not _is_water_species(m)
    ]
    ligands = [
        l for l in (chemical_system.get("ligands") or [])
        if isinstance(l, dict) and not _is_water_species(l)
    ]

    metal_id_to_element: Dict[int, str] = {}
    elements: list[str] = []
    for m in metals:
        element = str(m.get("element") or m.get("name") or "").strip()
        if not element:
            continue
        if element not in elements:
            elements.append(element)
        for rs in m.get("redox_states") or []:
            rs_id = _db_id_int((rs or {}).get("db_id"))
            if rs_id is not None:
                metal_id_to_element[rs_id] = element
        mid = _db_id_int(m.get("db_id"))
        if mid is not None:
            metal_id_to_element[mid] = element
        # The fetch expands to every SRD-46 charge state of the element.
        for row in sibling_metal_rows(element):
            sib_id = _db_id_int(row.get("metal_id"))
            if sib_id is not None:
                metal_id_to_element.setdefault(sib_id, element)

    ligand_id_to_name: Dict[int, str] = {}
    for l in ligands:
        lid = _db_id_int(l.get("db_id"))
        if lid is not None:
            ligand_id_to_name[lid] = str(
                l.get("name") or l.get("internal_id") or lid
            )

    covered: set[tuple[str, int]] = set()
    for row in eq_map_card.get("equilibrium_networks") or []:
        element = metal_id_to_element.get(_db_id_int(row.get("metal_id")))
        lid = _db_id_int(row.get("ligand_id"))
        if element is not None and lid in ligand_id_to_name:
            covered.add((element, lid))

    covered_pairs = [
        [e, ligand_id_to_name[lid]]
        for e in elements for lid in ligand_id_to_name
        if (e, lid) in covered
    ]
    missing_pairs = [
        [e, ligand_id_to_name[lid]]
        for e in elements for lid in ligand_id_to_name
        if (e, lid) not in covered
    ]
    uncovered_ligands = [
        ligand_id_to_name[lid] for lid in ligand_id_to_name
        if not any((e, lid) in covered for e in elements)
    ]
    uncovered_metals = [
        e for e in elements
        if ligand_id_to_name
        and not any((e, lid) in covered for lid in ligand_id_to_name)
    ]
    return {
        "requested_metals": elements,
        "requested_ligands": list(ligand_id_to_name.values()),
        "covered_pairs": covered_pairs,
        "missing_pairs": missing_pairs,
        "uncovered_ligands": uncovered_ligands,
        "uncovered_metals": uncovered_metals,
        "complete": not missing_pairs,
    }


def coverage_gate_error(coverage: Dict[str, Any]) -> Optional[str]:
    """Return the premise-failure message, or ``None`` when the gate passes."""
    unc_l = coverage.get("uncovered_ligands") or []
    unc_m = coverage.get("uncovered_metals") or []
    if not unc_l and not unc_m:
        return None
    parts = []
    if unc_l:
        parts.append(
            "ligand(s) with no complexation data against any requested metal: "
            + ", ".join(unc_l)
        )
    if unc_m:
        parts.append(
            "metal(s) with no complexation data against any requested ligand: "
            + ", ".join(unc_m)
        )
    missing = ", ".join(
        f"{e} x {l}" for e, l in (coverage.get("missing_pairs") or [])
    )
    return (
        "SRD-46 has no data for the requested metal-ligand system "
        "(not in database): " + "; ".join(parts)
        + (f". Missing metal x ligand pairs: {missing}" if missing else "")
        + ". The requested speciation cannot be represented from SRD-46; "
        "the pipeline stopped before building any card. Report the missing "
        "data — do not substitute a different system or estimate constants."
    )


def _is_exact_sha256(value: Any) -> bool:
    """Return whether *value* is an exact lowercase SHA-256 receipt."""

    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _bind_child_sessions(call_dir: Path, debug: bool) -> tuple[Path, Path]:
    """Re-wire LC1_1 + LC1_2 per-session side-channels to this LC1 call.

    LC1_1 artefacts land under ``call_dir/LC1_1``; LC1_2 under
    ``call_dir/LC1_2`` so the whole stage shares one tree.
    """
    common = dict(
        history=_SESSION["history"],
        stats=_SESSION["stats"],
        working_memory=_SESSION["working_memory"],
        debug=debug,
    )
    lc1_1_dir = call_dir / "LC1_1"
    lc1_2_dir = call_dir / "LC1_2"
    lc1_1_dir.mkdir(parents=True, exist_ok=True)
    lc1_2_dir.mkdir(parents=True, exist_ok=True)
    configure_lc1_1_session(session_dir=lc1_1_dir, **common)
    configure_lc1_2_session(session_dir=lc1_2_dir, **common)
    return lc1_1_dir, lc1_2_dir


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def run_lc1(
    purpose: str,
    tasks: str = "",
    *,
    output_dir: str | Path | None = None,
    request_T_C: float = 25.0,
    request_I_M: float = 0.1,
    water_system: bool = True,
    max_validator_retries: int = 2,
    max_parallel: int = 4,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    chemical_context_plan: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full LC1 stage from a ``purpose`` + ``tasks`` contract.

    Parameters
    ----------
    purpose
        Free-text scientific question describing the chemistry of
        interest (one or two sentences, e.g. ``"Pourbaix diagram of
        copper in the presence of glycine"``).
    tasks
        Free-text brief written as natural prose. A single string,
        forwarded verbatim to both child stages (never split or
        templated). May be omitted/empty.
    output_dir
        Where to drop the LC1 artefact tree. If omitted, falls back to
        the per-call directory under whatever ``configure_lc1_session``
        bound (or ``./_lc1_adhoc`` if neither is set).
    request_T_C, request_I_M
        Reference conditions forwarded to LC1_2's deterministic screen.
    water_system
        When ``True`` (default), inject the aqueous self-system proton
        H⁺ (``metal_68``) and hydroxide OH⁻ (``ligand_10076``) into the
        LC1_1 chemical system so they are treated as first-class system
        entries by every downstream stage.
    max_validator_retries, max_parallel
        LC1_2 per-pair validator knobs.
    debug
        Verbose logging for the child agent loops.
    estimate_missing_equilibria
        Optional per-run override for query-assisted missing-equilibrium
        support. ``None`` inherits the shared default-false setting. The
        disabled path remains the established LC1_2 wrapper path and does not
        import, prompt, or create artifacts for LC1_3.
    chemical_context_plan
        Optional branch-only context included in the templated SRD46 query
        command when estimation is enabled. It is ignored when disabled.

    Returns
    -------
    dict
        ``{status, output_dir, purpose, tasks, chemical_system,
        system_catalog, eq_map_card_path, manifest_path, lc1_1, lc1_2,
        elapsed_s}``. ``status`` is ``"failed"`` when LC1_1 cannot
        resolve any chemistry; otherwise it mirrors the LC1_2 dispatch
        status (``ok`` / ``partial`` / ``failed`` / ``skipped``).
    """
    t0 = time.perf_counter()
    purpose_clean = (purpose or "").strip()
    tasks_norm = _clean_tasks(tasks)
    effective_estimation = resolve_estimate_missing_equilibria(
        estimate_missing_equilibria,
    )

    if _SESSION["session_dir"] is None and output_dir is not None:
        configure_lc1_session(session_dir=output_dir, debug=debug)

    call_dir = Path(output_dir) if output_dir is not None else _per_call_dir()
    call_dir.mkdir(parents=True, exist_ok=True)
    debug = bool(debug or _SESSION["debug"])

    history = _SESSION["history"]
    stats = _SESSION["stats"]
    working_memory = _SESSION["working_memory"]

    if not purpose_clean and not tasks_norm:
        if history is not None:
            history.log("LC1_run_skip", reason="empty purpose and tasks")
        return {
            "status":           "failed",
            "output_dir":       str(call_dir),
            "purpose":          purpose_clean,
            "tasks":            tasks_norm,
            "chemical_system":  {"metals": [], "ligands": []},
            "system_catalog":   None,
            "eq_map_card_path": None,
            "manifest_path":    None,
            "lc1_1":            None,
            "lc1_2":            None,
            "_error":           "empty purpose and tasks",
            "elapsed_s":        round(time.perf_counter() - t0, 3),
        }

    lc1_1_dir, lc1_2_dir = _bind_child_sessions(call_dir, debug)

    if history is not None:
        history.log("LC1_run_start", output_dir=str(call_dir))

    # ── 1. LC1_1 — resolve the chemical system ─────────────────────
    if history is not None:
        history.log("LC1_step_start", step="LC1_1")
    lc1_1 = align_chemical_system(
        purpose_clean, tasks_norm, session_dir=lc1_1_dir,
        water_system=water_system, debug=debug,
    )
    system_catalog = lc1_1.get("system_catalog") or {}
    chem = system_catalog.get("chemical_system") or {"metals": [], "ligands": []}
    metals = chem.get("metals") or []
    ligands = chem.get("ligands") or []

    if not metals and not ligands:
        elapsed = round(time.perf_counter() - t0, 3)
        err = lc1_1.get("_error") or "LC1_1 resolved no metals or ligands"
        if stats is not None:
            stats.incr("LC1", "runs", 1)
            stats.incr("LC1", "failed", 1)
        if history is not None:
            history.log("LC1_run_end", status="failed", detail=err,
                         elapsed_s=elapsed)
        out: Dict[str, Any] = {
            "status":           "failed",
            "output_dir":       str(call_dir),
            "purpose":          purpose_clean,
            "tasks":            tasks_norm,
            "chemical_system":  chem,
            "system_catalog":   system_catalog,
            "eq_map_card_path": None,
            "manifest_path":    None,
            "lc1_1":            lc1_1,
            "lc1_2":            None,
            "_error":           err,
            "elapsed_s":        elapsed,
        }
        _write_summary(call_dir, out)
        return out

    # ── 2. Eq-map acquisition/review, with an enabled-only LC1_3 seam ──
    # Keep this literal false fast path as the legacy call. In particular it
    # must not import LC1_3, load its templates, add prompt text, create its
    # directory, or add enabled-only result keys/events.
    lc1_3_result: Any = None
    lc1_3_payload: Optional[Dict[str, Any]] = None
    support_eq_map_path: Optional[str] = None
    support_session_id: Optional[str] = None
    support_eq_map_sha256: Optional[str] = None
    session_working_map_path: Optional[str] = None
    session_working_map_sha256: Optional[str] = None
    coverage: Optional[Dict[str, Any]] = None
    if not effective_estimation:
        if history is not None:
            history.log("LC1_step_start", step="LC1_2",
                         n_metals=len(metals), n_ligands=len(ligands))
        t_lc1_2 = time.perf_counter()
        fetched_card = fetch_lc1_2_eq_map_card(chemical_system=chem)
        # Reference-only runs cannot fill gaps: a requested metal or ligand
        # with no SRD-46 partner data is a premise failure, not a spectator.
        coverage = pair_coverage(chem, fetched_card)
        gate_error = coverage_gate_error(coverage)
        if gate_error is not None:
            elapsed = round(time.perf_counter() - t0, 3)
            log.warning("LC1 coverage gate failed: %s", gate_error)
            if stats is not None:
                stats.incr("LC1", "runs", 1)
                stats.incr("LC1", "failed", 1)
            if history is not None:
                history.log("LC1_run_end", status="failed",
                             detail=gate_error, elapsed_s=elapsed)
            out = {
                "status":           "failed",
                "output_dir":       str(call_dir),
                "purpose":          purpose_clean,
                "tasks":            tasks_norm,
                "chemical_system":  chem,
                "system_catalog":   system_catalog,
                "eq_map_card_path": None,
                "manifest_path":    None,
                "lc1_1":            lc1_1,
                "lc1_2":            None,
                "coverage":         coverage,
                "_error":           gate_error,
                "elapsed_s":        elapsed,
            }
            _write_summary(call_dir, out)
            return out
        lc1_2 = review_lc1_2_eq_map_card(
            card=fetched_card,
            purpose=purpose_clean,
            tasks=tasks_norm,
            output_dir=lc1_2_dir,
            request_T_C=request_T_C,
            request_I_M=request_I_M,
            max_validator_retries=max_validator_retries,
            max_parallel=max_parallel,
            _started_at=t_lc1_2,
        )
    else:
        # Imports, templates, models, database-tool binding, and the artefact
        # root all remain behind the resolved true gate. LC1_3 produces a
        # session-only, complete native support eq_map; it never modifies the
        # fetched reference card or performs free-energy conversion.
        from .LC1_3_estimate_eq_stability_dispatch.LC1_3_estimate_eq_stability_dispatch_orchestrator import (
            build_default_lc1_3_dependencies,
            run_lc1_3,
        )
        from .LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (
            LC13Settings,
        )

        lc1_3_dir = call_dir / "LC1_3"

        if history is not None:
            history.log("LC1_step_start", step="LC1_2.fetch",
                         n_metals=len(metals), n_ligands=len(ligands))
        fetched_card = fetch_lc1_2_eq_map_card(chemical_system=chem)
        # Reported only: LC1_3 estimation is the sanctioned gap filler here.
        coverage = pair_coverage(chem, fetched_card)

        try:
            settings = LC13Settings.from_config(AGENT_CONFIG)
            dependencies = build_default_lc1_3_dependencies(settings)
            if history is not None:
                history.log("LC1_step_start", step="LC1_3")
            lc1_3_result = run_lc1_3(
                base_eq_map_card=fetched_card,
                target_chemical_system=chem,
                purpose=purpose_clean,
                tasks=tasks_norm,
                chemical_context_plan=chemical_context_plan,
                request_T_C=request_T_C,
                request_I_M=request_I_M,
                output_dir=lc1_3_dir,
                settings=settings,
                dependencies=dependencies,
            )
            lc1_3_payload = lc1_3_result.as_dict()
            if lc1_3_result.estimation_search_complete is not True:
                reason = (
                    lc1_3_result.reference_only_reason
                    or lc1_3_result.status
                    or "unspecified"
                )
                raise RuntimeError(
                    "LC1_3 estimation search did not complete: "
                    f"{reason}"
                )
            candidate_support_path = lc1_3_result.support_eq_map_path
            candidate_session_id = lc1_3_result.session_id
            candidate_support_sha256 = lc1_3_result.support_eq_map_sha256
            candidate_working_map_path = getattr(
                lc1_3_result, "session_working_map_path", None
            )
            candidate_working_map_sha256 = getattr(
                lc1_3_result, "session_working_map_sha256", None
            )
            if candidate_support_path is not None:
                if (
                    not str(candidate_support_path).strip()
                    or not isinstance(candidate_session_id, str)
                    or not candidate_session_id.strip()
                    or not _is_exact_sha256(candidate_support_sha256)
                ):
                    raise RuntimeError(
                        "LC1_3 published support without its exact session ID "
                        "and SHA-256 provenance binding"
                    )
                if (
                    candidate_working_map_path is None
                    or not str(candidate_working_map_path).strip()
                    or not _is_exact_sha256(candidate_working_map_sha256)
                ):
                    raise RuntimeError(
                        "LC1_3 published support without a session working map "
                        "and its exact SHA-256 publication receipt"
                    )
                support_eq_map_path = candidate_support_path
                support_session_id = candidate_session_id
                support_eq_map_sha256 = candidate_support_sha256
                session_working_map_path = candidate_working_map_path
                session_working_map_sha256 = candidate_working_map_sha256
            if history is not None:
                history.log(
                    "LC1_step_end",
                    step="LC1_3",
                    status=lc1_3_result.status,
                    support_eq_map_path=support_eq_map_path,
                    support_session_id=support_session_id,
                    support_eq_map_sha256=support_eq_map_sha256,
                    session_working_map_path=session_working_map_path,
                    session_working_map_sha256=session_working_map_sha256,
                )
        except Exception as exc:
            # A runtime/infrastructure exception is not an ordinary
            # no-estimation result.  When the caller explicitly enabled
            # LC1_3, fail this build attempt closed so the enclosing ReAct
            # loop can repair/retry it instead of silently solving a
            # chemically narrower reference-only system.
            lc1_3_dir.mkdir(parents=True, exist_ok=True)
            failure_path = lc1_3_dir / "LC1_3_failure.json"
            error_text = f"{type(exc).__name__}: {exc}"
            prior_lc1_3_payload = dict(lc1_3_payload or {})
            incomplete_search = (
                prior_lc1_3_payload.get("estimation_search_complete") is False
            )
            failure_kind = (
                "lc1_3_incomplete_search"
                if incomplete_search
                else "lc1_3_runtime_failure"
            )
            failure_payload = {
                **prior_lc1_3_payload,
                "status": "failed",
                "error": error_text,
                "support_eq_map_path": None,
                "session_working_map_path": None,
                "session_working_map_sha256": None,
                "free_energy_conversion_performed": False,
                "estimation_search_complete": False,
                "reference_only_reason": failure_kind,
                "failure_summary": {
                    "kind": failure_kind,
                    "error": error_text,
                    "reference_path_continued": False,
                    "upstream_lc1_3": prior_lc1_3_payload or None,
                },
            }
            failure_path.write_text(
                json.dumps(failure_payload, indent=2, default=str),
                encoding="utf-8",
            )
            lc1_3_payload = {
                **failure_payload,
                "output_dir": str(lc1_3_dir),
                "manifest_path": str(failure_path),
                "counts": {
                    "scopes": 0, "validated": 0, "accepted": 0,
                    "rejected": 0, "failures": 1,
                },
            }
            if history is not None:
                history.log("LC1_step_end", step="LC1_3", status="failed",
                            detail=failure_payload["error"])

            elapsed = round(time.perf_counter() - t0, 3)
            if stats is not None:
                stats.incr("LC1", "runs", 1)
                stats.incr("LC1", "failed", 1)
            if history is not None:
                history.log(
                    "LC1_run_end",
                    status="failed",
                    detail=error_text,
                    elapsed_s=elapsed,
                )
            out = {
                "status": "failed",
                "output_dir": str(call_dir),
                "purpose": purpose_clean,
                "tasks": tasks_norm,
                "chemical_system": chem,
                "system_catalog": system_catalog,
                "eq_map_card_path": None,
                "manifest_path": str(failure_path),
                "lc1_1": lc1_1,
                "lc1_2": None,
                "lc1_3": lc1_3_payload,
                "support_eq_map_path": None,
                "support_session_id": None,
                "support_eq_map_sha256": None,
                "session_working_map_path": None,
                "session_working_map_sha256": None,
                "_error": (
                    "LC1_3 failed while missing-equilibrium estimation was "
                    f"enabled: {error_text}"
                ),
                "elapsed_s": elapsed,
            }
            _write_summary(call_dir, out)
            return out

        # Review the measured reference card through the established LC1_2
        # path. Estimated nodes remain a separate native support artefact and
        # are united with measured nodes deterministically in LC2, before the
        # common stability-constant/free-energy conversion.
        if history is not None:
            history.log("LC1_step_start", step="LC1_2.review")
        lc1_2 = review_lc1_2_eq_map_card(
            card=fetched_card,
            purpose=purpose_clean,
            tasks=tasks_norm,
            output_dir=lc1_2_dir,
            request_T_C=request_T_C,
            request_I_M=request_I_M,
            max_validator_retries=max_validator_retries,
            max_parallel=max_parallel,
        )

    status = lc1_2.get("status", "failed")
    eq_map_card_path = lc1_2.get("eq_map_card_path")
    manifest_path = lc1_2.get("manifest_path")
    elapsed = round(time.perf_counter() - t0, 3)

    if working_memory is not None:
        try:
            working_memory.set("lc1_chemical_system", chem)
            if eq_map_card_path:
                working_memory.set("lc1_eq_map_card_path", eq_map_card_path)
            if effective_estimation and support_eq_map_path:
                working_memory.set(
                    "lc1_support_eq_map_path",
                    support_eq_map_path,
                )
                working_memory.set(
                    "lc1_support_session_id",
                    support_session_id,
                )
                working_memory.set(
                    "lc1_support_eq_map_sha256",
                    support_eq_map_sha256,
                )
                working_memory.set(
                    "lc1_session_working_map_path",
                    session_working_map_path,
                )
                working_memory.set(
                    "lc1_session_working_map_sha256",
                    session_working_map_sha256,
                )
        except Exception as exc:                    # pragma: no cover
            log.warning("LC1 working_memory.set failed: %s", exc)

    if stats is not None:
        stats.incr("LC1", "runs", 1)
        stats.incr("LC1", "ok" if status == "ok" else status, 1)

    if history is not None:
        history.log("LC1_run_end", status=status,
                     eq_map_card_path=eq_map_card_path, elapsed_s=elapsed)

    out = {
        "status":           status,
        "output_dir":       str(call_dir),
        "purpose":          purpose_clean,
        "tasks":            tasks_norm,
        "chemical_system":  chem,
        "system_catalog":   system_catalog,
        "eq_map_card_path": eq_map_card_path,
        "manifest_path":    manifest_path,
        "lc1_1":            lc1_1,
        "lc1_2":            lc1_2,
        "coverage":         coverage,
        "elapsed_s":        elapsed,
    }
    if effective_estimation:
        out["lc1_3"] = lc1_3_payload
        out["support_eq_map_path"] = support_eq_map_path
        out["support_session_id"] = support_session_id
        out["support_eq_map_sha256"] = support_eq_map_sha256
        out["session_working_map_path"] = session_working_map_path
        out["session_working_map_sha256"] = session_working_map_sha256
    _write_summary(call_dir, out)
    return out


def _write_summary(call_dir: Path, out: Dict[str, Any]) -> None:
    """Persist the LC1 stage artefacts under the call directory.

    Layout::

        <call_dir>/
          lc1_2_eqmap_card.json   — copy of the final eq-map card LC1_2
                                    generated (parseable ``patch_notes``
                                    the downstream solver reads).
          lc1_sweep_input.json    — solver calc-input skeleton.  LC1 only
                                    builds the ``system_catalog`` block,
                                    so that is the *only* field written.
          summary/
            LC1_summary.json      — compact stage summary (child payloads
                                    elided), pointing at the artefacts
                                    above.
    """
    try:
        summary_dir = call_dir / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)

        # ── Copy the final eq-map card to the call-dir root ───────────
        eqmap_card_dst: Optional[Path] = None
        src = out.get("eq_map_card_path")
        if src:
            src_path = Path(src)
            if src_path.is_file():
                eqmap_card_dst = call_dir / "lc1_2_eqmap_card.json"
                shutil.copyfile(src_path, eqmap_card_dst)

        # ── Solver calc-input skeleton (only system_catalog is built) ─
        system_catalog = out.get("system_catalog") or {
            "chemical_system": {"metals": [], "ligands": []}
        }
        sweep_input = {"system_catalog": system_catalog}
        sweep_input_path = call_dir / "lc1_sweep_input.json"
        sweep_input_path.write_text(
            json.dumps(sweep_input, indent=2, default=str), encoding="utf-8",
        )

        # ── Compact stage summary, pointing at the artefacts above ────
        summary = {
            k: v
            for k, v in out.items()
            if k not in ("lc1_1", "lc1_2", "lc1_3")
        }
        summary["lc1_1_error"] = (out.get("lc1_1") or {}).get("_error")
        lc1_2 = out.get("lc1_2") or {}
        summary["lc1_2_status"] = lc1_2.get("status")
        summary["lc1_2_n_pairs"] = len(lc1_2.get("pair_results") or [])
        if "lc1_3" in out:
            lc1_3 = out.get("lc1_3") or {}
            summary["lc1_3"] = {
                "status": lc1_3.get("status"),
                "output_dir": lc1_3.get("output_dir"),
                "manifest_path": lc1_3.get("manifest_path"),
                "support_eq_map_path": lc1_3.get("support_eq_map_path"),
                "session_id": lc1_3.get("session_id"),
                "support_eq_map_sha256": lc1_3.get(
                    "support_eq_map_sha256"
                ),
                "session_working_map_path": lc1_3.get(
                    "session_working_map_path"
                ),
                "session_working_map_sha256": lc1_3.get(
                    "session_working_map_sha256"
                ),
                "estimation_search_complete": lc1_3.get(
                    "estimation_search_complete"
                ),
                "reference_only_reason": lc1_3.get(
                    "reference_only_reason"
                ),
                "failure_summary": lc1_3.get("failure_summary"),
                "base_eq_map_sha256": lc1_3.get("base_eq_map_sha256"),
                "reviewed_base_eq_map_sha256": lc1_3.get(
                    "reviewed_base_eq_map_sha256"
                ),
                "counts": lc1_3.get("counts"),
                "error": lc1_3.get("error"),
                "review_errors": lc1_3.get("review_errors"),
            }
        summary["sweep_input_path"] = str(sweep_input_path)
        summary["eqmap_card_path_copy"] = (
            str(eqmap_card_dst) if eqmap_card_dst else None
        )
        (summary_dir / "LC1_summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8",
        )
    except Exception:                               # pragma: no cover
        pass



__all__ = [
    "run_lc1",
    "configure_lc1_session",
]
