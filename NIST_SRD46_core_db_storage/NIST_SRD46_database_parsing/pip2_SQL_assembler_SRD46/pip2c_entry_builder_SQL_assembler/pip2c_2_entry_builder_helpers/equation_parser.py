"""Equation tree parsing helpers for complex entries.

Functions to parse equation_tree_json and extract species/presence flags.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional


def maybe_json(s: Any):
    """Parse JSON string or return as-is if already parsed."""
    if isinstance(s, (dict, list)):
        return s
    if isinstance(s, str):
        t = s.strip()
        if t.startswith("{") or t.startswith("["):
            try:
                return json.loads(t)
            except Exception:
                return s
    return s


def extract_species_from_tree(tree_side) -> list[dict[str, Any]]:
    """Extract species list from equation_tree_json structure.
    
    The tree structure contains either a list of species dicts or 
    a dict with 'numerator'/'denominator' keys.
    Each species has: species, power, components, elements_total, phase, species_clean
    """
    out = []
    if isinstance(tree_side, list):
        for item in tree_side:
            if isinstance(item, dict):
                species_name = item.get("species") or item.get("species_clean")
                power = item.get("power", 1.0)
                if species_name:
                    out.append({"species": str(species_name), "power": float(power) if power else 1.0})
            elif isinstance(item, list) and len(item) >= 1:
                # Old format: [species_name, power]
                out.append({"species": str(item[0]), "power": float(item[1]) if len(item) > 1 else 1.0})
    return out


def _side_has(labels: list, token: str) -> bool:
    """Check if labels list contains a specific token type."""
    if not labels:
        return False
    if token == "[H]":
        return any(sp.get("species") == "[H]" for sp in labels)
    if token == "ligand":
        # Strict full-token match for bracketed HxLy-like forms
        full_pat = re.compile(r"^\[(?:L(?:[-+]?\d*\.?\d*)|H[-+]?\d*\.?\d*L(?:[-+]?\d*\.?\d*)?)\]$", re.IGNORECASE)
        return any(isinstance(sp.get("species"), str) and bool(full_pat.match(sp.get("species"))) for sp in labels)
    if token == "metal":
        return any(sp.get("species") == "[M]" for sp in labels)
    return False


def presence_from_labels(labels_left: list, labels_right: list) -> dict[str, str]:
    """Compute presence flags from LHS and RHS species labels."""
    def to_flag(has_l, has_r):
        if has_l and has_r:
            return "both"
        if has_l:
            return "lhs_only"
        if has_r:
            return "rhs_only"
        return "none"
    
    return {
        "proton_flag": to_flag(_side_has(labels_left, "[H]"), _side_has(labels_right, "[H]")),
        "ligand_flag": to_flag(_side_has(labels_left, "ligand"), _side_has(labels_right, "ligand")),
        "metal_flag": to_flag(_side_has(labels_left, "metal"), _side_has(labels_right, "metal")),
    }


def extract_hxl_involved(lhs_species: list, rhs_species: list) -> Optional[list[str]]:
    """Extract HxL species tokens from both sides of the equation."""
    labs = [sp["species"] for sp in (lhs_species or [])] + [sp["species"] for sp in (rhs_species or [])]
    try:
        full_pat = re.compile(r"^\[(?:L(?:[-+]?\d*\.?\d*)|H[-+]?\d*\.?\d*L(?:[-+]?\d*\.?\d*)?)\]$", re.IGNORECASE)
        hxl_list = [lbl for lbl in labs if isinstance(lbl, str) and full_pat.match(lbl)]
        return hxl_list or None
    except Exception:
        return None


def parse_equation_tree(eq_tree_raw: Any, beta_fix_row: dict) -> dict[str, Any]:
    """Parse equation_tree_json and return LHS/RHS species plus derived fields.
    
    Returns dict with:
        - lhs_species: list of species on left side
        - rhs_species: list of species on right side  
        - presence_flags: proton/ligand/metal presence
        - hxl_involved: list of HxL tokens found
        - eq_tree: parsed tree object
    """
    from .csv_io_helpers import pick_any
    
    eq_tree = maybe_json(eq_tree_raw or pick_any(beta_fix_row, ["equation_tree_json", "beta_eq_tree_json"]))
    
    lhs_species = None
    rhs_species = None
    presence_flags = {"proton_flag": "none", "ligand_flag": "none", "metal_flag": "none"}
    hxl_involved: Optional[list[str]] = None
    
    if isinstance(eq_tree, dict):
        rhs_species = extract_species_from_tree(eq_tree.get("numerator")) or None
        lhs_species = extract_species_from_tree(eq_tree.get("denominator")) or None
    
    if lhs_species or rhs_species:
        presence_flags = presence_from_labels(lhs_species or [], rhs_species or [])
        hxl_involved = extract_hxl_involved(lhs_species or [], rhs_species or [])
    
    return {
        "lhs_species": lhs_species,
        "rhs_species": rhs_species,
        "presence_flags": presence_flags,
        "hxl_involved": hxl_involved,
        "eq_tree": eq_tree,
    }
