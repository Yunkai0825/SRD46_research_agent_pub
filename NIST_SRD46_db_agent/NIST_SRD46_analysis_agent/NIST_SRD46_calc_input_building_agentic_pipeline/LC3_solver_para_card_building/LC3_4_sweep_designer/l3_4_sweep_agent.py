"""L3_4 -- LLM sweep-grid designer (numeric axis ranges).

The final stage of the LC3 solver-parameter card-building pipeline.
L3_1 chose the ``sweep_method`` / ``dof``, L3_2 fixed the initial
conditions, and L3_3 authored the **constraint card** -- the residual
equations that pin every degree of freedom and declare which handles are
*swept* (the ``axes`` block of the ``lc3_2.v1`` spec).

This stage attaches a numeric grid -- ``min`` / ``max`` / ``n_points`` --
to each swept axis.  It changes nothing about the constraints; it only
gives every axis the constraint card declared a range to scan.  The LLM
reads the L0 ``purpose`` / ``tasks`` plus the swept-axis table and emits
one ``{name, min, max, n_points}`` row per axis.

Correctness gate
----------------
The emitted axes are merged with the L3_3 spec / settings / system
catalog into a **native calc-input** card::

    {sweep_method, sweep_axes, system_catalog,
     constraint_spec, constraint_settings, grid_refine?}

and re-validated by the real solver loader
(``calc_json_input_reader.load_calc_input``).  This parses the constraint
spec AND checks every axis (legal name, ``n_points >= 2``, ``max > min``),
so a committed card is guaranteed consumable by the numcalc solver.

Public API
----------
configure_l3_4_session(session_dir, history, stats, working_memory, debug)
run_l3_4(purpose, tasks, calc_input_card_path, fixed_card_path,
         system_catalog_path, output_dir) -> dict
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .....general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
    AgentTurnResult,
)
from .....general_db_query_engine.general_subagent_skill_schema_and_parser import (
    parse_workflow,
)
from .....general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from ....analysis_agent_context_hooks.hook_catalog import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from ....analysis_agent_argo_engine.argo_client import SRD46AnalysisClient
from ....SRD46_analysis_argo_config import AGENT_CONFIG as cfg
from ....analysis_agent_toolbox.calc_wrappers import _require_purpose_tasks

# ── path bootstrap so the numcalc calc-input loader imports cleanly ───
# NOTE: do NOT call ``.resolve()`` on Windows mapped drives that point at
# a UNC share -- it rewrites the path into the \\server\share form and
# Python's package finder then fails sub-package imports.  Use
# ``.absolute()`` and keep the mapped-drive root.
_HERE = Path(__file__).absolute()
_WORKFLOW_PATH = _HERE.parent / "L3_4_sweep_workflow.md"
_NUMCALC_ROOT = _HERE.parents[3] / "NIST_SRD46_core_numcalc_pipeline"
_INPUT_BUILD = _HERE.parents[2]         # NIST_SRD46_calc_input_building_agentic_pipeline
_CARD_MGMT = _INPUT_BUILD / "card_management_helpers"
_SRD46_ROOT = _HERE.parents[5]          # SRD46_research_agent/ (holds NIST_SRD46_db_agent)
for _p in (_NUMCALC_ROOT, _CARD_MGMT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Authoritative solver-side calc-input loader (the same path the numcalc
# solver consumes); used as the final validation gate.
from numcalc_input_cards_reader.calc_json_input_reader import (  # noqa: E402
    load_calc_input,
    SUPPORTED_SWEEP_METHODS,
    _RECOGNISED_AXES,
)
from ..sweep_template_router import (  # noqa: E402
    append_freeform_gallery_note,
    build_sweep_skill_context,
    get_freeform_gallery_note,
    get_sweep_skill_tools,
    skill_selection_record,
)

log = logging.getLogger("Analysis.L3_4")


# ════════════════════════════════════════════════════════════════════
#  Session state
# ════════════════════════════════════════════════════════════════════

_SESSION: Dict[str, Any] = {
    "session_dir":    None,
    "history":        None,
    "stats":          None,
    "working_memory": None,
    "debug":          False,
    "call_index":     0,
    "_sweep_method":  "",
    "_dof":           None,
    "_card":          None,          # full evolving calc-input card (L3_1..L3_3)
    "_spec":          None,          # lc3_2.v1 constraint spec (carried verbatim)
    "_settings":      None,          # constraint settings sidecar
    "_system_catalog": {},
    "_axis_names":    [],            # physical axis names the LLM must declare
}


def configure_l3_4_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or Path.cwd()
    _SESSION["call_index"] += 1
    out = Path(base) / f"L3_4_call_{_SESSION['call_index']:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ════════════════════════════════════════════════════════════════════
#  Constraint-card / axis helpers
# ════════════════════════════════════════════════════════════════════

def _load_constraint_card(path: Path) -> Dict[str, Any]:
    """Read the single evolving ``calc_input_card.json``.

    Carries ``sweep_method``, ``_meta.dof``, ``system_catalog``,
    ``constraint_spec`` and ``constraint_settings`` (everything L3_1..L3_3
    have authored).  L3_4 only appends ``sweep_axes`` (+ optional
    ``grid_refine``).
    """
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"L3_4: calc-input card in {path} is not an object")
    return obj


# Direct solver handles that map 1:1 to a recognised physical axis name.
_HANDLE_TO_AXIS: Dict[str, str] = {
    "pH":             "pH",
    "E_V":            "E_V",
    "temperature":    "temperature",
    "ionic_strength": "ionic_strength",
}


def _strip_axis_suffix(axis: str) -> str:
    """Reduce a card axis handle to a physical axis name.

    ``pH_axis`` -> ``pH``; ``E_V_axis`` -> ``E_V``; ``a_w_axis`` ->
    ``a_w``; ``V_added_mL`` -> ``V_added_mL`` (no suffix).
    """
    for suf in ("_tot_axis", "_axis"):
        if axis.endswith(suf):
            return axis[: -len(suf)]
    return axis


def _axis_physical_hints(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """Map each declared card axis to the physical name the loader wants.

    Scans the spec ``binds`` for the variable each axis drives (a bind
    whose ``rhs`` references the axis); falls back to suffix-stripping
    when an axis is used only inside slaved expressions.
    """
    binds = spec.get("binds", []) or []
    hints: List[Dict[str, str]] = []
    for axis in (spec.get("axes", []) or []):
        handle = ""
        physical = ""
        for b in binds:
            rhs = b.get("rhs")
            if isinstance(rhs, dict) and rhs.get("axis") == axis:
                lhs = b.get("lhs") or {}
                ref = str(lhs.get("ref") or "")
                cid = lhs.get("id")
                handle = f's.{ref}["{cid}"]' if cid else f"s.{ref}"
                if ref in _HANDLE_TO_AXIS:
                    physical = _HANDLE_TO_AXIS[ref]
                elif ref == "total" and cid:
                    physical = str(cid)
                break
        if not physical:
            physical = _strip_axis_suffix(axis)
        hints.append({"axis": axis, "physical": physical, "handle": handle})
    return hints


# ════════════════════════════════════════════════════════════════════
#  Tool surface
# ════════════════════════════════════════════════════════════════════

_FINAL_SLOT: Dict[str, Any] = {
    "payload": None,
    "calc_input": None,
    "error": None,
    "failure_scope": None,
    "latest_attempt": None,
    "restart_request": None,
}
NOT_DEFINED = "Not defined"


def _strip_fence(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _parse_refinement_design(
    grid_refine_json: str,
    *,
    dof: Optional[int],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse the mandatory refinement decision without numerical defaults."""
    gr_raw = _strip_fence(grid_refine_json)
    if not gr_raw or gr_raw == NOT_DEFINED:
        raise ValueError(
            "refinement design is 'Not defined'; declare mode='none' or "
            "mode='boundary'"
        )
    gr = json.loads(gr_raw)
    if not isinstance(gr, dict):
        raise ValueError("refinement design must be a JSON object")
    mode = str(gr.get("mode") or "").strip().lower()
    if mode not in {"none", "boundary"}:
        raise ValueError("refinement mode must be 'none' or 'boundary'")
    if mode == "none":
        unexpected = sorted(set(gr) - {"mode"})
        if unexpected:
            raise ValueError(
                "mode='none' cannot carry refinement knobs: "
                + ", ".join(unexpected)
            )
        design = {"mode": "none"}
        return design, design

    if dof not in {2, 3}:
        raise ValueError("boundary refinement requires a 2-D or 3-D sweep")
    missing = [key for key in ("factor", "n_layers") if key not in gr]
    if missing:
        raise ValueError(
            "mode='boundary' requires explicit " + ", ".join(missing)
        )
    factor = int(gr["factor"])
    n_layers = int(gr["n_layers"])
    if factor < 2:
        raise ValueError("refinement factor must be >= 2")
    if n_layers < 1:
        raise ValueError(
            "boundary refinement n_layers must be >= 1; use mode='none' "
            "when no layer is requested"
        )
    return (
        {"mode": "boundary", "factor": factor, "n_layers": n_layers},
        {"mode": "boundary", "factor": factor, "n_layers": n_layers},
    )


def _loader_rejection_is_grid_repairable(exc: Exception) -> bool:
    """Return whether an authoritative-loader rejection is L3_4-local.

    Cheap shape and numeric checks already catch most grid defects.  Loader
    failures involving the catalog, constraint specification, or inherited
    modelling settings belong to an upstream stage and must not be presented
    to the grid-design agent as something another axis choice can repair.
    """

    message = str(exc).lower()
    upstream_markers = (
        "constraint/dof validation failed",
        "constraint_spec",
        "constraint_settings",
        "system_catalog",
        "undeclared physical/model inputs",
        "activity_model",
        "ionic_strength_mode",
        "ionic_strength.value",
        "fixed ionic strength",
        "redox_mode",
    )
    if any(marker in message for marker in upstream_markers):
        return False
    grid_markers = (
        "sweep axis",
        "sweep_axes",
        "required sweep axis",
        "grid_refine",
        "refinement",
    )
    return any(marker in message for marker in grid_markers)


def _finalize_sweep_grid(axes_json: str = "",
                         grid_refine_json: str = NOT_DEFINED) -> str:
    """Commit the FINAL numeric axis grid.

    ``axes_json`` is a JSON list of ``{name, min, max, n_points}`` -- one
    object per swept axis declared by the L3_3 constraint card.
    ``grid_refine_json`` is a mandatory design declaration: use
    ``{"mode":"none"}``, or use
    ``{"mode":"boundary","factor":...,"n_layers":...}`` for 2-D / 3-D
    adaptive refinement.  No mode or numerical knob is inferred.

    The axes are merged with the carried L3_3 spec / settings / system
    catalog into a native calc-input card and re-validated by the real
    solver loader (``load_calc_input``).  A successful call seals the
    payload; no subsequent commit call is needed.
    """
    if _FINAL_SLOT.get("restart_request") is not None:
        return (
            "RESTART_LOCKED: an LC3 restart is already requested. Do not "
            "call `finalize_sweep_grid` again; end this stage now."
        )
    _FINAL_SLOT["latest_attempt"] = {
        "tool": "finalize_sweep_grid",
        "arguments": {
            "axes_json": axes_json,
            "grid_refine_json": grid_refine_json,
        },
    }
    gallery_note = None
    if str(_SESSION.get("_sweep_method") or "") == "freeform_sweep":
        gallery_note = get_freeform_gallery_note("sweep_design")
    _FINAL_SLOT["gallery_note"] = gallery_note
    _FINAL_SLOT["latest_attempt"]["freeform_gallery_note"] = gallery_note
    if _FINAL_SLOT.get("calc_input") is not None:
        return "OK -- sweep grid was already accepted; make no further tool calls."
    if _FINAL_SLOT.get("failure_scope") == "upstream":
        return (
            "FATAL_UPSTREAM: this stage is already blocked by the upstream "
            f"calc-input error: {_FINAL_SLOT.get('error')}. Do not re-call "
            "`finalize_sweep_grid`; report this exact error."
        )

    raw = _strip_fence(axes_json)
    if not raw:
        _FINAL_SLOT["error"] = "empty_axes"
        _FINAL_SLOT["failure_scope"] = "grid"
        return "ERROR: empty `axes_json` -- provide the per-axis grid list."

    try:
        axes = json.loads(raw)
    except Exception as exc:
        _FINAL_SLOT["error"] = f"json_parse_error:{exc!r}"
        _FINAL_SLOT["failure_scope"] = "grid"
        return f"ERROR: json.loads failed on axes_json: {exc!r}. Re-call."
    if not isinstance(axes, list) or not axes:
        _FINAL_SLOT["error"] = "axes_not_list"
        _FINAL_SLOT["failure_scope"] = "grid"
        return "ERROR: `axes_json` must be a non-empty JSON list. Re-call."

    # Located, cheap pre-checks before the heavier loader gate.
    issues: List[str] = []
    dof = _SESSION.get("_dof")
    if isinstance(dof, int) and len(axes) != dof:
        issues.append(f"expected {dof} axis row(s) (dof), got {len(axes)}")
    seen: set = set()
    norm_axes: List[Dict[str, Any]] = []
    for i, ax in enumerate(axes):
        if not isinstance(ax, dict):
            issues.append(f"axis #{i} is not an object")
            continue
        name = str(ax.get("name", "")).strip()
        if not name:
            issues.append(f"axis #{i} missing 'name'")
        if name in seen:
            issues.append(f"duplicate axis '{name}'")
        seen.add(name)
        for k in ("min", "max", "n_points"):
            if k not in ax:
                issues.append(f"axis '{name}' missing '{k}'")
        try:
            lo, hi, npts = float(ax["min"]), float(ax["max"]), int(ax["n_points"])
            if hi <= lo:
                issues.append(f"axis '{name}' max ({hi}) must exceed min ({lo})")
            if npts < 2:
                issues.append(f"axis '{name}' n_points must be >= 2 (got {npts})")
            norm_axes.append({"name": name, "min": lo, "max": hi,
                              "n_points": npts})
        except Exception:
            issues.append(f"axis '{name}' numeric coercion failed")
    if issues:
        _FINAL_SLOT["error"] = "; ".join(issues)
        _FINAL_SLOT["failure_scope"] = "grid"
        return "ERROR: " + "; ".join(issues) + ". Re-call `finalize_sweep_grid`."

    try:
        grid_refine, refinement_design = _parse_refinement_design(
            grid_refine_json, dof=dof if isinstance(dof, int) else None)
    except Exception as exc:
        _FINAL_SLOT["error"] = f"grid_refine_invalid:{exc!r}"
        _FINAL_SLOT["failure_scope"] = "grid"
        return f"ERROR: grid_refine_json invalid: {exc!r}. Re-call."

    # Assemble the native calc-input card and run the authoritative gate.
    # Start from the full evolving card carried in from L3_1..L3_3 (so
    # ``_meta`` / ``_initial_conditions`` and any future keys ride along;
    # the loader ignores ``_``-prefixed keys) and only append the grid.
    native: Dict[str, Any] = dict(_SESSION.get("_card") or {})
    native["sweep_method"]        = _SESSION.get("_sweep_method", "")
    native["sweep_axes"]          = norm_axes
    native["system_catalog"]      = _SESSION.get("_system_catalog", {})
    native["constraint_spec"]     = _SESSION.get("_spec")
    native["constraint_settings"] = _SESSION.get("_settings") or {}
    native["_meta"]               = {
        **native.get("_meta", {}),
        "stage": "LC3_4",
    }
    if gallery_note is not None:
        native = append_freeform_gallery_note(native, gallery_note)
    native["grid_refine"] = grid_refine

    # Preserve both the agent's direct grid declaration and the exact native
    # calc-input artifact the authoritative loader is about to inspect.  If
    # that loader reports FATAL_UPSTREAM, the fresh LC3 attempt therefore sees
    # the actual rejected handoff rather than having to reconstruct it from
    # only the raw axis arguments.
    _FINAL_SLOT["latest_attempt"] = {
        **dict(_FINAL_SLOT.get("latest_attempt") or {}),
        "assembled_calc_input": native,
    }

    try:
        load_calc_input(native)
    except Exception as exc:
        if _loader_rejection_is_grid_repairable(exc):
            _FINAL_SLOT["error"] = f"grid_invalid:{exc}"
            _FINAL_SLOT["failure_scope"] = "grid"
            return (
                f"ERROR: the assembled calc-input rejected this grid: {exc}. "
                "Correct the axis/refinement declaration and re-call "
                "`finalize_sweep_grid`."
            )
        _FINAL_SLOT["error"] = f"upstream_calc_input_invalid:{exc}"
        _FINAL_SLOT["failure_scope"] = "upstream"
        _FINAL_SLOT["restart_request"] = {
            "requested_by": "LC3_4",
            "error": str(_FINAL_SLOT["error"]),
            "reason": (
                "The authoritative L3_4 loader classified the rejection as "
                "upstream; changing only the numeric grid cannot repair it."
            ),
            "automatic": True,
        }
        return (
            f"FATAL_UPSTREAM: the assembled calc-input was rejected before "
            f"solver execution: {exc}. This is not repairable by changing "
            "the L3_4 grid. Do not re-call `finalize_sweep_grid`; report this "
            "exact error so the upstream card-building stage can be fixed."
        )

    _FINAL_SLOT["payload"]    = {"sweep_axes": norm_axes,
                                 "grid_refine": grid_refine,
                                 "refinement_design": refinement_design}
    _FINAL_SLOT["calc_input"] = native
    _FINAL_SLOT["error"]      = None
    _FINAL_SLOT["failure_scope"] = None
    _FINAL_SLOT["restart_request"] = None
    n_cells = 1
    for ax in norm_axes:
        n_cells *= int(ax["n_points"])
    return (f"OK -- sweep grid accepted: {len(norm_axes)} axis/axes, "
            f"{n_cells} grid cell(s).")


def _request_lc3_restart(reason: str = "") -> str:
    """Request a fresh LC3 attempt after a deterministic grid error."""
    if _FINAL_SLOT.get("restart_request") is not None:
        return (
            "ERROR: an LC3 restart is already requested; duplicate restart "
            "requests are forbidden. End this stage now."
        )
    error = _FINAL_SLOT.get("error")
    latest_attempt = _FINAL_SLOT.get("latest_attempt")
    why = (reason or "").strip()
    if not error:
        return (
            "ERROR: an LC3 restart can be requested only after "
            "`finalize_sweep_grid` has returned an error in this run."
        )
    if latest_attempt is None:
        return (
            "ERROR: no directly emitted `finalize_sweep_grid` attempt is "
            "available to attach to the restart request."
        )
    if not why:
        return "ERROR: `reason` must explain why local correction is insufficient."
    if str(_SESSION.get("_sweep_method") or "") == "freeform_sweep":
        gallery_note = get_freeform_gallery_note("sweep_design")
        _FINAL_SLOT["gallery_note"] = gallery_note
        latest_attempt["freeform_gallery_note"] = gallery_note
    _FINAL_SLOT["restart_request"] = {
        "requested_by": "LC3_4",
        "error": str(error),
        "reason": why,
        "automatic": False,
    }
    return (
        "OK_RESTART_REQUESTED: end this stage now. The orchestrator will "
        "start LC3 again with this exact error and the latest attempted "
        "sweep-grid artifact as recovery context."
    )


def _build_agent_tools() -> Dict[str, Callable]:
    """Build the L3_4 finalize surface plus optional sweep-skill reads."""
    tools: Dict[str, Callable] = {
        "finalize_sweep_grid": _finalize_sweep_grid,
        "request_lc3_restart": _request_lc3_restart,
    }
    tools.update(get_sweep_skill_tools())
    return tools


# ════════════════════════════════════════════════════════════════════
#  Dispatcher
# ════════════════════════════════════════════════════════════════════

def _build_axis_table(hints: List[Dict[str, str]],
                      sweep_method: str) -> str:
    rows = ["[SWEEP AXES -- one grid row required per axis]",
            "| card axis | drives handle | name (use this) |",
            "|-----------|---------------|-----------------|"]
    for h in hints:
        rows.append(f"| {h['axis']} | {h['handle'] or '_(slaved)_'} "
                    f"| {h['physical']} |")
    recognised = _RECOGNISED_AXES.get(sweep_method, ())
    rec = ", ".join(recognised) if recognised else "(any -- freeform)"
    rows.append("")
    rows.append(f"[Recognised physical axis names for {sweep_method}: {rec}]")
    return "\n".join(rows)


def _render_restart_context(restart_context: Any = None) -> str:
    if restart_context in (None, "", {}):
        return ""
    if isinstance(restart_context, (dict, list)):
        rendered = json.dumps(restart_context, indent=2, default=str)
    else:
        rendered = str(restart_context).strip()
    return (
        "\n\n[LC3 RESTART CONTEXT -- evidence from the latest failed LC3 "
        "attempt]\n"
        f"{rendered}\n"
        "Generate a fresh sweep-grid artifact. Use the prior directly "
        "emitted artifact and exact error diagnostically; retain unaffected "
        "user requirements and inherited decisions."
    )


def _build_user_message(purpose: str, tasks: str, sweep_method: str,
                        dof: Any, axis_table: str,
                        restart_context: Any = None) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n"
        f"[sweep_method (chosen by L3_1): {sweep_method}]\n"
        f"[dof (number of sweep axes): {dof}]\n\n"
        f"{axis_table}\n\n"
        f"Design the numeric grid (min / max / n_points) for each axis "
        f"above. Explicitly choose no refinement or boundary refinement; "
        f"for boundary refinement declare both factor and layer count. "
        f"Commit both decisions with `finalize_sweep_grid`."
        f"{_render_restart_context(restart_context)}"
    )


def run_l3_4(
    *,
    purpose: str,
    tasks: str,
    calc_input_card_path: str | Path,
    fixed_card_path: str | Path = "",
    system_catalog_path: str | Path = "",
    output_dir: str | Path,
    restart_context: Any = None,
) -> Dict[str, Any]:
    """Run the L3_4 sweep-grid designer.

    Parameters
    ----------
    calc_input_card_path
        The single evolving ``calc_input_card.json`` (carries
        ``sweep_method``, ``_meta.dof``, ``system_catalog``,
        ``constraint_spec`` and ``constraint_settings``).  L3_4 appends
        ``sweep_axes`` (+ optional ``grid_refine``) and rewrites it as the
        final native card.
    fixed_card_path, system_catalog_path
        Accepted for orchestrator-call symmetry; not required here (the
        evolving card already carries the system catalog + spec).
    output_dir
        Where to write the per-call artefact tree.

    Returns
    -------
    dict
        ``status``, ``output_dir``, ``calc_input_path``, ``sweep_axes``,
        ``grid_refine``, ``n_cells``, ``elapsed_s``, ``report``.
    """
    purpose, tasks_text = _require_purpose_tasks(purpose, tasks)

    if _SESSION["session_dir"] is None:
        configure_l3_4_session(session_dir=Path.cwd() / "_l3_4_adhoc_session")

    call_dir = _per_call_dir()
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)

    calc_input_card_path = Path(calc_input_card_path)
    if not calc_input_card_path.exists():
        raise FileNotFoundError(
            f"L3_4: calc-input card not found: {calc_input_card_path}")

    card = _load_constraint_card(calc_input_card_path)
    sweep_method = card.get("sweep_method") or ""
    dof = (card.get("_meta") or {}).get("dof")
    spec = card.get("constraint_spec")
    settings = card.get("constraint_settings") or {}
    system_catalog = card.get("system_catalog") or {}
    if not sweep_method:
        raise ValueError("L3_4: calc-input card is missing 'sweep_method'.")
    if not isinstance(spec, dict) or not spec.get("axes"):
        raise ValueError("L3_4: calc-input card has no 'constraint_spec.axes' to range.")
    if sweep_method not in SUPPORTED_SWEEP_METHODS:
        raise ValueError(
            f"L3_4: unsupported sweep_method {sweep_method!r}; "
            f"supported: {SUPPORTED_SWEEP_METHODS}")
    stored_skill = ((card.get("_meta") or {}).get("sweep_skill_selection")
                    or {})
    declared_skill_id = (stored_skill.get("primary_skill")
                         if isinstance(stored_skill, dict) else None)
    skill_record = skill_selection_record(sweep_method, declared_skill_id)
    if skill_record["primary_skill"] is None:
        raise ValueError(
            "L3_4: the selected sweep method has no routable design skill."
        )

    if dof is None:
        dof = len(spec.get("axes") or [])

    hints = _axis_physical_hints(spec)

    _SESSION["_card"]           = card
    _SESSION["_sweep_method"]   = sweep_method
    _SESSION["_dof"]            = dof
    _SESSION["_spec"]           = spec
    _SESSION["_settings"]       = settings
    _SESSION["_system_catalog"] = system_catalog
    _SESSION["_axis_names"]     = [h["physical"] for h in hints]

    history = _SESSION["history"]; stats = _SESSION["stats"]
    if history is not None:
        history.log("L3_4_dispatch_start",
                    call_index=_SESSION["call_index"],
                    sweep_method=sweep_method, dof=dof,
                    n_axes=len(hints))

    _FINAL_SLOT["payload"]    = None
    _FINAL_SLOT["calc_input"] = None
    _FINAL_SLOT["error"]      = None
    _FINAL_SLOT["failure_scope"] = None
    _FINAL_SLOT["latest_attempt"] = None
    _FINAL_SLOT["restart_request"] = None
    _FINAL_SLOT["gallery_note"] = None

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    prior_gallery_notes = ((card.get("_meta") or {}).get(
        "freeform_gallery_notes") or [])
    system_prompt += "\n\n" + build_sweep_skill_context(
        sweep_method, "sweep_design", declared_skill_id,
        prior_gallery_notes=prior_gallery_notes, debug=_SESSION["debug"])
    tools = _build_agent_tools()
    system_prompt += "\n\n" + build_tool_instructions(tools)

    axis_table = _build_axis_table(hints, sweep_method)
    user_message = _build_user_message(purpose, tasks_text, sweep_method,
                                       dof, axis_table, restart_context)
    client = SRD46AnalysisClient.for_l1()
    _engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "", guidance_hooks=[],
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
            required_tools={"finalize_sweep_grid"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        log.error("L3_4 agent_turn raised: %s", exc, exc_info=_SESSION["debug"])
        return {
            "status":          "failed",
            "_error":          f"agent_turn_exception: {exc!r}",
            "failure_scope":   "agent_turn",
            "restart_request": None,
            "latest_attempt_artifact_path": None,
            "output_dir":      str(call_dir),
            "calc_input_path": None,
            "sweep_axes":      None,
            "grid_refine":     None,
            "n_cells":         0,
            "elapsed_s":       round(elapsed, 3),
            "report":          f"agent_turn_exception: {exc!r}",
        }

    elapsed = time.time() - t0
    payload    = _FINAL_SLOT["payload"]
    calc_input = _FINAL_SLOT["calc_input"]
    error      = _FINAL_SLOT["error"]
    failure_scope = _FINAL_SLOT["failure_scope"]
    latest_attempt = _FINAL_SLOT["latest_attempt"]
    restart_request = _FINAL_SLOT["restart_request"]
    gallery_note = _FINAL_SLOT["gallery_note"]

    latest_attempt_path: Optional[Path] = None
    if latest_attempt is not None:
        latest_attempt_path = call_dir / "latest_attempt.json"
        latest_attempt_path.write_text(
            json.dumps(latest_attempt, indent=2, default=str), encoding="utf-8")
    if restart_request is not None:
        restart_request = dict(restart_request)
        restart_request["latest_attempt_artifact_path"] = (
            str(latest_attempt_path) if latest_attempt_path else None)
        (call_dir / "restart_request.json").write_text(
            json.dumps(restart_request, indent=2), encoding="utf-8")

    sweep_axes = (payload or {}).get("sweep_axes") if payload else None
    grid_refine = (payload or {}).get("grid_refine") if payload else None
    refinement_design = ((payload or {}).get("refinement_design")
                         if payload else None)
    calc_input_path: Optional[Path] = None
    n_cells = 0
    if calc_input is not None:
        n_cells = 1
        for ax in (sweep_axes or []):
            n_cells *= int(ax["n_points"])
        calc_input_path = call_dir / "calc_input_card.json"
        calc_input_path.write_text(json.dumps(calc_input, indent=2),
                                   encoding="utf-8")

    # Persist artefacts.
    (call_dir / "input.json").write_text(json.dumps({
        "purpose": purpose, "tasks": tasks_text,
        "calc_input_card_path": str(calc_input_card_path),
        "sweep_method": sweep_method, "dof": dof,
        "sweep_skill_selection": skill_record,
        "freeform_gallery_note": gallery_note,
        "axis_hints": hints,
        "restart_context": restart_context,
    }, indent=2, default=str), encoding="utf-8")
    (call_dir / "sweep_axes.json").write_text(
        json.dumps({"sweep_axes": sweep_axes or [],
                    "grid_refine": grid_refine,
                    "refinement_design": refinement_design}, indent=2),
        encoding="utf-8")

    rows = [
        "# L3_4 Tool Calls",
        "",
        "| # | iter | tool | args (excerpt) | result_chars | elapsed_s |",
        "|--:|----:|------|----------------|-------------:|----------:|",
    ]
    for i, c in enumerate(result.tool_history, start=1):
        args_excerpt = json.dumps(c.get("arguments", {}))[:140].replace("|", "\\|")
        rows.append(
            f"| {i} | {c.get('iteration','')} | {c.get('tool','?')} "
            f"| {args_excerpt} | {c.get('result_chars','')} "
            f"| {c.get('elapsed_s','')} |"
        )
    (call_dir / "l3_4_tool_calls.md").write_text("\n".join(rows) + "\n",
                                                 encoding="utf-8")

    # Raw text the agent emitted (final answer + last context), for debugging.
    (call_dir / "agent_response.md").write_text(
        "# L3_4 agent response\n\n"
        "## Final answer (text emitted by the agent)\n\n"
        f"{result.answer or '_(empty)_'}\n\n"
        "## Final context\n\n"
        f"{result.final_context or '_(empty)_'}\n",
        encoding="utf-8",
    )

    report_lines = [
        f"# L3_4 dispatch report (call {_SESSION['call_index']:02d})",
        "",
        f"- output_dir: `{call_dir}`",
        f"- elapsed_s: {elapsed:.2f}",
        f"- llm_iterations: {result.iterations}",
        f"- llm_tool_calls: {len(result.tool_history)}",
        f"- sweep_method (from L3_1): **{sweep_method}**",
        f"- dof (number of axes): {dof}",
        "",
    ]
    if calc_input is None:
        report_lines.append(f"**Status**: FAILED ({error or 'no_payload'})")
        report_lines.append(f"- failure_scope: `{failure_scope or 'unknown'}`")
        if restart_request is not None:
            report_lines.extend([
                "",
                "## LC3 restart requested",
                f"- exact_error: `{restart_request['error']}`",
                f"- reason: {restart_request['reason']}",
                f"- latest_attempt: `{latest_attempt_path}`",
            ])
    else:
        report_lines.append("## sweep_axes")
        report_lines.append("```json")
        report_lines.append(json.dumps(sweep_axes, indent=2))
        report_lines.append("```")
        report_lines.append("")
        report_lines.append(
            f"## refinement_design: `{refinement_design}`")
        report_lines.append("")
        report_lines.append(f"## Grid: {n_cells} cell(s) across {len(sweep_axes or [])} axis/axes")
        report_lines.append(f"- calc_input_path: `{calc_input_path}`")
        if gallery_note is not None:
            report_lines.extend([
                "",
                "## Freeform gallery note (stored in final card)",
                "```json",
                json.dumps(gallery_note, indent=2),
                "```",
            ])
    report = "\n".join(report_lines)
    (call_dir / "report.md").write_text(report, encoding="utf-8")

    if stats is not None:
        stats.incr("L3_4", "dispatch_calls", 1)
        stats.incr("L3_4", "llm_iterations", result.iterations)
        stats.incr("L3_4", "tool_calls",     len(result.tool_history))
        stats.incr("L3_4", "ok" if calc_input is not None else "failed", 1)

    if _SESSION["working_memory"] is not None and calc_input_path is not None:
        try:
            _SESSION["working_memory"].set("sweep_axes", sweep_axes)
            _SESSION["working_memory"].set("calc_input_path",
                                            str(calc_input_path))
        except Exception as exc:                   # pragma: no cover
            log.warning("working_memory.set failed: %s", exc)

    if history is not None:
        history.log("L3_4_dispatch_end",
                    call_index=_SESSION["call_index"],
                    elapsed_s=elapsed,
                    ok=calc_input is not None,
                    n_cells=n_cells)

    status = ("ok" if calc_input is not None else
              "restart_requested" if restart_request is not None else
              "failed")
    return {
        "status":          status,
        "_error":          None if calc_input is not None else (
            error or "no_payload"),
        "failure_scope":   failure_scope,
        "restart_request": restart_request,
        "latest_attempt_artifact_path": (
            str(latest_attempt_path) if latest_attempt_path else None),
        "output_dir":      str(call_dir),
        "calc_input_path": str(calc_input_path) if calc_input_path else None,
        "sweep_axes":      sweep_axes,
        "grid_refine":     grid_refine,
        "refinement_design": refinement_design,
        "freeform_gallery_note": gallery_note,
        "n_cells":         n_cells,
        "elapsed_s":       round(elapsed, 3),
        "report":          report,
    }
