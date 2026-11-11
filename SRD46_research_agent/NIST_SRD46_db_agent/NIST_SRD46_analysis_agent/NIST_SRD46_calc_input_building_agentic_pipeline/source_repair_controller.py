"""Bounded LC2→LC1 repair, preserving the original brief and card revisions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable


def repair_policy() -> dict:
    from SRD46_analysis_argo_config import AGENT_CONFIG as config
    return {
        "contract": "source-repair/v1",
        "enabled": bool(getattr(config, "SOURCE_REPAIR_ENABLED", True)),
        "max_rounds": max(0, int(getattr(config, "SOURCE_REPAIR_MAX_ROUNDS", 2))),
    }


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _selection_sha(lc1: dict) -> str:
    # Ignore reviewer prose and file locations; reject unchanged scientific input.
    value = json.loads(Path(lc1["eq_map_card_path"]).read_text(encoding="utf-8-sig"))
    def strip(item):
        if isinstance(item, list):
            return [strip(v) for v in item]
        if isinstance(item, dict):
            return {k: strip(v) for k, v in item.items() if k not in {
                "rationale", "reason", "notes", "created_at", "timestamp", "report_path",
                "validation_report_path", "source_repair_report_path",
            }}
        return item
    return hashlib.sha256(json.dumps(strip(value), sort_keys=True).encode()).hexdigest()


def _issue_key(diagnostic: dict) -> str:
    pairs = diagnostic.get("pair_keys") or [diagnostic.get("pair_key", "unknown")]
    return str(diagnostic.get("issue_key") or ",".join(sorted(map(str, pairs))))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def repair_failed_lc2(
    *, lc1: dict, lc2: dict, purpose: str, tasks: str, output_dir,
    run_lc2: Callable, request_T_C: float = 25.0, request_I_M: float = 0.1,
    debug: bool = False, repair_selection: Callable | None = None,
    repair_delta: Callable | None = None, policy: dict | None = None,
) -> tuple[dict, dict, dict]:
    """Repair typed source errors only; an ordinary stage error is returned intact.

    An existing deduplicated card uses the delta path. Early compiler failures
    have no decisions to reuse and enter LC2 normally after source repair.
    """
    policy = policy or repair_policy()
    root = Path(output_dir)
    receipt = {"policy": policy, "attempts": [], "status": "not_needed"}
    if not policy["enabled"] or lc2.get("status") != "source_repair_required":
        return lc1, lc2, receipt
    if repair_selection is None:
        from .LC1_SRD46_eq_card_alignment.source_repair import repair_lc1_selection
        repair_selection = repair_lc1_selection
    if repair_delta is None:
        from .repair_support import repair_lc2_from_delta
        repair_delta = repair_lc2_from_delta

    catalog_sha = _sha(lc1["system_catalog_path"])
    counts = dict(lc1.get("source_repair_attempts_by_issue") or {})
    seen = {_selection_sha(lc1)}
    prior_attempts = 0
    # Persisted requests consume their attempt even if a process stopped before
    # the API response was saved. Never buy extra calls by restarting a process.
    for request_path in root.glob("attempt_*/request.json"):
        try:
            saved = json.loads(request_path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict) or not isinstance(saved.get("attempts_by_issue", {}), dict):
                raise ValueError("Invalid persisted repair request structure")
            if any(type(value) is not int or value < 0 for value in saved.get("attempts_by_issue", {}).values()):
                raise ValueError("Invalid persisted repair attempt count")
        except (OSError, ValueError) as exc:
            receipt.update(status="invalid_prior_repair_receipt", path=str(request_path),
                           reason=f"{type(exc).__name__}: {exc}")
            _write(root / "repair_receipt.json", receipt)
            return lc1, lc2, receipt
        for key, count in (saved.get("attempts_by_issue") or {}).items():
            counts[key] = max(int(counts.get(key, 0)), int(count))
        if any(saved.get(key, value) != value for key, value in (("purpose", purpose), ("tasks", tasks))):
            receipt.update(status="prior_repair_scope_mismatch", path=str(request_path))
            _write(root / "repair_receipt.json", receipt)
            return lc1, lc2, receipt
        prior_attempts += 1
        prior_result_path = request_path.with_name("lc1_result.json")
        if prior_result_path.exists():
            try:
                prior_result = json.loads(prior_result_path.read_text(encoding="utf-8"))
                if prior_result.get("status") == "ok":
                    seen.add(_selection_sha(prior_result))
            except (OSError, ValueError, KeyError) as exc:
                receipt.update(status="invalid_prior_repair_result", path=str(prior_result_path),
                               reason=f"{type(exc).__name__}: {exc}")
                _write(root / "repair_receipt.json", receipt)
                return lc1, lc2, receipt
    # The per-issue limit is supplemented by an overall limit: changing error
    # names cannot create an unbounded chain of API calls.
    max_total = max(1, policy["max_rounds"] * 4)
    for index in range(max(0, max_total - prior_attempts)):
        if lc2.get("status") != "source_repair_required":
            break
        diagnostic = dict(lc2.get("source_repair") or {})
        if not diagnostic or diagnostic.get("repair_scope", "source_selection") != "source_selection":
            receipt["status"] = "needs_broader_review"
            break
        issue = _issue_key(diagnostic)
        if int(counts.get(issue, 0)) >= policy["max_rounds"]:
            receipt["status"] = "repair_limit_reached"
            break
        counts[issue] = int(counts.get(issue, 0)) + 1
        attempt_dir = root / f"attempt_{index + 1:02d}"
        # A resumed controller never overwrites an earlier repair attempt.
        while attempt_dir.exists():
            index += 1
            attempt_dir = root / f"attempt_{index + 1:02d}"
        attempt_dir.mkdir(parents=True)
        _write(attempt_dir / "request.json", {
            "purpose": purpose, "tasks": tasks, "diagnostic": diagnostic,
            "previous_lc1": lc1, "previous_lc2": lc2,
            "request_T_C": request_T_C, "request_I_M": request_I_M,
            "attempts_by_issue": counts,
        })
        revised = repair_selection(
            previous_lc1=lc1, diagnostic=diagnostic, purpose=purpose, tasks=tasks,
            output_dir=attempt_dir / "LC1", request_T_C=request_T_C,
            request_I_M=request_I_M, max_rounds=1,
        )
        record = {"issue_key": issue, "folder": str(attempt_dir),
                  "source_status": revised.get("status")}
        receipt["attempts"].append(record)
        _write(attempt_dir / "lc1_result.json", revised)
        for key, count in (revised.get("source_repair_attempts_by_issue") or {}).items():
            counts[key] = max(int(counts.get(key, 0)), int(count))
        if revised.get("status") != "ok":
            receipt["status"] = "source_repair_unresolved"
            receipt["last_source_result"] = revised
            break
        if _sha(revised.get("system_catalog_path") or lc1["system_catalog_path"]) != catalog_sha:
            receipt["status"] = "needs_broader_review"
            receipt["reason"] = "Source repair changed the system catalog."
            break
        selected_sha = _selection_sha(revised)
        if selected_sha in seen:
            receipt["status"] = "unchanged_or_repeated_selection"
            break
        seen.add(selected_sha)
        revised["system_catalog_path"] = lc1["system_catalog_path"]
        revised["source_repair_attempts_by_issue"] = dict(counts)
        dedup = lc2.get("lc2_3") or {}
        has_decisions = bool(lc2.get("dedup_result") or dedup.get("final_committed") or
                             (dedup.get("source_repair_pending") and dedup.get("accepted_decision_overlay_path")) or
                             lc2.get("final_card_path"))
        if has_decisions:
            next_lc2 = repair_delta(
                previous_lc2=lc2, previous_lc1=lc1, revised_lc1=revised,
                diagnostic=diagnostic, purpose=purpose, tasks=tasks,
                output_dir=attempt_dir / "LC2", debug=debug,
            )
            record["mode"] = "existing_card_delta"
        else:
            extras = {key: revised[key] for key in (
                "support_eq_map_path", "session_working_map_path",
            ) if revised.get(key) is not None}
            for source, target in (
                ("support_session_id", "expected_support_session_id"),
                ("support_eq_map_sha256", "expected_support_eq_map_sha256"),
                ("session_working_map_sha256", "expected_session_working_map_sha256"),
            ):
                if revised.get(source) is not None:
                    extras[target] = revised[source]
            next_lc2 = run_lc2(
                purpose, tasks, system_catalog_path=revised["system_catalog_path"],
                lc1_2_eqmap_card_path=revised["eq_map_card_path"],
                output_dir=attempt_dir / "LC2", debug=debug, **extras,
            )
            record["mode"] = "first_card_build"
        lc1, lc2 = revised, next_lc2
        record["lc2_status"] = lc2.get("status")
        _write(attempt_dir / "lc2_result.json", lc2)
        receipt["status"] = "ok" if lc2.get("status") == "ok" else "unresolved"
        _write(root / "repair_receipt.json", receipt)
    else:
        receipt["status"] = "total_repair_limit_reached"
    receipt["attempts_by_issue"] = counts
    lc1["source_repair_attempts_by_issue"] = dict(counts)
    _write(root / "repair_receipt.json", receipt)
    return lc1, lc2, receipt
