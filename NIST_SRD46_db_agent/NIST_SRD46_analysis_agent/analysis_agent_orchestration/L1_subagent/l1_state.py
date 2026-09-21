"""Session and per-call state primitives for the L1 analysis agent.

This module deliberately contains no agent-engine or solver imports.  It is
the small shared dependency used by the L1 tool, artifact, audit, and runner
modules, which keeps those modules acyclic while preserving the process-wide
session contract exposed by :mod:`l1_subagent`.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_SESSION: Dict[str, Any] = {
    "session_dir": None,
    "history": None,
    "stats": None,
    "working_memory": None,
    "debug": False,
    "estimate_missing_equilibria": False,
    "forward_explicit_estimation_disable": False,
    "call_index": 0,
    "claimed_call_indices": set(),
    "_lock": threading.Lock(),
}


@dataclass
class _L1State:
    """Mutable state shared by the tools belonging to one L1 call."""

    purpose: str
    tasks_text: str
    call_dir: Path
    idx: int
    debug: bool = False
    estimate_missing_equilibria: bool = False
    forward_explicit_estimation_disable: bool = False
    # Pipeline run results (populated by run_analysis_pipeline).
    ran_ok: bool = False
    pipeline_status: Optional[Dict[str, Any]] = None
    solver_dir: Optional[Path] = None
    calc_input_card_path: Optional[Path] = None
    model_coverage: Optional[Dict[str, Any]] = None
    topology_summary: Optional[Dict[str, Any]] = None
    # Canonical sweep methods whose briefing already sits in the system
    # prompt; the pipeline result then points at it instead of repeating it.
    briefed_methods: List[str] = field(default_factory=list)
    # Deterministic solver verdicts are injected automatically in the
    # run_analysis_pipeline tool result. ``full`` is the only normal mode;
    # ``api_error_fallback`` is entered once, and only after Argo explicitly
    # rejects the full prompt as too large.
    default_verdicts: List[tuple[Path, str]] = field(default_factory=list)
    default_reference_constants: Optional[tuple[Path, str]] = None
    verdict_delivery_mode: str = "full"
    verdict_api_retry_used: bool = False
    verdict_api_retry_error: Optional[str] = None
    # Terminal commit (populated by record_analysis).
    committed_report: Optional[str] = None
    agent_committed_report: bool = False
    # Long reports are staged in small, ordered tool calls before the terminal
    # commit.  Keeping the chunks in state avoids forcing one JSON argument to
    # fit inside a single model response (and therefore inside its token cap).
    analysis_draft_chunks: List[str] = field(default_factory=list)
    analysis_draft_generation: int = 0
    last_ld_verdict: Optional[Dict[str, Any]] = None
    artifacts: List[str] = field(default_factory=list)


def configure_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    resolved_estimation_default: bool = False,
) -> None:
    """Bind the process-wide L1 side-channel.

    ``resolved_estimation_default`` is injected by the public facade so this
    state-only module does not import the analysis configuration layer.
    """

    _SESSION["session_dir"] = Path(session_dir)
    _SESSION["history"] = history
    _SESSION["stats"] = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"] = bool(debug)
    _SESSION["estimate_missing_equilibria"] = bool(
        estimate_missing_equilibria
    )
    _SESSION["forward_explicit_estimation_disable"] = (
        estimate_missing_equilibria is False
        and bool(resolved_estimation_default)
    )
    _SESSION["call_index"] = 0
    _SESSION["claimed_call_indices"] = set()


def _read_call_input(path: Path) -> Optional[Dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "purpose": str(payload.get("purpose") or "").strip(),
        "tasks": str(payload.get("tasks") or "").strip(),
    }


def _per_call_dir(
    purpose: Optional[str] = None,
    tasks_text: Optional[str] = None,
) -> Path:
    """Reserve an existing matching call directory or a fresh one.

    A process restart resets the in-memory call counter.  Matching the exact
    persisted brief first lets a restarted L0 redispatch idempotently into the
    interrupted L1 directory instead of silently creating or overwriting an
    unrelated call.
    """

    base = _SESSION["session_dir"] or (Path.cwd() / "_l1_adhoc")
    base = Path(base)
    expected = None
    if purpose is not None or tasks_text is not None:
        expected = {
            "purpose": str(purpose or "").strip(),
            "tasks": str(tasks_text or "").strip(),
        }
    with _SESSION["_lock"]:
        claimed = _SESSION.setdefault("claimed_call_indices", set())
        existing: list[tuple[int, Path]] = []
        for path in base.glob("L1_call_*"):
            if not path.is_dir():
                continue
            try:
                idx = int(path.name.rsplit("_", 1)[-1])
            except (TypeError, ValueError):
                continue
            existing.append((idx, path))
        if expected is not None:
            for idx, path in sorted(existing):
                if idx in claimed:
                    continue
                if _read_call_input(path / "input.json") == expected:
                    claimed.add(idx)
                    _SESSION["call_index"] = idx
                    return path
        idx = max([row[0] for row in existing] + [0]) + 1
        while idx in claimed:
            idx += 1
        claimed.add(idx)
        _SESSION["call_index"] = idx
    out = base / f"L1_call_{idx:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _clean_tasks(tasks: Any) -> str:
    """Return the free-text tasks brief verbatim except outer whitespace."""

    if tasks is None:
        return ""
    return str(tasks).strip()


def _build_user_message(purpose: str, tasks: str, hint: str = "") -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    msg = f"[Purpose: {purpose}]\n[Tasks:\n{body}\n]"
    if hint:
        msg += (
            "\n\n[Reviewer feedback — your previous analysis was flagged. "
            "Re-read the output files and correct it:\n" + hint + "\n]"
        )
    return msg


def _rel_to_session(path: Path) -> str:
    """Return a path relative to the configured session root when possible."""

    session_dir = _SESSION["session_dir"]
    try:
        if session_dir is not None:
            return path.resolve().relative_to(Path(session_dir).resolve()).as_posix()
    except Exception:
        pass
    return path.as_posix()


def _rel_path_under(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _rel_to_call(state: _L1State, path: Path) -> str:
    return _rel_path_under(path, Path(state.call_dir))


def _wm_append(key: str, value: Any) -> None:
    working_memory = _SESSION.get("working_memory")
    if working_memory is None:
        return
    try:
        working_memory.append(key, value)
    except Exception:  # pragma: no cover - bookkeeping must not break a run
        try:
            working_memory.set(key, [value])
        except Exception:
            pass


def _stat_incr(phase: str, key: str) -> None:
    stats = _SESSION.get("stats")
    if stats is None:
        return
    try:
        stats.incr(f"L1_{phase}", key)
    except Exception:  # pragma: no cover
        pass


__all__ = ["_L1State", "_SESSION", "configure_session"]
