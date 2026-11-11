"""
L0 orchestrator — LLM-driven top-level reasoner for the SRD-46
analysis agent.

Responsibilities:

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
from ...analysis_continuation import native_clock, seed_working_memory, saved_l0_prompt
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
from ...analysis_reconstruction import reconstruction_reads, analysis_entrypoint
from ...SRD46_analysis_argo_config import (
    AGENT_CONFIG as cfg,
    resolve_estimate_missing_equilibria,
)

# L1 sub-agent (the only thing L0 can call into the pipeline)
from ..L1_subagent import dispatch_l1_pipeline, configure_l1_session

# LV validator — reviews L0's final answer; an ``execution_failure`` verdict
# gives L0 the turn back (bounded by cfg.L0_EXECUTION_BOUNCE_BUDGET).
from ..LV_validator import (
    EXECUTION_FAILURE as LV_EXECUTION_FAILURE,
    bounce_notice as lv_bounce_notice,
    call_skeleton as lv_call_skeleton,
    host_checks as lv_host_checks,
    review as lv_review,
)

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


def _l0_resume_identity(user_request: str, *, estimate_missing_equilibria: bool) -> Dict[str, Any]:
    return {
        "contract": "l0-analysis-resume/v1",
        "user_request": str(user_request),
        "estimate_missing_equilibria": bool(estimate_missing_equilibria),
    }


def _prepare_l0_run(session_dir: Path, identity: Dict[str, Any]) -> None:
    """Record a fresh or strictly reconstructed invocation, never infer context."""
    checkpoint_dir = session_dir / "_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    expected_sha256 = identity_sha256(identity)
    atomic_write_json(checkpoint_dir / "l0_run_identity.json", {
        "schema_version": "l0_run_identity.v1",
        "identity": identity,
        "identity_sha256": expected_sha256,
    })
    atomic_write_json(checkpoint_dir / "l0_resume_status.json", {
        "schema_version": "l0_resume_status.v1",
        "status": "running",
        "identity_sha256": expected_sha256,
        "pid": os.getpid(),
        "started_or_resumed_at": native_clock(__name__, "time", time.time),
        "prior_durable_work_detected": False,
    })


# ════════════════════════════════════════════════════════════════
#  Session-scoped tool: list_session_files
# ════════════════════════════════════════════════════════════════

_SESSION_DIR_REF: Dict[str, Optional[Path]] = {"path": None}
_RECONSTRUCTION_INTERNAL_PARTS = ("run_provenance", "first_principle_reconstruction")


def _list_session_files(purpose: str = "", tasks: str = "", folder: str = "") -> str:
    """Compact catalog of this session's files: pipeline flags first, then each L1 call's core artifacts in full and every other folder as one count line; pass folder="<path prefix>" to list that folder in full.

    ``purpose`` / ``tasks`` are accepted for call-site compatibility and
    ignored.  Reconstruction-internal records are never listed.
    """
    sess = _SESSION_DIR_REF["path"]
    if sess is None or not sess.exists():
        return "_(no session directory)_"
    rows = []
    for p in sorted(sess.rglob("*")):
        relative = p.relative_to(sess)
        if tuple(part.lower() for part in relative.parts[:2]) == _RECONSTRUCTION_INTERNAL_PARTS:
            continue
        if p.is_file():
            rel = relative.as_posix()
            rows.append((rel, relative.parts, p.stat().st_size))
    if not rows:
        return "_(no files yet)_"
    if str(folder or "").strip():
        return _session_folder_listing(sess, rows, str(folder))
    return _compact_session_listing(sess, rows)


# Files L0 reads to answer: one L1 call's reports and statuses, the LC1
# eq-map card and sweep input, the LC1_3 manifest or failure record with
# the query agents' answers and the values that passed the parser gate,
# the stage summaries, every solver output (the working-memory
# ``output_files`` list) and the LD verdict.  Everything else is shown as
# one count line per folder and served in full on request (``folder=``).
_SESSION_CORE_CALL_FILES = frozenset({
    "l1_report.md", "l1_analysis.json", "l1_report_status.json",
    "pipeline_status.json", "thermodynamic_reference_constants.md", "input.json",
})
_SESSION_CORE_LC1_FILES = frozenset({"lc1_sweep_input.json", "lc1_2_eqmap_card.json"})
_SESSION_CORE_LC1_3_FILES = frozenset({"LC1_3_manifest.json", "LC1_3_failure.json"})
_SESSION_FOLDER_ROW_CAP = 400
_SESSION_ROOT_ROW_CAP = 12


def _session_file_is_core(parts: tuple) -> bool:
    if not parts or not parts[0].startswith("L1_call_"):
        return False
    inner = parts[1:]
    if not inner or "_checkpoints" in inner:
        return False
    name = inner[-1]
    if len(inner) == 1:
        return name in _SESSION_CORE_CALL_FILES
    if inner[0] == "solver":
        return True
    if inner[0] == "LD":
        return name == "verdict.json"
    if inner[0] in ("LC1", "LC2", "LC3") and inner[1] == "summary":
        return True
    if inner[0] == "LC1" and len(inner) == 2:
        return name in _SESSION_CORE_LC1_FILES
    if inner[:2] == ("LC1", "LC1_3"):
        if len(inner) == 3:
            return name in _SESSION_CORE_LC1_3_FILES
        if inner[2] == "support_eq_map":
            return True
        if inner[2] == "parser_agents" and name == "committed_guess_set.json":
            return True
        if inner[2] == "query_agents" and name == "answer.md":
            # The dispatch answer and every follow-up answer; the last
            # one is the final answer the parser read.
            return True
    return False


def _session_group_key(parts: tuple) -> str:
    if not parts[0].startswith("L1_call_"):
        return "(session root)"
    return "/".join(parts[:3]) if len(parts) > 3 else "/".join(parts[:-1])


def _session_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _session_kb(n_bytes: int) -> str:
    return f"{n_bytes / 1024:.0f} KB" if n_bytes >= 1024 else f"{n_bytes} bytes"


def _session_flags(sess: Path, call_dirs: list) -> list:
    """Out-of-the-ordinary pipeline records, one line each, from the
    deterministic status files (never from agent prose)."""
    flags: list = []
    for call in call_dirs:
        name = call.name
        status = _session_json(call / "pipeline_status.json") or {}
        state = str(status.get("status") or "").strip().lower()
        if state and state != "ok":
            flags.append(
                f"{name}: pipeline status `{state}` at stage "
                f"{status.get('stage') or '?'} \u2014 "
                f"{str(status.get('error') or '').strip()[:300]}"
            )
        report = _session_json(call / "l1_report_status.json") or {}
        if report and (
            str(report.get("status") or "") != "complete"
            or report.get("agent_turn_timed_out")
        ):
            flags.append(
                f"{name}: L1 report status `{report.get('status')}`"
                + (" (agent turn timed out)" if report.get("agent_turn_timed_out") else "")
                + (f" \u2014 {report.get('reason')}" if report.get("reason") else "")
            )
        manifest = _session_json(call / "LC1" / "LC1_3" / "LC1_3_manifest.json")
        if isinstance(manifest, dict) and str(manifest.get("status") or "ok") != "ok":
            summary = manifest.get("failure_summary") or {}
            rows = summary.get("parser_failures") or [] if isinstance(summary, dict) else []
            detail = "; ".join(
                f"{row.get('query_id')}: {str(row.get('error') or '')[:160]}"
                + (" [gateway transport failure]" if row.get("transport_failure") else "")
                for row in rows if isinstance(row, dict)
            )
            flags.append(
                f"{name}: LC1_3 status `{manifest.get('status')}` "
                f"({manifest.get('reference_only_reason')}); estimated support withheld"
                + (f" \u2014 {detail}" if detail else "")
            )
        for failure in sorted(call.rglob("*failure*.json")):
            if isinstance(manifest, dict) and "LC1_3" in failure.parts:
                continue  # covered by the LC1_3 status line above
            flags.append(f"{name}: failure record `{failure.relative_to(sess).as_posix()}`")
        verdict = _session_json(call / "LD" / "verdict.json")
        if isinstance(verdict, dict) and (
            str(verdict.get("verdict") or "") != "supported"
            or verdict.get("timed_out")
            or not verdict.get("committed", True)
        ):
            flags.append(
                f"{name}: LD verdict `{verdict.get('verdict')}`"
                + (" (timed out)" if verdict.get("timed_out") else "")
                + ("" if verdict.get("committed", True) else " (not committed)")
            )
        if state == "ok" and not any((call / "solver").glob("*")):
            flags.append(f"{name}: status ok but no solver outputs")
    return flags


def _session_folder_listing(sess: Path, rows: list, folder: str) -> str:
    """List every file under one path prefix."""
    prefix = tuple(folder.strip().replace("\\", "/").strip("/").split("/"))
    hits = [(rel, size) for rel, parts, size in rows if parts[:len(prefix)] == prefix]
    if not hits:
        return f"_(no files under `{'/'.join(prefix)}`)_"
    head = (
        f"# Session files under `{'/'.join(prefix)}` ({len(hits)} files, "
        f"{_session_kb(sum(size for _, size in hits))})\n"
    )
    body = [f"- `{rel}` ({size} bytes)" for rel, size in hits[:_SESSION_FOLDER_ROW_CAP]]
    if len(hits) > _SESSION_FOLDER_ROW_CAP:
        body.append(
            f"- \u2026 {len(hits) - _SESSION_FOLDER_ROW_CAP} more; ask for a narrower prefix"
        )
    return head + "\n" + "\n".join(body)


def _compact_session_listing(sess: Path, rows: list) -> str:
    """Flags, then per L1 call the core artifacts in full and the other
    folders as count lines, then the session-root files."""
    call_dirs = sorted(p for p in sess.glob("L1_call_*") if p.is_dir())
    total = sum(size for _, _, size in rows)
    out = [
        f"# Session files (`{sess}`) \u2014 compact view: {len(rows)} files, {_session_kb(total)}",
        "",
        "Core artifacts are listed in full; every other folder is one line with its "
        "count. Ask for any folder in full with `list_session_files(folder=\"<path prefix>\")`, "
        "e.g. `list_session_files(folder=\"L1_call_01/LC1/LC1_3/parser_agents\")`.",
        "",
        "## Flags \u2014 out of the ordinary",
    ]
    flags = _session_flags(sess, call_dirs)
    out += [f"- {flag}" for flag in flags] or ["- none detected"]

    by_call: Dict[str, list] = {}
    for rel, parts, size in rows:
        key = parts[0] if parts[0].startswith("L1_call_") else ""
        by_call.setdefault(key, []).append((rel, parts, size))

    for call in call_dirs:
        call_rows = by_call.get(call.name, [])
        status = _session_json(call / "pipeline_status.json") or {}
        out += [
            "",
            f"## {call.name} \u2014 status {status.get('status') or '?'}"
            + (f", {status.get('sweep_method')}" if status.get("sweep_method") else "")
            + f", {len(call_rows)} files",
            "### Core artifacts",
        ]
        core = [(rel, size) for rel, parts, size in call_rows if _session_file_is_core(parts)]
        out += [f"- `{rel}` ({size} bytes)" for rel, size in core] or ["- (none)"]
        groups: Dict[str, list] = {}
        for rel, parts, size in call_rows:
            if not _session_file_is_core(parts):
                groups.setdefault(_session_group_key(parts), []).append((parts, size))
        if groups:
            out.append("### Other folders (count only; ask by prefix)")
            for key, items in sorted(groups.items()):
                sample = ", ".join(dict.fromkeys(parts[-1] for parts, _ in items[:3]))
                out.append(
                    f"- `{key}` \u2014 {len(items)} files, "
                    f"{_session_kb(sum(size for _, size in items))} (e.g. {sample})"
                )
    root_rows = by_call.get("", [])
    if root_rows:
        out += ["", f"## Session root \u2014 {len(root_rows)} files"]
        out += [f"- `{rel}` ({size} bytes)" for rel, _, size in root_rows[:_SESSION_ROOT_ROW_CAP]]
        if len(root_rows) > _SESSION_ROOT_ROW_CAP:
            out.append(f"- \u2026 {len(root_rows) - _SESSION_ROOT_ROW_CAP} more")
    return "\n".join(out)


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
        relative = target.relative_to(sess.resolve())
    except ValueError:
        return f"_(refused: path '{relative_path}' escapes session dir)_"
    if tuple(part.lower() for part in relative.parts[:2]) == _RECONSTRUCTION_INTERNAL_PARTS:
        return "_(internal reconstruction records are not analysis evidence)_"
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
#  Output-rendering helpers
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
        # Without an explicit report status, l1_analysis.json proves a
        # successful terminal commit; l1_report.md alone does not.
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


def _l0_reasoning_seconds(
    result: AgentTurnResult,
    start_index: int = 0,
    untimed_tools: tuple[str, ...] = ("dispatch_l1_pipeline",),
) -> float:
    """Wall time of one L0 turn minus the untimed tools it ran.

    Mirrors the engine's time-budget credit for ``untimed_tools``: only
    L0's own reasoning counts.  ``start_index`` skips tool-history entries
    the turn inherited from an earlier turn or a crash recovery.
    """
    untimed_s = sum(
        float(call.get("elapsed_s") or 0.0)
        for call in list(result.tool_history)[start_index:]
        if str(call.get("tool") or "") in untimed_tools
    )
    return max(0.0, float(result.elapsed_seconds or 0.0) - untimed_s)


def _bounce_budget_line(turns_left: int, seconds_left: float, seconds_pool: float) -> str:
    """Budget sentence for a bounce notice — only near the limit of the pool.

    Shown when at most two turns are left in the bounce pool, or when three
    quarters of its reasoning time are spent; otherwise "".
    """
    near_turns = turns_left <= 2
    near_time = seconds_pool > 0 and seconds_left <= 0.25 * seconds_pool
    if not (near_turns or near_time):
        return ""
    return (
        f"Host budget: {turns_left} turn(s) and about {max(0, int(seconds_left))} s "
        "of reasoning time remain for the returned turns (pipeline wall time is "
        "not counted)."
    )


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

    Each entry stores arguments under ``arguments``. The summary table
    and per-call detail blocks include the full arguments JSON, the LLM's
    reasoning excerpt, and a result preview for transcript inspection.
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

@analysis_entrypoint
def run(
    user_request: str,
    *,
    session_dir: str | Path,
    debug: bool = False,
    estimate_missing_equilibria: Optional[bool] = None,
    l0_max_iterations: Optional[int] = None,
    l0_reasoning_timeout_s: Optional[float] = None,
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
    _prepare_l0_run(
        sess,
        _l0_resume_identity(
            user_request,
            estimate_missing_equilibria=effective_estimation,
        ),
    )

    # Hooks (history + stats live at the L0 level so they capture
    # ALL L1 sub-agent calls, not just one).
    history = AnalysisHistoryRecorder(session_dir=sess)
    stats   = AnalysisStatsRecorder(session_dir=sess)
    working_mem = AnalysisWorkingMemory(session_dir=sess)
    seed_working_memory(working_mem)

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

    def dispatch_system(purpose: str = "", tasks: Any = None) -> str:
        """Dispatch one L1 system."""
        return dispatch_l1_pipeline(str(purpose or "").strip(), str(tasks or "").strip())

    # Tool registry (L1 dispatch + session catalog + per-file reader so
    # L0 can quote actual numerics from envelope CSVs / verdict.md).
    tools: Dict[str, Callable] = {
        "dispatch_l1_pipeline": dispatch_system,
        "list_session_files":   _list_session_files,
        "read_session_file":    _read_session_file,
    }
    tools = reconstruction_reads(tools)

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
    t0 = native_clock(__name__, "time", time.time)
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
    system_prompt = saved_l0_prompt(system_prompt, user_request, initial_memory, tools)
    result: AgentTurnResult = agent_turn(
        user_request,
        system_prompt=system_prompt,
        tools=tools,
        memory=initial_memory,
        client=client,
        max_iterations=effective_l0_max_iterations,
        timeout=effective_l0_reasoning_timeout_s,
        # A prose reply before any tool call is not re-asked here: the fact
        # reaches the LV review as a screening check, which returns the turn
        # by default unless the reviewer waives it — see the LV loop below.
        hooks=_engine_agent_hooks.engine_hooks,
        # Each dispatch_l1_pipeline call runs a full L1 sub-pipeline
        # (200-450s of deterministic solve + sub-agent reasoning). Exclude
        # that wall-clock from the L0 turn budget so only the L0's own
        # reasoning counts against MAX_TURN_SECONDS — mirrors the L1
        # subagent excluding its pipeline tool. Without this, a multi-call
        # orchestration (e.g. a 3x3 metal x ligand matrix) exhausts the
        # 600s budget during dispatch and truncates the final synthesis.
        untimed_tools={"dispatch_l1_pipeline"},
    )
    l0_iterations = result.iterations

    # ── LV review of the final answer, with execution bounces ──────────
    lv_reviews: list[Dict[str, Any]] = []
    lv_bounces = 0
    # The LV client is derived from the L0 client's class, so a client
    # family that carries L0 (production, or a stand-in in a test) carries
    # the review too; a class without ``for_lv`` leaves LV skipped.
    lv_client_factory = getattr(type(client), "for_lv", None)
    if not bool(getattr(cfg, "LV_VALIDATOR_ENABLED", False)):
        lv_enabled, lv_skip_reason = False, "LV validation disabled"
    elif not callable(lv_client_factory):
        lv_enabled, lv_skip_reason = False, "L0 client offers no LV client"
    else:
        lv_enabled, lv_skip_reason = True, None
    # Neither LV's reviews nor the bounce turns are charged to L0's own
    # turn cap or reasoning clock: each review runs under LV_MAX_ITERATIONS
    # / LV_MAX_SECONDS, and the bounce turns share a pool of their own,
    # fixed here from what the main turn left unused: L0's unused turns +
    # L0_BOUNCE_EXTRA_TURNS, and (L0's unused reasoning time +
    # L0_BOUNCE_EXTRA_SECONDS) × L0_BOUNCE_TIME_FACTOR (dispatch wall time
    # excluded, as in the main turn).  All three figures are reported
    # side by side.
    l0_turn_cap = int(effective_l0_max_iterations or cfg.MAX_TOOL_ITERATIONS)
    l0_time_cap = float(effective_l0_reasoning_timeout_s or cfg.MAX_TURN_SECONDS)
    l0_main_iterations = result.iterations
    l0_main_reasoning_s = _l0_reasoning_seconds(result, 0)
    bounce_turns_pool = (
        max(0, l0_turn_cap - l0_main_iterations)
        + int(getattr(cfg, "L0_BOUNCE_EXTRA_TURNS", 5) or 0)
    )
    bounce_seconds_pool = (
        max(0.0, l0_time_cap - l0_main_reasoning_s)
        + float(getattr(cfg, "L0_BOUNCE_EXTRA_SECONDS", 300) or 0)
    ) * float(getattr(cfg, "L0_BOUNCE_TIME_FACTOR", 2.0) or 1.0)
    bounce_iterations = 0
    bounce_reasoning_s = 0.0
    lv_elapsed_s = 0.0
    lv_stop_reason: Optional[str] = None
    # Escalation facts: how many tool calls the last returned turn made
    # (None before any return) and how many returns went unanswered by
    # any call.  LV reads them in the host checks and escalates its own
    # notice; the host adds a fixed escalation paragraph as well.
    last_bounce_tool_calls: Optional[int] = None
    ignored_bounces = 0
    if lv_enabled:
        lv_client = lv_client_factory()
        min_bounce_s = float(getattr(cfg, "L0_BOUNCE_MIN_SECONDS", 30) or 0)
        while True:
            turns_left = bounce_turns_pool - bounce_iterations
            seconds_left = bounce_seconds_pool - bounce_reasoning_s
            snapshot = working_mem.as_dict()
            checks = lv_host_checks(
                answer=result.answer,
                final_context=result.final_context,
                tool_history=result.tool_history,
                round_number=round_number,
                timed_out=bool(result.timed_out),
                l1_execution_runs=_collect_l1_execution_runs(sess, snapshot),
                l1_reviews=_collect_l1_validation_reviews(sess, snapshot),
                bounce_turns_remaining=turns_left,
                bounce_seconds_remaining=seconds_left,
                bounce_round=lv_bounces,
                bounce_turn_tool_calls=last_bounce_tool_calls,
                previous_notices=[r.get("notice") or "" for r in lv_reviews],
            )
            lv = lv_review(
                user_request=user_request,
                answer=result.answer,
                final_context=result.final_context,
                system_prompt=system_prompt,
                session_dir=sess,
                host_checks=checks,
                attempt=len(lv_reviews) + 1,
                debug=debug,
                client=lv_client,
            )
            lv["host_check_flags"] = [c.get("flag") for c in checks]
            lv_elapsed_s += float(lv.get("elapsed_s") or 0.0)
            lv_reviews.append(lv)
            history.log(
                "LV_review",
                attempt=len(lv_reviews),
                verdict=lv.get("verdict"),
                reviewer_verdict=lv.get("agent_verdict"),
                hints=lv.get("hints"),
                host_check_flags=lv["host_check_flags"],
                waived=sorted(lv.get("waived") or {}),
                enforced=list(lv.get("enforced_checks") or []),
            )
            if lv.get("verdict") != LV_EXECUTION_FAILURE:
                break
            if turns_left < 1:
                lv_stop_reason = f"bounce turn pool spent ({bounce_turns_pool} turns)"
                break
            if seconds_left < min_bounce_s:
                lv_stop_reason = (
                    f"{seconds_left:.0f}s of the bounce time pool left "
                    f"({bounce_seconds_pool:.0f}s), under the {min_bounce_s:.0f}s "
                    "a bounce needs"
                )
                break
            lv_bounces += 1
            lv_text = lv.get("notice") or "; ".join(lv.get("hints") or [])
            # Skeletons: every tool LV's notice names, plus the dispatch
            # tool when the turn called nothing at all or the no-dispatch
            # screening check is in force.
            skeleton_names = [name for name in sorted(tools) if name in lv_text]
            enforced_checks = set(lv.get("enforced_checks") or [])
            if ("no_tool_called" in lv["host_check_flags"]
                    or "no_l1_dispatch" in enforced_checks) \
                    and "dispatch_l1_pipeline" not in skeleton_names \
                    and "dispatch_l1_pipeline" in tools:
                skeleton_names.insert(0, "dispatch_l1_pipeline")
            notice = lv_bounce_notice(
                lv_text,
                tool_names=sorted(tools),
                example_calls=[lv_call_skeleton(n, tools[n]) for n in skeleton_names],
                budget_line=_bounce_budget_line(
                    turns_left, seconds_left, bounce_seconds_pool
                ),
                bounce_number=lv_bounces,
                ignored_bounces=ignored_bounces,
            )
            history.log(
                "L0_execution_bounce",
                bounce=lv_bounces,
                ignored_bounces=ignored_bounces,
                skeletons=skeleton_names,
                turns_left=turns_left,
                seconds_left=round(seconds_left, 1),
                notice_chars=len(notice),
            )
            previous_calls = len(result.tool_history)
            result = agent_turn(
                notice,
                system_prompt=system_prompt,
                tools=tools,
                memory=initial_memory,
                client=client,
                max_iterations=turns_left,
                timeout=max(1, int(seconds_left)),
                hooks=_engine_agent_hooks.engine_hooks,
                untimed_tools={"dispatch_l1_pipeline"},
                # A returned turn reads session files to repair the answer.
                # The engine's stage compaction would reduce a batch of reads
                # to a 200-char note per file, and its cache does not outlive
                # the turn, so L0 would read the same files again on the next
                # return. Reads in a returned turn come back in full; the main
                # turn above keeps the default compaction.
                uncompacted_tools={"read_session_file", "list_session_files"},
                initial_tool_history=result.tool_history,
            )
            bounce_iterations += result.iterations
            bounce_reasoning_s += _l0_reasoning_seconds(result, previous_calls)
            l0_iterations = l0_main_iterations + bounce_iterations
            last_bounce_tool_calls = len(result.tool_history) - previous_calls
            if last_bounce_tool_calls == 0:
                ignored_bounces += 1

    elapsed = native_clock(__name__, "time", time.time) - t0
    history.log(
        "L0_end",
        elapsed_s=elapsed,
        iterations=l0_iterations,
        l0_main_iterations=l0_main_iterations,
        l0_main_reasoning_s=round(l0_main_reasoning_s, 1),
        timed_out=result.timed_out,
        lv_bounces=lv_bounces,
        bounce_iterations=bounce_iterations,
        bounce_reasoning_s=round(bounce_reasoning_s, 1),
        lv_elapsed_s=round(lv_elapsed_s, 1),
    )

    stats.incr("L0", "iterations", l0_iterations)
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
        "iterations": l0_iterations,
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
        # Scientific acceptance metadata is included only when enrichment
        # is enabled.
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
    # LV review of L0's synthesis.  ``complete`` only on a committed
    # ``supported``; an ``execution_failure`` that survived the bounce
    # budget keeps its own name so the verdict can carry it.
    if lv_enabled and lv_reviews:
        lv_last = lv_reviews[-1]
        manifest["phases"]["l0_synthesis_review"] = {
            "status": (
                "complete"
                if lv_last.get("verdict") == "supported" and lv_last.get("committed")
                else "incomplete"
            ),
            "lv_verdict": lv_last.get("verdict"),
            "reviewer_verdict": lv_last.get("agent_verdict"),
            "hints": lv_last.get("hints") or [],
            "waived_checks": dict(lv_last.get("waived") or {}),
            "enforced_checks": list(lv_last.get("enforced_checks") or []),
            "reviews": lv_reviews,
            "bounces": lv_bounces,
            "bounces_not_acted_on": ignored_bounces,
            "bounce_stop_reason": lv_stop_reason,
            # Three separate budgets: L0's main turn against its own caps,
            # the bounce turns against theirs, and LV's review time.
            "l0_budget": {
                "turns_used": l0_main_iterations,
                "turn_cap": l0_turn_cap,
                "reasoning_s": round(l0_main_reasoning_s, 1),
                "reasoning_cap_s": l0_time_cap,
            },
            "bounce_budget": {
                "turns_pool": bounce_turns_pool,
                "reasoning_pool_s": round(bounce_seconds_pool, 1),
                "turns_used": bounce_iterations,
                "reasoning_s": round(bounce_reasoning_s, 1),
            },
            "lv_elapsed_s": round(lv_elapsed_s, 1),
            "skipped_reason": (
                None
                if lv_last.get("verdict") == "supported" and lv_last.get("committed")
                else f"LV verdict {lv_last.get('verdict')}"
            ),
        }
    else:
        manifest["phases"]["l0_synthesis_review"] = {
            "status": "skipped",
            "skipped_reason": lv_skip_reason or "LV validation disabled",
            "lv_verdict": "not_run",
            "reviews": [],
            "bounces": 0,
        }
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
        "completed_at": native_clock(__name__, "time", time.time),
        "manifest_sha256": file_sha256(sess / "manifest.json"),
        "answer_sha256": (
            file_sha256(sess / "answer.md")
            if (sess / "answer.md").is_file() else None
        ),
    })

    # Verdict
    verdict = run_verdict(sess) if (sess / "manifest.json").exists() else {
        "verdict": "unknown", "notes": []
    }
    if lv_reviews:
        verdict["lv"] = {
            "verdict": lv_reviews[-1].get("verdict"),
            "hints": lv_reviews[-1].get("hints") or [],
            "bounces": lv_bounces,
        }
        if lv_reviews[-1].get("verdict") == LV_EXECUTION_FAILURE:
            # L0 ended on an intention after every allowed bounce: the run
            # is an LLM execution failure, not a scientific one.  The
            # deterministic phase notes are kept beneath the label.
            verdict["verdict"] = "llm_execution_failure"
    save_final_context(sess, verdict)

    log.info(
        "L0 done: %d iterations (%d main + %d bounce), %.1fs wall (L0 reasoning "
        "%.1fs, bounce turns %.1fs, LV %.1fs), %d tool calls, LV %s (%d bounce%s)",
        l0_iterations, l0_main_iterations, bounce_iterations, elapsed,
        l0_main_reasoning_s, bounce_reasoning_s, lv_elapsed_s, len(result.tool_history),
        (lv_reviews[-1].get("verdict") if lv_reviews else "disabled"),
        lv_bounces, "" if lv_bounces == 1 else "s",
    )
    response = {
        "answer":       final_answer,
        "iterations":   l0_iterations,
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
        "lv_reviews":   lv_reviews,
        "lv_bounces":   lv_bounces,
        "lv_elapsed_s": lv_elapsed_s,
        "verdict":      verdict,
    }
    if l0_budget_override_used:
        response["l0_budget"] = manifest["l0_budget"]
    return response


__all__ = ["run"]
