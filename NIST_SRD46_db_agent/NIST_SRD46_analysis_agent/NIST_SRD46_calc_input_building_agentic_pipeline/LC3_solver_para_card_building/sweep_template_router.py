"""Route stage-local sweep skills and trace freeform-example inspection.

Templates live with the agent that consumes them: L3_2 initial conditions,
L3_3 constraints, and L3_4 sweep design.  The selected method gets only its
current-stage template.  Freeform is a standalone method family; each stage
also owns a small example gallery whose reads and optional recommendation are
recorded for explicit hand-off to the next stage. A canonical registry hides
misaligned or solve-invalid entries from every agent-facing gallery tool.
"""

from __future__ import annotations

from copy import deepcopy
from contextvars import ContextVar
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from .freeform_gallery_registry import (
    audit_freeform_gallery,
    read_text as _registry_read_text,
    visible_freeform_gallery_index,
)


_ROOT = Path(__file__).absolute().parent
_VALID_STAGES = {
    "initial_conditions": (
        "LC3_2_initial_condition_designer", "_standard_initcond_templates"),
    "constraints": (
        "LC3_3_constraint_designer", "_standard_constr_templates"),
    "sweep_design": (
        "LC3_4_sweep_designer", "_standard_sweep_templates"),
}

# ``build_sweep_skill_context`` and ``get_sweep_skill_tools`` are called
# consecutively by each L3 dispatcher.  Keep the caller's stage in a
# context-local slot so the model-facing alternative-family reader cannot
# request another L3 stage, without coupling this router back into the agent
# modules.  The unbound ``read_sweep_design_skill`` remains available for
# internal context assembly and focused tests.
_ACTIVE_TOOL_STAGE: ContextVar[Optional[str]] = ContextVar(
    "lc3_sweep_skill_tool_stage", default=None)
_ACTIVE_SWEEP_METHOD: ContextVar[Optional[str]] = ContextVar(
    "lc3_sweep_skill_method", default=None)
_ACTIVE_GALLERY_DEBUG: ContextVar[bool] = ContextVar(
    "lc3_freeform_gallery_debug", default=False)

# Each LC3 stage has an independent trace.  A copy-on-write mapping avoids
# leaking mutable state between concurrently executing ContextVar contexts.
_GALLERY_STATES: ContextVar[Optional[Dict[str, Dict[str, Any]]]] = ContextVar(
    "lc3_freeform_gallery_states", default=None)
_FREEFORM_SKILL_ID = "freeform-sweep-design"
_MAX_GALLERY_READ_CHARS = 12_000
_EXAMPLE_ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_GALLERY_LOG = logging.getLogger("Analysis.FreeformGallery")


@dataclass(frozen=True)
class _SkillRecord:
    skill_id: str
    folder_name: str
    description: str
    standard_methods: Tuple[str, ...]
    compatible_methods: Tuple[str, ...]

    def template_path(self, stage: str) -> Path:
        agent_folder, template_folder = _VALID_STAGES[stage]
        return (_ROOT / agent_folder / template_folder / self.folder_name
                / "SKILL.md")


_SKILLS: Tuple[_SkillRecord, ...] = (
    _SkillRecord(
        skill_id="speciation-path-design",
        folder_name="speciation",
        description=(
            "Use the standard pH-speciation or titration path contract."
        ),
        standard_methods=("pH_sweep", "titration_sweep"),
        compatible_methods=(),
    ),
    _SkillRecord(
        skill_id="predominance-map-design",
        folder_name="predominance",
        description=(
            "Use the standard two-coordinate Eh-pH Pourbaix contract."
        ),
        standard_methods=("pourbaix_sweep",),
        compatible_methods=(),
    ),
    _SkillRecord(
        skill_id=_FREEFORM_SKILL_ID,
        folder_name="freeform",
        description=(
            "Use an explicitly designed freeform path or field whose state "
            "relations do not fit a standard sweep contract."
        ),
        standard_methods=("freeform_sweep",),
        compatible_methods=(),
    ),
)
_BY_ID = {record.skill_id: record for record in _SKILLS}


def _frontmatter_values(
    path: Path,
    required: Sequence[str],
) -> Dict[str, str]:
    text = _registry_read_text(path)
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise ValueError(f"Markdown file has no YAML frontmatter: {path}")
    values: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    for key in required:
        if not values.get(key):
            raise ValueError(f"Markdown frontmatter lacks {key!r}: {path}")
    return values


def _frontmatter(path: Path) -> Dict[str, str]:
    return _frontmatter_values(path, ("name", "description"))


def _body(path: Path) -> str:
    text = _registry_read_text(path)
    match = re.match(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", text, re.DOTALL)
    return text[match.end():].strip() if match else text.strip()


def _overview(record: _SkillRecord) -> str:
    standard = ", ".join(record.standard_methods) or "none"
    compatible = ", ".join(record.compatible_methods) or "none"
    return (
        f"# {record.skill_id}\n\n{record.description}\n\n"
        f"Standard methods: {standard}. Compatible methods: {compatible}."
    )


def _record_header(record: _SkillRecord) -> Dict[str, object]:
    headers = {
        stage: _frontmatter(record.template_path(stage))
        for stage in _VALID_STAGES
    }
    for stage, header in headers.items():
        if header["name"] != record.skill_id:
            raise ValueError(
                f"Sweep skill folder/id mismatch at {stage}: "
                f"{record.skill_id!r} != {header['name']!r}"
            )
    return {
        "skill_id": record.skill_id,
        "description": record.description,
        "standard_methods": list(record.standard_methods),
        "compatible_methods": list(record.compatible_methods),
        "sections": list(_VALID_STAGES),
    }


def primary_skill_id_for_method(
    sweep_method: str,
    declared_skill_id: Optional[str] = None,
) -> Optional[str]:
    """Resolve the immutable standard family or a compatible declared one."""
    method = (sweep_method or "").strip()
    declared = (declared_skill_id or "").strip() or None
    standard: Optional[str] = None
    for record in _SKILLS:
        if method in record.standard_methods:
            standard = record.skill_id
            break

    if standard is not None:
        if declared is not None and declared != standard:
            raise ValueError(
                f"{method!r} is a standard method for {standard!r}; "
                f"it cannot declare {declared!r}"
            )
        return standard

    if declared is None:
        return None
    record = _BY_ID.get(declared)
    if record is None:
        raise ValueError(
            f"Unknown sweep-design skill {declared!r}; available: "
            + ", ".join(_BY_ID)
        )
    if method not in record.compatible_methods:
        raise ValueError(
            f"Sweep-design skill {declared!r} is not compatible with "
            f"method {method!r}"
        )
    return declared


def skill_selection_record(
    sweep_method: str,
    declared_skill_id: Optional[str] = None,
) -> Dict[str, object]:
    """Return a serializable trace of standard or agent-declared selection."""
    declared = (declared_skill_id or "").strip() or None
    primary = primary_skill_id_for_method(sweep_method, declared)
    compatible = [
        record.skill_id for record in _SKILLS
        if sweep_method in record.compatible_methods
    ]
    is_standard = bool(primary) and any(
        record.skill_id == primary and sweep_method in record.standard_methods
        for record in _SKILLS
    )
    if primary is None:
        selection = "intent-required"
    elif is_standard:
        selection = "standard-method"
    else:
        selection = "agent-declared"
    return {
        "sweep_method": sweep_method,
        "primary_skill": primary,
        "selection": selection,
        "compatible_skill_ids": compatible,
        "available_skill_ids": [record.skill_id for record in _SKILLS],
    }


def list_sweep_design_skills() -> str:
    """List sweep-design skill headers and their standard/compatible methods.

    Use this when the selected method's primary guidance does not fully match
    the requested calculation geometry. Headers are returned without loading
    the detailed stage templates.
    """
    return json.dumps([_record_header(record) for record in _SKILLS], indent=2)


def read_sweep_design_skill(skill_id: str = "", section: str = "overview") -> str:
    """Read one sweep-design skill section.

    ``skill_id`` is one returned by ``list_sweep_design_skills``. ``section``
    may be ``overview``, ``initial_conditions``, ``constraints``,
    ``sweep_design``, or ``all``. This unbound function is for internal context
    assembly and tests; model-facing readers are restricted to their caller's
    stage.
    """
    record = _BY_ID.get((skill_id or "").strip())
    if record is None:
        return (
            "ERROR: unknown sweep-design skill. Available: "
            + ", ".join(_BY_ID)
        )
    requested = (section or "overview").strip().lower().replace("-", "_")
    valid = {"overview", "all", *_VALID_STAGES}
    if requested not in valid:
        return "ERROR: section must be one of: " + ", ".join(sorted(valid))

    chunks = []
    if requested in {"overview", "all"}:
        chunks.append(_overview(record))
    stages = tuple(_VALID_STAGES) if requested == "all" else (requested,)
    for stage in stages:
        if stage in _VALID_STAGES:
            chunks.append(_body(record.template_path(stage)))
    return "\n\n".join(chunks)


def _normalize_stage(stage: Optional[str]) -> str:
    stage_key = (
        (stage or "").strip().lower().replace("-", "_")
        if stage is not None else _ACTIVE_TOOL_STAGE.get()
    )
    if stage_key not in _VALID_STAGES:
        if stage is None:
            raise ValueError(
                "no L3 stage is bound; build the stage context first"
            )
        raise ValueError(
            f"Unknown LC3 sweep-skill stage {stage!r}; "
            f"expected {tuple(_VALID_STAGES)}"
        )
    return stage_key


def _empty_gallery_state(stage: str) -> Dict[str, Any]:
    return {
        "stage": stage,
        "inspected_examples": [],
        "best_example": None,
        "best_example_rationale": "",
    }


def _reset_gallery_state(stage: str) -> None:
    states = dict(_GALLERY_STATES.get() or {})
    states[stage] = _empty_gallery_state(stage)
    _GALLERY_STATES.set(states)


def _get_gallery_state(stage: str) -> Dict[str, Any]:
    states = _GALLERY_STATES.get() or {}
    state = states.get(stage)
    if state is None:
        state = _empty_gallery_state(stage)
        updated = dict(states)
        updated[stage] = state
        _GALLERY_STATES.set(updated)
    return state


def _set_gallery_state(stage: str, state: Mapping[str, Any]) -> None:
    states = dict(_GALLERY_STATES.get() or {})
    states[stage] = dict(state)
    _GALLERY_STATES.set(states)


def _gallery_dir(stage: str) -> Path:
    return _BY_ID[_FREEFORM_SKILL_ID].template_path(stage).parent / "gallery"


def _gallery_index(stage: str) -> Dict[str, Tuple[Dict[str, str], Path]]:
    """Return only registry-aligned and solve-approved canonical entries."""
    index, _ = visible_freeform_gallery_index(
        stage,
        root=_ROOT,
        run_solve_checks=_ACTIVE_GALLERY_DEBUG.get(),
    )
    if not index:
        raise ValueError(
            "no validated freeform gallery entries are currently available"
        )
    return index


def _lookup_example(
    stage: str,
    example_id: str,
) -> Tuple[Dict[str, str], Path]:
    requested = (example_id or "").strip()
    if (not _EXAMPLE_ID_RE.fullmatch(requested or "")
            or ".." in requested):
        raise ValueError(
            "unknown freeform example_id; use list_freeform_examples"
        )
    match = _gallery_index(stage).get(requested)
    if match is None:
        raise ValueError(
            f"unknown freeform example_id {requested!r}; use "
            "list_freeform_examples"
        )
    return match


def _bounded_example_text(metadata: Mapping[str, str], path: Path) -> str:
    from .freeform_gallery_validation import gallery_validation_card

    stage_slice = _body(path)
    supporting_card = gallery_validation_card(metadata["example_id"])
    supporting = (
        "\n\n## Supporting reference: complete validated calculation card\n\n"
        "This is a minimal concrete instantiation of the same structural "
        "pattern and is the complete card used by its local registry solve "
        "check. Its values may differ from illustrative values in the slice. "
        "It is supporting context only: emit the current stage's direct tool "
        "arguments, not this entire card."
        "\n\n### Canonical gallery identity\n\n```json\n"
        + json.dumps(dict(metadata), indent=2, ensure_ascii=False)
        + "\n```\n\n### Complete calc-input card\n\n```json\n"
        + json.dumps(supporting_card, indent=2, ensure_ascii=False)
        + "\n```"
    )
    rendered = "[FREEFORM EXAMPLE]\n\n" + stage_slice + supporting
    if len(rendered) <= _MAX_GALLERY_READ_CHARS:
        return rendered
    marker = "\n\n[example text truncated by the bounded gallery reader]"
    return rendered[:_MAX_GALLERY_READ_CHARS - len(marker)] + marker


def list_freeform_examples(stage: Optional[str] = None) -> str:
    """List current-stage freeform examples without marking them inspected."""
    try:
        stage_key = _normalize_stage(stage)
        examples = [metadata for metadata, _ in _gallery_index(stage_key).values()]
    except ValueError as exc:
        return f"ERROR: {exc}"
    return json.dumps(examples, indent=2, ensure_ascii=False)


def read_freeform_example(
    example_id: str = "",
    *,
    stage: Optional[str] = None,
) -> str:
    """Read one current-stage example and record its first inspection order."""
    try:
        stage_key = _normalize_stage(stage)
        metadata, path = _lookup_example(stage_key, example_id)
    except ValueError as exc:
        return f"ERROR: {exc}"

    state = dict(_get_gallery_state(stage_key))
    inspected = [dict(item) for item in state["inspected_examples"]]
    if not any(item["example_id"] == metadata["example_id"]
               for item in inspected):
        inspected.append(dict(metadata))
        state["inspected_examples"] = inspected
        _set_gallery_state(stage_key, state)
    return _bounded_example_text(metadata, path)


def get_freeform_gallery_note(
    stage: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the stage note, with an optional best example ordered first."""
    stage_key = _normalize_stage(stage)
    state = _get_gallery_state(stage_key)
    inspected = [dict(item) for item in state["inspected_examples"]]
    best = state.get("best_example")
    if best:
        inspected.sort(key=lambda item: item["example_id"] != best)
    return {
        "stage": stage_key,
        "best_example": best,
        "best_example_rationale": state.get("best_example_rationale", ""),
        "inspected_examples": inspected,
    }


def append_freeform_gallery_note(
    card: Mapping[str, Any],
    note: Mapping[str, Any],
) -> Dict[str, Any]:
    """Purely append/replace one advisory stage note in a calculation card.

    Notes are stored in stage-arrival order at
    ``_meta.freeform_gallery_notes``. Re-appending the same stage replaces its
    earlier note in place, so retries cannot create duplicate stage records.
    Inspection and recommendation are optional. When a best example is
    nominated, it must be among the inspected examples and is stored first.
    """
    if not isinstance(card, Mapping):
        raise ValueError("card must be a mapping")
    if not isinstance(note, Mapping):
        raise ValueError("freeform gallery note must be a mapping")
    stage = str(note.get("stage") or "").strip()
    if stage not in _VALID_STAGES:
        raise ValueError(f"freeform gallery note has invalid stage {stage!r}")
    best_raw = note.get("best_example")
    best = str(best_raw).strip() if best_raw is not None else None
    if best == "":
        best = None
    rationale = str(note.get("best_example_rationale") or "").strip()
    inspected_raw = note.get("inspected_examples")
    if (not isinstance(inspected_raw, Sequence)
            or isinstance(inspected_raw, (str, bytes))):
        raise ValueError(
            "freeform gallery note inspected_examples must be a sequence"
        )
    inspected = []
    seen = set()
    for item in inspected_raw:
        if not isinstance(item, Mapping):
            raise ValueError("inspected freeform examples must be mappings")
        canonical_item = {
            "example_id": str(item.get("example_id") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
        }
        example_id = canonical_item["example_id"]
        if not example_id:
            raise ValueError("inspected freeform examples require example_id")
        if example_id not in seen:
            inspected.append(canonical_item)
            seen.add(example_id)
    if best is not None:
        if not rationale:
            raise ValueError(
                "a nominated best freeform example requires a rationale")
        if best not in seen:
            raise ValueError(
                "the nominated best freeform example must have been inspected")
        inspected.sort(key=lambda item: item["example_id"] != best)
    else:
        rationale = ""
    canonical = {
        "stage": stage,
        "best_example": best,
        "best_example_rationale": rationale,
        "inspected_examples": inspected,
    }

    updated = deepcopy(dict(card))
    meta_raw = updated.get("_meta")
    meta = deepcopy(dict(meta_raw)) if isinstance(meta_raw, Mapping) else {}
    existing_raw = meta.get("freeform_gallery_notes")
    existing = list(existing_raw) if isinstance(existing_raw, list) else []
    for index, prior in enumerate(existing):
        if isinstance(prior, Mapping) and prior.get("stage") == stage:
            existing[index] = canonical
            break
    else:
        existing.append(canonical)
    meta["freeform_gallery_notes"] = existing
    updated["_meta"] = meta
    return updated


def select_freeform_example(
    example_id: str = "",
    rationale: str = "",
    *,
    stage: Optional[str] = None,
) -> str:
    """Select one already-inspected example as the best current-stage guide."""
    reason = (rationale or "").strip()
    if not reason:
        return "ERROR: rationale must be nonempty"
    try:
        stage_key = _normalize_stage(stage)
        metadata, _ = _lookup_example(stage_key, example_id)
    except ValueError as exc:
        return f"ERROR: {exc}"
    state = dict(_get_gallery_state(stage_key))
    inspected_ids = {
        item["example_id"] for item in state["inspected_examples"]
    }
    if metadata["example_id"] not in inspected_ids:
        return (
            "ERROR: select_freeform_example requires an inspected example; "
            f"read {metadata['example_id']!r} first"
        )
    state["best_example"] = metadata["example_id"]
    state["best_example_rationale"] = reason
    _set_gallery_state(stage_key, state)
    return "OK:\n" + json.dumps(
        get_freeform_gallery_note(stage_key), indent=2, ensure_ascii=False)


def _coerce_prior_gallery_notes(value: Any) -> Sequence[Mapping[str, Any]]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        if "stage" in value:
            return (value,)
        return tuple(
            item for item in value.values() if isinstance(item, Mapping)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    raise ValueError(
        "prior_gallery_notes must be a gallery-note mapping or sequence"
    )


def build_sweep_skill_context(
    sweep_method: str,
    stage: str,
    declared_skill_id: Optional[str] = None,
    prior_gallery_notes: Any = None,
    debug: bool = False,
) -> str:
    """Build the progressively disclosed guidance injected into one LC3 stage."""
    stage_key = _normalize_stage(stage)
    _ACTIVE_TOOL_STAGE.set(stage_key)
    method = (sweep_method or "").strip()
    _ACTIVE_SWEEP_METHOD.set(method)
    _ACTIVE_GALLERY_DEBUG.set(bool(debug))
    _reset_gallery_state(stage_key)
    primary = primary_skill_id_for_method(sweep_method, declared_skill_id)
    headers = list_sweep_design_skills()
    lines = [
        "[SWEEP-DESIGN SKILL ROUTER]",
        f"Selected solver method: {sweep_method}",
    ]
    if primary:
        selection_text = (
            "persisted skill selection" if declared_skill_id
            else "this standard method"
        )
        lines.extend([
            f"Primary skill declared for {selection_text}: {primary}",
            "The primary overview and current-stage template are loaded below.",
            "",
            read_sweep_design_skill(primary, "overview"),
            "",
            read_sweep_design_skill(primary, stage_key),
        ])
    else:
        lines.extend([
            "No primary family is inferred from this method id. Inspect the "
            "available headers and read the relevant current-stage skill; "
            "the reader is already bound to this agent's stage.",
        ])
    prior_notes = _coerce_prior_gallery_notes(prior_gallery_notes)
    if prior_notes:
        lines.extend([
            "",
            "Prior freeform-gallery inspection notes from upstream LC3 stages "
            "(evidence only; do not treat them as solver input):",
            json.dumps(list(prior_notes), indent=2, ensure_ascii=False),
        ])
    if method == "freeform_sweep":
        gallery_report = audit_freeform_gallery(
            root=_ROOT, run_solve_checks=bool(debug))
        if gallery_report["hidden"]:
            hidden_ids = sorted(gallery_report["hidden"])
            if debug:
                _GALLERY_LOG.warning(
                    "Freeform gallery registry quarantined entries:\n%s",
                    json.dumps(gallery_report, indent=2, ensure_ascii=False),
                )
            else:
                _GALLERY_LOG.debug(
                    "Freeform gallery registry hid canonical IDs: %s",
                    hidden_ids,
                )
        lines.extend([
            "",
            "Freeform example-gallery protocol for this stage:",
            "1. You may call list_freeform_examples to see current-stage "
            "headers when examples would help.",
            "2. Call read_freeform_example for every example you actually "
            "use as guidance.",
            "3. You may call select_freeform_example to recommend one opened "
            "example, with a nonempty rationale, when a close analogue exists.",
            "Inspection and recommendation are advisory: the stage may "
            "submit without opening an example, and best_example may remain "
            "null. The unique inspection order and optional recommendation "
            "form a stage-local note for downstream freeform stages.",
        ])
    lines.extend([
        "",
        "Other available skill headers (details are not preloaded):",
        headers,
        "Use list_sweep_design_skills or read_sweep_design_skill when another "
        "family contains a relevant same-stage pattern. The callable reader "
        "is restricted to this agent's stage. Never copy a numeric value "
        "from a template as an undeclared solver default.",
        "[END SWEEP-DESIGN SKILL ROUTER]",
    ])
    return "\n".join(lines)


def get_sweep_skill_tools(stage: Optional[str] = None) -> Dict[str, Callable]:
    """Return discovery tools whose detailed reader is bound to one L3 stage.

    Production dispatchers call ``build_sweep_skill_context`` immediately
    before constructing tools, so ``stage`` is normally supplied through the
    context-local binding. The explicit argument supports isolated tests and
    other internal callers. If neither is available, the reader fails closed
    rather than exposing another stage.
    """
    stage_key = _normalize_stage(stage) if stage is not None else (
        _ACTIVE_TOOL_STAGE.get())

    def _list_stage_skill_headers() -> str:
        """List alternative sweep-family headers without loading details."""
        return list_sweep_design_skills()

    def _read_current_stage_skill(skill_id: str = "") -> str:
        """Read one alternative family's template for this agent's L3 stage."""
        if stage_key is None:
            return (
                "ERROR: no L3 stage is bound to this skill reader; build the "
                "stage context before constructing agent tools"
            )
        return read_sweep_design_skill(skill_id, stage_key)

    def _freeform_only_error() -> Optional[str]:
        if _ACTIVE_SWEEP_METHOD.get() != "freeform_sweep":
            return (
                "ERROR: the freeform example gallery is available only when "
                "the selected method is freeform_sweep"
            )
        if stage_key is None:
            return (
                "ERROR: no L3 stage is bound to this gallery reader; build "
                "the stage context before constructing agent tools"
            )
        return None

    def _list_current_stage_freeform_examples() -> str:
        """List this freeform stage's example headers without inspecting them."""
        error = _freeform_only_error()
        return error or list_freeform_examples(stage_key)

    def _read_current_stage_freeform_example(example_id: str = "") -> str:
        """Read and record one current-stage freeform gallery example."""
        error = _freeform_only_error()
        return error or read_freeform_example(example_id, stage=stage_key)

    def _select_current_stage_freeform_example(
        example_id: str = "",
        rationale: str = "",
    ) -> str:
        """Select an inspected example as best and explain why it matches."""
        error = _freeform_only_error()
        return error or select_freeform_example(
            example_id, rationale, stage=stage_key)

    return {
        "list_sweep_design_skills": _list_stage_skill_headers,
        "read_sweep_design_skill": _read_current_stage_skill,
        "list_freeform_examples": _list_current_stage_freeform_examples,
        "read_freeform_example": _read_current_stage_freeform_example,
        "select_freeform_example": _select_current_stage_freeform_example,
    }
