"""
diagnostics.py - Statistics and summary generation for HxL pipeline.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict
import pandas as pd

from .config import MOL_DATA_CSV, LIGANDEN_CSV, BUILD_DIR
from .logging_utils import log
from .rdkit_setup import RDKit_OK


def manual_review_reason(row: pd.Series) -> str:
    """
    Generate a reason string for rows needing manual review.
    
    Args:
        row: DataFrame row with validation flags
        
    Returns:
        Semicolon-separated reason string
    """
    reasons = []
    
    if row.get("figure_vs_molblock_charge_mismatch") is True:
        reasons.append("fig_vs_molblock_before_mismatch")
    
    if row.get("validation_ok") is False:
        reasons.append("postfix_validation_failed")
    
    st = row.get("formula_comp_status")
    if st in ("different", "unparsed"):
        reasons.append(f"formula_{st}")
    
    if pd.isna(row.get("target_charge")):
        reasons.append("missing_target_charge")
    
    return "; ".join(reasons)


def compute_debug_stats(out: pd.DataFrame) -> Dict[str, object]:
    """
    Compute statistics for the HxL parse run.
    
    Args:
        out: Processed DataFrame
        
    Returns:
        Dictionary of statistics
    """
    n = len(out)

    def cnt(mask):
        return int(pd.Series(mask).fillna(False).sum())

    stats = {}
    stats["total_rows"] = n
    stats["rdkit_available"] = bool(RDKit_OK)

    # ================================================================
    # PLACEHOLDER TRACKING (entries with "*" from pip1c-2 enrichment)
    # ================================================================
    # Count rows where pip1c-2 used "*" as placeholder for failed enrichment
    inchi_placeholder = (out["InChI"] == "*") if "InChI" in out.columns else pd.Series([False] * n)
    smiles_placeholder = (out["SMILES"] == "*") if "SMILES" in out.columns else pd.Series([False] * n)
    composition_placeholder = (out["COMPOSITION"] == "*") if "COMPOSITION" in out.columns else pd.Series([False] * n)
    
    # Any placeholder = entry from pip1c-2 that couldn't be enriched
    any_placeholder = (inchi_placeholder | smiles_placeholder | composition_placeholder)
    
    stats["inchi_placeholder_count"] = int(inchi_placeholder.sum())
    stats["smiles_placeholder_count"] = int(smiles_placeholder.sum())
    stats["composition_placeholder_count"] = int(composition_placeholder.sum())
    stats["any_placeholder_count"] = int(any_placeholder.sum())
    stats["truly_enriched_from_pip2"] = n - int(any_placeholder.sum())

    # Charge comparison stats
    has_fig = out["figure_definition_charge"].notna()
    has_mb_before = out["rdkit_charge_before"].notna()
    both_charge = (has_fig & has_mb_before)
    same_charge = both_charge & (out["figure_vs_molblock_charge_same"] == True)
    diff_charge = both_charge & (out["figure_vs_molblock_charge_mismatch"] == True)

    stats["charge_both_present"] = cnt(both_charge)
    stats["charge_same_count"] = cnt(same_charge)
    stats["charge_diff_count"] = cnt(diff_charge)

    stats["inchi_charge_present"] = int(out["inchi_charge_value"].notna().sum())
    stats["smiles_poly_before"] = int((out["pre_smiles_frag_count"].fillna(1) != 1).sum())
    stats["smiles_poly_after"] = int((out["post_smiles_frag_count"].fillna(1) != 1).sum())

    # Formula comparison stats
    status = out["formula_comp_status"].fillna("missing")
    for key in ("same", "different", "unparsed", "missing"):
        stats[f"formula_comp_{key}"] = int((status == key).sum())

    # ================================================================
    # PIPELINE SUCCESS - Distinguish placeholder vs truly processed
    # ================================================================
    # Pipeline success from pip1c-3's perspective
    stats["pipeline_success_count"] = cnt(out["pipeline_success"] == True)
    stats["needs_manual_review_count"] = cnt(out["needs_manual_review"] == True)
    
    # TRUE SUCCESS: Pipeline success AND not a placeholder entry
    truly_processed = (out["pipeline_success"] == True) & (~any_placeholder)
    stats["truly_processed_success_count"] = cnt(truly_processed)
    
    # Placeholder entries that went through pipeline
    placeholder_processed = (out["pipeline_success"] == True) & any_placeholder
    stats["placeholder_passed_through_count"] = cnt(placeholder_processed)

    # Rule usage stats
    corr = out["correction_applied"].fillna("")
    stats["rule1_used"] = int(corr.str.contains("Rule1", regex=False).sum())
    stats["rule2_used"] = int(corr.str.contains("Rule2", regex=False).sum())
    stats["rule2b_used"] = int(corr.str.contains("Rule2b", regex=False).sum())
    stats["rule3_used"] = int(corr.str.contains("Rule3", regex=False).sum())
    stats["rule4_used"] = int(corr.str.contains("Rule4", regex=False).sum())
    stats["rule4b_used"] = int(corr.str.contains("Rule4b", regex=False).sum())
    stats["rule5_used"] = int(corr.str.contains("Rule5", regex=False).sum())
    stats["rule6_used"] = int(corr.str.contains("Rule6", regex=False).sum())

    # Missing data stats (empty or null)
    stats["missing_molblock"] = int(out["molblock"].isna().sum() + (out["molblock"] == "").sum())
    stats["missing_smiles"] = int(out["SMILES"].isna().sum() + (out["SMILES"] == "").sum())
    stats["missing_figure_definition"] = int(out["figure_definition"].isna().sum() + (out["figure_definition"] == "").sum())

    # Rates
    def rate(num, den):
        return f"{(num / den * 100):.2f}%" if den else "n/a"

    stats["charge_same_rate"] = rate(stats["charge_same_count"], stats["charge_both_present"])
    stats["pipeline_success_rate"] = rate(stats["pipeline_success_count"], n)
    
    # TRUE SUCCESS RATE: Only entries that were actually enriched AND processed successfully
    stats["true_enrichment_rate"] = rate(stats["truly_processed_success_count"], n)
    stats["placeholder_rate"] = rate(stats["any_placeholder_count"], n)

    return stats


def generate_summary_markdown(stats: Dict, out_path: Path) -> None:
    """
    Generate a markdown summary of the HxL parse run.
    
    Args:
        stats: Statistics dictionary from compute_debug_stats
        out_path: Path to write the markdown file
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = stats.get("total_rows", 0)
    success = stats.get("pipeline_success_count", 0)
    manual = stats.get("needs_manual_review_count", 0)
    
    # True enrichment stats (excluding placeholder entries)
    truly_enriched = stats.get("truly_enriched_from_pip2", 0)
    truly_processed = stats.get("truly_processed_success_count", 0)
    placeholder_count = stats.get("any_placeholder_count", 0)
    placeholder_passed = stats.get("placeholder_passed_through_count", 0)
    
    # Rates
    pipeline_rate = (success / n * 100) if n > 0 else 0.0
    true_rate = (truly_processed / n * 100) if n > 0 else 0.0
    placeholder_rate = (placeholder_count / n * 100) if n > 0 else 0.0

    lines = [
        f"# Liganden + Molfile HxL Parse Pipeline Summary (pip1c-3)",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Configuration",
        f"",
        f"| Setting | Value |",
        f"|---------|-------|",
        f"| Mol Data Input | `{MOL_DATA_CSV}` |",
        f"| Liganden Input | `{LIGANDEN_CSV}` |",
        f"| Build Directory | `{BUILD_DIR}` |",
        f"",
        f"## Enrichment Quality (from pip1c-2)",
        f"",
        f"| Metric | Count | Percentage |",
        f"|--------|-------|------------|",
        f"| **Total Rows** | {n:,} | 100% |",
        f"| ✅ Truly Enriched (valid InChI/SMILES/COMPOSITION) | {truly_enriched:,} | {(truly_enriched/n*100) if n else 0:.2f}% |",
        f"| ⚠️ Placeholder ('*') entries | {placeholder_count:,} | {placeholder_rate:.2f}% |",
        f"",
        f"### Placeholder Breakdown",
        f"",
        f"| Column | Placeholder ('*') Count |",
        f"|--------|-------------------------|",
        f"| InChI = '*' | {stats.get('inchi_placeholder_count', 0):,} |",
        f"| SMILES = '*' | {stats.get('smiles_placeholder_count', 0):,} |",
        f"| COMPOSITION = '*' | {stats.get('composition_placeholder_count', 0):,} |",
        f"",
        f"## Pipeline Results (pip1c-3)",
        f"",
        f"| Metric | Count | Percentage |",
        f"|--------|-------|------------|",
        f"| **Total Rows Processed** | {n:,} | 100% |",
        f"| Pipeline Success (all rows) | {success:,} | {pipeline_rate:.2f}% |",
        f"| ✅ **Truly Processed Success** (enriched + processed) | {truly_processed:,} | {true_rate:.2f}% |",
        f"| ⚠️ Placeholder entries passed through | {placeholder_passed:,} | {(placeholder_passed/n*100) if n else 0:.2f}% |",
        f"| Needs Manual Review | {manual:,} | {(manual/n*100) if n else 0:.2f}% |",
        f"",
        f"## Charge Analysis",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Both fig & molblock charge present | {stats.get('charge_both_present', 0):,} |",
        f"| Charge same | {stats.get('charge_same_count', 0):,} |",
        f"| Charge different | {stats.get('charge_diff_count', 0):,} |",
        f"| InChI charge present | {stats.get('inchi_charge_present', 0):,} |",
        f"",
        f"## Rules Applied",
        f"",
        f"| Rule | Count |",
        f"|------|-------|",
        f"| Rule1 (desalt) | {stats.get('rule1_used', 0):,} |",
        f"| Rule2 (cyanide) | {stats.get('rule2_used', 0):,} |",
        f"| Rule2b (cyanometalate) | {stats.get('rule2b_used', 0):,} |",
        f"| Rule3 (polyanions) | {stats.get('rule3_used', 0):,} |",
        f"| Rule4 (desalted cation) | {stats.get('rule4_used', 0):,} |",
        f"| Rule4b (post-desalt) | {stats.get('rule4b_used', 0):,} |",
        f"| Rule5 (superatom) | {stats.get('rule5_used', 0):,} |",
        f"| Rule6 (known entries) | {stats.get('rule6_used', 0):,} |",
        f"",
        f"## Formula Analysis",
        f"",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| Same | {stats.get('formula_comp_same', 0):,} |",
        f"| Different | {stats.get('formula_comp_different', 0):,} |",
        f"| Unparsed | {stats.get('formula_comp_unparsed', 0):,} |",
        f"| Missing | {stats.get('formula_comp_missing', 0):,} |",
        f"",
        f"## Missing Data",
        f"",
        f"| Column | Missing/Empty Count |",
        f"|--------|---------------------|",
        f"| molblock | {stats.get('missing_molblock', 0):,} |",
        f"| SMILES | {stats.get('missing_smiles', 0):,} |",
        f"| figure_definition | {stats.get('missing_figure_definition', 0):,} |",
        f"",
        f"## Output Files",
        f"",
        f"- `liganden_moldata_HxL_parsed.csv` - Final parsed output",
        f"- `FAILED_HxL.csv` - Rows needing manual review",
        f"- `debug.csv` - Full debug output",
        f"- Log file - Processing log",
        f"",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log(f"[SUMMARY] Wrote markdown summary -> {out_path}")


def validate_exported_csv(csv_path: Path, expected_cols: list, expected_rows: int) -> tuple:
    """
    Validate the exported CSV file for data integrity.
    
    Performs the following checks:
    1. File exists and is readable
    2. All expected columns are present
    3. No unexpected columns
    4. Row count matches expected
    5. No duplicate ligandenID values
    6. ligandenID column has no nulls
    7. Key columns have reasonable non-null rates
    
    Args:
        csv_path: Path to the exported CSV file
        expected_cols: List of expected column names
        expected_rows: Expected number of rows
        
    Returns:
        tuple: (passed: bool, errors: list[str])
    """
    errors = []
    
    # Check 1: File exists
    if not csv_path.exists():
        errors.append(f"Output file does not exist: {csv_path}")
        return False, errors
    
    # Check 2: File is readable
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except Exception as e:
        errors.append(f"Failed to read CSV: {e}")
        return False, errors
    
    log(f"[VALIDATION] Reading exported CSV: {len(df):,} rows, {len(df.columns)} columns")
    
    # Check 3: All expected columns present
    missing_cols = set(expected_cols) - set(df.columns)
    if missing_cols:
        errors.append(f"Missing expected columns: {sorted(missing_cols)}")
    
    # Check 4: No unexpected columns
    extra_cols = set(df.columns) - set(expected_cols)
    if extra_cols:
        errors.append(f"Unexpected columns found: {sorted(extra_cols)}")
    
    # Check 5: Row count matches
    if len(df) != expected_rows:
        errors.append(f"Row count mismatch: expected {expected_rows:,}, got {len(df):,}")
    
    # Check 6: Duplicate ligandenID (this IS an error - each ligand should be unique)
    if 'ligandenID' in df.columns:
        dup_count = df['ligandenID'].duplicated().sum()
        if dup_count > 0:
            dup_ids = df.loc[df['ligandenID'].duplicated(keep=False), 'ligandenID'].unique().tolist()
            errors.append(f"Duplicate ligandenID values found: {dup_count:,} duplicates for IDs: {dup_ids}")
        
        # Check 7: No null ligandenID (this IS an error)
        null_count = df['ligandenID'].isna().sum()
        if null_count > 0:
            errors.append(f"Null ligandenID values found: {null_count:,}")
    
    # Check 8: Key columns have reasonable non-null rates
    key_cols_check = {
        'molblock': 0.95,      # At least 95% should have molblock
        'InChI': 0.95,         # At least 95% should have InChI
        'SMILES': 0.95,        # At least 95% should have SMILES
    }
    for col, min_rate in key_cols_check.items():
        if col in df.columns:
            non_null_rate = df[col].notna().mean()
            if non_null_rate < min_rate:
                errors.append(f"Column '{col}' has low non-null rate: {non_null_rate:.1%} (expected >= {min_rate:.0%})")
    
    # Check 9: Verify figure_definition_parsed format (should be HxL or similar)
    if 'figure_definition_parsed' in df.columns:
        valid_pattern = df['figure_definition_parsed'].str.match(r'^H\d*L\d*$', na=True)
        invalid_count = (~valid_pattern).sum()
        if invalid_count > 0:
            # This is a warning, not necessarily an error (some may have complex formats)
            log(f"[VALIDATION] Note: {invalid_count:,} rows have non-standard figure_definition_parsed format")
    
    # Check 10: Verify charge values are reasonable integers
    if 'figure_definition_charge' in df.columns:
        charge_col = df['figure_definition_charge'].dropna()
        if len(charge_col) > 0:
            # Check if charges are within reasonable range (-10 to +10)
            out_of_range = ((charge_col < -10) | (charge_col > 10)).sum()
            if out_of_range > 0:
                log(f"[VALIDATION] Note: {out_of_range:,} rows have unusual charge values (outside -10 to +10)")
    
    # Summary
    passed = len(errors) == 0
    
    if passed:
        log(f"[VALIDATION] ✓ Column check: {len(df.columns)} columns match expected")
        log(f"[VALIDATION] ✓ Row count: {len(df):,} rows")
        log(f"[VALIDATION] ✓ No null ligandenID values")
        log(f"[VALIDATION] ✓ No duplicate ligandenID values")
        log(f"[VALIDATION] ✓ Key columns have expected non-null rates")
    
    return passed, errors
