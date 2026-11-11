"""
Verdict hook — post-run scientific review of an analysis session.

Default deterministic implementation re-reads ``manifest.json`` and
flags any phase that did not reach status ``complete``. An LLM-based
verdict runner can be plugged in later by replacing
``run_verdict``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("Analysis.Verdict")


def run_verdict(session_dir: str | Path) -> Dict[str, Any]:
    """Read ``manifest.json`` and report completion with per-phase notes."""
    session_dir = Path(session_dir)
    manifest_path = session_dir / "manifest.json"
    if not manifest_path.exists():
        return {"verdict": "fail", "reason": "no_manifest", "notes": []}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"verdict": "fail", "reason": f"manifest_load_error:{exc!r}",
                "notes": []}

    if bool(manifest.get("timed_out")):
        return {
            # The shared engine also uses this flag for the iteration cap.
            # Reaching either resource limit leaves a partial run; it is not
            # evidence that the analysis failed or passed scientific review.
            "verdict": "partial",
            "reason": "timed_out",
            "timed_out": True,
            "notes": [
                "l0_orchestration:incomplete:iteration_or_time_limit_reached"
            ],
            "manifest": manifest,
        }

    notes: List[str] = []
    failed: List[str] = []
    for pid, info in (manifest.get("phases") or {}).items():
        status = info.get("status")
        if status == "complete":
            continue
        notes.append(f"{pid}:{status}:{info.get('skipped_reason') or info.get('ld_verdict','')}")
        if status == "incomplete":
            failed.append(pid)

    if failed:
        return {"verdict": "partial", "failed_phases": failed,
                "notes": notes, "manifest": manifest}
    if notes:
        return {"verdict": "skipped_some", "notes": notes,
                "manifest": manifest}
    return {"verdict": "pass", "notes": [], "manifest": manifest}


def save_final_context(session_dir: str | Path,
                       verdict: Dict[str, Any]) -> Path:
    out = Path(session_dir) / "verdict.json"
    out.write_text(json.dumps(verdict, indent=2, default=str), encoding="utf-8")
    return out


__all__ = ["run_verdict", "save_final_context"]
