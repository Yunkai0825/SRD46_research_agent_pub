"""L3_2 -- LLM initial-condition designer (code-card style).

Runs **before** the LC3_3 constraint designer.  Given the L0
``purpose / tasks``, the L3_1 partial calc-input (``sweep_method`` /
``dof``), the L1/L2 system catalog and the final L2 free-energy card, an
LLM lists everything that is already **known** or can be reasonably
**assumed** about the system's starting state -- temperature, ionic
strength, fixed pH / redox, component totals -- *before* the constraint
algebra is authored.

The output is an **initial-condition card**: a small Python module
written in the SAME lambda surface syntax as the LC3_3 constraint card,
but limited to constant assignments (no sweep axes, no freeform coupling)::

    inits = [
      {"id": "T",  "lhs": lambda s: s.temperature,    "value": 298.15, "basis": "known"},
      {"id": "I",  "lhs": lambda s: s.ionic_strength, "value": 0.1,    "basis": "assumed"},
      {"id": "Cu", "lhs": lambda s: s.total["Cu"],    "value": 1e-3,   "basis": "assumed"},
    ]

This is a drop-in subset of the constraint binds, so the constraint
designer can lift the entries it needs verbatim.  To stop the LLM
guessing variable names it is handed the SAME authoritative **variable
catalog** the constraint designer uses (``build_variable_catalog``).

The card is committed via ``commit_initial_conditions``; it is parsed
with ``ast`` and NEVER executed, then validated against the authoritative
id pools (``compile_initcond_card``).

Public API
----------
configure_l3_2_session(session_dir, history, stats, working_memory, debug)
run_l3_2(purpose, tasks, calc_input_card_path, system_catalog_path,
         fixed_card_path, output_dir) -> dict
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

# ── path bootstrap so the numcalc catalog builder imports cleanly ────
# NOTE: do NOT call ``.resolve()`` on Windows mapped drives that point at
# a UNC share -- it rewrites the path into the \\server\share form and
# Python's package finder then fails sub-package imports.  Use
# ``.absolute()`` and keep the mapped-drive root.
_HERE = Path(__file__).absolute()
_WORKFLOW_PATH = _HERE.parent / "L3_2_initial_condition_workflow.md"
_NUMCALC_ROOT = _HERE.parents[3] / "NIST_SRD46_core_numcalc_pipeline"
_SRD46_ROOT = _HERE.parents[5]          # SRD46_research_agent/ (holds NIST_SRD46_db_agent)
for _p in (_NUMCALC_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Authoritative card->report reader (same source the solver consumes).
from numcalc_input_cards_reader.card_md_input_reader import (  # noqa: E402
    resolve_card_source,
)

# Reuse the constraint designer's authoritative variable-catalog pipeline
# (the exact same handles/ids the LC3_3 agent references).
from ....NIST_SRD46_normalizer_helpers.constr_card_normalizer.constr_variable_catalog import (  # noqa: E402
    build_variable_catalog,
)

# Reconcile the LC1 system_catalog with the LC2 card (drop phantom
# oxidation states / ligands the card never realises) so the solver's
# strict ``validate_catalog_against_report`` accepts the final card.
from ....NIST_SRD46_normalizer_helpers.constr_card_normalizer.system_catalog_normalizer import (  # noqa: E402
    prune_system_catalog_to_report,
)

# Local initial-condition card validator.
from ._initcond_helpers.initcond_card import (  # noqa: E402
    compile_initcond_card,
    render_initcond_brief,
    InitCondCompileError,
)
from ..sweep_template_router import (  # noqa: E402
    append_freeform_gallery_note,
    build_sweep_skill_context,
    get_freeform_gallery_note,
    get_sweep_skill_tools,
    skill_selection_record,
)

log = logging.getLogger("Analysis.L3_2")


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
    "session_dir":     None,
    "history":         None,
    "stats":           None,
    "working_memory":  None,
    "debug":           False,
    "call_index":      0,
    "card_text":       "",
    "_sweep_method":   "",
    "_dof":            None,
    "_components":     [],            # valid s.total[...] ids
    "_species":        [],            # valid s.species[...] ids
    "_intensives":     [],            # valid s.<name> intensive handles
    "_catalog_text":   "",           # rendered variable catalog (prompt)
    "_catalog_structured": {},        # metal/ligand declaration groups
}


def configure_l3_2_session(
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
    out = Path(base) / f"L3_2_call_{_SESSION['call_index']:02d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


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
    """Read the L1/L2 system catalog (bare dict or ``{system_catalog: ...}``)."""
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and "system_catalog" in obj:
        sc = obj.get("system_catalog") or {}
    else:
        sc = obj or {}
    if not isinstance(sc, dict):
        raise ValueError(f"L3_2: system_catalog in {path} is not an object")
    _normalize_redox_states(sc)
    return sc


# ════════════════════════════════════════════════════════════════════
#  Non-residual settings sidecar vocabularies
# ════════════════════════════════════════════════════════════════════
#  L3_2 decides the system's modelling regime (the non-residual context
#  the constraint algebra does not capture) alongside the initial
#  conditions, so the constraint designer (L3_3) INHERITS these instead of
#  re-deriving them -- and is never forced down a default (e.g. fixed
#  ionic-strength) pathway.  These closed enums are validated on commit.

_SETTINGS_ENUMS: Dict[str, set] = {
    "activity_model":      {"ideal", "davies"},
    "solids":              {"include", "exclude"},
    "redox_mode":          {"axis", "fixed", "freeform", "solve", "excluded"},
    "ionic_strength_mode": {"fixed", "auto", "none"},
}


# ════════════════════════════════════════════════════════════════════
#  Tool surface
# ════════════════════════════════════════════════════════════════════

_FINAL_SLOT: Dict[str, Any] = {"pins": None, "source": None, "notes": "",
                               "settings": None, "deferred": None,
                               "skill_record": None, "error": None,
                               "latest_attempt": None,
                               "restart_request": None}

NOT_DEFINED = "Not defined"


def _required_declaration_issues(
    pins: List[Any],
    settings: Dict[str, Any],
    deferred: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """Check each input is fixed now or explicitly deferred to L3_3."""
    issues: List[str] = []
    by_ref: Dict[str, List[Any]] = {}
    for pin in pins:
        by_ref.setdefault(pin.ref, []).append(pin)
    deferred_by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for item in deferred or []:
        deferred_by_ref.setdefault(str(item["ref"]), []).append(item)

    if not by_ref.get("temperature") and not deferred_by_ref.get("temperature"):
        issues.append(
            f"temperature is {NOT_DEFINED!r}; pin it or explicitly defer it "
            "as a swept/derived L3_3 handle")

    ionic_pins = by_ref.get("ionic_strength", [])
    ionic_mode = settings["ionic_strength_mode"]
    if ionic_mode == "fixed" and not ionic_pins:
        issues.append(
            f"fixed ionic strength is {NOT_DEFINED!r}; add an explicit pin")
    if ionic_mode in {"auto", "none"} and ionic_pins:
        issues.append(
            f"ionic_strength_mode={ionic_mode!r} must not also pin a fixed value")
    if deferred_by_ref.get("ionic_strength"):
        issues.append(
            "ionic strength cannot be deferred with the currently supported "
            "fixed|auto|none modes")

    e_pins = by_ref.get("E_V", [])
    redox_mode = settings["redox_mode"]
    if redox_mode == "fixed" and not e_pins:
        issues.append(
            f"redox_mode='fixed' requires an explicit E_V pin; it is {NOT_DEFINED!r}")
    if redox_mode in {"axis", "freeform", "solve", "excluded"} and e_pins:
        issues.append(
            f"redox_mode={redox_mode!r} must not pin E_V in initial conditions; "
            "the potential is absent for excluded/solve modes and declared "
            "downstream for axis/freeform modes")

    total_ids = {str(pin.handle_id) for pin in by_ref.get("total", [])
                 if pin.handle_id}
    total_ids.update(
        str(item["handle_id"])
        for item in deferred_by_ref.get("total", [])
        if item.get("handle_id")
    )
    structured = _SESSION.get("_catalog_structured") or {}
    solve_state_targets: List[str] = []
    for metal in structured.get("metals") or []:
        element_aliases = {
            str(value) for value in (metal.get("element"), metal.get("name"))
            if value
        }
        valence_ids = {
            str(v.get("valence")) for v in (metal.get("valences") or [])
            if v.get("valence")
        }
        parent_declarations = element_aliases & total_ids
        state_declarations = valence_ids & total_ids
        label = metal.get("element") or metal.get("name") or "metal"

        if len(parent_declarations) > 1:
            issues.append(
                f"metal {label!r} has duplicate parent-total aliases: "
                f"{sorted(parent_declarations)}")
            continue

        # A one-valence metal has one analytical component.  Its parent and
        # state names are aliases for that one declaration, not two DOFs.
        if len(valence_ids) <= 1:
            declarations = parent_declarations | state_declarations
            if not declarations:
                issues.append(
                    f"metal total for {label!r} is {NOT_DEFINED!r}; declare "
                    "one parent-element or redox-state alias")
            elif len(declarations) > 1:
                issues.append(
                    f"single-state metal {label!r} has duplicate total "
                    f"declarations: {sorted(declarations)}")
            continue

        if redox_mode == "excluded":
            rank = len(parent_declarations) + len(state_declarations)
            if rank < len(valence_ids):
                issues.append(
                    f"redox-excluded metal {label!r} is rank-deficient: "
                    f"declare every redox-state subtotal, or one parent total "
                    f"plus {len(valence_ids) - 1} state subtotals")
            elif rank > len(valence_ids):
                issues.append(
                    f"redox-excluded metal {label!r} is over-determined: do "
                    "not declare the parent total together with every state "
                    "subtotal")
            continue

        if not parent_declarations:
            issues.append(
                f"redox-enabled metal total for {label!r} is {NOT_DEFINED!r}; "
                "declare one parent-element total")
        if redox_mode == "solve":
            if len(state_declarations) > 1:
                issues.append(
                    f"redox_mode='solve' permits at most one state-subtotal "
                    f"target per metal; {label!r} has "
                    f"{sorted(state_declarations)}")
            solve_state_targets.extend(sorted(state_declarations))
        elif state_declarations:
            issues.append(
                f"redox-state subtotal(s) {sorted(state_declarations)} "
                f"over-constrain {label!r} when E_V is externally declared; "
                "remove them or use redox_mode='solve'")

    if redox_mode == "solve" and len(solve_state_targets) != 1:
        issues.append(
            "redox_mode='solve' requires exactly one global redox-state "
            "subtotal target for the one shared E_V degree of freedom; "
            f"got {len(solve_state_targets)}")
    for ligand in structured.get("ligands") or []:
        aliases = {
            str(value) for value in (ligand.get("db_id"), ligand.get("internal_id"))
            if value
        }
        if not (aliases & total_ids):
            label = ligand.get("name") or ligand.get("db_id") or "ligand"
            issues.append(
                f"ligand total for {label!r} is {NOT_DEFINED!r}; declare one "
                f"of {sorted(aliases)}")
    return issues


def _strip_fence(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:python|py)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


_DEFERRED_ROLES = {"swept", "derived"}


def _parse_deferred_conditions(
    raw: str,
    pins: List[Any],
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Validate explicit handles that L3_3 must close instead of L3_2 pinning."""
    if not (raw or "").strip():
        return [], []
    try:
        payload = json.loads(raw)
    except Exception as exc:
        return [], [f"deferred_json is not valid JSON: {exc}"]
    if not isinstance(payload, list):
        return [], ["deferred_json must be a JSON list"]

    components = {str(value) for value in (_SESSION.get("_components") or [])}
    intensives = {
        str(value) for value in
        (_SESSION.get("_intensives") or ("temperature", "ionic_strength", "pH", "E_V"))
    }
    pinned = {pin.handle for pin in pins}
    seen: set[str] = set()
    parsed: List[Dict[str, Any]] = []
    issues: List[str] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            issues.append(f"deferred entry #{idx} must be an object")
            continue
        handle = str(item.get("handle") or "").strip()
        role = str(item.get("role") or "").strip().lower()
        note = str(item.get("note") or "").strip()
        ref: Optional[str] = None
        handle_id: Optional[str] = None
        intensive_match = re.fullmatch(r"s\.([A-Za-z_][A-Za-z0-9_]*)", handle)
        total_match = re.fullmatch(
            r'''s\.total\[(?:"([^"]+)"|'([^']+)')\]''', handle)
        if intensive_match:
            ref = intensive_match.group(1)
            if ref not in intensives:
                issues.append(
                    f"deferred entry #{idx} uses unknown intensive {handle!r}")
                continue
            canonical = f"s.{ref}"
        elif total_match:
            ref = "total"
            handle_id = total_match.group(1) or total_match.group(2)
            if handle_id not in components:
                issues.append(
                    f"deferred entry #{idx} uses unknown total id {handle_id!r}")
                continue
            canonical = f's.total["{handle_id}"]'
        else:
            issues.append(
                f"deferred entry #{idx} handle must be a catalog intensive or "
                f"component total, got {handle!r}")
            continue
        if role not in _DEFERRED_ROLES:
            issues.append(
                f"deferred entry #{idx} role must be one of "
                f"{sorted(_DEFERRED_ROLES)}, got {role!r}")
        if not note:
            issues.append(
                f"deferred entry #{idx} requires a note explaining its L3_3 closure")
        if canonical in pinned:
            issues.append(f"{canonical} cannot be both pinned and deferred")
        if canonical in seen:
            issues.append(f"duplicate deferred handle {canonical}")
        seen.add(canonical)
        parsed.append({
            "handle": canonical,
            "ref": ref,
            "handle_id": handle_id,
            "role": role,
            "note": note,
        })
    return parsed, issues


def _render_deferred_brief(deferred: List[Dict[str, Any]]) -> str:
    if not deferred:
        return ""
    lines = [
        "# Explicitly deferred to L3_3 (must be closed there)",
        "deferred = [",
    ]
    for item in deferred:
        lines.append(
            "  " + repr({key: item[key] for key in ("handle", "role", "note")}) + ",")
    lines.append("]")
    return "\n".join(lines)


def _inspect_card_section(section: str = "") -> str:
    key = (section or "").strip()
    if key not in _SECTION_HEADERS:
        return (f"ERROR: section={key!r} not allowed. "
                f"Valid: {sorted(_SECTION_HEADERS)}")
    text = _SESSION.get("card_text") or ""
    if not text:
        return "_(no card text bound to this session)_"
    return _slice_section(text, _SECTION_HEADERS[key])


def _commit_initial_conditions(
    card_source: str = "",
    notes: str = "",
    activity_model: str = NOT_DEFINED,
    solids: str = NOT_DEFINED,
    redox_mode: str = NOT_DEFINED,
    ionic_strength_mode: str = NOT_DEFINED,
    freeform_vars_json: str = "",
    deferred_json: str = "",
    sweep_skill_id: str = "",
) -> str:
    """Validate + accept the FINAL initial-condition card AND settings.

    ``card_source`` is the Python card module string with a single
    top-level ``inits`` list, written in lambda surface syntax against the
    variable-catalog handles (``s.temperature``, ``s.total["<id>"]`` ...).
    It is parsed with ``ast`` and NEVER executed.  Each entry is a
    constant assignment tagged ``known`` or ``assumed``.

    The remaining args are the non-residual *settings* sidecar -- the
    modelling regime the constraint designer (L3_3) inherits:

    | argument               | allowed values                          |
    |------------------------|-----------------------------------------|
    | ``activity_model``     | ``ideal`` / ``davies``                    |
    | ``solids``             | ``include`` / ``exclude``               |
    | ``redox_mode``         | ``axis`` / ``fixed`` / ``freeform`` / ``solve`` / ``excluded`` |
    | ``ionic_strength_mode``| ``fixed`` / ``auto`` / ``none`` |
    | ``freeform_vars_json`` | optional JSON dict of named scalar constants |
    | ``deferred_json``      | optional list of catalog handles L3_3 must sweep or derive |
    | ``sweep_skill_id``     | optional backward-compatible skill id; normally leave empty |

    Calling this successfully ends the run.
    """
    if _FINAL_SLOT.get("restart_request") is not None:
        return (
            "RESTART_LOCKED: an LC3 restart is already requested. Do not "
            "call `commit_initial_conditions` again; end this stage now."
        )
    _FINAL_SLOT["latest_attempt"] = {
        "tool": "commit_initial_conditions",
        "arguments": {
            "card_source": card_source,
            "notes": notes,
            "activity_model": activity_model,
            "solids": solids,
            "redox_mode": redox_mode,
            "ionic_strength_mode": ionic_strength_mode,
            "freeform_vars_json": freeform_vars_json,
            "deferred_json": deferred_json,
            "sweep_skill_id": sweep_skill_id,
        },
    }
    gallery_note = None
    if str(_SESSION.get("_sweep_method") or "") == "freeform_sweep":
        gallery_note = get_freeform_gallery_note("initial_conditions")
    _FINAL_SLOT["gallery_note"] = gallery_note
    _FINAL_SLOT["latest_attempt"]["freeform_gallery_note"] = gallery_note
    src = _strip_fence(card_source)
    if not src:
        _FINAL_SLOT["error"] = "empty_card"
        return "ERROR: empty `card_source` -- provide the `inits` card."

    # Validate the settings sidecar enums and the persistent artifact family
    # first (cheap, located feedback).
    issues: List[str] = []
    for key, val in (("activity_model", activity_model),
                     ("solids", solids),
                     ("redox_mode", redox_mode),
                     ("ionic_strength_mode", ionic_strength_mode)):
        if val not in _SETTINGS_ENUMS[key]:
            if val == NOT_DEFINED:
                issues.append(f"{key} is {NOT_DEFINED!r}; declare it explicitly")
            else:
                issues.append(f"{key}={val!r} not in {sorted(_SETTINGS_ENUMS[key])}")
    try:
        selected_skill = skill_selection_record(
            str(_SESSION.get("_sweep_method") or ""), sweep_skill_id)
        if selected_skill["primary_skill"] is None:
            issues.append(
                "the selected sweep method has no routable design skill"
            )
    except ValueError as exc:
        selected_skill = None
        issues.append(str(exc))
    freeform_vars: Dict[str, Any] = {}
    if freeform_vars_json.strip():
        try:
            fv = json.loads(freeform_vars_json)
            if not isinstance(fv, dict):
                raise ValueError("freeform_vars must be a JSON object")
            freeform_vars = {str(k): float(v) for k, v in fv.items()}
        except Exception as exc:
            issues.append(f"freeform_vars_json invalid: {exc!r}")
    if issues:
        _FINAL_SLOT["error"] = "; ".join(issues)
        return ("ERROR: " + "; ".join(issues)
                + ". Re-call `commit_initial_conditions`.")

    components = _SESSION.get("_components", [])
    species    = _SESSION.get("_species", [])
    intensives = _SESSION.get("_intensives", []) or None

    try:
        result = compile_initcond_card(
            src, components=components, species=species, intensives=intensives,
            source_name="l3_2_initial_condition_card.py",
        )
    except InitCondCompileError as exc:
        lines = exc.format_lines()
        _FINAL_SLOT["error"] = "compile_error:" + "; ".join(lines)
        return ("ERROR: the initial-condition card did not validate:\n  "
                + "\n  ".join(lines)
                 + "\nFix the card and re-call `commit_initial_conditions`.")

    deferred, deferred_issues = _parse_deferred_conditions(
        deferred_json, result.pins)
    if deferred_issues:
        _FINAL_SLOT["error"] = "deferred_invalid:" + "; ".join(deferred_issues)
        return (
            "ERROR: deferred L3_3 declarations did not validate:\n  "
            + "\n  ".join(deferred_issues)
            + "\nFix deferred_json and re-call `commit_initial_conditions`.")

    settings: Dict[str, Any] = {
        "activity_model":      activity_model,
        "solids":              solids,
        "redox_mode":          redox_mode,
        "ionic_strength_mode": ionic_strength_mode,
    }
    if freeform_vars:
        settings["freeform_vars"] = freeform_vars

    declaration_issues = _required_declaration_issues(
        result.pins, settings, deferred)
    if declaration_issues:
        _FINAL_SLOT["error"] = "undeclared_inputs:" + "; ".join(declaration_issues)
        return (
            "ERROR: undeclared physical/model inputs are forbidden:\n  "
            + "\n  ".join(declaration_issues)
            + "\nDeclare them and re-call `commit_initial_conditions`.")

    _FINAL_SLOT["pins"]     = result.pins
    _FINAL_SLOT["source"]   = result.source
    _FINAL_SLOT["notes"]    = (notes or "").strip()
    _FINAL_SLOT["settings"] = settings
    _FINAL_SLOT["deferred"] = deferred
    _FINAL_SLOT["skill_record"] = selected_skill
    _FINAL_SLOT["gallery_note"] = gallery_note
    _FINAL_SLOT["error"]    = None
    _FINAL_SLOT["restart_request"] = None
    n_known = len(result.known)
    n_assumed = len(result.assumed)
    return (f"OK -- initial conditions accepted: {len(result.pins)} pin(s), "
            f"{len(deferred)} explicitly deferred handle(s) "
            f"({n_known} known, {n_assumed} assumed); "
            f"ionic_strength_mode={ionic_strength_mode}, "
            f"redox_mode={redox_mode}, "
            f"sweep_skill={selected_skill['primary_skill']}.")


def _request_lc3_restart(reason: str = "") -> str:
    """Request a fresh LC3 attempt after a deterministic commit error."""
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
            "`commit_initial_conditions` has returned an error in this run."
        )
    if latest_attempt is None:
        return (
            "ERROR: no directly emitted `commit_initial_conditions` attempt "
            "is available to attach to the restart request."
        )
    if not why:
        return "ERROR: `reason` must explain why local correction is insufficient."
    if str(_SESSION.get("_sweep_method") or "") == "freeform_sweep":
        gallery_note = get_freeform_gallery_note("initial_conditions")
        _FINAL_SLOT["gallery_note"] = gallery_note
        latest_attempt["freeform_gallery_note"] = gallery_note
    _FINAL_SLOT["restart_request"] = {
        "requested_by": "LC3_2",
        "error": str(error),
        "reason": why,
    }
    return (
        "OK_RESTART_REQUESTED: end this stage now. The orchestrator will "
        "start LC3 again with this exact error and the latest attempted "
        "initial-condition artifact as recovery context."
    )


def _build_agent_tools() -> Dict[str, Callable]:
    """Build the L3_2 commit/inspection surface plus optional skill reads."""
    tools: Dict[str, Callable] = {
        "inspect_card_section":       _inspect_card_section,
        "commit_initial_conditions":  _commit_initial_conditions,
        "request_lc3_restart":        _request_lc3_restart,
    }
    tools.update(get_sweep_skill_tools())
    return tools


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
        "Generate a fresh initial-condition artifact. Use the prior direct "
        "artifact and exact error diagnostically; retain unaffected user "
        "requirements."
    )


def _build_user_message(purpose: str, tasks: str, sweep_method: str,
                        dof: Any, catalog_text: str, snapshot: str,
                        restart_context: Any = None) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n"
        f"[sweep_method (chosen by L3_1): {sweep_method}]\n"
        f"[dof (number of sweep axes chosen by L3_1): {dof}]\n\n"
        f"{catalog_text}\n\n"
        f"[Card section 2 snapshot -- components / metals / ligands]\n"
        f"{snapshot}\n\n"
        f"Explicitly declare every physical/model input. List what is KNOWN "
        f"or, when the task is silent, make and document an ASSUMPTION about "
        f"the starting "
        f"state as an `inits` card using ONLY the handles above, then commit "
        f"it with `commit_initial_conditions`.  Do NOT pin a value that the "
        f"sweep will scan or L3_3 will derive; list each such catalog handle "
        f"in `deferred_json` with role `swept` or `derived` and a rationale. "
        f"A deferred handle remains mandatory and must be closed by L3_3. On the same "
        f"commit, choose the modelling-regime settings -- `activity_model`, "
        f"`solids`, `redox_mode`, `ionic_strength_mode` -- so the constraint "
        f"designer inherits them. Omitting a total, temperature, or modelling "
        f"mode is rejected as `Not defined` (e.g. set "
        f"`ionic_strength_mode=auto` to let "
        f"the solver compute I self-consistently instead of pinning it). "
        f"For `freeform_sweep`, use the loaded standalone freeform skill. "
        f"You may list and read relevant stage-gallery examples before "
        f"committing. Recommending one inspected example as the best "
        f"structural analogue is optional; `best_example` may remain null. "
        f"All inspected examples and any optional recommendation are passed "
        f"to L3_3 as an advisory note."
        f"{_render_restart_context(restart_context)}"
    )


def run_l3_2(
    *,
    purpose: str,
    tasks: str,
    calc_input_card_path: str | Path,
    system_catalog_path: str | Path,
    fixed_card_path: str | Path,
    output_dir: str | Path,
    restart_context: Any = None,
) -> Dict[str, Any]:
    """Run the L3_2 initial-condition designer.

    Parameters
    ----------
    calc_input_card_path
        The single evolving ``calc_input_card.json`` seeded by L3_1
        (carries ``sweep_method`` and ``_meta.dof`` -- context so the
        agent does not pin a swept variable).  L3_2 appends the
        ``system_catalog`` + ``constraint_settings`` it authors and
        rewrites the same card.
    system_catalog_path
        The L1/L2 system-catalog file; bare dict or ``{system_catalog: ...}``.
    fixed_card_path
        The final L2 free-energy markdown card; resolved to a
        ``FreeEnergyReport`` to build the authoritative variable catalog.

    Returns
    -------
    dict
        ``status``, ``output_dir``, ``calc_input_card_path``,
        ``initial_condition_card_path``, ``initial_conditions_brief_path``,
        ``initial_conditions_text``, ``inits``, ``n_known``, ``n_assumed``,
        ``elapsed_s``, ``report``.
    """
    purpose, tasks_text = _require_purpose_tasks(purpose, tasks)

    if _SESSION["session_dir"] is None:
        configure_l3_2_session(session_dir=Path.cwd() / "_l3_2_adhoc_session")

    call_dir = _per_call_dir()
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)

    calc_input_card_path = Path(calc_input_card_path)
    system_catalog_path = Path(system_catalog_path)
    fixed_card_path = Path(fixed_card_path)
    if not calc_input_card_path.exists():
        raise FileNotFoundError(
            f"L3_2: calc-input card not found: {calc_input_card_path}")
    if not system_catalog_path.exists():
        raise FileNotFoundError(
            f"L3_2: system catalog not found: {system_catalog_path}")
    if not fixed_card_path.exists():
        raise FileNotFoundError(
            f"L3_2: fixed card not found: {fixed_card_path}")

    card = json.loads(calc_input_card_path.read_text(encoding="utf-8"))
    sweep_method = card.get("sweep_method")
    dof = (card.get("_meta") or {}).get("dof")

    system_catalog = _load_system_catalog(system_catalog_path)
    card_text = fixed_card_path.read_text(encoding="utf-8")

    # Authoritative FreeEnergyReport -> variable catalog (same handles the
    # constraint designer sees).
    report = resolve_card_source(fixed_card_path)
    # Prune phantom catalog entries (e.g. an LC1-enumerated ``Cu$+3`` the
    # card never realises) so the catalog stays a strict subset of the
    # card.  Mutates ``system_catalog`` in place before it is folded into
    # the calc-input card below.
    _prune_notes = prune_system_catalog_to_report(system_catalog, report)
    if _prune_notes:
        print("[L3_2] system_catalog reconciled with card: "
              + "; ".join(_prune_notes))
    var_catalog = build_variable_catalog(report, system_catalog or None)

    _SESSION["card_text"]      = card_text
    _SESSION["_sweep_method"]  = sweep_method
    _SESSION["_dof"]           = dof
    _SESSION["_components"]    = var_catalog.components
    _SESSION["_species"]       = var_catalog.species
    _SESSION["_intensives"]    = var_catalog.intensives
    _SESSION["_catalog_text"]  = var_catalog.text
    _SESSION["_catalog_structured"] = var_catalog.structured

    history = _SESSION["history"]; stats = _SESSION["stats"]
    if history is not None:
        history.log("L3_2_dispatch_start",
                    call_index=_SESSION["call_index"],
                    sweep_method=sweep_method, dof=dof,
                    n_components=len(var_catalog.components))

    _FINAL_SLOT["pins"]     = None
    _FINAL_SLOT["source"]   = None
    _FINAL_SLOT["notes"]    = ""
    _FINAL_SLOT["settings"] = None
    _FINAL_SLOT["deferred"] = None
    _FINAL_SLOT["skill_record"] = None
    _FINAL_SLOT["gallery_note"] = None
    _FINAL_SLOT["error"]    = None
    _FINAL_SLOT["latest_attempt"] = None
    _FINAL_SLOT["restart_request"] = None

    workflow = parse_workflow(_WORKFLOW_PATH)
    system_prompt = workflow["system_prompt"]
    skill_record = skill_selection_record(sweep_method)
    system_prompt += "\n\n" + build_sweep_skill_context(
        sweep_method, "initial_conditions", debug=_SESSION["debug"])
    tools = _build_agent_tools()
    system_prompt += "\n\n" + build_tool_instructions(tools)

    snapshot = _build_card_snapshot(card_text)
    user_message = _build_user_message(purpose, tasks_text, sweep_method, dof,
                                       var_catalog.text, snapshot,
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
            required_tools={"commit_initial_conditions"},
            hooks=_engine_agent_hooks.engine_hooks,
            is_subagent=True,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        log.error("L3_2 agent_turn raised: %s", exc, exc_info=_SESSION["debug"])
        return {
            "status":                        "failed",
            "_error":                        f"agent_turn_exception: {exc!r}",
            "restart_request":               None,
            "latest_attempt_artifact_path":  None,
            "output_dir":                    str(call_dir),
            "initial_condition_card_path":   None,
            "initial_conditions_brief_path": None,
            "initial_conditions_text":       "",
            "inits":                         [],
            "n_known":                       0,
            "n_assumed":                     0,
            "elapsed_s":                     round(elapsed, 3),
            "report":                        f"agent_turn_exception: {exc!r}",
        }

    elapsed = time.time() - t0
    pins     = _FINAL_SLOT["pins"]
    source   = _FINAL_SLOT["source"]
    notes    = _FINAL_SLOT["notes"]
    settings = _FINAL_SLOT["settings"]
    deferred = _FINAL_SLOT["deferred"]
    committed_skill_record = _FINAL_SLOT["skill_record"]
    gallery_note = _FINAL_SLOT["gallery_note"]
    error    = _FINAL_SLOT["error"]
    latest_attempt = _FINAL_SLOT["latest_attempt"]
    restart_request = _FINAL_SLOT["restart_request"]
    if committed_skill_record is not None:
        skill_record = committed_skill_record

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

    card_path: Optional[Path] = None
    brief_path: Optional[Path] = None
    settings_path: Optional[Path] = None
    calc_card_out_path: Optional[Path] = None
    brief_text = ""
    structured: List[Dict[str, Any]] = []
    n_known = n_assumed = 0

    if pins is not None:
        from ._initcond_helpers.initcond_card import InitCondResult
        res = InitCondResult(pins=pins, source=source or "")
        brief_text = render_initcond_brief(res)
        deferred_text = _render_deferred_brief(deferred or [])
        if deferred_text:
            brief_text = brief_text.rstrip() + "\n\n" + deferred_text + "\n"
        structured = [
            {"id": p.id, "handle": p.handle, "ref": p.ref,
             "handle_id": p.handle_id, "value": p.value, "basis": p.basis,
             "note": p.note}
            for p in pins
        ]
        n_known = len(res.known)
        n_assumed = len(res.assumed)

        card_path = call_dir / "initial_condition_card.py"
        card_path.write_text(source or "", encoding="utf-8")
        brief_path = call_dir / "initial_conditions_brief.md"
        brief_path.write_text(brief_text, encoding="utf-8")
        (call_dir / "initial_conditions.json").write_text(
            json.dumps({"inits": structured, "deferred": deferred or [],
                        "notes": notes,
                        "freeform_gallery_note": gallery_note,
                        "n_known": n_known, "n_assumed": n_assumed},
                       indent=2),
            encoding="utf-8",
        )
        # Extend the single evolving calc-input card: attach the system
        # catalog and the non-residual modelling settings this stage
        # authors (inherited verbatim by L3_3 + folded into the final
        # card). The initial-condition pins ride along under a debug-only
        # ``_initial_conditions`` key (the loader ignores ``_``-prefixed
        # keys), so the settings are never written to a separate file.
        card["system_catalog"] = system_catalog
        if settings is not None:
            card["constraint_settings"] = settings
        card["_initial_conditions"] = {
            "inits": structured, "deferred": deferred or [], "notes": notes,
            "n_known": n_known, "n_assumed": n_assumed,
        }
        card["_deferred_conditions"] = deferred or []
        card.setdefault("_meta", {})["stage"] = "LC3_2"
        card["_meta"]["sweep_skill_selection"] = skill_record
        if gallery_note is not None:
            card = append_freeform_gallery_note(card, gallery_note)
        calc_card_out_path = call_dir / "calc_input_card.json"
        calc_card_out_path.write_text(json.dumps(card, indent=2),
                                      encoding="utf-8")
        # The settings now live inside the evolving card (no duplicate
        # sidecar); expose the card path for traceability.
        if settings is not None:
            settings_path = calc_card_out_path

    # Persist artefacts.
    (call_dir / "input.json").write_text(json.dumps({
        "purpose": purpose, "tasks": tasks_text,
        "calc_input_card_path": str(calc_input_card_path),
        "system_catalog_path": str(system_catalog_path),
        "fixed_card_path": str(fixed_card_path),
        "sweep_method": sweep_method, "dof": dof,
        "sweep_skill_selection": skill_record,
        "freeform_gallery_note": gallery_note,
        "n_components": len(_SESSION.get("_components", [])),
        "n_species": len(_SESSION.get("_species", [])),
        "restart_context": restart_context,
    }, indent=2, default=str), encoding="utf-8")
    (call_dir / "variable_catalog.txt").write_text(
        _SESSION.get("_catalog_text", ""), encoding="utf-8")

    rows = [
        "# L3_2 Tool Calls",
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
    (call_dir / "l3_2_tool_calls.md").write_text("\n".join(rows) + "\n",
                                                 encoding="utf-8")

    # Raw text the agent emitted (final answer + last context), for debugging.
    (call_dir / "agent_response.md").write_text(
        "# L3_2 agent response\n\n"
        "## Final answer (text emitted by the agent)\n\n"
        f"{result.answer or '_(empty)_'}\n\n"
        "## Final context\n\n"
        f"{result.final_context or '_(empty)_'}\n",
        encoding="utf-8",
    )

    report_lines = [
        f"# L3_2 initial-condition report (call {_SESSION['call_index']:02d})",
        "",
        f"- output_dir: `{call_dir}`",
        f"- elapsed_s: {elapsed:.2f}",
        f"- llm_iterations: {result.iterations}",
        f"- llm_tool_calls: {len(result.tool_history)}",
        f"- sweep_method (from L3_1): **{sweep_method}**",
        f"- dof (from L3_1): {dof}",
        "",
    ]
    if pins is None:
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
        report_lines.append(
            f"## Initial conditions: {len(pins)} pin(s) "
            f"({n_known} known, {n_assumed} assumed), "
            f"{len(deferred or [])} deferred handle(s)")
        report_lines.append("```python")
        report_lines.append(brief_text)
        report_lines.append("```")
        if notes:
            report_lines.append("")
            report_lines.append("## Notes")
            report_lines.append(notes)
        if settings is not None:
            report_lines.append("")
            report_lines.append("## Settings (inherited by L3_3)")
            report_lines.append("```json")
            report_lines.append(json.dumps(settings, indent=2))
            report_lines.append("```")
        if gallery_note is not None:
            report_lines.extend([
                "",
                "## Freeform gallery note (passed to L3_3)",
                "```json",
                json.dumps(gallery_note, indent=2),
                "```",
            ])
    report = "\n".join(report_lines)
    (call_dir / "report.md").write_text(report, encoding="utf-8")

    if stats is not None:
        stats.incr("L3_2", "dispatch_calls", 1)
        stats.incr("L3_2", "llm_iterations", result.iterations)
        stats.incr("L3_2", "tool_calls",     len(result.tool_history))
        stats.incr("L3_2", "ok" if pins is not None else "failed", 1)

    if _SESSION["working_memory"] is not None and card_path is not None:
        try:
            _SESSION["working_memory"].set("initial_conditions_text", brief_text)
            _SESSION["working_memory"].set("initial_condition_card_path",
                                           str(card_path))
            if settings is not None:
                _SESSION["working_memory"].set("constraint_settings", settings)
        except Exception as exc:                   # pragma: no cover
            log.warning("working_memory.set failed: %s", exc)

    if history is not None:
        history.log("L3_2_dispatch_end",
                    call_index=_SESSION["call_index"],
                    elapsed_s=elapsed,
                    n_pins=len(pins or []),
                    n_deferred=len(deferred or []),
                    n_known=n_known, n_assumed=n_assumed)

    status = ("ok" if pins is not None else
              "restart_requested" if restart_request is not None else
              "failed")
    return {
        "status":                        status,
        "_error":                        None if pins is not None else (
            error or "no_payload"),
        "restart_request":               restart_request,
        "latest_attempt_artifact_path":  (
            str(latest_attempt_path) if latest_attempt_path else None),
        "output_dir":                    str(call_dir),
        "calc_input_card_path":          str(calc_card_out_path) if calc_card_out_path else None,
        "initial_condition_card_path":   str(card_path) if card_path else None,
        "initial_conditions_brief_path": str(brief_path) if brief_path else None,
        "initial_conditions_text":       brief_text,
        "inits":                         structured,
        "deferred_conditions":           deferred or [],
        "constraint_settings":           settings,
        "sweep_skill_selection":          skill_record,
        "freeform_gallery_note":          gallery_note,
        "constraint_settings_path":      str(settings_path) if settings_path else None,
        "n_known":                       n_known,
        "n_assumed":                     n_assumed,
        "elapsed_s":                     round(elapsed, 3),
        "report":                        report,
    }
