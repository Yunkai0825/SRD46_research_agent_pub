"""
JSON Schemas for SRD46 data structures.

This package contains the dataclass models for the four JSON classes:
- ReferencesEntry: shared references block (literature, authors, footnotes)
- LigandEntry: ligand.json schema
- CationEntry: cation.json (metal) schema  
- MetalLigandComplexEntry: metal_ligand_complex.json schema
"""
from __future__ import annotations

# Schemas
from .references_schema import ReferencesEntry
from .ligand_cards_schema import LigandEntry
from .metal_cards_schema import CationEntry
from .ligandmetal_cards_schema import MetalLigandComplexEntry

# Builder functions
from .references_schema import create_references_entry, create_references_entry_from_tables, create_references_entry_by_ligand_metal, build_reference_indexes
from .ligand_cards_schema import create_ligand_entry, load_ligand_entry_from_json
from .metal_cards_schema import create_cation_entry, load_cation_entry_from_json
from .ligandmetal_cards_schema import create_metal_ligand_complex_entry, load_metal_ligand_complex_entry_from_json

# Utilities
from ._utils import (
    MissingFieldTracker,
    DEFAULT_MISSING_TRACKER,
    get_missing_field_report,
    get_missing_field_report_text,
    _is_empty,
    _load_json_like,
)

__all__ = [
    # Schemas
    "ReferencesEntry",
    "LigandEntry", 
    "CationEntry",
    "MetalLigandComplexEntry",
    # Builder functions
    "create_references_entry",
    "create_references_entry_from_tables",
    "create_references_entry_by_ligand_metal",
    "build_reference_indexes",
    "create_ligand_entry",
    "load_ligand_entry_from_json",
    "create_cation_entry",
    "load_cation_entry_from_json",
    "create_metal_ligand_complex_entry",
    "load_metal_ligand_complex_entry_from_json",
    # Utilities
    "MissingFieldTracker",
    "DEFAULT_MISSING_TRACKER",
    "get_missing_field_report",
    "get_missing_field_report_text",
]
