"""LC2_4 — LLM free-energy-card repair agent.

Invoked by the LC2_4 validator orchestrator *only* when the
post-deduplication card fails the solver's own parser
(``numcalc_input_cards_reader.resolve_card_source``).  The agent is
handed the verbatim solver parse error plus the failing card and uses
generic markdown-editing tools to make the card parseable again with
the smallest possible structural edits.  It re-validates against the
*same* solver parser after every edit, so the loop is grounded in the
real solver error rather than a heuristic.

Public API
----------
run_repair_agent(purpose, tasks, card_text, parse_error, parse_traceback,
                 scratch_dir, debug) -> dict
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── path bootstrap: import LC2's external deps (shared LLM engine, query
#    agent context hooks, analysis config) as bare top-level packages
#    WITHOUT pulling in the heavy NIST_SRD46_analysis_agent package
#    __init__ chain. ───────────────────────────────────────────────
_THIS = Path(__file__).absolute()
_ANALYSIS_ROOT = _THIS.parents[4]   # NIST_SRD46_analysis_agent/
_DB_AGENT_ROOT = _THIS.parents[5]   # NIST_SRD46_db_agent/
_SRD46_ROOT    = _THIS.parents[6]   # SRD46_research_agent/
for _p in (_ANALYSIS_ROOT, _DB_AGENT_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
    AgentTurnResult,
)
from general_db_query_engine.general_argo_engine_helpers.engine_config import (
    load_config as _load_engine_config,
)
from general_db_query_engine.general_argo_engine_helpers._argo_engine_entry_point import (
    ArgoClient as _ArgoClient,
)
from general_db_query_engine.general_subagent_skill_schema_and_parser import (
    parse_workflow,
)
from general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from SRD46_analysis_argo_config import AGENT_CONFIG as cfg
from .._card_validation import validate_card_text
from ...agent_context_artifacts import write_agent_context_bundle

# LC2 builds its LLM client from the SHARED engine ArgoClient + the analysis
# config directly, rather than importing analysis_agent_argo_engine (whose
# package __init__ drags in the full analysis-agent stack).  Loading the
# config here mirrors that package's import-time side effect.
_load_engine_config(cfg)

log = logging.getLogger("Analysis.LC2_4.repair")

_HERE = Path(__file__).resolve().parent
_WORKFLOW_PATH = _HERE / "LC2_4_repair_workflow.md"


# ════════════════════════════════════════════════════════════════════
#  Per-run working state (LC2_4 repair runs sequentially, never in
#  parallel, so module-level state is safe — mirrors the prior agent).
# ════════════════════════════════════════════════════════════════════

_WORK: Dict[str, Any] = {
    "card_text":   "",      # mutable working copy of the card
    "scratch_dir": None,    # where revalidation scratch files land
    "n_edits":     0,
    "finalized":   False,
    "last_error":  None,    # last solver error seen by revalidate/finalize
}


# ── section slicing (read-only inspection) ──────────────────────────

_SECTION_HEADERS: Dict[str, str] = {
    "1":   "## 1. Notation",
    "2":   "## 2. Components",
    "2.4": "### 2.4 Metal Valence",
    "3":   "## 3. Reactions",
    "4":   "## 4. Free Energy",
    "5":   "## 5. Species",
    "5.1": "### 5.1 Aqueous",
    "5.2": "### 5.2 Dissolution",
    "5.3": "### 5.3 Gas",
}


def _slice_section(text: str, header_prefix: str,
                   *, max_chars: int = 12_000) -> str:
    if not text:
        return ""
    idx = text.find(header_prefix)
    if idx < 0:
        return f"_(section header {header_prefix!r} not found)_"
    line_start = text.rfind("\n", 0, idx) + 1
    body = text[line_start:]
    end = body.find("\n## ", 1)
    if end < 0:
        end = len(body)
    sliced = body[:end].rstrip()
    if len(sliced) > max_chars:
        sliced = sliced[:max_chars] + (
            f"\n\n_(truncated; original was {len(body[:end])} chars)_"
        )
    return sliced


# ════════════════════════════════════════════════════════════════════
#  Tool surface
# ════════════════════════════════════════════════════════════════════

def _inspect_card_section(section: str = "") -> str:
    key = (section or "").strip()
    if key not in _SECTION_HEADERS:
        return (f"ERROR: section={key!r} not allowed. "
                f"Valid: {sorted(_SECTION_HEADERS)}")
    text = _WORK.get("card_text") or ""
    if not text:
        return "_(no card text bound to this session)_"
    return _slice_section(text, _SECTION_HEADERS[key])


def _replace_card_text(old: str = "", new: str = "") -> str:
    """Replace exactly one verbatim occurrence of ``old`` with ``new``."""
    text = _WORK.get("card_text") or ""
    if not text:
        return "ERROR: no card text bound to this session."
    if not old:
        return "ERROR: `old` must be a non-empty literal string to replace."
    count = text.count(old)
    if count == 0:
        return ("ERROR: `old` not found verbatim in the card. "
                "Use inspect_card_section to copy the exact text "
                "(including whitespace).")
    if count > 1:
        return (f"ERROR: `old` matches {count} locations; it must be unique. "
                "Add surrounding context so it identifies a single spot.")
    _WORK["card_text"] = text.replace(old, new, 1)
    _WORK["n_edits"] += 1
    return (f"OK — replaced 1 occurrence (edit #{_WORK['n_edits']}; "
            f"{len(old)} -> {len(new)} chars). "
            "Call revalidate_card() to check the result.")


def _revalidate_card(_: str = "") -> str:
    """Re-run the solver parser on the current working card."""
    text = _WORK.get("card_text") or ""
    scratch = _WORK.get("scratch_dir") or Path.cwd()
    res = validate_card_text(text, scratch_dir=scratch)
    _WORK["last_error"] = None if res.ok else res.short_error()
    if res.ok:
        return "VALID — the card now parses with the solver's reader."
    return ("STILL INVALID — solver parse error:\n"
            f"{res.short_error()}")


def _finalize_repair(_: str = "") -> str:
    """Declare repair complete; only succeeds if the card is VALID."""
    text = _WORK.get("card_text") or ""
    scratch = _WORK.get("scratch_dir") or Path.cwd()
    res = validate_card_text(text, scratch_dir=scratch)
    if res.ok:
        _WORK["finalized"] = True
        _WORK["last_error"] = None
        return "OK — card is VALID. Repair finalized."
    _WORK["finalized"] = False
    _WORK["last_error"] = res.short_error()
    return ("CANNOT FINALIZE — card still fails the solver parser:\n"
            f"{res.short_error()}\n"
            "Keep editing with replace_card_text and re-check.")


# ════════════════════════════════════════════════════════════════════
#  User message
# ════════════════════════════════════════════════════════════════════

def _build_card_block(card_text: str, *, max_chars: int = 24_000) -> str:
    if len(card_text) <= max_chars:
        return card_text
    head = card_text[:max_chars]
    return (head + f"\n\n_(card truncated to {max_chars} chars; "
            "use inspect_card_section to read specific sections)_")


def _build_user_message(
    purpose: str,
    tasks: str,
    parse_error: str,
    parse_traceback: Optional[str],
    card_text: str,
) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    tb = ""
    if parse_traceback:
        tb_short = parse_traceback
        if len(tb_short) > 4000:
            tb_short = tb_short[-4000:]
        tb = f"\n[Solver traceback (tail)]\n```\n{tb_short}\n```"
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n"
        f"[Solver parse error]\n{parse_error}{tb}\n\n"
        f"[Card]\n{_build_card_block(card_text)}"
    )


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def _write_repair_context(
    scratch_dir: Path,
    result: Any,
    *,
    system_prompt: str,
    user_message: str,
    tools: Dict[str, Callable],
    error: str | None = None,
) -> None:
    """Persist the exact repair-agent context and audit-visible result."""
    try:
        write_agent_context_bundle(
            scratch_dir,
            stage_id="LC2_4.repair",
            stage_label="LC2_4 repair",
            role="solver-card repair agent",
            phase="repair",
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            required_tools={"finalize_repair"},
            memory=[],
            result=result,
            error=error,
            metadata={
                "initial_card_prefix_limit_chars": 24_000,
                "traceback_tail_limit_chars": 4_000,
                "section_inspection_limit_chars": 12_000,
            },
            runtime={
                "engine": (
                    "general_db_query_engine.general_argo_engine_helpers."
                    "agent_turn"
                ),
                "argo_api_user": cfg.API_USER,
                "model": cfg.L1_MODEL,
                "tier": "L1-phase",
                "temperature": cfg.TEMPERATURE,
                "top_p": cfg.TOP_P,
                "max_tokens": cfg.MAX_TOKENS,
                "max_tool_iterations": cfg.MAX_TOOL_ITERATIONS,
                "turn_timeout_seconds": cfg.MAX_TURN_SECONDS,
                "keep_recent_results": cfg.KEEP_RECENT_RESULTS,
                "trimmed_preview_chars": cfg.TRIMMED_PREVIEW_CHARS,
                "guidance_max_tokens": cfg.GUIDANCE_MAX_TOKENS,
                "http_timeout_seconds": cfg.HTTP_TIMEOUT,
            },
        )
    except Exception:                                # pragma: no cover
        pass


def run_repair_agent(
    *,
    purpose: str,
    tasks: str,
    card_text: str,
    parse_error: str,
    parse_traceback: Optional[str] = None,
    scratch_dir: str | Path,
    debug: bool = False,
) -> Dict[str, Any]:
    """Run the LLM repair agent against a failing card.

    Returns
    -------
    dict with keys:
        ``status``            — ``"ok"`` (card valid) or ``"failed"``.
        ``repaired_card_text``— the (possibly edited) working card.
        ``final_error``       — last solver error (None when ok).
        ``n_edits``           — number of applied text replacements.
        ``iterations``        — LLM tool-loop iterations.
        ``tool_history``      — agent_turn tool history (list).
    """
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Reset working state for this run.
    _WORK["card_text"]   = card_text
    _WORK["scratch_dir"] = scratch_dir
    _WORK["n_edits"]     = 0
    _WORK["finalized"]   = False
    _WORK["last_error"]  = parse_error

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    tools: Dict[str, Callable] = {
        "inspect_card_section": _inspect_card_section,
        "replace_card_text":    _replace_card_text,
        "revalidate_card":      _revalidate_card,
        "finalize_repair":      _finalize_repair,
    }
    system_prompt += "\n\n" + build_tool_instructions(tools)

    user_message = _build_user_message(
        purpose, tasks, parse_error, parse_traceback, card_text,
    )
    client = _ArgoClient(
        model=cfg.L1_MODEL, max_tokens=cfg.MAX_TOKENS, _tier="L1-phase",
    )
    _engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "",
        guidance_hooks=[],
    )

    t0 = time.time()
    try:
        result: AgentTurnResult = agent_turn(
            user_message,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=cfg.MAX_TOOL_ITERATIONS,
            timeout=cfg.MAX_TURN_SECONDS,
            required_tools={"finalize_repair"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        log.error("LC2_4 repair agent_turn raised: %s", exc,
                  exc_info=debug)
        _write_repair_context(
            scratch_dir,
            None,
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            error=f"agent_turn_exception: {exc!r}",
        )
        return {
            "status":             "failed",
            "repaired_card_text": _WORK["card_text"],
            "final_error":        f"agent_turn_exception: {exc!r}",
            "n_edits":            _WORK["n_edits"],
            "iterations":         0,
            "tool_history":       [],
            "elapsed_s":          round(elapsed, 3),
        }

    elapsed = time.time() - t0
    finalized = bool(_WORK["finalized"])
    status = "ok" if finalized else "failed"
    if not finalized:
        log.warning("LC2_4 repair agent did not reach a VALID card "
                    "(edits=%d, last_error=%s)",
                    _WORK["n_edits"], _WORK["last_error"])

    # Record the agent's full context (final answer + system prompt +
    # conversation + LLM response) and tool-call history, so the LC2_4
    # repair sub-agent logs its context like the LC1_*/LC3_* stages do.
    _write_repair_context(
        scratch_dir,
        result,
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tools,
    )

    return {
        "status":             status,
        "repaired_card_text": _WORK["card_text"],
        "final_error":        None if finalized else _WORK["last_error"],
        "n_edits":            _WORK["n_edits"],
        "iterations":         result.iterations,
        "tool_history":       result.tool_history,
        "elapsed_s":          round(elapsed, 3),
    }
