"""
enriched_card_writer.py — Rewrite a speciation card with Pourbaix IDs.
======================================================================
Takes an original speciation card (Markdown) and enriches it:

* Sections 1–4: remap internal IDs (M1→Fe$+2 etc.), add Atlas-only metals
* Section 5: fully regenerated tables including Atlas species, with
  Pourbaix IDs in stoich columns and include/exclude flags from dedup.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

_RE_POURBAIX = re.compile(r'^([A-Z][a-z]*)\$([+-]\d+)$')


# ======================================================================
#  Data container for enriched species
# ======================================================================

@dataclass
class EnrichedSpecies:
    """One row in the output Section 5 table."""
    species_id: str
    original_id: str
    label: str
    charge: int
    phase: str            # "aqueous" or "dissolution"
    log_beta: float
    mu0_free_kJ: float
    mu0_canon_kJ: float
    stoich: str           # Pourbaix-notation stoich string
    include: bool
    additional_notes: str
    # Enrichment metadata (not in table, but useful)
    source: str           # "SRD-46" or "Atlas"
    mu_aligned_kJ: float


# ======================================================================
#  Section 5 table generation
# ======================================================================

_S5_HEADER = (
    "| species_id | original_id | label | charge | phase "
    "| log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich "
    "| source | include | additional_notes |"
)
_S5_SEP = (
    "|------------|-------------|-------|--------|-------"
    "|----------|-------------|--------------|---------------|--------"
    "|--------|---------|------------------|"
)


def _fmt_charge(c: int) -> str:
    return f"{c:+d}"


def _fmt_float(v: float) -> str:
    return f"{v:+.4f}"


def _fmt_include(b: bool) -> str:
    return "true" if b else "false"


def _species_row(sp: EnrichedSpecies) -> str:
    """Format a single species as a pipe-delimited table row."""
    return (
        f"| {sp.species_id} "
        f"| {sp.original_id} "
        f"| {sp.label} "
        f"| {_fmt_charge(sp.charge)} "
        f"| {sp.phase} "
        f"| {_fmt_float(sp.log_beta)} "
        f"| {_fmt_float(sp.mu0_free_kJ)} "
        f"| {_fmt_float(sp.mu0_canon_kJ)} "
        f"| {_fmt_float(sp.mu_aligned_kJ)} "
        f"| {sp.stoich} "
        f"| {sp.source} "
        f"| {_fmt_include(sp.include)} "
        f"| {sp.additional_notes} |"
    )


# ──────────────────────────────────────────────────────────────────────
#  Structured Section-5 ordering
# ──────────────────────────────────────────────────────────────────────
# Rows are ordered by: (1) element block — metal-free proton/ligand
# species first, then metals alphabetically; (2) valence — the reference
# oxidation state first, then by increasing distance from it; (3) ligand
# — free/hydroxo (OH = L0) first, then L1, L2, …; (4) protonation — the
# canonical HₓL reference (highest net H) first, then decreasing H.
# μ°_canon then species_id break any remaining ties deterministically.

_RE_STOICH_PAIR = re.compile(r'([^\s,]+):([+-]?\d+)')
_RE_METAL_TOKEN = re.compile(r'([A-Z][a-z]*)\$([+-]\d+)')
_RE_LIGAND_TOKEN = re.compile(r'L(\d+)')
_RE_EMB_H = re.compile(r'\[H\](-?\d+)?')
_RE_EMB_OH = re.compile(r'\[OH\](-?\d+)?')


def _parse_species_for_sort(
    stoich: str,
) -> Tuple[Optional[Tuple[str, int]], int, int]:
    """Extract (metal, ligand_index, net_H) from a stoich string.

    Handles both SRD-46 (``[Cu$+2]:+1, [L1]:+2``) and Atlas
    (``Fe$+6:+1 H:-8``) notations.  ``metal`` is ``(element, charge)``
    of the first metal token, or ``None`` for proton/ligand-only
    species.  ``ligand_index`` is the largest ``L<n>`` present (0 when
    only free ion / hydroxide).  ``net_H`` is the signed proton count
    (each OH contributes −1; embedded ``[H]k`` / ``[OH]k`` honoured).
    """
    metal: Optional[Tuple[str, int]] = None
    ligand_index = 0
    net_h = 0
    for token, coeff_s in _RE_STOICH_PAIR.findall(stoich or ""):
        coeff = int(coeff_s)
        mm = _RE_METAL_TOKEN.search(token)
        if mm and metal is None:
            metal = (mm.group(1), int(mm.group(2)))
        for lm in _RE_LIGAND_TOKEN.findall(token):
            ligand_index = max(ligand_index, int(lm))
        h_unit = 0
        for hm in _RE_EMB_H.finditer(token):
            h_unit += int(hm.group(1)) if hm.group(1) else 1
        for om in _RE_EMB_OH.finditer(token):
            h_unit -= int(om.group(1)) if om.group(1) else 1
        if token == "H":
            h_unit += 1
        elif token == "OH":
            h_unit -= 1
        net_h += h_unit * coeff
    return metal, ligand_index, net_h


def _species_sort_key(
    sp: EnrichedSpecies,
    element_ref_charge: Dict[str, int],
) -> Tuple:
    """Build the structured ordering key for one Section-5 row."""
    metal, ligand_index, net_h = _parse_species_for_sort(sp.stoich)
    if metal is None:
        # Metal-free proton/ligand species sort to the very top.
        return (0, "", 0, 0, 0, ligand_index, -net_h,
                sp.mu0_canon_kJ, sp.species_id)
    element, charge = metal
    ref_charge = element_ref_charge.get(element)
    if ref_charge is None:
        is_ref, dist = 1, abs(charge)
    else:
        is_ref = 0 if charge == ref_charge else 1
        dist = abs(charge - ref_charge)
    return (1, element, is_ref, dist, -charge, ligand_index, -net_h,
            sp.mu0_canon_kJ, sp.species_id)


def generate_section5(
    aqueous: List[EnrichedSpecies],
    dissolution: List[EnrichedSpecies],
    gas: List[EnrichedSpecies],
    element_ref_charge: Optional[Dict[str, int]] = None,
) -> str:
    """Generate full Section 5 markdown (5.1 – 5.4)."""
    ref_charges = element_ref_charge or {}

    def _key(s: EnrichedSpecies) -> Tuple:
        return _species_sort_key(s, ref_charges)

    lines: List[str] = []
    lines.append("## 5. Standard Chemical Potentials")
    lines.append("")
    lines.append(
        "All values in kJ/mol. Sorted by element (proton/ligand systems "
        "first), then valence (reference state first), ligand, and "
        "protonation (canonical HₓL reference first)."
    )
    lines.append("")

    # §5.1 Aqueous
    lines.append("### 5.1 Aqueous Species")
    lines.append("")
    if aqueous:
        sorted_aq = sorted(aqueous, key=_key)
        lines.append(_S5_HEADER)
        lines.append(_S5_SEP)
        for sp in sorted_aq:
            lines.append(_species_row(sp))
    else:
        lines.append("(No aqueous species in this system.)")
    lines.append("")

    # §5.2 Dissolution
    lines.append("### 5.2 Dissolution / Solid Species")
    lines.append("")
    if dissolution:
        sorted_dis = sorted(dissolution, key=_key)
        lines.append(_S5_HEADER)
        lines.append(_S5_SEP)
        for sp in sorted_dis:
            lines.append(_species_row(sp))
    else:
        lines.append("(No dissolution species in this system.)")
    lines.append("")

    # §5.3 Gas
    lines.append("### 5.3 Gas Species")
    lines.append("")
    if gas:
        sorted_gas = sorted(gas, key=_key)
        lines.append(_S5_HEADER)
        lines.append(_S5_SEP)
        for sp in sorted_gas:
            lines.append(_species_row(sp))
    else:
        lines.append("(No gas species in this system.)")
    lines.append("")

    # §5.4 Supportive
    lines.append("### 5.4 Supportive Thermodynamic Data")
    lines.append("")
    lines.append(
        "| entity_id | property | value | unit "
        "| derived_mu0_kJ | notes |"
    )
    lines.append(
        "|-----------|----------|-------|------"
        "|----------------|-------|"
    )
    lines.append(
        "| S0 | pKw | 14.00 | - "
        "| +79.9077 | water self-dissociation |"
    )
    lines.append(
        "| e- | charge | -1 | - "
        "| +0.0000 | electron reference μ°≡0 |"
    )
    lines.append(
        "| e- | F_over_RT_ln10 | 16.9044 | V⁻¹ "
        "| - | F/(2.303RT) at 25°C |"
    )
    lines.append(
        "| e- | nernst_factor | 0.05916 | V "
        "| - | 2.303RT/F at 25°C |"
    )

    return "\n".join(lines)


# ======================================================================
#  Parse Card-3 (dedup resolved) markdown → EnrichedSpecies
# ======================================================================

def _parse_card3_table(text: str) -> List[Dict[str, str]]:
    """Parse all pipe-delimited table rows from Card-3 markdown.

    Returns one dict per data row, keyed by header names.
    Handles tables split across multiple phase sections.
    """
    rows: List[Dict[str, str]] = []
    lines = text.splitlines()
    current_headers: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            current_headers = []
            continue

        cells = [c.strip() for c in stripped.split("|")[1:-1]]

        # Detect header row (contains "species_id" or "#")
        if not current_headers:
            if any("species_id" in c or c == "#" for c in cells):
                current_headers = cells
            continue

        # Skip separator row
        if all(set(c) <= {"-", " ", ":"} for c in cells):
            continue

        # Data row
        row = {}
        for j, h in enumerate(current_headers):
            row[h] = cells[j] if j < len(cells) else ""
        rows.append(row)

    return rows


def _required_float(s: str, *, field: str, species_id: str) -> float:
    s = s.strip().lstrip("+")
    if not s or s in ("—", "–", "Not defined"):
        raise ValueError(f"species {species_id!r} field {field!r} is Not defined")
    try:
        value = float(s)
    except ValueError as exc:
        raise ValueError(
            f"species {species_id!r} field {field!r} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"species {species_id!r} field {field!r} must be finite")
    return value


def parse_card3_to_enriched(card3_md: str) -> List[EnrichedSpecies]:
    """Parse a Card-3 (dedup resolved) markdown into EnrichedSpecies.

    Card-3 table must contain columns: species_id, original_id, phase,
    log_beta, mu0_free_kJ, mu0_canon_kJ, mu_aligned_kJ, stoich, source,
    charge, species (label), include, reason.
    """
    if not card3_md.strip():
        raise ValueError("Card-3 content is empty; no implicit species card is permitted")

    rows = _parse_card3_table(card3_md)
    if not rows:
        raise ValueError("Card-3 contains no species rows")
    enriched: List[EnrichedSpecies] = []

    for row in rows:
        species_id = row.get("species_id", "").strip()
        if not species_id or species_id == "Not defined":
            raise ValueError("Card-3 species_id is Not defined")
        include_raw = row.get("include", "").replace("*", "").strip().lower()
        if include_raw not in {"true", "false"}:
            raise ValueError(
                f"species {species_id!r} include must be exactly true or false")
        include = include_raw == "true"
        charge_number = _required_float(
            row.get("charge", "").replace("+", ""),
            field="charge", species_id=species_id)
        if not charge_number.is_integer():
            raise ValueError(f"species {species_id!r} charge must be an integer")
        charge = int(charge_number)
        source = row.get("source", "")
        label = row.get("species", "")
        reason = row.get("reason", "").rstrip("…").strip()
        phase = row.get("phase", "").strip().lower()
        if phase not in {"aqueous", "dissolution", "solid", "gas"}:
            raise ValueError(
                f"species {species_id!r} phase is Not defined or unsupported: {phase!r}")
        stoich = row.get("stoich", "").strip()
        if not stoich or stoich == "Not defined":
            raise ValueError(f"species {species_id!r} stoichiometry is Not defined")

        # Build notes
        notes = ""
        if not include:
            notes = f"EXCLUDED ({source}): {reason[:80]}"
        elif reason:
            notes = reason[:80]
        # Prepend atlas-name info for Atlas species
        if source == "Atlas":
            atlas_note = f"Atlas: {label}"
            notes = f"{atlas_note}. {notes}".strip() if notes else atlas_note

        enriched.append(EnrichedSpecies(
            species_id=species_id,
            original_id=row.get("original_id", ""),
            label=label,
            charge=charge,
            phase=phase,
            log_beta=_required_float(
                row.get("log_beta", ""), field="log_beta", species_id=species_id),
            mu0_free_kJ=_required_float(
                row.get("mu0_free_kJ", ""), field="mu0_free_kJ", species_id=species_id),
            mu0_canon_kJ=_required_float(
                row.get("mu0_canon_kJ", ""), field="mu0_canon_kJ", species_id=species_id),
            stoich=stoich,
            include=include,
            additional_notes=notes,
            source=source,
            mu_aligned_kJ=_required_float(
                row.get("mu_aligned_kJ", ""),
                field="mu_aligned_kJ", species_id=species_id),
        ))

    return enriched


# ======================================================================
#  Section 1–4 enrichment
# ======================================================================

def _remap_id_in_cells(
    line: str,
    id_map: Dict[str, str],
) -> str:
    """Replace M-IDs in pipe-delimited table cells using id_map."""
    if not line.strip().startswith("|"):
        return line
    cells = line.split("|")
    new_cells: List[str] = []
    for cell in cells:
        txt = cell.strip()
        if txt in id_map:
            # Exact cell match (e.g. internal_id column)
            new_cells.append(f" {id_map[txt]} ")
        else:
            # Partial replacement in stoich-like strings: "M1:+1 H:-1"
            def _repl(m: re.Match) -> str:
                key = m.group(0)
                return id_map.get(key, key)
            txt2 = re.sub(r"\bM\d+\b", _repl, txt)
            new_cells.append(f" {txt2} " if txt2 != txt else cell)
    return "|".join(new_cells)


def _find_section_range(
    lines: List[str],
    prefix: str,
) -> Tuple[int, int]:
    """Return (start_line, end_line) for a section starting with prefix.

    end_line is the first line of the NEXT section at the same or
    higher heading level, or len(lines).
    """
    start = -1
    heading_level = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and prefix in stripped:
            start = i
            heading_level = len(stripped) - len(stripped.lstrip("#"))
            break
    if start < 0:
        return -1, -1

    # Find end: next heading at same or higher level
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            lvl = len(stripped) - len(stripped.lstrip("#"))
            if lvl <= heading_level:
                return start, i
    return start, len(lines)


def enrich_section1_notation(
    lines: List[str],
    id_map: Dict[str, str],
    atlas_metals: List[Dict],
) -> List[str]:
    """Remap M-IDs in §1 notation table and add Atlas-only entries.

    Only modifies the first table (Symbol | Meaning), not sub-tables.
    """
    start, end = _find_section_range(lines, "1. Notation")
    if start < 0:
        return lines

    new_lines = list(lines)

    # Remap existing M-ID rows
    for i in range(start, end):
        new_lines[i] = _remap_id_in_cells(new_lines[i], id_map)

    # Find the FIRST table in §1 (Symbol | Meaning), then its last row
    first_table_start = -1
    first_table_end = -1
    in_table = False
    for i in range(start, end):
        stripped = new_lines[i].strip()
        if stripped.startswith("|"):
            if not in_table:
                first_table_start = i
                in_table = True
            first_table_end = i
        elif in_table:
            # Left the first table
            break

    if first_table_end > 0:
        insert_rows = []
        for am in atlas_metals:
            pid = am["internal_id"]
            desc = f"Metal component from Atlas: {am['name']}"
            insert_rows.append(f"| {pid} | {desc} |")
        for j, row in enumerate(insert_rows):
            new_lines.insert(first_table_end + 1 + j, row)

    return new_lines


def enrich_section22_metals(
    lines: List[str],
    id_map: Dict[str, str],
    atlas_metals: List[Dict],
) -> List[str]:
    """Remap M-IDs in §2.2 Metals table and add Atlas-only metal rows."""
    new_lines = list(lines)
    start, end = _find_section_range(new_lines, "2.2 Metals")
    if start < 0:
        return new_lines

    for i in range(start, end):
        new_lines[i] = _remap_id_in_cells(new_lines[i], id_map)

    # Find last table row
    last_table = -1
    for i in range(start, min(end, len(new_lines))):
        if new_lines[i].strip().startswith("|"):
            last_table = i
    if last_table > 0:
        insert_rows = []
        for am in atlas_metals:
            insert_rows.append(
                f"| {am['internal_id']} | {am['name']} "
                f"| {_fmt_charge(am['charge'])} | 0 "
                f"| Pourbaix Atlas |  |"
            )
        for j, row in enumerate(insert_rows):
            new_lines.insert(last_table + 1 + j, row)

    return new_lines


def enrich_section24_valence(
    lines: List[str],
    id_map: Dict[str, str],
    atlas_metals: List[Dict],
    n_valences_total: int,
) -> List[str]:
    """Remap M-IDs in §2.4 table and add Atlas-only valence rows."""
    new_lines = list(lines)
    start, end = _find_section_range(new_lines, "2.4 Metal Valence")
    if start < 0:
        return new_lines

    for i in range(start, end):
        new_lines[i] = _remap_id_in_cells(new_lines[i], id_map)

    last_table = -1
    for i in range(start, min(end, len(new_lines))):
        if new_lines[i].strip().startswith("|"):
            last_table = i
    if last_table > 0:
        insert_rows = []
        for am in atlas_metals:
            insert_rows.append(
                f"| {am['element']} | {am['internal_id']} "
                f"| {am['name']} | {_fmt_charge(am['charge'])} "
                f"| false | {n_valences_total} |"
            )
        for j, row in enumerate(insert_rows):
            new_lines.insert(last_table + 1 + j, row)

    return new_lines


def enrich_section31_refs(
    lines: List[str],
    id_map: Dict[str, str],
    atlas_metals: List[Dict],
    atlas_offsets: Dict[str, float],
    valence_offsets: Dict[str, float],
) -> List[str]:
    """Remap M-IDs in §3.1 table, update mu0_ref_kJ for existing metals,
    and add Atlas-only reference rows."""
    new_lines = list(lines)
    start, end = _find_section_range(new_lines, "3.1 Component Reference")
    if start < 0:
        return new_lines

    # First pass: remap IDs
    for i in range(start, end):
        new_lines[i] = _remap_id_in_cells(new_lines[i], id_map)

    # Find header row and mu0_ref_kJ column index
    header_idx = -1
    mu_col = -1
    comp_col = -1
    for i in range(start, end):
        if "mu0_ref_kJ" in new_lines[i]:
            header_idx = i
            raw_cells = new_lines[i].split("|")
            for ci, cell in enumerate(raw_cells):
                if "mu0_ref_kJ" in cell:
                    mu_col = ci
                if "component_id" in cell:
                    comp_col = ci
            break

    # Second pass: update mu0_ref_kJ for existing metals
    if header_idx >= 0 and mu_col >= 0 and comp_col >= 0:
        for i in range(header_idx + 1, end):
            line = new_lines[i]
            if not line.strip().startswith("|"):
                continue
            cells = line.split("|")
            if len(cells) <= max(mu_col, comp_col):
                continue
            if "---" in cells[comp_col]:
                continue
            comp_id = cells[comp_col].strip()
            if comp_id in valence_offsets:
                cells[mu_col] = f" {_fmt_float(valence_offsets[comp_id])} "
                new_lines[i] = "|".join(cells)

    # Add atlas-only metal rows
    last_table = -1
    for i in range(start, min(end, len(new_lines))):
        if new_lines[i].strip().startswith("|"):
            last_table = i
    if last_table > 0:
        insert_rows = []
        for am in atlas_metals:
            pid = am["internal_id"]
            offset = atlas_offsets.get(pid, 0.0)
            insert_rows.append(
                f"| {pid} | {am['name']} | metal "
                f"| {am['name']}(aq/s) | {_fmt_float(offset)} "
                f"| RULE 1 | {am['element']} "
                f"| {_fmt_charge(am['charge'])} | false |"
            )
        for j, row in enumerate(insert_rows):
            new_lines.insert(last_table + 1 + j, row)

    return new_lines


# ======================================================================
#  Metal-row reordering: group by element, reference first
# ======================================================================

def _reorder_section_metals(
    lines: List[str],
    section_prefix: str,
    id_col: int,
    reference_ids: Set[str],
    element_order: List[str],
) -> List[str]:
    """Reorder metal rows in the first table of a section.

    Groups metals by element (in *element_order*), placing the reference
    state first within each group, then ascending charge.  Non-metal rows
    (M0, L0, ligands, …) keep their relative positions.

    Parameters
    ----------
    id_col : 1-based index among pipe-separated cells (cell[0] is the
             empty string before the leading ``|``).
    """
    start, end = _find_section_range(lines, section_prefix)
    if start < 0:
        return lines

    # Locate first table: header → separator → data rows
    in_table = False
    sep_idx = -1
    table_end = -1          # inclusive
    for i in range(start, end):
        stripped = lines[i].strip()
        if stripped.startswith("|"):
            if not in_table:
                in_table = True
            if "---" in stripped and sep_idx < 0:
                sep_idx = i
            table_end = i
        elif in_table:
            break               # left the first table

    if sep_idx < 0 or table_end <= sep_idx:
        return lines

    data_start = sep_idx + 1
    data_end = table_end + 1        # exclusive

    # Classify each data row
    metals: List[tuple] = []        # (element, pid, charge, row_text)
    non_metals_before: List[str] = []
    non_metals_after: List[str] = []
    seen_metal = False

    for i in range(data_start, data_end):
        row = lines[i]
        if not row.strip().startswith("|"):
            continue
        cells = row.split("|")
        is_metal = False
        if len(cells) > id_col:
            val = cells[id_col].strip()
            m = _RE_POURBAIX.match(val)
            if m:
                is_metal = True
                metals.append((m.group(1), val, int(m.group(2)), row))
                seen_metal = True
        if not is_metal:
            (non_metals_after if seen_metal else non_metals_before).append(row)

    if not metals:
        return lines

    # Sort: element order → reference first → charge ascending
    def _key(tup):
        el, pid, chg, _ = tup
        el_idx = element_order.index(el) if el in element_order else 999
        return (el_idx, pid not in reference_ids, chg)

    metals.sort(key=_key)

    reordered = (non_metals_before
                 + [row for _, _, _, row in metals]
                 + non_metals_after)

    result = list(lines)
    for i, row in enumerate(reordered):
        result[data_start + i] = row
    return result


def _fix_section24_nvalences(
    lines: List[str],
    element_order: List[str],
) -> List[str]:
    """Update n_valences column in §2.4 to reflect per-element counts."""
    start, end = _find_section_range(lines, "2.4 Metal Valence")
    if start < 0:
        return lines

    # Find table data rows
    sep_idx = -1
    table_end = -1
    for i in range(start, end):
        stripped = lines[i].strip()
        if stripped.startswith("|"):
            table_end = i
            if "---" in stripped and sep_idx < 0:
                sep_idx = i
    if sep_idx < 0 or table_end <= sep_idx:
        return lines

    data_start = sep_idx + 1

    # Find n_valences column index and element column index
    header = lines[sep_idx - 1]
    hcells = header.split("|")
    nv_col = -1
    el_col = -1
    for ci, cell in enumerate(hcells):
        if "n_valences" in cell:
            nv_col = ci
        if "element" in cell:
            el_col = ci
    if nv_col < 0 or el_col < 0:
        return lines

    # Count metals per element
    from collections import Counter
    elem_counts: Counter = Counter()
    for i in range(data_start, table_end + 1):
        cells = lines[i].split("|")
        if len(cells) > el_col and "---" not in cells[el_col]:
            elem_counts[cells[el_col].strip()] += 1

    # Update n_valences cells
    result = list(lines)
    for i in range(data_start, table_end + 1):
        cells = result[i].split("|")
        if len(cells) > max(nv_col, el_col) and "---" not in cells[el_col]:
            el = cells[el_col].strip()
            cells[nv_col] = f" {elem_counts[el]} "
            result[i] = "|".join(cells)

    return result


def _replace_section5(card_text: str, new_section5: str) -> str:
    """Replace everything from '## 5.' to end of file with new_section5."""
    pattern = r"(^|\n)(##\s+5\.\s+Standard Chemical Potentials\b)"
    m = re.search(pattern, card_text)
    if m:
        cut_pos = m.start() + len(m.group(1))
        return card_text[:cut_pos] + new_section5 + "\n"
    # Fallback: append
    return card_text.rstrip() + "\n\n" + new_section5 + "\n"


# ======================================================================
#  Top-level card rewriter
# ======================================================================

def build_enriched_card(
    card_text: str,
    id_map: Dict[str, str],
    enriched_species: List[EnrichedSpecies],
    atlas_metals: List[Dict],
    atlas_offsets: Dict[str, float],
    valence_offsets: Dict[str, float],
    n_valences_total: int,
) -> str:
    """Produce the full enriched card text.

    Parameters
    ----------
    card_text : original card markdown
    id_map : M1→Fe$+2 mapping
    enriched_species : all species rows (SRD-46 + Atlas, included + excluded)
    atlas_metals : dicts with keys internal_id, name, element, charge
    atlas_offsets : {atlas_metal_id: mu0_ref_kJ}
    valence_offsets : {pourbaix_id: offset_kJ} for all metals (card + atlas)
    n_valences_total : total number of valence entries (card + atlas)
    """
    # Partition enriched species by phase
    aqueous = [s for s in enriched_species if s.phase == "aqueous"]
    dissolution = [s for s in enriched_species
                   if s.phase in ("dissolution", "solid")]
    gas = [s for s in enriched_species if s.phase == "gas"]

    # Per-element reference charge (μ° ≡ 0 ⇒ offset 0.0) drives the
    # valence ordering of the Section 5 tables.
    element_ref_charge: Dict[str, int] = {}
    for pid, off in valence_offsets.items():
        if off == 0.0:
            m = _RE_POURBAIX.match(pid)
            if m:
                element_ref_charge[m.group(1)] = int(m.group(2))

    # Generate new Section 5
    section5 = generate_section5(aqueous, dissolution, gas,
                                 element_ref_charge)

    # Enrich Sections 1–4 (work on lines)
    lines = card_text.split("\n")
    lines = enrich_section1_notation(lines, id_map, atlas_metals)
    lines = enrich_section22_metals(lines, id_map, atlas_metals)
    lines = enrich_section24_valence(
        lines, id_map, atlas_metals, n_valences_total)
    lines = enrich_section31_refs(lines, id_map, atlas_metals, atlas_offsets,
                                   valence_offsets)

    # ── Reorder metals: group by element, reference first ─────
    reference_ids: Set[str] = {
        pid for pid, off in valence_offsets.items() if off == 0.0
    }
    seen: set = set()
    element_order: List[str] = []
    for pid in id_map.values():
        m = _RE_POURBAIX.match(pid)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            element_order.append(m.group(1))

    lines = _reorder_section_metals(
        lines, "1. Notation", 1, reference_ids, element_order)
    lines = _reorder_section_metals(
        lines, "2.2 Metals", 1, reference_ids, element_order)
    lines = _reorder_section_metals(
        lines, "2.4 Metal Valence", 2, reference_ids, element_order)
    lines = _fix_section24_nvalences(lines, element_order)
    lines = _reorder_section_metals(
        lines, "3.1 Component Reference", 1, reference_ids, element_order)

    enriched_text = "\n".join(lines)

    # Replace section 5
    enriched_text = _replace_section5(enriched_text, section5)

    return enriched_text
