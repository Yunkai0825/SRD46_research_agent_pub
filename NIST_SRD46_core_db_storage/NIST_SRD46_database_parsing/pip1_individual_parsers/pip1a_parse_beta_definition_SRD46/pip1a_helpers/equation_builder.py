"""
Equation building and balance computation for beta_definition parsing.
"""
import re
import json
from copy import deepcopy
from typing import Dict, List, Tuple, Optional
import pandas as pd

from .species_parser import (
    collect_basis_counts, species_to_components_with_specials,
    has_dup_L, strip_brackets
)
from .constants import _ELEMENT_KEY_RE

# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════
def beta_to_pairs(val) -> List[Tuple[str, float]]:
    """Normalize equation tokens into (species, signed_power) pairs."""
    def to_pairs(x):
        if isinstance(x, (list, tuple)) and len(x) == 0:
            return []
        if isinstance(x, (list, tuple)):
            if len(x) and isinstance(x[0], (list, tuple)):
                out = []
                for item in x:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        try:
                            kk = float(item[1])
                        except Exception:
                            kk = 1.0
                        out.append((str(item[0]), kk))
                return out
            toks = list(x)
            out = []
            for sp, k in zip(toks[0::2], toks[1::2]):
                try:
                    kk = float(k)
                except Exception:
                    kk = 1.0
                out.append((str(sp), kk))
            return out
        return []

    if isinstance(val, (list, tuple)) and len(val) == 2 and all(isinstance(x, (list, tuple)) for x in val):
        num_pairs = to_pairs(val[0])
        den_pairs = to_pairs(val[1])
        signed = [(sp, +abs(float(k))) for sp, k in num_pairs] + [(sp, -abs(float(k))) for sp, k in den_pairs]
        return signed

    pairs = to_pairs(val)
    return [(str(sp), float(k)) for sp, k in pairs]

def eq_to_sides(val) -> Dict[str, List[Tuple[str, float]]]:
    """Split expression into numerator/denominator with positive powers."""
    pairs = beta_to_pairs(val)
    num, den = [], []
    for spec, p in pairs:
        if p >= 0:
            num.append((spec, abs(p)))
        else:
            den.append((spec, abs(p)))
    return {"numerator": num, "denominator": den}

def render_beta_tokens(val) -> str:
    """Render human-friendly equation string."""
    try:
        sides = eq_to_sides(val)
        def term(sp, kk):
            try:
                i = int(round(kk))
                kk = i
            except Exception:
                pass
            return f"{sp}" if kk == 1 else f"{sp}^{kk}"
        num_str = " ".join(term(sp, kk) for sp, kk in sides["numerator"]) or "1"
        den_str = " ".join(term(sp, kk) for sp, kk in sides["denominator"]) or "1"
        return f"{num_str} / ({den_str})"
    except Exception:
        return str(val)

# ═══════════════════════════════════════════════════════════════════════════════
# STRING FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════
def format_species_python(spec: str) -> str:
    return spec

def format_species_latex(spec: str) -> str:
    s = spec.replace("-", "{-}").replace("_", r"\_")
    return r"\mathrm{" + s + "}"

def strings_from_sides(sides: Dict) -> Tuple[str, str]:
    """Generate Python and LaTeX strings from sides dict."""
    def side_str(items, latex=False):
        def sp_to_str(s, p):
            if latex:
                s_lx = format_species_latex(s)
                return s_lx if p == 1 else f"{s_lx}^{int(p)}"
            return s if p == 1 else f"{s}^{int(p)}"
        return " + ".join(sp_to_str(s, p) for s, p in items) or ("\\mathrm{1}" if latex else "1")
    
    py = f"{side_str(sides['denominator'])} <=> {side_str(sides['numerator'])}"
    lx = side_str(sides['denominator'], latex=True) + r" \rightleftharpoons " + side_str(sides['numerator'], latex=True)
    return py, lx

# ═══════════════════════════════════════════════════════════════════════════════
# BALANCE COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════
def compute_balance_vector(val) -> Dict[str, float]:
    """Compute net stoichiometric balance."""
    pairs = beta_to_pairs(val)
    balance: Dict[str, float] = {}
    for spec, signed_pow in pairs:
        basis = collect_basis_counts(spec)
        for k, v in basis.items():
            balance[k] = balance.get(k, 0.0) + v * signed_pow
    for k in list(balance.keys()):
        if abs(balance[k]) < 1e-12:
            balance[k] = 0.0
    return balance

def balance_from_sides(sides: Dict) -> Dict[str, float]:
    """Compute balance from sides dict."""
    balance: Dict[str, float] = {}
    for spec, p in sides.get("numerator", []):
        for k, v in collect_basis_counts(spec).items():
            balance[k] = balance.get(k, 0.0) + v * p
    for spec, p in sides.get("denominator", []):
        for k, v in collect_basis_counts(spec).items():
            balance[k] = balance.get(k, 0.0) - v * p
    for k in list(balance.keys()):
        if abs(balance[k]) < 1e-12:
            balance[k] = 0.0
    return balance

# ═══════════════════════════════════════════════════════════════════════════════
# NESTED JSON TREE
# ═══════════════════════════════════════════════════════════════════════════════
def species_node(spec: str, power: float) -> dict:
    """Build species node with components and element totals."""
    comps = species_to_components_with_specials(spec)
    totals: Dict[str, float] = {}
    for c in comps:
        for k, v in c['elements'].items():
            totals[k] = totals.get(k, 0.0) + v
    return {'species': spec, 'power': float(power), 'components': comps, 'elements_total': totals}

def sides_to_nested_tree(sides: Dict) -> dict:
    """Convert sides to nested JSON tree."""
    num = [species_node(s, p) for s, p in sides.get('numerator', [])]
    den = [species_node(s, p) for s, p in sides.get('denominator', [])]
    return {'numerator': num, 'denominator': den}

def element_net_from_tree(tree: dict) -> Dict[str, float]:
    """Net element counts from tree (numerator - denominator)."""
    net: Dict[str, float] = {}
    for side, sign in (('numerator', +1), ('denominator', -1)):
        for node in (tree.get(side) or []):
            p = float(node.get('power', 1.0) or 1.0)
            elems = node.get('elements_total') or {}
            for k, v in elems.items():
                if k in ('M', 'L'):
                    continue
                if not _ELEMENT_KEY_RE.match(str(k)):
                    continue
                net[k] = net.get(k, 0.0) + sign * float(v) * p
    for k in list(net.keys()):
        if abs(net[k]) < 1e-12:
            net[k] = 0.0
    return net

def element_mass_conserved_from_tree(tree: dict) -> bool:
    n = element_net_from_tree(tree)
    return all(v == 0.0 for v in n.values())

# ═══════════════════════════════════════════════════════════════════════════════
# ROW-LEVEL PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════
def process_equation(val) -> dict:
    """Process single equation value and return full result dict."""
    out = {
        "sides": {"numerator": [], "denominator": []},
        "py": None, "lx": None, "bal": {},
        "parse_status": "parsed",
        "net_M": pd.NA, "net_L": pd.NA, "net_H": pd.NA, "net_O": pd.NA,
        "net_C": pd.NA, "net_N": pd.NA, "net_S": pd.NA, "net_P": pd.NA,
        "water_n": None, "water_side": None, "after_ok": False,
        "sides_adj": None, "py_adj": None, "lx_adj": None, "bal_adj": None,
        "cons_ML": False, "cons_full": False,
    }
    
    try:
        sides = eq_to_sides(val)
        py, lx = strings_from_sides(sides)
        bal = balance_from_sides(sides)
    except Exception:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            out["parse_status"] = "empty"
        elif isinstance(val, str):
            out["parse_status"] = "unparsed_string"
        else:
            out["parse_status"] = "error"
        return out

    out["sides"], out["py"], out["lx"], out["bal"] = sides, py, lx, bal

    for k in ("M", "L", "H", "O", "C", "N", "S", "P"):
        out[f"net_{k}"] = bal.get(k, 0.0)

    parsed_ok = bool(sides["numerator"] or sides["denominator"])
    empty_bal = len(bal) == 0

    if parsed_ok and not empty_bal:
        out["cons_ML"] = bal.get("M", 0.0) == 0.0 and bal.get("L", 0.0) == 0.0
        out["cons_full"] = all(abs(v) == 0.0 for v in bal.values())

    # Water adjustment
    if parsed_ok and not empty_bal and not out["cons_full"]:
        h_imb = float(bal.get("H", 0.0))
        o_imb = float(bal.get("O", 0.0))
        ml_ok = bal.get("M", 0.0) == 0.0 and bal.get("L", 0.0) == 0.0
        others_ok = all(float(bal.get(k, 0.0)) == 0.0 for k in ("C", "N", "S", "P"))

        if ml_ok and others_ok and o_imb != 0.0 and h_imb * o_imb > 0 and abs(h_imb) == 2 * abs(o_imb):
            wn = int(abs(o_imb))
            wside = "numerator" if o_imb < 0 else "denominator"
            
            sides_adj = deepcopy(sides)
            target = sides_adj["numerator"] if wside == "numerator" else sides_adj["denominator"]
            target.append(("[H2O]", float(wn)))

            py_adj, lx_adj = strings_from_sides(sides_adj)
            bal_adj = balance_from_sides(sides_adj)
            after_ok = all(abs(v) == 0.0 for v in (bal_adj or {}).values())

            if after_ok:
                out.update({
                    "water_n": wn, "water_side": wside, "after_ok": True,
                    "sides_adj": sides_adj, "py_adj": py_adj, "lx_adj": lx_adj, "bal_adj": bal_adj,
                })

    return out

# ═══════════════════════════════════════════════════════════════════════════════
# DATAFRAME PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════
def add_equation_readability_and_balance(df: pd.DataFrame, source_col: str = "eqn_formula", prefix: str = "beta_eq") -> pd.DataFrame:
    """Add equation columns to DataFrame."""
    results = {k: [] for k in ["sides", "py", "lx", "bal", "parse_status",
               "net_M", "net_L", "net_H", "net_O", "net_C", "net_N", "net_S", "net_P",
               "cons_ML", "cons_full", "water_n", "water_side", "after_ok",
               "sides_adj", "py_adj", "lx_adj", "bal_adj"]}

    for v in df[source_col]:
        info = process_equation(v)
        for k in results:
            results[k].append(info.get(k))

    df[f"{prefix}_sides"] = results["sides"]
    df[f"{prefix}_str_python"] = results["py"]
    df[f"{prefix}_str_latex"] = results["lx"]
    df[f"{prefix}_balance"] = results["bal"]
    df["parse_status"] = results["parse_status"]

    for k in ["M", "L", "H", "O", "C", "N", "S", "P"]:
        df[f"net_{k}"] = results[f"net_{k}"]

    df["element_conserved_ML"] = results["cons_ML"]
    df["element_conserved_full"] = results["cons_full"]
    df["water_adjust_n"] = results["water_n"]
    df["water_adjust_side"] = results["water_side"]
    df["element_conserved_full_after_water"] = results["after_ok"]
    df[f"{prefix}_sides_adjusted"] = results["sides_adj"]
    df[f"{prefix}_str_python_adjusted"] = results["py_adj"]
    df[f"{prefix}_str_latex_adjusted"] = results["lx_adj"]
    df[f"{prefix}_balance_adjusted"] = results["bal_adj"]

    return df

def add_final_equation_columns(df: pd.DataFrame, prefix: str = "beta_eq") -> pd.DataFrame:
    """Build *_final columns, preferring adjusted when valid."""
    df = df.copy()

    adj_py = df.get(f"{prefix}_str_python_adjusted")
    adj_bal = df.get(f"{prefix}_balance_adjusted")
    adj_s = df.get(f"{prefix}_sides_adjusted")
    after_ok = df.get("element_conserved_full_after_water", pd.Series(False, index=df.index)).fillna(False)

    has_adj = pd.Series(True, index=df.index)
    if adj_py is not None:
        has_adj &= adj_py.notna()
    if adj_bal is not None:
        has_adj &= adj_bal.notna()
    if adj_s is not None:
        has_adj &= adj_s.notna()

    use_adj = after_ok & has_adj
    df["water_fix_applied"] = use_adj

    base_ok = df.get("element_conserved_full", pd.Series(False, index=df.index)).fillna(False)
    df["element_conserved_final"] = base_ok | use_adj

    base_py = df.get(f"{prefix}_str_python")
    if base_py is not None:
        df[f"{prefix}_str_python_final"] = base_py.where(~use_adj, adj_py)

    base_bal = df.get(f"{prefix}_balance")
    if base_bal is not None:
        df[f"{prefix}_balance_final"] = base_bal.where(~use_adj, adj_bal)

    base_sides = df.get(f"{prefix}_sides")
    if base_sides is not None:
        df[f"{prefix}_sides_final"] = base_sides.where(~use_adj, adj_s)

    return df

def add_equation_tree(df: pd.DataFrame, prefix: str = "beta_eq") -> pd.DataFrame:
    """Build nested JSON tree from sides."""
    sides_col = f"{prefix}_sides_final" if f"{prefix}_sides_final" in df.columns else f"{prefix}_sides"
    df[f"{prefix}_tree"] = df[sides_col].apply(lambda s: sides_to_nested_tree(s) if isinstance(s, dict) else None)
    df[f"{prefix}_tree_json"] = df[f"{prefix}_tree"].apply(lambda obj: json.dumps(obj, ensure_ascii=False) if isinstance(obj, dict) else None)
    return df

def add_tree_elemental_diagnostics(df: pd.DataFrame, prefix: str = "beta_eq") -> pd.DataFrame:
    """Add element conservation diagnostics from tree."""
    nets, conserved, pretty = [], [], []

    for i in range(len(df)):
        tcol = df.get(f"{prefix}_tree")
        t = tcol.iloc[i] if tcol is not None else None
        if t is None:
            s = df.get(f"{prefix}_sides_final", df.get(f"{prefix}_sides", pd.Series(index=df.index))).iloc[i]
            t = sides_to_nested_tree(s) if isinstance(s, dict) else None

        if isinstance(t, dict):
            n = element_net_from_tree(t)
            nets.append(n)
            ok = all(v == 0.0 for v in n.values())
            conserved.append(ok)
            pretty.append(", ".join(f"{k}:{int(v) if float(v).is_integer() else v}" for k, v in sorted(n.items())))
        else:
            nets.append(None)
            conserved.append(None)
            pretty.append(None)

    out = df.copy()
    out[f"{prefix}_element_net_tree"] = nets
    out[f"{prefix}_element_conserved_tree"] = conserved
    out[f"{prefix}_element_net_tree_str"] = pretty
    return out

def flag_suspect_L_duplication(df: pd.DataFrame, prefix: str = "beta_eq") -> pd.DataFrame:
    """Flag rows with suspected L duplication."""
    flag = []
    sides = df.get(f"{prefix}_sides", pd.Series(index=df.index, dtype=object))
    for i in range(len(df)):
        s = sides.iloc[i]
        hit = False
        if isinstance(s, dict):
            for side in ("numerator", "denominator"):
                for spec, p in (s.get(side) or []):
                    if has_dup_L(spec):
                        hit = True
                        break
                if hit:
                    break
        flag.append(hit)
    df["suspect_L_duplication"] = flag
    return df
