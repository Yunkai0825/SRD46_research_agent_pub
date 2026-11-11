"""free_energy_md_card_editor.py
Minimal, in-place editor for a Free-Energy Markdown Card.

Counterpart to :mod:`free_energy_md_card_reader`.  Where the reader
turns a card into a ``FreeEnergyReport``, this module performs small,
surgical text edits on the card markdown *without* re-rendering the
whole document — so every byte the merger produced is preserved except
the cells we deliberately change.

Current capability
------------------
* :func:`exclude_species` — flip the ``include`` cell of selected
  Section-5 species rows to ``false`` (the reader treats ``include ==
  false`` as an excluded species) and optionally annotate
  ``additional_notes`` with a rationale.  This is how LC2_3 collapses
  duplicate species after the dedup decision: the row stays visible for
  audit but is dropped from the solve.
* :func:`set_species_inclusion` — materialise an exact source-qualified
  include/exclude selection from an unchanged baseline card.  LC2_3's
  supervisory review loop uses this bidirectional editor so an entry may
  be restored as well as excluded without accumulating annotations from
  earlier review passes.

Species are matched by the ``(label, source)`` pair, which is unique
within a single card (a given species lives in exactly one phase /
source).  ``label`` equals the ``species`` column of the dedup report,
so decisions parsed from ``deduplication_check.md`` map directly onto
card rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

_PIPE_RE = re.compile(r"(?:^\||\|$)")        # leading/trailing pipes
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")      # separator row |---|---|

#: Key identifying a species row across the card.
SpeciesKey = Tuple[str, str]                 # (label, source)


@dataclass
class EditRow:
    """Audit record for one row whose ``include`` was flipped to false."""
    label:  str
    source: str
    phase:  str
    note:   str


@dataclass
class InclusionEditRow:
    """Audit record for one explicit include-state change."""
    label:       str
    source:      str
    phase:       str
    old_include: bool
    new_include: bool
    note:        str


def _split_cells(line: str) -> List[str]:
    return [c.strip() for c in _PIPE_RE.sub("", line.strip()).split("|")]


def _join_cells(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _is_species_header(cells: List[str]) -> bool:
    return "label" in cells and "include" in cells and "source" in cells


def exclude_species(
    card_text: str,
    drop_keys: Set[SpeciesKey],
    *,
    note_prefix: str = "dedup: excluded",
    notes_by_key: Optional[Dict[SpeciesKey, str]] = None,
) -> Tuple[str, List[EditRow]]:
    """Set ``include`` → ``false`` for every Section-5 row whose
    ``(label, source)`` is in *drop_keys*.

    Parameters
    ----------
    card_text : full free-energy card markdown.
    drop_keys : set of ``(label, source)`` pairs to exclude.
    note_prefix : text written into ``additional_notes`` for each
        dropped row (appended to any existing note).
    notes_by_key : optional per-key rationale appended after
        ``note_prefix`` (e.g. the LLM rationale for that group).

    Returns
    -------
    (new_card_text, audit) where *audit* lists the rows that were
    flipped.  Rows already ``include == false`` are left untouched and
    not re-audited.
    """
    if not drop_keys:
        return card_text, []

    notes_by_key = notes_by_key or {}
    lines = card_text.splitlines()
    out_lines: List[str] = []
    audit: List[EditRow] = []

    in_table = False
    cols: Dict[str, int] = {}

    for line in lines:
        stripped = line.strip()

        # Detect the header of a Section-5 species table.
        if stripped.startswith("|"):
            cells = _split_cells(line)
            if _is_species_header(cells):
                in_table = True
                cols = {name: i for i, name in enumerate(cells)}
                out_lines.append(line)
                continue
            if in_table and _SEP_RE.match(stripped):
                out_lines.append(line)
                continue
            if in_table:
                # Data row of the active species table.
                label = cells[cols["label"]] if cols["label"] < len(cells) else ""
                source = cells[cols["source"]] if cols["source"] < len(cells) else ""
                key = (label, source)
                inc_i = cols.get("include", -1)
                if (key in drop_keys and 0 <= inc_i < len(cells)
                        and cells[inc_i].lower() != "false"):
                    cells[inc_i] = "false"
                    note = note_prefix
                    extra = notes_by_key.get(key, "")
                    if extra:
                        note = f"{note_prefix} ({extra})"
                    notes_i = cols.get("additional_notes", -1)
                    if 0 <= notes_i < len(cells):
                        existing = cells[notes_i].strip()
                        cells[notes_i] = f"{existing} {note}".strip() if existing else note
                    out_lines.append(_join_cells(cells))
                    audit.append(EditRow(
                        label=label, source=source,
                        phase=cells[cols["phase"]] if cols.get("phase", -1) >= 0
                        and cols["phase"] < len(cells) else "",
                        note=note,
                    ))
                    continue
                out_lines.append(line)
                continue
            # A pipe row that is not part of a species table.
            out_lines.append(line)
            continue

        # Non-pipe line ends any active table.
        in_table = False
        cols = {}
        out_lines.append(line)

    trailing_nl = "\n" if card_text.endswith("\n") else ""
    return "\n".join(out_lines) + trailing_nl, audit


def set_species_inclusion(
    card_text: str,
    include_by_key: Dict[SpeciesKey, bool],
    *,
    notes_by_key: Optional[Dict[SpeciesKey, str]] = None,
    note_prefix: str = "dedup review",
) -> Tuple[str, List[InclusionEditRow]]:
    """Set exact ``include`` values for source-qualified species rows.

    The function is intentionally applied to the *original* LC2_2 card on
    every supervisory pass.  This makes both ``true`` and ``false`` edits
    deterministic and prevents prior-pass notes from being copied into the
    next fresh review context.
    """
    if not include_by_key:
        return card_text, []

    notes_by_key = notes_by_key or {}
    lines = card_text.splitlines()
    out_lines: List[str] = []
    audit: List[InclusionEditRow] = []
    in_table = False
    cols: Dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = _split_cells(line)
            if _is_species_header(cells):
                in_table = True
                cols = {name: i for i, name in enumerate(cells)}
                out_lines.append(line)
                continue
            if in_table and _SEP_RE.match(stripped):
                out_lines.append(line)
                continue
            if in_table:
                label_i = cols.get("label", -1)
                source_i = cols.get("source", -1)
                include_i = cols.get("include", -1)
                if min(label_i, source_i, include_i) < 0:
                    out_lines.append(line)
                    continue
                label = cells[label_i] if label_i < len(cells) else ""
                source = cells[source_i] if source_i < len(cells) else ""
                key = (label, source)
                if key not in include_by_key or include_i >= len(cells):
                    out_lines.append(line)
                    continue

                old_include = cells[include_i].strip().lower() in {
                    "true", "yes", "1",
                }
                new_include = bool(include_by_key[key])
                if old_include == new_include:
                    out_lines.append(line)
                    continue

                cells[include_i] = "true" if new_include else "false"
                extra = (notes_by_key.get(key) or "").strip()
                note = f"{note_prefix}: {extra}" if extra else note_prefix
                notes_i = cols.get("additional_notes", -1)
                if 0 <= notes_i < len(cells):
                    existing = cells[notes_i].strip()
                    cells[notes_i] = (
                        f"{existing} {note}".strip() if existing else note
                    )
                phase_i = cols.get("phase", -1)
                phase = cells[phase_i] if 0 <= phase_i < len(cells) else ""
                out_lines.append(_join_cells(cells))
                audit.append(InclusionEditRow(
                    label=label,
                    source=source,
                    phase=phase,
                    old_include=old_include,
                    new_include=new_include,
                    note=note,
                ))
                continue
            out_lines.append(line)
            continue

        in_table = False
        cols = {}
        out_lines.append(line)

    trailing_nl = "\n" if card_text.endswith("\n") else ""
    return "\n".join(out_lines) + trailing_nl, audit


__all__ = [
    "SpeciesKey",
    "EditRow",
    "InclusionEditRow",
    "exclude_species",
    "set_species_inclusion",
]
