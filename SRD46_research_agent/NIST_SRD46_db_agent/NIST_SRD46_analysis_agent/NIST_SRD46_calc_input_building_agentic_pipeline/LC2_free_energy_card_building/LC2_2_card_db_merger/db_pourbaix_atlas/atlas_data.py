"""
atlas_data.py — Shared Pourbaix-atlas runtime data contract.
=============================================================
Holds the data structures consumed at *runtime* by the LC2_2 merge
engine: the ``AtlasSpecies`` record and the element symbol → name map.

These are deliberately separate from the raw-database parsers (which
live under ``Auxillary_dbs_storage/_aux_db_parsers/`` and run once to
produce the cleaned CSV).  The loader (:mod:`atlas_loader`) reads that
CSV into ``AtlasSpecies`` objects on every pipeline run.
"""
from __future__ import annotations

from dataclasses import dataclass


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


# ── Symbol → element name mapping for atlas lookup ───────────
# Built from standard chemical symbols so a lookup for "Cu"
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
    "I": "Iodine", "Xe": "Xenon", "Cs": "Caesium", "Ba": "Barium",
    "La": "Lanthanum", "Ce": "Cerium", "Pr": "Praseodymium", "Nd": "Neodymium",
    "Pm": "Promethium", "Sm": "Samarium", "Eu": "Europium", "Gd": "Gadolinium",
    "Tb": "Terbium",
    "Dy": "Dysprosium", "Ho": "Holmium", "Er": "Erbium", "Tm": "Thulium",
    "Yb": "Ytterbium", "Lu": "Lutetium", "Hf": "Hafnium", "Ta": "Tantalum",
    "W": "Tungsten", "Re": "Rhenium", "Os": "Osmium", "Ir": "Iridium",
    "Pt": "Platinum", "Au": "Gold", "Hg": "Mercury", "Tl": "Thallium",
    "Pb": "Lead", "Bi": "Bismuth", "Po": "Polonium", "At": "Astatine",
    "Rn": "Radon", "Fr": "Francium", "Ra": "Radium", "Ac": "Actinium",
    "Th": "Thorium", "Pa": "Protactinium", "U": "Uranium", "Np": "Neptunium",
    "Pu": "Plutonium", "Am": "Americium",
}

__all__ = ["AtlasSpecies", "_SYMBOL_TO_NAME"]
