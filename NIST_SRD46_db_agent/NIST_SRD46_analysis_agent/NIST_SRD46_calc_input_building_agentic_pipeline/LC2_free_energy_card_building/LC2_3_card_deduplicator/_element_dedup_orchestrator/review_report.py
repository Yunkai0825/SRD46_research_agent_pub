"""Materialise and render LC2 element-level supervisory review state."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from ...LC2_2_card_db_merger.element_inventory import (
    ElementInventoryEntry,
    card_include_index,
    inventory_by_element,
)
from .._dedup_engine.decision_apply import (
    compute_drop_keys,
    decisions_from_dicts,
)
from card_management_helpers.free_energy_md_card_editor import (
    InclusionEditRow,
    set_species_inclusion,
)


SpeciesKey = Tuple[str, str]
MarkHistory = Mapping[SpeciesKey, Sequence[Mapping[str, Any]]]


@dataclass
class MaterializedReview:
    card_text: str
    include_by_key: Dict[SpeciesKey, bool]
    rationale_by_key: Dict[SpeciesKey, str]
    decision_audit: List[Dict[str, Any]]
    edit_audit: List[InclusionEditRow]


def materialize_review(
    *,
    original_card_text: str,
    report: Any,
    decision_dicts: Sequence[Mapping[str, Any]],
    overrides: Mapping[str, Tuple[bool, str]],
    inventory: Sequence[ElementInventoryEntry],
) -> MaterializedReview:
    """Build one pass from the immutable LC2_2 card, never a prior pass."""
    original = card_include_index(original_card_text)
    decisions = decisions_from_dicts(decision_dicts)
    drop_keys, drop_notes, decision_audit = compute_drop_keys(report, decisions)

    include_by_key: Dict[SpeciesKey, bool] = {}
    rationale_by_key: Dict[SpeciesKey, str] = {}
    for group in report.groups:
        for species in group.species:
            key = (species.name, species.source)
            include_by_key[key] = original.get(key, True) and key not in drop_keys
            if key in drop_notes:
                rationale_by_key[key] = drop_notes[key]

    by_entry_key = {entry.entry_key: entry for entry in inventory}
    for entry_key, (include, reason) in overrides.items():
        entry = by_entry_key[entry_key]
        include_by_key[entry.species_key] = bool(include)
        rationale_by_key[entry.species_key] = f"supervisor override: {reason}"

    card_text, edit_audit = set_species_inclusion(
        original_card_text,
        include_by_key,
        notes_by_key=rationale_by_key,
        note_prefix="LC2 element review",
    )
    return MaterializedReview(
        card_text=card_text,
        include_by_key=include_by_key,
        rationale_by_key=rationale_by_key,
        decision_audit=decision_audit,
        edit_audit=edit_audit,
    )


def _entry_index(
    inventory: Iterable[ElementInventoryEntry],
) -> Dict[SpeciesKey, ElementInventoryEntry]:
    return {entry.species_key: entry for entry in inventory}


def _history_text(
    history: MarkHistory | None,
    key: SpeciesKey,
) -> str:
    if not history or key not in history:
        return ""
    chunks: List[str] = []
    for event in history[key]:
        stage = str(event.get("stage", "")).strip()
        mark = str(event.get("mark", "not examined")).strip()
        reason = str(event.get("reason", "")).strip()
        text = f"{stage}: {mark}" if stage else mark
        if reason:
            text += f" — {reason}"
        chunks.append(text.replace("|", "\\|"))
    return "<br>".join(chunks)


def _current_mark(
    history: MarkHistory | None,
    key: SpeciesKey,
    fallback: str,
) -> str:
    if history and history.get(key):
        return str(history[key][-1].get("mark", fallback))
    return fallback


def render_post_dedup_report(
    *,
    report: Any,
    materialized: MaterializedReview,
    inventory: Sequence[ElementInventoryEntry],
    generation: int,
    mark_history: MarkHistory | None = None,
) -> str:
    """Render all original groups, including excluded entries."""
    entry_index = _entry_index(inventory)
    audit_index = {
        (row["name"], row["source"]): row for row in materialized.decision_audit
    }
    lines = [
        f"# LC2 post-deduplication report — generation {generation}",
        "",
        "All original LC2_2 entries remain visible; `current_include` is the "
        "selection passed to the card.",
        "",
        "| phase | core | elements | family | label | source | current mark | current_include | mark history | rationale |",
        "|-------|------|----------|--------|-------|--------|--------------|-----------------|--------------|-----------|",
    ]
    for group in sorted(report.groups, key=lambda g: (g.phase, g.core_label)):
        for species in sorted(group.species, key=lambda s: (s.source, s.name)):
            key = (species.name, species.source)
            inv = entry_index.get(key)
            audit = audit_index.get(key, {})
            fallback_mark = str(audit.get("decision", "not examined"))
            current_mark = _current_mark(mark_history, key, fallback_mark)
            history_text = _history_text(mark_history, key)
            rationale = materialized.rationale_by_key.get(
                key, str(audit.get("rationale", ""))
            ).replace("|", "\\|")
            lines.append(
                f"| {group.phase} | `{group.core_label}` "
                f"| {', '.join(inv.elements) if inv else '—'} "
                f"| {inv.phase_family if inv else '—'} | `{species.name}` "
                f"| {species.source} | {current_mark} "
                f"| {'true' if materialized.include_by_key.get(key, True) else 'false'} "
                f"| {history_text} | {rationale} |"
            )
    return "\n".join(lines) + "\n"


def render_entries_by_element(
    *,
    inventory: Sequence[ElementInventoryEntry],
    materialized: MaterializedReview,
    mark_history: MarkHistory | None = None,
) -> str:
    audit_index = {
        (row["name"], row["source"]): row for row in materialized.decision_audit
    }
    lines = [
        "# Deduplicated entries by element",
        "",
        "Distinct core groups are deliberately shown together within each "
        "element section for phase-family review.",
    ]
    for element, entries in inventory_by_element(inventory).items():
        lines += [
            "",
            f"## {element}",
            "",
            "| entry_key | include | dedup mark | phase | family | core | label | source | mu_aligned_kJ | mark history | rationale |",
            "|-----------|---------|------------|-------|--------|------|-------|--------|--------------:|--------------|-----------|",
        ]
        for entry in entries:
            audit = audit_index.get(entry.species_key, {})
            fallback_mark = str(audit.get("decision", "not examined"))
            current_mark = _current_mark(
                mark_history, entry.species_key, fallback_mark,
            )
            history_text = _history_text(mark_history, entry.species_key)
            reason = materialized.rationale_by_key.get(entry.species_key, "").replace(
                "|", "\\|"
            )
            lines.append(
                f"| `{entry.entry_key}` "
                f"| {'true' if materialized.include_by_key.get(entry.species_key, entry.original_include) else 'false'} "
                f"| {current_mark} | {entry.phase} | {entry.phase_family} | `{entry.core_label}` "
                f"| `{entry.label}` | {entry.source} | {entry.mu_aligned_kJ:+.3f} "
                f"| {history_text} | {reason} |"
            )
    return "\n".join(lines) + "\n"


def render_mark_history(
    *,
    inventory: Sequence[ElementInventoryEntry],
    mark_history: MarkHistory,
) -> str:
    """Render a complete, source-qualified mark trail for every entry."""
    lines = [
        "# LC2 deduplication mark history",
        "",
        "Every LC2_2 inventory entry is listed. `not examined` means no "
        "deduplication worker returned a verdict for that entry in that "
        "generation; its include value was inherited rather than approved.",
        "",
        "| entry_key | label | source | history |",
        "|-----------|-------|--------|---------|",
    ]
    seen: set[SpeciesKey] = set()
    for entry in sorted(inventory, key=lambda row: (row.elements, row.phase, row.core_label, row.source, row.label)):
        seen.add(entry.species_key)
        history_text = _history_text(mark_history, entry.species_key)
        if not history_text:
            history_text = "not examined"
        lines.append(
            f"| `{entry.entry_key}` | `{entry.label}` | {entry.source} "
            f"| {history_text} |"
        )
    # Pure reference species (for example H/O water-system rows) can be part
    # of the dedup report without belonging to a supervised metal element.
    # They still require an explicit audit mark.
    for key in sorted(set(mark_history) - seen):
        label, source = key
        history_text = _history_text(mark_history, key) or "not examined"
        lines.append(f"| — | `{label}` | {source} | {history_text} |")
    return "\n".join(lines) + "\n"


def selection_diff(
    before: Mapping[SpeciesKey, bool],
    after: Mapping[SpeciesKey, bool],
    inventory: Sequence[ElementInventoryEntry],
    *,
    reason: str,
) -> List[Dict[str, Any]]:
    entry_index = _entry_index(inventory)
    rows: List[Dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        old = before.get(key, True)
        new = after.get(key, True)
        if old == new:
            continue
        entry = entry_index.get(key)
        rows.append({
            "entry_key": entry.entry_key if entry else "",
            "label": key[0],
            "source": key[1],
            "before": old,
            "after": new,
            "reason": reason,
        })
    return rows


def render_diff(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Latest review diff",
        "",
        "| entry_key | label | source | before | after | reason |",
        "|-----------|-------|--------|--------|-------|--------|",
    ]
    if not rows:
        lines.append("| — | — | — | — | — | no inclusion changes |")
    for row in rows:
        lines.append(
            f"| `{row.get('entry_key', '')}` | `{row.get('label', '')}` "
            f"| {row.get('source', '')} | {str(row.get('before')).lower()} "
            f"| {str(row.get('after')).lower()} "
            f"| {str(row.get('reason', '')).replace('|', '\\|')} |"
        )
    return "\n".join(lines) + "\n"


def diff_to_json(rows: Sequence[Mapping[str, Any]]) -> str:
    return json.dumps(list(rows), indent=2, ensure_ascii=False)


def solid_family_warnings(
    *,
    inventory: Sequence[ElementInventoryEntry],
    include_by_key: Mapping[SpeciesKey, bool],
    instructions: Mapping[str, str],
    purpose: str,
    tasks: str,
) -> List[str]:
    """Flag an unexplained mixture of hydrated and anhydrous solid models."""
    def explicitly_retains_both(text: str) -> bool:
        lowered = text.lower()
        direct_markers = (
            "hydrated and anhydrous", "anhydrous and hydrated",
            "hydroxides and oxides", "oxides and hydroxides",
            "hydroxides/oxides", "oxides/hydroxides",
            "phase survey", "all solid phases",
        )
        if any(marker in lowered for marker in direct_markers):
            return True
        retain_words = ("retain", "keep", "include", "preserve")
        hydrated_words = (
            "hydrated", "hydroxide", "oxyhydroxide", "goethite",
            "fe(oh", "cu(oh",
        )
        anhydrous_words = (
            "anhydrous", "hematite", "magnetite",
            "fe2o3", "fe3o4", "cuo",
        )
        return (
            any(word in lowered for word in retain_words)
            and any(word in lowered for word in hydrated_words)
            and (
                any(word in lowered for word in anhydrous_words)
                or re.search(r"\boxides?\b", lowered) is not None
            )
        )

    warnings: List[str] = []
    query = f"{purpose} {tasks}".lower()
    explicit_query_comparison = explicitly_retains_both(query)
    for element, entries in inventory_by_element(inventory).items():
        families = {
            entry.phase_family
            for entry in entries
            if include_by_key.get(entry.species_key, entry.original_include)
            and entry.phase_family in {"hydrated_solid", "anhydrous_solid"}
        }
        instruction = instructions.get(element, "").lower()
        explicit_instruction_comparison = explicitly_retains_both(instruction)
        if len(families) > 1 and not (
            explicit_query_comparison or explicit_instruction_comparison
        ):
            warnings.append(
                f"{element}: hydrated and anhydrous solid branches are both "
                "included, but neither the user request nor the element "
                "instruction explicitly requests both."
            )
    return warnings


__all__ = [
    "MaterializedReview",
    "materialize_review",
    "render_post_dedup_report",
    "render_entries_by_element",
    "render_mark_history",
    "selection_diff",
    "render_diff",
    "diff_to_json",
    "solid_family_warnings",
]
