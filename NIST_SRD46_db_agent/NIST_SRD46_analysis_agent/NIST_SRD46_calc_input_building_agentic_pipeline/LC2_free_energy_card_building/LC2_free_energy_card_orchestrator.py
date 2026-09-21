"""LC2 — Free-energy card-building orchestrator (purpose + tasks + LC1
artefacts → solver-validated free-energy card).

This is the single top-level entry point for the **LC2** stage of the
calc-input-building pipeline. Its inputs are the L0 ``purpose`` +
``tasks`` contract plus the LC1 artefacts (the system-catalog card and,
when available, the LC1_2 ``lc1_2_eqmap_card.json`` ref-eq card).

Pipeline chained here
---------------------
1. **LC2_1** — :func:`run_lc2_1`
   Build the per-pair SRD-46 reference-equilibrium cards and merge them
   into one ``free_energy_card.md`` (no LLM inside LC2; SRD-46 plus any
   validated, explicitly enabled LC1_3 support overlay). Driven by the LC1_2
   eq-map card when present, otherwise synthesised from the system catalog.
2. **LC2_2** — :func:`run_lc2_2`  *(conditional)*
   Merge entries from databases OTHER than SRD-46 (Pourbaix atlas, CRC
   redox). Which external DBs participate is an **Argo-config setting**
   (``LC2_2_POURBAIX_ENABLED`` / ``LC2_2_CRC_REDOX_ENABLED``). When no
   external DB is enabled there is nothing to merge — the SRD-46 card is
   already final — so **both LC2_2 and LC2_3 are skipped**.
3. **LC2_3** — :func:`run_lc2_3`  *(conditional)*
   Groupwise LLM review of all candidates from the external/source merge,
   including singleton groups. It runs only when LC2_2 produced a
   ``deduplication_check.md`` report.
4. **LC2_4** — :func:`run_lc2_4`
   Validate (and, if needed, LLM-repair) the card against the solver's
   own parser, emitting the final ``free_energy_card_validated.md``.

Public API
----------
``configure_lc2_session(session_dir, history, stats, working_memory, debug)``
    Bind the per-session side-channel and mirror it into the LC2_3 /
    LC2_4 child stages (called once by the parent layer / L0).
``run_lc2(purpose, tasks, *, system_catalog_path=None,
          lc1_2_eqmap_card_path=None, output_dir=None, ...) -> dict``
    Run the full LC2 stage.
"""
from __future__ import annotations

import json
import hashlib
import logging
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ── Paths (drive-letter form; never .resolve() — UNC long-paths break
#    Python's import machinery on this N: share). Mirror LC2_2's header
#    so the bare config module + sibling packages resolve identically. ─
_THIS = Path(__file__)
_LC2_ROOT      = _THIS.parents[0]   # LC2_free_energy_card_building/
_PIPELINE_ROOT = _THIS.parents[1]   # NIST_SRD46_calc_input_building_agentic_pipeline/
_ANALYSIS_ROOT = _THIS.parents[2]   # NIST_SRD46_analysis_agent/
_SRD46_ROOT    = _THIS.parents[4]   # SRD46_research_agent/
_NUMCALC_ROOT  = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"

for _p in (_PIPELINE_ROOT, _LC2_ROOT, _NUMCALC_ROOT, _ANALYSIS_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Shared analysis config as a bare top-level module (avoids the heavy
# NIST_SRD46_analysis_agent package __init__ chain).
try:
    from SRD46_analysis_argo_config import AGENT_CONFIG as cfg  # noqa: E402
except Exception:                                # pragma: no cover
    from SRD46_calc_input_building_config import AGENT_CONFIG as cfg  # noqa: E402

# Child stages -----------------------------------------------------------
from .LC2_1_card_initializer.LC2_1_ref_eq_card_orchestrator import run_lc2_1
from .LC2_2_card_db_merger.lc2_2_orchestrator import run_lc2_2
from .LC2_3_card_deduplicator.lc2_3_dedup_agent import (
    configure_lc2_3_session,
    run_lc2_3,
)
from .LC2_4_card_validator.lc2_4_validator_agent import (
    CardValidationError,
    configure_lc2_4_session,
    run_lc2_4,
)
from .agent_context_artifacts import (
    _display_path,
    _io_path,
    verify_agent_context_manifest,
)

log = logging.getLogger("LC2.orchestrator")


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


def configure_lc2_session(
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
    base = _SESSION["session_dir"] or (Path.cwd() / "_lc2_adhoc")
    with _SESSION["_lock"]:
        _SESSION["call_index"] += 1
        idx = _SESSION["call_index"]
    out = Path(base) / f"LC2_call_{idx:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _clean_tasks(tasks: Any) -> str:
    """Return the free-text ``tasks`` brief verbatim (no splitting)."""
    if tasks is None:
        return ""
    return str(tasks).strip()


def _validate_support_handoff(
    *,
    support_eq_map_path: Union[str, Path, None],
    expected_support_session_id: Optional[str],
    expected_support_eq_map_sha256: Optional[str],
    session_working_map_path: Union[str, Path, None],
    expected_session_working_map_sha256: Optional[str],
) -> None:
    """Fail closed unless an enabled LC1 handoff is complete and exact."""

    enabled_receipts = (
        expected_support_session_id,
        expected_support_eq_map_sha256,
        session_working_map_path,
        expected_session_working_map_sha256,
    )
    if support_eq_map_path is None:
        if any(value is not None for value in enabled_receipts):
            raise ValueError(
                "enabled support receipts require support_eq_map_path"
            )
        return
    if not str(support_eq_map_path).strip():
        raise ValueError("support_eq_map_path must be a nonempty path")
    if not isinstance(expected_support_session_id, str) or not (
        expected_support_session_id.strip()
    ):
        raise ValueError(
            "support_eq_map_path requires expected_support_session_id"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_support_eq_map_sha256)
    ) is None:
        raise ValueError(
            "support_eq_map_path requires an exact lowercase "
            "expected_support_eq_map_sha256"
        )
    if session_working_map_path is None or not str(
        session_working_map_path
    ).strip():
        raise ValueError(
            "support_eq_map_path requires session_working_map_path"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_session_working_map_sha256)
    ) is None:
        raise ValueError(
            "support_eq_map_path requires an exact lowercase "
            "expected_session_working_map_sha256"
        )


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def run_lc2(
    purpose: str,
    tasks: str = "",
    *,
    system_catalog_path: Union[str, Path, None] = None,
    lc1_2_eqmap_card_path: Union[str, Path, None] = None,
    output_dir: Union[str, Path, None] = None,
    test_name: Optional[str] = None,
    enable_pourbaix: Optional[bool] = None,
    enable_crc: Optional[bool] = None,
    elements: Optional[List[str]] = None,
    temperature_K: Optional[float] = None,
    debug: bool = False,
    support_eq_map_path: Union[str, Path, None] = None,
    expected_support_session_id: Optional[str] = None,
    expected_support_eq_map_sha256: Optional[str] = None,
    session_working_map_path: Union[str, Path, None] = None,
    expected_session_working_map_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full LC2 stage.

    Parameters
    ----------
    purpose, tasks
        L0 audit contract. ``tasks`` accepts a list or a
        newline/semicolon-delimited string.
    system_catalog_path
        LC1 system-catalog card (``lc1_sweep_input.json`` /
        ``system_catalog.json``). Supplies metal/ligand IDs and the
        human-readable system name. Optional if a ref-eq card is given.
    lc1_2_eqmap_card_path
        LC1_2 ``lc1_2_eqmap_card.json`` (the validated/patched ref-eq
        card). When present it drives the LC2_1 build; otherwise LC2_1
        synthesises the eq-map from the catalog. Either this or
        ``system_catalog_path`` must be supplied.
    output_dir
        Base directory for the LC2 artefact tree. Falls back to the
        per-call directory under whatever ``configure_lc2_session``
        bound (or ``./_lc2_adhoc`` if neither is set).
    test_name
        Folder/identity label forwarded to LC2_1 / LC2_2. Defaults to
        the catalog/card-derived name.
    enable_pourbaix, enable_crc
        Override the external-DB merge toggles. ``None`` -> Argo-config
        defaults (``LC2_2_POURBAIX_ENABLED`` / ``LC2_2_CRC_REDOX_ENABLED``).
        When BOTH resolve False there is no external DB to merge, so the
        LC2_2 merge and LC2_3 dedup stages are skipped (SRD-46 only).
    elements
        Optional element-set override forwarded to LC2_2 / LC2_3.
    temperature_K
        Optional temperature forwarded to LC2_4's solver resolver.
    support_eq_map_path
        Enabled-run LC1_3 accepted-equilibrium sidecar.  When absent, LC2_1
        is called with its literal legacy argument set.
    expected_support_session_id, expected_support_eq_map_sha256
        Enabled-only provenance receipt from the exact LC1_3 publication.
        Both are required when ``support_eq_map_path`` is present.
    session_working_map_path, expected_session_working_map_sha256
        Exact LC1_3 session-map publication and digest. Both are mandatory
        whenever ``support_eq_map_path`` is present.
    debug
        Verbose logging for the child agent loops.

    Returns
    -------
    dict
        ``{status, output_dir, purpose, tasks, system_name,
        final_card_path, lc2_1, lc2_2, lc2_3, lc2_4, stages_run,
        db_merge_skipped, elapsed_s}``.
    """
    t0 = time.perf_counter()
    purpose_clean = (purpose or "").strip()
    tasks_norm = _clean_tasks(tasks)

    if system_catalog_path is None and lc1_2_eqmap_card_path is None:
        raise ValueError(
            "run_lc2 needs a system_catalog_path and/or a "
            "lc1_2_eqmap_card_path"
        )
    _validate_support_handoff(
        support_eq_map_path=support_eq_map_path,
        expected_support_session_id=expected_support_session_id,
        expected_support_eq_map_sha256=expected_support_eq_map_sha256,
        session_working_map_path=session_working_map_path,
        expected_session_working_map_sha256=(
            expected_session_working_map_sha256
        ),
    )

    if _SESSION["session_dir"] is None and output_dir is not None:
        configure_lc2_session(session_dir=output_dir, debug=debug)

    call_dir = Path(output_dir) if output_dir is not None else _per_call_dir()
    call_dir.mkdir(parents=True, exist_ok=True)
    debug = bool(debug or _SESSION["debug"])

    history        = _SESSION["history"]
    stats          = _SESSION["stats"]
    working_memory = _SESSION["working_memory"]

    # Resolve the external-DB merge toggles from config when unset.
    if enable_pourbaix is None:
        enable_pourbaix = bool(getattr(cfg, "LC2_2_POURBAIX_ENABLED", True))
    if enable_crc is None:
        enable_crc = bool(getattr(cfg, "LC2_2_CRC_REDOX_ENABLED", False))
    do_merge = enable_pourbaix or enable_crc

    if history is not None:
        history.log("LC2_run_start", output_dir=str(call_dir),
                    do_merge=do_merge, enable_pourbaix=enable_pourbaix,
                    enable_crc=enable_crc)

    stages_run: List[str] = []
    out: Dict[str, Any] = {
        "status":           "failed",
        "output_dir":       str(call_dir),
        "purpose":          purpose_clean,
        "tasks":            tasks_norm,
        "system_name":      None,
        "final_card_path":  None,
        "lc2_1":            None,
        "lc2_2":            None,
        "lc2_3":            None,
        "lc2_4":            None,
        "stages_run":       stages_run,
        "db_merge_skipped": not do_merge,
        "elapsed_s":        0.0,
        "inputs": {
            "system_catalog_path": (
                str(system_catalog_path) if system_catalog_path else None
            ),
            "lc1_2_eqmap_card_path": (
                str(lc1_2_eqmap_card_path) if lc1_2_eqmap_card_path else None
            ),
            "support_eq_map_path": (
                str(support_eq_map_path) if support_eq_map_path else None
            ),
            "session_working_map_path": (
                str(session_working_map_path)
                if session_working_map_path else None
            ),
        },
    }

    try:
        # ── 1. LC2_1 — SRD-46 reference cards → merged card ─────────
        lc2_1_dir = call_dir / "LC2_1"
        if history is not None:
            history.log("LC2_step_start", step="LC2_1")
        if support_eq_map_path is None:
            lc2_1 = run_lc2_1(
                system_catalog_path=system_catalog_path,
                lc1_2_eqmap_card_path=lc1_2_eqmap_card_path,
                output_dir=lc2_1_dir,
                test_name=test_name,
            )
        else:
            lc2_1 = run_lc2_1(
                system_catalog_path=system_catalog_path,
                lc1_2_eqmap_card_path=lc1_2_eqmap_card_path,
                output_dir=lc2_1_dir,
                test_name=test_name,
                support_eq_map_path=support_eq_map_path,
                expected_support_session_id=expected_support_session_id,
                expected_support_eq_map_sha256=expected_support_eq_map_sha256,
                session_working_map_path=session_working_map_path,
                expected_session_working_map_sha256=(
                    expected_session_working_map_sha256
                ),
            )
        stages_run.append("LC2_1")
        out["lc2_1"] = lc2_1
        system_name = lc2_1.get("system_name") or (test_name or "LC2 system")
        out["system_name"] = system_name
        current_card = Path(lc2_1["merged_card_path"])
        if test_name is None:
            test_name = lc2_1.get("test_name")
        # SRD-SRD duplicate twins kept in the LC2_1 card MUST reach LC2_3.
        srd_dup_count = int(lc2_1.get("srd_srd_collision_count") or 0)

        # ── 2/3. LC2_2 merge + LC2_3 dedup (only when an external DB
        #          actually participates) ───────────────────────────
        if do_merge:
            lc2_2_dir = call_dir / "LC2_2"
            if history is not None:
                history.log("LC2_step_start", step="LC2_2",
                            enable_pourbaix=enable_pourbaix,
                            enable_crc=enable_crc)
            lc2_2 = run_lc2_2(
                current_card,
                output_dir=lc2_2_dir,
                test_name=test_name,
                enable_pourbaix=enable_pourbaix,
                enable_crc=enable_crc,
                elements=elements,
            )
            stages_run.append("LC2_2")
            out["lc2_2"] = lc2_2
            current_card = Path(lc2_2["merged_card_path"])

            # LC2_3 only when LC2_2 emitted a cross-source dedup report.
            dedup_report_path = lc2_2.get("dedup_report_path")
            if dedup_report_path and Path(dedup_report_path).is_file():
                lc2_3_dir = call_dir / "LC2_3"
                lc2_3_dir.mkdir(parents=True, exist_ok=True)
                configure_lc2_3_session(
                    session_dir=lc2_3_dir, history=history, stats=stats,
                    working_memory=working_memory, debug=debug,
                )
                dedup_md = Path(dedup_report_path).read_text(encoding="utf-8")
                if history is not None:
                    history.log("LC2_step_start", step="LC2_3")
                lc2_3 = run_lc2_3(
                    purpose=purpose_clean,
                    tasks=tasks_norm,
                    dedup_md=dedup_md,
                    merged_card_path=current_card,
                    system_name=system_name,
                    output_dir=lc2_3_dir,
                    elements=elements,
                    element_inventory_path=lc2_2.get("element_inventory_path"),
                )
                stages_run.append("LC2_3")
                out["lc2_3"] = lc2_3
                if lc2_3.get("status") == "failed":
                    raise RuntimeError(
                        "LC2_3 element-level dedup review failed closed: "
                        f"{lc2_3.get('report', 'no report')}"
                    )
                current_card = Path(lc2_3["enriched_card_path"])
            else:
                if srd_dup_count:
                    raise RuntimeError(
                        f"LC2: {srd_dup_count} SRD-SRD duplicate group(s) "
                        "require LC2_3 adjudication, but LC2_2 emitted no "
                        "dedup report so LC2_3 cannot run. Refusing to "
                        "forward unresolved duplicate twins to the solver."
                    )
                log.info("LC2_3 skipped: LC2_2 produced no dedup report.")
        else:
            if srd_dup_count:
                raise RuntimeError(
                    f"LC2: {srd_dup_count} SRD-SRD duplicate group(s) "
                    "require LC2_3 adjudication, but the external-DB merge "
                    "(LC2_2/LC2_3) is disabled for this run. Enable LC2_2 "
                    "or resolve the duplicate frames upstream."
                )
            log.info("LC2_2/LC2_3 skipped: no external DB to merge "
                     "(SRD-46 only).")

        # ── 4. LC2_4 — validate / repair against the solver parser ──
        lc2_4_dir = call_dir / "LC2_4"
        lc2_4_dir.mkdir(parents=True, exist_ok=True)
        configure_lc2_4_session(
            session_dir=lc2_4_dir, history=history, stats=stats,
            working_memory=working_memory, debug=debug,
        )
        if history is not None:
            history.log("LC2_step_start", step="LC2_4")
        lc2_4 = run_lc2_4(
            purpose=purpose_clean,
            tasks=tasks_norm,
            enriched_card_path=current_card,
            output_dir=lc2_4_dir,
            temperature_K=temperature_K,
        )
        stages_run.append("LC2_4")
        out["lc2_4"] = lc2_4
        current_card = Path(lc2_4["validated_card_path"])

        out["status"] = "ok"

    except CardValidationError as exc:
        out["status"] = "failed"
        out["_error"] = f"LC2_4 validation failed: {exc}"
        log.error("LC2 failed at validation: %s", exc)
    except Exception as exc:                         # noqa: BLE001
        out["status"] = "failed"
        out["_error"] = f"{type(exc).__name__}: {exc}"
        log.exception("LC2 stage raised")

    # ── Final card + summary ────────────────────────────────────────
    elapsed = round(time.perf_counter() - t0, 3)
    out["elapsed_s"] = elapsed
    if out["status"] == "ok":
        try:
            final_dst = call_dir / "free_energy_card.md"
            shutil.copyfile(current_card, final_dst)
            out["final_card_path"] = str(final_dst)
        except Exception:                            # pragma: no cover
            out["final_card_path"] = str(current_card)

    if working_memory is not None and out.get("final_card_path"):
        try:
            working_memory.set("lc2_final_card_path", out["final_card_path"])
        except Exception as exc:                     # pragma: no cover
            log.warning("LC2 working_memory.set failed: %s", exc)

    if stats is not None:
        stats.incr("LC2", "runs", 1)
        stats.incr("LC2", "ok" if out["status"] == "ok" else "failed", 1)

    if history is not None:
        history.log("LC2_run_end", status=out["status"],
                    final_card_path=out.get("final_card_path"),
                    stages_run=stages_run, elapsed_s=elapsed)

    _write_summary(call_dir, out)
    return out


def _write_summary(call_dir: Path, out: Dict[str, Any]) -> None:
    """Persist a compact LC2 stage summary under ``summary/``.

    Full child payloads are elided; only their headline keys are kept.
    """
    try:
        summary_dir = call_dir / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)

        def _headline(stage: Optional[Dict[str, Any]], keys: tuple) -> Any:
            if not isinstance(stage, dict):
                return None
            return {k: stage.get(k) for k in keys}

        summary = {
            k: v for k, v in out.items()
            if k not in ("lc2_1", "lc2_2", "lc2_3", "lc2_4")
        }
        lc2_1_keys = [
            "system_name", "merged_card_path", "n_ref_cards",
            "n_species_merged",
        ]
        if isinstance(out.get("lc2_1"), dict) and out["lc2_1"].get("support_eq_map_path"):
            lc2_1_keys.extend((
                "support_eq_map_path", "support_eq_map_sha256",
                "support_session_id", "expected_support_session_id",
                "expected_support_eq_map_sha256",
                "provenance_binding_verified",
                "session_working_map_path", "session_working_map_sha256",
                "expected_session_working_map_sha256",
                "session_working_map_binding_verified",
                "support_candidate_count", "selected_support_node_count",
                "materialized_estimated_entry_count",
                "support_compile_manifest_path",
            ))
        summary["lc2_1"] = _headline(out.get("lc2_1"), tuple(lc2_1_keys))
        summary["lc2_2"] = _headline(
            out.get("lc2_2"),
            ("merged_card_path", "dedup_report_path", "enable_pourbaix",
             "enable_crc", "pathways_applied"),
        )
        summary["lc2_3"] = _headline(
            out.get("lc2_3"),
            ("status", "enriched_card_path", "n_groups", "n_dropped",
             "n_failures", "manifest_path", "agent_context_index_path",
             "agent_context_complete", "review_turns", "full_restarts",
             "targeted_reruns", "commit_flag_acknowledgement"),
        )
        summary["lc2_4"] = _headline(
            out.get("lc2_4"),
            ("status", "validated_card_path", "repaired", "n_edits",
             "manifest_path", "agent_context_index_path",
             "agent_context_complete"),
        )
        summary_path = summary_dir / "LC2_summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8",
        )

        def _record(path: Path) -> Dict[str, Any]:
            data = _io_path(path).read_bytes()
            return {
                "path": _display_path(path),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }

        # Forced \\?\ prefix: an unprefixed rglob root silently fails to
        # descend into >MAX_PATH subdirs, undercounting context bundles.
        walk_root = _io_path(call_dir, force=True)
        stage_manifests = sorted(
            path for path in walk_root.rglob("lc2_*_manifest.json")
            if path.name != "LC2_artifact_manifest.json"
        )
        context_manifests = sorted(
            walk_root.rglob("agent_context_manifest.json")
        )
        stage_context_audits = []
        for path in stage_manifests:
            payload = json.loads(path.read_text(encoding="utf-8"))
            audit = payload.get("agent_context")
            if isinstance(audit, dict):
                stage_context_audits.append({
                    "stage_manifest": _display_path(path),
                    "expected_calls": int(audit.get("expected_calls", 0)),
                    "documented_calls": int(audit.get("documented_calls", 0)),
                    "complete": bool(audit.get("complete", False)),
                })
        expected_contexts = sum(
            item["expected_calls"] for item in stage_context_audits
        )
        documented_contexts = sum(
            item["documented_calls"] for item in stage_context_audits
        )
        verified_contexts = sum(
            verify_agent_context_manifest(path) for path in context_manifests
        )
        context_audit_complete = (
            all(item["complete"] for item in stage_context_audits)
            and expected_contexts == documented_contexts
            and documented_contexts == len(context_manifests)
            and verified_contexts == len(context_manifests)
        )
        artifact_manifest = {
            "schema_version": 1,
            "artifact_kind": "LC2 run artifact index",
            "status": out.get("status"),
            "stages_run": out.get("stages_run", []),
            "inputs": out.get("inputs", {}),
            "final_card_path": out.get("final_card_path"),
            "summary": _record(summary_path),
            "stage_manifests": [_record(path) for path in stage_manifests],
            "agent_context_manifests": [
                _record(path) for path in context_manifests
            ],
            "agent_context_count": len(context_manifests),
            "agent_context_audit": {
                "expected_calls": expected_contexts,
                "documented_calls": documented_contexts,
                "indexed_manifests": len(context_manifests),
                "verified_bundles": verified_contexts,
                "complete": context_audit_complete,
                "stage_audits": stage_context_audits,
            },
            "documentation": str((_LC2_ROOT / "README.md").absolute()),
        }
        artifact_json_path = summary_dir / "LC2_artifact_manifest.json"
        artifact_json_path.write_text(
            json.dumps(artifact_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        md_lines = [
            "# LC2 artifact index",
            "",
            f"- status: {out.get('status')}",
            f"- stages: {', '.join(out.get('stages_run', [])) or 'none'}",
            f"- final card: `{out.get('final_card_path') or 'none'}`",
            f"- documented agent turns: {len(context_manifests)}",
            f"- verified context bundles: {verified_contexts}",
            f"- aggregate context audit complete: "
            f"{str(context_audit_complete).lower()}",
            "",
            "## Stage manifests",
            "",
        ]
        md_lines.extend(
            f"- `{_display_path(path)}`" for path in stage_manifests
        )
        md_lines.extend((
            "",
            "## Agent context manifests",
            "",
        ))
        md_lines.extend(
            f"- `{_display_path(path)}`" for path in context_manifests
        )
        (summary_dir / "LC2_artifact_manifest.md").write_text(
            "\n".join(md_lines) + "\n", encoding="utf-8",
        )
        out["artifact_manifest_path"] = str(artifact_json_path)
        out["artifact_manifest_md_path"] = str(
            summary_dir / "LC2_artifact_manifest.md"
        )
        if not context_audit_complete:
            raise RuntimeError(
                "LC2 aggregate agent-context audit is incomplete: "
                f"expected={expected_contexts}, documented={documented_contexts}, "
                f"indexed={len(context_manifests)}, verified={verified_contexts}"
            )
    except Exception as exc:                         # pragma: no cover
        out["status"] = "failed"
        out["artifact_manifest_error"] = repr(exc)
        log.exception("LC2 artifact documentation failed closed")
        raise RuntimeError(
            "LC2 artifact documentation is incomplete; refusing an "
            "undocumented hand-off."
        ) from exc


__all__ = [
    "run_lc2",
    "configure_lc2_session",
]
