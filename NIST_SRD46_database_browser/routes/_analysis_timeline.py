"""Wall-time component timeline for an analysis-agent session.

Reconstructs a Gantt-style timeline of the L0 orchestrator and its L1
sub-agents (plus each L1 call's internal build/solve + analysis phases)
from the artefacts written under a session directory:

* ``run_history.jsonl`` — authoritative absolute timestamps (``ts``),
  per-L1-call ``elapsed_s`` and ``ran_ok`` (the failure flag), plus the
  ``L0_end`` envelope (``timed_out``, ``iterations``).
* ``manifest.json`` ``tool_call_summary`` — used to detect which L1 calls
  were dispatched in the *same* L0 iteration (a parallel-dispatch batch).
* ``L1_call_NN/l1_tool_calls.md`` — the L1 sub-agent's own tool timeline,
  used to size the ``run_analysis_pipeline`` build/solve phase.
* ``L1_call_NN/LC{1,2,3}/summary/LC*_summary.json`` and
  ``L1_call_NN/LD/verdict.json`` — per-stage ``status`` / validator
  verdict, surfaced as success/failure chips.

The output is a plain dict (see :func:`build_agent_timeline`) consumed by
``templates/analysis_detail.html`` to render a CSS Gantt chart. No real
wall-clock overlap occurs in practice (the runtime serialises L1 calls),
so parallelism is conveyed via the *dispatch batch* marker rather than
overlapping bars.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from ._analysis_status import analysis_outcome
except ImportError:  # app.py also supports loading routes as top-level modules
    from _analysis_status import analysis_outcome

__all__ = ["build_agent_timeline"]


# ---------------------------------------------------------------------------
# Small IO helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out


def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fmt_secs(value: Optional[float]) -> str:
    if value is None:
        return "?"
    if value >= 60:
        m, s = divmod(int(round(value)), 60)
        return f"{m}m{s:02d}s"
    if value >= 10:
        return f"{value:.0f}s"
    return f"{value:.1f}s"


# ---------------------------------------------------------------------------
# Parse the L1 sub-agent's own tool-call table (l1_tool_calls.md)
# ---------------------------------------------------------------------------

def _parse_l1_tool_calls(md_path: Path) -> List[Dict[str, Any]]:
    """Return ``[{tool, iteration, elapsed_s}]`` from an L1 tool-call table."""
    rows: List[Dict[str, Any]] = []
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return rows
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0] in ("#", "") or re.fullmatch(r":?-+:?", cells[0]):
            continue
        try:
            iteration = int(cells[1])
        except ValueError:
            continue
        try:
            elapsed = float(cells[5])
        except ValueError:
            elapsed = 0.0
        rows.append({"tool": cells[2], "iteration": iteration, "elapsed_s": elapsed})
    return rows


def _pipeline_elapsed(l1_rows: List[Dict[str, Any]]) -> float:
    """Total wall time spent in ``run_analysis_pipeline`` (the build+solve)."""
    return sum(r["elapsed_s"] for r in l1_rows if r["tool"] == "run_analysis_pipeline")


# ---------------------------------------------------------------------------
# Per-L1-call sub-stage status (LC1/LC2/LC3 build stages + LD validator)
# ---------------------------------------------------------------------------

_LD_STATUS = {
    "supported": "ok",
    "contradicted": "fail",
    "inconclusive": "warn",
}


def _stage_chips(call_dir: Path) -> List[Dict[str, str]]:
    """Build the ordered status chips for one L1 call's sub-components."""
    chips: List[Dict[str, str]] = []
    for lc in ("LC1", "LC2", "LC3"):
        summary = call_dir / lc / "summary" / f"{lc}_summary.json"
        doc = _read_json(summary) if summary.exists() else None
        if doc is None:
            # stage directory exists but no summary => did not complete
            status = "fail" if (call_dir / lc).exists() else "missing"
        else:
            raw = str(doc.get("status", "")).lower()
            status = "ok" if raw in ("ok", "success", "succeeded") else "fail"
        if status != "missing":
            chips.append({"name": lc, "status": status})
    ld_doc = _read_json(call_dir / "LD" / "verdict.json")
    if ld_doc is not None:
        verdict = str(ld_doc.get("verdict") or "").lower()
        chips.append({"name": "LD", "status": _LD_STATUS.get(verdict, "warn")})
    return chips


def _worst_build_status(chips: List[Dict[str, str]]) -> str:
    build = [c["status"] for c in chips if c["name"].startswith("LC")]
    if not build:
        return "ok"
    return "fail" if "fail" in build else "ok"


# ---------------------------------------------------------------------------
# Purpose -> short system label  (e.g. "Compute ... for Cu in 0.1 M ...")
# ---------------------------------------------------------------------------

def _short_purpose(purpose: str) -> str:
    if not purpose:
        return ""
    m = re.search(r"\bfor\s+([A-Z][A-Za-z0-9()/+\- ]{0,40}?)\s+(?:in|at|with|over|across|under)\b", purpose)
    if m:
        return m.group(1).strip()
    return (purpose[:36] + "…") if len(purpose) > 38 else purpose


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_agent_timeline(sdir: Path) -> Optional[Dict[str, Any]]:
    """Construct the wall-time timeline view-model for a session.

    Returns ``None`` when there is insufficient timing data to draw a
    meaningful chart.
    """
    events = _read_jsonl(sdir / "run_history.jsonl")
    if not events:
        return None

    l0_start = next((e for e in events if e.get("event") == "L0_start"), None)
    l0_end = next((e for e in events if e.get("event") == "L0_end"), None)
    if l0_start is None:
        return None
    t0 = float(l0_start["ts"])

    # L1 lifecycle: pair starts with ends by call index.
    starts = {e["call"]: e for e in events if e.get("event") == "L1_start"}
    ends = {e["call"]: e for e in events if e.get("event") == "L1_end"}

    # Total wall time: prefer the L0_end envelope; else span to last activity.
    last_ts = t0
    for e in events:
        try:
            last_ts = max(last_ts, float(e["ts"]))
        except Exception:
            continue
    if l0_end is not None and isinstance(l0_end.get("elapsed_s"), (int, float)):
        total = float(l0_end["elapsed_s"])
    else:
        total = max(last_ts - t0, 0.0)
    if total <= 0:
        return None

    complete = l0_end is not None
    manifest = _read_json(sdir / "manifest.json") or {}
    completion = {**manifest, **(l0_end or {})}
    outcome = analysis_outcome(completion)
    limited = outcome["limited"]
    limit_label = outcome["stop_label"]
    timed_out = bool(completion.get("timed_out"))

    # Which L1 calls were dispatched together in one L0 iteration?
    iterations = int((l0_end or {}).get("iterations")
                     or manifest.get("iterations") or 0)
    dispatch_iter: Dict[int, int] = {}
    counter = 0
    for tc in manifest.get("tool_call_summary") or []:
        if tc.get("tool") == "dispatch_l1_pipeline":
            counter += 1
            dispatch_iter[counter] = tc.get("iteration")
    batch_size: Dict[int, int] = {}
    for it in dispatch_iter.values():
        batch_size[it] = batch_size.get(it, 0) + 1

    def _pct(seconds: float) -> float:
        return max(0.0, min(100.0, seconds / total * 100.0))

    rows: List[Dict[str, Any]] = []

    # Row 0 — L0 orchestrator envelope.
    n_l1 = len(starts)
    n_fail = sum(1 for c, e in ends.items() if not e.get("ran_ok", True))
    rows.append({
        "depth": 0,
        "kind": "l0",
        "label": "L0 orchestrator",
        "sublabel": f"{_fmt_secs(total)} · {iterations} iters · {n_l1} L1 call(s)"
                    + (f" · {n_fail} failed" if n_fail else ""),
        "start_pct": 0.0,
        "width_pct": 100.0,
        "status": "warn" if limited else "ok",
        "parallel": False,
        "stages": [],
        "title": "L0 orchestrator wall time"
                 + (f" — stopped: {limit_label}" if limited else ""),
    })

    # Pre-L1 planning phase (t0 -> first L1 start).
    ordered_calls = sorted(starts.keys(), key=lambda c: float(starts[c]["ts"]))
    if ordered_calls:
        first_start = float(starts[ordered_calls[0]]["ts"]) - t0
        if first_start > 2.0:
            rows.append({
                "depth": 1, "kind": "l0phase",
                "label": "L0 plan & dispatch",
                "sublabel": _fmt_secs(first_start),
                "start_pct": 0.0, "width_pct": _pct(first_start),
                "status": "neutral", "parallel": False, "stages": [],
                "title": "Orchestrator planning before the first L1 dispatch",
            })

    last_end_off = 0.0
    for call in ordered_calls:
        s_ev = starts[call]
        e_ev = ends.get(call)
        s_off = float(s_ev["ts"]) - t0
        incomplete = False
        if e_ev is not None:
            e_off = float(e_ev["ts"]) - t0
            elapsed = e_ev.get("elapsed_s")
            ran_ok = bool(e_ev.get("ran_ok", True))
            attempts = e_ev.get("attempts")
        else:  # start without a recorded end => the run was cut off here
            e_off = total
            elapsed = e_off - s_off
            # No L0_end either => whole session was interrupted (unknown), not
            # a genuine pipeline failure; flag as incomplete instead.
            incomplete = not complete
            ran_ok = complete  # if the run DID finish, a missing end is anomalous
            attempts = None
        last_end_off = max(last_end_off, e_off)
        span = max(e_off - s_off, 0.0)

        it = dispatch_iter.get(call)
        in_batch = bool(it is not None and batch_size.get(it, 0) > 1)
        call_dir = sdir / f"L1_call_{call:02d}"
        chips = _stage_chips(call_dir) if call_dir.exists() else []

        row_status = "warn" if incomplete else ("ok" if ran_ok else "fail")
        sub = "" if elapsed is None else _fmt_secs(float(elapsed))
        if attempts and attempts != 1:
            sub += f" · {attempts} attempts"
        if incomplete:
            sub += " · INCOMPLETE"
        elif not ran_ok:
            sub += " · FAILED"
        rows.append({
            "depth": 1, "kind": "l1",
            "label": f"L1 call {call}" + (f" · {_short_purpose(s_ev.get('purpose',''))}"
                                          if s_ev.get("purpose") else ""),
            "sublabel": sub,
            "start_pct": _pct(s_off), "width_pct": max(_pct(span), 0.4),
            "status": row_status,
            "parallel": in_batch,
            "stages": chips,
            "title": s_ev.get("purpose", "") or f"L1 call {call}",
        })

        # L1 internal phases: build & solve (run_analysis_pipeline) then the
        # read-outputs + write-analysis tail (which also absorbs model time).
        l1_rows = _parse_l1_tool_calls(call_dir / "l1_tool_calls.md")
        pipe = _pipeline_elapsed(l1_rows)
        if pipe > 0 and pipe <= span + 1.0:
            build_status = _worst_build_status(chips)
            rows.append({
                "depth": 2, "kind": "l1sub",
                "label": "build & solve",
                "sublabel": _fmt_secs(pipe),
                "start_pct": _pct(s_off), "width_pct": max(_pct(pipe), 0.4),
                "status": build_status, "parallel": False, "stages": [],
                "title": "run_analysis_pipeline: eq-card align → free-energy "
                         "card → solver-param card → numeric solve",
            })
            tail = span - pipe
            if tail > 2.0:
                rows.append({
                    "depth": 2, "kind": "l1sub",
                    "label": "read & write analysis",
                    "sublabel": _fmt_secs(tail),
                    "start_pct": _pct(s_off + pipe), "width_pct": max(_pct(tail), 0.4),
                    "status": "ok" if ran_ok else "warn",
                    "parallel": False, "stages": [],
                    "title": "L1 reads solver outputs and composes its analysis "
                             "(includes model reasoning time)",
                })
        elif span > 0:
            if incomplete:
                sub_label, sub_title = "incomplete (no end recorded)", \
                    "This L1 call started but the session was interrupted before it finished"
            elif ran_ok:
                sub_label, sub_title = "reasoning", "No run_analysis_pipeline recorded for this call"
            else:
                sub_label, sub_title = "failed / refused early", "No run_analysis_pipeline recorded for this call"
            rows.append({
                "depth": 2, "kind": "l1sub",
                "label": sub_label,
                "sublabel": _fmt_secs(span),
                "start_pct": _pct(s_off), "width_pct": max(_pct(span), 0.4),
                "status": row_status,
                "parallel": False, "stages": [],
                "title": sub_title,
            })

    # Post-L1 synthesis tail (last L1 end -> total).
    if ordered_calls:
        tail = total - last_end_off
        if tail > 2.0:
            rows.append({
                "depth": 1, "kind": "l0phase",
                "label": "L0 read results & compose answer",
                "sublabel": _fmt_secs(tail),
                "start_pct": _pct(last_end_off), "width_pct": _pct(tail),
                "status": "warn" if limited else "neutral",
                "parallel": False, "stages": [],
                "title": "Orchestrator reads L1 reports and writes the final answer"
                         + (f" — stopped: {limit_label}" if limited else ""),
            })

    # Axis tick marks (0, 25, 50, 75, 100 % of wall time).
    axis = [{"pct": p, "label": _fmt_secs(total * p / 100.0)} for p in (0, 25, 50, 75, 100)]

    started_iso = None
    try:
        started_iso = datetime.fromtimestamp(t0).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    # Distinct parallel-dispatch batches (for the caption).
    parallel_batches = sum(1 for it, n in batch_size.items() if n > 1)

    return {
        "total_s": total,
        "total_label": _fmt_secs(total),
        "started_iso": started_iso,
        "complete": complete,
        "timed_out": timed_out,
        "limited": limited,
        "limit_label": limit_label,
        "iterations": iterations,
        "n_l1": n_l1,
        "n_l1_failed": n_fail,
        "parallel_batches": parallel_batches,
        "rows": rows,
        "axis": axis,
    }
