"""Deterministic LC2_2 element inventory for downstream LC2_3 review."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


_COMPONENT_ELEMENT_RE = re.compile(r"^([A-Z][a-z]*)\$[+-]\d+$")
_HYDRATED_MARKERS = (
    "hydrat", "hyd.", "hydr.", "hydrox", "(oh)", "[oh]", "o(oh)", "ooh",
)


@dataclass(frozen=True)
class ElementInventoryEntry:
    """One immutable LC2_2 species row exposed to the LC2_3 supervisor."""

    entry_key: str
    elements: Tuple[str, ...]
    phase: str
    phase_family: str
    core_label: str
    label: str
    species_id: str
    source: str
    charge: int
    multiplier: int
    mu_aligned_kJ: float
    original_include: bool

    @property
    def species_key(self) -> Tuple[str, str]:
        return (self.label, self.source)


def _entry_key(label: str, source: str) -> str:
    digest = hashlib.sha256(
        f"{source}\0{label}".encode("utf-8")
    ).hexdigest()[:16]
    return f"DEDUP-{digest}"


def _split_cells(line: str) -> List[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def card_include_index(card_text: str) -> Dict[Tuple[str, str], bool]:
    """Read source-qualified include values without importing the card parser."""
    result: Dict[Tuple[str, str], bool] = {}
    columns: Dict[str, int] = {}
    in_table = False
    for line in card_text.splitlines():
        if not line.strip().startswith("|"):
            in_table = False
            columns = {}
            continue
        cells = _split_cells(line)
        if {"label", "source", "include"}.issubset(cells):
            columns = {name: idx for idx, name in enumerate(cells)}
            in_table = True
            continue
        if not in_table or not cells or set("".join(cells)) <= {"-", ":"}:
            continue
        try:
            label = cells[columns["label"]]
            source = cells[columns["source"]]
            raw = cells[columns["include"]].strip().lower()
        except (IndexError, KeyError):
            continue
        result[(label, source)] = raw in {"true", "yes", "1"}
    return result


def _elements_for_species(species: Any, valence_elements: Mapping[str, str]) -> Tuple[str, ...]:
    explicit = tuple(
        sorted({str(x) for x in (getattr(species, "elements", ()) or ()) if str(x)})
    )
    if explicit:
        return explicit

    extra = getattr(species, "extra", {}) or {}
    if extra.get("element"):
        return (str(extra["element"]),)

    found = set()
    for component in (getattr(species, "raw_stoich", {}) or {}):
        if component in valence_elements:
            found.add(valence_elements[component])
            continue
        match = _COMPONENT_ELEMENT_RE.match(str(component))
        if match:
            found.add(match.group(1))
    return tuple(sorted(found))


def _phase_family(element: str, phase: str, label: str) -> str:
    """Advisory solid-family label; the LLM still makes the chemistry choice."""
    if phase != "solid":
        return phase
    lower = label.lower().replace(" ", "")
    if any(marker.replace(" ", "") in lower for marker in _HYDRATED_MARKERS):
        return "hydrated_solid"
    if lower in {element.lower(), f"[{element.lower()}]", f"{element.lower()}(s)"}:
        return "elemental_solid"
    return "anhydrous_solid"


def build_element_inventory(
    grouped: Mapping[str, Sequence[Any]],
    valence_table: Sequence[Mapping[str, Any]],
    merged_card_text: str,
) -> List[ElementInventoryEntry]:
    """Build a stable, element-owned inventory from LC2_2 unified groups.

    Ownership comes from explicit Atlas/card component metadata, never from
    a lossy oxidation-state integer conversion.  A multi-element species is
    intentionally visible in every applicable element section.
    """
    valence_elements = {
        str(row.get("internal_id", "")): str(row.get("element", ""))
        for row in valence_table
        if row.get("internal_id") and row.get("element")
    }
    include_index = card_include_index(merged_card_text)
    entries: List[ElementInventoryEntry] = []

    for phase in sorted(grouped):
        groups = sorted(grouped.get(phase, ()), key=lambda g: str(g.core_label))
        for group in groups:
            for species in sorted(
                group.species,
                key=lambda sp: (str(sp.source), str(sp.name)),
            ):
                elements = _elements_for_species(species, valence_elements)
                if not elements:
                    # Water/ligand-only rows are not element-dedup targets. They
                    # remain in the canonical report and card unchanged.
                    continue
                source = str(species.source)
                label = str(species.name)
                species_id = str((getattr(species, "extra", {}) or {}).get(
                    "species_id", ""
                ))
                family = (
                    _phase_family(elements[0], str(phase), label)
                    if len(elements) == 1 else str(phase)
                )
                entries.append(ElementInventoryEntry(
                    entry_key=_entry_key(label, source),
                    elements=elements,
                    phase=str(phase),
                    phase_family=family,
                    core_label=str(group.core_label),
                    label=label,
                    species_id=species_id,
                    source=source,
                    charge=int(species.charge),
                    multiplier=int(species.multiplier),
                    mu_aligned_kJ=float(species.mu_aligned_kJ),
                    original_include=include_index.get((label, source), True),
                ))

    # The same (label, source) must resolve to exactly one card row.
    by_key: Dict[str, ElementInventoryEntry] = {}
    for entry in entries:
        prior = by_key.get(entry.entry_key)
        if prior is not None and prior.species_key != entry.species_key:
            raise ValueError(f"element inventory entry-key collision: {entry.entry_key}")
        by_key[entry.entry_key] = entry
    return sorted(
        by_key.values(),
        key=lambda e: (e.elements, e.phase, e.phase_family, e.core_label, e.source, e.label),
    )


def inventory_by_element(
    inventory: Iterable[ElementInventoryEntry],
) -> Dict[str, List[ElementInventoryEntry]]:
    result: Dict[str, List[ElementInventoryEntry]] = {}
    for entry in inventory:
        for element in entry.elements:
            result.setdefault(element, []).append(entry)
    for element in result:
        result[element] = sorted(
            result[element],
            key=lambda e: (e.phase, e.phase_family, e.core_label, e.source, e.label),
        )
    return dict(sorted(result.items()))


def inventory_to_json(inventory: Iterable[ElementInventoryEntry]) -> str:
    return json.dumps([asdict(entry) for entry in inventory], indent=2, ensure_ascii=False)


def inventory_from_json(text: str) -> List[ElementInventoryEntry]:
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("element inventory JSON must be a list")
    return [
        ElementInventoryEntry(
            entry_key=str(row["entry_key"]),
            elements=tuple(str(x) for x in row["elements"]),
            phase=str(row["phase"]),
            phase_family=str(row["phase_family"]),
            core_label=str(row["core_label"]),
            label=str(row["label"]),
            species_id=str(row.get("species_id", "")),
            source=str(row["source"]),
            charge=int(row["charge"]),
            multiplier=int(row["multiplier"]),
            mu_aligned_kJ=float(row["mu_aligned_kJ"]),
            original_include=bool(row["original_include"]),
        )
        for row in rows
    ]


def render_element_inventory(inventory: Iterable[ElementInventoryEntry]) -> str:
    lines = [
        "# LC2_2 element inventory",
        "",
        "This is the immutable, deterministic inventory supplied to LC2_3. "
        "Entries remain distinct even when they belong to the same element review section.",
    ]
    for element, entries in inventory_by_element(inventory).items():
        lines += [
            "",
            f"## {element}",
            "",
            "| entry_key | phase | family | core | label | species_id | source | charge | mult | mu_aligned_kJ | original_include |",
            "|-----------|-------|--------|------|-------|------------|--------|-------:|-----:|--------------:|------------------|",
        ]
        for entry in entries:
            lines.append(
                f"| `{entry.entry_key}` | {entry.phase} | {entry.phase_family} "
                f"| `{entry.core_label}` | `{entry.label}` | `{entry.species_id}` "
                f"| {entry.source} | {entry.charge:+d} | {entry.multiplier} "
                f"| {entry.mu_aligned_kJ:+.3f} | "
                f"{'true' if entry.original_include else 'false'} |"
            )
    return "\n".join(lines) + "\n"


__all__ = [
    "ElementInventoryEntry",
    "card_include_index",
    "build_element_inventory",
    "inventory_by_element",
    "inventory_to_json",
    "inventory_from_json",
    "render_element_inventory",
]
