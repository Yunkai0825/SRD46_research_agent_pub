"""LC1_2 — Eq-map node validator sub-agent (per pair).

Owns the ReAct loop for ONE ``(metal_id, ligand_id)`` pair:

* Reads the deterministic ``EqMapScreen`` produced by
  ``screen_eq_map`` over the draft eq-map.
* Exposes three tools to the LLM:
    1. ``get_node_neighbors`` — render the full sibling vlm-row table
       for one node (markdown).
    2. ``inspect_node`` — re-render the per-node block from the screen
       report (fallback when context is truncated).
    3. ``finalize_patches`` — terminal tool; submits the
       ``{"patches": [...]}`` payload and ends the turn.
* Returns the validated patch list to the LC1_2 orchestrator, which
  applies them via :func:`apply_patches_to_maps_json`.

The orchestrator decides **which** pairs to validate; this module
only knows how to handle ONE pair.  When
``AGENT_CONFIG.LC1_2_ENABLED`` is True the orchestrator invokes this
sub-agent on every pair (no skip route); when it is False the
orchestrator never calls in.

For a clean pair (no ``critical`` nodes) the expected outcome is
``{"patches": []}`` — that is **not** a failure.

Public API
----------
``validate_eq_map_pair(pair_key, metal_id, ligand_id, request_T_C,
    request_I_M, purpose, tasks, screen, *, session_dir=None,
    pair_log_dir=None, debug=False) -> ValidationResult``

``configure_lc1_2_session(session_dir, ...)``
    Bind the per-session side-channel (artefact dir, history, stats).
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── path bootstrap (mirrors LC1_1_subagent.py) ───────────────────
_THIS = Path(__file__).absolute()
_PIPELINE_ROOT = _THIS.parents[2]   # NIST_SRD46_calc_input_building_agentic_pipeline/
_ANALYSIS_ROOT = _THIS.parents[3]   # NIST_SRD46_analysis_agent/
_DB_AGENT_ROOT = _THIS.parents[4]   # NIST_SRD46_db_agent/
_SRD46_ROOT    = _THIS.parents[5]   # SRD46_research_agent/
for _p in (_PIPELINE_ROOT, _ANALYSIS_ROOT, _DB_AGENT_ROOT, _SRD46_ROOT):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# Shared engine & schemas ------------------------------------------------
from NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers import (  # noqa: E402
    agent_turn,
    AgentTurnResult,
)
from NIST_SRD46_db_agent.general_db_query_engine.general_subagent_skill_schema_and_parser import (  # noqa: E402
    parse_workflow,
)
from NIST_SRD46_db_agent.general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (  # noqa: E402
    build_tool_instructions,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_context_hooks.hook_catalog import (  # noqa: E402
    build_agent_hooks as _build_engine_agent_hooks,
)

# Analysis-agent client + config ---------------------------------------
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_argo_engine.argo_client import (  # noqa: E402
    SRD46AnalysisClient,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.SRD46_calc_input_building_config import (  # noqa: E402
    AGENT_CONFIG as cfg,
)

# Local validation helpers ---------------------------------------------
from .eqmap_validation_helpers import (  # noqa: E402
    EqMapScreen,
    NodeScreen,
    PatchValidationResult,
    VALID_OPERATIONS,
    format_errors_for_agent,
    get_node_neighbors,
    render_neighbors_md,
    render_screen_md,
    validate_patches,
)
from .eqmap_validation_helpers.report_md import _render_node_block  # noqa: E402

log = logging.getLogger("LC1_2.subagent")

_HERE = Path(__file__).resolve().parent
_WORKFLOW_PATH = _HERE / "LC1_2_eq_map_validator_workflow.md"


# ════════════════════════════════════════════════════════════════════
#  Session state (per-process, set once by the orchestrator)
# ════════════════════════════════════════════════════════════════════

_SESSION: Dict[str, Any] = {
    "session_dir":    None,
    "history":        None,
    "stats":          None,
    "working_memory": None,
    "debug":          False,
    "call_index":     0,
    "_lock":          threading.Lock(),
}


def configure_lc1_2_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    """Bind the per-session side-channel (called once by the orchestrator)."""
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _default_pair_log_dir(pair_key: str) -> Path:
    base = _SESSION["session_dir"] or (Path.cwd() / "_lc1_2_adhoc")
    with _SESSION["_lock"]:
        _SESSION["call_index"] += 1
        idx = _SESSION["call_index"]
    safe_pair = re.sub(r"[^A-Za-z0-9_]+", "_", pair_key)[:48] or "pair"
    out = Path(base) / f"LC1_2_call_{idx:02d}_{safe_pair}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ════════════════════════════════════════════════════════════════════
#  Per-call closure state
# ════════════════════════════════════════════════════════════════════

@dataclass
class _LC12State:
    pair_key:        str
    metal_id:        int
    ligand_id:       int
    request_T_C:     float
    request_I_M:     float
    screen:          EqMapScreen
    node_index:      Dict[str, NodeScreen]
    pair_log_dir:    Path
    debug:           bool = False
    final_patches:   Optional[List[Dict[str, Any]]] = None
    final_error:     Optional[str] = None
    last_validation: Optional[PatchValidationResult] = None


@dataclass
class ValidationResult:
    """Return value of :func:`validate_eq_map_pair`."""
    pair_key:       str
    patches:        List[Dict[str, Any]] = field(default_factory=list)
    error:          Optional[str] = None
    elapsed_s:      float = 0.0
    tool_history:   List[Dict[str, Any]] = field(default_factory=list)
    iterations:     int = 0
    validation:     Optional[PatchValidationResult] = None

    @property
    def ok(self) -> bool:
        return self.error is None and (
            self.validation is None or self.validation.ok
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pair_key":     self.pair_key,
            "ok":           self.ok,
            "patches":      list(self.patches),
            "error":        self.error,
            "elapsed_s":    round(self.elapsed_s, 3),
            "iterations":   self.iterations,
            "n_tool_calls": len(self.tool_history),
            "validation":   self.validation.as_dict() if self.validation else None,
        }


# ════════════════════════════════════════════════════════════════════
#  Patch validation (delegated to patch_validator)
# ════════════════════════════════════════════════════════════════════

def _strip_json_fences(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s


# ════════════════════════════════════════════════════════════════════
#  Tool factories
# ════════════════════════════════════════════════════════════════════

def _make_get_node_neighbors(state: _LC12State) -> Callable[..., str]:
    def get_node_neighbors_tool(node_key: str = "") -> str:
        """Return the sibling-vlm table for one node, grouped by (T, I).

        Args:
            node_key: A ``node_key`` from the ``[Critical nodes]`` or
                ``[Warn nodes]`` lists in the user message.

        Returns:
            Markdown table with one row per sibling vlm measurement,
            bucketed by (temperature, ionic strength). The currently
            chosen row is marked ``**\u2190chosen**``.
        """
        nk = (node_key or "").strip()
        ns = state.node_index.get(nk)
        if ns is None:
            return (f"ERROR: node_key={nk!r} not in this pair's screen. "
                    f"Available: {sorted(state.node_index.keys())}")
        n = ns.node
        try:
            neighbors = get_node_neighbors(
                n.metal_id, n.ligand_id, n.beta_definition_id,
            )
        except Exception as exc:                                # pragma: no cover
            log.warning("LC1_2 get_node_neighbors raised: %s", exc)
            return f"ERROR: get_node_neighbors raised {exc!r}"
        return render_neighbors_md(
            pair_key=state.pair_key,
            node_key=n.node_key,
            chosen_vlm_id=n.vlm_id,
            chosen_value=n.constant_value,
            chosen_constant_type=n.constant_type,
            chosen_T_C=n.temperature_C,
            chosen_I_M=n.ionic_strength_M,
            request_T_C=state.request_T_C,
            request_I_M=state.request_I_M,
            neighbors=neighbors,
            flags=ns.flags,
            notes=ns.notes,
        )
    return get_node_neighbors_tool


def _make_inspect_node(state: _LC12State) -> Callable[..., str]:
    def inspect_node_tool(node_key: str = "") -> str:
        """Return the per-node block from the deterministic screen.

        Use when the original screen report in the user message was
        truncated and you need the flags / K-sibling summary for one
        specific node.

        Args:
            node_key: A ``node_key`` from the pair's screen.

        Returns:
            Markdown block (same shape as one entry in
            ``[Screen report]``).
        """
        nk = (node_key or "").strip()
        ns = state.node_index.get(nk)
        if ns is None:
            return (f"ERROR: node_key={nk!r} not in this pair's screen. "
                    f"Available: {sorted(state.node_index.keys())}")
        return "\n".join(_render_node_block(
            ns, state.request_T_C, state.request_I_M,
        ))
    return inspect_node_tool


def _make_finalize_patches(state: _LC12State) -> Callable[..., str]:
    def finalize_patches(json_payload: str = "") -> str:
        """Submit the final patch list and end the turn.

        Args:
            json_payload: JSON string of shape ``{"patches": [...]}``.
                Each patch is a pure data instruction (no LLM math at
                parse time): operation must be one of
                ``set_value`` / ``drop_node``; ``set_value`` requires
                a finite ``chosen_value`` baked in. Empty patch list
                is legal and is the expected outcome for a clean
                pair.

        Returns:
            ``"OK \u2014 accepted N patch(es)."`` on success, or
            ``"ERROR: ...\\nRe-call `finalize_patches` with a
            corrected payload."`` on validation failure.
        """
        raw = _strip_json_fences(json_payload)
        if not raw:
            state.final_error = "empty json_payload"
            state.last_validation = None
            return ("ERROR: empty `json_payload`. "
                    "Re-call `finalize_patches` with a JSON object "
                    "of shape `{\"patches\": [...]}`.")
        try:
            obj = json.loads(raw)
        except Exception as exc:
            state.final_error = f"json_parse_error: {exc!r}"
            state.last_validation = None
            return (f"ERROR: json.loads failed: {exc!r}. "
                    f"Re-emit a strict JSON object "
                    f"(no comments, no trailing commas).")

        result = validate_patches(
            obj,
            pair_key=state.pair_key,
            metal_id=state.metal_id,
            ligand_id=state.ligand_id,
            screen=state.screen,
        )
        state.last_validation = result
        if not result.ok:
            state.final_error = "; ".join(result.errors[:3])
            return (
                "ERROR: patch list rejected by validator.\n\n"
                + format_errors_for_agent(result)
                + "\nRe-call `finalize_patches` with the corrected JSON."
            )
        state.final_patches = list(result.patches_norm)
        state.final_error = None
        return (f"OK — accepted {len(result.patches_norm)} patch(es) "
                f"({result.n_set_value} set_value, "
                f"{result.n_drop_node} drop_node).")
    return finalize_patches


# ════════════════════════════════════════════════════════════════════
#  User-message builder
# ════════════════════════════════════════════════════════════════════

def _clean_tasks(tasks: Any) -> str:
    """Return the free-text ``tasks`` brief verbatim (no splitting)."""
    if tasks is None:
        return ""
    return str(tasks).strip()


def _build_user_message(
    *,
    purpose: str,
    tasks: str,
    state: _LC12State,
) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    crit_lines = "\n".join(f"  - `{k}`"
                           for k in state.screen.critical_node_keys) \
                 or "  _(none)_"
    warn_lines = "\n".join(f"  - `{k}`"
                           for k in state.screen.warn_node_keys) \
                 or "  _(none)_"
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n"
        f"[Pair: pair_key=`{state.pair_key}`, "
        f"metal_id={state.metal_id}, ligand_id={state.ligand_id}, "
        f"T={state.request_T_C}°C, I={state.request_I_M} M]\n"
        f"[Critical nodes]\n{crit_lines}\n"
        f"[Warn nodes]\n{warn_lines}\n"
        f"[Screen report]\n{render_screen_md(state.screen)}"
    )


def _write_tool_history(pair_log_dir: Path,
                        tool_history: List[Dict[str, Any]]) -> None:
    rows = [
        "# LC1_2 Tool Calls",
        "",
        "| # | iter | tool | args (excerpt) | result_chars | elapsed_s |",
        "|--:|----:|------|----------------|-------------:|----------:|",
    ]
    for i, c in enumerate(tool_history, start=1):
        args = c.get("arguments", {}) or {}
        try:
            excerpt = json.dumps(args)[:120].replace("|", "\\|")
        except Exception:
            excerpt = repr(args)[:120].replace("|", "\\|")
        rows.append(
            f"| {i} | {c.get('iteration','')} | {c.get('tool','?')} "
            f"| {excerpt} | {c.get('result_chars','')} "
            f"| {c.get('elapsed_s','')} |"
        )
    (pair_log_dir / "lc1_2_tool_calls.md").write_bytes(
        ("\n".join(rows) + "\n").encode("utf-8"),
    )


# ════════════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════════════

def validate_eq_map_pair(
    *,
    pair_key: str,
    metal_id: int,
    ligand_id: int,
    request_T_C: float,
    request_I_M: float,
    purpose: str,
    tasks: str,
    screen: EqMapScreen,
    session_dir: str | Path | None = None,
    pair_log_dir: str | Path | None = None,
    additional_user_context: str = "",
    extra_user_context: str = "",
    debug: bool = False,
) -> ValidationResult:
    """Run the LC1_2 LLM agent on ONE (metal, ligand) pair.

    The orchestrator is responsible for deciding whether to call this
    function (via ``cfg.LC1_2_ENABLED``).  When enabled, this is
    invoked on **every** pair regardless of screen severity; for clean
    pairs the agent is expected to return ``{"patches": []}``.

    Parameters
    ----------
    pair_key, metal_id, ligand_id, request_T_C, request_I_M
        Identifiers + the (T, I) at which the eq-map should be
        evaluated.
    purpose, tasks
        Forwarded into the user message so the agent has the same
        scientific context that LC1_1 / L0 received.
    screen
        The :class:`EqMapScreen` produced by
        :func:`screen_eq_map` over the draft eq-map. Both the screen
        markdown and the per-node lookups go through this object.
    session_dir
        Optional override for the per-session artefact directory. If
        omitted, falls back to whatever
        :func:`configure_lc1_2_session` bound (or
        ``./_lc1_2_adhoc``).
    pair_log_dir
        Optional explicit log directory for this pair. When omitted,
        a ``LC1_2_call_NN_<pair_key>`` directory is created under the
        session dir.
    additional_user_context
        Optional caller-rendered audit context appended verbatim to the
        ordinary user message. Empty by default, preserving the legacy
        prompt exactly.
    extra_user_context
        Validator feedback used only for retry attempts.
    debug
        Verbose logging for the agent loop.

    Returns
    -------
    ValidationResult
        ``.patches`` is the validated patch list ready to feed into
        :func:`apply_patches_to_maps_json`. ``.error`` is non-None
        only when the agent failed to produce a valid payload.
    """
    if session_dir is not None:
        configure_lc1_2_session(session_dir=session_dir, debug=debug)
    elif _SESSION["session_dir"] is None:
        configure_lc1_2_session(
            session_dir=Path.cwd() / "_lc1_2_adhoc",
            debug=debug,
        )

    if pair_log_dir is None:
        log_dir = _default_pair_log_dir(pair_key)
    else:
        log_dir = Path(pair_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    tasks_text = _clean_tasks(tasks)
    state = _LC12State(
        pair_key=pair_key,
        metal_id=int(metal_id),
        ligand_id=int(ligand_id),
        request_T_C=float(request_T_C),
        request_I_M=float(request_I_M),
        screen=screen,
        node_index={ns.node.node_key: ns for ns in screen.nodes},
        pair_log_dir=log_dir,
        debug=bool(debug or _SESSION["debug"]),
    )

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    tools: Dict[str, Callable] = {
        "get_node_neighbors": _make_get_node_neighbors(state),
        "inspect_node":       _make_inspect_node(state),
        "finalize_patches":   _make_finalize_patches(state),
    }
    system_prompt += "\n\n" + build_tool_instructions(tools)

    user_message = _build_user_message(
        purpose=(purpose or "").strip(),
        tasks=tasks_text,
        state=state,
    )
    additional = (additional_user_context or "").strip()
    if additional:
        user_message = f"{user_message}\n\n---\n\n{additional}"
    extra = (extra_user_context or "").strip()
    if extra:
        user_message = (
            f"[Retry context — prior attempt was rejected by the validator]\n"
            f"{extra}\n\n"
            f"---\n\n"
            f"{user_message}"
        )
    try:
        (log_dir / "user_message.md").write_bytes(user_message.encode("utf-8"))
        (log_dir / "input_screen.json").write_bytes(
            json.dumps(screen.as_dict(), indent=2, default=str).encode("utf-8"),
        )
    except Exception:                                           # pragma: no cover
        pass

    client = SRD46AnalysisClient.for_lc1_2()
    _engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "",
        guidance_hooks=[],
    )

    t0 = time.time()
    result: Optional[AgentTurnResult] = None
    agent_error: Optional[str] = None
    try:
        result = agent_turn(
            user_message,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=cfg.LC1_2_MAX_ITERATIONS,
            timeout=cfg.LC1_2_MAX_SECONDS,
            required_tools={"finalize_patches"},
            terminal_tools={"finalize_patches"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:                                    # pragma: no cover
        agent_error = f"{type(exc).__name__}: {exc}"
        log.error("LC1_2[%s] agent_turn raised: %s",
                  pair_key, exc, exc_info=state.debug)
    elapsed = time.time() - t0

    tool_history: List[Dict[str, Any]] = []
    iterations = 0
    if result is not None:
        tool_history = list(result.tool_history)
        iterations = getattr(result, "iterations", 0) or len(tool_history)
        try:
            _write_tool_history(log_dir, tool_history)
        except Exception:                                       # pragma: no cover
            pass
        # Record the agent's final answer + full context (system prompt +
        # conversation + LLM response) so every stage logs its context
        # uniformly with the LC3_* stages.
        try:
            (log_dir / "agent_response.md").write_text(
                "# LC1_2 agent response\n\n"
                "## Final answer (text emitted by the agent)\n\n"
                f"{result.answer or '_(empty)_'}\n\n"
                "## Final context\n\n"
                f"{result.final_context or '_(empty)_'}\n",
                encoding="utf-8",
            )
        except Exception:                                       # pragma: no cover
            pass

    if state.final_patches is None:
        out = ValidationResult(
            pair_key=pair_key,
            patches=[],
            error=agent_error or state.final_error
                  or "agent did not call finalize_patches",
            elapsed_s=elapsed,
            tool_history=tool_history,
            iterations=iterations,
            validation=state.last_validation,
        )
    else:
        out = ValidationResult(
            pair_key=pair_key,
            patches=state.final_patches,
            error=None,
            elapsed_s=elapsed,
            tool_history=tool_history,
            iterations=iterations,
            validation=state.last_validation,
        )

    try:
        (log_dir / "validation_result.json").write_bytes(
            json.dumps(out.as_dict(), indent=2).encode("utf-8"),
        )
        (log_dir / "patches.json").write_bytes(
            json.dumps({"patches": out.patches}, indent=2).encode("utf-8"),
        )
    except Exception:                                           # pragma: no cover
        pass

    return out


__all__ = [
    "validate_eq_map_pair",
    "configure_lc1_2_session",
    "ValidationResult",
]
