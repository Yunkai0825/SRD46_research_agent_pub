"""
CationEntry schema - cation.json (metal) dataclass model.

This dataclass models the cation/metal entry from the SRD46 database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ._utils import MissingFieldTracker, DEFAULT_MISSING_TRACKER, _is_empty, _load_json_like


@dataclass
class CationEntry:
    """Cation (metal) entry schema for cation.json."""
    
    metal_id: int
    metal_name_SRD: str
    symbol_pure: Optional[str] = None
    charge: Optional[int] = None  # Ionic charge (e.g., 2 for Cu2+)
    charge_str: Optional[str] = None  # Charge string (e.g., "2+", "3+")
    SMILES: Optional[str] = None
    InChi: Optional[str] = None
    InChiKey: Optional[str] = None
    parts_used: Optional[List[str]] = None
    stoichiometry: Optional[Dict[str, int]] = None  # Element stoichiometry
    is_simple_ion: Optional[bool] = None  # True for simple ions like Cu2+, Na+
    is_organometallic: Optional[bool] = None  # True for organometallic species
    primary_metal: Optional[str] = None  # Primary metal element symbol
    formula_components: Optional[Dict[str, int]] = None  # Element counts as dict
    parse_notes: Optional[str] = None


# =============================================================================
# Builder functions
# =============================================================================

def create_cation_entry(data: Dict[str, Any] | None = None, tracker: MissingFieldTracker | None = None) -> CationEntry:
    """Create a CationEntry from a dictionary of cation/metal data."""
    tracker = tracker or DEFAULT_MISSING_TRACKER
    data = data or {}

    metal_id = data.get("metal_id")
    if _is_empty(metal_id):
        tracker.mark_missing("CationEntry", "metal_id")
        metal_id = 0
    metal_name = data.get("metal_name_SRD")
    if _is_empty(metal_name):
        tracker.mark_missing("CationEntry", "metal_name_SRD")
        metal_name = ""

    # Parse charge as int if possible
    charge_val = data.get("charge")
    charge_int = None
    if not _is_empty(charge_val):
        try:
            charge_int = int(float(str(charge_val)))
        except (ValueError, TypeError):
            charge_int = None

    # Parse parts_used from JSON string if needed
    parts_used = data.get("parts_used")
    if isinstance(parts_used, str):
        parts_used = _load_json_like(parts_used)
    if not isinstance(parts_used, list):
        parts_used = None

    # Parse stoichiometry from JSON string if needed
    stoichiometry = data.get("stoichiometry")
    if isinstance(stoichiometry, str) and stoichiometry.strip():
        stoichiometry = _load_json_like(stoichiometry)
    if not isinstance(stoichiometry, dict):
        stoichiometry = None

    # Parse boolean fields
    def _to_bool(val) -> Optional[bool]:
        if val is None or val == "" or val == "\\N":
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    # Parse formula_components from JSON string if needed
    formula_components = data.get("formula_components")
    if isinstance(formula_components, str):
        formula_components = _load_json_like(formula_components)
    if not isinstance(formula_components, dict):
        formula_components = None

    entry = CationEntry(
        metal_id=int(metal_id),
        metal_name_SRD=str(metal_name),
        symbol_pure=(None if _is_empty(data.get("symbol_pure")) else str(data.get("symbol_pure"))),
        charge=charge_int,
        charge_str=(None if _is_empty(data.get("charge_str")) else str(data.get("charge_str"))),
        SMILES=(None if _is_empty(data.get("SMILES")) else str(data.get("SMILES"))),
        InChi=(None if _is_empty(data.get("InChi")) else str(data.get("InChi"))),
        InChiKey=(None if _is_empty(data.get("InChiKey")) else str(data.get("InChiKey"))),
        parts_used=parts_used,
        stoichiometry=stoichiometry,
        is_simple_ion=_to_bool(data.get("is_simple_ion")),
        is_organometallic=_to_bool(data.get("is_organometallic")),
        primary_metal=(None if _is_empty(data.get("primary_metal")) else str(data.get("primary_metal"))),
        formula_components=formula_components,
        parse_notes=(None if _is_empty(data.get("parse_notes")) else str(data.get("parse_notes"))),
    )
    return entry


def load_cation_entry_from_json(source: Any, tracker: MissingFieldTracker | None = None) -> CationEntry:
    """Load a CationEntry from a JSON file path, JSON string, dict, or CationEntry."""
    tracker = tracker or DEFAULT_MISSING_TRACKER
    if isinstance(source, CationEntry):
        return source
    obj = _load_json_like(source)
    if isinstance(obj, dict):
        return create_cation_entry(obj, tracker)
    raise TypeError("Unsupported source for load_cation_entry_from_json: expected file path, JSON string, dict, or CationEntry")


__all__ = [
    "CationEntry",
    "create_cation_entry",
    "load_cation_entry_from_json",
]
