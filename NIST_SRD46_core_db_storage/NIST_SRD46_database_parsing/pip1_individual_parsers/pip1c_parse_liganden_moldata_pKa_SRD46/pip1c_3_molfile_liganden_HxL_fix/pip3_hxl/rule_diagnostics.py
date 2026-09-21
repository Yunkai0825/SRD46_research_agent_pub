"""
rule_diagnostics.py - Rule-specific diagnostic output generation.

Generates detailed CSV files for:
1. Each rule that was applied (before/after comparison)
2. Formula mismatch entries
3. Multi-component InChI entries
4. Entries needing manual review
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from .config import BUILD_DIR
from .logging_utils import log


# =====================================================================
# DIAGNOSTIC OUTPUT CONFIGURATION
# =====================================================================
DEBUG_RULES_DIR = BUILD_DIR / "DEBUG_rules"

# Columns to include in rule diagnostic CSVs
RULE_DIAG_COLS = [
    "ligandenID", "name_ligand", "COMMON_NAME", "IUPAC_NAME",
    # Figure definition
    "figure_definition_original", "figure_definition", "figure_definition_parsed",
    "figure_definition_charge", "h_count", "l_count",
    # Charges
    "rdkit_charge_before", "rdkit_charge_after", "target_charge",
    "inchi_charge_value",
    # Formulas
    "formula", "COMPOSITION", "formula_comp_status",
    "formula_canonical", "composition_canonical",
    # SMILES/InChI
    "SMILES_before", "SMILES", "InChI_before", "InChI",
    # Fragment counts
    "pre_smiles_frag_count", "post_smiles_frag_count",
    "pre_molblock_frag_count", "post_molblock_frag_count",
    # Validation
    "validation_ok", "pipeline_success", "rules_applied",
    "correction_applied",
]

# Minimal columns for summary views
MINIMAL_DIAG_COLS = [
    "ligandenID", "name_ligand",
    "figure_definition_original", "figure_definition",
    "rdkit_charge_before", "rdkit_charge_after", "target_charge",
    "SMILES_before", "SMILES",
    "rules_applied", "correction_applied",
]


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def is_multi_component_inchi(inchi: Optional[str]) -> bool:
    """
    Check if InChI represents a multi-component structure.
    
    Multi-component InChIs have disconnected fragments indicated by:
    - Multiple formula units separated by '.'
    - /c layer with multiple disconnected systems (;)
    """
    if not inchi or not isinstance(inchi, str):
        return False
    
    # Check for dot in formula layer (e.g., "InChI=1S/C6H6.ClH/")
    formula_match = re.match(r"InChI=1S?/([^/]+)", inchi)
    if formula_match:
        formula = formula_match.group(1)
        if "." in formula:
            return True
    
    # Check for semicolon in connection layer (disconnected fragments)
    if re.search(r"/c[^/]*;", inchi):
        return True
    
    return False


def count_inchi_components(inchi: Optional[str]) -> int:
    """Count the number of components in an InChI string."""
    if not inchi or not isinstance(inchi, str):
        return 0
    
    formula_match = re.match(r"InChI=1S?/([^/]+)", inchi)
    if formula_match:
        formula = formula_match.group(1)
        return len(formula.split("."))
    
    return 1


def has_formula_mismatch(row: pd.Series) -> bool:
    """Check if row has formula vs composition mismatch."""
    status = row.get("formula_comp_status", "")
    return status in ("different", "unparsed")


def _filter_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Filter DataFrame to only include existing columns."""
    existing = [c for c in cols if c in df.columns]
    return df[existing].copy()


# =====================================================================
# RULE-SPECIFIC DIAGNOSTIC GENERATION
# =====================================================================

def generate_rule_diagnostics(df: pd.DataFrame, timestamp: str = None) -> Dict[str, pd.DataFrame]:
    """
    Generate diagnostic DataFrames for each rule that was applied.
    
    Args:
        df: Full processed DataFrame with before/after columns
        timestamp: Optional timestamp for file naming
        
    Returns:
        Dictionary mapping rule names to diagnostic DataFrames
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    diagnostics = {}
    
    # Parse rules_applied column to identify which rules were used
    rules_used = set()
    for ra in df["rules_applied"].dropna():
        if isinstance(ra, str):
            for rule in ra.split(";"):
                rule = rule.strip()
                if rule:
                    rules_used.add(rule)
    
    log(f"[DIAG] Rules used in processing: {sorted(rules_used)}")
    
    # Generate diagnostic for each rule
    for rule in sorted(rules_used):
        # Filter rows where this rule was applied
        mask = df["rules_applied"].fillna("").str.contains(rule, regex=False)
        rule_df = df[mask].copy()
        
        if len(rule_df) == 0:
            continue
        
        # Add filtered columns
        diag_df = _filter_columns(rule_df, RULE_DIAG_COLS)
        diagnostics[rule] = diag_df
        
        log(f"[DIAG] {rule}: {len(diag_df):,} entries")
    
    return diagnostics


# =====================================================================
# FORMULA MISMATCH ANALYSIS UTILITIES
# =====================================================================

def _parse_formula_atoms(formula: str) -> Dict[str, int]:
    """Parse molecular formula into element counts dict."""
    if not formula or not isinstance(formula, str):
        return {}
    # Remove charge notation
    formula = re.sub(r'/[+-]+$', '', str(formula))
    formula = re.sub(r'[+-]+$', '', formula)
    
    atoms = {}
    for m in re.finditer(r'([A-Z][a-z]?)(\d*)', formula):
        elem, cnt = m.groups()
        if elem:
            atoms[elem] = atoms.get(elem, 0) + int(cnt or 1)
    return atoms


def _compute_atom_diff(formula: str, composition: str) -> Dict[str, int]:
    """Compute atom count differences: COMPOSITION - formula."""
    f_atoms = _parse_formula_atoms(formula)
    c_atoms = _parse_formula_atoms(composition)
    
    all_elems = set(f_atoms.keys()) | set(c_atoms.keys())
    diff = {}
    for e in all_elems:
        d = c_atoms.get(e, 0) - f_atoms.get(e, 0)
        if d != 0:
            diff[e] = d
    return diff


def _categorize_discrepancy(row: pd.Series) -> str:
    """
    Categorize the formula vs COMPOSITION discrepancy.
    
    Categories:
    - 'rule_fix': Discrepancy caused by rule-based structure modification
    - 'salt_counterion': COMPOSITION includes counter-ion (Cl, Br, NO3, etc.)
    - 'protonation_H+': Only H difference (protonation state)
    - 'hydration': O and H difference consistent with water
    - 'carbon_skeleton': C count differs (structural difference)
    - 'other': Other or multiple causes
    """
    formula = str(row.get("formula", "") or "")
    composition = str(row.get("COMPOSITION", "") or "")
    rules = str(row.get("rules_applied", "") or "")
    
    if not formula or not composition:
        return "missing_data"
    
    diff = _compute_atom_diff(formula, composition)
    
    if not diff:
        return "match"
    
    # Check if rule was applied - likely cause of discrepancy
    if rules:
        return "rule_fix"
    
    # Check for salt counter-ions in COMPOSITION
    # Common counter-ions: Cl, Br, I, F (halides), NO3, ClO4, etc.
    salt_ions = []
    if diff.get("Cl", 0) > 0:
        salt_ions.append("Cl")
    if diff.get("Br", 0) > 0:
        salt_ions.append("Br")
    if diff.get("I", 0) > 0:
        salt_ions.append("I")
    if diff.get("F", 0) > 0:
        salt_ions.append("F")
    # Check for NO3 pattern (N+3, O+3 roughly)
    if diff.get("N", 0) > 0 and diff.get("O", 0) >= 3 * diff.get("N", 0):
        salt_ions.append("NO3")
    
    if salt_ions:
        return f"salt_counterion({','.join(salt_ions)})"
    
    # Check for hydration (water): O+n, H+2n
    o_diff = diff.get("O", 0)
    h_diff = diff.get("H", 0)
    other_diff = {k: v for k, v in diff.items() if k not in ("H", "O")}
    
    if not other_diff and o_diff > 0 and h_diff == 2 * o_diff:
        return f"hydration(+{o_diff}H2O)"
    if not other_diff and o_diff < 0 and h_diff == 2 * o_diff:
        return f"dehydration({o_diff}H2O)"
    
    # Check for protonation-only (H difference, no other atoms)
    if not other_diff and o_diff == 0 and h_diff != 0:
        if h_diff > 0:
            return f"protonation(+{h_diff}H)"
        else:
            return f"deprotonation({h_diff}H)"
    
    # Check for carbon skeleton differences
    c_diff = diff.get("C", 0)
    if c_diff != 0:
        # Format the full diff string
        diff_str = "; ".join(f"{k}:{v:+d}" for k, v in sorted(diff.items()))
        return f"carbon_skeleton({diff_str})"
    
    # Other heteroatom differences
    diff_str = "; ".join(f"{k}:{v:+d}" for k, v in sorted(diff.items()))
    return f"other({diff_str})"


def _format_atom_diff(formula: str, composition: str) -> str:
    """Format atom differences as a readable string."""
    diff = _compute_atom_diff(formula, composition)
    if not diff:
        return ""
    return "; ".join(f"{k}:{v:+d}" for k, v in sorted(diff.items()))


def generate_formula_mismatch_diagnostic(df: pd.DataFrame) -> pd.DataFrame:
    """Generate diagnostic for entries with formula vs composition mismatch."""
    mask = df["formula_comp_status"].isin(["different", "unparsed"])
    mismatch_df = df[mask].copy()
    
    # Add discrepancy analysis columns
    mismatch_df["discrepancy_category"] = mismatch_df.apply(_categorize_discrepancy, axis=1)
    mismatch_df["atom_diff"] = mismatch_df.apply(
        lambda r: _format_atom_diff(str(r.get("formula", "")), str(r.get("COMPOSITION", ""))),
        axis=1
    )
    
    # Select relevant columns
    cols = [
        "ligandenID", "name_ligand", "COMMON_NAME", "IUPAC_NAME",
        "formula", "COMPOSITION",
        "discrepancy_category", "atom_diff",
        "formula_comp_status", "formula_canonical", "composition_canonical",
        "SMILES", "InChI",
        "figure_definition", "figure_definition_charge",
        "rules_applied",
    ]
    
    diag_df = _filter_columns(mismatch_df, cols)
    
    # Log category breakdown
    if "discrepancy_category" in diag_df.columns:
        cat_counts = diag_df["discrepancy_category"].value_counts()
        log(f"[DIAG] Formula mismatch breakdown:")
        for cat, cnt in cat_counts.items():
            log(f"[DIAG]   {cat}: {cnt}")
    
    log(f"[DIAG] Formula mismatch: {len(diag_df):,} entries")
    
    return diag_df


def write_formula_mismatch_by_category(formula_df: pd.DataFrame, timestamp: str) -> Dict[str, Path]:
    """
    Write formula mismatch entries to category-based subfolders.
    
    Creates folder structure:
        DEBUG_rules/formula_mismatch/
            protonation/
                DIAG_protonation_+1H_*.csv
                DIAG_protonation_+2H_*.csv
            deprotonation/
                DIAG_deprotonation_-1H_*.csv
            carbon_skeleton/
                DIAG_carbon_skeleton_*.csv
            salt_counterion/
            rule_fix/
            hydration/
            other/
    
    Args:
        formula_df: DataFrame with discrepancy_category column
        timestamp: Timestamp string for file naming
        
    Returns:
        Dictionary mapping category to output paths
    """
    if "discrepancy_category" not in formula_df.columns:
        return {}
    
    # Create base folder
    base_dir = DEBUG_RULES_DIR / "formula_mismatch"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    output_files = {}
    
    # Group by base category for folder structure
    def get_base_category(cat: str) -> str:
        if "(" in cat:
            return cat.split("(")[0]
        return cat
    
    formula_df["_base_category"] = formula_df["discrepancy_category"].apply(get_base_category)
    
    # Process each base category
    for base_cat in formula_df["_base_category"].unique():
        if not base_cat or pd.isna(base_cat):
            continue
        
        # Create category subfolder - ensure it exists
        cat_dir = base_dir / base_cat
        try:
            cat_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log(f"[DIAG] Warning: Could not create {cat_dir}: {e}")
            continue
        
        # Get entries for this base category
        cat_mask = formula_df["_base_category"] == base_cat
        cat_df = formula_df[cat_mask].drop(columns=["_base_category"])
        
        # Get unique detailed categories within this base
        detailed_cats = cat_df["discrepancy_category"].unique()
        
        for detail_cat in detailed_cats:
            detail_mask = cat_df["discrepancy_category"] == detail_cat
            detail_df = cat_df[detail_mask].copy()
            
            if len(detail_df) == 0:
                continue
            
            # Create safe filename from category - be more aggressive with cleaning
            safe_name = str(detail_cat)
            safe_name = safe_name.replace("(", "_").replace(")", "")
            safe_name = safe_name.replace(";", "_").replace(":", "_")
            safe_name = safe_name.replace("+", "plus").replace("-", "minus")
            safe_name = safe_name.replace(" ", "").replace("__", "_")
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)  # Remove invalid filename chars
            
            filename = f"DIAG_{safe_name}_{timestamp}.csv"
            filepath = cat_dir / filename
            
            try:
                detail_df.to_csv(filepath, index=False)
                output_files[detail_cat] = filepath
            except Exception as e:
                log(f"[DIAG] Warning: Could not write {filepath.name}: {e}")
        
        log(f"[DIAG] Wrote {len(detailed_cats)} files to {base_cat}/ ({cat_df.shape[0]} entries)")
    
    # Write index summary for the folder
    summary_lines = [
        f"# Formula Mismatch by Category",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total entries:** {len(formula_df):,}",
        f"",
        f"## Category Folders",
        f"",
    ]
    
    for base_cat in sorted(formula_df["_base_category"].unique()):
        if not base_cat or pd.isna(base_cat):
            continue
        cnt = (formula_df["_base_category"] == base_cat).sum()
        summary_lines.append(f"- **{base_cat}/**: {cnt:,} entries")
    
    summary_path = base_dir / f"_INDEX_{timestamp}.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    
    log(f"[DIAG] Formula mismatch folder index -> {summary_path.name}")
    
    return output_files


def generate_multicore_inchi_diagnostic(df: pd.DataFrame) -> pd.DataFrame:
    """Generate diagnostic for entries with multi-component InChI after fixes."""
    # Check post-fix InChI for multi-component structures
    multi_mask = df["InChI"].apply(is_multi_component_inchi)
    multi_df = df[multi_mask].copy()
    
    # Add component count
    multi_df["inchi_component_count"] = multi_df["InChI"].apply(count_inchi_components)
    
    # Select relevant columns
    cols = [
        "ligandenID", "name_ligand", "COMMON_NAME", "IUPAC_NAME",
        "SMILES_before", "SMILES",
        "InChI_before", "InChI",
        "inchi_component_count",
        "pre_smiles_frag_count", "post_smiles_frag_count",
        "figure_definition", "figure_definition_charge",
        "rdkit_charge_before", "rdkit_charge_after",
        "rules_applied", "correction_applied",
    ]
    
    diag_df = _filter_columns(multi_df, cols)
    
    # Sort by component count descending
    if "inchi_component_count" in diag_df.columns:
        diag_df = diag_df.sort_values("inchi_component_count", ascending=False)
    
    log(f"[DIAG] Multi-component InChI (post-fix): {len(diag_df):,} entries")
    
    return diag_df


def generate_charge_mismatch_diagnostic(df: pd.DataFrame) -> pd.DataFrame:
    """Generate diagnostic for entries where charge still mismatches after fixes."""
    # Entries where validation failed
    mask = (df["validation_ok"] == False) | (df["figure_vs_molblock_charge_mismatch"] == True)
    mismatch_df = df[mask].copy()
    
    cols = [
        "ligandenID", "name_ligand", "COMMON_NAME", "IUPAC_NAME",
        "figure_definition_original", "figure_definition",
        "figure_definition_charge",
        "rdkit_charge_before", "rdkit_charge_after", "target_charge",
        "inchi_charge_value",
        "SMILES_before", "SMILES",
        "pre_smiles_frag_count", "post_smiles_frag_count",
        "rules_applied", "correction_applied",
        "validation_ok", "figure_vs_molblock_charge_mismatch",
    ]
    
    diag_df = _filter_columns(mismatch_df, cols)
    log(f"[DIAG] Charge mismatch (post-fix): {len(diag_df):,} entries")
    
    return diag_df


# =====================================================================
# MAIN DIAGNOSTIC WRITER
# =====================================================================

def write_all_diagnostics(df: pd.DataFrame, timestamp: str = None) -> Dict[str, Path]:
    """
    Write all diagnostic CSVs to the DEBUG_rules folder.
    
    Args:
        df: Full processed DataFrame
        timestamp: Optional timestamp string
        
    Returns:
        Dictionary mapping diagnostic names to output paths
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    # Create DEBUG_rules directory
    DEBUG_RULES_DIR.mkdir(parents=True, exist_ok=True)
    
    output_files = {}
    
    # 1. Rule-specific diagnostics
    rule_diags = generate_rule_diagnostics(df, timestamp)
    for rule_name, rule_df in rule_diags.items():
        if len(rule_df) > 0:
            filename = f"DIAG_{rule_name}_{timestamp}.csv"
            filepath = DEBUG_RULES_DIR / filename
            rule_df.to_csv(filepath, index=False)
            output_files[rule_name] = filepath
            log(f"[DIAG] Wrote {rule_name} diagnostic: {len(rule_df):,} rows -> {filepath.name}")
    
    # 2. Formula mismatch diagnostic
    formula_df = generate_formula_mismatch_diagnostic(df)
    if len(formula_df) > 0:
        filepath = DEBUG_RULES_DIR / f"DIAG_formula_mismatch_{timestamp}.csv"
        formula_df.to_csv(filepath, index=False)
        output_files["formula_mismatch"] = filepath
        log(f"[DIAG] Wrote formula mismatch: {len(formula_df):,} rows -> {filepath.name}")
        
        # 2b. Write category-based subfolders
        cat_files = write_formula_mismatch_by_category(formula_df, timestamp)
        output_files["formula_mismatch_by_category"] = cat_files
    
    # 3. Multi-component InChI diagnostic
    multi_df = generate_multicore_inchi_diagnostic(df)
    if len(multi_df) > 0:
        filepath = DEBUG_RULES_DIR / f"DIAG_multicore_inchi_{timestamp}.csv"
        multi_df.to_csv(filepath, index=False)
        output_files["multicore_inchi"] = filepath
        log(f"[DIAG] Wrote multi-core InChI: {len(multi_df):,} rows -> {filepath.name}")
    
    # 4. Charge mismatch diagnostic
    charge_df = generate_charge_mismatch_diagnostic(df)
    if len(charge_df) > 0:
        filepath = DEBUG_RULES_DIR / f"DIAG_charge_mismatch_{timestamp}.csv"
        charge_df.to_csv(filepath, index=False)
        output_files["charge_mismatch"] = filepath
        log(f"[DIAG] Wrote charge mismatch: {len(charge_df):,} rows -> {filepath.name}")
    
    # 5. Summary of all diagnostics
    summary_lines = [
        f"# HxL Pipeline Diagnostics Summary",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total rows processed:** {len(df):,}",
        f"",
        f"## Rule Application Summary",
        f"",
        f"| Rule | Entries Affected |",
        f"|------|------------------|",
    ]
    for rule_name, rule_df in rule_diags.items():
        summary_lines.append(f"| {rule_name} | {len(rule_df):,} |")
    
    # Add formula discrepancy breakdown with high-level summary first
    summary_lines.extend([
        f"",
        f"## Formula vs COMPOSITION Discrepancy Analysis",
        f"",
        f"Total mismatches: **{len(formula_df):,}**",
        f"",
    ])
    
    # Group categories for high-level summary
    if "discrepancy_category" in formula_df.columns:
        cat_counts = formula_df["discrepancy_category"].value_counts()
        
        # Aggregate by base category
        grouped = {}
        for cat, cnt in cat_counts.items():
            base_cat = cat.split("(")[0] if "(" in cat else cat
            grouped[base_cat] = grouped.get(base_cat, 0) + cnt
        
        # High-level summary table
        summary_lines.extend([
            f"### High-Level Summary",
            f"",
            f"| Category | Count | % of Mismatches | Description |",
            f"|----------|-------|-----------------|-------------|",
        ])
        
        category_descriptions = {
            "rule_fix": "Structure modified by rule-based fix (counter-ion removal, etc.)",
            "salt_counterion": "COMPOSITION includes salt counter-ion (Cl⁻, Br⁻, NO₃⁻, etc.)",
            "protonation": "COMPOSITION has extra H (protonated form)",
            "deprotonation": "Formula has extra H (InChI shows neutral/deprotonated)",
            "hydration": "Water of hydration difference",
            "dehydration": "Anhydrous vs hydrated form",
            "carbon_skeleton": "Carbon count differs (structural mismatch in source data)",
            "other": "Other heteroatom differences",
            "missing_data": "Missing formula or COMPOSITION data",
            "match": "Marked different but atoms actually match",
        }
        
        for base_cat in ["protonation", "deprotonation", "carbon_skeleton", "rule_fix", 
                         "salt_counterion", "hydration", "dehydration", "other", "match", "missing_data"]:
            cnt = grouped.get(base_cat, 0)
            if cnt > 0:
                pct = 100.0 * cnt / len(formula_df)
                desc = category_descriptions.get(base_cat, base_cat)
                summary_lines.append(f"| {base_cat} | {cnt:,} | {pct:.1f}% | {desc} |")
        
        # Detailed breakdown
        summary_lines.extend([
            f"",
            f"### Detailed Breakdown",
            f"",
            f"<details>",
            f"<summary>Click to expand full breakdown ({len(cat_counts)} unique patterns)</summary>",
            f"",
            f"| Category | Count |",
            f"|----------|-------|",
        ])
        
        for cat, cnt in cat_counts.items():
            summary_lines.append(f"| {cat} | {cnt:,} |")
        
        summary_lines.append(f"</details>")
    
    summary_lines.extend([
        f"",
        f"## Diagnostic Files",
        f"",
        f"| Category | Count | File |",
        f"|----------|-------|------|",
    ])
    for name, filepath in output_files.items():
        # Skip nested dicts (like formula_mismatch_by_category)
        if isinstance(filepath, dict):
            continue
        count = len(rule_diags.get(name, [])) if name in rule_diags else 0
        if name == "formula_mismatch":
            count = len(formula_df)
        elif name == "multicore_inchi":
            count = len(multi_df)
        elif name == "charge_mismatch":
            count = len(charge_df)
        # Handle filepath - might be string or Path
        fname = Path(filepath).name if filepath else "—"
        count_str = f"{count:,}" if isinstance(count, int) else str(count)
        summary_lines.append(f"| {name} | {count_str} | `{fname}` |")
    
    summary_path = DEBUG_RULES_DIR / f"DIAG_summary_{timestamp}.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    output_files["summary"] = summary_path
    log(f"[DIAG] Wrote diagnostic summary -> {summary_path.name}")
    
    return output_files


def generate_diagnostic_stats(df: pd.DataFrame) -> Dict[str, int]:
    """Generate statistics for diagnostic categories."""
    stats = {}
    
    # Rule counts
    rules_applied = df["rules_applied"].fillna("")
    for rule in ["Rule1", "Rule2", "Rule2b", "Rule3", "Rule4", "Rule4b", "Rule5", "Rule6"]:
        stats[f"diag_{rule.lower()}_count"] = int(rules_applied.str.contains(rule, regex=False).sum())
    
    # Formula mismatch
    stats["diag_formula_mismatch_count"] = int(df["formula_comp_status"].isin(["different", "unparsed"]).sum())
    
    # Multi-component InChI
    stats["diag_multicore_inchi_count"] = int(df["InChI"].apply(is_multi_component_inchi).sum())
    
    # Charge mismatch
    stats["diag_charge_mismatch_count"] = int(
        ((df["validation_ok"] == False) | (df["figure_vs_molblock_charge_mismatch"] == True)).sum()
    )
    
    return stats
