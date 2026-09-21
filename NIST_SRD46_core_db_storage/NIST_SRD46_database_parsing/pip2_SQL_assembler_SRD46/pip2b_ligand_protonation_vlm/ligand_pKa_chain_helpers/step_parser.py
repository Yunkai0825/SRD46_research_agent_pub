"""
Step Parser

Parses HxL stages from species strings and derives protonation steps.
Handles various formats:
- [L], [HL], [H2L], [H-1L], [H-2L] (simple HxL)
- [M3H17L6] (composite with embedded HxL)
- [H] or [H]^+ (free proton)
"""
from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# =============================================================================
# Regex patterns for stage parsing
# =============================================================================

# Simple HxL pattern: [HnL] where n can be '', '1', '2', '-1', '-2', etc.
RE_HXL_SIMPLE = re.compile(r"""
    ^\[
      H([+-]?\d*)     # stage digits (may be '', '+1', '-2', '0', etc.)
      \s*L(?:[^]]*)?  # L plus optional decorations inside bracket
    \]
    (?:\^\s*[+-]?\d+)?  # optional external charge
    $""", re.VERBOSE)

# Bare ligand [L] pattern (stage = 0)
RE_L_BARE = re.compile(r"""
    ^\[
      L(?:[^]]*)?     # L plus optional decorations
    \]
    (?:\^\s*[+-]?\d+)?  # optional external charge
    $""", re.VERBOSE)

# Free proton [H] or [H]^+ pattern
RE_H_FREE = re.compile(r"^\[H\](?:\^\s*[+-]?\d*)?$")

# Composite pattern for HnLm inside larger species
RE_HL_COMPOSITE = re.compile(r"H\s*([+-]?\d*)\s*L", re.IGNORECASE)

# Pattern to find any HxL reference
RE_HXL_ANY = re.compile(r"H([+-]?\d*)L")


# =============================================================================
# Stage parsing functions
# =============================================================================

def parse_stage_from_species(species: str) -> Optional[int]:
    """Parse protonation stage from a species string.
    
    Handles formats:
    - [L] -> 0
    - [HL] -> 1
    - [H2L] -> 2
    - [H-1L] -> -1
    - [M3H17L6] -> 17 (composite)
    
    Args:
        species: Species string like "[HL]", "[H2L]", "[L]"
        
    Returns:
        Integer stage or None if not a protonation species
    """
    if not species:
        return None
    
    species = species.strip()
    
    # Try simple HxL pattern first
    m = RE_HXL_SIMPLE.match(species)
    if m:
        stage_str = m.group(1)
        if stage_str == "" or stage_str == "+":
            return 1
        elif stage_str == "-":
            return -1
        else:
            try:
                return int(stage_str.replace("+", ""))
            except ValueError:
                return None
    
    # Try bare [L] pattern (stage = 0)
    if RE_L_BARE.match(species):
        return 0
    
    # Try composite pattern (fallback)
    return parse_stage_from_composite(species)


def parse_stage_from_composite(species: str) -> Optional[int]:
    """Parse stage from composite species like [M3H17L6].
    
    Args:
        species: Species string
        
    Returns:
        Integer stage or None if not found
    """
    if not species:
        return None
    
    # Look for HnL pattern inside the species
    m = RE_HL_COMPOSITE.search(species)
    if m:
        stage_str = m.group(1)
        if stage_str == "" or stage_str == "+":
            return 1
        elif stage_str == "-":
            return -1
        else:
            try:
                return int(stage_str.replace("+", ""))
            except ValueError:
                return None
    
    # Check if it's just [L...] without H
    if "[L" in species.upper() and "H" not in species.upper():
        return 0
    
    return None


def is_free_proton(species: str) -> bool:
    """Check if species is a free proton [H] or [H]^+.
    
    Args:
        species: Species string
        
    Returns:
        True if free proton
    """
    if not species:
        return False
    return RE_H_FREE.match(species.strip()) is not None


def stage_to_token(stage: Optional[int]) -> str:
    """Convert stage integer to HxL token string.
    
    Args:
        stage: Integer stage (0, 1, 2, -1, etc.)
        
    Returns:
        Token string like "L", "HL", "H2L", "H-1L"
    """
    if stage is None:
        return "?"
    if stage == 0:
        return "L"
    if stage == 1:
        return "HL"
    if stage >= 2:
        return f"H{stage}L"
    if stage == -1:
        return "H-1L"
    return f"H{stage}L"


def edge_to_label(from_stage: int, to_stage: int) -> str:
    """Create edge label from stages.
    
    Args:
        from_stage: Starting stage (reactant side)
        to_stage: Ending stage (product side)
        
    Returns:
        Label like "L->HL", "HL->H2L"
    """
    return f"{stage_to_token(from_stage)}->{stage_to_token(to_stage)}"


# =============================================================================
# Step derivation from nodes
# =============================================================================

def extract_stages_from_species_set(species_set: FrozenSet[str]) -> Set[int]:
    """Extract all protonation stages from a set of species.
    
    Args:
        species_set: Set of species strings
        
    Returns:
        Set of integer stages found
    """
    stages = set()
    for sp in species_set:
        stage = parse_stage_from_species(sp)
        if stage is not None:
            stages.add(stage)
    return stages


def count_free_protons(species_set: FrozenSet[str]) -> int:
    """Count free protons [H] in a species set.
    
    Args:
        species_set: Set of species strings
        
    Returns:
        Number of free protons
    """
    count = 0
    for sp in species_set:
        if is_free_proton(sp):
            count += 1
    return count


def derive_step_from_node(
    lhs_species: FrozenSet[str],
    rhs_species: FrozenSet[str],
) -> Tuple[Optional[int], Optional[int], Dict]:
    """Derive protonation step from node species (LHS and RHS).
    
    The equilibrium is: LHS (denominator/reactants) -> RHS (numerator/products)
    For a valid protonation step:
    - Product side should have HxL species
    - Reactant side should have Hy-nL species + n free [H]
    - The difference (x - (y-n)) should equal n
    
    Args:
        lhs_species: LHS (reactant/denominator) species set
        rhs_species: RHS (product/numerator) species set
        
    Returns:
        Tuple of (from_stage, to_stage, metadata)
        metadata contains: {"ok": bool, "reason": str, "protons": int}
    """
    meta = {"ok": False, "reason": "", "protons": 0}
    
    # Extract stages from both sides
    lhs_stages = extract_stages_from_species_set(lhs_species)
    rhs_stages = extract_stages_from_species_set(rhs_species)
    
    # Count free protons on LHS
    n_protons = count_free_protons(lhs_species)
    meta["protons"] = n_protons
    
    # Need exactly one HxL stage on each side for a clean step
    if len(rhs_stages) != 1:
        meta["reason"] = f"rhs_stages={len(rhs_stages)}"
        return None, None, meta
    
    if len(lhs_stages) != 1:
        meta["reason"] = f"lhs_stages={len(lhs_stages)}"
        return None, None, meta
    
    to_stage = list(rhs_stages)[0]
    from_stage = list(lhs_stages)[0]
    
    # For a valid step: to_stage - from_stage should equal n_protons
    expected_diff = to_stage - from_stage
    
    if n_protons == 0:
        meta["reason"] = "no_protons_in_lhs"
        return from_stage, to_stage, meta
    
    if expected_diff != n_protons:
        meta["reason"] = f"diff_mismatch: {expected_diff} != {n_protons}"
        return from_stage, to_stage, meta
    
    meta["ok"] = True
    meta["reason"] = "valid"
    return from_stage, to_stage, meta


def derive_step_from_node_pair(
    node1_lhs: FrozenSet[str],
    node1_rhs: FrozenSet[str],
    node2_lhs: FrozenSet[str],
    node2_rhs: FrozenSet[str],
) -> Tuple[Optional[int], Optional[int], Dict]:
    """Derive step from two connected nodes (for edge-based analysis).
    
    This is a fallback when single-node analysis doesn't work.
    Looks for shared species and derives the step difference.
    """
    # For now, just use node1 for step derivation
    return derive_step_from_node(node1_lhs, node1_rhs)
