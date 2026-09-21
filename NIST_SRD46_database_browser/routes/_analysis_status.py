"""Display L0 completion separately from scientific or execution failures.

Historical L0 ``timed_out`` flags cover both time and iteration exhaustion.
Only explicit reason fields distinguish them; an iteration count alone is
not proof that a limit stopped a run. LD review flags have different semantics
and must not be passed to this L0 classifier.
"""
from __future__ import annotations

from collections.abc import Mapping

_TIME = {"timeout", "time_limit", "time_limit_reached", "time_budget",
         "time_budget_exhausted", "deadline", "deadline_exceeded",
         "reasoning_timeout", "reasoning_time_limit", "wall_timeout"}
_ITERATION = {"iteration_limit", "iteration_limit_reached", "iteration_cap",
              "iteration_budget", "iteration_budget_exhausted", "max_iterations",
              "max_iterations_reached", "max_turns", "max_turns_reached", "turn_limit"}
_BUDGET = {"budget_limit", "limit_reached", "budget_exhausted",
           "iteration_or_time_limit_reached", "timed_out"}
_LABELS = {"time_limit": "time limit reached", "iteration_limit": "iteration limit reached",
           "budget_limit": "time / iteration limit reached"}
_BADGES = {"pass": "success", "supported": "success", "partial": "warning",
           "skipped_some": "warning", "fail": "danger", "failed": "danger",
           "error": "danger", "contradicted": "danger", "inconclusive": "secondary"}


def _record(value):
    return value if isinstance(value, Mapping) else {}


def _token(value):
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def completion_stop_reason(document) -> str:
    """Return the recorded L0 resource stop, without inferring it from counters."""
    document = _record(document)
    for key in ("stop_reason", "termination_reason", "completion_status", "reason"):
        reason = _token(document.get(key))
        if reason in _TIME:
            return "time_limit"
        if reason in _ITERATION:
            return "iteration_limit"
        if reason in _BUDGET:
            return "budget_limit"
    if any(document.get(key) is True for key in
           ("iteration_limit_reached", "max_iterations_reached")):
        return "iteration_limit"
    if document.get("timed_out") is True:
        return "budget_limit"
    return ""


def analysis_outcome(manifest=None, verdict=None) -> dict:
    """Build one browser outcome; retain the recorded verdict for diagnostics."""
    manifest = _record(manifest)
    document = _record(verdict)
    nested = document.get("verdict")
    if isinstance(nested, Mapping):
        document = nested
    raw = _token(document.get("verdict") if isinstance(verdict, Mapping) else verdict) or "unknown"
    stops = [completion_stop_reason(source) for source in
             (manifest, document, document.get("manifest"))]
    stop = next((value for value in stops if value and value != "budget_limit"),
                next((value for value in stops if value), ""))
    reason = _token(document.get("reason"))
    # A real exception or an independently recorded failure stays visible even
    # if a budget was also reached. The old timed_out failure gate is excluded.
    error = manifest.get("error") or document.get("error")
    independent_failure = raw == "contradicted" or (
        raw in {"fail", "failed"} and bool(reason)
        and reason not in (_TIME | _ITERATION | _BUDGET))
    if error:
        status, label = "error", "error"
    elif stop and not independent_failure and raw != "error":
        status, label = "stopped", "stopped"
    else:
        status = raw
        label = raw.replace("_", " ")
    return {
        "status": status, "label": label,
        "badge": "warning" if status == "stopped" else _BADGES.get(status, "secondary"),
        "limited": bool(stop), "stop_reason": stop, "stop_label": _LABELS.get(stop, ""),
        "recorded_verdict": raw,
    }


def batch_outcomes(batch):
    """Recount historical batch rows for display without rewriting artifacts."""
    if not isinstance(batch, Mapping):
        return None
    rows = batch.get("results")
    if not isinstance(rows, list):
        # Aggregate-only files cannot distinguish old timeout failures.
        return {**batch, "totals": None}
    totals = dict.fromkeys(("pass", "partial", "fail", "error", "stopped", "unknown", "n"), 0)
    for row in rows:
        row = _record(row)
        status = analysis_outcome(row, row)["status"]
        category = {"supported": "pass", "skipped_some": "partial",
                    "inconclusive": "partial", "failed": "fail", "contradicted": "fail"}.get(status, status)
        totals[category if category in totals and category != "n" else "unknown"] += 1
        totals["n"] += 1
    return {**batch, "totals": totals}
