"""LD — analysis validator (LLM quality gate for the L1 sub-agent).

After the L1 sub-agent writes its analysis, :func:`validate` runs a small
read-only LLM reviewer that checks the prose against the raw solver
outputs on disk and returns a verdict::

    {"verdict": "supported" | "contradicted" | "inconclusive",
     "hints": [<actionable issue strings>]}

Only a ``contradicted`` verdict causes L1 to revise (bounded by
``cfg.PHASE_RETRY_BUDGET``). The reviewer never authors analysis and
never runs a calculation — it only reads ``list_outputs`` /
``read_output_file`` and commits a verdict.

All LLM content is persisted under ``<call_dir>/LD/`` (``agent_response.md``
+ ``ld_tool_calls.md`` + ``verdict.json``).

Public API
----------
``validate(*, purpose, tasks, report, call_dir, solver_dir, attempt=1,
           debug=False) -> dict``
``format_hints(hints) -> str``
"""
from __future__ import annotations

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
from ...SRD46_analysis_argo_config import AGENT_CONFIG as cfg

log = logging.getLogger("Analysis.LD")

_HERE = Path(__file__).absolute().parent
_WORKFLOW_PATH = _HERE / "LD_validator_workflow.md"
_ESTIMATION_REVIEW_PROMPT_PATH = _HERE / "estimated_equilibrium_review_prompt.md"

_VALID_VERDICTS = {"supported", "contradicted", "inconclusive"}
_READ_DEFAULT_MAX_CHARS = 8000
_READ_HARD_MAX_CHARS = 60000


# ════════════════════════════════════════════════════════════════════
#  Per-call state
# ════════════════════════════════════════════════════════════════════

@dataclass
class _LDState:
    call_dir:   Path
    solver_dir: Optional[Path]
    ld_dir:     Path
    debug:      bool = False
    verdict:    Optional[str] = None
    hints:      List[str] = field(default_factory=list)
    committed:  bool = False


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def format_hints(hints: Any) -> str:
    """Render LD hints as a markdown bullet list for an L1 retry message."""
    items = _coerce_list(hints)
    if not items:
        return ""
    return "\n".join(f"  - {h}" for h in items)


# ════════════════════════════════════════════════════════════════════
#  Tools (read-only + terminal verdict)
# ════════════════════════════════════════════════════════════════════

def _list_solver_files(state: _LDState) -> List[Path]:
    files: List[Path] = []
    if state.solver_dir is not None and Path(state.solver_dir).exists():
        files.extend(
            p for p in sorted(Path(state.solver_dir).rglob("*")) if p.is_file()
        )
    for name in ("thermodynamic_reference_constants.md", "l1_report.md"):
        candidate = Path(state.call_dir) / name
        if candidate.is_file() and candidate not in files:
            files.append(candidate)
    return files


def _rel_to_call(state: _LDState, p: Path) -> str:
    try:
        return p.resolve().relative_to(Path(state.call_dir).resolve()).as_posix()
    except Exception:
        return p.as_posix()


def _make_list_outputs(state: _LDState) -> Callable[[], str]:
    def list_outputs() -> str:
        """List the solver output files available for review."""
        files = _list_solver_files(state)
        if not files:
            return "_(no solver outputs found — the run may have failed)_"
        rows = [f"# Solver outputs ({len(files)} files)", ""]
        for p in files:
            rows.append(f"- `{_rel_to_call(state, p)}` ({p.stat().st_size} B)")
        return "\n".join(rows)

    return list_outputs


def _make_read_output_file(state: _LDState) -> Callable[..., str]:
    def read_output_file(relative_path: str = "", max_chars: int = _READ_DEFAULT_MAX_CHARS) -> str:
        """Read one output file (or ``l1_report.md``) as text."""
        base = Path(state.call_dir)
        rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
        if not rel:
            return "_(empty path)_"
        target = (base / rel).resolve()
        try:
            target.relative_to(base.resolve())
        except ValueError:
            return f"_(refused: path '{relative_path}' escapes the call dir)_"
        if not target.exists() or not target.is_file():
            return f"_(no such file: '{relative_path}')_"
        if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".bin"}:
            return (f"_(binary file '{relative_path}', "
                    f"{target.stat().st_size} bytes — not returned)_")
        cap = max(1, min(int(max_chars or _READ_DEFAULT_MAX_CHARS), _READ_HARD_MAX_CHARS))
        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > cap
        header = (f"# `{rel}` ({target.stat().st_size} B"
                  + (f", first {cap} chars" if truncated else "") + ")\n\n")
        return header + text[:cap] + ("\n\n_(truncated)_" if truncated else "")

    return read_output_file


def _make_commit_verdict(state: _LDState) -> Callable[..., str]:
    def commit_verdict(verdict: str = "", hints: str = "") -> str:
        """Commit the review verdict and end the turn (REQUIRED terminal tool).

        Args:
            verdict: one of ``supported`` / ``contradicted`` /
                ``inconclusive``.
            hints: newline- or comma-separated specific issues (required
                when ``verdict="contradicted"``).
        """
        v = (verdict or "").strip().lower()
        if v not in _VALID_VERDICTS:
            return ("ERROR: verdict must be one of "
                    f"{sorted(_VALID_VERDICTS)}. Re-call commit_verdict.")
        hint_list = [h.strip() for h in re.split(r"[\n,]+", hints or "") if h.strip()]
        if v == "contradicted" and not hint_list:
            return ("ERROR: a 'contradicted' verdict requires at least one "
                    "specific hint. Re-call commit_verdict with hints.")
        state.verdict = v
        state.hints = hint_list
        state.committed = True
        return f"OK — verdict '{v}' recorded ({len(hint_list)} hints)."

    return commit_verdict


# ════════════════════════════════════════════════════════════════════
#  Persistence
# ════════════════════════════════════════════════════════════════════

def _write_artifacts(
    state: _LDState,
    result: Optional[AgentTurnResult],
    attempt: int,
    *,
    review_timed_out: bool,
    agent_turn_timed_out: bool,
) -> None:
    suffix = "" if attempt <= 1 else f"_retry{attempt - 1}"
    if result is not None:
        rows = [
            f"# LD Tool Calls (attempt {attempt})",
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
            (state.ld_dir / f"ld_tool_calls{suffix}.md").write_text(
                "\n".join(rows) + "\n", encoding="utf-8")
            (state.ld_dir / f"agent_response{suffix}.md").write_text(
                "# LD validator agent response\n\n"
                "## Final answer (text emitted by the agent)\n\n"
                f"{getattr(result, 'answer', '') or '_(empty)_'}\n\n"
                "## Final context\n\n"
                f"{getattr(result, 'final_context', '') or '_(empty)_'}\n",
                encoding="utf-8",
            )
        except Exception:  # pragma: no cover
            pass
    try:
        (state.ld_dir / f"verdict{suffix}.json").write_text(
            json.dumps({
                           "verdict": state.verdict,
                           "hints": state.hints,
                           # ``timed_out`` is the review-level contract used
                           # by L1/L0.  Once the terminal tool committed a
                           # valid verdict the review is complete, even if the
                           # generic ReAct engine subsequently reports that it
                           # exhausted its own turn budget while unwinding.
                           "timed_out": bool(review_timed_out),
                           # Preserve the raw engine diagnostic separately so
                           # the hard-stop remains inspectable without
                           # invalidating an already committed review.
                           "agent_turn_timed_out": bool(agent_turn_timed_out),
                           "committed": bool(state.committed),
                       },
                       indent=2),
            encoding="utf-8",
        )
    except Exception:  # pragma: no cover
        pass


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def validate(
    *,
    purpose: str,
    tasks: str = "",
    report: str,
    call_dir: str | Path,
    solver_dir: Optional[str | Path] = None,
    attempt: int = 1,
    debug: bool = False,
    estimation_enabled: bool = False,
    enabled_run_facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Review an L1 analysis report against the solver outputs.

    Returns ``{"verdict": str, "hints": [str, ...]}``. On any internal
    failure (LLM error, no commit) the verdict defaults to
    ``"inconclusive"`` so the caller never blocks or loops on the gate.
    """
    call_dir = Path(call_dir)
    ld_dir = call_dir / "LD"
    ld_dir.mkdir(parents=True, exist_ok=True)
    state = _LDState(
        call_dir=call_dir,
        solver_dir=Path(solver_dir) if solver_dir else None,
        ld_dir=ld_dir,
        debug=bool(debug),
    )

    tasks_text = str(tasks or "").strip()
    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    if estimation_enabled:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n"
            + _ESTIMATION_REVIEW_PROMPT_PATH.read_text(
                encoding="utf-8"
            ).strip()
        )
    tools: Dict[str, Callable] = {
        "list_outputs":     _make_list_outputs(state),
        "read_output_file": _make_read_output_file(state),
        "commit_verdict":   _make_commit_verdict(state),
    }
    system_prompt += "\n\n" + build_tool_instructions(tools)

    body = tasks_text if tasks_text else "(none)"
    user_message = (
        f"[Purpose: {(purpose or '').strip()}]\n"
        f"[Tasks:\n{body}\n]\n\n"
        "[L1 analysis report under review:\n"
        "------------------------------------------------------------\n"
        f"{(report or '').strip() or '(empty report)'}\n"
        "------------------------------------------------------------\n]"
    )
    if estimation_enabled:
        user_message += (
            "\n\n[Deterministic enabled-run facts:\n"
            + json.dumps(enabled_run_facts or {}, indent=2, default=str)
            + "\n]"
        )

    client = SRD46AnalysisClient.for_ld()
    _engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "",
        guidance_hooks=[],
    )

    result: Optional[AgentTurnResult] = None
    t0 = time.time()
    try:
        result = agent_turn(
            user_message,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=getattr(cfg, "L2_MAX_ITERATIONS", 4),
            timeout=getattr(cfg, "VERDICT_MAX_SECONDS", 60),
            required_tools={"commit_verdict"},
            terminal_tools={"commit_verdict"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:  # pragma: no cover
        log.warning("LD agent_turn raised: %s", exc, exc_info=debug)
    elapsed = time.time() - t0

    # Capture terminal-tool state *before* installing the fail-closed
    # fallback.  Otherwise the fallback value looks indistinguishable from a
    # verdict actually committed by LD.
    committed = bool(state.committed and state.verdict in _VALID_VERDICTS)
    if not committed:
        # Persist the same effective verdict that is returned. A missing
        # terminal commit is review evidence, not a JSON null that downstream
        # code can accidentally ignore.
        state.verdict = "inconclusive"
        if not state.hints:
            state.hints = [
                "LD did not successfully commit a verdict; scientific "
                "review is inconclusive."
            ]
    agent_turn_timed_out = bool(
        result is not None and getattr(result, "timed_out", False)
    )
    # A review without a terminal commit is incomplete regardless of whether
    # the generic engine labelled the exit as a timeout, iteration exhaustion,
    # or an exception.  Conversely, a valid commit is authoritative.
    review_timed_out = not committed
    _write_artifacts(
        state,
        result,
        attempt,
        review_timed_out=review_timed_out,
        agent_turn_timed_out=agent_turn_timed_out,
    )

    verdict = state.verdict or "inconclusive"
    log.info("LD verdict=%s hints=%d (%.1fs)", verdict, len(state.hints), elapsed)
    return {
        "verdict": verdict,
        "hints": list(state.hints),
        "timed_out": bool(review_timed_out),
        "agent_turn_timed_out": bool(agent_turn_timed_out),
        "committed": bool(committed),
    }


__all__ = ["validate", "format_hints"]
