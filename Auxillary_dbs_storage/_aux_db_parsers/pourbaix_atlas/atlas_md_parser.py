"""
atlas_parser.py — Parse Pourbaix Atlas ``.md`` files for species data.
======================================================================
Extracts the **Substances Considered** table from Pourbaix atlas
Markdown files.  Only the free-energy table at the top of each file
is parsed — domain-knowledge prose and equilibrium-equation sections
are intentionally skipped (per objectives.md: "only free energies are
corrected after pdf parsing").

Public API
----------
    parse_pourbaix_atlas_md(path)  → list[AtlasSpecies]
    list_atlas_elements()          → list[dict]
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("AtlasParser")

# ── Atlas directory default (overrideable) ────────────────────
# This standalone parser lives in Auxillary_dbs_storage/_aux_db_parsers/
# pourbaix_atlas/ ; the raw atlas .md files sit one level up under
# Auxillary_dbs_storage/Pourbaix_atlas_database/.
_THIS_DIR = Path(__file__).resolve().parent
_DEFAULT_ATLAS_DIR = _THIS_DIR.parents[1] / "Pourbaix_atlas_database"


# ══════════════════════════════════════════════════════════════
#  Data container
# ══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AtlasSpecies:
    """One species from the Pourbaix atlas *Substances Considered* table."""
    phase: str                  # "Solid", "Dissolved", "Gaseous"
    species: str                # e.g. "Fe2+", "Fe(OH)3 (hydr.)"
    oxidation_state: str        # e.g. "+2", "0", "+2, +3"
    mu0_cal: float              # free enthalpy of formation in calories
    name: str                   # descriptive name
    element: str                # parent element symbol (from filename)
    source_file: str            # filename stem


# ══════════════════════════════════════════════════════════════
#  Internal parsing helpers
# ══════════════════════════════════════════════════════════════

_MU0_RE = re.compile(r"^[+-]?[\d,]+(?:\.\d+)?$")


def _parse_mu0(raw: str) -> Optional[float]:
    """Parse mu_0 value from atlas table cell.

    Handles comma-separated thousands (e.g. "-118,580") and plain
    integers.  Returns None on parse failure.
    """
    cleaned = raw.strip().replace(",", "").replace(" ", "")
    if not cleaned or cleaned == "—" or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_element_from_filename(stem: str) -> str:
    """Extract element symbol from atlas filename like '12_Iron'."""
    parts = stem.split("_", 1)
    if len(parts) >= 2:
        return parts[1]
    return stem


def _parse_substances_table(text: str) -> List[dict]:
    """Parse the Substances Considered markdown table."""
    rows: List[dict] = []

    # Find the table: starts after "## Substances Considered"
    section_match = re.search(
        r"##\s+Substances\s+Considered\s*\n",
        text, re.IGNORECASE,
    )
    if not section_match:
        return rows

    block = text[section_match.end():]

    # Find table header row (contains "Phase" and "mu_0")
    header_pattern = re.compile(
        r"^\|[^|]*Phase[^|]*\|[^|]*Species[^|]*\|[^|]*Oxidation[^|]*\|[^|]*mu_0[^|]*\|[^|]*Name[^|]*\|",
        re.IGNORECASE | re.MULTILINE,
    )
    hdr_match = header_pattern.search(block)
    if not hdr_match:
        return rows

    # Skip header + separator row
    after_header = block[hdr_match.end():]
    lines = after_header.split("\n")
    started = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue

        # Skip separator row (|---|---|...)
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            started = True
            continue

        # Must be a table row
        if not stripped.startswith("|"):
            if started:
                break
            continue

        started = True
        cells = [c.strip() for c in stripped.split("|")]
        # Remove empty first/last from leading/trailing pipes
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]

        if len(cells) < 5:
            continue

        phase = cells[0].strip()
        species = cells[1].strip()
        ox_state = cells[2].strip()
        mu0_raw = cells[3].strip()
        name = cells[4].strip()

        mu0 = _parse_mu0(mu0_raw)
        if mu0 is None and mu0_raw not in ("0", ""):
            log.warning("Could not parse mu_0=%r for %s", mu0_raw, species)
            continue
        if mu0 is None and mu0_raw == "0":
            mu0 = 0.0

        rows.append({
            "phase": phase,
            "species": species,
            "oxidation_state": ox_state,
            "mu0_cal": mu0,
            "name": name,
        })

    return rows


# ══════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════

def parse_pourbaix_atlas_md(
    path: str | Path,
) -> List[AtlasSpecies]:
    """Parse a single Pourbaix atlas .md file.

    Parameters
    ----------
    path : path to the atlas markdown file

    Returns
    -------
    List[AtlasSpecies] with one entry per species in the
    *Substances Considered* table.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Atlas file not found: {p}")

    text = p.read_text(encoding="utf-8")
    element = _extract_element_from_filename(p.stem)
    raw_rows = _parse_substances_table(text)

    species_list = []
    for r in raw_rows:
        if r["mu0_cal"] is None:
            continue
        species_list.append(AtlasSpecies(
            phase=r["phase"],
            species=r["species"],
            oxidation_state=r["oxidation_state"],
            mu0_cal=r["mu0_cal"],
            name=r["name"],
            element=element,
            source_file=p.stem,
        ))

    log.info("Parsed %d species from %s", len(species_list), p.name)
    return species_list


def list_atlas_elements(atlas_dir: str | Path | None = None) -> List[dict]:
    """List all available elements in the Pourbaix atlas database.

    Returns a list of dicts with keys: number, element, filename, path.
    """
    d = Path(atlas_dir) if atlas_dir else _DEFAULT_ATLAS_DIR
    if not d.exists():
        return []

    results = []
    for f in sorted(d.glob("*.md")):
        stem = f.stem
        parts = stem.split("_", 1)
        number = parts[0] if parts[0].isdigit() else ""
        element = parts[1] if len(parts) >= 2 else stem
        results.append({
            "number": number,
            "element": element,
            "filename": f.name,
            "path": str(f),
        })
    return results


# ── Symbol → element name mapping for atlas lookup ───────────
# Built from standard chemical symbols so find_atlas_file("Cu")
# resolves to "Copper" instead of hitting "Mercury" via substring.
_SYMBOL_TO_NAME: dict[str, str] = {
    "H": "Hydrogen", "He": "Helium", "Li": "Lithium", "Be": "Beryllium",
    "B": "Boron", "C": "Carbon", "N": "Nitrogen", "O": "Oxygen",
    "F": "Fluorine", "Ne": "Neon", "Na": "Sodium", "Mg": "Magnesium",
    "Al": "Aluminium", "Si": "Silicon", "P": "Phosphorus", "S": "Sulphur",
    "Cl": "Chlorine", "Ar": "Argon", "K": "Potassium", "Ca": "Calcium",
    "Sc": "Scandium", "Ti": "Titanium", "V": "Vanadium", "Cr": "Chromium",
    "Mn": "Manganese", "Fe": "Iron", "Co": "Cobalt", "Ni": "Nickel",
    "Cu": "Copper", "Zn": "Zinc", "Ga": "Gallium", "Ge": "Germanium",
    "As": "Arsenic", "Se": "Selenium", "Br": "Bromine", "Kr": "Krypton",
    "Rb": "Rubidium", "Sr": "Strontium", "Y": "Yttrium", "Zr": "Zirconium",
    "Nb": "Niobium", "Mo": "Molybdenum", "Tc": "Technetium", "Ru": "Ruthenium",
    "Rh": "Rhodium", "Pd": "Palladium", "Ag": "Silver", "Cd": "Cadmium",
    "In": "Indium", "Sn": "Tin", "Sb": "Antimony", "Te": "Tellurium",
    "I": "Iodine", "Xe": "Xenon", "Cs": "Cesium", "Ba": "Barium",
    "La": "Lanthanum", "Ce": "Cerium", "Pr": "Praseodymium", "Nd": "Neodymium",
    "Sm": "Samarium", "Eu": "Europium", "Gd": "Gadolinium", "Tb": "Terbium",
    "Dy": "Dysprosium", "Ho": "Holmium", "Er": "Erbium", "Tm": "Thulium",
    "Yb": "Ytterbium", "Lu": "Lutetium", "Hf": "Hafnium", "Ta": "Tantalum",
    "W": "Tungsten", "Re": "Rhenium", "Os": "Osmium", "Ir": "Iridium",
    "Pt": "Platinum", "Au": "Gold", "Hg": "Mercury", "Tl": "Thallium",
    "Pb": "Lead", "Bi": "Bismuth", "Po": "Polonium", "At": "Astatine",
    "Rn": "Radon", "Fr": "Francium", "Ra": "Radium", "Ac": "Actinium",
    "Th": "Thorium", "Pa": "Protactinium", "U": "Uranium", "Np": "Neptunium",
    "Pu": "Plutonium", "Am": "Americium",
}


def find_atlas_file(element: str,
                    atlas_dir: str | Path | None = None) -> Optional[Path]:
    """Find the atlas .md file for a given element name or symbol.

    Matches case-insensitively against the filename element portion.
    If *element* is a chemical symbol (e.g. "Cu"), it is first
    resolved to the full element name ("Copper") so that the atlas
    file ``14_Copper.md`` is matched correctly.

    Returns None if not found.
    """
    d = Path(atlas_dir) if atlas_dir else _DEFAULT_ATLAS_DIR
    if not d.exists():
        return None

    element_stripped = element.strip()
    # Resolve symbol → full name (e.g. "Cu" → "Copper")
    resolved = _SYMBOL_TO_NAME.get(element_stripped, element_stripped)
    element_lower = resolved.lower()

    for f in d.glob("*.md"):
        stem = f.stem
        parts = stem.split("_", 1)
        file_element = parts[1].lower() if len(parts) >= 2 else stem.lower()
        if file_element == element_lower:
            return f

    # Also try the original input as-is (handles full names passed directly)
    if resolved.lower() != element_stripped.lower():
        orig_lower = element_stripped.lower()
        for f in d.glob("*.md"):
            stem = f.stem
            parts = stem.split("_", 1)
            file_element = parts[1].lower() if len(parts) >= 2 else stem.lower()
            if file_element == orig_lower:
                return f

    return None
