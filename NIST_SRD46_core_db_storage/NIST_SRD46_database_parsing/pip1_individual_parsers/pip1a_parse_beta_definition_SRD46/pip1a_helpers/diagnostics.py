"""
Diagnostics and reporting module for beta_definition parsing.
Provides comprehensive checks, failure categorization, and summary reporting.

Functions:
- Failure masks and classification
- Unbalanced cause summarization  
- EXTRA:* token counting
- Pre-parse residual analysis
- Tree-based elemental conservation checks
- Run summary printing
"""
from collections import Counter
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
import json

import pandas as pd

from .io_utils import print_debug, BD_PK
from .equation_builder import sides_to_nested_tree

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
VERBOSE_FLAG = True

def set_verbose(flag: bool):
    """Set global verbose flag."""
    global VERBOSE_FLAG
    VERBOSE_FLAG = flag

# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE MASKS
# ═══════════════════════════════════════════════════════════════════════════════
def build_failure_masks(df: pd.DataFrame, prefix: str = "beta_eq") -> Dict[str, pd.Series]:
    """
    Build boolean masks for various failure categories.
    
    Returns dict with masks:
    - empty_eq: equation is placeholder (1 ⇔ 1)
    - has_extras: balance contains EXTRA:* keys
    - ml_ok: M and L are balanced
    - ho_only: only H/O imbalance (or M/L/H/O all present)
    - ho_ratio_2to1: H:O ratio is 2:1 (water stoichiometry)
    - chem_only: only chemical elements (H/O/C/N/S/P/M/L)
    - tree_not_conserved: JSON tree elemental check failed
    """
    masks = {}
    
    # Get relevant columns
    sides_base = df.get(f"{prefix}_sides")
    eq_py = df.get(f"{prefix}_str_python", pd.Series(index=df.index, dtype=object))
    bal_final = df.get(f"{prefix}_balance_final", df.get(f"{prefix}_balance"))
    
    # Empty equation check
    def sides_empty(s, eqpy):
        try:
            if isinstance(eqpy, str) and eqpy.strip() in ("1 ⇔ 1", "1 <=> 1"):
                return True
            if not isinstance(s, dict):
                return True
            return (len(s.get("numerator") or []) == 0) and (len(s.get("denominator") or []) == 0)
        except Exception:
            return True
    
    if sides_base is not None:
        masks["empty_eq"] = pd.Series([
            sides_empty(sides_base.iloc[i], eq_py.iloc[i]) for i in range(len(df))
        ], index=df.index)
    else:
        masks["empty_eq"] = pd.Series(False, index=df.index)
    
    # EXTRA:* tokens check
    def has_extras_fn(d):
        return any(isinstance(k, str) and k.startswith("EXTRA:") for k in (d or {}).keys())
    
    if bal_final is not None:
        masks["has_extras"] = bal_final.apply(has_extras_fn)
    else:
        masks["has_extras"] = pd.Series(False, index=df.index)
    
    # Helper for getting numeric value from balance dict
    def gv(d, k):
        try:
            return float((d or {}).get(k, 0.0))
        except Exception:
            return 0.0
    
    if bal_final is not None:
        # M/L balanced check
        masks["ml_ok"] = bal_final.apply(lambda d: abs(gv(d, "M")) == 0.0 and abs(gv(d, "L")) == 0.0)
        
        # Chemical keys analysis
        chem_keys = bal_final.apply(lambda d: set((d or {}).keys()))
        masks["ho_only"] = chem_keys.apply(
            lambda ks: ks.issubset({"H", "O"}) or all(k in {"H", "O", "M", "L"} for k in ks)
        )
        masks["ho_ratio_2to1"] = bal_final.apply(
            lambda d: (abs(gv(d, "H")) == 2.0 * abs(gv(d, "O"))) and (gv(d, "O") != 0.0)
        )
        masks["chem_only"] = chem_keys.apply(
            lambda ks: ks.issubset({"H", "O", "C", "N", "S", "P", "M", "L"})
        )
    else:
        for key in ["ml_ok", "ho_only", "ho_ratio_2to1", "chem_only"]:
            masks[key] = pd.Series(False, index=df.index)
    
    # Tree elemental conservation check
    tree_col = f"{prefix}_element_conserved_tree"
    if tree_col in df.columns:
        masks["tree_not_conserved"] = ~df[tree_col].fillna(False)
    else:
        masks["tree_not_conserved"] = pd.Series(False, index=df.index)
    
    return masks


def select_balance_for_classification(row: pd.Series, prefix: str = "beta_eq") -> dict:
    """Select the best balance dict for classification (prefer final)."""
    bf = row.get(f"{prefix}_balance_final")
    if isinstance(bf, dict):
        return bf
    b = row.get(f"{prefix}_balance")
    return b if isinstance(b, dict) else {}


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
def classify_unbalanced_row(row: pd.Series, prefix: str = "beta_eq") -> str:
    """
    Classify the reason why an equation is unbalanced.
    
    Returns one of:
    - empty_equation
    - no_sides_parsed
    - tree_not_conserved
    - contains_EXTRA_tokens
    - ML_OK_HO_only_not_2_to_1
    - ML_OK_other_chem_mismatch
    - ML_not_balanced
    - unclassified
    """
    bal = select_balance_for_classification(row, prefix=prefix)
    
    def gv(k):
        try:
            return float(bal.get(k, 0.0))
        except Exception:
            return 0.0
    
    # Empty / unparsable first
    eqpy = row.get(f"{prefix}_str_python_final") or row.get(f"{prefix}_str_python")
    sides = row.get(f"{prefix}_sides")
    if isinstance(eqpy, str) and eqpy.strip() in ("1 ⇔ 1", "1 <=> 1"):
        return "empty_equation"
    if not isinstance(sides, dict) or ((sides.get("numerator") or []) == [] and (sides.get("denominator") or []) == []):
        return "no_sides_parsed"
    
    # Tree/element conservation failure
    tree_col = f"{prefix}_element_conserved_tree"
    if tree_col in row.index:
        tree_ok = bool(row.get(tree_col))
        if tree_ok is False:
            return "tree_not_conserved"
    
    # EXTRA tokens check
    has_extras = any(isinstance(k, str) and k.startswith("EXTRA") for k in (bal or {}).keys())
    ml_ok = abs(gv("M")) == 0.0 and abs(gv("L")) == 0.0
    chem_keys = set((bal or {}).keys())
    ho_only = chem_keys.issubset({"H", "O"}) or all(
        (k in {"H", "O", "M", "L"} and abs(gv(k)) == 0.0) for k in (bal or {}).keys()
    )
    ho_ratio_2to1 = (abs(gv("H")) == 2.0 * abs(gv("O"))) and (gv("O") != 0.0)
    
    if has_extras:
        return "contains_EXTRA_tokens"
    if ml_ok and ho_only and not ho_ratio_2to1:
        return "ML_OK_HO_only_not_2_to_1"
    if ml_ok and not ho_only and chem_keys.issubset({"H", "O", "C", "N", "S", "P", "M", "L"}):
        return "ML_OK_other_chem_mismatch"
    if not ml_ok:
        return "ML_not_balanced"
    return "unclassified"


def classify_unbalanced_simple(bal: dict, net_M: float, net_L: float, 
                                net_H: float, net_O: float) -> str:
    """
    Simplified classification based on balance dict and net values.
    Used for quick categorization in summary stats.
    """
    if not isinstance(bal, dict) or len(bal) == 0:
        return "empty_balance"
    
    extras = [k for k in bal.keys() if k not in ("M", "L", "H", "O", "C", "N", "S", "P")]
    if extras:
        return f"EXTRA:{','.join(sorted(extras))}"
    
    if net_M != 0:
        return f"net_M={int(net_M)}"
    if net_L != 0:
        return f"net_L={int(net_L)}"
    if net_H != 0 or net_O != 0:
        return f"net_H={int(net_H)},net_O={int(net_O)}"
    
    return "other"


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRA TOKEN COUNTING
# ═══════════════════════════════════════════════════════════════════════════════
def count_extra_tokens(bal_series: pd.Series, section_flag: str = "", top: int = 10) -> Counter:
    """
    Count EXTRA:* tokens across all balance dicts.
    Optionally print top results.
    """
    ctr = Counter()
    for d in bal_series.dropna():
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(k, str) and k.startswith("EXTRA:"):
                    ctr[k] += 1
    
    if ctr and VERBOSE_FLAG:
        print_debug(f"\n★ Top EXTRA:* tokens {section_flag}:")
        for k, v in ctr.most_common(top):
            print_debug(f"  {k:30s} {v}")
    
    return ctr


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════
def compute_summary_stats(df: pd.DataFrame, prefix: str = "beta_eq") -> Dict:
    """
    Compute comprehensive summary statistics for parsed DataFrame.
    
    Returns dict with:
    - total, balanced, unbalanced, empty counts
    - hit_rate, hit_rate_str
    - extra_token_counts (Counter)
    - reason_counts (Counter)
    """
    total = len(df)
    if total == 0:
        return {
            "total": 0, "balanced": 0, "unbalanced": 0, "empty": 0,
            "hit_rate": 0.0, "hit_rate_str": "0/0 (0.0%)",
            "extra_token_counts": Counter(),
            "reason_counts": Counter(),
        }
    
    # Conservation flags
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    balanced = int(cons_final.sum())
    unbalanced = total - balanced
    
    # Empty check
    masks = build_failure_masks(df, prefix)
    empty = int(masks.get("empty_eq", pd.Series(False, index=df.index)).sum())
    
    # Hit rate = balanced / (total - empty)
    denom = total - empty
    hit_rate = balanced / denom if denom > 0 else 0.0
    
    # EXTRA counters from final balance
    bal_final = df.get(f"{prefix}_balance_final", df.get(f"{prefix}_balance"))
    extra_ctr = Counter()
    if bal_final is not None:
        for d in bal_final.dropna():
            if isinstance(d, dict):
                for k in d.keys():
                    if isinstance(k, str) and k.startswith("EXTRA"):
                        extra_ctr[k] += 1
    
    # Failure reasons
    unb = df[~cons_final].copy()
    reason_counts = Counter()
    if not unb.empty:
        reasons = unb.apply(lambda r: classify_unbalanced_row(r, prefix), axis=1)
        reason_counts = Counter(reasons)
    
    return {
        "total": total,
        "balanced": balanced,
        "unbalanced": unbalanced,
        "empty": empty,
        "hit_rate": round(hit_rate * 100, 2),
        "hit_rate_str": f"{balanced}/{denom} ({hit_rate*100:.1f}%)",
        "extra_token_counts": extra_ctr,
        "reason_counts": reason_counts,
    }


def summarize_unbalanced_causes(df: pd.DataFrame, prefix: str = "beta_eq") -> Counter:
    """
    Summarize causes of unbalanced equations.
    Adds 'reason' column to df for unbalanced rows.
    Returns Counter of reasons.
    """
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    unbal_mask = ~cons_final
    unbal_df = df[unbal_mask]
    
    if unbal_df.empty:
        return Counter()
    
    # Use select_balance_for_classification
    def get_balance(row):
        bf = row.get(f"{prefix}_balance_final")
        if isinstance(bf, dict):
            return bf
        b = row.get(f"{prefix}_balance")
        return b if isinstance(b, dict) else {}
    
    reasons = []
    for i, row in unbal_df.iterrows():
        bal = get_balance(row)
        reason = classify_unbalanced_simple(
            bal,
            float(row.get("net_M", 0) or 0),
            float(row.get("net_L", 0) or 0),
            float(row.get("net_H", 0) or 0),
            float(row.get("net_O", 0) or 0),
        )
        reasons.append(reason)
    
    df.loc[unbal_mask, "reason"] = reasons
    return Counter(reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# ELEMENTAL CONSERVATION (TREE-BASED)
# ═══════════════════════════════════════════════════════════════════════════════
def element_mass_conserved_from_tree(tree: dict) -> bool:
    """
    Check if elemental mass is conserved in the tree structure.
    
    Tree should have structure:
    {
        "numerator": [{"species": ..., "power": ..., "components": {...}}, ...],
        "denominator": [...]
    }
    
    Components map element symbols to counts.
    Returns True if net element counts are zero.
    """
    if not isinstance(tree, dict):
        return True  # Can't check, assume OK
    
    net = Counter()
    
    def process_side(items, sign):
        for item in (items or []):
            if not isinstance(item, dict):
                continue
            power = item.get("power", 1)
            comps = item.get("components", {})
            if isinstance(comps, dict):
                for elem, count in comps.items():
                    try:
                        net[elem] += sign * power * float(count)
                    except (TypeError, ValueError):
                        pass
    
    process_side(tree.get("numerator", []), +1)
    process_side(tree.get("denominator", []), -1)
    
    # Check if all net counts are zero (within tolerance)
    return all(abs(v) < 1e-6 for v in net.values())


def check_tree_conservation(df: pd.DataFrame, prefix: str = "beta_eq") -> Tuple[int, int, List[int]]:
    """
    Check elemental conservation for all rows with tree data.
    
    Returns:
    - eligible: number of rows with tree data
    - violations: number of rows with conservation violations
    - examples_idx: list of row indices with violations (first 5)
    """
    eligible = 0
    violations = 0
    examples_idx = []
    
    tree_col = f"{prefix}_tree"
    sides_col = f"{prefix}_sides_final" if f"{prefix}_sides_final" in df.columns else f"{prefix}_sides"
    
    for i in range(len(df)):
        # Get tree
        tree = None
        if tree_col in df.columns:
            t = df[tree_col].iloc[i]
            if isinstance(t, dict):
                tree = t
        
        # Build from sides if needed
        if tree is None and sides_col in df.columns:
            s = df[sides_col].iloc[i]
            if isinstance(s, dict):
                tree = sides_to_nested_tree(s)
        
        if not isinstance(tree, dict):
            continue
        
        eligible += 1
        if not element_mass_conserved_from_tree(tree):
            violations += 1
            if len(examples_idx) < 5:
                examples_idx.append(i)
    
    return eligible, violations, examples_idx


# ═══════════════════════════════════════════════════════════════════════════════
# DETAILED UNBALANCED BREAKDOWN
# ═══════════════════════════════════════════════════════════════════════════════
def print_unbalanced_breakdown(df: pd.DataFrame, prefix: str = "beta_eq"):
    """
    Print detailed breakdown of unbalanced equations.
    Shows counts and examples for each failure category.
    """
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    unb = df[~cons_final].copy()
    
    if unb.empty:
        print_debug("\n✓ All rows balanced after processing. Great!")
        return unb
    
    # Build masks
    masks = build_failure_masks(unb, prefix=prefix)
    for name, series in masks.items():
        unb[name] = series
    
    print_debug("\n--- Unbalanced breakdown ---")
    print_debug(f"Total unbalanced (final): {len(unb)}")
    print_debug(f" - empty equations (1 ⇔ 1): {unb['empty_eq'].sum()}")
    print_debug(f" - with EXTRA:* tokens: {unb['has_extras'].sum()}")
    print_debug(f" - chem-only keys (H/O/C/N/S/P/M/L): {(unb['chem_only'] & ~unb['empty_eq']).sum()}")
    print_debug(f" - M/L balanced, H/O-only not 2:1: {(unb['ml_ok'] & unb['ho_only'] & ~unb['ho_ratio_2to1'] & ~unb['empty_eq']).sum()}")
    print_debug(f" - M/L balanced, other chem mismatch: {(unb['ml_ok'] & ~unb['ho_only'] & unb['chem_only'] & ~unb['empty_eq']).sum()}")
    print_debug(f" - M/L not balanced: {((~unb['ml_ok']) & (~unb['empty_eq'])).sum()}")
    
    return unb


def show_examples(df: pd.DataFrame, mask: pd.Series, title: str, prefix: str = "beta_eq", n: int = 5):
    """Show sample rows matching mask."""
    ex = df[mask]
    if ex.empty:
        return
    
    cols = [c for c in [
        "verkn_ligand_metalID", "beta_definitionID", "ligand_name_ligand", "metal_name_metal",
        f"{prefix}_str_python", f"{prefix}_balance",
        "water_adjust_n", "water_adjust_side",
        f"{prefix}_str_python_adjusted", f"{prefix}_balance_adjusted",
        "element_conserved_full_after_water"
    ] if c in df.columns]
    
    print_debug(f"\nExamples: {title} (n={len(ex)})")
    with pd.option_context("display.max_colwidth", 160, "display.width", 200):
        nn = min(n, len(ex))
        if nn > 0:
            print_debug(ex[cols].sample(n=nn, random_state=None).to_string(index=False))


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-PARSE RESIDUAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_preparse_residuals(df: pd.DataFrame, top: int = 10, sample: int = 5) -> Dict:
    """
    Analyze pre-parse residuals (raw -> eqn pass).
    
    Returns dict with:
    - n_with_residuals: count of rows with any residuals
    - fragment_counts: Counter of residual fragments
    """
    required_cols = ["preparse_residual_present", "preparse_residual_any"]
    if not all(c in df.columns for c in required_cols):
        return {"n_with_residuals": 0, "fragment_counts": Counter()}
    
    n_any = int(df["preparse_residual_present"].sum())
    
    # Build fragment frequency table
    raw_ctr = Counter()
    for s in df["preparse_residual_any"]:
        if isinstance(s, str) and s.strip():
            for tok in s.split():
                t = tok.strip(" ,;:+")
                if t:
                    raw_ctr[t] += 1
    
    if VERBOSE_FLAG and n_any > 0:
        print_debug(f"\n★ Pre-parse residuals (raw -> eqn):")
        print_debug(f"  Rows with any residuals: {n_any:,} ({n_any/max(len(df),1):6.2%})")
        
        if raw_ctr:
            print_debug(f"  Top residual fragments (n={top}):")
            for tok, cnt in raw_ctr.most_common(top):
                print_debug(f"    {tok:24s} {cnt}")
        
        # Show examples
        if sample > 0:
            ex_all = df[df["preparse_residual_present"]].copy()
            cols_pre = [c for c in [
                "beta_definitionID",
                "name_beta_definition_fixed",
                "preparse_residual_num",
                "preparse_residual_den",
                "preparse_residual_any",
            ] if c in ex_all.columns]
            nshow = min(sample, len(ex_all))
            if nshow:
                print_debug(f"\n  Examples: rows with pre-parse residuals (showing {nshow})")
                with pd.option_context("display.max_colwidth", 140, "display.width", 180):
                    print_debug(ex_all[cols_pre].sample(nshow, random_state=None).to_string(index=False))
    
    return {
        "n_with_residuals": n_any,
        "fragment_counts": raw_ctr,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SUMMARY PRINTER
# ═══════════════════════════════════════════════════════════════════════════════
def print_run_summary(
    df: pd.DataFrame,
    prefix: str = "beta_eq",
    sample_unbalanced: int = 10,
    show_preparse_residuals: bool = True,
    preparse_top: int = 10,
    preparse_sample: int = 5,
):
    """
    Print comprehensive run summary with all diagnostics.
    
    Organized sections:
    1. Run Summary (overall stats)
    2. Pre-parse residuals (raw -> eqn)
    3. Tree-based elemental conservation
    4. EXTRA:* token counts
    5. Failure breakdown statistics
    6. Sample unbalanced rows by category
    """
    total = len(df)
    if total == 0:
        print_debug("\n=== Run summary ===")
        print_debug("No rows to analyze.")
        return
    
    # ─────────────────────────────────────────────────────────────────────────
    # 1. RUN SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    cons_full = df.get("element_conserved_full", pd.Series(False, index=df.index)).fillna(False)
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    
    base_ok = int(cons_full.sum())
    final_ok = int(cons_final.sum())
    need_water = int((~cons_full).sum())
    
    # Water adjustment counts
    adopted = df.get("water_fix_applied", pd.Series(False, index=df.index)).fillna(False)
    applied_water = int(adopted.sum())
    suggested = int(df.get("water_adjust_n", pd.Series(index=df.index)).notna().sum())
    
    # Pre-parse residuals count
    n_pre_any = int(df.get("preparse_residual_present", pd.Series(False, index=df.index)).sum())
    
    print_debug("\n" + "="*70)
    print_debug("RUN SUMMARY")
    print_debug("="*70)
    print_debug(f"Rows analyzed:                 {total:,}")
    print_debug(f"Balanced (base):               {base_ok:,}  ({base_ok/total:6.2%})")
    print_debug(f"Balanced (final):              {final_ok:,}  ({final_ok/total:6.2%})")
    print_debug(f"Needed water check:            {need_water:,}")
    print_debug(f"Water suggested (any):         {suggested:,}")
    print_debug(f"Balanced by water (adopted):   {applied_water:,}")
    print_debug(f"Rows with pre-parse residuals: {n_pre_any:,}  ({n_pre_any/max(total,1):6.2%})")
    
    # Tree conservation summary
    tree_col = f"{prefix}_element_conserved_tree"
    if tree_col in df.columns:
        has_tree = df[tree_col].notna()
        n_tree_rows = int(has_tree.sum())
        n_tree_ok = int(df.loc[has_tree, tree_col].fillna(False).sum())
        n_tree_fail = n_tree_rows - n_tree_ok
        print_debug(f"Tree-conserved (JSON):         {n_tree_ok:,} / {n_tree_rows:,} ({n_tree_ok/max(n_tree_rows,1):6.2%})")
        print_debug(f"Tree violations:               {n_tree_fail:,} / {n_tree_rows:,}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # 2. PRE-PARSE RESIDUALS (raw -> eqn)
    # ─────────────────────────────────────────────────────────────────────────
    if show_preparse_residuals and "preparse_residual_any" in df.columns:
        print_debug("\n" + "-"*70)
        print_debug("★ PRE-PARSE RESIDUALS (raw → eqn)")
        print_debug("-"*70)
        print_debug(f"Rows with any residuals: {n_pre_any:,} ({n_pre_any/max(total,1):6.2%})")
        
        # Build fragment frequency table
        raw_ctr = Counter()
        for s in df["preparse_residual_any"]:
            if isinstance(s, str) and s.strip():
                for tok in s.split():
                    t = tok.strip(" ,;:+")
                    if t:
                        raw_ctr[t] += 1
        
        if raw_ctr:
            print_debug(f"\nTop residual fragments (n={preparse_top}):")
            for tok, cnt in raw_ctr.most_common(preparse_top):
                print_debug(f"  {tok:28s} {cnt:4d}")
        
        # Examples
        if VERBOSE_FLAG and n_pre_any > 0 and preparse_sample > 0:
            ex_all = df[df["preparse_residual_present"]].copy()
            cols_pre = [c for c in [
                "beta_definitionID",
                "name_beta_definition_fixed",
                "preparse_residual_num",
                "preparse_residual_den",
            ] if c in ex_all.columns]
            nshow = min(preparse_sample, len(ex_all))
            if nshow and cols_pre:
                print_debug(f"\nExamples: rows with pre-parse residuals (showing {nshow})")
                with pd.option_context("display.max_colwidth", 100, "display.width", 180):
                    print_debug(ex_all[cols_pre].sample(nshow, random_state=42).to_string(index=False))
    
    # ─────────────────────────────────────────────────────────────────────────
    # 3. ELEMENTAL MASS-CONSERVATION (tree-based)
    # ─────────────────────────────────────────────────────────────────────────
    eligible, violations, examples_idx = check_tree_conservation(df, prefix)
    if eligible > 0:
        print_debug("\n" + "-"*70)
        print_debug("★ ELEMENTAL MASS-CONSERVATION (tree-based)")
        print_debug("-"*70)
        print_debug(f"Eligible rows with tree:       {eligible:,}")
        print_debug(f"Violations (not conservative): {violations:,} ({violations/max(eligible,1):6.2%})")
        
        if VERBOSE_FLAG and examples_idx:
            cols = [c for c in [
                "beta_definitionID", "name_beta_definition_fixed",
                f"{prefix}_str_python_final", f"{prefix}_balance_final",
            ] if c in df.columns]
            if cols:
                print_debug("\nExamples with elemental non-conservation (first 5):")
                with pd.option_context("display.max_colwidth", 100, "display.width", 180):
                    print_debug(df.iloc[examples_idx][cols].to_string(index=False))
    
    # ─────────────────────────────────────────────────────────────────────────
    # 4. EXTRA:* TOKEN COUNTS
    # ─────────────────────────────────────────────────────────────────────────
    stats = compute_summary_stats(df, prefix)
    extra_ctr = stats["extra_token_counts"]
    if extra_ctr:
        print_debug("\n" + "-"*70)
        print_debug("★ TOP EXTRA:* TOKENS (all data)")
        print_debug("-"*70)
        for k, v in extra_ctr.most_common(10):
            print_debug(f"  {k:28s} {v:4d}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # 5. FAILURE BREAKDOWN STATISTICS (final)
    # ─────────────────────────────────────────────────────────────────────────
    unb = df[~cons_final].copy()
    n_unb = len(unb)
    
    print_debug("\n" + "-"*70)
    print_debug("★ FAILURE BREAKDOWN STATISTICS (final)")
    print_debug("-"*70)
    print_debug(f"Total unbalanced: {n_unb:,}")
    
    if n_unb > 0:
        # Add reason column if not present
        if "reason" not in unb.columns:
            unb["reason"] = unb.apply(lambda r: classify_unbalanced_row(r, prefix), axis=1)
        
        reason_counts = Counter(unb["reason"])
        
        # Print categorized breakdown
        def _p(label):
            n = int(reason_counts.get(label, 0))
            pct = n / max(n_unb, 1)
            print_debug(f"  {label:36s} {n:6d} ({pct:6.2%})")
        
        _p("empty_equation")
        _p("no_sides_parsed")
        _p("contains_EXTRA_tokens")
        _p("ML_OK_HO_only_not_2_to_1")
        _p("ML_OK_other_chem_mismatch")
        _p("ML_not_balanced")
        _p("tree_not_conserved")
        _p("unclassified")
        
        # Count with pre-parse residuals
        if "preparse_residual_present" in df.columns:
            pre_flag_unb = df.loc[unb.index, "preparse_residual_present"].fillna(False)
            n_unb_pre = int(pre_flag_unb.sum())
            print_debug(f"  with pre-parse residuals           {n_unb_pre:6d} ({n_unb_pre/max(n_unb,1):6.2%})")
        
        # Count with tree violations
        if f"{prefix}_element_conserved_tree" in unb.columns:
            n_tree_fail_unb = int((~unb[f"{prefix}_element_conserved_tree"].fillna(False)).sum())
            print_debug(f"  with tree/element non-conservation {n_tree_fail_unb:6d} ({n_tree_fail_unb/max(n_unb,1):6.2%})")
    
    # ─────────────────────────────────────────────────────────────────────────
    # 6. SAMPLE UNBALANCED ROWS
    # ─────────────────────────────────────────────────────────────────────────
    if VERBOSE_FLAG and n_unb > 0 and sample_unbalanced > 0:
        print_debug("\n" + "-"*70)
        print_debug(f"★ SAMPLE UNBALANCED ROWS (n={n_unb:,}, showing {min(sample_unbalanced, n_unb)})")
        print_debug("-"*70)
        
        cols = [c for c in [
            "beta_definitionID", "name_beta_definition_fixed",
            f"{prefix}_str_python", "reason"
        ] if c in unb.columns]
        
        if cols:
            nn = min(sample_unbalanced, n_unb)
            with pd.option_context("display.max_colwidth", 80, "display.width", 180):
                print_debug(unb[cols].head(nn).to_string(index=False))
        
        # Helper to print examples by reason label
        def _print_cat_sample(reason_label, max_n=3):
            if "reason" not in unb.columns:
                return
            ex = unb[unb["reason"] == reason_label]
            if ex.empty:
                return
            nshow = min(max_n, len(ex))
            ccols = [c for c in [
                "beta_definitionID", "name_beta_definition_fixed",
                f"{prefix}_str_python", f"{prefix}_balance"
            ] if c in ex.columns]
            if ccols:
                print_debug(f"\n  ── {reason_label} (n={len(ex)}, showing {nshow}) ──")
                with pd.option_context("display.max_colwidth", 80, "display.width", 180):
                    print_debug(ex[ccols].head(nshow).to_string(index=False))
        
        # Show examples for key failure categories
        _print_cat_sample("contains_EXTRA_tokens", 3)
        _print_cat_sample("ML_not_balanced", 3)
        _print_cat_sample("tree_not_conserved", 3)
    
    # ─────────────────────────────────────────────────────────────────────────
    # FINAL SUMMARY BOX
    # ─────────────────────────────────────────────────────────────────────────
    print_debug("\n" + "="*70)
    print_debug("FINAL SUMMARY")
    print_debug("="*70)
    print_debug(f"  Total rows:      {total:,}")
    print_debug(f"  Balanced:        {final_ok:,}")
    print_debug(f"  Unbalanced:      {n_unb:,}")
    empty_count = int(stats.get("empty", 0))
    denom = total - empty_count
    hit_rate = final_ok / denom if denom > 0 else 0.0
    print_debug(f"  Hit rate:        {final_ok}/{denom} ({hit_rate*100:.1f}%)")
    print_debug("="*70)


# ═══════════════════════════════════════════════════════════════════════════════
# LOG WRITING
# ═══════════════════════════════════════════════════════════════════════════════
def write_summary_log(
    df: pd.DataFrame,
    log_path: Path,
    prefix: str = "beta_eq",
):
    """Write summary statistics to a log file."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    stats = compute_summary_stats(df, prefix)
    
    lines = [
        f"Beta Definition Parsing Summary",
        f"Generated: {datetime.now().isoformat()}",
        f"",
        f"Total rows:    {stats['total']}",
        f"Balanced:      {stats['balanced']}",
        f"Unbalanced:    {stats['unbalanced']}",
        f"Empty:         {stats['empty']}",
        f"Hit rate:      {stats['hit_rate_str']}",
        f"",
        f"EXTRA tokens:",
    ]
    
    for k, v in stats["extra_token_counts"].most_common(20):
        lines.append(f"  {k}: {v}")
    
    lines.append("")
    lines.append("Failure reasons:")
    for k, v in stats["reason_counts"].most_common(20):
        lines.append(f"  {k}: {v}")
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print_debug(f"Wrote summary log → {log_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION REPORT
# ═══════════════════════════════════════════════════════════════════════════════
def generate_validation_report(
    df: pd.DataFrame,
    output_path: Path,
    prefix: str = "beta_eq",
) -> pd.DataFrame:
    """
    Generate a CSV validation report with row-level diagnostics.
    
    Returns DataFrame with validation columns.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = pd.DataFrame(index=df.index)
    report[BD_PK] = df.get(BD_PK)
    report["name_beta_definition_fixed"] = df.get("name_beta_definition_fixed")
    report["equation_python"] = df.get(f"{prefix}_str_python_final", df.get(f"{prefix}_str_python"))
    report["element_conserved_final"] = df.get("element_conserved_final", False)
    
    # Add failure masks
    masks = build_failure_masks(df, prefix)
    report["is_empty"] = masks.get("empty_eq", False)
    report["has_extras"] = masks.get("has_extras", False)
    report["ml_ok"] = masks.get("ml_ok", True)
    report["tree_not_conserved"] = masks.get("tree_not_conserved", False)
    
    # Add reason if unbalanced
    cons_final = df.get("element_conserved_final", pd.Series(False, index=df.index)).fillna(False)
    report["reason"] = ""
    unbal_idx = ~cons_final
    if unbal_idx.any():
        reasons = df.loc[unbal_idx].apply(lambda r: classify_unbalanced_row(r, prefix), axis=1)
        report.loc[unbal_idx, "reason"] = reasons
    
    report.to_csv(output_path, index=False, encoding="utf-8-sig")
    print_debug(f"Wrote validation report → {output_path}")
    
    return report
