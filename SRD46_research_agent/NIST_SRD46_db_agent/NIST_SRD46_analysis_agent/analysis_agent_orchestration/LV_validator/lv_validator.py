"""LV — review of the L0 orchestrator's final answer (one LLM agent turn).

After L0 returns its final answer, :func:`review` runs a read-only reviewer
over the answer, L0's system prompt, L0's own conversation, the L1 reports
and a block of host checks, and returns a verdict::

    {"verdict": "execution_failure" | "supported" | "contradicted" | "inconclusive",
     "hints": [<issue strings>], "notice": <message for L0 or "">,
     "committed": bool, "timed_out": bool, "agent_turn_timed_out": bool,
     "elapsed_s": float}

The reviewer works in two steps inside the same turn.  Step 1 checks whether
the required work was performed or a limitation was established with evidence.
Unjustified omissions receive ``execution_failure`` with the action L0 must
take, and the orchestrator gives L0 the turn back with :func:`bounce_notice`.
The loop continues until that execution check is resolved or its remaining
turn / reasoning-time budget is spent; those budgets are shown as fact rows.
Step 2 assesses the claims against the requested system, the pipeline's
instructions and capabilities, and the underlying evidence. Agreement with
an L1 report alone does not establish scientific correctness. Only
``execution_failure`` bounces; the other verdicts are recorded in the
manifest phase ``l0_synthesis_review``.

Host checks (:func:`host_checks`) are deterministic flags computed from the
run records — tool calls made, host notices sent, phase statuses.  The
flags in :data:`SCREENING_FLAGS` are *screening checks*: each one returns
the turn to L0 with its notice by default, whatever verdict the reviewer
commits and whether or not it commits one.  The reviewer releases a
screening check only by an explicit ``waive_host_check(flag, reason)``
call; a check it did not waive is enforced by the host regardless of the
reviewer's verdict. The validity of a waiver remains the reviewer's judgment.
The other rows are facts
for the reviewer to weigh and never return the turn by themselves.

With ``LV_WRITE_ARTIFACTS`` on (off by default) the LLM content is persisted
under ``<session_dir>/LV/`` (``agent_response*.md`` + ``lv_tool_calls*.md`` +
``verdict*.json``), one suffix per review attempt; off, no ``LV`` folder is
created and the review's record is what the orchestrator writes to the
manifest phase ``l0_synthesis_review`` and the run history.
"""
from __future__ import annotations

import inspect
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ....general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
    AgentTurnResult,
)
from ....general_db_query_engine.general_subagent_skill_schema_and_parser import (
    parse_workflow,
)
from ....general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from ...analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from ...analysis_agent_argo_engine.argo_client import SRD46AnalysisClient
from ...analysis_reconstruction import reconstruction_reads
from ...SRD46_analysis_argo_config import AGENT_CONFIG as cfg

log = logging.getLogger("Analysis.LV")

_HERE = Path(__file__).absolute().parent
_WORKFLOW_PATH = _HERE / "LV_validator_workflow.md"

EXECUTION_FAILURE = "execution_failure"
_VALID_VERDICTS = {EXECUTION_FAILURE, "supported", "contradicted", "inconclusive"}
_HINT_REQUIRED = {EXECUTION_FAILURE, "contradicted"}
_READ_DEFAULT_MAX_CHARS = 8000
_READ_HARD_MAX_CHARS = 60000
_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".bin"}
_SYSTEM_PROMPT_HEADER = "## System Prompt\n"
_CONTEXT_CUT_NOTE = "[… {omitted} earlier characters of the conversation omitted …]\n"
EXECUTION_INCOMPLETE_TAG = "[EXECUTION INCOMPLETE]"

# Host notice tags the engine (or this module) may have sent L0 during the
# turn; their occurrence in the conversation is reported as a flag.
_HOST_NOTICE_TAGS = (
    "[NO TOOL CALLED]", "[EMPTY REPLY]", "[REPLY CUT OFF]", "[REPLY STOPPED]",
    "[TOOL CALL FORMAT]", "[ANSWER CUT OFF]", "[ANSWER JOIN FAILED]",
    "[TERMINAL COMMIT MISSING]", EXECUTION_INCOMPLETE_TAG,
)
# Text the engine appends to a compacted tool-result batch.
_COMPACTION_MARKER = "inspect_batch_result(tool_number)"
_INSPECT_TOOL = "inspect_batch_result"
_CALL_VALUE_PLACEHOLDER = "<value>"
# Screening checks: each returns the turn to L0 unless the reviewer waives
# it.  Every other flag ``host_checks`` emits is a fact row.
SCREENING_FLAGS = (
    "no_tool_called",
    "bounce_not_acted_on",
    "no_l1_dispatch",
    "compacted_results_not_inspected",
    "l1_execution_incomplete",
    "l1_review_unsettled",
)
_SCREENING_MARK = "returns the turn"


# ════════════════════════════════════════════════════════════════════
#  Context preparation
# ════════════════════════════════════════════════════════════════════

def strip_system_prompt(final_context: str, system_prompt: str) -> str:
    """Return ``final_context`` without the leading ``## System Prompt`` block.

    ``agent_turn`` records the final context as the system prompt, then the
    flat prompt it sent, then the reply.  The exact system prompt is removed
    when it is known; otherwise everything up to the next ``## `` heading
    goes.  The reviewer receives L0's instructions in a block of their own
    (:func:`_user_message`), so they are not repeated inside the conversation
    and the conversation tail cut never eats into them.
    """
    text = final_context or ""
    if not text.startswith(_SYSTEM_PROMPT_HEADER):
        return text
    exact = f"{_SYSTEM_PROMPT_HEADER}{system_prompt}\n\n"
    if system_prompt and text.startswith(exact):
        return text[len(exact):]
    marker = "\n\n## "
    cut = text.find(marker, len(_SYSTEM_PROMPT_HEADER))
    return text[cut + 2:] if cut >= 0 else ""


def _context_tail(context: str, limit: int) -> str:
    if limit <= 0 or len(context) <= limit:
        return context
    omitted = len(context) - limit
    return _CONTEXT_CUT_NOTE.format(omitted=omitted) + context[-limit:]


def _collect_l1_reports(session_dir: Path) -> List[Dict[str, str]]:
    reports: List[Dict[str, str]] = []
    for call_dir in sorted(session_dir.glob("L1_call_*")):
        path = call_dir / "l1_report.md"
        if not path.is_file():
            continue
        reports.append({
            "call_dir": call_dir.name,
            "path": f"{call_dir.name}/l1_report.md",
            "text": path.read_text(encoding="utf-8", errors="replace").strip(),
        })
    return reports


# ════════════════════════════════════════════════════════════════════
#  Host checks — deterministic warning flags
# ════════════════════════════════════════════════════════════════════

def _successful_tool_names(tool_history: List[dict]) -> set:
    names: set = set()
    for entry in tool_history or []:
        name = str(entry.get("tool") or "")
        result = str(entry.get("result_full") or "").lstrip().lower()
        if not name:
            continue
        if result.startswith("error:") or result.startswith('{"error"') \
                or result.startswith("[validation "):
            continue
        names.add(name)
    return names


def _check(flag: str, detail: str, suggested_notice: str = "") -> Dict[str, str]:
    row = {"flag": flag, "detail": detail}
    if suggested_notice:
        row["suggested_notice"] = suggested_notice
    return row


_PREVIOUS_NOTICE_CHARS = 400


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _ordinal(n: int) -> str:
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def host_checks(
    *,
    answer: str,
    final_context: str,
    tool_history: List[dict],
    round_number: int = 1,
    timed_out: bool = False,
    l1_execution_runs: Optional[List[Dict[str, Any]]] = None,
    l1_reviews: Optional[List[Dict[str, Any]]] = None,
    dispatch_tool: str = "dispatch_l1_pipeline",
    bounce_turns_remaining: Optional[int] = None,
    bounce_seconds_remaining: Optional[float] = None,
    bounce_round: int = 0,
    bounce_turn_tool_calls: Optional[int] = None,
    previous_notices: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Screening checks and fact rows computed from the run records.

    Flags: ``no_tool_called``, ``bounce_not_acted_on``, ``no_l1_dispatch``,
    ``compacted_results_not_inspected``, ``host_notices``,
    ``l0_limit_reached``, ``l1_execution_incomplete``,
    ``l1_review_unsettled``; data rows ``previous_notices`` (the notices
    sent on earlier returns of the turn), ``dispatch_calls``,
    ``answer_chars`` and, when known, the turns and reasoning seconds left
    in the pool the returned turns draw on (separate from L0's own budget),
    always follow.  ``bounce_round`` is how many times the turn has been
    returned so far and ``bounce_turn_tool_calls`` how many tool calls the
    last returned turn made. Screening checks return the turn unless explicitly
    waived; other rows inform the review without forcing a return.
    """
    history = list(tool_history or [])
    called = {str(h.get("tool") or "") for h in history}
    successful = _successful_tool_names(history)
    context = final_context or ""
    rows: List[Dict[str, str]] = []

    if not history:
        rows.append(_check(
            "no_tool_called",
            "the turn made no tool call",
            "Your reply ended the turn without any tool call; the host runs a "
            "tool only when the reply itself contains the call. If the task "
            "needs a tool, call it now. A refusal must identify a verified "
            "limitation supported by your pipeline instructions or session "
            "evidence; missing outputs alone do not establish one.",
        ))
    rounds = int(bounce_round or 0)
    if rounds >= 1 and int(bounce_turn_tool_calls or 0) == 0:
        rows.append(_check(
            "bounce_not_acted_on",
            f"the host returned the turn {rounds} time(s); the last returned "
            "turn made no tool call and ended in prose again",
            "The previous notice was not acted on: your reply contained no tool "
            "call. Do not describe what you will do; put the call in this reply.",
        ))
    earlier = [str(n or "").strip() for n in (previous_notices or []) if str(n or "").strip()]
    if earlier:
        rows.append(_check(
            "previous_notices",
            "; ".join(
                f"#{i}: «{_shorten(text, _PREVIOUS_NOTICE_CHARS)}»"
                for i, text in enumerate(earlier, start=1)
            ),
        ))
    dispatch_calls = sum(1 for h in history if str(h.get("tool") or "") == dispatch_tool)
    if int(round_number or 1) <= 1 and dispatch_tool not in successful:
        rows.append(_check(
            "no_l1_dispatch",
            f"round {int(round_number or 1)} ended without a successful "
            f"{dispatch_tool} call",
            "No successful dispatch_l1_pipeline call is recorded for this round. "
            "Check any recorded attempt and failure. If the requested calculation "
            "remains unattempted, dispatch it now. If existing evidence answers "
            "the request or a verified limitation prevents the calculation, "
            "identify that evidence and its scope. Missing outputs alone do not "
            "show that the pipeline cannot calculate the system.",
        ))
    if _COMPACTION_MARKER in context and _INSPECT_TOOL not in called:
        rows.append(_check(
            "compacted_results_not_inspected",
            "the host replaced a batch of tool results by a summary table and "
            "the full outputs were never read",
            "A batch of tool results was shown to you only as a summary table "
            "and the full outputs were never read. Read them — with the tool "
            "named in the summary note or from the session files — before "
            "concluding.",
        ))
    notices = [
        f"{tag} ×{context.count(tag)}" for tag in _HOST_NOTICE_TAGS if tag in context
    ]
    if notices:
        rows.append(_check(
            "host_notices",
            "host notices sent during the turn: " + ", ".join(notices),
        ))
    if timed_out:
        rows.append(_check(
            "l0_limit_reached",
            "L0 reached its iteration or reasoning-time limit; the answer may "
            "be partial",
        ))
    failed_runs = [
        str(run.get("call_dir") or "?")
        + (f" ({run.get('stage')}: {run.get('error')})" if run.get("error") else
           f" (status {run.get('status')})")
        for run in (l1_execution_runs or [])
        if str(run.get("status") or "").lower() != "ok"
    ]
    if failed_runs:
        rows.append(_check(
            "l1_execution_incomplete",
            "L1 calls that did not complete the deterministic pipeline: "
            + "; ".join(failed_runs),
            "The pipeline did not complete for " + ", ".join(
                r.split(" ")[0] for r in failed_runs
            ) + ". Inspect the recorded stage and cause; complete any remaining "
            "feasible requested work or report the observed failure with its "
            "scope. Do not turn an execution error into a claim of scientific "
            "impossibility or repeat an identical deterministic failure.",
        ))
    unsettled = []
    for rev in (l1_reviews or []):
        if rev.get("validation_enabled") is False:
            continue
        verdict = str(rev.get("verdict") or "not_run").lower()
        settled = (
            verdict == "supported"
            and bool(rev.get("committed"))
            and not bool(rev.get("timed_out"))
            and bool(rev.get("l1_report_committed", True))
        )
        if not settled:
            why = verdict
            if not bool(rev.get("l1_report_committed", True)):
                why += ", report not committed"
            if bool(rev.get("timed_out")) and verdict not in {"contradicted", "inconclusive"}:
                why += ", review not completed"
            unsettled.append(f"{rev.get('call_dir') or '?'}: {why}")
    if unsettled:
        rows.append(_check(
            "l1_review_unsettled",
            "L1 reports whose LD review did not end supported: "
            + "; ".join(unsettled),
            "The report of " + ", ".join(u.split(":")[0] for u in unsettled)
            + " was not confirmed by its review. Inspect the recorded issue "
            "and correct or qualify the affected claims accordingly. A caveat "
            "does not make a contradicted claim correct or a result validated.",
        ))
    rows.append(_check("dispatch_calls", str(dispatch_calls)))
    rows.append(_check("answer_chars", str(len(answer or ""))))
    if bounce_turns_remaining is not None:
        rows.append(_check(
            "bounce_turns_remaining",
            f"{int(bounce_turns_remaining)} tool turn(s) left in the pool the "
            "returned turns draw on (separate from L0's own budget)",
        ))
    if bounce_seconds_remaining is not None:
        rows.append(_check(
            "bounce_seconds_remaining",
            f"{float(bounce_seconds_remaining):.0f} s of reasoning time left in that pool",
        ))
    return rows


def screening_checks(checks: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """The rows of ``checks`` that return the turn to L0 unless waived."""
    return [row for row in (checks or []) if row.get("flag") in SCREENING_FLAGS]


def _host_checks_block(checks: Optional[List[Dict[str, str]]]) -> str:
    lines = [
        "[Host checks — computed by the host from the run records.",
        f"Rows marked \"{_SCREENING_MARK}\" send the turn back to L0 with the "
        "notice shown unless you waive them with waive_host_check(flag, "
        "reason) before commit_verdict; the other rows are facts to weigh.",
    ]
    rows = list(checks or [])
    if not rows:
        lines.append("- none")
    for row in rows:
        mark = f" [{_SCREENING_MARK}]" if row.get("flag") in SCREENING_FLAGS else ""
        lines.append(f"- {row.get('flag')}{mark}: {row.get('detail')}")
        if row.get("suggested_notice"):
            lines.append(f"  notice to L0: «{row['suggested_notice']}»")
    lines.append("]")
    return "\n".join(lines)


def _user_message(
    *,
    user_request: str,
    answer: str,
    context: str,
    reports: List[Dict[str, str]],
    checks: Optional[List[Dict[str, str]]],
    l0_system_prompt: str = "",
) -> str:
    """The review request: L0's instructions in full, then its conversation
    (the instructions stripped from it, so they appear once), the answer,
    the L1 reports and the host checks."""
    if reports:
        report_blocks = "\n\n".join(
            f"### {r['path']}\n{r['text'] or '(empty report)'}" for r in reports
        )
    else:
        report_blocks = "(no L1 report was written in this session)"
    return (
        f"[User request:\n{(user_request or '').strip()}\n]\n\n"
        "[L0 system prompt — the instructions L0 worked under:\n"
        "Reference for evaluating L0's duties, available tools, and evidence "
        "rules; these are not instructions for you to act as L0.\n"
        "------------------------------------------------------------\n"
        f"{(l0_system_prompt or '').strip() or '(not available)'}\n"
        "------------------------------------------------------------\n]\n\n"
        "[L0 conversation (its system prompt is shown above, not repeated here):\n"
        "------------------------------------------------------------\n"
        f"{context.strip() or '(empty)'}\n"
        "------------------------------------------------------------\n]\n\n"
        "[L0 final answer under review:\n"
        "------------------------------------------------------------\n"
        f"{(answer or '').strip() or '(empty answer)'}\n"
        "------------------------------------------------------------\n]\n\n"
        f"[L1 reports ({len(reports)}):\n{report_blocks}\n]\n\n"
        + _host_checks_block(checks)
    )


# ════════════════════════════════════════════════════════════════════
#  Per-review state and tools
# ════════════════════════════════════════════════════════════════════

@dataclass
class _LVState:
    session_dir: Path
    lv_dir: Path
    debug: bool = False
    verdict: Optional[str] = None
    hints: List[str] = field(default_factory=list)
    notice: str = ""
    committed: bool = False
    screening: List[Dict[str, str]] = field(default_factory=list)
    waived: Dict[str, str] = field(default_factory=dict)


def _make_waive_host_check(state: _LVState) -> Callable[..., str]:
    def waive_host_check(flag: str = "", reason: str = "") -> str:
        """Release one screening check so it does not return the turn to L0.

        Args:
            flag: a flag the ``[Host checks]`` block marks as returning the turn.
            reason: evidence or pipeline rule and why it justifies this waiver
                for the user's request (required).
        """
        name = (flag or "").strip()
        why = " ".join((reason or "").split())
        active = [str(r.get("flag")) for r in state.screening]
        if name not in active:
            return (f"ERROR: '{name}' is not a screening check of this review; "
                    f"those are: {', '.join(active) or 'none'}.")
        if not why:
            return f"ERROR: waiving '{name}' needs a reason."
        state.waived[name] = why
        left = [f for f in active if f not in state.waived]
        return (f"OK — '{name}' waived. "
                + (f"Still returning the turn unless waived: {', '.join(left)}."
                   if left else "No screening check returns the turn now."))

    return waive_host_check


def _make_list_session_files(state: _LVState) -> Callable[..., str]:
    def list_session_files(folder: str = "") -> str:
        """List session files: L1 reports and solver verdicts first, then the rest.

        Args:
            folder: optional path prefix; list that folder in full.
        """
        base = state.session_dir
        prefix = (folder or "").strip().replace("\\", "/").strip("/")
        root = (base / prefix).resolve() if prefix else base.resolve()
        try:
            root.relative_to(base.resolve())
        except ValueError:
            return f"_(refused: folder '{folder}' escapes the session dir)_"
        if not root.is_dir():
            return f"_(no such folder: '{folder}')_"
        files = sorted(p for p in root.rglob("*") if p.is_file())
        if not files:
            return "_(no files)_"
        rel = [p.resolve().relative_to(base.resolve()).as_posix() for p in files]
        if prefix:
            rows = [f"# `{prefix}` ({len(rel)} files)", ""]
            rows += [f"- `{r}`" for r in rel]
            return "\n".join(rows)
        core = [
            r for r in rel
            if r.endswith("/l1_report.md")
            or ("/solver/" in r and r.endswith("_verdict.md"))
        ]
        rows = [f"# Session files ({len(rel)} files)", "", "## L1 reports and solver verdicts"]
        rows += [f"- `{r}`" for r in core] or ["- (none)"]
        by_folder: Dict[str, int] = {}
        for r in rel:
            if r in core:
                continue
            top = r.split("/", 1)[0] if "/" in r else "."
            by_folder[top] = by_folder.get(top, 0) + 1
        rows += ["", "## Other folders (count; pass folder=<name> to list)"]
        rows += [f"- `{k}`: {v}" for k, v in sorted(by_folder.items())] or ["- (none)"]
        return "\n".join(rows)

    return list_session_files


def _make_read_session_file(state: _LVState) -> Callable[..., str]:
    def read_session_file(relative_path: str = "", max_chars: int = _READ_DEFAULT_MAX_CHARS) -> str:
        """Read one session file as text (truncated at ``max_chars``).

        Args:
            relative_path: path as listed by ``list_session_files``.
            max_chars: characters returned at most (hard cap 60000).
        """
        base = state.session_dir
        rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
        if not rel:
            return "_(empty path)_"
        target = (base / rel).resolve()
        try:
            target.relative_to(base.resolve())
        except ValueError:
            return f"_(refused: path '{relative_path}' escapes the session dir)_"
        if not target.is_file():
            return f"_(no such file: '{relative_path}')_"
        if target.suffix.lower() in _BINARY_SUFFIXES:
            return (f"_(binary file '{relative_path}', "
                    f"{target.stat().st_size} bytes — not returned)_")
        cap = max(1, min(int(max_chars or _READ_DEFAULT_MAX_CHARS), _READ_HARD_MAX_CHARS))
        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > cap
        header = (f"# `{rel}` ({target.stat().st_size} B"
                  + (f", first {cap} chars" if truncated else "") + ")\n\n")
        return header + text[:cap] + ("\n\n_(truncated)_" if truncated else "")

    return read_session_file


def _make_commit_verdict(state: _LVState) -> Callable[..., str]:
    def commit_verdict(verdict: str = "", hints: str = "", notice: str = "") -> str:
        """Commit the review verdict and end the turn (REQUIRED terminal tool).

        Args:
            verdict: one of ``execution_failure`` / ``supported`` /
                ``contradicted`` / ``inconclusive``.
            hints: newline- or comma-separated specific issues (required for
                ``execution_failure`` and ``contradicted``).
            notice: for ``execution_failure``, the message L0 receives when
                it is given the turn back — written to L0, saying what it
                must do now.
        """
        v = (verdict or "").strip().lower()
        if v not in _VALID_VERDICTS:
            return ("ERROR: verdict must be one of "
                    f"{sorted(_VALID_VERDICTS)}. Re-call commit_verdict.")
        hint_list = [h.strip() for h in re.split(r"[\n,]+", hints or "") if h.strip()]
        if v in _HINT_REQUIRED and not hint_list:
            return (f"ERROR: a '{v}' verdict requires at least one specific "
                    "hint. Re-call commit_verdict with hints.")
        state.verdict = v
        state.hints = hint_list
        state.notice = (notice or "").strip() if v == EXECUTION_FAILURE else ""
        state.committed = True
        return f"OK — verdict '{v}' recorded ({len(hint_list)} hints)."

    return commit_verdict


def _verdict_committed(receipts: List[dict]) -> bool:
    """Completion predicate: the batch holds an accepted ``commit_verdict``."""
    return any(
        str(r.get("tool") or "") == "commit_verdict"
        and str(r.get("result_full") or "").lstrip().startswith("OK")
        for r in receipts
    )


# ════════════════════════════════════════════════════════════════════
#  Persistence
# ════════════════════════════════════════════════════════════════════

def _write_artifacts(
    state: _LVState,
    result: Optional[AgentTurnResult],
    attempt: int,
    *,
    checks: Optional[List[Dict[str, str]]],
    review_timed_out: bool,
    agent_turn_timed_out: bool,
) -> None:
    suffix = "" if attempt <= 1 else f"_bounce{attempt - 1}"
    if result is not None:
        rows = [
            f"# LV Tool Calls (review {attempt})",
            "",
            "| # | iter | tool | args (excerpt) | result_chars | elapsed_s |",
            "|--:|----:|------|----------------|-------------:|----------:|",
        ]
        for i, c in enumerate(list(result.tool_history), start=1):
            args = c.get("arguments", {}) or {}
            try:
                excerpt = json.dumps(args)[:120].replace("|", "\\|")
            except Exception:
                excerpt = repr(args)[:120].replace("|", "\\|")
            rows.append(
                f"| {i} | {c.get('iteration','')} | {c.get('tool','?')} "
                f"| {excerpt} | {c.get('result_chars','')} | {c.get('elapsed_s','')} |"
            )
        try:
            (state.lv_dir / f"lv_tool_calls{suffix}.md").write_text(
                "\n".join(rows) + "\n", encoding="utf-8")
            (state.lv_dir / f"agent_response{suffix}.md").write_text(
                "# LV validator agent response\n\n"
                "## Final answer (text emitted by the agent)\n\n"
                f"{getattr(result, 'answer', '') or '_(empty)_'}\n\n"
                "## Final context\n\n"
                f"{getattr(result, 'final_context', '') or '_(empty)_'}\n",
                encoding="utf-8",
            )
        except Exception:  # pragma: no cover
            pass
    try:
        (state.lv_dir / f"verdict{suffix}.json").write_text(
            json.dumps({
                "verdict": state.verdict,
                "hints": state.hints,
                "notice": state.notice,
                "host_checks": list(checks or []),
                "screening_checks": [str(r.get("flag")) for r in state.screening],
                "waived": dict(state.waived),
                "enforced_checks": [
                    str(r.get("flag")) for r in state.screening
                    if str(r.get("flag")) not in state.waived
                ],
                "timed_out": bool(review_timed_out),
                "agent_turn_timed_out": bool(agent_turn_timed_out),
                "committed": bool(state.committed),
            }, indent=2),
            encoding="utf-8",
        )
    except Exception:  # pragma: no cover
        pass


# ════════════════════════════════════════════════════════════════════
#  Public entry points
# ════════════════════════════════════════════════════════════════════

def call_skeleton(name: str, fn: Optional[Callable]) -> Optional[str]:
    """``<tool_call>{"name": ..., "arguments": {<param>: <value>, ...}}</tool_call>``
    from ``fn``'s named parameters; the placeholder is not valid JSON on
    purpose, so a copied skeleton fails to parse instead of running."""
    if fn is None:
        return None
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return None
    named = [
        p.name for p in params
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.name != "self"
    ]
    if not named:
        return None
    arguments = ", ".join(f'"{p}": {_CALL_VALUE_PLACEHOLDER}' for p in named)
    return f'<tool_call>{{"name": "{name}", "arguments": {{{arguments}}}}}</tool_call>'


def bounce_notice(
    notice: str,
    tool_names: List[str],
    example_call: Optional[str] = None,
    budget_line: str = "",
    *,
    example_calls: Optional[List[str]] = None,
    bounce_number: int = 1,
    ignored_bounces: int = 0,
) -> str:
    """Host turn that gives L0 the turn back after an ``execution_failure``.

    ``notice`` is the reviewer's message to L0; the host adds only how a
    call is made, example skeletons, an optional budget line (the caller
    passes one only near the limit) and the callable tools.  When earlier
    returns of the turn were not acted on (``ignored_bounces`` ≥ 1), a
    fixed escalation paragraph follows the reviewer's text; the reviewer
    is expected to have escalated its own text as well.
    """
    body = (notice or "").strip() or (
        "Your last reply ended the turn with an intention, not a result; "
        "nothing you announced has happened."
    )
    lines = [f"{EXECUTION_INCOMPLETE_TAG} {body}"]
    if int(ignored_bounces or 0) >= 1:
        lines.append(
            f"This is the {_ordinal(bounce_number)} time the host returns the "
            "turn. The previous reply again contained no tool call. A reply "
            "without a tool call and without the final answer will be taken as "
            "your final answer, and the task will be closed as incomplete."
        )
    lines.append(
        "The host runs a tool only when your reply itself contains the call: "
        "one <tool_call>…</tool_call> per call, then a single <wait/>. The "
        "results come back in the next message; then give the final answer "
        "in the required format. If you decline the task on its merits, give "
        "that as your final answer with the reason."
    )
    skeletons: List[str] = []
    for call in ([example_call] if example_call else []) + list(example_calls or []):
        if call and call not in skeletons:
            skeletons.append(call)
    for call in skeletons:
        lines.append(
            f"Example call: {call}"
            + (f" — replace each {_CALL_VALUE_PLACEHOLDER} with your own."
               if _CALL_VALUE_PLACEHOLDER in call else "")
        )
    if budget_line:
        lines.append(budget_line.strip())
    lines.append("Tools you can call now: " + ", ".join(sorted(tool_names)) + ".")
    return "\n".join(lines)


def review(
    *,
    user_request: str,
    answer: str,
    final_context: str,
    system_prompt: str,
    session_dir: str | Path,
    host_checks: Optional[List[Dict[str, str]]] = None,
    attempt: int = 1,
    debug: bool = False,
    client: Any = None,
) -> Dict[str, Any]:
    """Review L0's final answer; see the module docstring for the result shape.

    On an internal failure (LLM error, no commit), the reviewer outcome is
    ``inconclusive`` with ``committed: False``. Any unwaived screening check
    still enforces ``execution_failure`` and returns the turn to L0.
    ``attempt`` numbers the review (1 = first; 2 = after the first bounce).
    """
    session_dir = Path(session_dir)
    lv_dir = session_dir / "LV"
    write_artifacts = bool(getattr(cfg, "LV_WRITE_ARTIFACTS", False))
    if write_artifacts:
        lv_dir.mkdir(parents=True, exist_ok=True)
    state = _LVState(session_dir=session_dir, lv_dir=lv_dir, debug=bool(debug),
                     screening=screening_checks(host_checks))

    workflow = parse_workflow(_WORKFLOW_PATH)
    lv_system_prompt = workflow["system_prompt"]
    tools: Dict[str, Callable] = {
        "list_session_files": _make_list_session_files(state),
        "read_session_file": _make_read_session_file(state),
        "waive_host_check": _make_waive_host_check(state),
        "commit_verdict": _make_commit_verdict(state),
    }
    tools = reconstruction_reads(tools)
    lv_system_prompt += "\n\n" + build_tool_instructions(tools)

    context = _context_tail(
        strip_system_prompt(final_context, system_prompt),
        int(getattr(cfg, "LV_CONTEXT_CHARS", 60_000) or 0),
    )
    user_message = _user_message(
        user_request=user_request,
        answer=answer,
        context=context,
        reports=_collect_l1_reports(session_dir),
        checks=host_checks,
        l0_system_prompt=system_prompt,
    )

    if client is None:
        client = SRD46AnalysisClient.for_lv()
    hooks = _build_engine_agent_hooks(working_memory_loader=lambda: "", guidance_hooks=[])

    result: Optional[AgentTurnResult] = None
    t0 = time.time()
    try:
        result = agent_turn(
            user_message,
            system_prompt=lv_system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=int(getattr(cfg, "LV_MAX_ITERATIONS", 4) or 4),
            timeout=int(getattr(cfg, "LV_MAX_SECONDS", 180) or 180),
            required_tools={"commit_verdict"},
            terminal_tools={"commit_verdict"},
            tool_completion_check=_verdict_committed,
            # A reviewer's reads are its work product: a batch of them must
            # not be stage-compacted into 200-char notes, which would make
            # it re-read the same files until its turns are gone.
            uncompacted_tools={"list_session_files", "read_session_file"},
            hooks=hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:  # pragma: no cover
        log.warning("LV agent_turn raised: %s", exc, exc_info=debug)
    elapsed = time.time() - t0

    committed = bool(state.committed and state.verdict in _VALID_VERDICTS)
    agent_verdict = state.verdict if committed else None
    if not committed:
        state.verdict = "inconclusive"
        state.notice = ""
        if not state.hints:
            state.hints = ["LV did not successfully commit a verdict; the review is inconclusive."]
    enforced = [r for r in state.screening if str(r.get("flag")) not in state.waived]
    if enforced:
        # A screening check the reviewer did not waive returns the turn,
        # whatever it committed: the reviewer's own notice (when it found an
        # execution failure) leads, the checks' notices follow.
        state.notice = _enforced_notice(
            state.notice if agent_verdict == EXECUTION_FAILURE else "",
            enforced,
            review_hints=state.hints if agent_verdict in {"contradicted", "inconclusive"} else [],
        )
        state.hints = list(state.hints) + [
            f"host check {r.get('flag')} in force: {r.get('detail')}" for r in enforced
        ]
        state.verdict = EXECUTION_FAILURE
    agent_turn_timed_out = bool(result is not None and getattr(result, "timed_out", False))
    review_timed_out = not committed
    if write_artifacts:
        _write_artifacts(
            state, result, attempt,
            checks=host_checks,
            review_timed_out=review_timed_out,
            agent_turn_timed_out=agent_turn_timed_out,
        )
    verdict = state.verdict or "inconclusive"
    log.info(
        "LV review %d: verdict=%s (reviewer %s) hints=%d waived=%s enforced=%s (%.1fs)",
        attempt, verdict, agent_verdict or "none", len(state.hints),
        sorted(state.waived) or "-", [r.get("flag") for r in enforced] or "-", elapsed,
    )
    return {
        "verdict": verdict,
        "agent_verdict": agent_verdict,
        "hints": list(state.hints),
        "notice": state.notice,
        "committed": committed,
        "screening_checks": [str(r.get("flag")) for r in state.screening],
        "waived": dict(state.waived),
        "enforced_checks": [str(r.get("flag")) for r in enforced],
        "timed_out": bool(review_timed_out),
        "agent_turn_timed_out": agent_turn_timed_out,
        "elapsed_s": round(elapsed, 1),
        "artifacts_written": write_artifacts,
    }


def _enforced_notice(
    lead: str,
    enforced: List[Dict[str, str]],
    *,
    review_hints: Optional[List[str]] = None,
) -> str:
    """The message L0 receives when screening checks stay in force.

    ``lead`` is the reviewer's own notice (empty when it committed no
    execution failure); each enforced check contributes its notice once;
    ``review_hints`` (a contradicted or inconclusive review's findings) are
    appended so L0 can act on them in the same turn.
    """
    lines: List[str] = []
    if (lead or "").strip():
        lines.append(lead.strip())
    for row in enforced:
        text = str(row.get("suggested_notice") or "").strip() or (
            f"Host check {row.get('flag')}: {row.get('detail')}."
        )
        if text not in lines:
            lines.append(text)
    hints = [h for h in (review_hints or []) if str(h).strip()]
    if hints:
        lines.append("The review also found: " + "; ".join(str(h).strip() for h in hints) + ".")
    return "\n".join(lines)


__all__ = [
    "review", "host_checks", "screening_checks", "bounce_notice", "call_skeleton",
    "strip_system_prompt", "EXECUTION_FAILURE", "EXECUTION_INCOMPLETE_TAG",
    "SCREENING_FLAGS",
]
