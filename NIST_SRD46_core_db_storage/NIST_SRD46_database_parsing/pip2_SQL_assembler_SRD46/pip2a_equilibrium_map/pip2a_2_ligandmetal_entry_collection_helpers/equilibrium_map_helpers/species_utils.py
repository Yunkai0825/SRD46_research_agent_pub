"""
Species extraction utilities.

Handles parsing of equation_tree_json to extract species.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd


# =============================================================================
# JSON parsing utilities
# =============================================================================

def _safe_get_scalar(value: Any) -> Any:
    """Convert pandas Series or numpy array to scalar if single element."""
    if isinstance(value, pd.Series):
        if len(value) == 1:
            return value.iloc[0]
        return value.values[0] if len(value) > 0 else None
    elif isinstance(value, np.ndarray):
        if value.ndim == 0:
            return value.item()
        elif len(value) == 1:
            return value[0]
        return value[0] if len(value) > 0 else None
    return value


def _parse_json_safe(value: Any) -> Optional[Dict]:
    """Safely parse a JSON string or return dict if already parsed."""
    # Handle numpy arrays and pandas Series first
    if isinstance(value, (np.ndarray, pd.Series)):
        value = _safe_get_scalar(value)
    
    if pd.isna(value):
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


# =============================================================================
# Species extraction from equation tree
# =============================================================================

def extract_species_from_equation_tree(equation_tree: Dict) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """Extract LHS and RHS species from an equation_tree_json structure.
    
    The structure uses:
    - "denominator" for LHS (reactants) - what K is divided by
    - "numerator" for RHS (products) - what K multiplies
    
    Args:
        equation_tree: Parsed equation_tree_json dict
        
    Returns:
        Tuple of (lhs_species frozenset, rhs_species frozenset)
    """
    lhs_species: Set[str] = set()
    rhs_species: Set[str] = set()
    
    if not equation_tree:
        return frozenset(), frozenset()
    
    # Primary format: {"numerator": [...], "denominator": [...]}
    # numerator = products (RHS), denominator = reactants (LHS)
    if "numerator" in equation_tree or "denominator" in equation_tree:
        numerator = equation_tree.get("numerator", [])
        denominator = equation_tree.get("denominator", [])
        
        for item in denominator if denominator else []:
            species = _extract_species_from_item(item)
            lhs_species.update(species)
        
        for item in numerator if numerator else []:
            species = _extract_species_from_item(item)
            rhs_species.update(species)
        
        return frozenset(lhs_species), frozenset(rhs_species)
    
    # Alternative format 1: {"lhs": [...], "rhs": [...]}
    if "lhs" in equation_tree and "rhs" in equation_tree:
        lhs_data = equation_tree.get("lhs", [])
        rhs_data = equation_tree.get("rhs", [])
        
        for item in lhs_data if lhs_data else []:
            species = _extract_species_from_item(item)
            lhs_species.update(species)
        
        for item in rhs_data if rhs_data else []:
            species = _extract_species_from_item(item)
            rhs_species.update(species)
        
        return frozenset(lhs_species), frozenset(rhs_species)
    
    # Alternative format 2: {"reactants": [...], "products": [...]}
    if "reactants" in equation_tree or "products" in equation_tree:
        reactants = equation_tree.get("reactants", [])
        products = equation_tree.get("products", [])
        
        for item in reactants if reactants else []:
            species = _extract_species_from_item(item)
            lhs_species.update(species)
        
        for item in products if products else []:
            species = _extract_species_from_item(item)
            rhs_species.update(species)
        
        return frozenset(lhs_species), frozenset(rhs_species)
    
    # Alternative format 3: Direct species list {"species": [...]}
    if "species" in equation_tree:
        species_list = equation_tree.get("species", [])
        for item in species_list if species_list else []:
            species = _extract_species_from_item(item)
            # Put all in RHS if no side info
            rhs_species.update(species)
    
    return frozenset(lhs_species), frozenset(rhs_species)


def _extract_species_from_item(item: Any) -> Set[str]:
    """Extract species name(s) from a single item in the equation tree."""
    species: Set[str] = set()
    
    if isinstance(item, str):
        species.add(item.strip())
    elif isinstance(item, dict):
        # Try various keys for species name
        for key in ["species", "name", "symbol", "formula"]:
            if key in item:
                val = item[key]
                if isinstance(val, str):
                    species.add(val.strip())
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, str):
                            species.add(v.strip())
        
        # Also check for nested items
        if "items" in item:
            for sub_item in item["items"]:
                species.update(_extract_species_from_item(sub_item))
    elif isinstance(item, list):
        for sub_item in item:
            species.update(_extract_species_from_item(sub_item))
    
    return species


def extract_species_from_beta_definition(
    beta_row: Union[pd.Series, Dict],
    beta_id: Optional[int] = None,
) -> Tuple[FrozenSet[str], FrozenSet[str], FrozenSet[str]]:
    """Extract species from a beta definition row.
    
    Args:
        beta_row: Row from beta_definition_augmented DataFrame or dict
        beta_id: Optional beta ID for logging
        
    Returns:
        Tuple of (lhs_species, rhs_species, all_species) as frozensets
    """
    # Handle DataFrame row (when there are duplicates)
    if isinstance(beta_row, pd.DataFrame):
        beta_row = beta_row.iloc[0]
    
    # Try equation_tree_json first
    equation_tree_raw = None
    if isinstance(beta_row, dict):
        equation_tree_raw = beta_row.get("equation_tree_json")
    elif isinstance(beta_row, pd.Series):
        if "equation_tree_json" in beta_row.index:
            equation_tree_raw = beta_row["equation_tree_json"]
    
    equation_tree_raw = _safe_get_scalar(equation_tree_raw)
    equation_tree = _parse_json_safe(equation_tree_raw)
    
    if equation_tree:
        lhs, rhs = extract_species_from_equation_tree(equation_tree)
        return lhs, rhs, lhs | rhs
    
    # Fallback: try to parse from equation_python
    equation_python = None
    if isinstance(beta_row, dict):
        equation_python = beta_row.get("equation_python")
    elif isinstance(beta_row, pd.Series):
        if "equation_python" in beta_row.index:
            equation_python = beta_row["equation_python"]
    
    equation_python = _safe_get_scalar(equation_python)
    
    if equation_python and isinstance(equation_python, str):
        lhs, rhs = _parse_species_from_equation_string(equation_python)
        return lhs, rhs, lhs | rhs
    
    return frozenset(), frozenset(), frozenset()


def _parse_species_from_equation_string(equation: str) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """Parse species from a simple equation string like 'M + L = ML'."""
    lhs_species: Set[str] = set()
    rhs_species: Set[str] = set()
    
    # Split on common equation separators
    if "=" in equation:
        parts = equation.split("=", 1)
    elif "⇌" in equation:
        parts = equation.split("⇌", 1)
    elif "->" in equation:
        parts = equation.split("->", 1)
    elif "→" in equation:
        parts = equation.split("→", 1)
    else:
        # No separator found, can't parse
        return frozenset(), frozenset()
    
    lhs_str = parts[0].strip()
    rhs_str = parts[1].strip() if len(parts) > 1 else ""
    
    # Parse each side: split on + and extract species
    for term in lhs_str.split("+"):
        species = _clean_species_term(term)
        if species:
            lhs_species.add(species)
    
    for term in rhs_str.split("+"):
        species = _clean_species_term(term)
        if species:
            rhs_species.add(species)
    
    return frozenset(lhs_species), frozenset(rhs_species)


def _clean_species_term(term: str) -> Optional[str]:
    """Clean a species term, removing coefficients."""
    term = term.strip()
    if not term:
        return None
    
    # Remove leading coefficients (digits)
    match = re.match(r'^(\d+\s*)?(.+)$', term)
    if match:
        species = match.group(2).strip()
        if species:
            return species
    
    return term if term else None


__all__ = [
    # JSON utilities
    "_safe_get_scalar",
    "_parse_json_safe",
    # Species extraction
    "extract_species_from_equation_tree",
    "extract_species_from_beta_definition",
]
