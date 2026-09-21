"""
I/O utilities for beta_definition parsing.
Handles file loading, debug printing, and DataFrame augmentation.
"""
from pathlib import Path
from typing import Optional, Sequence, Union, List
import pandas as pd
import json
import ast

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
BD_PK = "beta_definitionID"
PLACEHOLDER_DEFAULT = "*"

# ═══════════════════════════════════════════════════════════════════════════════
# DEBUG PRINTING
# ═══════════════════════════════════════════════════════════════════════════════
_DEBUG_LOG_PATH: Optional[Path] = None

def set_debug_log(path: Optional[Path]):
    """Set global debug log path."""
    global _DEBUG_LOG_PATH
    _DEBUG_LOG_PATH = path

def print_debug(*args, **kwargs):
    """Print to console and optionally append to log file."""
    msg = " ".join(str(a) for a in args)
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))
    if _DEBUG_LOG_PATH:
        try:
            _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(msg.rstrip("\n") + "\n")
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# FILE LOADING
# ═══════════════════════════════════════════════════════════════════════════════
def load_beta_definition(
    file_path: Union[str, Path],
    *,
    sep: str = ",",
    parse_dates: Optional[Sequence[str]] = ("Acc_feld",),
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """Load beta_definition CSV with proper NA handling."""
    df = pd.read_csv(
        file_path,
        sep=sep,
        encoding=encoding,
        na_values=[r"\N"],
        parse_dates=list(parse_dates) if parse_dates else False,
        engine="python"
    )
    return df

def load_csv_safe(path: Path, encoding: str = "utf-8-sig") -> pd.DataFrame:
    """Load CSV with encoding fallback."""
    try:
        return pd.read_csv(path, encoding=encoding, low_memory=False)
    except Exception:
        return pd.read_csv(path, encoding="latin1", low_memory=False)

# ═══════════════════════════════════════════════════════════════════════════════
# JSON COLUMN PARSING
# ═══════════════════════════════════════════════════════════════════════════════
def maybe_parse_json_columns(df: pd.DataFrame, candidate_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Parse JSON or Python-literal strings back into Python objects."""
    out = df.copy()

    def is_jsonish(s: str) -> bool:
        return isinstance(s, str) and len(s) > 0 and s.strip()[:1] in ("[", "{")

    if candidate_cols is None:
        candidate_cols = []
        for c in out.columns:
            if out[c].dtype == "object":
                sample = out[c].dropna().astype(str).head(50)
                if len(sample) and sample.apply(is_jsonish).any():
                    candidate_cols.append(c)

    if "beta_definition_eqn_formula" in out.columns and "beta_definition_eqn_formula" not in candidate_cols:
        candidate_cols.append("beta_definition_eqn_formula")

    def safe_load(val):
        if not isinstance(val, str) or not is_jsonish(val):
            return val
        try:
            return json.loads(val.strip())
        except Exception:
            try:
                return ast.literal_eval(val.strip())
            except Exception:
                return val

    for c in candidate_cols:
        out[c] = out[c].apply(safe_load)
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# ID NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════
def normalize_id(val) -> Optional[str]:
    """Normalize ID values to comparable string integers."""
    if pd.isna(val):
        return None
    try:
        return str(int(float(str(val).strip())))
    except Exception:
        s = str(val).strip()
        digits = []
        for ch in s:
            if ch.isdigit():
                digits.append(ch)
            elif digits:
                break
        return "".join(digits) if digits else None

# ═══════════════════════════════════════════════════════════════════════════════
# DATAFRAME AUGMENTATION
# ═══════════════════════════════════════════════════════════════════════════════
def augment_with_original_rows(
    df: pd.DataFrame,
    original_path: Path,
    pk_col: str = BD_PK,
    placeholder: str = PLACEHOLDER_DEFAULT,
) -> pd.DataFrame:
    """Ensure all original rows appear in df, filling missing with placeholder."""
    try:
        if not original_path.exists():
            return df
        orig = pd.read_csv(original_path, engine="python")
    except Exception:
        return df

    if pk_col not in df.columns or pk_col not in orig.columns:
        return df

    out = df.copy()
    out["_merge_id"] = out[pk_col].apply(normalize_id)
    orig = orig.copy()
    orig["_merge_id"] = orig[pk_col].apply(normalize_id)

    have = set(out["_merge_id"].dropna().astype(str))
    want = set(orig["_merge_id"].dropna().astype(str))
    missing = sorted(want - have)

    if not missing:
        out.drop(columns=["_merge_id"], inplace=True)
        return out

    missing_rows = orig[orig["_merge_id"].isin(missing)].copy()
    for c in out.columns:
        if c not in missing_rows.columns and c != "_merge_id":
            missing_rows[c] = placeholder

    out = pd.concat([out, missing_rows], ignore_index=True)
    out.drop(columns=["_merge_id"], inplace=True, errors="ignore")
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def to_json_safe(v):
    """Convert dict/list to JSON string safely."""
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
