"""LC1_2 — Eq-map node validator orchestrator (per-pair, parallel).

For one chemical system (LC1_1 output) this orchestrator:

1. Calls :func:`fetch_eqmap_card` to build the per-pair eq-map card
   (one ``eq_network`` row per ``(metal, ligand)`` pair).
2. For each pair, in parallel:
   a. Synthesises a minimal ephemeral ``maps_v0.json`` from the
      pair's ``network_db_id`` so :func:`screen_eq_map` can
      materialise the deterministic per-node screen.
   b. If :data:`cfg.LC1_2_ENABLED` is True, dispatches
      :func:`validate_eq_map_pair` (the per-pair LLM curator). On
      validator failure (i.e. the agent's payload couldn't be
      parsed), retries up to ``max_validator_retries`` times,
      feeding the validator errors back as ``extra_user_context``.
   c. Writes the validated patch list, the screen summary, and any
      residual error into the corresponding ``eq_network.patch_notes``
      slot.
3. Persists the augmented eq-map card (``lc1_2_eqmap_card.json``) and
   a per-pair manifest.

The SRD-46 SQL DB is only ever READ. Patches are persisted as
parseable JSON inside ``patch_notes``; the downstream pipeline reads
the card and hardcodes the edits.

Public API
----------
configure_lc1_2_session(session_dir, history, stats, working_memory, debug)
run_lc1_2(chemical_system, purpose, tasks, output_dir, ...) -> dict
"""
from __future__ import annotations

import copy
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from ....SRD46_analysis_argo_config import AGENT_CONFIG as cfg
from .eqmap_fetch_helpers import empty_patch_notes, fetch_eqmap_card
from .eqmap_validation_helpers import (
    EqMapScreen,
    PatchValidationResult,
    format_errors_for_agent,
    render_screen_md,
    screen_eq_map,
)
from .LC1_2_eq_map_validator_subagent import (
    ValidationResult,
    configure_lc1_2_session as _configure_subagent_session,
    validate_eq_map_pair,
)

log = logging.getLogger("LC1_2.orchestrator")

DEFAULT_MAX_VALIDATOR_RETRIES = 2     # = up to 3 subagent calls per pair
DEFAULT_MAX_PARALLEL = 4

_NET_ID_RE = re.compile(r"ref_eq_net_(\d+)")


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


def configure_lc1_2_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    """Bind the per-session side-channel (called once by the caller)."""
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0
    # Mirror into the subagent so per-pair logs share the session tree.
    _configure_subagent_session(
        session_dir=session_dir,
        history=history,
        stats=stats,
        working_memory=working_memory,
        debug=debug,
    )


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or Path.cwd()
    with _SESSION["_lock"]:
        _SESSION["call_index"] += 1
        idx = _SESSION["call_index"]
    out = Path(base) / f"c{idx:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════

def _network_db_id_of(pair_row: Dict[str, Any]) -> int:
    """Extract the SRD-46 ``network_db_id`` from a card row."""
    raw = pair_row.get("eq_network") or ""
    m = _NET_ID_RE.match(str(raw).strip())
    if not m:
        raise ValueError(f"cannot parse network_db_id from eq_network={raw!r}")
    return int(m.group(1))


def _write_maps_v0(
    *,
    pair_log_dir: Path,
    metal_id: int,
    ligand_id: int,
    network_db_id: int,
) -> Path:
    """Synthesize the ephemeral ``maps_v0.json`` consumed by ``screen_eq_map``."""
    payload = {
        "pair_key": f"m{metal_id}_l{ligand_id}",
        "pairs": [
            {
                "metal_id":             int(metal_id),
                "ligand_id":            int(ligand_id),
                "selected_network_ids": [int(network_db_id)],
            }
        ],
    }
    path = pair_log_dir / "maps_v0.json"
    path.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))
    return path


def _screen_summary(screen: EqMapScreen) -> Dict[str, Any]:
    """Compact summary embedded in ``patch_notes.screen_summary``."""
    return {
        "n_nodes":            len(screen.nodes),
        "n_critical":         len(screen.critical_node_keys),
        "n_warn":             len(screen.warn_node_keys),
        "critical_node_keys": list(screen.critical_node_keys),
        "warn_node_keys":     list(screen.warn_node_keys),
    }


def _clean_tasks(tasks: Any) -> str:
    """Return the free-text ``tasks`` brief verbatim (no splitting)."""
    if tasks is None:
        return ""
    return str(tasks).strip()


# ════════════════════════════════════════════════════════════════════
#  Per-pair worker
# ════════════════════════════════════════════════════════════════════

def _validate_one_pair(
    *,
    pair_row: Dict[str, Any],
    purpose: str,
    tasks: str,
    request_T_C: float,
    request_I_M: float,
    max_validator_retries: int,
    pair_log_dir: Path,
    pair_review_context: str = "",
) -> Dict[str, Any]:
    """Validate ONE (metal, ligand) eq-map. Returns the patch_notes dict
    plus orchestrator metadata for the manifest."""
    pair_log_dir.mkdir(parents=True, exist_ok=True)

    metal_id  = int(pair_row.get("metal_id")  or 0)
    ligand_id = int(pair_row.get("ligand_id") or 0)
    pair_key  = f"m{metal_id}_l{ligand_id}"

    notes = empty_patch_notes()
    out: Dict[str, Any] = {
        "pair_key":     pair_key,
        "metal_id":     metal_id,
        "metal_name":   pair_row.get("metal_name", ""),
        "ligand_id":    ligand_id,
        "ligand_name":  pair_row.get("ligand_name", ""),
        "eq_network":   pair_row.get("eq_network"),
        "status":       "ok",
        "log_dir":      str(pair_log_dir),
        "patch_notes":  notes,
    }

    # ── 1. Build ephemeral draft + run the deterministic screen ─
    try:
        network_db_id = _network_db_id_of(pair_row)
        maps_path = _write_maps_v0(
            pair_log_dir=pair_log_dir,
            metal_id=metal_id,
            ligand_id=ligand_id,
            network_db_id=network_db_id,
        )
        screen = screen_eq_map(
            pair_key=pair_key,
            eq_map_meta={"maps_json_path": str(maps_path)},
            request_T_C=request_T_C,
            request_I_M=request_I_M,
        )
    except Exception as exc:
        notes["error"] = f"screen_failed: {exc!r}"
        out["status"]  = "failed"
        return out

    (pair_log_dir / "screen.md").write_bytes(
        render_screen_md(screen).encode("utf-8"),
    )
    (pair_log_dir / "screen.json").write_bytes(
        json.dumps(screen.as_dict(), indent=2, default=str).encode("utf-8"),
    )

    notes["screen_summary"] = _screen_summary(screen)

    # ── 2. If LC1_2 disabled, record screen-only and return ─────
    if not cfg.LC1_2_ENABLED:
        notes["validated"]          = False
        notes["validator_attempts"] = 0
        notes["error"]              = "lc1_2_disabled"
        return out

    # ── 3. Dispatch the subagent, with validator-feedback retry ─
    extra_context = ""
    vres: Optional[ValidationResult] = None
    attempts = 0
    last_validation: Optional[PatchValidationResult] = None

    for attempt in range(max_validator_retries + 1):
        attempts = attempt + 1
        attempt_log_dir = pair_log_dir / f"attempt{attempts:02d}"
        try:
            vres = validate_eq_map_pair(
                pair_key=pair_key,
                metal_id=metal_id,
                ligand_id=ligand_id,
                request_T_C=request_T_C,
                request_I_M=request_I_M,
                purpose=purpose,
                tasks=tasks,
                screen=screen,
                pair_log_dir=attempt_log_dir,
                additional_user_context=pair_review_context,
                extra_user_context=extra_context,
                debug=_SESSION["debug"],
            )
        except Exception as exc:
            notes["validated"]          = False
            notes["validator_attempts"] = attempts
            notes["error"]              = f"subagent_exception: {exc!r}"
            out["status"]               = "failed"
            return out

        last_validation = vres.validation

        # Subagent returned a validated patch list (possibly empty).
        if vres.ok:
            break

        # Validator rejected the payload: build retry context from the
        # validator feedback so the next attempt can correct it.
        if last_validation is not None and not last_validation.ok:
            extra_context = format_errors_for_agent(last_validation)
        else:
            # Transient failure with no validator feedback to act on:
            # the agent timed out or never called finalize_patches.
            # This is a non-deterministic ReAct hiccup (not a bad input),
            # so a fresh attempt from a clean slate commonly succeeds.
            # Retry rather than give up; the loop bound caps attempts.
            extra_context = (
                "The previous attempt ended without a successful terminal "
                "commit. You MUST call `finalize_patches` before ending this "
                "attempt. For a clean pair, commit exactly "
                "`{\"patches\": []}`; do not return the payload only as "
                "prose."
            )

    notes["validator_attempts"] = attempts

    if vres is None:
        notes["error"] = "no subagent attempt completed"
        out["status"]  = "failed"
        return out

    if not vres.ok:
        notes["validated"] = False
        notes["error"]     = vres.error or "validator rejected final payload"
        notes["patches"]   = []
        out["status"]      = "partial"
        return out

    # Success path.
    notes["validated"] = True
    notes["error"]     = None
    notes["patches"]   = [copy.deepcopy(p) for p in vres.patches]
    notes["validation"] = (
        last_validation.as_dict() if last_validation is not None else None
    )

    # Persist the final patch_notes for this pair (a single audit file).
    (pair_log_dir / "patch_notes.json").write_bytes(
        json.dumps(notes, indent=2, default=str).encode("utf-8"),
    )
    return out


# ════════════════════════════════════════════════════════════════════
#  Top-level entry point
# ════════════════════════════════════════════════════════════════════

def fetch_lc1_2_eq_map_card(
    *,
    chemical_system: Dict[str, Any],
) -> Dict[str, Any]:
    """Fetch the authoritative SRD-46 seed card without reviewing it."""
    return fetch_eqmap_card(chemical_system)


def run_lc1_2(
    *,
    chemical_system: Dict[str, Any],
    purpose: str,
    tasks: str = "",
    output_dir: str | Path,
    request_T_C: float = 25.0,
    request_I_M: float = 0.1,
    max_validator_retries: int = DEFAULT_MAX_VALIDATOR_RETRIES,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
) -> Dict[str, Any]:
    """Compatibility wrapper for the legacy fetch-then-review LC1_2 path."""
    t0 = time.perf_counter()
    card = fetch_lc1_2_eq_map_card(chemical_system=chemical_system)
    return review_lc1_2_eq_map_card(
        card=card,
        purpose=purpose,
        tasks=tasks,
        output_dir=output_dir,
        request_T_C=request_T_C,
        request_I_M=request_I_M,
        max_validator_retries=max_validator_retries,
        max_parallel=max_parallel,
        _started_at=t0,
    )


def review_lc1_2_eq_map_card(
    *,
    card: Dict[str, Any],
    purpose: str,
    tasks: str = "",
    output_dir: str | Path,
    request_T_C: float = 25.0,
    request_I_M: float = 0.1,
    max_validator_retries: int = DEFAULT_MAX_VALIDATOR_RETRIES,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    pair_review_context: Optional[Dict[str, str]] = None,
    _started_at: Optional[float] = None,
) -> Dict[str, Any]:
    """Review and persist an already-fetched LC1_2 equilibrium-map card.

    Parameters
    ----------
    card
        Authoritative seed returned by :func:`fetch_lc1_2_eq_map_card`.
    purpose, tasks
        L0 audit contract; forwarded into the per-pair LLM user
        message when :data:`cfg.LC1_2_ENABLED`.
    output_dir
        Where to drop the eq-map card, manifest, and per-pair logs.
    request_T_C, request_I_M
        Reference conditions used by the deterministic screen for
        ``wide_TI_distance`` and nearest-neighbour summaries.
    max_validator_retries
        How many EXTRA subagent calls per pair when the validator
        rejects the previous payload (0 = single attempt, no retry).
        Default 2 → up to 3 attempts per pair.
    max_parallel
        ``ThreadPoolExecutor`` worker count.

    Returns
    -------
    dict
        ``{status, output_dir, eq_map_card_path, manifest_path,
        pair_results, elapsed_s}``. The augmented card at
        ``eq_map_card_path`` carries the parseable ``patch_notes``
        slot inside every ``eq_network`` entry.
    """
    t0 = _started_at if _started_at is not None else time.perf_counter()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_text = _clean_tasks(tasks)

    if _SESSION["session_dir"] is None:
        configure_lc1_2_session(session_dir=output_dir)

    # Keep the fetched coverage card immutable for the interposed caller.
    card = copy.deepcopy(card)
    pairs: List[Dict[str, Any]] = list(card.get("equilibrium_networks") or [])

    history = _SESSION["history"]
    if history is not None:
        history.log(
            "LC1_2_dispatch_start",
            n_pairs=len(pairs),
            lc1_2_enabled=cfg.LC1_2_ENABLED,
            max_validator_retries=max_validator_retries,
            max_parallel=max_parallel,
        )

    # ── 2. Per-pair workers ────────────────────────────────────────
    call_dir = _per_call_dir()
    results: List[Optional[Dict[str, Any]]] = [None] * len(pairs)

    if pairs:
        workers = max(1, min(int(max_parallel), len(pairs)))
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for idx, pair_row in enumerate(pairs):
                m_id = pair_row.get("metal_id")
                l_id = pair_row.get("ligand_id")
                pair_log_dir = call_dir / f"p{idx:02d}_m{m_id}_l{l_id}"
                fut = pool.submit(
                    _validate_one_pair,
                    pair_row=pair_row,
                    purpose=purpose,
                    tasks=tasks_text,
                    request_T_C=request_T_C,
                    request_I_M=request_I_M,
                    max_validator_retries=max_validator_retries,
                    pair_log_dir=pair_log_dir,
                    pair_review_context=(pair_review_context or {}).get(
                        f"m{m_id}_l{l_id}", "",
                    ),
                )
                futures[fut] = idx
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as exc:                       # pragma: no cover
                    pr = pairs[idx]
                    failed_notes = empty_patch_notes()
                    failed_notes["error"] = f"worker_exception: {exc!r}"
                    results[idx] = {
                        "pair_key":    f"m{pr.get('metal_id')}_l{pr.get('ligand_id')}",
                        "metal_id":    pr.get("metal_id"),
                        "ligand_id":   pr.get("ligand_id"),
                        "status":      "failed",
                        "patch_notes": failed_notes,
                    }

    # ── 3. Merge patch_notes back into the card ────────────────────
    for idx, row in enumerate(results):
        if row is None:
            continue
        pairs[idx]["patch_notes"] = row.get("patch_notes") or empty_patch_notes()

    card_path = output_dir / "lc1_2_eqmap_card.json"
    card_path.write_bytes(json.dumps(card, indent=2, default=str).encode("utf-8"))

    # ── 4. Build the manifest ──────────────────────────────────────
    rows = [r for r in results if r is not None]
    n_failed  = sum(1 for r in rows if r.get("status") == "failed")
    n_partial = sum(1 for r in rows if r.get("status") == "partial")
    n_ok      = sum(1 for r in rows if r.get("status") == "ok")
    n_with_patches = sum(
        1 for r in rows
        if (r.get("patch_notes") or {}).get("patches")
    )

    status = "ok" if (n_failed == 0 and n_partial == 0) else "partial"
    if rows and n_failed == len(rows):
        status = "failed"

    elapsed = round(time.perf_counter() - t0, 3)

    manifest = {
        "status":                status,
        "lc1_2_enabled":         bool(cfg.LC1_2_ENABLED),
        "request_T_C":           request_T_C,
        "request_I_M":           request_I_M,
        "max_validator_retries": int(max_validator_retries),
        "max_parallel":          int(max_parallel),
        "n_pairs":               len(rows),
        "n_pairs_ok":            n_ok,
        "n_pairs_partial":       n_partial,
        "n_pairs_failed":        n_failed,
        "n_pairs_with_patches":  n_with_patches,
        "pair_results":          [
            {k: v for k, v in r.items() if k != "patch_notes"}
            | {"patch_notes_summary": _patch_notes_summary(r.get("patch_notes"))}
            for r in rows
        ],
        "eq_map_card_path":      str(card_path),
        "call_dir":              str(call_dir),
        "elapsed_s":             elapsed,
    }
    manifest_path = output_dir / "LC1_2_manifest.json"
    manifest_path.write_bytes(
        json.dumps(manifest, indent=2, default=str).encode("utf-8"),
    )

    if _SESSION["stats"] is not None:
        _SESSION["stats"].incr("LC1_2", "pairs",              len(rows))
        _SESSION["stats"].incr("LC1_2", "pairs_ok",           n_ok)
        _SESSION["stats"].incr("LC1_2", "pairs_partial",      n_partial)
        _SESSION["stats"].incr("LC1_2", "pairs_failed",       n_failed)
        _SESSION["stats"].incr("LC1_2", "pairs_with_patches", n_with_patches)

    if history is not None:
        history.log(
            "LC1_2_dispatch_end",
            status=status,
            n_ok=n_ok,
            n_partial=n_partial,
            n_failed=n_failed,
            n_with_patches=n_with_patches,
            elapsed_s=elapsed,
        )

    return {
        "status":           status,
        "output_dir":       str(output_dir),
        "eq_map_card_path": str(card_path),
        "manifest_path":    str(manifest_path),
        "pair_results":     rows,
        "elapsed_s":        elapsed,
    }


def _patch_notes_summary(notes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact projection of a pair's ``patch_notes`` for the manifest."""
    if not notes:
        return {"validated": False, "n_patches": 0, "error": "missing"}
    patches = notes.get("patches") or []
    return {
        "validated":          bool(notes.get("validated")),
        "validator_attempts": int(notes.get("validator_attempts") or 0),
        "n_patches":          len(patches),
        "n_set_value":        sum(1 for p in patches
                                  if p.get("operation") == "set_value"),
        "n_drop_node":        sum(1 for p in patches
                                  if p.get("operation") == "drop_node"),
        "error":              notes.get("error"),
    }


__all__ = [
    "configure_lc1_2_session",
    "fetch_lc1_2_eq_map_card",
    "review_lc1_2_eq_map_card",
    "run_lc1_2",
    "DEFAULT_MAX_VALIDATOR_RETRIES",
    "DEFAULT_MAX_PARALLEL",
]
