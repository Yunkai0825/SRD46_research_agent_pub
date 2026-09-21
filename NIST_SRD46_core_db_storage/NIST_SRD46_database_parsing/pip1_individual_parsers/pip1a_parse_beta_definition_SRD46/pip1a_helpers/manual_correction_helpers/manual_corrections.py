"""
Manual corrections for beta_definition entries that cannot be parsed by the standard pipeline.

The data no longer lives here. Every hand-made chemistry decision of the SRD46 chain is
declared once in ``srd46_pipeline/manual_rules.py`` (single register, evidence strings,
``validate()``); this module re-exports the two tables the parser consumes, in their
original shape, so the parser code did not have to change:

    MANUAL_CORRECTIONS  <- manual_rules.BETA_EQUATION_CORRECTIONS  (rule BETA-03)
    MANUAL_NAME_FIXES   <- manual_rules.BETA_NAME_FIXES            (rule BETA-02)

Format (unchanged):
    MANUAL_CORRECTIONS = {
        beta_definitionID: {
            "equation_sides": {
                "numerator": [["[species]", coefficient], ...],
                "denominator": [["[species]", coefficient], ...]
            },
            "beta_eq_str_python_final": "human readable equation string",
            "notes": "explanation of the correction"
        }
    }
    MANUAL_NAME_FIXES = {beta_definitionID: {"raw": <exact raw string>, "fixed": <corrected string>, "notes": <why>}}

IMPORTANT: For solid oxide dissolution where L=OH⁻, use [OH] in equation_sides
instead of [L] to ensure the parser can verify element balance.
(The parser treats [L] as abstract ligand, but [OH] as H:1+O:1)

The equation_sides follows the K = products/reactants convention:
    K = [numerator species] / [denominator species]

For formation constants (β):   numerator = product complex, denominator = reactant species (M, L, H, ...)
For dissolution constants (Ksp): numerator = dissolved species (M, L, ...), denominator = solid phase

Running this file directly still validates the (re-exported) corrections.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from srd46_pipeline import manual_rules as _mr
except ImportError:  # standalone use from inside the parser package: project root = 4 levels up
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from srd46_pipeline import manual_rules as _mr

# =============================================================================
# MANUAL CORRECTIONS DICTIONARY (rule BETA-03, re-exported)
# =============================================================================

MANUAL_CORRECTIONS: dict[int, dict] = _mr.beta_equation_corrections_legacy()

# =============================================================================
# MANUAL RAW-NAME FIXES (rule BETA-02, re-exported)
# =============================================================================
# Typos and ill-formed definitions in `beta_definition.name_beta_definition`; applied to
# `name_beta_definition_fixed`, guarded by the exact raw string so a changed upstream export
# is reported instead of silently patched.

MANUAL_NAME_FIXES: dict[int, dict[str, str]] = _mr.beta_name_fixes_legacy()


def get_manual_name_fixes() -> dict[int, dict[str, str]]:
    """Return a copy of MANUAL_NAME_FIXES (raw-name typo patches)."""
    return dict(MANUAL_NAME_FIXES)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_manual_correction(beta_id: int) -> dict | None:
    """
    Get manual correction for a specific beta_definitionID.
    
    Returns:
        dict with equation_sides and beta_eq_str_python_final, or None if no correction exists
    """
    return MANUAL_CORRECTIONS.get(beta_id, None)


def has_manual_correction(beta_id: int) -> bool:
    """Check if a manual correction exists for this beta_definitionID."""
    return beta_id in MANUAL_CORRECTIONS


def get_all_correctable_ids() -> list[int]:
    """Get list of all beta_definitionIDs that have manual corrections."""
    return list(MANUAL_CORRECTIONS.keys())


def get_valid_corrections() -> dict[int, dict]:
    """Get all corrections from MANUAL_CORRECTIONS."""
    return dict(MANUAL_CORRECTIONS)


# =============================================================================
# VALIDATION FUNCTION
# =============================================================================

def validate_correction(beta_id: int, correction: dict) -> tuple[bool, str]:
    """
    Validate a manual correction entry.
    
    Checks:
    - equation_sides has numerator and denominator
    - All species entries are [name, coefficient] pairs
    - Coefficients are positive numbers
    
    Returns:
        (is_valid, error_message)
    """
    if correction.get("equation_sides") is None:
        return True, "Explicitly marked as invalid entry"
    
    eq_sides = correction["equation_sides"]
    
    if "numerator" not in eq_sides:
        return False, f"β={beta_id}: Missing 'numerator' in equation_sides"
    
    if "denominator" not in eq_sides:
        return False, f"β={beta_id}: Missing 'denominator' in equation_sides"
    
    for side_name in ["numerator", "denominator"]:
        for entry in eq_sides[side_name]:
            if not isinstance(entry, list) or len(entry) != 2:
                return False, f"β={beta_id}: {side_name} entry {entry} is not [species, coeff] format"
            species, coeff = entry
            if not isinstance(species, str):
                return False, f"β={beta_id}: Species '{species}' is not a string"
            if not isinstance(coeff, (int, float)) or coeff <= 0:
                return False, f"β={beta_id}: Coefficient {coeff} must be positive number"
    
    return True, "OK"


def validate_all_corrections() -> list[tuple[int, str]]:
    """Validate all manual corrections and return list of errors."""
    errors = []
    for beta_id, correction in MANUAL_CORRECTIONS.items():
        is_valid, msg = validate_correction(beta_id, correction)
        if not is_valid:
            errors.append((beta_id, msg))
    return errors


def verify_balance_all() -> list[tuple[int, dict]]:
    """
    Verify that all valid corrections produce balanced equations.
    Returns list of (beta_id, balance_dict) for unbalanced entries.
    """
    # Import here to avoid circular dependency
    from pip1a_helpers import balance_from_sides
    
    unbalanced = []
    for beta_id, correction in MANUAL_CORRECTIONS.items():
        eq_sides = correction.get("equation_sides")
        if eq_sides is None:
            continue  # Skip invalid entries
        
        balance = balance_from_sides(eq_sides)
        if not all(abs(v) < 1e-9 for v in balance.values()):
            unbalanced.append((beta_id, balance))
    
    return unbalanced


# =============================================================================
# MAIN - Run validation when executed directly
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("MANUAL CORRECTIONS VALIDATION")
    print("=" * 70)
    print()
    
    total = len(MANUAL_CORRECTIONS)
    valid_entries = len(get_valid_corrections())
    invalid_entries = total - valid_entries
    
    print(f"Total entries:   {total}")
    print(f"Valid entries:   {valid_entries}")
    print(f"Invalid/skip:    {invalid_entries}")
    print()
    
    # Structural validation
    errors = validate_all_corrections()
    if errors:
        print("STRUCTURAL ERRORS FOUND:")
        for beta_id, msg in errors:
            print(f"  β={beta_id}: {msg}")
    else:
        print("✓ All corrections structurally valid")
    
    # Balance verification (requires pip1a_helpers)
    print()
    print("Verifying balance with parser...")
    try:
        unbalanced = verify_balance_all()
        if unbalanced:
            print(f"UNBALANCED ({len(unbalanced)}):")
            for beta_id, balance in unbalanced:
                non_zero = {k: v for k, v in balance.items() if abs(v) > 1e-9}
                print(f"  β={beta_id}: {non_zero}")
        else:
            print(f"✓ All {valid_entries} valid corrections produce balanced equations")
    except ImportError:
        print("  (Cannot import pip1a_helpers - run from correct directory)")
    
    print()
    print("Corrections by verdict (from srd46_pipeline.manual_rules):")
    print("-" * 40)
    for verdict in (_mr.BALANCED, _mr.UNBALANCED):
        ids = [b for b, c in _mr.BETA_EQUATION_CORRECTIONS.items() if c.verdict == verdict]
        print(f"  {verdict}: {len(ids)} entries {ids}")
    print(f"  superseded by BETA-02 text repairs: {sorted(_mr.BETA03_SUPERSEDED_BY_BETA02)}")
