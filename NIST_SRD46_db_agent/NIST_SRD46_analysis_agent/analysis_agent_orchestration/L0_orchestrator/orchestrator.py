"""
L0 orchestrator — LLM-driven top-level reasoner for the SRD-46
analysis agent.

Replaces the previous deterministic "L0 reasoner" (which was actually
just a checkpoint dispatcher and is now demoted to the L1 sub-agent
internals). This module is the *real* L0:

* Parses ``L0_orchestrator_workflow.md`` for the system prompt.
* Builds a tool registry whose only meaningful entry is
  :func:`~..L1_subagent.dispatch_l1_pipeline`. The L0 LLM cannot call
  the deterministic pipeline directly — it must go through the L1
  subagent with ``purpose`` and ``tasks`` fields.
* Drives the shared ReAct engine (:func:`agent_turn`).
* Persists ``answer.md``, ``run_history.md``, and ``run_stats.md`` next
  to ``manifest.json``.

Public API
----------
run(user_request, *, session_dir, debug=False) -> dict
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Shared engine
from ....general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
    AgentTurnResult,
)
from ....general_db_query_engine.general_checkpointing import (
    atomic_write_json,
    atomic_write_text,
    file_sha256,
    identity_sha256,
)
from ....general_db_query_engine.general_subagent_skill_schema_and_parser import (
    parse_workflow,
)
from ....general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)

# SRD-46 analysis client
from ...analysis_agent_argo_engine.argo_client import SRD46AnalysisClient
from ...SRD46_analysis_argo_config import (
    AGENT_CONFIG as cfg,
    resolve_estimate_missing_equilibria,
)

# L1 sub-agent (the only thing L0 can call into the pipeline)
from ..L1_subagent import dispatch_l1_pipeline, configure_l1_session

# Hooks
from ...analysis_agent_context_hooks import (
    AnalysisHistoryRecorder,
    AnalysisStatsRecorder,
    AnalysisWorkingMemory,
    run_verdict,
    save_final_context,
)
# Raw-LLM-context persistence (distinct from the verdict-json writer above)
from ....general_db_query_engine.general_hooks_management_helpers.general_context_hooks.postjob_verdict_hooks import (
    save_final_context as _save_llm_final_context,
)

# Engine-level hook bindings — needed so ``agent_turn`` finds handlers
# for SYNC_TOOL_CALLS_MEMORY_COMPACT etc.  These are built from the
# analysis agent's own context-hooks package (self-contained: only the
# shared ``general_db_query_engine`` is used under the hood — no
# dependency on the sibling query agent).  The analysis-tier guidance
# hooks list is empty because none of the query-tool-specific guidance
# applies to ``dispatch_l1_pipeline``.
from ...analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)

log = logging.getLogger("Analysis.L0")

_HERE = Path(__file__).absolute().parent
_WORKFLOW_PATH = _HERE / "L0_orchestrator_workflow.md"
_ESTIMATION_STATUS_PROMPT_PATH = _HERE / "estimated_equilibrium_status_prompt.md"


def _read_json_dict(path: Path) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _l0_resume_identity(
    user_request: str,
    *,
    estimate_missing_equilibria: bool,
) -> Dict[str, Any]:
    return {
        "contract": "l0-analysis-resume/v1",
        "user_request": str(user_request),
        "estimate_missing_equilibria": bool(estimate_missing_equilibria),
    }


def _prepare_l0_resume(
    session_dir: Path,
    identity: Dict[str, Any],
    *,
    resume: bool,
) -> bool:
    """Bind a reusable directory to one exact top-level request.

    Returns true when durable work from an earlier process exists.  A prompt
    mismatch fails closed instead of mixing two analyses in one directory.
    """

    checkpoint_dir = session_dir / "_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    identity_path = checkpoint_dir / "l0_run_identity.json"
    expected_sha256 = identity_sha256(identity)
    existing = _read_json_dict(identity_path)
    had_work = any(session_dir.glob("L1_call_*"))
    if existing is not None:
        existing_sha256 = str(existing.get("identity_sha256") or "")
        if existing_sha256 != expected_sha256:
            raise ValueError(
                "session_dir already belongs to a different L0 request; "
                "use a fresh directory"
            )
        had_work = True
    if resume and existing is None:
        atomic_write_json(identity_path, {
            "schema_version": "l0_run_identity.v1",
            "identity": identity,
            "identity_sha256": expected_sha256,
        })
    atomic_write_json(checkpoint_dir / "l0_resume_status.json", {
        "schema_version": "l0_resume_status.v1",
        "status": "running",
        "identity_sha256": expected_sha256,
        "pid": os.getpid(),
        "started_or_resumed_at": time.time(),
        "prior_durable_work_detected": bool(had_work and resume),
    })
    return bool(had_work and resume)


def _completed_l1_report(call_dir: Path) -> Optional[str]:
    report_path = call_dir / "l1_report.md"
    report_status = _read_json_dict(call_dir / "l1_report_status.json")
    pipeline_status = _read_json_dict(call_dir / "pipeline_status.json")
    if not (
        report_path.is_file()
        and report_status
        and pipeline_status
        and report_status.get("l1_report_committed") is True
        and str(pipeline_status.get("status") or "").lower() == "ok"
    ):
        return None
    expected_sha256 = str(report_status.get("report_sha256") or "")
    if expected_sha256 and file_sha256(report_path) != expected_sha256:
        return None
    report = report_path.read_text(
        encoding="utf-8", errors="replace"
    ).strip()
    return report or None


def _recover_l0_dispatches(
    session_dir: Path,
) -> tuple[List[dict], List[dict], Dict[tuple[str, str], str], List[dict]]:
    """Finish/replay exact pre-crash L1 calls and rebuild L0 context."""

    memory: List[dict] = []
    tool_history: List[dict] = []
    recovered: Dict[tuple[str, str], str] = {}
    audit_rows: List[dict] = []
    for call_dir in sorted(session_dir.glob("L1_call_*")):
        if not call_dir.is_dir():
            continue
        call_input = _read_json_dict(call_dir / "input.json")
        if not call_input:
            continue
        purpose = str(call_input.get("purpose") or "").strip()
        tasks = str(call_input.get("tasks") or "").strip()
        if not purpose and not tasks:
            continue
        report = _completed_l1_report(call_dir)
        action = "replayed_completed_report"
        if report is None:
            action = "resumed_incomplete_dispatch"
            report = dispatch_l1_pipeline(purpose, tasks)
        key = (purpose, tasks)
        recovered[key] = report
        memory.extend([
            {
                "role": "assistant",
                "content": (
                    "<summary>Crash-recovery replay of the exact previously "
                    f"committed {call_dir.name} dispatch.</summary>\n"
                    "<tool_call>dispatch_l1_pipeline("
                    f"purpose={purpose!r}, tasks={tasks!r})</tool_call>"
                ),
            },
            {
                "role": "user",
                "content": f"<tool_result>\n{report}\n</tool_result>",
            },
        ])
        receipt = {
            "iteration": 0,
            "tool": "dispatch_l1_pipeline",
            "args_keys": ["purpose", "tasks"],
            "arguments": {"purpose": purpose, "tasks": tasks},
            "result_chars": len(report),
            "result_full": report,
            "reasoning": "crash-recovery replay",
            "elapsed_s": 0.0,
            "recovered": True,
        }
        tool_history.append(receipt)
        audit_rows.append({
            "call_dir": call_dir.name,
            "purpose": purpose,
            "tasks": tasks,
            "action": action,
            "report_sha256": identity_sha256(report),
        })
    return memory, tool_history, recovered, audit_rows


# ════════════════════════════════════════════════════════════════
#  Session-scoped tool: list_session_files
# ════════════════════════════════════════════════════════════════

_SESSION_DIR_REF: Dict[str, Optional[Path]] = {"path": None}


def _list_session_files(purpose: str = "", tasks: str = "") -> str:
    """Return a markdown listing of every file produced so far in this
    L0 session (per-call sub-dirs included)."""
    sess = _SESSION_DIR_REF["path"]
    if sess is None or not sess.exists():
        return "_(no session directory)_"
    rows = []
    for p in sorted(sess.rglob("*")):
        if p.is_file():
            rel = p.relative_to(sess).as_posix()
            rows.append(f"- `{rel}` ({p.stat().st_size} bytes)")
    if not rows:
        return "_(no files yet)_"
    return f"# Session files (`{sess}`)\n\n" + "\n".join(rows)


# Cap how much text we hand back to L0 in one read so we don't blow up
# the context window on a 50 KB CSV.  L0 can re-read with a different
# ``max_chars`` if it needs more, but in practice the envelope CSVs are
# < 1 KB and the verdict markdowns are < 4 KB.
_READ_DEFAULT_MAX_CHARS = 8000
_READ_HARD_MAX_CHARS    = 60000


def _read_session_file(
    relative_path: str = "",
    max_chars: int = _READ_DEFAULT_MAX_CHARS,
) -> str:
    """Read a text file from the current session directory.

    Parameters
    ----------
    relative_path : str
        Path of the file relative to the session directory, exactly as
        returned by ``list_session_files`` (forward slashes ok).
    max_chars : int
        Truncate the returned content to this many characters.
        Defaults to 8000; hard-capped at 60000.

    The path is resolved against the session directory and rejected if
    it escapes (no ``..`` traversal, no absolute paths).  Binary files
    (PNG / JPG) are not returned — the caller is told their size and
    asked to look at the on-disk path instead.
    """
    sess = _SESSION_DIR_REF["path"]
    if sess is None or not sess.exists():
        return "_(no session directory)_"
    rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return "_(empty path)_"
    target = (sess / rel).resolve()
    try:
        target.relative_to(sess.resolve())
    except ValueError:
        return f"_(refused: path '{relative_path}' escapes session dir)_"
    if not target.exists() or not target.is_file():
        return f"_(no such file: '{relative_path}')_"
    suffix = target.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".bin"}:
        return (f"_(binary file '{relative_path}', "
                f"{target.stat().st_size} bytes — not returned)_")
    cap = max(1, min(int(max_chars or _READ_DEFAULT_MAX_CHARS),
                     _READ_HARD_MAX_CHARS))
    text = target.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > cap
    body = text[:cap]
    header = (f"# `{rel}` ({target.stat().st_size} bytes"
              + (f", first {cap} chars shown" if truncated else "") + ")\n\n")
    return header + body + ("\n\n_(truncated)_" if truncated else "")


# ════════════════════════════════════════════════════════════════
#  Output-rendering helpers (mirrors what the old pipeline did)
# ════════════════════════════════════════════════════════════════

def _write_answer_md(session_dir: Path, answer: str, user_request: str) -> None:
    text = (answer or "").strip()
    if not text:
        text = (
            "# Analysis Answer\n\n"
            f"**User request**: {user_request}\n\n"
            "_(L0 produced no final answer — likely hit iteration cap.)_\n"
        )
    atomic_write_text(session_dir / "answer.md", text)


RUN_TIMED_OUT_BANNER = (
    "## Run status: timed out\n\n"
    "The L0 orchestration reached its iteration or reasoning-time limit. "
    "This text is a partial synthesis and must not be treated as a "
    "completed or validated run. The structured API result and manifest "
    "also set `timed_out: true` and `completion_status: timed_out`."
)

VALIDATION_INCOMPLETE_BANNER = (
    "## Validation status: incomplete\n\n"
    "One or more L1 reports did not receive a completed `supported` LD "
    "review. This synthesis is retained for inspection, but it must "
    "not be treated as fully validated; see the `l1_scientific_review` "
    "phase in `manifest.json`."
)

ENABLED_INCOMPLETE_BANNER = (
    "## SRD-46 analysis — enabled estimation run incomplete\n\n"
    "One or more enabled scientific phases did not complete; see the "
    "`phases` block in `manifest.json` and the `l1_scientific_quality` "
    "rows in `working_memory.json`. "
    "This synthesis is retained for inspection, but it must not be "
    "treated as a validated result."
)

_EVIDENCE_HEADING_RE = re.compile(r"^## Evidence\b.*$", re.MULTILINE)


def insert_before_evidence(text: str, block: str) -> str:
    """Place ``block`` between the ``## Answer`` body and ``## Evidence``.

    Prepends when the prose has no Evidence heading, so the notice is never
    dropped from answers that do not follow the L0 output template.
    """

    match = _EVIDENCE_HEADING_RE.search(text)
    if match is None:
        return f"{block}\n\n{text}"
    head = text[: match.start()].rstrip()
    tail = text[match.start():]
    return f"{head}\n\n{block}\n\n{tail}" if head else f"{block}\n\n{tail}"


def annotate_answer(
    answer: str,
    *,
    timed_out: bool,
    validation_incomplete: bool,
    enabled_run: bool = False,
) -> str:
    """Expose run/validation gates to consumers that read only the prose.

    Status blocks are emitted as one group (timed-out first) so their order
    is the same whether they anchor before ``## Evidence`` or lead the text.
    """

    blocks: list[str] = []
    if timed_out:
        blocks.append(RUN_TIMED_OUT_BANNER)
    if validation_incomplete:
        blocks.append(
            ENABLED_INCOMPLETE_BANNER if enabled_run
            else VALIDATION_INCOMPLETE_BANNER
        )
    text = (answer or "").strip()
    if not blocks:
        return text
    return insert_before_evidence(
        text or "_(No synthesis was returned.)_",
        "\n\n".join(blocks),
    )


_LD_VERDICT_NAME_RE = re.compile(r"^verdict(?:_retry(?P<retry>\d+))?\.json$")


def _latest_ld_verdict(call_dir: Path) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
    """Load the latest readable LD verdict for one L1 call.

    Retry numbers encode review order (``verdict.json`` is attempt one,
    ``verdict_retry1.json`` is attempt two).  A malformed newest file does not
    erase an earlier valid review: candidates are tried newest-first until one
    decodes to a JSON object.
    """

    ld_dir = Path(call_dir) / "LD"
    candidates: list[tuple[int, Path]] = []
    if ld_dir.is_dir():
        for path in ld_dir.glob("verdict*.json"):
            match = _LD_VERDICT_NAME_RE.fullmatch(path.name)
            if match is None:
                continue
            retry = match.group("retry")
            attempt = 1 if retry is None else int(retry) + 1
            candidates.append((attempt, path))
    for _attempt, path in sorted(
        candidates, key=lambda item: (item[0], item[1].name), reverse=True
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload, path
    return None, None


def _normalise_validation_review(
    payload: Dict[str, Any],
    *,
    call_name: str,
    verdict_path: Optional[Path] = None,
    session_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    verdict = str(payload.get("verdict") or "not_run").strip().lower()
    hints_value = payload.get("hints") or []
    if isinstance(hints_value, (list, tuple)):
        hints = [str(item).strip() for item in hints_value if str(item).strip()]
    else:
        hints = [str(hints_value).strip()] if str(hints_value).strip() else []
    committed_value = payload.get("committed")
    if committed_value is None:
        # Compatibility with verdict files written before the explicit flag:
        # a concrete verdict can only have arisen from the terminal tool.
        committed = verdict in {"supported", "contradicted", "inconclusive"}
    else:
        committed = bool(committed_value)
    row: Dict[str, Any] = {
        "call_dir": call_name,
        "verdict": verdict,
        "hints": hints,
        "timed_out": bool(payload.get("timed_out", False)),
        "agent_turn_timed_out": bool(
            payload.get("agent_turn_timed_out", False)
        ),
        "committed": committed,
        # This is independent of the LD terminal commit above.  A validator
        # cannot promote an uncommitted/truncated L1 hard-stop answer into a
        # valid scientific report.
        "l1_report_committed": bool(
            payload.get("l1_report_committed", False)
        ),
        "l1_agent_turn_timed_out": bool(
            payload.get("l1_agent_turn_timed_out", False)
        ),
    }
    if payload.get("l1_report_reason"):
        row["l1_report_reason"] = str(payload["l1_report_reason"])
    if "validation_enabled" in payload:
        row["validation_enabled"] = bool(payload.get("validation_enabled"))
    if verdict_path is not None:
        try:
            row["verdict_path"] = verdict_path.resolve().relative_to(
                Path(session_dir).resolve()
            ).as_posix()
        except Exception:
            row["verdict_path"] = verdict_path.as_posix()
    return row


def _read_l1_report_status(
    call_dir: Path,
) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
    """Read the independent L1 terminal-report status sidecar, if present."""

    path = Path(call_dir) / "l1_report_status.json"
    if not path.is_file():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, path
    return (payload, path) if isinstance(payload, dict) else (None, path)


def _merge_l1_report_status(
    payload: Dict[str, Any],
    *,
    call_dir: Path,
) -> tuple[Dict[str, Any], Optional[Path]]:
    """Attach fail-closed report-commit evidence to an LD review payload."""

    merged = dict(payload)
    status, status_path = _read_l1_report_status(call_dir)
    if isinstance(status, dict):
        merged["l1_report_committed"] = bool(
            status.get("l1_report_committed", False)
        )
        merged["l1_agent_turn_timed_out"] = bool(
            status.get("agent_turn_timed_out", False)
        )
        if status.get("reason"):
            merged["l1_report_reason"] = str(status["reason"])
    elif "l1_report_committed" not in merged:
        # Compatibility for historical successful terminal commits.  The
        # terminal tool always wrote l1_analysis.json; the bad fallback path
        # that motivated this gate wrote only l1_report.md.
        merged["l1_report_committed"] = bool(
            (Path(call_dir) / "l1_analysis.json").is_file()
        )
    return merged, status_path


def _collect_l1_validation_reviews(
    session_dir: Path,
    working_memory: Dict[str, Any],
) -> list[Dict[str, Any]]:
    """Collect final per-call LD reviews, preferring working memory.

    Working memory is the normal same-run interface.  On legacy or partially
    persisted runs, the latest readable ``LD/verdict*.json`` is a deterministic
    fallback.  Every on-disk L1 call is represented, so a missing review cannot
    silently disappear from the aggregate gate.
    """

    session_dir = Path(session_dir)
    by_call: Dict[str, Dict[str, Any]] = {}
    rows = working_memory.get("l1_validation_reviews") or []
    if isinstance(rows, list):
        for payload in rows:
            if not isinstance(payload, dict):
                continue
            call_name = Path(str(payload.get("call_dir") or "")).name
            if not call_name.startswith("L1_call_"):
                call_number = payload.get("call")
                try:
                    call_name = f"L1_call_{int(call_number):02d}"
                except Exception:
                    continue
            merged, report_status_path = _merge_l1_report_status(
                payload,
                call_dir=session_dir / call_name,
            )
            by_call[call_name] = _normalise_validation_review(
                merged, call_name=call_name, session_dir=session_dir
            )
            if report_status_path is not None:
                try:
                    by_call[call_name]["report_status_path"] = (
                        report_status_path.resolve().relative_to(
                            session_dir.resolve()
                        ).as_posix()
                    )
                except Exception:
                    by_call[call_name]["report_status_path"] = (
                        report_status_path.as_posix()
                    )

    call_dirs = {
        path.name: path
        for path in session_dir.glob("L1_call_*")
        if path.is_dir()
    }
    for call_name, call_dir in call_dirs.items():
        if call_name in by_call:
            continue
        payload, verdict_path = _latest_ld_verdict(call_dir)
        if payload is None:
            payload = {
                "verdict": "not_run",
                "hints": ["No persisted LD terminal review was found."],
                "timed_out": True,
                "committed": False,
            }
        payload, report_status_path = _merge_l1_report_status(
            payload,
            call_dir=call_dir,
        )
        by_call[call_name] = _normalise_validation_review(
            payload,
            call_name=call_name,
            verdict_path=verdict_path,
            session_dir=session_dir,
        )
        if report_status_path is not None:
            try:
                by_call[call_name]["report_status_path"] = (
                    report_status_path.resolve().relative_to(
                        session_dir.resolve()
                    ).as_posix()
                )
            except Exception:
                by_call[call_name]["report_status_path"] = (
                    report_status_path.as_posix()
                )

    def _call_order(item: Dict[str, Any]) -> tuple[int, str]:
        name = str(item.get("call_dir") or "")
        match = re.search(r"(\d+)$", name)
        return (int(match.group(1)) if match else 10**9, name)

    return sorted(by_call.values(), key=_call_order)


def _normalise_l1_execution(
    payload: Dict[str, Any],
    *,
    call_name: str,
) -> Dict[str, Any]:
    """Return the compact execution row used by the deterministic L0 gate."""

    status = str(payload.get("status") or "").strip().lower()
    if not status:
        # Compatibility with successful rows persisted before execution
        # status became explicit.
        status = (
            "ok"
            if payload.get("sweep_method") or payload.get("output_dir")
            else "unknown"
        )
    return {
        "call_dir": call_name,
        "status": status,
        "stage": payload.get("stage"),
        "error": payload.get("error"),
        "sweep_method": payload.get("sweep_method"),
        "output_dir": payload.get("output_dir"),
        "n_output_files": payload.get("n_output_files"),
        "elapsed_s": payload.get("elapsed_s"),
    }


def _collect_l1_execution_runs(
    session_dir: Path,
    working_memory: Dict[str, Any],
) -> list[Dict[str, Any]]:
    """Collect one final deterministic execution outcome per L1 call.

    Working memory is authoritative during a normal run.  The per-call
    ``pipeline_status.json`` sidecar is the crash/debug fallback.  An L1 call
    with neither record is retained as ``not_run`` rather than disappearing
    from the execution gate.
    """

    session_dir = Path(session_dir)
    by_call: Dict[str, Dict[str, Any]] = {}
    rows = working_memory.get("l1_pipeline_runs") or []
    if isinstance(rows, list):
        for payload in rows:
            if not isinstance(payload, dict):
                continue
            call_name = Path(str(payload.get("call_dir") or "")).name
            if not call_name.startswith("L1_call_"):
                try:
                    call_name = f"L1_call_{int(payload.get('call')):02d}"
                except Exception:
                    continue
            # Later rows supersede earlier attempts for the same L1 call.
            by_call[call_name] = _normalise_l1_execution(
                payload,
                call_name=call_name,
            )

    call_dirs = {
        path.name: path
        for path in session_dir.glob("L1_call_*")
        if path.is_dir()
    }
    for call_name, call_dir in call_dirs.items():
        if call_name in by_call:
            continue
        status_path = call_dir / "pipeline_status.json"
        payload: Optional[Dict[str, Any]] = None
        if status_path.is_file():
            try:
                candidate = json.loads(status_path.read_text(encoding="utf-8"))
            except Exception:
                candidate = None
            if isinstance(candidate, dict):
                payload = candidate
        if payload is None:
            payload = {
                "status": "not_run",
                "stage": "L1",
                "error": "No deterministic pipeline execution status was recorded.",
            }
        by_call[call_name] = _normalise_l1_execution(
            payload,
            call_name=call_name,
        )

    def _call_order(item: Dict[str, Any]) -> tuple[int, str]:
        name = str(item.get("call_dir") or "")
        match = re.search(r"(\d+)$", name)
        return (int(match.group(1)) if match else 10**9, name)

    return sorted(by_call.values(), key=_call_order)


def _l1_execution_phase(runs: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Separate numerical completion from LD support of the resulting prose."""

    complete = bool(runs) and all(
        str(run.get("status") or "").lower() == "ok" for run in runs
    )
    return {
        "status": "complete" if complete else "incomplete",
        "skipped_reason": (
            None
            if complete
            else (
                "one or more L1 calls did not complete the deterministic "
                "build-and-solve pipeline"
            )
        ),
        "runs": runs,
    }


def _reference_validation_phase(
    reviews: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate reference-only LD reviews without changing L0 timeout."""

    reports_committed = bool(reviews) and all(
        bool(review.get("l1_report_committed")) for review in reviews
    )
    explicitly_disabled = reports_committed and all(
        review.get("validation_enabled") is False for review in reviews
    )
    if explicitly_disabled:
        return {
            "status": "skipped",
            "skipped_reason": "LD validation was disabled for every L1 call",
            "ld_verdict": "not_run",
            "reviews": reviews,
        }
    complete = bool(reviews) and all(
        bool(review.get("l1_report_committed"))
        and review.get("verdict") == "supported"
        and not bool(review.get("timed_out"))
        and bool(review.get("committed"))
        for review in reviews
    )
    return {
        "status": "complete" if complete else "incomplete",
        "skipped_reason": (
            None
            if complete
            else (
                "one or more L1 reports lack a successful record_analysis "
                "commit or a completed supported LD terminal review"
            )
        ),
        "ld_verdict": (
            "supported" if complete else "not_supported_or_inconclusive"
        ),
        "reviews": reviews,
    }


def _enabled_scientific_phases(
    quality_rows: list[Any],
) -> Dict[str, Dict[str, Any]]:
    """Build fail-closed L0 phase status from guarded L1 quality rows."""

    rows = [row for row in quality_rows if isinstance(row, dict)]
    coverage_complete = bool(rows) and all(
        ((row.get("model_coverage") or {}).get("complete") is True)
        for row in rows
    )
    reports_committed = bool(rows) and all(
        row.get("agent_committed_report") is True for row in rows
    )
    ld_supported = reports_committed and all(
        (
            (row.get("ld_verdict") or {}).get("verdict") == "supported"
            and (row.get("ld_verdict") or {}).get("committed") is True
            and not bool((row.get("ld_verdict") or {}).get("timed_out"))
        )
        for row in rows
    )
    estimation_search_complete = bool(rows) and all(
        (
            (row.get("estimated_equilibrium_enrichment") or {}).get(
                "estimation_search_complete"
            ) is True
        )
        for row in rows
    )
    return {
        "l1_estimation_search": {
            "status": (
                "complete" if estimation_search_complete else "incomplete"
            ),
            "skipped_reason": (
                None
                if estimation_search_complete
                else (
                    "one or more enabled LC1_3 searches failed or were "
                    "omitted; the reference-only fallback is not an "
                    "ordinary no-estimation result"
                )
            ),
        },
        "l1_requested_system_coverage": {
            "status": "complete" if coverage_complete else "incomplete",
            "skipped_reason": (
                None
                if coverage_complete
                else (
                    "one or more requested ligands were omitted or coverage "
                    "was unverified"
                )
            ),
        },
        "l1_scientific_review": {
            "status": "complete" if ld_supported else "incomplete",
            "skipped_reason": (
                None
                if ld_supported
                else (
                    "one or more L1 calls lack a successful record_analysis "
                    "commit or a completed supported LD terminal review"
                )
            ),
            "ld_verdict": (
                "supported"
                if ld_supported
                else "not_supported_or_inconclusive"
            ),
        },
    }


def _write_history_md(session_dir: Path, history_path: Path) -> None:
    if not history_path.exists():
        return
    rows = [
        "# L0 Run History",
        "",
        "| ts (s offset) | event | details |",
        "|--------------:|-------|---------|",
    ]
    t0 = None
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            if t0 is None:
                t0 = float(ts)
            offset = f"{float(ts) - t0:7.3f}"
        else:
            offset = "      -"
        event = str(rec.get("event", ""))
        keys = [k for k in rec.keys() if k not in ("ts", "event")]
        details = "; ".join(f"{k}={rec[k]!r}" for k in keys).replace("|", "\\|")
        rows.append(f"| {offset} | {event} | {details} |")
    (session_dir / "run_history.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8")


def _write_tool_history_md(session_dir: Path, tool_history: list) -> None:
    """Render the engine's ``tool_history`` (one entry per LLM tool call).

    The engine records each entry under the key ``arguments`` (not
    ``args``); previous code read the wrong key and produced an empty
    table.  In addition to the summary table we now emit a per-call
    detail block with the full arguments JSON, the LLM's reasoning
    excerpt, and a result preview, so that the L0 transcript is
    actually inspectable after a run.
    """
    rows = [
        "# L0 Tool Calls",
        "",
        "| # | iter | tool | purpose (excerpt) | tasks (excerpt) | result_chars | elapsed_s |",
        "|--:|----:|------|-------------------|-----------------|------------:|---------:|",
    ]
    detail_blocks: list[str] = []
    for i, call in enumerate(tool_history, start=1):
        tool = call.get("tool", "?")
        it   = call.get("iteration", "")
        args = call.get("arguments", {}) or {}
        purpose = str(args.get("purpose", ""))[:80].replace("|", "\\|").replace("\n", " ")
        tasks   = str(args.get("tasks",   ""))[:80].replace("|", "\\|").replace("\n", " ")
        rc = call.get("result_chars", "")
        es = call.get("elapsed_s", "")
        rows.append(f"| {i} | {it} | {tool} | {purpose} | {tasks} | {rc} | {es} |")

        try:
            args_json = json.dumps(args, indent=2, default=str)
        except Exception:
            args_json = repr(args)
        reasoning_excerpt = str(call.get("reasoning") or "")[:1500]
        result_preview    = str(call.get("result_full") or "")
        detail_blocks.append(
            f"\n## Tool call {i} \u2014 `{tool}` (iteration {it})\n\n"
            f"### Arguments\n```json\n{args_json}\n```\n\n"
            f"### Reasoning excerpt\n```\n{reasoning_excerpt}\n```\n\n"
            f"### Result ({call.get('result_chars','?')} chars)\n"
            f"```\n{result_preview}\n```\n"
        )
    out = "\n".join(rows) + "\n" + "\n".join(detail_blocks)
    (session_dir / "l0_tool_calls.md").write_text(out, encoding="utf-8")

    # JSONL mirror (raw, never truncated) for replay / regression tests.
    jsonl_path = session_dir / "l0_tool_calls.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for i, call in enumerate(tool_history, start=1):
            rec = {
                "agent":        "L0",
                "call_index":   i,
                "iteration":    call.get("iteration"),
                "tool":         call.get("tool"),
                "arguments":    call.get("arguments", {}) or {},
                "result_chars": call.get("result_chars"),
                "result_full":  call.get("result_full", "") or "",
                "reasoning":    call.get("reasoning", "") or "",
                "elapsed_s":    call.get("elapsed_s"),
            }
            fh.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")


# ════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════

def run(
    user_request: str,
    *,
    session_dir: str | Path,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    l0_max_iterations: Optional[int] = None,
    l0_reasoning_timeout_s: Optional[float] = None,
    resume: bool = True,
    round_number: int = 1,
    prev_context: str = "",
) -> Dict[str, Any]:
    """Drive one full LLM-orchestrated analysis turn.

    Parameters
    ----------
    user_request : str
        Natural-language analysis request (e.g. "Pourbaix diagram for
        Cu in glycine").
    session_dir : str | Path
        Output root for this run. ``answer.md``, ``run_history.md``,
        ``run_stats.md``, ``manifest.json`` and per-pipeline-call
        sub-directories ``L1_call_NN/`` are written here.
    debug : bool
        Forwarded to the L1 sub-agent for tracebacks.
    estimate_missing_equilibria : bool | None
        Fixed session-level gate for query-assisted missing-equilibrium
        support. ``None`` inherits the shared configuration for direct calls.
    l0_max_iterations : int | None
        Optional per-run cap on L0 LLM turns only.  Inner agent budgets keep
        their shared defaults.
    l0_reasoning_timeout_s : float | None
        Optional per-run L0 effective-reasoning-time budget in seconds only.
        ``dispatch_l1_pipeline`` wall time is excluded, as documented below.
    resume : bool
        Recover exact L0-to-L1 dispatches already persisted in ``session_dir``
        and continue their stage/grid journals. A directory bound to another
        top-level request is rejected rather than mixed silently.
    round_number : int
        1-based round index inside a multi-round conversation.  Rounds after
        the first drop the ``dispatch_l1_pipeline`` requirement so a
        follow-up that only reinterprets existing results does not force a
        full L1 re-dispatch.
    prev_context : str
        Cleaned full context from the previous round, pre-seeded into L0
        memory so the LLM sees the complete prior conversation.

    Returns
    -------
    dict with keys ``answer``, ``iterations``, ``elapsed_s``,
    ``tool_history``, ``session_dir``, ``timed_out``.
    """
    if l0_max_iterations is None:
        effective_l0_max_iterations = int(cfg.MAX_TOOL_ITERATIONS)
    else:
        if isinstance(l0_max_iterations, bool) or not isinstance(
            l0_max_iterations, int
        ):
            raise TypeError("l0_max_iterations must be an integer or None")
        if l0_max_iterations < 1:
            raise ValueError("l0_max_iterations must be at least 1")
        effective_l0_max_iterations = l0_max_iterations

    if l0_reasoning_timeout_s is None:
        effective_l0_reasoning_timeout_s = float(cfg.MAX_TURN_SECONDS)
    else:
        if isinstance(l0_reasoning_timeout_s, bool) or not isinstance(
            l0_reasoning_timeout_s, (int, float)
        ):
            raise TypeError(
                "l0_reasoning_timeout_s must be a number or None"
            )
        effective_l0_reasoning_timeout_s = float(l0_reasoning_timeout_s)
        if not (
            effective_l0_reasoning_timeout_s > 0.0
            and effective_l0_reasoning_timeout_s < float("inf")
        ):
            raise ValueError(
                "l0_reasoning_timeout_s must be finite and greater than 0"
            )

    l0_budget_override_used = (
        l0_max_iterations is not None
        or l0_reasoning_timeout_s is not None
    )

    effective_estimation = resolve_estimate_missing_equilibria(
        estimate_missing_equilibria
    )
    forward_explicit_estimation_disable = (
        estimate_missing_equilibria is False
        and resolve_estimate_missing_equilibria() is True
    )

    sess = Path(session_dir)
    sess.mkdir(parents=True, exist_ok=True)
    _SESSION_DIR_REF["path"] = sess
    had_prior_work = _prepare_l0_resume(
        sess,
        _l0_resume_identity(
            user_request,
            estimate_missing_equilibria=effective_estimation,
        ),
        resume=bool(resume),
    )

    # Hooks (history + stats live at the L0 level so they capture
    # ALL L1 sub-agent calls, not just one).
    history = AnalysisHistoryRecorder(session_dir=sess)
    stats   = AnalysisStatsRecorder(session_dir=sess)
    working_mem = AnalysisWorkingMemory(session_dir=sess)

    # Wire the L1 sub-agent's session side-channel.  ``working_mem``
    # is shared with the pipeline so that the deterministic S1..S8 driver
    # and the per-checkpoint L1 sub-agent both populate it (seed_system
    # at C1, sweep_intent at C3, final_summary at C4, key artifacts after
    # S2/S6).  Without this, ``working_memory.json`` stays empty.
    if effective_estimation:
        configure_l1_session(
            session_dir=sess,
            history=history,
            stats=stats,
            working_memory=working_mem,
            debug=debug,
            estimate_missing_equilibria=True,
        )
    elif forward_explicit_estimation_disable:
        # Preserve a per-run explicit false across the L1 seam when the
        # shared setting is true.  Without the keyword, L1's later call into
        # ``run_pipeline`` would inherit the global true value again.
        configure_l1_session(
            session_dir=sess,
            history=history,
            stats=stats,
            working_memory=working_mem,
            debug=debug,
            estimate_missing_equilibria=False,
        )
    else:
        configure_l1_session(
            session_dir=sess,
            history=history,
            stats=stats,
            working_memory=working_mem,
            debug=debug,
        )

    recovered_memory: List[dict] = []
    recovered_tool_history: List[dict] = []
    recovered_dispatches: Dict[tuple[str, str], str] = {}
    recovery_audit: List[dict] = []
    if had_prior_work:
        (
            recovered_memory,
            recovered_tool_history,
            recovered_dispatches,
            recovery_audit,
        ) = _recover_l0_dispatches(sess)
        if recovery_audit:
            atomic_write_json(
                sess / "_checkpoints" / "l0_dispatch_recovery.json",
                {
                    "schema_version": "l0_dispatch_recovery.v1",
                    "recovered_at": time.time(),
                    "calls": recovery_audit,
                },
            )

    def dispatch_with_resume(purpose: str = "", tasks: Any = None) -> str:
        """Dispatch one L1 system or replay its exact recovered report."""

        key = (
            str(purpose or "").strip(),
            str(tasks or "").strip(),
        )
        if key in recovered_dispatches:
            history.log(
                "L0_recovered_dispatch_reused",
                purpose=key[0][:200],
            )
            return recovered_dispatches[key]
        return dispatch_l1_pipeline(key[0], key[1])

    # Tool registry (L1 dispatch + session catalog + per-file reader so
    # L0 can quote actual numerics from envelope CSVs / verdict.md).
    tools: Dict[str, Callable] = {
        "dispatch_l1_pipeline": dispatch_with_resume,
        "list_session_files":   _list_session_files,
        "read_session_file":    _read_session_file,
    }

    # Workflow + system prompt
    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    if effective_estimation:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n"
            + _ESTIMATION_STATUS_PROMPT_PATH.read_text(
                encoding="utf-8"
            ).strip()
        )
    system_prompt += "\n\n" + build_tool_instructions(tools)

    # LLM client
    client = SRD46AnalysisClient.for_l0()

    # Engine hooks (compaction, working-memory rendering, …).  No engine
    # tracking recorders are bound here: the L0 ReAct loop's per-iteration
    # tool decisions are already captured in ``l0_tool_calls.md`` (a
    # human-friendly view of ``result.tool_history``), and the actual
    # "engine" that the user cares about is the deterministic L1 pipeline
    # whose events are recorded in ``run_history.md`` / ``run_stats.md``.
    # Wire ``working_mem.render`` so each LLM turn's WORKING_MEMORY_RENDER
    # anchor returns the live cross-checkpoint scratch state populated by
    # the pipeline.
    _engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=working_mem.render,
        guidance_hooks=[],
    )

    history.log(
        "L0_start",
        user_request=user_request[:200],
        max_iterations=effective_l0_max_iterations,
        reasoning_timeout_s=effective_l0_reasoning_timeout_s,
    )
    t0 = time.time()
    initial_memory: List[dict] = []
    if prev_context:
        initial_memory.append({
            "role": "user",
            "content": (
                "## Prior Conversation Context\n"
                "Below is the full conversation history from the previous "
                "round. Continue from where it left off.\n\n" + prev_context
            ),
        })
    if recovered_memory:
        initial_memory.append({"role": "user", "content": user_request})
        initial_memory.extend(recovered_memory)
    result: AgentTurnResult = agent_turn(
        user_request,
        system_prompt=system_prompt,
        tools=tools,
        memory=initial_memory,
        client=client,
        max_iterations=effective_l0_max_iterations,
        timeout=effective_l0_reasoning_timeout_s,
        required_tools=(
            {"dispatch_l1_pipeline"} if round_number <= 1 else None
        ),
        hooks=_engine_agent_hooks.engine_hooks,
        # Each dispatch_l1_pipeline call runs a full L1 sub-pipeline
        # (200-450s of deterministic solve + sub-agent reasoning). Exclude
        # that wall-clock from the L0 turn budget so only the L0's own
        # reasoning counts against MAX_TURN_SECONDS — mirrors the L1
        # subagent excluding its pipeline tool. Without this, a multi-call
        # orchestration (e.g. a 3x3 metal x ligand matrix) exhausts the
        # 600s budget during dispatch and truncates the final synthesis.
        untimed_tools={"dispatch_l1_pipeline"},
        append_user_message=not bool(recovered_memory),
        initial_tool_history=recovered_tool_history,
    )
    elapsed = time.time() - t0
    history.log(
        "L0_end",
        elapsed_s=elapsed,
        iterations=result.iterations,
        timed_out=result.timed_out,
    )

    stats.incr("L0", "iterations", result.iterations)
    stats.incr("L0", "tool_calls", len(result.tool_history))
    stats.save()

    # Persist artifacts.  On the enabled path, L0's synthesis is the
    # user-facing answer; its deterministic backing lives in the
    # l1_scientific_quality working-memory rows and the manifest phases.
    working_memory_snapshot = working_mem.as_dict()
    l1_execution_runs = _collect_l1_execution_runs(
        sess,
        working_memory_snapshot,
    )
    l1_execution_phase = _l1_execution_phase(l1_execution_runs)
    l1_execution_complete = l1_execution_phase.get("status") == "complete"
    reference_validation_reviews: list[Dict[str, Any]] = []
    reference_validation_phase: Optional[Dict[str, Any]] = None
    reference_validation_complete = False
    enabled_scientific_phases: Optional[Dict[str, Dict[str, Any]]] = None
    validation_incomplete = False
    if not effective_estimation:
        reference_validation_reviews = _collect_l1_validation_reviews(
            sess, working_memory_snapshot
        )
        reference_validation_phase = _reference_validation_phase(
            reference_validation_reviews
        )
        reference_validation_complete = (
            reference_validation_phase.get("status") == "complete"
        )
        validation_incomplete = (
            reference_validation_phase.get("status") == "incomplete"
        )
    else:
        enabled_scientific_phases = _enabled_scientific_phases(
            working_memory_snapshot.get("l1_scientific_quality") or []
        )
        validation_incomplete = any(
            phase.get("status") == "incomplete"
            for phase in enabled_scientific_phases.values()
        )
    final_answer = annotate_answer(
        result.answer,
        timed_out=bool(result.timed_out),
        validation_incomplete=validation_incomplete,
        enabled_run=bool(effective_estimation),
    )
    _write_answer_md(sess, final_answer, user_request)
    _write_history_md(sess, history.path)
    _write_tool_history_md(sess, result.tool_history)
    # Raw last-turn LLM context — the restorable "state" for continuations.
    _save_llm_final_context(sess, result.final_context)

    # Manifest
    completion_status = (
        "timed_out"
        if result.timed_out
        else (
            "execution_failed"
            if not l1_execution_complete
            else (
                "validation_incomplete"
                if validation_incomplete
                else "complete"
            )
        )
    )
    manifest = {
        "user_request": user_request,
        "session_dir": str(sess),
        "iterations": result.iterations,
        "elapsed_s": round(elapsed, 3),
        "timed_out": result.timed_out,
        "completion_status": completion_status,
        "n_tool_calls": len(result.tool_history),
        "tool_call_summary": [
            {
                "tool": c.get("tool"),
                "iteration": c.get("iteration"),
                "arguments": c.get("arguments", {}),
                "result_chars": c.get("result_chars"),
                "elapsed_s": c.get("elapsed_s"),
            }
            for c in result.tool_history
        ],
        "working_memory": working_memory_snapshot,
    }
    if l0_budget_override_used:
        manifest["l0_budget"] = {
            "max_iterations": effective_l0_max_iterations,
            "reasoning_timeout_s": effective_l0_reasoning_timeout_s,
            "scope": "L0 only; dispatch_l1_pipeline wall time excluded",
        }
    if round_number > 1:
        manifest["round_number"] = round_number
    if effective_estimation:
        # Enabled-only scientific acceptance metadata.  The disabled manifest
        # remains byte-for-byte shaped like the legacy path.
        manifest["estimated_equilibrium_enrichment_enabled"] = True
        manifest["phases"] = enabled_scientific_phases or (
            _enabled_scientific_phases([])
        )
    elif reference_validation_phase is not None:
        # Reference-only runs do not publish the enabled-run quality rows, so
        # expose their per-L1 LD reviews through a deterministic phase of their
        # own.  This affects validation completeness, never L0's timeout flag.
        manifest["validation_complete"] = reference_validation_complete
        manifest["validation_reviews"] = reference_validation_reviews
        manifest["phases"] = {
            "l1_scientific_review": reference_validation_phase
        }
    manifest["l1_execution_complete"] = l1_execution_complete
    manifest.setdefault("phases", {})["l1_execution"] = l1_execution_phase
    if result.timed_out:
        manifest.setdefault("phases", {})["l0_orchestration"] = {
            "status": "incomplete",
            "skipped_reason": (
                "L0 reached its iteration or reasoning-time limit; synthesis "
                "is partial"
            ),
        }
    atomic_write_json(sess / "manifest.json", manifest)
    atomic_write_json(sess / "_checkpoints" / "l0_resume_status.json", {
        "schema_version": "l0_resume_status.v1",
        "status": "complete",
        "identity_sha256": identity_sha256(_l0_resume_identity(
            user_request,
            estimate_missing_equilibria=effective_estimation,
        )),
        "completed_at": time.time(),
        "manifest_sha256": file_sha256(sess / "manifest.json"),
        "answer_sha256": (
            file_sha256(sess / "answer.md")
            if (sess / "answer.md").is_file() else None
        ),
        "recovered_dispatch_count": len(recovery_audit),
    })

    # Verdict
    verdict = run_verdict(sess) if (sess / "manifest.json").exists() else {
        "verdict": "unknown", "notes": []
    }
    save_final_context(sess, verdict)

    log.info(
        "L0 done: %d iterations, %.1fs, %d tool calls",
        result.iterations, elapsed, len(result.tool_history),
    )
    response = {
        "answer":       final_answer,
        "iterations":   result.iterations,
        "elapsed_s":    elapsed,
        "tool_history": result.tool_history,
        "session_dir":  str(sess),
        "timed_out":    result.timed_out,
        "completion_status": completion_status,
        "validation_complete": (
            None if effective_estimation else reference_validation_complete
        ),
        "validation_reviews": (
            [] if effective_estimation else reference_validation_reviews
        ),
        "l1_execution_complete": l1_execution_complete,
        "l1_execution_runs": l1_execution_runs,
        "verdict":      verdict,
    }
    if l0_budget_override_used:
        response["l0_budget"] = manifest["l0_budget"]
    return response


__all__ = ["run"]
