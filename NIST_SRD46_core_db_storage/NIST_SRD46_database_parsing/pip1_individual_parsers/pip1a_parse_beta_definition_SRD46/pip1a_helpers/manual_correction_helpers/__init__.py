"""
manual_correction_helpers - Tools for manual correction of beta definitions.

This package provides utilities for:
1. Testing proposed manual corrections against the standard parser
2. Exploring how species labels are parsed
3. Looking up ligand/metal associations for beta definitions
4. Managing the MANUAL_CORRECTIONS dictionary

Key modules:
    - manual_corrections: The dictionary of manual corrections
    - test_manual_correction: Testing tool for validating corrections
    - DEBUG_probe_beta_ligand_metal: Lookup ligand/metal associations
"""

from .manual_corrections import (
    MANUAL_CORRECTIONS,
    MANUAL_NAME_FIXES,
    get_manual_correction,
    get_manual_name_fixes,
    has_manual_correction,
    get_all_correctable_ids,
    get_valid_corrections,
    validate_correction,
    validate_all_corrections,
)

__all__ = [
    "MANUAL_CORRECTIONS",
    "MANUAL_NAME_FIXES",
    "get_manual_name_fixes",
    "get_manual_correction",
    "has_manual_correction",
    "get_all_correctable_ids",
    "get_valid_corrections",
    "validate_correction",
    "validate_all_corrections",
]
