"""dedup_md_card_reader.py
Parse a ``deduplication_check.md`` report back into structured groups.

This is the inverse of
``LC2_2_card_db_merger/_md_card_merge_core/species_dedup_report_writer.py``.
LC2_2 is purely a *merger + dedup-report generator*; it never drops
species.  LC2_3 consumes the report this parser produces, lets an LLM
decide which species in each core-stoichiometry group survive, then
edits the merged free-energy card accordingly.  No intermediate JSON is
needed — the markdown report is the canonical hand-off.

What this reads
---------------
The per-phase **overview tables** are the canonical, complete record of
the grouping::

    | # | core | species | source | charge | mult | mu_aligned_kJ | n_e | misalignment_kJ |

Every species appears exactly once there, tagged with its ``core``
label and phase section.  Rows sharing the same ``(phase, core)`` form
one :class:`DedupGroup`.  The richer ``### Duplicated Groups``
subsections are a human-facing superset of the overview and are *not*
parsed (the overview already carries every field LC2_3 needs).

The species ``name`` column equals the ``label`` column of the merged
card's Section 5, so it is the join key when applying keep/drop
decisions back onto ``free_energy_card.md``.

Design goals
------------
  • Self-contained — no thermodynamics / pipeline imports, so any stage
    may parse a report cheaply.
  • Field names on :class:`DedupSpecies` (name, source, charge,
    mu_aligned_kJ, multiplier) map directly onto the LC2_3 dedup
    engine and the card editor's ``(name, source)`` join key.
  • Tolerant of missing optional sections; strict on the overview
    header column order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# ══════════════════════════════════════════════════════════════════
#  Canonical phase keys (match the ``_grouped`` dict in LC2_2)
# ══════════════════════════════════════════════════════════════════

#: Map a phase-section title keyword → canonical phase key.
_PHASE_KEYWORDS: Tuple[Tuple[str, str], ...] = (
    ("aqueous", "aqueous"),
    ("solid", "solid"),
    ("gas", "gas"),
)

_PIPE_RE = re.compile(r"(?:^\||\|$)")          # leading/trailing pipes
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")        # separator row |---|---|
_BACKTICK_RE = re.compile(r"^`(.*)`$")          # `core_label`

# "## 1. Aqueous / Dissolved Species"
_PHASE_HEADING_RE = re.compile(r"^##\s+\d+\.\s+(.*)$")
# "Baseline source for misalignment deltas: **SRD-46**."
_BASELINE_RE = re.compile(r"Baseline source for misalignment deltas:\s*\*\*(.+?)\*\*")
# "# Deduplication Check: <system>"
_TITLE_RE = re.compile(r"^#\s+Deduplication Check:\s*(.*)$")
# "**Total species**: 39 | **Core groups**: 33 | ..."
_TOTALS_RE = re.compile(r"\*\*(.+?)\*\*:\s*(\d+)")

# Expected overview-table column order (used to detect the table).
_OVERVIEW_COLS = ("#", "core", "species", "source", "charge", "mult",
                  "mu_aligned_kJ", "n_e", "misalignment_kJ")


# ══════════════════════════════════════════════════════════════════
#  Data model
# ══════════════════════════════════════════════════════════════════

@dataclass
class DedupSpecies:
    """One row of a phase overview table.

    Field names map onto the LC2_3 deterministic dedup engine and the
    card editor's ``(name, source)`` join key without translation.
    """
    name:          str
    source:        str
    charge:        int
    multiplier:    int
    mu_aligned_kJ: float
    phase:         str
    core_label:    str
    n_e:           Optional[int] = None
    misalignment:  str = "—"      # "ref" | "—" | signed delta string
    notes:         str = ""       # additional_notes (e.g. [srd-dup ...])


@dataclass
class DedupGroup:
    """All species sharing one ``(phase, core_label)``."""
    phase:      str
    core_label: str
    species:    List[DedupSpecies] = field(default_factory=list)

    @property
    def key(self) -> Tuple[str, str]:
        return (self.phase, self.core_label)

    @property
    def count(self) -> int:
        return len(self.species)

    @property
    def is_singleton(self) -> bool:
        return len(self.species) <= 1

    @property
    def is_multi_source(self) -> bool:
        return len({s.source for s in self.species}) > 1


@dataclass
class ComponentRow:
    """One row of the ``### Component Mapping`` table."""
    pourbaix_id: str
    original_id: str
    name:        str
    element:     str
    charge:      str


@dataclass
class DedupReport:
    """Structured view of a ``deduplication_check.md`` report."""
    system_name:       str
    baseline_source:   str
    sources_present:   List[str]
    component_mapping: List[ComponentRow]
    groups:            List[DedupGroup]
    totals:            Dict[str, int]

    @property
    def grouped(self) -> Dict[str, List[DedupGroup]]:
        """Groups bucketed by phase key (mirrors LC2_2 ``_grouped``)."""
        out: Dict[str, List[DedupGroup]] = {}
        for g in self.groups:
            out.setdefault(g.phase, []).append(g)
        return out

    def group(self, phase: str, core_label: str) -> Optional[DedupGroup]:
        for g in self.groups:
            if g.phase == phase and g.core_label == core_label:
                return g
        return None


# ══════════════════════════════════════════════════════════════════
#  Low-level helpers
# ══════════════════════════════════════════════════════════════════

def _phase_key(title: str) -> Optional[str]:
    low = title.lower()
    for kw, key in _PHASE_KEYWORDS:
        if kw in low:
            return key
    return None


def _strip_backticks(s: str) -> str:
    s = s.strip()
    m = _BACKTICK_RE.match(s)
    return m.group(1) if m else s


def _to_int(s: str, default: Optional[int] = None) -> Optional[int]:
    s = (s or "").strip().lstrip("+")
    if not s or s in ("—", "–", "-"):
        return default
    try:
        return int(s)
    except ValueError:
        return default


def _to_float(s: str, default: float = 0.0) -> float:
    s = (s or "").strip().lstrip("+")
    if not s or s in ("—", "–"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _to_mult(s: str, default: int = 1) -> int:
    """Parse a multiplier cell like ``2x`` → 2."""
    s = (s or "").strip().rstrip("xX")
    val = _to_int(s, default)
    return val if val is not None else default


def _parse_md_table(lines: List[str], start: int) -> Tuple[List[Dict[str, str]], int]:
    """Parse a pipe-delimited markdown table starting at/after *start*.

    Returns ``(list-of-row-dicts, next-line-index-after-table)``.  Each
    row dict maps column-header → stripped cell value.  Stops scanning
    for the header if a markdown heading is reached first.
    """
    idx = start
    while idx < len(lines) and not lines[idx].strip().startswith("|"):
        if lines[idx].strip().startswith("#"):
            return [], idx
        idx += 1
    if idx >= len(lines):
        return [], idx

    headers = [h.strip() for h in _PIPE_RE.sub("", lines[idx].strip()).split("|")]
    idx += 1
    if idx < len(lines) and _SEP_RE.match(lines[idx].strip()):
        idx += 1

    rows: List[Dict[str, str]] = []
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("|"):
            break
        if _SEP_RE.match(line):
            idx += 1
            continue
        cells = [c.strip() for c in _PIPE_RE.sub("", line).split("|")]
        rows.append({h: (cells[i] if i < len(cells) else "")
                     for i, h in enumerate(headers)})
        idx += 1
    return rows, idx


def _is_overview_header(line: str) -> bool:
    if not line.strip().startswith("|"):
        return False
    headers = [h.strip() for h in _PIPE_RE.sub("", line.strip()).split("|")]
    return headers[:3] == ["#", "core", "species"]


# ══════════════════════════════════════════════════════════════════
#  Section parsers
# ══════════════════════════════════════════════════════════════════

def _parse_component_mapping(lines: List[str]) -> List[ComponentRow]:
    start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("#") and "Component Mapping" in line:
            start = i + 1
            break
    if start < 0:
        return []
    rows, _ = _parse_md_table(lines, start)
    out: List[ComponentRow] = []
    for r in rows:
        out.append(ComponentRow(
            pourbaix_id=r.get("pourbaix_id", ""),
            original_id=r.get("original_id", ""),
            name=r.get("name", ""),
            element=r.get("element", ""),
            charge=r.get("charge", ""),
        ))
    return out


def _parse_totals(lines: List[str]) -> Dict[str, int]:
    for line in lines:
        if line.strip().startswith("**Total species**"):
            return {m.group(1): int(m.group(2))
                    for m in _TOTALS_RE.finditer(line)}
    return {}


def _parse_overview_rows(
    rows: List[Dict[str, str]], phase: str,
) -> List[DedupSpecies]:
    out: List[DedupSpecies] = []
    for r in rows:
        core = _strip_backticks(r.get("core", ""))
        raw_notes = r.get("notes", "").strip()
        out.append(DedupSpecies(
            name=r.get("species", "").strip(),
            source=r.get("source", "").strip(),
            charge=_to_int(r.get("charge", ""), 0) or 0,
            multiplier=_to_mult(r.get("mult", "")),
            mu_aligned_kJ=_to_float(r.get("mu_aligned_kJ", "")),
            phase=phase,
            core_label=core,
            n_e=_to_int(r.get("n_e", ""), None),
            misalignment=r.get("misalignment_kJ", "").strip() or "—",
            notes="" if raw_notes in ("—", "–") else raw_notes,
        ))
    return out


def _group_rows(species: List[DedupSpecies]) -> List[DedupGroup]:
    """Bucket species into groups by ``(phase, core_label)``, preserving
    first-appearance order."""
    order: List[Tuple[str, str]] = []
    buckets: Dict[Tuple[str, str], DedupGroup] = {}
    for sp in species:
        key = (sp.phase, sp.core_label)
        g = buckets.get(key)
        if g is None:
            g = DedupGroup(phase=sp.phase, core_label=sp.core_label)
            buckets[key] = g
            order.append(key)
        g.species.append(sp)
    return [buckets[k] for k in order]


# ══════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════

def parse_dedup_markdown(text: str) -> DedupReport:
    """Parse ``deduplication_check.md`` text into a :class:`DedupReport`."""
    lines = text.splitlines()

    system_name = ""
    baseline_source = "SRD-46"
    for line in lines[:12]:
        m = _TITLE_RE.match(line.strip())
        if m:
            system_name = m.group(1).strip()
        m = _BASELINE_RE.search(line)
        if m:
            baseline_source = m.group(1).strip()

    component_mapping = _parse_component_mapping(lines)
    totals = _parse_totals(lines)

    # Walk phase sections, parsing the first overview table in each.
    all_species: List[DedupSpecies] = []
    current_phase: Optional[str] = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        hm = _PHASE_HEADING_RE.match(line.strip())
        if hm:
            current_phase = _phase_key(hm.group(1))
            i += 1
            continue
        if current_phase and _is_overview_header(line):
            rows, nxt = _parse_md_table(lines, i)
            all_species.extend(_parse_overview_rows(rows, current_phase))
            # Skip the rest of this phase's detail subsections until the
            # next phase heading (avoid re-parsing the species tables in
            # the "### Duplicated Groups" block).
            i = nxt
            while i < n and not _PHASE_HEADING_RE.match(lines[i].strip()):
                i += 1
            continue
        i += 1

    groups = _group_rows(all_species)
    sources_present = sorted({sp.source for sp in all_species})

    return DedupReport(
        system_name=system_name,
        baseline_source=baseline_source,
        sources_present=sources_present,
        component_mapping=component_mapping,
        groups=groups,
        totals=totals,
    )


def read_dedup_report(path: Union[str, Path]) -> DedupReport:
    """Read and parse a ``deduplication_check.md`` file."""
    path = Path(path)
    return parse_dedup_markdown(path.read_text(encoding="utf-8"))


__all__ = [
    "DedupSpecies",
    "DedupGroup",
    "ComponentRow",
    "DedupReport",
    "parse_dedup_markdown",
    "read_dedup_report",
]
