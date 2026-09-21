"""
Filtering and deduplication utilities for equilibrium map building.

Handles:
- Constant type filtering (K only)
- Soft temperature and ionic strength range filters
- Duplicate entry handling (same beta/metal/ligand)
- Condition popularity analysis for iterative building
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from .data_structures import (
    CONSTANT_TYPE_K,
    CONSTANT_TYPE_NAMES,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMP_TOLERANCE,
    DEFAULT_IONIC_STRENGTH,
    DEFAULT_IONIC_TOLERANCE,
    ConditionBin,
    EquilibriumNode,
)
from .species_utils import _safe_get_scalar


# =============================================================================
# Constant type filtering
# =============================================================================

def filter_by_constant_type(
    df: pd.DataFrame,
    constant_type: int = CONSTANT_TYPE_K,
    constant_type_col: str = "constanttypNr",
) -> pd.DataFrame:
    """Filter entries to only include specified constant type.
    
    Args:
        df: DataFrame with entries
        constant_type: Constant type to keep (default: 3 for K)
        constant_type_col: Column name for constant type
        
    Returns:
        Filtered DataFrame
    """
    if constant_type_col not in df.columns:
        return df
    
    mask = df[constant_type_col] == constant_type
    return df[mask].copy()


# =============================================================================
# Soft condition filters (range-based)
# =============================================================================

def apply_soft_temperature_filter(
    df: pd.DataFrame,
    target_temp: float = DEFAULT_TEMPERATURE,
    tolerance: float = DEFAULT_TEMP_TOLERANCE,
    temp_col: str = "temperature",
) -> pd.DataFrame:
    """Apply soft temperature filter: keep entries within target ± tolerance.
    
    Null temperatures are kept (will be handled by deduplication).
    
    Args:
        df: DataFrame with entries
        target_temp: Target temperature (°C)
        tolerance: Tolerance (±°C)
        temp_col: Column name for temperature
        
    Returns:
        Filtered DataFrame
    """
    if temp_col not in df.columns:
        return df
    
    temp_min = target_temp - tolerance
    temp_max = target_temp + tolerance
    
    # Convert temperature column to numeric (coerce errors to NaN)
    temp_numeric = pd.to_numeric(df[temp_col], errors='coerce')
    
    # Keep entries where temperature is null OR within range
    mask = temp_numeric.isna() | ((temp_numeric >= temp_min) & (temp_numeric <= temp_max))
    return df[mask].copy()


def apply_soft_ionic_filter(
    df: pd.DataFrame,
    target_ionic: float = DEFAULT_IONIC_STRENGTH,
    tolerance: float = DEFAULT_IONIC_TOLERANCE,
    ionic_col: str = "ionicstrength",
) -> pd.DataFrame:
    """Apply soft ionic strength filter: keep entries within target ± tolerance.
    
    Null ionic strengths are kept (will be handled by deduplication).
    
    Args:
        df: DataFrame with entries
        target_ionic: Target ionic strength
        tolerance: Tolerance (±)
        ionic_col: Column name for ionic strength
        
    Returns:
        Filtered DataFrame
    """
    if ionic_col not in df.columns:
        return df
    
    ionic_min = target_ionic - tolerance
    ionic_max = target_ionic + tolerance
    
    # Convert ionic strength column to numeric (coerce errors to NaN)
    ionic_numeric = pd.to_numeric(df[ionic_col], errors='coerce')
    
    # Keep entries where ionic strength is null OR within range
    mask = ionic_numeric.isna() | ((ionic_numeric >= ionic_min) & (ionic_numeric <= ionic_max))
    return df[mask].copy()


def apply_combined_soft_filter(
    df: pd.DataFrame,
    target_temp: float = DEFAULT_TEMPERATURE,
    temp_tolerance: float = DEFAULT_TEMP_TOLERANCE,
    target_ionic: float = DEFAULT_IONIC_STRENGTH,
    ionic_tolerance: float = DEFAULT_IONIC_TOLERANCE,
    temp_col: str = "temperature",
    ionic_col: str = "ionicstrength",
) -> pd.DataFrame:
    """Apply both temperature and ionic strength soft filters.
    
    Args:
        df: DataFrame with entries
        target_temp: Target temperature (°C)
        temp_tolerance: Temperature tolerance (±°C)
        target_ionic: Target ionic strength
        ionic_tolerance: Ionic strength tolerance (±)
        temp_col: Column name for temperature
        ionic_col: Column name for ionic strength
        
    Returns:
        Filtered DataFrame
    """
    df = apply_soft_temperature_filter(df, target_temp, temp_tolerance, temp_col)
    df = apply_soft_ionic_filter(df, target_ionic, ionic_tolerance, ionic_col)
    return df


# =============================================================================
# Duplicate handling
# =============================================================================

def calculate_condition_distance(
    row: pd.Series,
    target_temp: float = DEFAULT_TEMPERATURE,
    target_ionic: float = DEFAULT_IONIC_STRENGTH,
    temp_weight: float = 1.0,
    ionic_weight: float = 10.0,
    temp_col: str = "temperature",
    ionic_col: str = "ionicstrength",
) -> float:
    """Calculate distance from target conditions for a single row.
    
    Lower distance is better.
    """
    distance = 0.0
    
    temp_val = row.get(temp_col) if isinstance(row, dict) else row[temp_col] if temp_col in row.index else None
    ionic_val = row.get(ionic_col) if isinstance(row, dict) else row[ionic_col] if ionic_col in row.index else None
    
    temp_val = _safe_get_scalar(temp_val)
    ionic_val = _safe_get_scalar(ionic_val)
    
    # Temperature distance
    if temp_val is not None and not pd.isna(temp_val):
        distance += temp_weight * abs(float(temp_val) - target_temp)
    else:
        distance += temp_weight * 10.0  # Penalty for missing
    
    # Ionic strength distance
    if ionic_val is not None and not pd.isna(ionic_val):
        distance += ionic_weight * abs(float(ionic_val) - target_ionic)
    else:
        distance += ionic_weight * 1.0  # Penalty for missing
    
    return distance


def deduplicate_by_closest_conditions(
    df: pd.DataFrame,
    target_temp: float = DEFAULT_TEMPERATURE,
    target_ionic: float = DEFAULT_IONIC_STRENGTH,
    beta_col: str = "beta_definitionNr",
    metal_col: str = "metalNr",
    ligand_col: str = "ligandenNr",
    temp_col: str = "temperature",
    ionic_col: str = "ionicstrength",
    vlm_id_col: str = "verkn_ligand_metalID",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Deduplicate entries by keeping the one closest to target conditions.
    
    For entries with the same (metalID, ligandID, betaDefinitionID), only keep
    the entry with conditions closest to the target.
    
    Args:
        df: DataFrame with entries
        target_temp: Target temperature
        target_ionic: Target ionic strength
        beta_col, metal_col, ligand_col: Columns for grouping
        temp_col, ionic_col: Columns for condition comparison
        vlm_id_col: VLM ID column
        
    Returns:
        Tuple of (deduped DataFrame, stray DataFrame with removed entries)
    """
    if df.empty:
        return df, pd.DataFrame()
    
    # Create composite key
    group_cols = [metal_col, ligand_col, beta_col]
    
    # Check that required columns exist
    missing_cols = [c for c in group_cols if c not in df.columns]
    if missing_cols:
        return df, pd.DataFrame()
    
    # Calculate condition distance for each row
    distances = []
    for idx, row in df.iterrows():
        dist = calculate_condition_distance(
            row, target_temp, target_ionic,
            temp_col=temp_col, ionic_col=ionic_col
        )
        distances.append(dist)
    
    df = df.copy()
    df["_condition_distance"] = distances
    
    # For each group, keep only the row with minimum distance
    keep_indices = []
    stray_indices = []
    
    grouped = df.groupby(group_cols, dropna=False)
    for group_key, group_df in grouped:
        if len(group_df) == 1:
            keep_indices.append(group_df.index[0])
        else:
            # Find row with minimum distance
            min_idx = group_df["_condition_distance"].idxmin()
            keep_indices.append(min_idx)
            # Rest are strays
            for idx in group_df.index:
                if idx != min_idx:
                    stray_indices.append(idx)
    
    # Split into kept and stray
    deduped_df = df.loc[keep_indices].drop(columns=["_condition_distance"])
    stray_df = df.loc[stray_indices].drop(columns=["_condition_distance"]) if stray_indices else pd.DataFrame()
    
    return deduped_df, stray_df


# =============================================================================
# Condition popularity analysis
# =============================================================================

def find_most_popular_conditions(
    df: pd.DataFrame,
    temp_col: str = "temperature",
    ionic_col: str = "ionicstrength",
    temp_bin_width: float = 2.0,  # Bin width for temperature (°C)
    ionic_bin_width: float = 0.05,  # Bin width for ionic strength
) -> Tuple[Optional[float], Optional[float], int]:
    """Find the most popular temperature and ionic strength bins.
    
    Bins values and finds the most common bin.
    
    Args:
        df: DataFrame with entries
        temp_col, ionic_col: Column names
        temp_bin_width, ionic_bin_width: Bin widths
        
    Returns:
        Tuple of (representative_temp, representative_ionic, count)
    """
    if df.empty:
        return None, None, 0
    
    # Create bin labels for each entry
    bin_labels = []
    
    for idx, row in df.iterrows():
        temp_val = row.get(temp_col) if isinstance(row, dict) else row[temp_col] if temp_col in row.index else None
        ionic_val = row.get(ionic_col) if isinstance(row, dict) else row[ionic_col] if ionic_col in row.index else None
        
        temp_val = _safe_get_scalar(temp_val)
        ionic_val = _safe_get_scalar(ionic_val)
        
        # Bin temperature
        if temp_val is not None and not pd.isna(temp_val):
            temp_bin = round(float(temp_val) / temp_bin_width) * temp_bin_width
        else:
            temp_bin = None
        
        # Bin ionic strength
        if ionic_val is not None and not pd.isna(ionic_val):
            ionic_bin = round(float(ionic_val) / ionic_bin_width) * ionic_bin_width
        else:
            ionic_bin = None
        
        bin_labels.append((temp_bin, ionic_bin))
    
    # Count bin occurrences (ignoring None bins)
    valid_bins = [b for b in bin_labels if b[0] is not None and b[1] is not None]
    
    if not valid_bins:
        # Try with only temperature
        temp_only = [b[0] for b in bin_labels if b[0] is not None]
        if temp_only:
            most_common_temp = Counter(temp_only).most_common(1)[0]
            return most_common_temp[0], None, most_common_temp[1]
        return None, None, 0
    
    # Find most common bin
    bin_counts = Counter(valid_bins)
    most_common = bin_counts.most_common(1)[0]
    
    return most_common[0][0], most_common[0][1], most_common[1]


def bin_conditions(
    df: pd.DataFrame,
    target_temp: float = DEFAULT_TEMPERATURE,
    temp_tolerance: float = DEFAULT_TEMP_TOLERANCE,
    target_ionic: float = DEFAULT_IONIC_STRENGTH,
    ionic_tolerance: float = DEFAULT_IONIC_TOLERANCE,
    temp_col: str = "temperature",
    ionic_col: str = "ionicstrength",
    iteration: int = 0,
) -> ConditionBin:
    """Create a ConditionBin from the current filter settings.
    
    Args:
        df: DataFrame being processed (for range statistics)
        target_temp, temp_tolerance: Temperature target and tolerance
        target_ionic, ionic_tolerance: Ionic strength target and tolerance
        temp_col, ionic_col: Column names
        iteration: Iteration number for this bin
        
    Returns:
        ConditionBin object
    """
    temp_min = target_temp - temp_tolerance
    temp_max = target_temp + temp_tolerance
    ionic_min = target_ionic - ionic_tolerance
    ionic_max = target_ionic + ionic_tolerance
    
    return ConditionBin(
        temperature=target_temp,
        ionic_strength=target_ionic,
        temp_range=(temp_min, temp_max),
        ionic_range=(ionic_min, ionic_max),
        iteration=iteration,
    )


__all__ = [
    # Constant type filtering
    "filter_by_constant_type",
    # Soft filters
    "apply_soft_temperature_filter",
    "apply_soft_ionic_filter",
    "apply_combined_soft_filter",
    # Deduplication
    "calculate_condition_distance",
    "deduplicate_by_closest_conditions",
    # Condition analysis
    "find_most_popular_conditions",
    "bin_conditions",
]
