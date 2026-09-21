"""
NIST SRD 46 Beta-Definition Parsing Pipeline (Unified)
=======================================================
Merged from pip-1 (HOL autocorrect) and pip-3 (parsing pipeline).

Description: Parses beta_definition equilibrium expressions, applies HOL 
             auto-correction for polymetal species, computes mass balance,
             and exports structured equation data.
"""

from pathlib import Path
import re
import os
import json
import html
import ast
import shutil
from copy import deepcopy
from datetime import datetime
from collections import Counter
from typing import Dict, List, Tuple, Optional, NamedTuple
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
now = datetime.now()
formatted_datetime = now.strftime("%Y-%m-%d-%H-%M-%S")

EXPORT_FLAG = True
VERBOSE_FLAG = True

CODE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_ROOT.parent.parent  # Navigate to NIST_SRD46_Correction_and_Parser

# Input: from _input/SRD46_SQL_and_CSV/Export/CSV files/
INPUT_DIR = PROJECT_ROOT / "_input" / "SRD46_SQL_and_CSV" / "Export" / "CSV files"
INPUT_FILE = INPUT_DIR / "beta_definition__2.csv"

# Build: all intermediate outputs go to _build
BUILD_DIR = CODE_ROOT / "_build"

# Output: final outputs copied to _output folder
FINAL_OUTPUT_DIR = PROJECT_ROOT / "_output" / "pip1a_beta_definition_pipeline_final_output"

# Cache file (auto-fixed version in _build)
CACHE_FILENAME = "beta_definition_auto_fixed.csv"
CACHE_FILE = BUILD_DIR / CACHE_FILENAME
ORIGINAL_FILE = INPUT_FILE  # Use input file as original

# Log file location
SUMMARY_LOG = BUILD_DIR / "log_summary_runs" / f"summary_betadefinition_{formatted_datetime}.txt"

# Summary markdown path
SUMMARY_MD = BUILD_DIR / f"pipeline_summary_{formatted_datetime}.md"

BD_PK = "beta_definitionID"
PLACEHOLDER_DEFAULT = "*"

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT FROM HELPERS (modularized code)
# ═══════════════════════════════════════════════════════════════════════════════
from pip1a_helpers import (
    # Constants and patterns
    VALID_ELEMENTS, POLYMETAL_HOL_RULES, ParsedConst,
    _SPECIAL_HOL_GROUP_RE, _ELEMENT_KEY_RE,
    # I/O utilities
    load_beta_definition, load_csv_safe, print_debug, normalize_id, 
    augment_with_original_rows, maybe_parse_json_columns,
    # Species parsing
    parse_species_label_to_basis, collect_basis_counts,
    species_to_components, species_to_components_with_specials,
    strip_brackets, strip_nonchemical_annotations, has_dup_L,
    # Equation building
    beta_to_pairs, eq_to_sides, render_beta_tokens,
    compute_balance_vector, balance_from_sides, process_equation,
    add_equation_readability_and_balance, add_final_equation_columns,
    add_equation_tree, add_tree_elemental_diagnostics, flag_suspect_L_duplication,
    sides_to_nested_tree, element_net_from_tree, strings_from_sides,
    # HOL autocorrect
    apply_polymetal_hol_rule, preprocess_beta_definition,
    # Diagnostics and reporting
    print_run_summary, summarize_unbalanced_causes, compute_summary_stats,
    build_failure_masks, classify_unbalanced_row, write_summary_log,
    generate_validation_report, set_verbose,
    # Export utilities
    export_all, write_column_metadata, COLUMN_METADATA,
    # Species library and phase classification
    PhaseType, SpeciesEntry, SpeciesLibrary,
    build_species_library_from_df, add_species_phase_columns,
    enrich_equation_tree_with_phase, classify_reaction_type, export_species_library,
)

# Manual corrections for edge cases
from pip1a_helpers.manual_correction_helpers import (
    MANUAL_CORRECTIONS, 
    get_manual_correction, 
    has_manual_correction,
    get_valid_corrections,
    get_manual_name_fixes,
)

# ═══════════════════════════════════════════════════════════════════════════════
# REGEX PATTERNS (inline for beta_definition preliminary parsing)
# ═══════════════════════════════════════════════════════════════════════════════
PAT_EQ_SPLIT = r'/(?!sub|sup)'
PAT_SEGMENT_TOKEN = r'(\[.*?\]|&lt;sup&gt;.*?&lt;/sup&gt;)'
RE_EQ_SPLIT = re.compile(PAT_EQ_SPLIT)
RE_SEGMENT_TOKEN = re.compile(PAT_SEGMENT_TOKEN)
RE_HTML_SUB_TAGS = re.compile(r'</?\s*sub\s*>', re.IGNORECASE)
HTML_SUP_OPEN = "<sup>"
HTML_SUP_CLOSE = "</sup>"

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: PRELIMINARY PARSING (raw → tokens)
# ═══════════════════════════════════════════════════════════════════════════════

def _html_unescape_all(s: str) -> str:
    """Unescape HTML entities like &lt; → <."""
    prev = None
    out = s
    for _ in range(3):
        prev = out
        out = html.unescape(out)
        if out == prev:
            break
    return out

def beta_definition_preliminary_parsing(df: pd.DataFrame, 
                                         source_col: str = "name_beta_definition_fixed",
                                         out_col: str = "eqn_formula") -> pd.DataFrame:
    """
    Split beta_definition strings into tokenized equation format.
    Output: eqn_formula column containing [num_tokens, den_tokens] as flat alternating lists.
    """
    df = df.copy()
    
    # Drop rows with neither ID nor name
    if "beta_definitionID" in df.columns and source_col in df.columns:
        df = df[~(df["beta_definitionID"].isna() & df[source_col].isna())].copy()
    
    def custom_split(input_string: str):
        if input_string == '*' or pd.isna(input_string):
            return ['*']
        
        s = str(input_string)
        
        # Apply HOL preprocessing (periodate/vanadate conversions)
        s = preprocess_beta_definition(s)
        
        # Strip <sub>...</sub> tags
        s = RE_HTML_SUB_TAGS.sub("", s)
        
        # Split on "/" not followed by "sub" or "sup"
        segments = RE_EQ_SPLIT.split(s)
        if len(segments) != 2:
            return None
        
        # LHS: split by bracket tokens, remove <sup>...</sup>
        lhs_parts = RE_SEGMENT_TOKEN.split(segments[0])
        for i in range(len(lhs_parts)):
            lhs_parts[i] = lhs_parts[i].replace(HTML_SUP_OPEN, "").replace(HTML_SUP_CLOSE, "")
        # Remove first empty element
        if lhs_parts and lhs_parts[0] == '':
            lhs_parts = lhs_parts[1:]
        lhs_parts = ['1' if s == '' else s for s in lhs_parts]
        
        # RHS: split by bracket tokens, convert <sup>...</sup> to leading "-"
        rhs_parts = RE_SEGMENT_TOKEN.split(segments[1])
        for i in range(len(rhs_parts)):
            rhs_parts[i] = rhs_parts[i].replace(HTML_SUP_OPEN, "-").replace(HTML_SUP_CLOSE, "")
        # Remove first empty element
        if rhs_parts and rhs_parts[0] == '':
            rhs_parts = rhs_parts[1:]
        rhs_parts = ['-1' if s == '' else s for s in rhs_parts]
        
        return [lhs_parts, rhs_parts]
    
    def safe_apply(row):
        val = row.get(source_col, None)
        if pd.isna(val):
            return None
        try:
            return custom_split(str(val))
        except Exception:
            return None
    
    df[out_col] = df.apply(safe_apply, axis=1)
    return df

def add_preparse_residuals(df: pd.DataFrame, 
                           raw_col: str = "name_beta_definition_fixed",
                           out_prefix: str = "preparse") -> pd.DataFrame:
    """Add residual diagnostics from pre-parsing stage."""
    residuals_num, residuals_den, residuals_any, has_residual = [], [], [], []
    
    for val in df.get(raw_col, pd.Series(dtype=object)):
        if pd.isna(val) or not isinstance(val, str):
            residuals_num.append(None)
            residuals_den.append(None)
            residuals_any.append(None)
            has_residual.append(False)
            continue
        
        s = _html_unescape_all(str(val).strip())
        s = RE_HTML_SUB_TAGS.sub('', s)
        
        parts = RE_EQ_SPLIT.split(s, maxsplit=1)
        lhs = parts[0] if len(parts) >= 1 else ""
        rhs = parts[1] if len(parts) >= 2 else ""
        
        # Remove matched bracket tokens
        lhs_resid = re.sub(r'\[[^\]]+\](?:\^?\{?\d*\}?)?', '', lhs).strip()
        rhs_resid = re.sub(r'\[[^\]]+\](?:\^?\{?\d*\}?)?', '', rhs).strip()
        
        # Clean whitespace
        lhs_resid = re.sub(r'\s+', ' ', lhs_resid).strip()
        rhs_resid = re.sub(r'\s+', ' ', rhs_resid).strip()
        
        combined = f"{lhs_resid} {rhs_resid}".strip()
        
        residuals_num.append(lhs_resid if lhs_resid else None)
        residuals_den.append(rhs_resid if rhs_resid else None)
        residuals_any.append(combined if combined else None)
        has_residual.append(bool(combined))
    
    df[f"{out_prefix}_residual_num"] = residuals_num
    df[f"{out_prefix}_residual_den"] = residuals_den
    df[f"{out_prefix}_residual_any"] = residuals_any
    df[f"{out_prefix}_residual_present"] = has_residual
    
    return df

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: DIAGNOSTICS (imported from pip1a_helpers.diagnostics)
# ═══════════════════════════════════════════════════════════════════════════════
# All diagnostics functions are now in pip1a_helpers/diagnostics.py:
# - build_failure_masks, classify_unbalanced_row, summarize_unbalanced_causes
# - compute_summary_stats, print_run_summary, write_summary_log
# - check_tree_conservation, element_mass_conserved_from_tree
# - generate_validation_report

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2.5: MANUAL CORRECTIONS FOR EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

def apply_manual_name_fixes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Patch raw-name typos listed in MANUAL_NAME_FIXES into `name_beta_definition_fixed`.

    The raw column is left untouched; a fix is applied only when the raw string matches
    the recorded one, otherwise the entry is reported as stale and skipped.
    Adds columns `manual_name_fix` (bool) and `manual_name_fix_note`.
    """
    df = df.copy()
    df["manual_name_fix"] = False
    df["manual_name_fix_note"] = ""

    applied = stale = missing = 0
    for beta_id, fix in get_manual_name_fixes().items():
        mask = df[BD_PK] == beta_id
        if not mask.any():
            missing += 1
            print_debug(f"[MANUAL-NAME] β={beta_id} not in data; fix skipped.")
            continue
        idx = df.index[mask][0]
        raw_val = df.at[idx, "name_beta_definition"]
        if raw_val != fix["raw"]:
            stale += 1
            df.at[idx, "manual_name_fix_note"] = f"STALE: raw string differs from recorded fix ({fix['notes']})"
            print_debug(f"[MANUAL-NAME] β={beta_id} raw string changed upstream; fix NOT applied.")
            continue
        df.at[idx, "name_beta_definition_fixed"] = preprocess_beta_definition(fix["fixed"])
        df.at[idx, "manual_name_fix"] = True
        df.at[idx, "manual_name_fix_note"] = fix["notes"]
        applied += 1

    print_debug(f"[MANUAL-NAME] Applied {applied} raw-name fixes ({stale} stale, {missing} missing).")
    return df


def apply_manual_corrections(
    df: pd.DataFrame,
    prefix: str = "beta_eq",
) -> pd.DataFrame:
    """
    Apply manual corrections to entries that cannot be parsed by the standard pipeline.
    
    This function:
    1. Identifies rows with beta_definitionID in MANUAL_CORRECTIONS
    2. Overwrites their equation_sides and equation string columns
    3. Recalculates balance and conservation flags using standard parser
    
    Note: Manual corrections must provide equation_sides that balance correctly
    when processed by the standard parser. If they don't balance, they will
    still be flagged as unbalanced.
    
    Args:
        df: DataFrame with parsed beta definitions
        prefix: Column prefix for equation columns
        
    Returns:
        DataFrame with manual corrections applied
    """
    df = df.copy()
    
    valid_corrections = get_valid_corrections()
    if not valid_corrections:
        print_debug("[MANUAL] No valid manual corrections to apply.")
        return df
    
    corrected_count = 0
    balanced_count = 0
    skipped_count = 0
    
    for beta_id, correction in valid_corrections.items():
        # Find row with this beta_definitionID
        mask = df[BD_PK] == beta_id
        if not mask.any():
            skipped_count += 1
            continue
        
        idx = df.index[mask][0]
        
        # Apply correction
        eq_sides = correction["equation_sides"]
        eq_str = correction.get("beta_eq_str_python_final", "")
        notes = correction.get("notes", "")
        
        # Update equation_sides
        df.at[idx, f"{prefix}_sides"] = eq_sides
        df.at[idx, f"{prefix}_sides_final"] = eq_sides
        df.at[idx, "equation_sides"] = json.dumps(eq_sides, ensure_ascii=False)
        
        # Update equation string
        if eq_str:
            df.at[idx, f"{prefix}_str_python"] = eq_str
            df.at[idx, f"{prefix}_str_python_final"] = eq_str
        
        # Recalculate balance using the corrected sides (standard parser)
        balance = balance_from_sides(eq_sides)
        df.at[idx, f"{prefix}_balance"] = balance
        df.at[idx, f"{prefix}_balance_final"] = balance
        
        # Check if now balanced
        is_balanced = all(abs(v) < 1e-9 for v in balance.values())
        df.at[idx, "element_conserved_final"] = is_balanced
        df.at[idx, "element_conserved_full"] = is_balanced
        
        if is_balanced:
            balanced_count += 1
        
        # Mark as manually corrected
        if "manual_correction" not in df.columns:
            df["manual_correction"] = False
        df.at[idx, "manual_correction"] = True
        
        if "correction_notes" not in df.columns:
            df["correction_notes"] = None
        df.at[idx, "correction_notes"] = notes
        
        corrected_count += 1
    
    print_debug(f"[MANUAL] Applied {corrected_count} manual corrections, {balanced_count} now balanced.")
    if skipped_count > 0:
        print_debug(f"[MANUAL] {skipped_count} IDs not found in data.")
    
    # Rebuild tree for corrected entries
    if corrected_count > 0:
        print_debug("[MANUAL] Rebuilding trees for corrected entries...")
        corrected_mask = df.get("manual_correction", pd.Series(False, index=df.index)).fillna(False)
        
        for idx in df.index[corrected_mask]:
            sides = df.at[idx, f"{prefix}_sides"]
            if isinstance(sides, dict):
                try:
                    tree = sides_to_nested_tree(sides)
                    df.at[idx, f"{prefix}_tree"] = tree
                    df.at[idx, f"{prefix}_tree_json"] = json.dumps(tree, ensure_ascii=False)
                    
                    # Check tree conservation normally
                    net = element_net_from_tree(tree)
                    tree_balanced = all(abs(v) < 1e-9 for v in net.values())
                    df.at[idx, f"{prefix}_element_conserved_tree"] = tree_balanced
                except Exception as e:
                    print_debug(f"[MANUAL] Tree rebuild failed for ID={df.at[idx, BD_PK]}: {e}")
    
    return df

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def _dict_json(obj) -> Optional[str]:
    """Convert dict to JSON string."""
    if isinstance(obj, dict):
        return json.dumps(obj, ensure_ascii=False)
    return None

def _add_export_columns(df: pd.DataFrame, prefix: str = "beta_eq") -> pd.DataFrame:
    """Add convenience columns for export."""
    df = df.copy()
    
    # equation_sides JSON
    sides_col = f"{prefix}_sides_final" if f"{prefix}_sides_final" in df.columns else f"{prefix}_sides"
    if sides_col in df.columns:
        df["equation_sides"] = df[sides_col].apply(_dict_json)
    
    # equation_python
    py_col = f"{prefix}_str_python_final" if f"{prefix}_str_python_final" in df.columns else f"{prefix}_str_python"
    if py_col in df.columns:
        df["equation_python"] = df[py_col]
    
    # equation_latex
    lx_col = f"{prefix}_str_latex_final" if f"{prefix}_str_latex_final" in df.columns else f"{prefix}_str_latex"
    if lx_col in df.columns:
        df["equation_latex"] = df[lx_col]
    
    return df

def export_beta_definition_good_bad(
    df: pd.DataFrame,
    out_dir: Path,
    root_dir: Path = None,
    prefix: str = "beta_eq",
    good_cols: List[str] = None,
    bad_cols: List[str] = None,
    drop_all_nan: bool = True,
    require_tree_conserved: bool = True,
    json_last: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Export good (balanced) and bad (unbalanced) DataFrames."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    df = _add_export_columns(df, prefix)
    
    # Success mask
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    tree_cons = df.get(f"{prefix}_element_conserved_tree", pd.Series(True, index=df.index)).fillna(True)
    
    if require_tree_conserved:
        success_mask = cons_final & tree_cons
    else:
        success_mask = cons_final
    
    good_df = df[success_mask].copy()
    bad_df = df[~success_mask].copy()
    
    # Add failure_reason to bad
    if "reason" in bad_df.columns:
        bad_df["failure_reason"] = bad_df["reason"]
    else:
        bad_df["failure_reason"] = "unbalanced"
    
    # Default columns
    if good_cols is None:
        good_cols = [BD_PK, "name_beta_definition_fixed", "equation_python", "equation_sides", f"{prefix}_tree_json"]
    if bad_cols is None:
        bad_cols = [BD_PK, "name_beta_definition_fixed", "equation_python", "failure_reason", f"{prefix}_balance"]
    
    # Filter to available columns
    good_cols = [c for c in good_cols if c in good_df.columns]
    bad_cols = [c for c in bad_cols if c in bad_df.columns]
    
    good_out = good_df[good_cols]
    bad_out = bad_df[bad_cols]
    
    # Export
    good_path = out_dir / "equilibria_success.csv"
    bad_path = out_dir / "equilibria_unsuccessful.csv"
    
    good_out.to_csv(good_path, index=False, encoding="utf-8-sig")
    bad_out.to_csv(bad_path, index=False, encoding="utf-8-sig")
    
    print_debug(f"Exported {len(good_out)} success rows → {good_path}")
    print_debug(f"Exported {len(bad_out)} failure rows → {bad_path}")
    
    return good_df, bad_df

def build_beta_definition_column_meta(prefix: str = "beta_eq") -> Dict[str, str]:
    """Build column metadata dictionary."""
    P = prefix
    return {
        BD_PK: "Primary key from SRD46 beta_definition table.",
        "name_beta_definition": "Original equilibrium expression (raw).",
        "name_beta_definition_fixed": "Auto-corrected expression (after pip-1 HOL fixes).",
        "eqn_formula": "Tokenized equation: [[num_pairs], [den_pairs]].",
        f"{P}_sides": "Structured sides: {numerator: [...], denominator: [...]}.",
        f"{P}_str_python": "Readable equation string.",
        f"{P}_str_latex": "LaTeX equation string.",
        f"{P}_balance": "Balance dict on {M,L,H,O,...} basis.",
        "element_conserved_ML": "True if M and L are balanced.",
        "element_conserved_full": "True if all elements balanced.",
        "element_conserved_final": "Final conservation status (with water fix if applied).",
        "water_fix_applied": "True if water adjustment was applied.",
        f"{P}_tree_json": "Nested JSON tree for export.",
    }

def write_beta_definition_meta(out_path: Path, prefix: str = "beta_eq"):
    """Write column metadata JSON."""
    meta = build_beta_definition_column_meta(prefix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
    print_debug(f"Wrote column metadata → {out_path}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: ORCHESTRATION (end-to-end runners)
# ═══════════════════════════════════════════════════════════════════════════════

def run_beta_definition_debug(
    csv_path: str | Path = "beta_definition_auto_fixed.csv",
    sep: str = ",",
    encoding: str = "utf-8",
    sample_unbalanced: int = 15,
) -> pd.DataFrame:
    """Quick debug pipeline for beta_definition only."""
    df = load_beta_definition(file_path=csv_path, sep=sep, encoding=encoding)
    df = beta_definition_preliminary_parsing(df)
    df = add_equation_readability_and_balance(df, source_col="eqn_formula", prefix="beta_eq")
    df = add_final_equation_columns(df, prefix="beta_eq")
    df = add_equation_tree(df, prefix="beta_eq")
    df = add_tree_elemental_diagnostics(df, prefix="beta_eq")
    print_run_summary(df, prefix="beta_eq", sample_unbalanced=sample_unbalanced)
    return df

def run_full_beta_pipeline(
    csv_path: str | Path,
    *,
    sep: str = ",",
    encoding: str = "utf-8",
    compute_preparse_residuals: bool = True,
    apply_manual: bool = True,
    build_species_library: bool = True,
) -> Tuple[pd.DataFrame, Optional['SpeciesLibrary']]:
    """
    Full pipeline: load → preparse → tokenize → balance → tree → manual_corrections → 
                   species_library → phase_classification → diagnostics.
    
    Returns:
        Tuple of (processed_df, species_library) where species_library is None if 
        build_species_library is False.
    """
    # Step 1: Load
    df = load_beta_definition(file_path=csv_path, sep=sep, encoding=encoding)
    
    # Step 1.5: Create name_beta_definition_fixed if it doesn't exist
    if "name_beta_definition_fixed" not in df.columns:
        if "name_beta_definition" in df.columns:
            print_debug("[INFO] Creating 'name_beta_definition_fixed' from 'name_beta_definition'...")
            # Apply preprocessing (HOL normalization) to create fixed column
            df["name_beta_definition_fixed"] = df["name_beta_definition"].apply(
                lambda x: preprocess_beta_definition(x) if pd.notna(x) else x
            )
        else:
            raise ValueError("DataFrame must contain 'name_beta_definition' or 'name_beta_definition_fixed' column")
    
    # Step 1.6: Codified raw-name typo fixes (MANUAL_NAME_FIXES)
    if apply_manual:
        df = apply_manual_name_fixes(df)
    
    # Step 2: Preliminary parsing
    df = beta_definition_preliminary_parsing(df)
    
    # Step 2.5: Pre-parse residuals
    if compute_preparse_residuals:
        df = add_preparse_residuals(df, raw_col="name_beta_definition_fixed", out_prefix="preparse")
    
    # Step 3: Tokenize, normalize, compute balances
    df = add_equation_readability_and_balance(df, source_col="eqn_formula", prefix="beta_eq")
    
    # Step 4: Consolidate final columns
    df = add_final_equation_columns(df, prefix="beta_eq")
    
    # Step 5: Build nested tree
    df = add_equation_tree(df, prefix="beta_eq")
    df = add_tree_elemental_diagnostics(df, prefix="beta_eq")
    
    # Step 6: Flag suspect duplications
    df = flag_suspect_L_duplication(df, prefix="beta_eq")
    
    # Step 7: Apply manual corrections for edge cases
    if apply_manual:
        df = apply_manual_corrections(df, prefix="beta_eq")
    
    # Step 8: Build species library and add phase classification
    species_lib = None
    if build_species_library:
        print_debug("[INFO] Building species library with phase classification...")
        # Use the prefixed tree column created by add_equation_tree
        tree_col = "beta_eq_tree_json"
        species_lib = build_species_library_from_df(
            df, 
            tree_col=tree_col,
            beta_id_col=BD_PK,
        )
        print_debug(f"[INFO] Found {species_lib.unique_count} unique species")
        print_debug(f"[INFO] Phase breakdown: {species_lib.phase_counts()}")
        
        # Add phase columns to DataFrame
        df = add_species_phase_columns(df, species_lib, tree_col=tree_col, out_prefix="species")
        
        # Enrich equation tree with phase state for each species (modifies tree_col in place)
        df = enrich_equation_tree_with_phase(df, species_lib, tree_col=tree_col)
        print_debug(f"[INFO] Enriched equation trees with phase state in {tree_col}")
        
        # Classify reaction types
        df = classify_reaction_type(df, species_lib, tree_col=tree_col, out_col="reaction_type")
    
    return df, species_lib

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: SUMMARY MARKDOWN GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_summary_markdown(
    df: pd.DataFrame,
    prefix: str = "beta_eq",
    out_path: Path = None,
) -> str:
    """
    Generate a comprehensive pipeline summary as Markdown.
    
    Args:
        df: Processed DataFrame
        prefix: Column prefix for equation columns
        out_path: Path to save markdown file (optional)
        
    Returns:
        Markdown string
    """
    stats = compute_summary_stats(df, prefix=prefix)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build markdown content
    lines = [
        "# NIST SRD 46 Beta Definition Pipeline Summary",
        "",
        f"**Generated:** {now_str}",
        f"**Input File:** `{INPUT_FILE}`",
        f"**Build Directory:** `{BUILD_DIR}`",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total rows | {stats.get('total', 0)} |",
        f"| Successful (balanced) | {stats.get('balanced', 0)} |",
        f"| Failed (unbalanced) | {stats.get('unbalanced', 0)} |",
        f"| Empty/placeholder | {stats.get('empty', 0)} |",
        f"| **Hit Rate** | **{stats.get('hit_rate', 0):.2f}%** |",
        "",
        "---",
        "",
        "## Failure Breakdown by Reason",
        "",
        "| Reason | Count |",
        "|--------|-------|",
    ]
    
    # Add failure reason counts from stats
    reason_counts = stats.get('reason_counts', {})
    if reason_counts:
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| (no failures) | 0 |")
    
    # EXTRA token breakdown
    extra_counts = stats.get('extra_token_counts', {})
    if extra_counts:
        lines.extend([
            "",
            "---",
            "",
            "## EXTRA Token Breakdown (Unparseable Species)",
            "",
            "| Token | Count |",
            "|-------|-------|",
        ])
        for token, count in sorted(extra_counts.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"| `{token}` | {count} |")
    
    lines.extend([
        "",
        "---",
        "",
        "## Output Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `equilibria_success.csv` | {stats.get('balanced', 0)} balanced equations |",
        f"| `equilibria_unsuccessful.csv` | {stats.get('unbalanced', 0)} unbalanced equations |",
        f"| `beta_definition_augmented.csv` | Full processed DataFrame with all columns |",
        f"| `beta_definition_columns_meta.json` | Column metadata documentation |",
        "",
        "---",
        "",
        "## Configuration",
        "",
        "```python",
        f"INPUT_FILE = {INPUT_FILE}",
        f"BUILD_DIR = {BUILD_DIR}",
        f"FINAL_OUTPUT_DIR = {FINAL_OUTPUT_DIR}",
        f"EXPORT_FLAG = {EXPORT_FLAG}",
        f"VERBOSE_FLAG = {VERBOSE_FLAG}",
        "```",
        "",
        "---",
        "",
        "## Column Definitions",
        "",
        "| Column | Description |",
        "|--------|-------------|",
    ])
    
    col_meta = build_beta_definition_column_meta(prefix)
    for col, desc in col_meta.items():
        lines.append(f"| `{col}` | {desc} |")
    
    lines.extend([
        "",
        "---",
        "",
        f"*Pipeline completed at {now_str}*",
    ])
    
    md_content = "\n".join(lines)
    
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print_debug(f"[SUMMARY] Wrote markdown summary → {out_path}")
    
    return md_content


def copy_core_outputs_to_final(
    build_dir: Path,
    final_dir: Path,
    timestamp: str,
) -> List[Path]:
    """
    Copy core output files to final output directory.
    
    Copies:
    - beta_definition_success.csv
    - beta_definition_unsuccessful.csv
    - beta_definition_augmented.csv
    - beta_definition_columns_meta.json
    - pipeline_summary_{timestamp}.md
    - log file summary_betadefinition_{timestamp}.txt
    
    Returns list of copied file paths.
    """
    final_dir = Path(final_dir)
    final_dir.mkdir(parents=True, exist_ok=True)
    
    copied = []
    failed = []
    
    # Core files to copy (only augmented + metadata, success/unsuccessful stay in build)
    core_files = [
        "beta_definition_augmented.csv",
        "beta_definition_columns_meta.json",
        # Species library files
        "species_library_aqueous.csv",
        "species_library_solid.csv",
        "species_library_gas.csv",
    ]
    
    for filename in core_files:
        src = build_dir / filename
        if src.exists():
            dst = final_dir / filename
            try:
                shutil.copy2(src, dst)
                copied.append(dst)
                print_debug(f"[COPY] {filename} → {dst}")
            except PermissionError as e:
                failed.append(filename)
                print_debug(f"[COPY WARNING] Could not copy {filename}: {e}")
    
    # Copy the current run's summary markdown (using timestamp)
    md_file = build_dir / f"pipeline_summary_{timestamp}.md"
    if md_file.exists():
        dst = final_dir / md_file.name
        try:
            shutil.copy2(md_file, dst)
            copied.append(dst)
            print_debug(f"[COPY] {md_file.name} → {dst}")
        except PermissionError as e:
            failed.append(md_file.name)
            print_debug(f"[COPY WARNING] Could not copy {md_file.name}: {e}")
    
    # Copy the current run's log file (using timestamp)
    log_dir = build_dir / "log_summary_runs"
    log_file = log_dir / f"summary_betadefinition_{timestamp}.txt"
    if log_file.exists():
        dst = final_dir / log_file.name
        try:
            shutil.copy2(log_file, dst)
            copied.append(dst)
            print_debug(f"[COPY] {log_file.name} → {dst}")
        except PermissionError as e:
            failed.append(log_file.name)
            print_debug(f"[COPY WARNING] Could not copy {log_file.name}: {e}")
    
    if failed:
        print_debug(f"[COPY WARNING] {len(failed)} files could not be copied (may be open in another application)")
    
    return copied


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Ensure build directory exists
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "log_summary_runs").mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("NIST SRD 46 Beta Definition Parsing Pipeline")
    print("=" * 70)
    print(f"[CONFIG] CODE_ROOT: {CODE_ROOT}")
    print(f"[CONFIG] INPUT_FILE: {INPUT_FILE}")
    print(f"[CONFIG] BUILD_DIR: {BUILD_DIR}")
    print(f"[CONFIG] FINAL_OUTPUT_DIR: {FINAL_OUTPUT_DIR}")
    print(f"[CONFIG] Input exists: {INPUT_FILE.exists()}")
    print()
    
    # Check if auto-fixed cache exists, otherwise use original input
    if CACHE_FILE.exists():
        print(f"[INFO] Using cached auto-fixed file: {CACHE_FILE}")
        input_path = CACHE_FILE
    else:
        print(f"[INFO] Cache not found. Using original input: {INPUT_FILE}")
        input_path = INPUT_FILE
    
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Run full pipeline (now returns both df and species library)
    print("\n[STEP 1] Running full beta definition pipeline...")
    beta_df, species_library = run_full_beta_pipeline(input_path)
    
    # Print summary
    print("\n[STEP 2] Computing run summary...")
    print_run_summary(beta_df, prefix="beta_eq", sample_unbalanced=15)
    
    # Print species library summary
    if species_library:
        print("\n[STEP 2.5] Species Library Summary:")
        print(species_library.summary())
    
    # Show sample
    if VERBOSE_FLAG:
        cols_to_show = [
            "beta_definitionID",
            "name_beta_definition_fixed",
            "eqn_formula",
            "beta_eq_str_python",
            "element_conserved_final",
            "reaction_type",  # New column from species classification
        ]
        cols_to_show = [c for c in cols_to_show if c in beta_df.columns]
        print_debug('\n=== Sample processed data ===')
        with pd.option_context("display.max_colwidth", 120):
            print_debug(beta_df[cols_to_show].head(10))
    
    # Export
    if EXPORT_FLAG:
        print("\n[STEP 3] Exporting results to build directory...")
        
        # Use new organized export module
        export_results = export_all(
            beta_df,
            build_dir=BUILD_DIR,
            prefix="beta_eq",
            include_diagnostics=True,
            project_root=PROJECT_ROOT,  # Pass project root for VLM lookups
        )
        
        # Export species library
        if species_library:
            print("\n[STEP 3.5] Exporting species library...")
            species_lib_paths = export_species_library(
                species_library, 
                out_dir=BUILD_DIR,
                prefix="species_library",
            )
            print(f"[INFO] Species library exported to:")
            for key, path in species_lib_paths.items():
                print(f"       - {key}: {path}")
        
        # Write column metadata
        meta_path = BUILD_DIR / "beta_definition_columns_meta.json"
        write_column_metadata(meta_path)
        
        # Write summary log
        print("\n[STEP 4] Writing summary log...")
        SUMMARY_LOG.parent.mkdir(parents=True, exist_ok=True)
        write_summary_log(beta_df, SUMMARY_LOG, prefix="beta_eq")
        
        # Generate summary markdown
        print("\n[STEP 5] Generating summary markdown...")
        md_path = BUILD_DIR / f"pipeline_summary_{formatted_datetime}.md"
        generate_summary_markdown(beta_df, prefix="beta_eq", out_path=md_path)
        
        # Copy core outputs to final directory
        print("\n[STEP 6] Copying core outputs to final output directory...")
        FINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        copied_files = copy_core_outputs_to_final(BUILD_DIR, FINAL_OUTPUT_DIR, formatted_datetime)
        print(f"[INFO] Copied {len(copied_files)} files to {FINAL_OUTPUT_DIR}")
    
    print("\n" + "=" * 70)
    print("[DONE] Beta definition parsing pipeline complete.")
    print("=" * 70)
