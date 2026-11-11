"""
General chemical-name normalizer.

Public API:
    normalize_chemical_name(name) -> NormalizedChemical | None
    extract_chemicals_from_text(text) -> List[NormalizedChemical]
    NormalizedChemical (dataclass)
"""
from .normalizer import (
    CHEM_KIND_LIGAND,
    CHEM_KIND_METAL,
    NormalizedChemical,
    extract_chemicals_from_text,
    normalize_chemical_name,
)

__all__ = [
    "CHEM_KIND_LIGAND",
    "CHEM_KIND_METAL",
    "NormalizedChemical",
    "extract_chemicals_from_text",
    "normalize_chemical_name",
]
