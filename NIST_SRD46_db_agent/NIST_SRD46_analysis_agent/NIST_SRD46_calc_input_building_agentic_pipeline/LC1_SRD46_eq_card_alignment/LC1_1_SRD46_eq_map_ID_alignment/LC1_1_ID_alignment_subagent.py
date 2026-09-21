"""LC1_1 — Chemical-system ID alignment sub-agent.

Owns the ReAct loop:

* Reads ``purpose`` + ``tasks`` (free text from the parent layer / L0).
* Exposes two tools to the LLM:
    1. ``quick_fact`` — an LC1 adapter over the SRD-46 shared NIST_SRD46_core_db_search_tools.
    2. ``commit_chemical_system`` — terminal tool that locks in
       ``{metals,ligands}`` and ends the turn.
* Hands the agent's commit to :func:`build_system_catalog` (from
  ``id_enrichment_helpers``) for deterministic DB enrichment.

Public API
----------
``align_chemical_system(purpose, tasks, *, session_dir=None, debug=False)``
    → ``{"system_catalog": {"chemical_system": {"metals":[...],
    "ligands":[...]}}}``
``configure_lc1_1_session(session_dir, ...)``
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

# ── path bootstrap (absolute imports, mirrors auto_fetch.py) ───
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

# Analysis-agent client + config (via the calc-input-building wrapper) --
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_argo_engine.argo_client import (  # noqa: E402
    SRD46AnalysisClient,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.SRD46_calc_input_building_config import (  # noqa: E402
    AGENT_CONFIG as cfg,
)

# Optional LC1 adapter over shared NIST_SRD46_core_db_search_tools. Imported lazily inside
# ``_make_quick_fact`` so this module can report a tool-level error instead of
# breaking at import time.

# Deterministic enrichment (sibling module) ------------------------------
from .id_enrichment_helpers import build_system_catalog  # noqa: E402

log = logging.getLogger("LC1_1.subagent")

_HERE = Path(__file__).resolve().parent
_WORKFLOW_PATH = _HERE / "LC1_1_ID_alignment_workflow.md"


# ════════════════════════════════════════════════════════════════════
#  Session state (per-process, set once by the parent layer)
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


def configure_lc1_1_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    """Bind the per-session side-channel (called once by the parent)."""
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or (Path.cwd() / "_lc1_1_adhoc")
    with _SESSION["_lock"]:
        _SESSION["call_index"] += 1
        idx = _SESSION["call_index"]
    out = Path(base) / f"LC1_1_call_{idx:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ════════════════════════════════════════════════════════════════════
#  Per-call closure state
# ════════════════════════════════════════════════════════════════════

@dataclass
class _LC11State:
    purpose:        str
    tasks_text:     str
    call_dir:       Path
    debug:          bool = False
    # quick_fact calls write here; commit_chemical_system reads it.
    verified:       Dict[str, Dict[str, Any]] = field(default_factory=dict)
    committed:      Optional[Dict[str, Any]]  = None  # {metals, ligands}
    commit_error:   Optional[str]             = None


# ════════════════════════════════════════════════════════════════════
#  Tool factories
# ════════════════════════════════════════════════════════════════════

def _make_quick_fact(state: _LC11State) -> Callable[..., str]:
    def quick_fact_tool(
        name: str = "",
        smiles: str = "",
        prefix_id: str = "",
        exclude_ids: str = "",
    ) -> str:
        """Resolve a chemistry token to canonical SRD-46 rows.

        Thin wrapper around existing SRD-46 shared NIST_SRD46_core_db_search_tools. Searches
        **both** metals and ligands and returns a markdown table whose
        rows include a canonical ``prefix_id`` (``metal_<int>`` or
        ``ligand_<int>``) plus the SRD-46 ``type``, display ``name``
        and identifying details.

        Args:
            name: Chemical name (``"copper"``, ``"glycine"``,
                ``"citric acid"``).
            smiles: SMILES string.
            prefix_id: Direct ID lookup (``"metal_41"``, ``"ligand_5760"``).
            exclude_ids: Comma-separated ``prefix_id`` values to drop.

        Returns:
            Markdown table from ``compact_quick_fact``, or a
            ``_(no matches)_`` marker.
        """
        if not (name or smiles or prefix_id):
            return "ERROR: provide at least one of `name`, `smiles`, `prefix_id`."
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_toolbox.quick_fact_tool import (
                compact_quick_fact,
                quick_fact,
            )
        except Exception as exc:
            log.warning("LC1_1 quick_fact resolver unavailable: %s", exc)
            return f"ERROR: quick_fact resolver unavailable ({exc!r})."
        try:
            data = quick_fact(
                name=name,
                smiles=smiles,
                prefix_id=prefix_id,
                exclude_ids=exclude_ids,
            )
        except Exception as exc:                # pragma: no cover
            log.warning("LC1_1 quick_fact raised: %s", exc)
            return f"ERROR: quick_fact raised {exc!r}"

        for row in data.get("matches", []) or []:
            pid = row.get("prefix_id")
            if not pid:
                continue
            state.verified[pid] = {
                "kind":   row.get("entity_type") or (
                    "metal" if pid.startswith("metal_") else "ligand"
                ),
                "name":   row.get("name") or "",
                "smiles": row.get("smiles") or "",
            }
        return compact_quick_fact(data)
    return quick_fact_tool


def _strip_json_fences(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s


def _validate_commit_payload(
    payload: Any,
    *,
    verified: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    issues: List[str] = []
    if not isinstance(payload, dict):
        return None, ["payload must be a JSON object"]
    metals_in  = payload.get("metals")  or []
    ligands_in = payload.get("ligands") or []
    if not isinstance(metals_in, list) or not metals_in:
        issues.append("'metals' must be a non-empty list")
    if not isinstance(ligands_in, list) or not ligands_in:
        issues.append("'ligands' must be a non-empty list")
    if issues:
        return None, issues

    def _norm(entries: List[Any], expected_prefix: str, kind: str,
              label: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen_db: set = set()
        for i, e in enumerate(entries):
            if not isinstance(e, dict):
                issues.append(f"{label}[{i}] must be an object")
                continue
            db_id = str(e.get("db_id") or "").strip()
            name  = str(e.get("name")  or "").strip()
            if not db_id.startswith(expected_prefix):
                issues.append(f"{label}[{i}].db_id={db_id!r} must start with "
                              f"{expected_prefix!r}")
                continue
            if db_id not in verified or verified[db_id].get("kind") != kind:
                issues.append(
                    f"{label}[{i}].db_id={db_id!r} was not returned by a "
                    f"prior `quick_fact` call — search for it first."
                )
                continue
            if not name:
                name = verified[db_id].get("name") or ""
            if db_id in seen_db:
                issues.append(f"{label}[{i}].db_id={db_id!r} duplicated")
                continue
            seen_db.add(db_id)
            out.append({"db_id": db_id, "name": name})
        return out

    metals  = _norm(metals_in,  "metal_",  "metal",  "metals")
    ligands = _norm(ligands_in, "ligand_", "ligand", "ligands")
    if issues:
        return None, issues
    return {"metals": metals, "ligands": ligands}, []


def _make_commit_system(state: _LC11State) -> Callable[[str], str]:
    def commit_chemical_system(json_payload: str = "") -> str:
        """Lock in the resolved ``{metals, ligands}`` list and end the turn.

        Args:
            json_payload: JSON string with shape ``{"metals":[{"db_id":...,
                "name":...}, ...], "ligands":[...]}``. Every ``db_id`` must
                have already been returned by a prior ``quick_fact`` call.

        Returns:
            ``"OK — committed N metals, M ligands."`` on success, or
            ``"ERROR: <issues>. Re-call ..."`` on validation failure.
        """
        raw = _strip_json_fences(json_payload)
        if not raw:
            return "ERROR: empty `json_payload`. Re-emit the JSON."
        try:
            obj = json.loads(raw)
        except Exception as exc:
            return f"ERROR: json.loads failed: {exc!r}. Re-emit strict JSON."
        normalised, issues = _validate_commit_payload(
            obj, verified=state.verified,
        )
        if normalised is None:
            state.commit_error = "; ".join(issues)
            return ("ERROR: " + "; ".join(issues)
                    + ". Re-call `commit_chemical_system`.")
        state.committed = normalised
        state.commit_error = None
        try:
            (state.call_dir / "chemical_system_commit.json").write_text(
                json.dumps(normalised, indent=2), encoding="utf-8",
            )
        except Exception as exc:                # pragma: no cover
            log.warning("LC1_1 could not write commit JSON: %s", exc)
        return (f"OK — committed {len(normalised['metals'])} metals, "
                f"{len(normalised['ligands'])} ligands.")
    return commit_chemical_system


# ════════════════════════════════════════════════════════════════════
#  User-message builder + entry point
# ════════════════════════════════════════════════════════════════════

def _clean_tasks(tasks: Any) -> str:
    """Return the free-text ``tasks`` brief verbatim (no splitting)."""
    if tasks is None:
        return ""
    return str(tasks).strip()


def _build_user_message(purpose: str, tasks: str) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    return f"[Purpose: {purpose}]\n[Tasks:\n{body}\n]"


def _write_tool_history(call_dir: Path,
                        tool_history: List[Dict[str, Any]]) -> None:
    rows = [
        "# LC1_1 Tool Calls",
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
            f"| {excerpt} | {c.get('result_chars','')} | {c.get('elapsed_s','')} |"
        )
    (call_dir / "lc1_1_tool_calls.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8",
    )


def align_chemical_system(
    purpose: str,
    tasks: str = "",
    *,
    session_dir: str | Path | None = None,
    water_system: bool = True,
    debug: bool = False,
) -> Dict[str, Any]:
    """Run the LC1_1 LLM agent and return the enriched ``system_catalog`` block.

    Parameters
    ----------
    purpose
        Free-text scientific question (one or two sentences).
    tasks
        Free-text brief written as natural prose. A single string,
        forwarded verbatim (never split or templated).
    session_dir
        Optional override for the per-call artefact directory. If
        omitted, falls back to whatever ``configure_lc1_1_session``
        bound (or ``./_lc1_1_adhoc`` if neither is set).
    water_system
        When ``True`` (default), inject the aqueous self-system proton
        H\u207a (``metal_68``, a metal entry) and hydroxide OH\u207b
        (``ligand_10076``, a ligand entry) into the committed chemical
        system so the downstream pipeline treats them as first-class
        system species.
    debug
        Verbose logging for the agent loop.

    Returns
    -------
    dict
        ``{"system_catalog": {"chemical_system": {"metals":[...],
        "ligands":[...]}}}``. On hard failure the inner lists are empty
        and ``"_error"`` is attached at the top level.
    """
    purpose_clean = (purpose or "").strip()
    tasks_text = _clean_tasks(tasks)
    if not purpose_clean and not tasks_text:
        return {
            "system_catalog": {"chemical_system": {"metals": [], "ligands": []}},
            "_error": "empty purpose and tasks",
        }

    if session_dir is not None:
        configure_lc1_1_session(session_dir=session_dir, debug=debug)
    elif _SESSION["session_dir"] is None:
        configure_lc1_1_session(session_dir=Path.cwd() / "_lc1_1_adhoc",
                                debug=debug)

    call_dir = _per_call_dir()
    state = _LC11State(
        purpose=purpose_clean,
        tasks_text=tasks_text,
        call_dir=call_dir,
        debug=bool(debug or _SESSION["debug"]),
    )

    try:
        (call_dir / "input.json").write_text(
            json.dumps({"purpose": purpose_clean, "tasks": tasks_text},
                       indent=2),
            encoding="utf-8",
        )
    except Exception:                           # pragma: no cover
        pass

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    tools: Dict[str, Callable] = {
        "quick_fact":             _make_quick_fact(state),
        "commit_chemical_system": _make_commit_system(state),
    }
    system_prompt += "\n\n" + build_tool_instructions(tools)

    user_message = _build_user_message(purpose_clean, tasks_text)
    client = SRD46AnalysisClient.for_lc1_1()
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
            max_iterations=cfg.LC1_1_MAX_ITERATIONS,
            timeout=cfg.LC1_1_MAX_SECONDS,
            required_tools={"commit_chemical_system"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:                    # pragma: no cover
        agent_error = f"{type(exc).__name__}: {exc}"
        log.error("LC1_1 agent_turn raised: %s", exc, exc_info=state.debug)
    elapsed = time.time() - t0

    if result is not None:
        try:
            _write_tool_history(call_dir, list(result.tool_history))
        except Exception:                       # pragma: no cover
            pass
        # Record the agent's final answer + full context (system prompt +
        # conversation + LLM response) so every stage logs its context
        # uniformly with the LC3_* stages.
        try:
            (call_dir / "agent_response.md").write_text(
                "# LC1_1 agent response\n\n"
                "## Final answer (text emitted by the agent)\n\n"
                f"{result.answer or '_(empty)_'}\n\n"
                "## Final context\n\n"
                f"{result.final_context or '_(empty)_'}\n",
                encoding="utf-8",
            )
        except Exception:                       # pragma: no cover
            pass

    if state.committed is None:
        out: Dict[str, Any] = {
            "system_catalog": {
                "chemical_system": {"metals": [], "ligands": []}
            },
            "_error": agent_error or state.commit_error
                      or "agent did not call commit_chemical_system",
            "_elapsed_s": round(elapsed, 3),
        }
    else:
        out = build_system_catalog(
            state.committed,
            water_system=water_system,
            free_ligand_state_cache_path=(
                call_dir
                / "_temporary"
                / "pubchem_free_ligand_state_cache.json"
            ),
        )
        out["_elapsed_s"] = round(elapsed, 3)

    try:
        (call_dir / "system_catalog.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8",
        )
    except Exception:                           # pragma: no cover
        pass

    return out


__all__ = [
    "align_chemical_system",
    "configure_lc1_1_session",
]
