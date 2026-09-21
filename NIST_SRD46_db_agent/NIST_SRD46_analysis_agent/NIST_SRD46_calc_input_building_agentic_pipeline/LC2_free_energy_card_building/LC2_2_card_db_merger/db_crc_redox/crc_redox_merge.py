"""
redox_merger.py — Embed Pourbaix atlas redox data into card §3.1 and §5.
========================================================================
Takes an existing free-energy MD card (built from SRD-46 speciation data)
and enriches the standard chemical potentials in Sections 3.1 and 5 so that
species of different oxidation states of the same element are on the same
energy scale.

How it works
------------
1. Parse §2.4 Metal Valence Alignment to identify reference / non-reference
   metals for each element.
2. Load the Pourbaix atlas for each element.
3. Use ``compute_valence_offsets()`` to derive an energy offset (kJ/mol)
   for each non-reference metal from the atlas E° data.
4. Update §3.1: set ``mu0_ref_kJ`` for non-reference metals.
5. Update §5.1 / §5.2: shift ``mu0_free_kJ`` and ``mu0_canon_kJ`` for
   every species that involves a non-reference metal, by
   ``stoich_metal × offset_kJ``.

No sections beyond §5 are generated — the downstream card parser derives
redox equilibria from the μ° differences.

Public API
----------
    embed_redox_in_card(card_path, atlas_dir) → dict
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..db_pourbaix_atlas.atlas_loader import atlas_species_for_element
from ..db_pourbaix_atlas.atlas_data import AtlasSpecies
from .._md_card_merge_core.merge_helpers import (
    _parse_card_metals,
    _parse_card_valence_table,
    _element_from_metal_name,
)
from .._md_card_merge_core.reference_state_converter import (
    compute_valence_offsets,
    cal_to_kJ,
    F_CONST,
    CAL_TO_J,
)

log = logging.getLogger("RedoxMerger")


# ══════════════════════════════════════════════════════════════
#  §3.1 and §5 updater helpers
# ══════════════════════════════════════════════════════════════

def _update_section_31(card_text: str, offsets: Dict[str, float]) -> str:
    """Update §3.1 Component Reference Declarations: set mu0_ref_kJ."""
    lines = card_text.split("\n")
    sec = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("#") and "3.1" in line and "Component" in line:
            sec = i
            break
    if sec < 0:
        return card_text

    # Find the table header row
    idx = sec + 1
    while idx < len(lines):
        if lines[idx].strip().startswith("|"):
            break
        idx += 1
    if idx >= len(lines):
        return card_text

    header_line = lines[idx].strip()
    headers = [h.strip() for h in header_line.split("|")[1:-1]]

    # Find column indices
    try:
        cid_col = headers.index("component_id")
        mu_col = headers.index("mu0_ref_kJ")
    except ValueError:
        return card_text

    # Skip separator
    idx += 1
    if idx < len(lines) and re.match(r"^\s*\|[\s\-|]+\|\s*$", lines[idx]):
        idx += 1

    # Update rows
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.split("|")]
        # cells[0] and cells[-1] are empty strings from leading/trailing |
        data_cells = cells[1:-1] if cells[-1] == "" else cells[1:]
        if len(data_cells) > max(cid_col, mu_col):
            comp_id = data_cells[cid_col].strip()
            if comp_id in offsets and offsets[comp_id] != 0.0:
                data_cells[mu_col] = f"{offsets[comp_id]:+.4f}"
                lines[idx] = "| " + " | ".join(data_cells) + " |"
        idx += 1

    return "\n".join(lines)


def _compute_species_shift(
    stoich_str: str,
    offsets: Dict[str, float],
) -> float:
    """Compute the total μ° shift for a species from its stoich string."""
    shift = 0.0
    for tok in stoich_str.split():
        if ":" not in tok:
            continue
        key, val = tok.split(":", 1)
        key = key.strip()
        if key in offsets:
            shift += int(val) * offsets[key]
    return shift


def _update_section_5x(card_text: str, offsets: Dict[str, float]) -> str:
    """Update §5.1 and §5.2 tables: shift mu0_free_kJ and mu0_canon_kJ."""
    lines = card_text.split("\n")
    result = list(lines)

    for section_prefix in ["5.1 Aqueous", "5.2 Dissolution"]:
        # Find section
        sec = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("#") and section_prefix in line:
                sec = i
                break
        if sec < 0:
            continue

        # Find table header
        idx = sec + 1
        while idx < len(result):
            if result[idx].strip().startswith("|"):
                break
            idx += 1
        if idx >= len(result):
            continue

        header_line = result[idx].strip()
        headers = [h.strip() for h in header_line.split("|")[1:-1]]

        try:
            stoich_col = headers.index("stoich")
            mu_free_col = headers.index("mu0_free_kJ")
            mu_canon_col = headers.index("mu0_canon_kJ")
        except ValueError:
            continue

        # Skip separator
        idx += 1
        if idx < len(result) and re.match(r"^\s*\|[\s\-|]+\|\s*$", result[idx]):
            idx += 1

        # Update rows
        while idx < len(result):
            line = result[idx].strip()
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.split("|")]
            data_cells = cells[1:-1] if cells[-1] == "" else cells[1:]
            cols_needed = max(stoich_col, mu_free_col, mu_canon_col)
            if len(data_cells) > cols_needed:
                stoich_str = data_cells[stoich_col].strip()
                shift = _compute_species_shift(stoich_str, offsets)
                if abs(shift) > 1e-6:
                    old_free = _sfloat(data_cells[mu_free_col])
                    old_canon = _sfloat(data_cells[mu_canon_col])
                    data_cells[mu_free_col] = f"{old_free + shift:+.4f}"
                    data_cells[mu_canon_col] = f"{old_canon + shift:+.4f}"
                    result[idx] = "| " + " | ".join(data_cells) + " |"
            idx += 1

    return "\n".join(result)


def _sfloat(s: str, default: float = 0.0) -> float:
    s = s.strip()
    if not s or s == "—" or s == "–":
        return default
    try:
        return float(s)
    except ValueError:
        return default


# ══════════════════════════════════════════════════════════════
#  Main embed function
# ══════════════════════════════════════════════════════════════

def embed_redox_in_card(
    card_path: str | Path,
    atlas_dir: str | Path | None = None,
    *,
    csv_path: str | Path | None = None,
    write_back: bool = True,
) -> dict:
    """Embed Pourbaix atlas redox offsets into a free-energy MD card.

    Updates §3.1 ``mu0_ref_kJ`` and §5.1/§5.2 μ° values so that
    different oxidation states of the same element are on a common
    energy scale.  No sections beyond §5 are touched or added.

    Parameters
    ----------
    card_path   : path to the existing free-energy card .md
    atlas_dir   : Pourbaix atlas directory (auto-detected if None)
    csv_path    : path to pourbaix_substances_all.csv (preferred)
    write_back  : if True, overwrite the card file in place

    Returns
    -------
    dict with keys: status, element, offsets, card_path
    """
    card_path = Path(card_path)
    if not card_path.exists():
        return {"status": "error", "error": f"Card not found: {card_path}"}

    card_text = card_path.read_text(encoding="utf-8")

    # 1. Parse metals and valence table
    metals = _parse_card_metals(card_text)
    if not metals:
        return {"status": "error", "error": "No metals found in card header"}

    valence_table = _parse_card_valence_table(card_text)
    if not valence_table:
        return {
            "status": "no_valence",
            "error": "No §2.4 valence table (single-valence system?)",
            "card_path": str(card_path),
        }

    # 2. Load atlas species for each element
    elements = list(dict.fromkeys(
        _element_from_metal_name(m) for m in metals
    ))
    log.info("Card metals: %s → elements: %s", metals, elements)

    all_atlas: List[AtlasSpecies] = []
    for element in elements:
        species = atlas_species_for_element(element, csv_path)
        if not species:
            log.warning("No atlas species for element: %s", element)
            continue
        all_atlas.extend(species)

    if not all_atlas:
        return {
            "status": "no_atlas",
            "error": "No atlas data found for any element",
            "elements": elements,
            "card_path": str(card_path),
        }

    # 3. Compute offsets
    offsets = compute_valence_offsets(all_atlas, valence_table)
    if not any(abs(v) > 1e-6 for v in offsets.values()):
        return {
            "status": "no_offset",
            "error": "All offsets are zero (no multi-valent redox to embed)",
            "offsets": offsets,
            "card_path": str(card_path),
        }

    log.info("Valence offsets: %s", offsets)

    # 4. Update §3.1
    new_text = _update_section_31(card_text, offsets)

    # 5. Update §5.1 and §5.2
    new_text = _update_section_5x(new_text, offsets)

    # 6. Write back
    if write_back:
        card_path.write_text(new_text, encoding="utf-8")
        log.info("Wrote updated card with redox offsets: %s", card_path.name)

    return {
        "status": "ok",
        "element": ", ".join(elements),
        "offsets": offsets,
        "card_path": str(card_path),
    }


# ══════════════════════════════════════════════════════════════
#  Legacy API (kept for backward compat, delegates to embed)
# ══════════════════════════════════════════════════════════════

def merge_redox_into_card(
    card_path: str | Path,
    atlas_dir: str | Path | None = None,
    *,
    csv_path: str | Path | None = None,
    write_back: bool = True,
    include_solids: bool = True,
    max_couples: int = 50,
) -> dict:
    """Legacy wrapper — now delegates to ``embed_redox_in_card``."""
    return embed_redox_in_card(
        card_path, atlas_dir, csv_path=csv_path, write_back=write_back,
    )
