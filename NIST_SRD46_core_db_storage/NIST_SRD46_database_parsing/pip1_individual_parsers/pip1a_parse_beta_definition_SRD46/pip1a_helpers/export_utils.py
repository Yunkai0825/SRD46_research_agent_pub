"""
Export utilities for beta_definition parsing pipeline.
Provides organized, comprehensive CSV exports with consistent column ordering.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import pandas as pd

from .io_utils import print_debug, BD_PK

# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN DEFINITIONS - Organized by category
# ═══════════════════════════════════════════════════════════════════════════════

# Core identification columns (always first)
CORE_ID_COLS = [
    "beta_definitionID",
]

# Original data columns
ORIGINAL_DATA_COLS = [
    "name_beta_definition",
    "name_beta_definition_fixed",
    "comment",
]

# Parsed equation columns (human-readable)
EQUATION_READABLE_COLS = [
    "equation_python",
    "equation_latex",
]

# Structured equation data (JSON)
EQUATION_STRUCTURE_COLS = [
    "equation_sides",
    "equation_tree_json",
]

# Balance and conservation status
BALANCE_STATUS_COLS = [
    "element_conserved_final",
    "element_conserved_ML",
    "element_conserved_full",
    "water_fix_applied",
    "water_fix_delta",
]

# Balance details (for debugging/analysis)
BALANCE_DETAIL_COLS = [
    "balance_dict",
    "balance_final_dict",
]

# Failure analysis (for unsuccessful only)
FAILURE_ANALYSIS_COLS = [
    "failure_reason",
    "failure_category",
]

# Pre-parse residuals (diagnostic)
PREPARSE_COLS = [
    "preparse_residual_num",
    "preparse_residual_den",
    "preparse_residual_any",
    "preparse_residual_present",
]

# Manual correction tracking
MANUAL_CORRECTION_COLS = [
    "manual_correction",
    "correction_notes",
    "manual_name_fix",
    "manual_name_fix_note",
]

# Tree conservation (diagnostic)
TREE_DIAGNOSTIC_COLS = [
    "tree_element_conserved",
    "suspect_L_duplication",
]

# Species classification columns
SPECIES_CLASSIFICATION_COLS = [
    "species_list_all",
    "species_list_solid",
    "species_list_gas",
    "species_list_aqueous",
    "species_count_by_phase",
    "reaction_type",
]

# Columns to EXCLUDE from augmented export (intermediate/redundant columns)
EXCLUDE_FROM_AUGMENTED = [
    # Intermediate tree columns (we only want the final equation_tree_json)
    "beta_eq_tree",
    "beta_eq_tree_json",
    "beta_eq_element_net_tree",
    "beta_eq_element_conserved_tree",
    "beta_eq_element_net_tree_str",
    # Intermediate equation columns
    "beta_eq_sides",
    "beta_eq_str_python",
    "beta_eq_str_latex",
    "beta_eq_balance",
    "beta_eq_sides_adjusted",
    "beta_eq_str_python_adjusted",
    "beta_eq_str_latex_adjusted",
    "beta_eq_balance_adjusted",
    "beta_eq_str_python_final",
    "beta_eq_balance_final",
    "beta_eq_sides_final",
    # Redundant equation format columns
    "equation_latex",
    "equation_sides",
    # Balance/failure columns (not needed in augmented output)
    "balance_dict",
    "balance_final_dict",
    "failure_reason",
    "failure_category",
    # Pre-parse residual columns
    "preparse_residual_num",
    "preparse_residual_den",
    "preparse_residual_any",
    # Other intermediate columns
    "eqn_formula",
    "parse_status",
    "net_M", "net_L", "net_H", "net_O", "net_C", "net_N", "net_S", "net_P",
    "water_adjust_n",
    "water_adjust_side",
    "element_conserved_full_after_water",
    # Unnamed columns from original CSV
    "Acc_feld",
    "Unnamed: 4", "Unnamed: 5", "Unnamed: 6", "Unnamed: 7", "Unnamed: 8", "Unnamed: 9",
]

# VLM reference IDs (for unsuccessful entries - helps trace to original data)
VLM_REFERENCE_COLS = [
    "vlm_ids",          # List of verkn_ligand_metalID values using this beta_definition
    "ligand_ids",       # List of unique ligandenNr values
    "metal_ids",        # List of unique metalNr values
    "vlm_count",        # Count of VLM entries using this beta_definition
]

# Path to VLM table (relative to project root)
VLM_TABLE_RELPATH = "_input/SRD46_SQL_and_CSV/Export/CSV files/verkn_ligand_metal__16__8-11-2-5-6-14.csv"


def load_vlm_lookup(project_root: Path) -> pd.DataFrame:
    """
    Load VLM (verkn_ligand_metal) table for beta_definition ID lookups.
    
    Returns DataFrame with columns:
    - beta_definitionNr (the beta_definition ID)
    - verkn_ligand_metalID (vlm ID)
    - ligandenNr (ligand ID)
    - metalNr (metal ID)
    """
    vlm_path = project_root / VLM_TABLE_RELPATH
    if not vlm_path.exists():
        print_debug(f"[VLM] Warning: VLM table not found at {vlm_path}")
        return pd.DataFrame()
    
    try:
        vlm_df = pd.read_csv(vlm_path, encoding="utf-8-sig", low_memory=False)
        # Keep only relevant columns
        keep_cols = ["verkn_ligand_metalID", "ligandenNr", "metalNr", "beta_definitionNr"]
        available = [c for c in keep_cols if c in vlm_df.columns]
        vlm_df = vlm_df[available].copy()
        print_debug(f"[VLM] Loaded {len(vlm_df)} VLM entries with {len(available)} columns")
        return vlm_df
    except Exception as e:
        print_debug(f"[VLM] Error loading VLM table: {e}")
        return pd.DataFrame()


def aggregate_vlm_by_beta_definition(vlm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate VLM data by beta_definitionNr.
    
    Returns DataFrame indexed by beta_definitionNr with aggregated ID lists.
    """
    if vlm_df.empty or "beta_definitionNr" not in vlm_df.columns:
        return pd.DataFrame()
    
    agg_df = vlm_df.groupby("beta_definitionNr").agg({
        "verkn_ligand_metalID": lambda x: sorted(set(x.dropna().astype(int))),
        "ligandenNr": lambda x: sorted(set(x.dropna().astype(int))),
        "metalNr": lambda x: sorted(set(x.dropna().astype(int))),
    }).reset_index()
    
    agg_df.columns = ["beta_definitionNr", "vlm_ids", "ligand_ids", "metal_ids"]
    agg_df["vlm_count"] = agg_df["vlm_ids"].apply(len)
    
    return agg_df


def add_vlm_references(
    df: pd.DataFrame,
    project_root: Path,
    bd_pk: str = "beta_definitionID",
) -> pd.DataFrame:
    """
    Add VLM reference columns (vlm_ids, ligand_ids, metal_ids, vlm_count) to DataFrame.
    
    Joins on beta_definitionID to find all VLM entries that reference each beta_definition.
    """
    out_df = df.copy()
    
    # Load and aggregate VLM data
    vlm_df = load_vlm_lookup(project_root)
    if vlm_df.empty:
        # Add empty columns if VLM data not available
        for col in VLM_REFERENCE_COLS:
            out_df[col] = ""
        return out_df
    
    agg_vlm = aggregate_vlm_by_beta_definition(vlm_df)
    if agg_vlm.empty:
        for col in VLM_REFERENCE_COLS:
            out_df[col] = ""
        return out_df
    
    # Merge on beta_definitionID
    out_df = out_df.merge(
        agg_vlm,
        left_on=bd_pk,
        right_on="beta_definitionNr",
        how="left",
    )
    
    # Drop the duplicate key column
    if "beta_definitionNr" in out_df.columns:
        out_df.drop(columns=["beta_definitionNr"], inplace=True)
    
    # Convert lists to string representation for CSV export
    for col in ["vlm_ids", "ligand_ids", "metal_ids"]:
        if col in out_df.columns:
            out_df[col] = out_df[col].apply(
                lambda x: ", ".join(map(str, x)) if isinstance(x, list) else ""
            )
    
    # Fill NaN with empty strings
    for col in VLM_REFERENCE_COLS:
        if col in out_df.columns:
            out_df[col] = out_df[col].fillna("")
    
    return out_df


# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN METADATA
# ═══════════════════════════════════════════════════════════════════════════════

COLUMN_METADATA = {
    # Core ID
    "beta_definitionID": "Primary key from SRD46 beta_definition table.",
    
    # Original data
    "name_beta_definition": "Original equilibrium expression (raw from database).",
    "name_beta_definition_fixed": "Auto-corrected expression (after HOL preprocessing).",
    "comment": "Original comment field from database.",
    
    # Equation readable
    "equation_python": "Human-readable equation string (Python format: [species]^power).",
    "equation_latex": "LaTeX-formatted equation string for typesetting.",
    
    # Equation structure
    "equation_sides": "JSON: Structured equation sides {numerator: [...], denominator: [...]}.",
    "equation_tree_json": "JSON: Nested tree with species, components, elemental breakdown, and phase state (aqueous/solid/gas/liquid) for each species.",
    
    # Balance status
    "element_conserved_final": "True if equation is balanced (after water fix if applied).",
    "element_conserved_ML": "True if Metal (M) and Ligand (L) are balanced.",
    "element_conserved_full": "True if all elements are balanced before water fix.",
    "water_fix_applied": "True if H2O was added to balance H/O.",
    "water_fix_delta": "Number of H2O molecules added (positive) or removed (negative).",
    
    # Balance details
    "balance_dict": "JSON: Element-wise balance before water fix {H: x, O: y, M: z, L: w, ...}.",
    "balance_final_dict": "JSON: Element-wise balance after water fix.",
    
    # Failure analysis
    "failure_reason": "Primary reason for parse/balance failure.",
    "failure_category": "Categorized failure type (e.g., tree_not_conserved, ML_not_balanced).",
    
    # Pre-parse residuals
    "preparse_residual_num": "Unparsed residual text from numerator.",
    "preparse_residual_den": "Unparsed residual text from denominator.",
    "preparse_residual_any": "Combined unparsed residual text.",
    "preparse_residual_present": "True if any pre-parse residual exists.",
    
    # Manual corrections
    "manual_correction": "True if this entry was manually corrected.",
    "correction_notes": "Notes explaining the manual correction.",
    "manual_name_fix": "True if a codified raw-name typo fix (MANUAL_NAME_FIXES) was applied to name_beta_definition_fixed.",
    "manual_name_fix_note": "Reason for the raw-name fix, or STALE marker if the raw string no longer matches.",
    
    # Tree diagnostics
    "tree_element_conserved": "True if tree-based elemental check passes.",
    "suspect_L_duplication": "True if ligand duplication pattern detected.",
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _dict_to_json(obj) -> Optional[str]:
    """Convert dict/list to JSON string, return None for non-dict."""
    if isinstance(obj, (dict, list)):
        return json.dumps(obj, ensure_ascii=False)
    return None


def _safe_json_str(obj) -> str:
    """Convert to JSON string, handling None and non-serializable types."""
    if obj is None or (isinstance(obj, float) and pd.isna(obj)):
        return ""
    try:
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, ensure_ascii=False)
        return str(obj)
    except Exception:
        return str(obj)


def _classify_failure(row: pd.Series, prefix: str = "beta_eq") -> str:
    """Classify the failure reason for an unbalanced row."""
    # Check for existing reason
    if "reason" in row and pd.notna(row.get("reason")):
        return str(row["reason"])
    
    # Check for EXTRA tokens
    balance = row.get(f"{prefix}_balance") or row.get(f"{prefix}_balance_final") or {}
    if isinstance(balance, dict):
        if any(k.startswith("EXTRA:") for k in balance.keys()):
            return "contains_EXTRA_tokens"
    
    # Check balance values
    if isinstance(balance, dict):
        m_val = balance.get("M", 0)
        l_val = balance.get("L", 0)
        if abs(m_val) > 0.001 or abs(l_val) > 0.001:
            return "ML_not_balanced"
    
    # Check tree conservation
    tree_cons = row.get(f"{prefix}_element_conserved_tree")
    if tree_cons is False:
        return "tree_not_conserved"
    
    # Check for empty equation
    eq_py = row.get(f"{prefix}_str_python") or row.get("equation_python")
    if eq_py in ("1 <=> 1", "1 ⇔ 1", None, ""):
        return "empty_equation"
    
    return "unbalanced"


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT COLUMN PREPARATION
# ═══════════════════════════════════════════════════════════════════════════════

def prepare_export_dataframe(
    df: pd.DataFrame,
    prefix: str = "beta_eq",
    include_diagnostics: bool = False,
) -> pd.DataFrame:
    """
    Prepare DataFrame for export with standardized column names.
    
    Maps internal column names to clean export names.
    """
    out = df.copy()
    
    # Map internal columns to export names
    column_mapping = {
        # Equation readable
        f"{prefix}_str_python_final": "equation_python",
        f"{prefix}_str_python": "equation_python",
        f"{prefix}_str_latex_final": "equation_latex",
        f"{prefix}_str_latex": "equation_latex",
        
        # Equation structure
        f"{prefix}_sides_final": "equation_sides",
        f"{prefix}_sides": "equation_sides",
        f"{prefix}_tree_json": "equation_tree_json",
        
        # Balance
        f"{prefix}_balance": "balance_dict",
        f"{prefix}_balance_final": "balance_final_dict",
        
        # Tree diagnostics
        f"{prefix}_element_conserved_tree": "tree_element_conserved",
    }
    
    # Apply mappings (prefer _final versions)
    for src, dst in column_mapping.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]
    
    # Convert dict columns to JSON strings
    json_cols = ["equation_sides", "equation_tree_json", "balance_dict", "balance_final_dict"]
    for col in json_cols:
        if col in out.columns:
            out[col] = out[col].apply(_safe_json_str)
    
    return out


def get_ordered_columns(
    df: pd.DataFrame,
    column_groups: List[List[str]],
    include_remaining: bool = False,
) -> List[str]:
    """
    Get ordered list of columns based on column groups.
    Only includes columns that exist in the DataFrame.
    """
    ordered = []
    seen = set()
    
    for group in column_groups:
        for col in group:
            if col in df.columns and col not in seen:
                ordered.append(col)
                seen.add(col)
    
    if include_remaining:
        for col in df.columns:
            if col not in seen:
                ordered.append(col)
                seen.add(col)
    
    return ordered


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def export_success_dataframe(
    df: pd.DataFrame,
    out_path: Path,
    prefix: str = "beta_eq",
    include_diagnostics: bool = False,
) -> pd.DataFrame:
    """
    Export successful (balanced) entries with comprehensive columns.
    
    Column order:
    1. Core ID
    2. Original data
    3. Equation readable
    4. Equation structure
    5. Balance status
    6. (Optional) Diagnostics
    """
    # Prepare export columns
    export_df = prepare_export_dataframe(df, prefix, include_diagnostics)
    
    # Define column groups for success
    column_groups = [
        CORE_ID_COLS,
        ORIGINAL_DATA_COLS,
        EQUATION_READABLE_COLS,
        EQUATION_STRUCTURE_COLS,
        BALANCE_STATUS_COLS,
    ]
    
    if include_diagnostics:
        column_groups.extend([
            BALANCE_DETAIL_COLS,
            PREPARSE_COLS,
            MANUAL_CORRECTION_COLS,
            TREE_DIAGNOSTIC_COLS,
        ])
    
    # Get ordered columns that exist
    columns = get_ordered_columns(export_df, column_groups, include_remaining=False)
    
    # Filter to available columns
    available_cols = [c for c in columns if c in export_df.columns]
    out_df = export_df[available_cols].copy()
    
    # Export
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    
    print_debug(f"[EXPORT] {len(out_df)} success rows → {out_path}")
    print_debug(f"[EXPORT] Columns: {', '.join(available_cols[:5])}...")
    
    return out_df


def export_unsuccessful_dataframe(
    df: pd.DataFrame,
    out_path: Path,
    prefix: str = "beta_eq",
    include_diagnostics: bool = True,
    project_root: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Export unsuccessful (unbalanced) entries with comprehensive columns.
    
    Column order:
    1. Core ID
    2. Original data
    3. VLM references (ligand_ids, metal_ids, vlm_ids, vlm_count)
    4. Failure analysis
    5. Equation readable
    6. Equation structure
    7. Balance details
    8. (Optional) Diagnostics
    """
    # Prepare export columns
    export_df = prepare_export_dataframe(df, prefix, include_diagnostics)
    
    # Add failure classification
    export_df["failure_reason"] = df.apply(
        lambda r: _classify_failure(r, prefix), axis=1
    )
    export_df["failure_category"] = export_df["failure_reason"]
    
    # Add VLM references if project_root is provided
    if project_root is not None:
        export_df = add_vlm_references(export_df, project_root, BD_PK)
    
    # Define column groups for unsuccessful
    column_groups = [
        CORE_ID_COLS,
        ORIGINAL_DATA_COLS,
        VLM_REFERENCE_COLS,  # Add VLM references after original data
        FAILURE_ANALYSIS_COLS,
        EQUATION_READABLE_COLS,
        EQUATION_STRUCTURE_COLS,
        BALANCE_DETAIL_COLS,
    ]
    
    if include_diagnostics:
        column_groups.extend([
            BALANCE_STATUS_COLS,
            PREPARSE_COLS,
            MANUAL_CORRECTION_COLS,
            TREE_DIAGNOSTIC_COLS,
        ])
    
    # Get ordered columns that exist
    columns = get_ordered_columns(export_df, column_groups, include_remaining=False)
    
    # Filter to available columns
    available_cols = [c for c in columns if c in export_df.columns]
    out_df = export_df[available_cols].copy()
    
    # Export
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    
    print_debug(f"[EXPORT] {len(out_df)} unsuccessful rows → {out_path}")
    print_debug(f"[EXPORT] Columns: {', '.join(available_cols[:5])}...")
    
    return out_df


# Columns to mark with "*" for unsuccessful entries in augmented export
UNSUCCESSFUL_STAR_COLS = [
    "equation_python",
    "equation_latex",
    "equation_sides",
    "equation_tree_json",
    "balance_dict",
    "balance_final_dict",
    "element_conserved_ML",
    "element_conserved_full",
    "water_fix_applied",
    "water_fix_delta",
    "tree_element_conserved",
]


def build_augmented_dataframe(
    df: pd.DataFrame,
    prefix: str = "beta_eq",
    mark_unsuccessful_with_star: bool = True,
) -> pd.DataFrame:
    """
    Build the full augmented DataFrame (all curated columns, ordered) without writing it.
    
    For unsuccessful (unbalanced) entries, equation and balance columns
    are filled with "*" to clearly indicate parse failure, while
    preserving name_beta_definition_fixed and other core identifiers.
    
    Column order:
    1. Core ID
    2. Original data
    3. Equation readable
    4. Equation structure
    5. Balance status
    6. Balance details
    7. Failure analysis (if applicable)
    8. Pre-parse residuals
    9. Manual corrections
    10. Tree diagnostics
    11. Species classification
    """
    # Prepare export columns
    export_df = prepare_export_dataframe(df, prefix, include_diagnostics=True)
    
    # Add failure classification for unbalanced rows
    cons_final = export_df.get("element_conserved_final", pd.Series(False, index=export_df.index)).fillna(False)
    tree_cons = df.get(f"{prefix}_element_conserved_tree", pd.Series(True, index=df.index)).fillna(True)
    success_mask = cons_final & tree_cons
    
    export_df["failure_reason"] = ""
    export_df.loc[~success_mask, "failure_reason"] = df.loc[~success_mask].apply(
        lambda r: _classify_failure(r, prefix), axis=1
    )
    export_df["failure_category"] = export_df["failure_reason"]
    
    # Mark unsuccessful entries with "*" in equation/balance columns
    if mark_unsuccessful_with_star:
        for col in UNSUCCESSFUL_STAR_COLS:
            if col in export_df.columns:
                # Convert boolean columns to object type to avoid FutureWarning
                if export_df[col].dtype == bool:
                    export_df[col] = export_df[col].astype(object)
                export_df.loc[~success_mask, col] = "*"
    
    # Define column groups (ordered for final output)
    column_groups = [
        CORE_ID_COLS,
        ORIGINAL_DATA_COLS,
        EQUATION_READABLE_COLS,
        EQUATION_STRUCTURE_COLS,
        BALANCE_STATUS_COLS,
        BALANCE_DETAIL_COLS,
        FAILURE_ANALYSIS_COLS,
        PREPARSE_COLS,
        MANUAL_CORRECTION_COLS,
        TREE_DIAGNOSTIC_COLS,
        SPECIES_CLASSIFICATION_COLS,
    ]
    
    # Get ordered columns (do NOT include remaining - only curated columns)
    columns = get_ordered_columns(export_df, column_groups, include_remaining=False)
    
    # Filter to available columns and exclude intermediate columns
    available_cols = [c for c in columns if c in export_df.columns and c not in EXCLUDE_FROM_AUGMENTED]
    return export_df[available_cols].copy()


def export_augmented_dataframe(
    df: pd.DataFrame,
    out_path: Path,
    prefix: str = "beta_eq",
    mark_unsuccessful_with_star: bool = True,
) -> pd.DataFrame:
    """Write the augmented DataFrame (see build_augmented_dataframe) to CSV."""
    out_df = build_augmented_dataframe(df, prefix=prefix, mark_unsuccessful_with_star=mark_unsuccessful_with_star)
    
    # Export
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    
    print_debug(f"[EXPORT] {len(out_df)} total rows → {out_path}")
    print_debug(f"[EXPORT] Total columns: {len(out_df.columns)}")
    
    return out_df


def export_all(
    df: pd.DataFrame,
    build_dir: Path,
    prefix: str = "beta_eq",
    include_diagnostics: bool = True,
    project_root: Optional[Path] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Export all outputs: success, unsuccessful, and augmented.
    
    Args:
        df: Full processed DataFrame
        build_dir: Directory for output files
        prefix: Column prefix
        include_diagnostics: Include diagnostic columns in exports
        project_root: Project root directory (for VLM lookups in unsuccessful export)
        
    Returns:
        Dict with 'success', 'unsuccessful', 'augmented' DataFrames
    """
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Create success mask
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    tree_cons = df.get(f"{prefix}_element_conserved_tree", pd.Series(True, index=df.index)).fillna(True)
    success_mask = cons_final & tree_cons
    
    # Split data
    success_df = df[success_mask].copy()
    unsuccessful_df = df[~success_mask].copy()
    
    # Export each
    results = {}
    
    results["success"] = export_success_dataframe(
        success_df,
        build_dir / "beta_definition_success.csv",
        prefix=prefix,
        include_diagnostics=include_diagnostics,
    )
    
    results["unsuccessful"] = export_unsuccessful_dataframe(
        unsuccessful_df,
        build_dir / "beta_definition_unsuccessful.csv",
        prefix=prefix,
        include_diagnostics=include_diagnostics,
        project_root=project_root,  # Pass project_root for VLM lookups
    )
    
    results["augmented"] = export_augmented_dataframe(
        df,
        build_dir / "beta_definition_augmented.csv",
        prefix=prefix,
    )
    
    return results


def write_column_metadata(out_path: Path) -> None:
    """Write column metadata to JSON file."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(COLUMN_METADATA, f, ensure_ascii=False, indent=2, sort_keys=False)
    
    print_debug(f"[EXPORT] Column metadata → {out_path}")
