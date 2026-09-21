"""L3_3 -- LLM constraint designer (freeform residual-equation DSL).

Given the L0 ``purpose / tasks``, the single evolving ``calc_input_card``
(with ``sweep_method`` and ``_meta.dof`` already chosen by L3_1 and the
``system_catalog`` / ``constraint_settings`` authored by L3_2), the
system catalog built by the L1/L2 pipeline, and the final L2 free-energy
card, an LLM authors the system's **constraint card** -- a small Python
module (``axes`` / ``lets`` / ``binds``) written in lambda surface syntax
that pins every degree of freedom with a residual equation.

To stop the LLM guessing variable names, it is handed an authoritative
**variable catalog** built from the solver's own ``FreeEnergyReport``
(the same source the numcalc solver consumes).  The catalog mirrors the
card namespace exactly::

    s.E_V                  # electron / redox handle
    s.pH                   # proton handle
    s.temperature
    s.ionic_strength
    s.total["<id>"]        # element / valence / ligand totals
    s.species["<id>"]      # one dependent aqueous / solid / gas species
    s.conc["<id>"] / s.lnconc["<id>"]

The agent commits the card via ``compile_constraint_card``; it carries
the residual code plus a small non-residual *settings* sidecar
(``activity_model`` / ``solids`` / ``redox_mode`` / ``ionic_strength_mode``
and optional freeform-var scalars).  This stage does NOT choose numeric
``initial_condition`` scalars or axis grid ranges -- those are later
stages' jobs.

Correctness gate
----------------
The committed card is (1) compiled to an ``lc3_2.v1`` spec by
``compile_card`` (id-resolution against the authoritative catalog,
DOF==K, Jacobian-rank independence, domain guards); and (2) compiled
natively against the real solver via ``compile_spec`` (which lowers the
Tier-1 binds and runs ``compile_constraints``) using the authoritative
``SystemCatalog``.  A card is only accepted when both succeed,
guaranteeing it is consumable downstream.

Public API
----------
configure_l3_3_session(session_dir, history, stats, working_memory, debug)
run_l3_3(purpose, tasks, calc_input_card_path, system_catalog_path,
         fixed_card_path, output_dir, initial_conditions_text="") -> dict
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import asdict, is_dataclass
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

# ── path bootstrap so the numcalc constraint compiler imports cleanly ─
# NOTE: do NOT call ``.resolve()`` on Windows mapped drives that point at
# a UNC share -- it rewrites the path into the \\server\share form and
# Python's package finder then fails sub-package imports.  Use
# ``.absolute()`` and keep the mapped-drive root.
_HERE = Path(__file__).absolute()
_WORKFLOW_PATH = _HERE.parent / "L3_3_constraint_workflow.md"
_NUMCALC_ROOT = _HERE.parents[3] / "NIST_SRD46_core_numcalc_pipeline"
_INPUT_BUILD = _HERE.parents[2]         # NIST_SRD46_calc_input_building_agentic_pipeline
_CARD_MGMT = _INPUT_BUILD / "card_management_helpers"
_SRD46_ROOT = _HERE.parents[5]          # SRD46_research_agent/ (holds NIST_SRD46_db_agent)
for _p in (_NUMCALC_ROOT, _CARD_MGMT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Authoritative solver-side catalog + constraint compiler (the same path
# the numcalc solver consumes) and the card->report reader.
from numcalc_input_cards_reader.card_md_input_reader import (  # noqa: E402
    resolve_card_source,
)
from sweep_pipelines._sweep_input_entry_point.constraint_compiler import (  # noqa: E402
    build_default_catalog,
    merge_catalog_overrides,
    validate_catalog_against_report,
    compile_spec,
    ConstraintCompileError,
)

# LC3_3 freeform-DSL stack (helper modules in this package).
from ._constraint_helpers.constr_code_card_compiler import (  # noqa: E402
    compile_card,
    CardCompileError,
)
from ....NIST_SRD46_normalizer_helpers.constr_card_normalizer.constr_variable_catalog import (  # noqa: E402
    build_variable_catalog,
)
# Reconcile the LC1 system_catalog with the LC2 card (drop phantom
# oxidation states / ligands the card never realises) -- the same
# normalizer L3_2 runs on its own copy.  L3_3 re-reads the *original*
# catalog file, so it must prune again before validating.
from ....NIST_SRD46_normalizer_helpers.constr_card_normalizer.system_catalog_normalizer import (  # noqa: E402
    prune_system_catalog_to_report,
)
from ..sweep_template_router import (  # noqa: E402
    append_freeform_gallery_note,
    build_sweep_skill_context,
    get_freeform_gallery_note,
    get_sweep_skill_tools,
    skill_selection_record,
)

log = logging.getLogger("Analysis.L3_3")


# ════════════════════════════════════════════════════════════════════
#  Non-residual settings sidecar vocabularies
# ════════════════════════════════════════════════════════════════════
#  The DSL card proper carries only the residual equations (axes / lets /
#  binds).  These closed enums cover the *context* the residual algebra
#  does not model -- they are validated when the agent commits a card.

_SETTINGS_ENUMS: Dict[str, set] = {
    "activity_model":      {"ideal", "davies"},
    "solids":              {"include", "exclude"},
    "redox_mode":          {"axis", "fixed", "freeform", "solve", "excluded"},
    "ionic_strength_mode": {"fixed", "auto", "axis", "freeform"},
}


# ════════════════════════════════════════════════════════════════════
#  Card section slicer (for the inspect tool)
# ════════════════════════════════════════════════════════════════════

_SECTION_HEADERS: Dict[str, str] = {
    "1":   "## 1. Notation",
    "2":   "## 2. Components",
    "2.2": "### 2.2 Metals",
    "2.3": "### 2.3 Ligands",
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
        sliced = sliced[:max_chars] + f"\n\n_(truncated; original was {len(body[:end])} chars)_"
    return sliced


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
    "card_text":      "",
    "_sweep_method":  "",
    "_dof":           None,
    "_system_catalog": {},
    "_catalog_obj":   None,          # solver SystemCatalog (the gate)
    "_components":    [],            # valid s.total[...] ids
    "_species":       [],            # valid s.species[...] ids
    "_catalog_text":  "",            # rendered variable catalog (prompt)
    "_settings":      None,          # modelling regime inherited from L3_2
}


def configure_l3_3_session(
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
    out = Path(base) / f"L3_3_call_{_SESSION['call_index']:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ════════════════════════════════════════════════════════════════════
#  System-catalog helpers
# ════════════════════════════════════════════════════════════════════

def _redox_state_id(rs: Any) -> str:
    """Reduce a redox-state entry to its bare string id."""
    if isinstance(rs, str):
        return rs
    if isinstance(rs, dict):
        return str(rs.get("internal_id") or rs.get("db_id")
                   or rs.get("id") or rs.get("name") or "")
    return str(rs)


def _normalize_redox_states(sc: Dict[str, Any]) -> None:
    """In-place: coerce ``chemical_system.metals[].redox_states`` to str ids.

    The LC1 catalog stores redox states as dicts; the solver's catalog
    merge expects bare valence strings, so flatten them here.
    """
    cs = sc.get("chemical_system")
    if not isinstance(cs, dict):
        return
    for m in (cs.get("metals") or []):
        if isinstance(m, dict) and m.get("redox_states"):
            m["redox_states"] = [
                rid for rid in (_redox_state_id(r) for r in m["redox_states"])
                if rid
            ]


def _load_system_catalog(path: Path) -> Dict[str, Any]:
    """Read the L1/L2 system catalog.

    Accepts a file that is either the bare ``system_catalog`` dict or a
    wrapper object carrying it under a ``system_catalog`` key (the shape
    of LC1's ``lc1_sweep_input.json``).
    """
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and "system_catalog" in obj:
        sc = obj.get("system_catalog") or {}
    else:
        sc = obj or {}
    if not isinstance(sc, dict):
        raise ValueError(f"L3_3: system_catalog in {path} is not an object")
    _normalize_redox_states(sc)
    return sc


# ════════════════════════════════════════════════════════════════════
#  Tool surface
# ════════════════════════════════════════════════════════════════════

_FINAL_SLOT: Dict[str, Any] = {
    "payload": None,
    "bindings": None,
    "error": None,
    "latest_attempt": None,
    "restart_request": None,
}


def _inspect_card_section(section: str = "") -> str:
    key = (section or "").strip()
    if key not in _SECTION_HEADERS:
        return (f"ERROR: section={key!r} not allowed. "
                f"Valid: {sorted(_SECTION_HEADERS)}")
    text = _SESSION.get("card_text") or ""
    if not text:
        return "_(no card text bound to this session)_"
    return _slice_section(text, _SECTION_HEADERS[key])


def _strip_fence(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:python|py)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _spec_handle(node: Any) -> Optional[str]:
    if not isinstance(node, dict):
        return None
    ref = str(node.get("ref") or "")
    if ref in {"temperature", "ionic_strength", "pH", "E_V"}:
        return f"s.{ref}"
    if ref == "total" and node.get("id") is not None:
        return f's.total["{node["id"]}"]'
    return None


def _validate_deferred_closures(
    spec: Dict[str, Any],
    deferred: List[Dict[str, Any]],
) -> List[str]:
    """Ensure every L3_2 deferral is closed with the declared L3_3 role."""
    by_handle: Dict[str, List[Dict[str, Any]]] = {}
    for bind in spec.get("binds", []) or []:
        handle = _spec_handle(bind.get("lhs"))
        if handle:
            by_handle.setdefault(handle, []).append(bind)
    issues: List[str] = []
    for item in deferred or []:
        handle = str(item.get("handle") or "")
        role = str(item.get("role") or "")
        matches = by_handle.get(handle, [])
        if not matches:
            issues.append(
                f"deferred handle {handle} is not closed by any L3_3 bind")
            continue
        rhs = matches[0].get("rhs")
        if role == "swept":
            if not (isinstance(rhs, dict) and set(rhs) == {"axis"}):
                issues.append(
                    f"deferred swept handle {handle} must be tied directly to "
                    "one axis")
        elif role == "derived":
            if isinstance(rhs, dict) and "const" in rhs:
                issues.append(
                    f"deferred derived handle {handle} was fixed to a constant; "
                    "re-run L3_2 or author the declared relation")
    return issues


def _build_settings(activity_model: str, solids: str, redox_mode: str,
                    ionic_strength_mode: str,
                    freeform_vars: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    settings: Dict[str, Any] = {
        "activity_model":      activity_model,
        "solids":              solids,
        "redox_mode":          redox_mode,
        "ionic_strength_mode": ionic_strength_mode,
    }
    if freeform_vars:
        settings["freeform_vars"] = freeform_vars
    return settings


_DIRECT_AXIS_REFS = {
    "pH",
    "E_V",
    "a_w",
    "temperature",
    "ionic_strength",
}


def _physical_axis_names(spec: Dict[str, Any]) -> List[str]:
    """Return solver runtime-axis names for the card's symbolic axes.

    LC3 cards deliberately use symbolic names such as ``pH_axis`` while the
    native compiler consumes the physical coordinates they drive (``pH``).
    Keep this derivation aligned with L3_4: prefer a direct axis bind and use
    suffix stripping only for an axis referenced exclusively by a formula.
    """
    binds = list(spec.get("binds", []) or [])
    physical: List[str] = []
    for raw_axis in list(spec.get("axes", []) or []):
        axis = str(raw_axis)
        mapped = ""
        for bind in binds:
            rhs = bind.get("rhs")
            if not (isinstance(rhs, dict) and rhs.get("axis") == axis):
                continue
            lhs = bind.get("lhs") or {}
            ref = str(lhs.get("ref") or "")
            component_id = lhs.get("id")
            if ref in _DIRECT_AXIS_REFS:
                mapped = ref
            elif ref == "total" and component_id:
                mapped = str(component_id)
            if mapped:
                break
        if not mapped:
            mapped = axis
            for suffix in ("_tot_axis", "_axis"):
                if mapped.endswith(suffix):
                    mapped = mapped[:-len(suffix)]
                    break
        physical.append(mapped)
    return physical


def _compile_constraint_card(
    card_source: str = "",
    expected_K: str = "",
) -> str:
    """Compile + accept the FINAL lc3_2 constraint *card* (the residual code).

    ``card_source`` is the Python card module string with three top-level
    bindings -- ``axes`` / ``lets`` / ``binds`` -- written in lambda
    surface syntax against the variable catalog handles (``s.pH``,
    ``s.E_V``, ``s.total["<id>"]``, ``s.species["<id>"]`` ...).  It is
    parsed with ``ast`` and NEVER executed.

    The non-residual *settings* sidecar (activity model, solids, redox
    mode, ionic-strength mode) is **inherited from L3_2** -- it is NOT
    chosen here.  Author the card so it is CONSISTENT with those settings
    (e.g. ``ionic_strength_mode=auto`` or ``none`` -> do not pin
    ``s.ionic_strength``; ``=fixed`` -> pin it). On success the
    card is:

      1. compiled to an ``lc3_2.v1`` spec (id-resolution against the
         authoritative catalog, DOF==K, Jacobian-rank independence,
         domain guards) via ``compile_card``;
      2. compiled natively against the real solver via ``compile_spec``
         (lowers the Tier-1 binds and runs ``compile_constraints``)
         using the authoritative ``SystemCatalog`` and the inherited
         settings.

    Calling this successfully ends the run.
    """
    if _FINAL_SLOT.get("restart_request") is not None:
        return (
            "RESTART_LOCKED: an LC3 restart is already requested. Do not "
            "call `compile_constraint_card` again; end this stage now."
        )
    _FINAL_SLOT["latest_attempt"] = {
        "tool": "compile_constraint_card",
        "arguments": {
            "card_source": card_source,
            "expected_K": expected_K,
        },
    }
    gallery_note = None
    if str(_SESSION.get("_sweep_method") or "") == "freeform_sweep":
        gallery_note = get_freeform_gallery_note("constraints")
    _FINAL_SLOT["gallery_note"] = gallery_note
    _FINAL_SLOT["latest_attempt"]["freeform_gallery_note"] = gallery_note
    src = _strip_fence(card_source)
    if not src:
        _FINAL_SLOT["error"] = "empty_card"
        return "ERROR: empty `card_source` -- provide the axes/lets/binds card."

    # The modelling regime is inherited from L3_2 (validated there).
    inherited = dict(_SESSION.get("_settings") or {})
    missing_settings = [
        key for key in ("activity_model", "solids", "redox_mode",
                        "ionic_strength_mode")
        if inherited.get(key) in (None, "", "Not defined")
    ]
    if missing_settings:
        _FINAL_SLOT["error"] = "undeclared_settings:" + ",".join(missing_settings)
        return (
            "ERROR: inherited physical/model settings are Not defined: "
            f"{missing_settings}. Re-run L3_2 and explicitly declare them.")
    activity_model      = inherited["activity_model"]
    solids              = inherited["solids"]
    redox_mode          = inherited["redox_mode"]
    ionic_strength_mode = inherited["ionic_strength_mode"]
    freeform_vars: Dict[str, Any] = dict(inherited.get("freeform_vars", {}) or {})

    issues: List[str] = []
    exp_K: Optional[int] = None
    if str(expected_K).strip():
        try:
            exp_K = int(expected_K)
        except Exception:
            issues.append(f"expected_K={expected_K!r} is not an integer")
    if issues:
        _FINAL_SLOT["error"] = "; ".join(issues)
        return "ERROR: " + "; ".join(issues) + ". Re-call `compile_constraint_card`."

    components = _SESSION.get("_components", [])
    species    = _SESSION.get("_species", [])
    catalog    = _SESSION.get("_catalog_obj")

    # 1. compile the DSL card -> lc3_2.v1 spec.
    try:
        spec = compile_card(
            src,
            components=components,
            species=species,
            expected_K=exp_K,
            source_name="l3_3_constraint_card.py",
        )
    except CardCompileError as exc:
        lines = [f"line {i.get('line')}: {i.get('msg')}" for i in exc.issues]
        _FINAL_SLOT["error"] = "compile_error:" + "; ".join(lines)
        return ("ERROR: the constraint card did not compile:\n  "
                + "\n  ".join(lines)
                + "\nFix the card and re-call `compile_constraint_card`.")
    except SyntaxError as exc:
        _FINAL_SLOT["error"] = f"card_syntax:{exc!r}"
        return (f"ERROR: card is not valid Python: {exc}. "
                f"Re-call `compile_constraint_card`.")

    deferred_issues = _validate_deferred_closures(
        spec, list(_SESSION.get("_deferred_conditions") or []))
    if deferred_issues:
        _FINAL_SLOT["error"] = "deferred_closure_error:" + "; ".join(
            deferred_issues)
        return (
            "ERROR: the constraint card does not honor L3_2 deferrals:\n  "
            + "\n  ".join(deferred_issues)
            + "\nFix the card and re-call `compile_constraint_card`.")

    settings = _build_settings(activity_model, solids, redox_mode,
                               ionic_strength_mode, freeform_vars)

    # 2. definitive gate: compile the spec natively against the real
    #    authoritative catalog.  ``compile_spec`` lowers the Tier-1 binds
    #    and runs the solver's own ``compile_constraints`` internally --
    #    no intermediate bindings list is materialised.
    bindings: List[Any] = []
    if catalog is not None:
        try:
            runtime_axes = _physical_axis_names(spec)
            compiled = compile_spec(
                catalog, runtime_axes, spec, settings)
        except ConstraintCompileError as exc:
            _FINAL_SLOT["error"] = f"constraint_compile_error:{exc}"
            return (f"ERROR: the solver rejected these constraints: {exc}. "
                    f"Re-call `compile_constraint_card` after fixing it.")
        except Exception as exc:                   # pragma: no cover
            _FINAL_SLOT["error"] = f"constraint_compile_exception:{exc!r}"
            return (f"ERROR: unexpected constraint-compile failure: {exc!r}. "
                    f"Re-call `compile_constraint_card`.")
        bindings = list(compiled.eval_order)

    _FINAL_SLOT["payload"]  = {"spec": spec, "settings": settings}
    _FINAL_SLOT["bindings"] = bindings
    _FINAL_SLOT["gallery_note"] = gallery_note
    _FINAL_SLOT["error"]    = None
    _FINAL_SLOT["restart_request"] = None
    n_binds = len(spec.get("binds", []) or [])
    return (f"OK -- constraint card accepted: {n_binds} residual bind(s), "
            f"{len(bindings)} solver binding(s); redox_mode={redox_mode}.")


def _request_lc3_restart(reason: str = "") -> str:
    """Request a fresh LC3 attempt after a deterministic compile error."""
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
            "`compile_constraint_card` has returned an error in this run."
        )
    if latest_attempt is None:
        return (
            "ERROR: no directly emitted `compile_constraint_card` attempt "
            "is available to attach to the restart request."
        )
    if not why:
        return "ERROR: `reason` must explain why local correction is insufficient."
    if str(_SESSION.get("_sweep_method") or "") == "freeform_sweep":
        gallery_note = get_freeform_gallery_note("constraints")
        _FINAL_SLOT["gallery_note"] = gallery_note
        latest_attempt["freeform_gallery_note"] = gallery_note
    _FINAL_SLOT["restart_request"] = {
        "requested_by": "LC3_3",
        "error": str(error),
        "reason": why,
    }
    return (
        "OK_RESTART_REQUESTED: end this stage now. The orchestrator will "
        "start LC3 again with this exact error and the latest attempted "
        "constraint artifact as recovery context."
    )


def _build_agent_tools() -> Dict[str, Callable]:
    """Build the L3_3 compile/inspection surface plus optional skill reads."""
    tools: Dict[str, Callable] = {
        "inspect_card_section":    _inspect_card_section,
        "compile_constraint_card": _compile_constraint_card,
        "request_lc3_restart":     _request_lc3_restart,
    }
    tools.update(get_sweep_skill_tools())
    return tools


def _infer_redox_mode(spec: Dict[str, Any]) -> str:
    """Infer the redox input mode from how the card treats ``E_V``."""
    axes = [a.lower() for a in (spec.get("axes", []) or [])]
    if any(a.startswith("e") for a in axes):
        # an E_V-like axis is declared
        for b in spec.get("binds", []) or []:
            rhs = b.get("rhs")
            lhs = b.get("lhs")
            if (isinstance(lhs, dict) and lhs.get("ref") == "E_V"
                    and isinstance(rhs, dict) and "axis" in rhs):
                return "axis"
    for b in spec.get("binds", []) or []:
        lhs = b.get("lhs")
        rhs = b.get("rhs")
        if isinstance(lhs, dict) and lhs.get("ref") == "E_V":
            if isinstance(rhs, dict) and "const" in rhs:
                return "fixed"
            if isinstance(rhs, dict) and "axis" in rhs:
                return "axis"
            return "freeform"
    return "excluded"


# ════════════════════════════════════════════════════════════════════
#  Dispatcher
# ════════════════════════════════════════════════════════════════════

def _build_card_snapshot(card_text: str) -> str:
    parts: List[str] = []
    for hdr in ("### 2.2 Metals", "### 2.3 Ligands", "### 2.4 Metal Valence"):
        sec = _slice_section(card_text, hdr, max_chars=4000)
        if sec:
            parts.append(sec)
    return "\n\n".join(parts) or "_(card §2 not found)_"


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
        "Generate a fresh constraint artifact. Use the prior directly "
        "emitted artifact and exact error diagnostically; retain unaffected "
        "user requirements and inherited decisions."
    )


def _build_user_message(purpose: str, tasks: str, sweep_method: str,
                        dof: Any, catalog_text: str, snapshot: str,
                        initial_conditions_text: str = "",
                        settings: Optional[Dict[str, Any]] = None,
                        restart_context: Any = None) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    init_block = ""
    if (initial_conditions_text or "").strip():
        init_block = (
            f"[Initial-state decisions from L3_2 -- reuse fixed KNOWN / "
            f"ASSUMED pins and close every explicitly deferred handle with "
            f"its declared swept/derived role]\n"
            f"{initial_conditions_text.strip()}\n\n"
        )
    settings_block = ""
    if settings:
        ism = settings["ionic_strength_mode"]
        rdx = settings["redox_mode"]
        settings_block = (
            f"[Modelling regime decided by L3_2 -- INHERITED, do NOT choose; "
            f"author binds CONSISTENT with it]\n"
            f"  activity_model      = {settings['activity_model']}\n"
            f"  solids              = {settings['solids']}\n"
            f"  redox_mode          = {rdx}\n"
            f"  ionic_strength_mode = {ism}\n"
            f"  -> ionic_strength_mode=fixed: pin s.ionic_strength with a "
            f"const bind; =auto: do NOT bind s.ionic_strength (solver "
            f"computes I); =none: do NOT bind it.\n"
            f"  -> redox_mode=axis: add an E_V axis + tie bind; =solve: do "
            f"not bind s.E_V, bind one parent total for every redox-active "
            f"metal, and add exactly one global state-subtotal target; "
            f"=excluded: do not bind s.E_V and declare a full-rank set of "
            f"independent state totals.\n\n"
        )
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n"
        f"[sweep_method (chosen by L3_1): {sweep_method}]\n"
        f"[dof (number of sweep axes chosen by L3_1): {dof}]\n\n"
        f"{catalog_text}\n\n"
        f"{init_block}"
        f"{settings_block}"
        f"[Card section 2 snapshot -- components / metals / ligands]\n"
        f"{snapshot}\n\n"
        f"Author the lc3_2 constraint card (axes / lets / binds) using ONLY "
        f"the handles above, then commit it with `compile_constraint_card`."
        f"{_render_restart_context(restart_context)}"
    )


def _build_aligned_constraint_catalogs(
    report: Any,
    system_catalog: Dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Build native and prompt catalogs from one validated override decision.

    A requested component may be present in the LC1 system catalog but absent
    from the materialized free-energy report.  Reconcile first (prune phantom
    entries the card never realises -- same normalizer L3_2 applies) so a few
    unrealised entries do not void the whole override: wholesale rejection
    silently dropped an L1-committed divalent-only restriction and exploded
    the basis to every oxidation state (L2_1, 2026-09-06).  Only when the
    *pruned* override still fails validation is it rejected for both
    catalogs; otherwise the prompt could advertise a handle the native
    constraint compiler cannot accept.
    """

    catalog_obj = build_default_catalog(report)
    validated_system_catalog: Dict[str, Any] | None = None
    if system_catalog:
        prune_notes = prune_system_catalog_to_report(system_catalog, report)
        if prune_notes:
            log.info("L3_3: system_catalog reconciled with card: %s",
                     "; ".join(prune_notes))
        try:
            catalog_obj = merge_catalog_overrides(catalog_obj, system_catalog)
            validate_catalog_against_report(catalog_obj, report)
            validated_system_catalog = system_catalog
        except Exception as exc:                   # keep authoritative base
            log.warning("L3_3: system_catalog override ignored: %s", exc)
            catalog_obj = build_default_catalog(report)
    var_catalog = build_variable_catalog(report, validated_system_catalog)
    return catalog_obj, var_catalog


def _serialize_compiler_catalog(
    catalog_obj: Any,
    source_catalog: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Serialize the exact catalog used by the native constraint compiler.

    L3_3 may reject an incomplete LC1 override and compile against the
    report-derived catalog instead.  L3_4 must receive that same resolved
    catalog; otherwise a constraint accepted here can fail downstream because
    the evolving card still contains the stale override.
    """

    if not is_dataclass(catalog_obj):
        raise TypeError(
            "L3_3 compiler catalog is not a dataclass and cannot be "
            "serialized deterministically"
        )
    resolved = asdict(catalog_obj)
    if not isinstance(resolved, dict):  # defensive guard for future types
        raise TypeError("L3_3 compiler catalog did not serialize to an object")
    # Retain non-compiler provenance keys, but make the resolved compiler
    # fields authoritative.
    aligned = dict(source_catalog or {})
    aligned.update(resolved)
    return aligned


def run_l3_3(
    *,
    purpose: str,
    tasks: str,
    calc_input_card_path: str | Path,
    system_catalog_path: str | Path,
    fixed_card_path: str | Path,
    output_dir: str | Path,
    initial_conditions_text: str = "",
    constraint_settings: Optional[Dict[str, Any]] = None,
    restart_context: Any = None,
) -> Dict[str, Any]:
    """Run the L3_3 constraint designer.

    Parameters
    ----------
    calc_input_card_path
        The single evolving ``calc_input_card.json`` (carries
        ``sweep_method``, ``_meta.dof`` and the ``system_catalog`` /
        ``constraint_settings`` authored by L3_2).  L3_3 appends the
        ``constraint_spec`` it designs and rewrites the same card.
    system_catalog_path
        The L1/L2 system-catalog file (e.g. LC1's ``lc1_sweep_input.json``);
        either the bare ``system_catalog`` dict or a wrapper carrying it.
    fixed_card_path
        The final L2 free-energy markdown card.  Resolved to a
        ``FreeEnergyReport`` to build the authoritative variable catalog
        (and read so the agent can inspect section 2 components).
    initial_conditions_text
        Optional code-style brief of the KNOWN / ASSUMED initial
        conditions produced by the L3_2 initial-condition designer; shown
        to the agent so it can lift the pre-decided pins verbatim.
    constraint_settings
        The non-residual modelling-regime settings (``activity_model`` /
        ``solids`` / ``redox_mode`` / ``ionic_strength_mode`` + optional
        ``freeform_vars``) decided by L3_2.  Inherited here -- the agent
        no longer chooses them; the card is authored to be consistent
        with them and they feed ``compile_spec`` directly.

    Returns
    -------
    dict
        ``status``, ``output_dir``, ``calc_input_card_path``,
        ``spec_path``, ``settings_path``, ``spec``, ``settings``,
        ``expand_ok``, ``n_bindings``, ``elapsed_s``, ``report``.
    """
    purpose, tasks_text = _require_purpose_tasks(purpose, tasks)

    if _SESSION["session_dir"] is None:
        configure_l3_3_session(session_dir=Path.cwd() / "_l3_3_adhoc_session")

    call_dir = _per_call_dir()
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)

    calc_input_card_path = Path(calc_input_card_path)
    system_catalog_path = Path(system_catalog_path)
    fixed_card_path = Path(fixed_card_path)
    if not calc_input_card_path.exists():
        raise FileNotFoundError(
            f"L3_3: calc-input card not found: {calc_input_card_path}")
    if not system_catalog_path.exists():
        raise FileNotFoundError(
            f"L3_3: system catalog not found: {system_catalog_path}")
    if not fixed_card_path.exists():
        raise FileNotFoundError(
            f"L3_3: fixed card not found: {fixed_card_path}")

    card = json.loads(calc_input_card_path.read_text(encoding="utf-8"))
    sweep_method = card.get("sweep_method")
    dof = (card.get("_meta") or {}).get("dof")
    if not sweep_method:
        raise ValueError("L3_3: calc-input card is missing 'sweep_method'.")
    stored_skill = ((card.get("_meta") or {}).get("sweep_skill_selection")
                    or {})
    declared_skill_id = (stored_skill.get("primary_skill")
                         if isinstance(stored_skill, dict) else None)
    skill_record = skill_selection_record(sweep_method, declared_skill_id)
    if skill_record["primary_skill"] is None:
        raise ValueError(
            "L3_3: the selected sweep method has no routable design skill."
        )

    system_catalog = _load_system_catalog(system_catalog_path)
    card_text = fixed_card_path.read_text(encoding="utf-8")

    # Resolve the card -> authoritative FreeEnergyReport, then build the
    # solver SystemCatalog (totals namespace) + the variable catalog the
    # agent references.  This is the SAME path the numcalc solver consumes,
    # so the handles the agent sees are exactly the solver's own ids.
    report = resolve_card_source(fixed_card_path)
    catalog_obj, var_catalog = _build_aligned_constraint_catalogs(
        report, system_catalog or None
    )
    aligned_system_catalog = _serialize_compiler_catalog(
        catalog_obj, system_catalog
    )

    _SESSION["card_text"]       = card_text
    _SESSION["_sweep_method"]   = sweep_method
    _SESSION["_dof"]            = dof
    _SESSION["_system_catalog"] = aligned_system_catalog
    _SESSION["_catalog_obj"]    = catalog_obj
    _SESSION["_components"]     = var_catalog.components
    _SESSION["_species"]        = var_catalog.species
    _SESSION["_catalog_text"]   = var_catalog.text
    _SESSION["_settings"]       = dict(constraint_settings or {})
    _SESSION["_deferred_conditions"] = list(
        card.get("_deferred_conditions") or [])
    history = _SESSION["history"]; stats = _SESSION["stats"]
    if history is not None:
        history.log("L3_3_dispatch_start",
                    call_index=_SESSION["call_index"],
                    sweep_method=sweep_method, dof=dof,
                    n_components=len(var_catalog.components))

    _FINAL_SLOT["payload"]  = None
    _FINAL_SLOT["bindings"] = None
    _FINAL_SLOT["error"]    = None
    _FINAL_SLOT["gallery_note"] = None
    _FINAL_SLOT["latest_attempt"] = None
    _FINAL_SLOT["restart_request"] = None

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    prior_gallery_notes = ((card.get("_meta") or {}).get(
        "freeform_gallery_notes") or [])
    system_prompt += "\n\n" + build_sweep_skill_context(
        sweep_method, "constraints", declared_skill_id,
        prior_gallery_notes=prior_gallery_notes, debug=_SESSION["debug"])
    tools = _build_agent_tools()
    system_prompt += "\n\n" + build_tool_instructions(tools)

    snapshot = _build_card_snapshot(card_text)
    user_message = _build_user_message(purpose, tasks_text, sweep_method, dof,
                                       var_catalog.text, snapshot,
                                       initial_conditions_text,
                                       _SESSION.get("_settings"),
                                       restart_context)
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
            required_tools={"compile_constraint_card"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        log.error("L3_3 agent_turn raised: %s", exc, exc_info=_SESSION["debug"])
        return {
            "status":               "failed",
            "_error":               f"agent_turn_exception: {exc!r}",
            "restart_request":      None,
            "latest_attempt_artifact_path": None,
            "output_dir":           str(call_dir),
            "calc_input_card_path": None,
            "sweep_constraints":    None,
            "expand_ok":            False,
            "n_bindings":           0,
            "elapsed_s":            round(elapsed, 3),
            "report":               f"agent_turn_exception: {exc!r}",
        }

    elapsed = time.time() - t0
    payload  = _FINAL_SLOT["payload"]
    bindings = _FINAL_SLOT["bindings"]
    error    = _FINAL_SLOT["error"]
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

    calc_card_out_path: Optional[Path] = None
    spec_path: Optional[Path] = None
    expand_ok = False
    spec = (payload or {}).get("spec") if payload else None
    settings = (payload or {}).get("settings") if payload else None

    if payload is not None:
        expand_ok = True
        # Debug-only residual spec snapshot (the authoritative copy is
        # folded into the evolving card under ``constraint_spec``).
        spec_path = call_dir / "sweep_card.lc3_2.json"
        spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        # Extend the single evolving calc-input card with the designed
        # constraint spec.  Persist the exact report-aligned system catalog
        # used by this stage's native compiler so L3_4 validates the same DOF
        # namespace instead of an older LC1/L3_2 override.
        card["system_catalog"] = aligned_system_catalog
        card["constraint_spec"] = spec
        if settings is not None:
            card["constraint_settings"] = settings
        card.setdefault("_meta", {})["stage"] = "LC3_3"
        card["_meta"]["sweep_skill_selection"] = skill_record
        if gallery_note is not None:
            card = append_freeform_gallery_note(card, gallery_note)
        calc_card_out_path = call_dir / "calc_input_card.json"
        calc_card_out_path.write_text(
            json.dumps(card, indent=2), encoding="utf-8")

    # Persist artefacts.
    (call_dir / "input.json").write_text(json.dumps({
        "purpose": purpose, "tasks": tasks_text,
        "calc_input_card_path": str(calc_input_card_path),
        "system_catalog_path": str(system_catalog_path),
        "fixed_card_path": str(fixed_card_path),
        "sweep_method": sweep_method, "dof": dof,
        "sweep_skill_selection": skill_record,
        "freeform_gallery_note": gallery_note,
        "components": _SESSION.get("_components", []),
        "n_species": len(_SESSION.get("_species", [])),
        "restart_context": restart_context,
    }, indent=2, default=str), encoding="utf-8")
    (call_dir / "card_snapshot.md").write_text(snapshot, encoding="utf-8")
    (call_dir / "variable_catalog.txt").write_text(
        _SESSION.get("_catalog_text", ""), encoding="utf-8")
    (call_dir / "constraints_payload.json").write_text(
        json.dumps(payload if payload is not None
                   else {"_error": error or "no_payload"}, indent=2),
        encoding="utf-8",
    )
    (call_dir / "expanded_bindings.json").write_text(
        json.dumps(bindings if bindings is not None else [], indent=2),
        encoding="utf-8",
    )

    rows = [
        "# L3_3 Tool Calls",
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
    (call_dir / "l3_3_tool_calls.md").write_text("\n".join(rows) + "\n",
                                                 encoding="utf-8")

    # Raw text the agent emitted (final answer + last context), for debugging.
    (call_dir / "agent_response.md").write_text(
        "# L3_3 agent response\n\n"
        "## Final answer (text emitted by the agent)\n\n"
        f"{result.answer or '_(empty)_'}\n\n"
        "## Final context\n\n"
        f"{result.final_context or '_(empty)_'}\n",
        encoding="utf-8",
    )

    report_lines = [
        f"# L3_3 dispatch report (call {_SESSION['call_index']:02d})",
        "",
        f"- output_dir: `{call_dir}`",
        f"- elapsed_s: {elapsed:.2f}",
        f"- llm_iterations: {result.iterations}",
        f"- llm_tool_calls: {len(result.tool_history)}",
        f"- sweep_method (from L3_1): **{sweep_method}**",
        f"- dof (from L3_1): {dof}",
        "",
    ]
    if payload is None:
        report_lines.append(f"**Status**: FAILED ({error or 'no_payload'})")
        if restart_request is not None:
            report_lines.extend([
                "",
                "## LC3 restart requested",
                f"- exact_error: `{restart_request['error']}`",
                f"- reason: {restart_request['reason']}",
                f"- latest_attempt: `{latest_attempt_path}`",
            ])
    else:
        report_lines.append("## lc3_2 spec")
        report_lines.append("```json")
        report_lines.append(json.dumps(spec, indent=2))
        report_lines.append("```")
        report_lines.append("")
        report_lines.append("## settings")
        report_lines.append("```json")
        report_lines.append(json.dumps(settings, indent=2))
        report_lines.append("```")
        report_lines.append("")
        report_lines.append(
            f"## Compile gate: OK -- {len(bindings or [])} solver binding(s)")
        report_lines.append(f"- calc_input_card_path: `{calc_card_out_path}`")
        if gallery_note is not None:
            report_lines.extend([
                "",
                "## Freeform gallery note (passed to L3_4)",
                "```json",
                json.dumps(gallery_note, indent=2),
                "```",
            ])
    report = "\n".join(report_lines)
    (call_dir / "report.md").write_text(report, encoding="utf-8")

    if stats is not None:
        stats.incr("L3_3", "dispatch_calls", 1)
        stats.incr("L3_3", "llm_iterations", result.iterations)
        stats.incr("L3_3", "tool_calls",     len(result.tool_history))
        stats.incr("L3_3", "ok" if payload is not None else "failed", 1)

    if _SESSION["working_memory"] is not None and calc_card_out_path is not None:
        try:
            _SESSION["working_memory"].set("constraint_spec", spec)
            _SESSION["working_memory"].set("constraint_settings", settings)
            _SESSION["working_memory"].set("calc_input_card_path",
                                            str(calc_card_out_path))
        except Exception as exc:                   # pragma: no cover
            log.warning("working_memory.set failed: %s", exc)

    if history is not None:
        history.log("L3_3_dispatch_end",
                    call_index=_SESSION["call_index"],
                    elapsed_s=elapsed,
                    expand_ok=expand_ok,
                    n_bindings=len(bindings or []))

    status = ("ok" if payload is not None else
              "restart_requested" if restart_request is not None else
              "failed")
    return {
        "status":               status,
        "_error":               None if payload is not None else (
            error or "no_payload"),
        "restart_request":      restart_request,
        "latest_attempt_artifact_path": (
            str(latest_attempt_path) if latest_attempt_path else None),
        "output_dir":           str(call_dir),
        "calc_input_card_path": str(calc_card_out_path) if calc_card_out_path else None,
        "spec_path":            str(spec_path) if spec_path else None,
        "settings_path":        None,
        "spec":                 spec,
        "settings":             settings,
        "freeform_gallery_note": gallery_note,
        "expand_ok":            expand_ok,
        "n_bindings":           len(bindings or []),
        "elapsed_s":            round(elapsed, 3),
        "report":               report,
    }

