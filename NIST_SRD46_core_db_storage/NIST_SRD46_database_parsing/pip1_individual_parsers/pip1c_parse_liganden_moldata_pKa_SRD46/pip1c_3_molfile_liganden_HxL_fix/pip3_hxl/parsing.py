"""
parsing.py - Parsing utilities for figure_definition and formula.
"""

import re
from typing import Optional, Tuple, Dict
from collections import defaultdict

# =====================================================================
# Figure Definition Parsing
# =====================================================================
CORE_RE = re.compile(r"^(H([+\-]?\d+)?)?L(\d+)?$", re.IGNORECASE)
TOKEN_RE = re.compile(r"([A-Z][a-z]?|\d+|\(|\))")


def parse_figure_definition(s: str) -> Tuple[str, int, int, int]:
    """
    Parse figure_definition like 'H2L/-' -> (core, h_count, l_count, charge).
    
    Args:
        s: Figure definition string (e.g., "H2L/-", "HL/+", "L")
        
    Returns:
        Tuple of (core_string, h_count, l_count, charge)
    """
    if not isinstance(s, str):
        return ("", 0, 0, 0)
    
    t = s.strip().replace(" ", "")
    t = (t.replace("−", "-").replace("–", "-").replace("—", "-").replace("＋", "+"))
    
    charge = 0
    
    # Match charge suffix like "/2-" or "/+"
    m = re.search(r"/(\d+)?([+-])\s*$", t)
    if m:
        mag = int(m.group(1)) if m.group(1) else 1
        sign = 1 if m.group(2) == "+" else -1
        charge = sign * mag
        t = t[: m.start()]
    else:
        # Match multiple +/- like "/--" or "/++"
        m = re.search(r"/([+-]{1,})\s*$", t)
        if m:
            run = m.group(1)
            charge = len(run) if run[0] == "+" else -len(run)
            t = t[: m.start()]
        else:
            # Match trailing +/- without slash
            m = re.search(r"([+-]{1,})\s*$", t)
            if m:
                run = m.group(1)
                charge = len(run) if run[0] == "+" else -len(run)
                t = t[: m.start()]
    
    t = t.rstrip("/")
    core = t.upper()
    
    if core == "L":
        return ("L", 0, 1, charge)
    if core == "HL":
        return ("HL", 1, 1, charge)
    
    m = CORE_RE.match(core)
    if not m:
        # Try alternative patterns
        m2 = re.match(r"^H([+\-]?\d+)?L(\d+)?$", core, re.IGNORECASE)
        if m2:
            h_str = m2.group(1)
            l_str = m2.group(2)
            h = 1 if (h_str is None) else int(h_str)
            l = 1 if (l_str is None) else int(l_str)
            core_str = f"H{h}L{l}" if h_str is not None else (f"HL{l}" if l_str is not None else "HL")
            return (core_str, h, l, charge)
        
        m3 = re.match(r"^L(\d+)$", core, re.IGNORECASE)
        if m3:
            l = int(m3.group(1))
            return (f"L{l}", 0, l, charge)
        
        return (core, 0, 0, charge)
    
    htok = m.group(1)
    hnum = m.group(2)
    lnum = m.group(3)
    
    if htok is None:
        h = 0
        l = int(lnum) if lnum else 1
        core_str = f"L{l}" if l != 1 else "L"
    else:
        h = 1 if (hnum is None) else int(hnum)
        l = int(lnum) if lnum else 1
        core_str = (f"HL{l}" if hnum is None else f"H{h}L{l}") if l != 1 else ("HL" if hnum is None else f"H{h}L")
    
    return (core_str, h, l, charge)


# =====================================================================
# Formula Parsing
# =====================================================================

def _parse_formula_part(part: str) -> Optional[Dict[str, int]]:
    """Parse a single formula part (without dots)."""
    if not part:
        return {}
    
    lead_mult = 1
    m = re.match(r"^(\d+)(.*)$", part)
    if m:
        lead_mult = int(m.group(1))
        part = m.group(2)
    
    tokens = TOKEN_RE.findall(part)
    if not tokens:
        return None
    
    stack = [defaultdict(int)]
    i = 0
    
    while i < len(tokens):
        t = tokens[i]
        if t == "(":
            stack.append(defaultdict(int))
            i += 1
        elif t == ")":
            i += 1
            mult = 1
            if i < len(tokens) and tokens[i].isdigit():
                mult = int(tokens[i])
                i += 1
            if len(stack) == 1:
                return None
            group = stack.pop()
            for el, c in group.items():
                stack[-1][el] += c * mult
        elif t.isdigit():
            return None
        else:
            el = t
            i += 1
            cnt = 1
            if i < len(tokens) and tokens[i].isdigit():
                cnt = int(tokens[i])
                i += 1
            stack[-1][el] += cnt
    
    if len(stack) != 1:
        return None
    
    out = dict(stack.pop())
    if lead_mult != 1:
        for k in list(out.keys()):
            out[k] *= lead_mult
    
    return out


def parse_formula_to_dict(s: Optional[str]) -> Optional[Dict[str, int]]:
    """
    Parse a molecular formula string to element counts.
    
    Args:
        s: Formula string (e.g., "C6H12O6", "2H2O.NaCl")
        
    Returns:
        Dictionary mapping element symbols to counts, or None if unparseable
    """
    if not isinstance(s, str) or not s.strip():
        return None
    
    s2 = s.strip().replace(" ", "")
    parts = re.split(r"[.\u00B7\u2022]", s2)
    
    total = defaultdict(int)
    any_ok = False
    
    for p in parts:
        if not p:
            continue
        d = _parse_formula_part(p)
        if d is None:
            return None
        any_ok = True
        for k, v in d.items():
            total[k] += v
    
    return dict(total) if any_ok else None


def canonical_formula(d: Optional[Dict[str, int]]) -> Optional[str]:
    """
    Convert element count dict to canonical formula string.
    
    Carbon and Hydrogen come first (Hill order), then alphabetical.
    """
    if not isinstance(d, dict):
        return None
    
    keys = list(d.keys())
    if "C" in d:
        order = (["C"] if "C" in d else []) + (["H"] if "H" in d else []) + sorted([k for k in keys if k not in ("C", "H")])
    else:
        order = sorted(keys)
    
    parts = []
    for el in order:
        c = d.get(el, 0)
        if c <= 0:
            continue
        parts.append(el if c == 1 else f"{el}{c}")
    
    return "".join(parts)


def compare_formulas(a: Optional[str], b: Optional[str]) -> Tuple[str, Optional[bool], Optional[str], Optional[str]]:
    """
    Compare two formula strings.
    
    Returns:
        Tuple of (status, same_bool, canonical_a, canonical_b)
        status is one of: "missing", "unparsed", "same", "different"
    """
    if (not a or not isinstance(a, str)) and (not b or not isinstance(b, str)):
        return "missing", None, None, None
    
    da = parse_formula_to_dict(a)
    db = parse_formula_to_dict(b)
    
    if da is None or db is None:
        return "unparsed", None, canonical_formula(da), canonical_formula(db)
    
    same = (da == db)
    return ("same" if same else "different", same, canonical_formula(da), canonical_formula(db))
