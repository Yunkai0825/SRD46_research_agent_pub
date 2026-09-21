"""
HOL auto-correction for polymetal species (pip-1 logic).
Uses POLYMETAL_HOL_TOKENS for direct HOL basis count lookup.
"""
import re
from typing import Dict, Optional

from .constants import POLYMETAL_HOL_TOKENS, POLYMETAL_TOKEN_PATTERN, _SPECIAL_HOL_GROUP_RE, _mr

# ═══════════════════════════════════════════════════════════════════════════════
# POLYMETAL HOL LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════
def apply_polymetal_hol_rule(species: str) -> Optional[Dict[str, float]]:
    """
    Look up polymetal species in POLYMETAL_HOL_TOKENS and return HOL basis counts.
    Returns dict like {'H': 0, 'O': -4, 'L': 7} or None if no match.
    
    Example:
        apply_polymetal_hol_rule("Mo7O24") → {'H': 0, 'O': -4, 'L': 7}
        apply_polymetal_hol_rule("HV10O28") → {'H': 1, 'O': -12, 'L': 10}
    """
    # Try exact match first (case-insensitive)
    species_clean = species.strip()
    for key, hol in POLYMETAL_HOL_TOKENS.items():
        if key.lower() == species_clean.lower():
            return dict(hol)
    
    # Try regex match for species containing the pattern
    for key, hol in POLYMETAL_HOL_TOKENS.items():
        if re.search(re.escape(key), species, re.IGNORECASE):
            return dict(hol)
    
    return None


def get_polymetal_hol_counts(species: str) -> Optional[Dict[str, float]]:
    """
    Extract HOL counts for a polymetal species.
    This is the main entry point for correcting species in equations.
    
    Returns:
        Dict with 'H', 'O', 'L' keys (values can be negative for O)
        None if species is not a recognized polymetal cluster
    """
    return apply_polymetal_hol_rule(species)


def fix_hol_for_polymetal(token_pairs: list, metal_symbol: str = "") -> list:
    """
    Correct HOL for polymetal species in token pairs.
    token_pairs: list of (species, power) tuples
    Returns list of (species, power, hol_dict or None) tuples.
    """
    out = []
    for spec, power in token_pairs:
        hol_fix = apply_polymetal_hol_rule(spec)
        if hol_fix:
            out.append((spec, power, hol_fix))
        else:
            out.append((spec, power, None))
    return out


def detect_polymetal_cluster(species: str) -> Optional[str]:
    """
    Detect if species contains a known polymetal cluster.
    Returns the matched cluster formula or None.
    """
    for key in POLYMETAL_HOL_TOKENS.keys():
        if re.search(re.escape(key), species, re.IGNORECASE):
            return key
    return None


def species_needs_hol_correction(species: str) -> bool:
    """Check if species needs HOL correction (is a polymetal cluster)."""
    return detect_polymetal_cluster(species) is not None


def preprocess_beta_definition(raw_str: str) -> str:
    """
    Preprocess beta_definition string before parsing.
    - Normalize whitespace
    - Fix common OCR/encoding errors
    """
    if not isinstance(raw_str, str):
        return str(raw_str) if raw_str is not None else ""
    
    s = raw_str.strip()
    # Normalize spaces
    s = re.sub(r'\s+', ' ', s)
    # Fix common encoding issues (rule BETA-02, srd46_pipeline.manual_rules.BETA02_TEXT_REPLACEMENTS)
    for bad, good in _mr.BETA02_TEXT_REPLACEMENTS:
        s = s.replace(bad, good)
    return s


def correct_hol_in_equation(sides: dict, metal_symbol: str = "") -> dict:
    """
    Apply HOL corrections to both sides of equation.
    
    For each species that matches a polymetal token, the HOL basis counts
    are available via apply_polymetal_hol_rule() for balance computation.
    
    This function annotates the sides dict with correction info.
    Returns corrected sides dict with 'hol_corrections' metadata.
    """
    from copy import deepcopy
    corrected = deepcopy(sides)
    corrections = []
    
    for side in ("numerator", "denominator"):
        for spec, power in corrected.get(side, []):
            hol_fix = apply_polymetal_hol_rule(spec)
            if hol_fix:
                corrections.append({
                    "side": side,
                    "species": spec,
                    "power": power,
                    "hol_basis": hol_fix,
                })
    
    corrected["hol_corrections"] = corrections
    return corrected
