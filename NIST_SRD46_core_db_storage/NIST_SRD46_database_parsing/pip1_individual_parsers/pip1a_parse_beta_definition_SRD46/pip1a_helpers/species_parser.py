"""
Species parsing utilities for beta_definition.
Hybrid approach:
- Token-based counting for balance computation (efficient, no string expansion)  
- String expansion for component breakdown in JSON tree (preserves individual tokens)
"""
import re
from typing import Dict, List, Tuple, Optional, NamedTuple
from .constants import (
    RE_MLH_SEQ_FULL, RE_MLH_TOKEN,
    RE_TRAILING_CHARGE, RE_IONIC_CHARGE, RE_STRAY_WORDS,
    RE_SIMPLE_TAG_PARENS, RE_PHASE_WITH_COLOR_PARENS, RE_EMPTY_PARENS, RE_SPACES,
    _SPECIAL_HOL_GROUP_RE,
    PAT_H2O_OPT, PAT_OH_OPT, PAT_HL_BOTH, PAT_HL_SIGN, PAT_HL_N,
    PAT_M_OPT, PAT_L_OPT, PAT_H_OPT, PAT_O_OPT, PAT_HALIDE, PAT_MET_OX, PAT_ELEM,
    PAT_H2PO4, PAT_HPO4, PAT_PO4, PAT_HSO4, PAT_SO4, PAT_HCO3, PAT_CO3, PAT_NO2, PAT_NO3,
    PAT_VO4, PAT_VO3, PAT_VO2, PAT_H2VO4, PAT_HVO4, PAT_MOO4, PAT_WO4, PAT_CRO4, PAT_CRO5,
    PAT_MNO4, PAT_ASO4, PAT_ASO3, PAT_SEO4, PAT_SEO3, PAT_SIO4,
    PAT_CL_INT, PAT_CLO4, PAT_CLO3, PAT_CLO2, PAT_BR_INT, PAT_F_INT, PAT_IO4, PAT_IO3, PAT_I_INT,
    PAT_M_NUM, PAT_L_NUM, PAT_H_NUM, PAT_O_NUM, PAT_GENERIC_ELEM_INT, _NUMF,
    POLYMETAL_HOL_TOKENS, POLYMETAL_TOKEN_PATTERN,
)

# ═══════════════════════════════════════════════════════════════════════════════
# SPECIAL RULES FOR HOL GROUPS
# ═══════════════════════════════════════════════════════════════════════════════
class _SpecialRule(NamedTuple):
    name: str
    pattern: re.Pattern
    handler: callable

def _subint(a: Optional[str], b: Optional[str]) -> int:
    """Extract integer from one of two optional groups."""
    v = a if a is not None else b
    return int(v) if v else 0

def _handle_HOL_group(m: re.Match) -> dict:
    """Handle matched HOL group and return component dict."""
    hx = _subint(m.group(1), m.group(2))
    oy = _subint(m.group(3), m.group(4))
    lz = _subint(m.group(5), m.group(6))
    return {'label': m.group(0), 'elements': {'H': float(hx), 'O': float(oy), 'L': float(lz)}}

_SPECIAL_RULES: List[_SpecialRule] = [
    _SpecialRule("HOL_parenthesized_triplet", _SPECIAL_HOL_GROUP_RE, _handle_HOL_group),
]

def apply_special_rules_to_basis(label: str) -> Tuple[Dict[str, float], str]:
    """Apply special rules and return (accumulated_counts, residual_label)."""
    acc: Dict[str, float] = {}
    s = label
    for rule in _SPECIAL_RULES:
        for m in rule.pattern.finditer(s):
            comp = rule.handler(m)
            if comp and 'elements' in comp:
                for k, v in comp['elements'].items():
                    acc[k] = acc.get(k, 0.0) + v
        s = rule.pattern.sub('', s)
    return acc, s

def apply_special_rules_to_components(label: str) -> Tuple[List[dict], str]:
    """Apply special rules and return (component_list, residual_label)."""
    comps = []
    s = label
    for rule in _SPECIAL_RULES:
        for m in rule.pattern.finditer(s):
            comp = rule.handler(m)
            if comp:
                comps.append(comp)
        s = rule.pattern.sub('', s)
    return comps, s

# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN-BASED COUNTING (replaces regex expansion)
# ═══════════════════════════════════════════════════════════════════════════════

# Regex to find opening bracket, closing bracket, or trailing coefficient
_RE_BRACKET_OR_COEFF = re.compile(r'([({])|\)(\d+(?:\.\d+)?)?|\}(\d+(?:\.\d+)?)?')
_FLOAT_COEFF_RE = re.compile(r'\(([^()]+)\)(\d+\.\d+)')

def _tokenize_with_groups(s: str) -> List:
    """
    Tokenize a formula string into a nested list structure.
    Handles (X)n and {X}n patterns recursively.
    Returns: list of (token_string, multiplier) or nested lists.
    """
    result = []
    stack = [result]
    last_pos = 0
    
    for m in _RE_BRACKET_OR_COEFF.finditer(s):
        # Add any text before this match
        if m.start() > last_pos:
            text = s[last_pos:m.start()]
            if text:
                stack[-1].append(('text', text))
        
        if m.group(1):  # Opening bracket ( or {
            new_group = []
            stack[-1].append(new_group)
            stack.append(new_group)
        elif m.group(0).startswith(')'):  # Closing )
            if len(stack) > 1:
                closed = stack.pop()
                # Apply multiplier
                mult = float(m.group(2)) if m.group(2) else 1.0
                # Replace the group in parent with (group, multiplier) tuple
                parent = stack[-1]
                if parent and parent[-1] is closed:
                    parent[-1] = ('group', closed, mult)
        elif m.group(0).startswith('}'):  # Closing }
            if len(stack) > 1:
                closed = stack.pop()
                mult = float(m.group(3)) if m.group(3) else 1.0
                parent = stack[-1]
                if parent and parent[-1] is closed:
                    parent[-1] = ('group', closed, mult)
        
        last_pos = m.end()
    
    # Add remaining text
    if last_pos < len(s):
        text = s[last_pos:]
        if text:
            stack[-1].append(('text', text))
    
    return result


def _match_polymetal_token(s: str, pos: int) -> Optional[Tuple[Dict[str, float], int]]:
    """
    Try to match a polymetal token at position pos.
    Returns (HOL_counts, match_end_position) or None.
    """
    m = POLYMETAL_TOKEN_PATTERN.match(s, pos)
    if m:
        species = m.group(1)
        mult_str = m.group(2)
        mult = float(mult_str) if mult_str else 1.0
        
        # Case-insensitive lookup in POLYMETAL_HOL_TOKENS
        hol = None
        for key, val in POLYMETAL_HOL_TOKENS.items():
            if key.lower() == species.lower():
                hol = val
                break
        
        if hol:
            # Apply multiplier to HOL counts
            scaled = {k: v * mult for k, v in hol.items()}
            return scaled, m.end()
    return None


def _count_flat_tokens(s: str) -> Tuple[Dict[str, float], List[str]]:
    """Parse a flat (no parentheses) formula string into element counts."""
    counts: Dict[str, float] = {}
    extras: List[str] = []
    pos, N = 0, len(s)
    
    def apply(token_counts: Dict[str, float], mult: float = 1.0):
        for k, v in token_counts.items():
            counts[k] = counts.get(k, 0.0) + v * mult

    # Ordered pattern matching (polymetal tokens checked first via special function)
    PATTERNS = [
        (PAT_H2O_OPT.replace(_NUMF, r'\d+(?:\.\d+)?'), lambda m: ({'H': 2.0, 'O': 1.0}, float(m.group(1) or 1))),
        (PAT_OH_OPT.replace(_NUMF, r'\d+(?:\.\d+)?'), lambda m: ({'H': 1.0, 'O': 1.0}, float(m.group(1) or 1))),
        (r'H([+-]?\d*)L(\d+)', lambda m: ({'H': 1.0 if (m.group(1) or "") in ("", "+") else (-1.0 if m.group(1) == "-" else float(m.group(1))), 'L': float(m.group(2))}, 1.0)),
        (r'HL', lambda m: ({'H': 1.0, 'L': 1.0}, 1.0)),
        (PAT_H2PO4, lambda m: ({'H': 2.0, 'P': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_HPO4, lambda m: ({'H': 1.0, 'P': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_PO4, lambda m: ({'P': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_HSO4, lambda m: ({'H': 1.0, 'S': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_SO4, lambda m: ({'S': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_HCO3, lambda m: ({'H': 1.0, 'C': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_CO3, lambda m: ({'C': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_NO2, lambda m: ({'N': 1.0, 'O': 2.0}, float(m.group(1) or 1))),
        (PAT_NO3, lambda m: ({'N': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_CL_INT, lambda m: ({'Cl': 1.0}, float(m.group(1) or 1))),
        (PAT_CLO4, lambda m: ({'Cl': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_CLO3, lambda m: ({'Cl': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_CLO2, lambda m: ({'Cl': 1.0, 'O': 2.0}, float(m.group(1) or 1))),
        (PAT_BR_INT, lambda m: ({'Br': 1.0}, float(m.group(1) or 1))),
        (PAT_F_INT, lambda m: ({'F': 1.0}, float(m.group(1) or 1))),
        # Periodate species: IO4/IO3 must come before I_INT
        (PAT_IO4, lambda m: ({'I': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_IO3, lambda m: ({'I': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_I_INT, lambda m: ({'I': 1.0}, float(m.group(1) or 1))),
        (PAT_H2VO4, lambda m: ({'H': 2.0, 'V': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_HVO4, lambda m: ({'H': 1.0, 'V': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_VO4, lambda m: ({'V': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_VO3, lambda m: ({'V': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_VO2, lambda m: ({'V': 1.0, 'O': 2.0}, float(m.group(1) or 1))),
        (PAT_MOO4, lambda m: ({'Mo': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_WO4, lambda m: ({'W': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_CRO5, lambda m: ({'Cr': 1.0, 'O': 5.0}, float(m.group(1) or 1))),
        (PAT_CRO4, lambda m: ({'Cr': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_MNO4, lambda m: ({'Mn': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_ASO4, lambda m: ({'As': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_ASO3, lambda m: ({'As': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_SEO4, lambda m: ({'Se': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        (PAT_SEO3, lambda m: ({'Se': 1.0, 'O': 3.0}, float(m.group(1) or 1))),
        (PAT_SIO4, lambda m: ({'Si': 1.0, 'O': 4.0}, float(m.group(1) or 1))),
        # Convention: "_" for subscript (positive), "-" for negative only
        # Examples: M → 1, M2 → 2, M_2 → 2, M-2 → -2
        (PAT_M_NUM, lambda m: ({'M': 1.0 if not m.group(1) else float(m.group(1).lstrip('_'))}, 1.0)),
        (PAT_L_NUM, lambda m: ({'L': 1.0 if not m.group(1) else float(m.group(1).lstrip('_'))}, 1.0)),
        (PAT_H_NUM, lambda m: ({'H': 1.0 if not m.group(1) else float(m.group(1).lstrip('_'))}, 1.0)),
        (PAT_O_NUM, lambda m: ({'O': 1.0 if not m.group(1) else float(m.group(1).lstrip('_'))}, 1.0)),
        (PAT_GENERIC_ELEM_INT, lambda m: ({'M': 1.0}, float(m.group(2) or 1))),
    ]

    while pos < N:
        matched = False
        
        # Priority 1: Check for polymetal special tokens (e.g., Mo7O24, V10O28)
        poly_result = _match_polymetal_token(s, pos)
        if poly_result:
            token_counts, end_pos = poly_result
            apply(token_counts)
            pos = end_pos
            matched = True
            continue
        
        # Priority 2: Standard pattern matching
        for pat, handler in PATTERNS:
            m = re.match(pat, s[pos:])
            if m:
                token_counts, mult = handler(m)
                apply(token_counts, mult)
                pos += m.end()
                matched = True
                break
        if not matched:
            extras.append(s[pos:])
            break

    return {k: v for k, v in counts.items() if v != 0}, extras

def _count_tokens_recursive(tokens: List, multiplier: float = 1.0) -> Tuple[Dict[str, float], List[str]]:
    """Recursively count elements from tokenized structure."""
    counts: Dict[str, float] = {}
    extras: List[str] = []
    
    for item in tokens:
        if isinstance(item, tuple):
            if item[0] == 'text':
                # Flat text - parse directly
                flat_counts, flat_extras = _count_flat_tokens(item[1])
                for k, v in flat_counts.items():
                    counts[k] = counts.get(k, 0.0) + v * multiplier
                extras.extend(flat_extras)
            elif item[0] == 'group':
                # Nested group with multiplier
                _, group_tokens, group_mult = item
                sub_counts, sub_extras = _count_tokens_recursive(group_tokens, multiplier * group_mult)
                for k, v in sub_counts.items():
                    counts[k] = counts.get(k, 0.0) + v
                extras.extend(sub_extras)
        elif isinstance(item, list):
            # Ungrouped nested list
            sub_counts, sub_extras = _count_tokens_recursive(item, multiplier)
            for k, v in sub_counts.items():
                counts[k] = counts.get(k, 0.0) + v
            extras.extend(sub_extras)
    
    return counts, extras

def parse_tokens_to_basis(s: str) -> Tuple[Dict[str, float], List[str]]:
    """Parse formula string using token-based counting (no string expansion)."""
    if not s or not s.strip():
        return {}, []
    
    # Convert braces to parens for uniform handling
    s = s.replace('{', '(').replace('}', ')')
    
    # Check if there are any parentheses
    if '(' not in s:
        # Simple flat formula
        return _count_flat_tokens(s)
    
    # Tokenize and count recursively
    tokens = _tokenize_with_groups(s)
    return _count_tokens_recursive(tokens)

def extract_float_groups(label: str) -> Tuple[Dict[str, float], str]:
    """Extract (X)0.5 type groups with fractional coefficients."""
    acc: Dict[str, float] = {}
    s = label
    while True:
        m = _FLOAT_COEFF_RE.search(s)
        if not m:
            break
        inner = m.group(1)
        mult = float(m.group(2))
        inner_counts, inner_extras = _count_flat_tokens(inner)
        if inner_extras:
            break
        for k, v in inner_counts.items():
            acc[k] = acc.get(k, 0.0) + v * mult
        s = s[:m.start()] + s[m.end():]
    return acc, s

# ═══════════════════════════════════════════════════════════════════════════════
# PARENTHESIS/BRACE EXPANSION (for component breakdown in JSON tree)
# ═══════════════════════════════════════════════════════════════════════════════
# Pattern for integer-only coefficients (don't match if followed by decimal point)
_PAREN_INT_RE = re.compile(r'\(([^()]+)\)(\d*)(?!\.)')
_BRACE_INT_RE = re.compile(r"\{([^{}]+)\}([0-9]+)(?!\.)")
# Pattern for float coefficients like (X)0.5 or (X)1.5
_PAREN_FLOAT_RE = re.compile(r'\(([^()]+)\)(\d+\.\d+)')
_BRACE_FLOAT_RE = re.compile(r'\{([^{}]+)\}(\d+\.\d+)')

def expand_parentheses_once(s: str) -> str:
    """Expand (X)n patterns by string repetition."""
    while True:
        m = _PAREN_INT_RE.search(s)
        if not m:
            break
        inner, num = m.group(1), m.group(2)
        k = int(num or '1')
        s = s[:m.start()] + (inner * k) + s[m.end():]
    return s

def expand_brace_groups(s: str) -> str:
    """Expand {X}n patterns by string repetition."""
    out = s
    while True:
        m = _BRACE_INT_RE.search(out)
        if not m:
            break
        inner, n = m.group(1), int(m.group(2))
        out = out[:m.start()] + (inner * n) + out[m.end():]
    return out

def promote_nested_paren_to_brace(s: str) -> str:
    """Promote outer (...)n with nested parens to {...}n."""
    out = list(s)
    stack = []
    i = 0
    while i < len(out):
        if out[i] == '(':
            stack.append(i)
        elif out[i] == ')' and stack:
            j = stack.pop()
            k = i + 1
            while k < len(out) and out[k].isspace():
                k += 1
            mstart = k
            while k < len(out) and out[k].isdigit():
                k += 1
            if k > mstart:
                inner = ''.join(out[j+1:i])
                if '(' in inner or ')' in inner:
                    out[j] = '{'
                    out[i] = '}'
        i += 1
    return ''.join(out)

def expand_brace_and_paren(spec: str) -> str:
    """Full expansion: promote nested, expand braces, expand parens."""
    s = spec
    for _ in range(5):
        prev = s
        s = promote_nested_paren_to_brace(s)
        if s == prev:
            break
    s = expand_brace_groups(s)
    s = expand_parentheses_once(s)
    return s

# ═══════════════════════════════════════════════════════════════════════════════
# SPECIES LABEL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
def parse_species_label_to_basis(spec_label: str) -> Tuple[Dict[str, float], List[str]]:
    """Main species parsing pipeline.
    
    IMPORTANT: Checks POLYMETAL_HOL_TOKENS first (before stripping annotations)
    so that phase markers like (s) are preserved for token matching.
    """
    label = (spec_label or "").strip()
    if not label:
        return {}, ["<empty>"]

    # Remove brackets first
    label = label.replace('[', '').replace(']', '')
    
    # Priority 0: Check for polymetal tokens BEFORE stripping annotations
    # This allows tokens like "(As4O6)0.25(s)" to match with phase markers
    poly_result = _match_polymetal_token(label, 0)
    if poly_result:
        token_counts, end_pos = poly_result
        remainder = label[end_pos:]
        remainder_clean = strip_nonchemical_annotations(remainder)
        if not remainder_clean.strip():
            # Entire species is a polymetal token
            return {k: v for k, v in token_counts.items() if v != 0}, []

    # Now strip annotations for standard processing
    label = strip_nonchemical_annotations(label)

    # Special rules (HOL groups)
    acc_counts, label = apply_special_rules_to_basis(label)

    # Float groups
    acc3, residual = extract_float_groups(label)
    for k, v in acc3.items():
        acc_counts[k] = acc_counts.get(k, 0.0) + v

    # Token-based counting (replaces expand + flat parse)
    rem_counts, rem_extras = parse_tokens_to_basis(residual)

    for k, v in rem_counts.items():
        acc_counts[k] = acc_counts.get(k, 0.0) + v
    return {k: v for k, v in acc_counts.items() if v != 0}, rem_extras

# ═══════════════════════════════════════════════════════════════════════════════
# MLH FAST PATH AND HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def parse_MLH_counts(spec_label: str) -> Tuple[Dict[str, int], List[str]]:
    """Parse pure MLH labels like 'MH-3L2' or 'M_2L_3'.
    
    Convention: "_" is subscript separator (positive), "-" is negative sign.
    Examples: M → 1, M2 → 2, M_2 → 2, M-2 → -2
    """
    s = spec_label.strip()
    if not s:
        return {}, ["<empty>"]
    if not RE_MLH_SEQ_FULL.fullmatch(s):
        return {}, [s]
    counts = {'M': 0, 'L': 0, 'H': 0}
    for sym, num in RE_MLH_TOKEN.findall(s):
        if num in (None, "", "+"):
            val = 1
        elif num == "-":
            val = -1
        else:
            # Strip leading "_" for subscript notation, keep "-" for negative
            val = int(num.lstrip('_')) if num.startswith('_') else int(num)
        counts[sym] += val
    return {k: v for k, v in counts.items() if v != 0}, []

def strip_brackets(spec: str) -> str:
    """Remove enclosing brackets from species string."""
    s = str(spec).strip()
    if s.startswith("["):
        j = s.find("]")
        return s[1:j].strip() if j != -1 else s[1:].strip()
    return s

def strip_nonchemical_annotations(label: str) -> str:
    """Remove benign annotations while preserving chemical groups."""
    if not label:
        return label
    lab = label
    lab = RE_IONIC_CHARGE.sub('', lab)
    lab = RE_SIMPLE_TAG_PARENS.sub('', lab)
    lab = RE_PHASE_WITH_COLOR_PARENS.sub('', lab)
    lab = RE_EMPTY_PARENS.sub('', lab)
    lab = RE_SPACES.sub('', lab)
    return lab

def clean_formula_artifacts(s: str) -> str:
    """Normalize formula-like string."""
    if not s:
        return s
    s = RE_IONIC_CHARGE.sub('', s)
    s = RE_TRAILING_CHARGE.sub('', s)
    s = s.replace('+', '')
    s = s.replace('o', 'O')
    s = RE_STRAY_WORDS.sub('', s)
    return s

def collect_basis_counts(spec: str) -> Dict[str, int]:
    """Get basis counts for a species string."""
    label = strip_brackets(spec)
    
    # Fast MLH path
    mlh, extras = parse_MLH_counts(label)
    if not extras:
        return mlh

    # Full chemistry-aware path
    expanded, extras2 = parse_species_label_to_basis(label)
    if expanded and not extras2:
        return expanded

    if expanded:
        out = dict(expanded)
        for tok in extras2:
            out[f"EXTRA:{tok}"] = out.get(f"EXTRA:{tok}", 0) + 1
        return out

    return {f"EXTRA:{label}": 1}

def has_dup_L(spec: str) -> bool:
    """Check if species has duplicate L runs."""
    label = strip_brackets(spec)
    core = strip_nonchemical_annotations(label)
    # Remove parentheses for simple L counting
    core = re.sub(r'[(){}\[\]]', '', core)
    parts = re.split(r'L\d*', core)
    return len(parts) >= 3

# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def component_token_to_elements(tok: str) -> Dict[str, float]:
    """Convert a single token to element counts."""
    t = tok.strip()
    
    # H2O, OH
    m = re.fullmatch(PAT_H2O_OPT, t)
    if m:
        n = float(m.group(1) or "1")
        return {'H': 2.0*n, 'O': 1.0*n}
    m = re.fullmatch(PAT_OH_OPT, t)
    if m:
        n = float(m.group(1) or "1")
        return {'H': 1.0*n, 'O': 1.0*n}

    # HL variants
    m = re.fullmatch(PAT_HL_BOTH, t)
    if m:
        hraw = (m.group(1) or "").strip()
        lraw = (m.group(2) or "").strip()
        h = 1.0 if hraw in ("", "+") else (-1.0 if hraw == "-" else float(hraw))
        l = 1.0 if lraw == "" else float(lraw)
        return {'H': h, 'L': l}

    m = re.fullmatch(PAT_HL_SIGN, t)
    if m:
        g = (m.group(1) or "").strip()
        n = 1.0 if g in ("", "+") else (-1.0 if g == "-" else float(g))
        return {'H': n, 'L': 1.0}

    m = re.fullmatch(PAT_HL_N, t)
    if m:
        return {'H': 1.0, 'L': float(m.group(1))}

    if t == 'HL':
        return {'H': 1.0, 'L': 1.0}

    # M, L, H, O
    m = re.fullmatch(PAT_M_OPT, t)
    if m:
        return {'M': float(m.group(1) or "1")}
    m = re.fullmatch(PAT_L_OPT, t)
    if m:
        return {'L': float(m.group(1) or "1")}
    m = re.fullmatch(PAT_H_OPT, t)
    if m:
        raw = (m.group(1) or "").strip()
        n = 1.0 if raw in ("", "+") else (-1.0 if raw == "-" else float(raw))
        return {'H': n}
    m = re.fullmatch(PAT_O_OPT, t)
    if m:
        return {'O': float(m.group(1) or "1")}

    # Metal oxide
    m = re.fullmatch(PAT_MET_OX, t)
    if m:
        sym, y = m.group(1), int(m.group(2))
        return {sym: 1.0, 'O': float(y)}

    # Generic element
    m = re.fullmatch(PAT_ELEM, t)
    if m:
        sym, num = m.group(1), m.group(2)
        return {sym: float(num) if num else 1.0}

    # Halides
    if t in ('Cl', 'Br', 'F', 'I'):
        return {t: 1.0}

    return {}


def _extract_float_groups_for_components(s: str) -> Tuple[List[dict], str]:
    """
    Extract (X)0.5 and {X}0.5 float-coefficient groups BEFORE integer expansion.
    Returns (list of component dicts, residual string).
    """
    comps = []
    residual = s
    
    # Process float groups iteratively
    while True:
        # Try paren float first
        m = _PAREN_FLOAT_RE.search(residual)
        if not m:
            m = _BRACE_FLOAT_RE.search(residual)
        if not m:
            break
            
        inner = m.group(1)
        mult = float(m.group(2))
        
        # Recursively get elements from inner (simple elements only)
        inner_counts, _ = _count_flat_tokens(inner)
        if inner_counts:
            scaled = {k: v * mult for k, v in inner_counts.items()}
            comps.append({'label': m.group(0), 'elements': scaled})
        else:
            comps.append({'label': m.group(0), 'elements': {}})
        
        # Remove matched portion from residual
        residual = residual[:m.start()] + residual[m.end():]
    
    return comps, residual


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN-BASED COMPONENT EXTRACTION (replaces string repetition)
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern to match a single token from a flat formula string
_COMPONENT_PATTERNS = None  # Lazy init

def _get_component_patterns():
    """Lazy initialization of component patterns."""
    global _COMPONENT_PATTERNS
    if _COMPONENT_PATTERNS is None:
        _COMPONENT_PATTERNS = [
            # H2O, OH first (most specific)
            (re.compile(PAT_H2O_OPT), lambda m: ('H2O' + (m.group(1) or ''), {'H': 2.0, 'O': 1.0}, float(m.group(1) or 1))),
            (re.compile(PAT_OH_OPT), lambda m: ('OH' + (m.group(1) or ''), {'H': 1.0, 'O': 1.0}, float(m.group(1) or 1))),
            # HL variants (deprotonated ligands) - CRITICAL for H-nL handling
            (re.compile(PAT_HL_BOTH), lambda m: (
                'H' + (m.group(1) or '') + 'L' + (m.group(2) or ''),
                {'H': 1.0 if (m.group(1) or "") in ("", "+") else (-1.0 if m.group(1) == "-" else float(m.group(1))),
                 'L': float(m.group(2)) if m.group(2) else 1.0},
                1.0
            )),
            (re.compile(PAT_HL_SIGN), lambda m: (
                'H' + (m.group(1) or '') + 'L',
                {'H': 1.0 if (m.group(1) or "") in ("", "+") else (-1.0 if m.group(1) == "-" else float(m.group(1))), 'L': 1.0},
                1.0
            )),
            (re.compile(r'HL'), lambda m: ('HL', {'H': 1.0, 'L': 1.0}, 1.0)),
            # Halides
            (re.compile(PAT_HALIDE), lambda m: (m.group(1) + (m.group(2) or ''), {m.group(1): 1.0}, float(m.group(2) or 1))),
            # M, L, H, O
            (re.compile(PAT_M_OPT), lambda m: ('M' + (m.group(1) or ''), {'M': 1.0}, float(m.group(1) or 1))),
            (re.compile(PAT_L_OPT), lambda m: ('L' + (m.group(1) or ''), {'L': 1.0}, float(m.group(1) or 1))),
            (re.compile(PAT_H_OPT), lambda m: (
                'H' + (m.group(1) or ''),
                {'H': 1.0 if (m.group(1) or "") in ("", "+") else (-1.0 if m.group(1) == "-" else float(m.group(1)))},
                1.0
            )),
            (re.compile(PAT_O_OPT), lambda m: (
                'O' + (m.group(1) or ''),
                {'O': 1.0 if (m.group(1) or "") in ("", "+") else (-1.0 if m.group(1) == "-" else float(m.group(1)))},
                1.0
            )),
            # Metal oxide like Fe2O3
            (re.compile(PAT_MET_OX), lambda m: (m.group(0), {m.group(1): 1.0, 'O': float(m.group(2))}, 1.0)),
            # Generic element
            (re.compile(PAT_ELEM), lambda m: (m.group(1) + (m.group(2) or ''), {m.group(1): 1.0}, float(m.group(2) or 1))),
        ]
    return _COMPONENT_PATTERNS


def _parse_flat_to_components(s: str) -> List[dict]:
    """Parse a flat (no parentheses) string into component dicts.
    
    IMPORTANT: Checks POLYMETAL_HOL_TOKENS first so that polymetal species
    (like V10O28, Mo7O24, Si2O3(OH)4) are represented as {H, O, L, M} basis
    instead of actual element symbols. This ensures tree balance consistency.
    """
    comps = []
    pos, N = 0, len(s)
    patterns = _get_component_patterns()
    
    while pos < N:
        matched = False
        
        # Priority 1: Check for polymetal special tokens (e.g., Mo7O24, V10O28)
        # This ensures tree balance uses HOL basis instead of actual elements
        poly_result = _match_polymetal_token(s, pos)
        if poly_result:
            token_counts, end_pos = poly_result
            # Create component with the matched text as label
            label = s[pos:end_pos]
            comps.append({'label': label, 'elements': token_counts})
            pos = end_pos
            matched = True
            continue
        
        # Priority 2: Standard pattern matching
        for pat, handler in patterns:
            m = pat.match(s, pos)
            if m:
                label, base_elements, mult = handler(m)
                # Scale elements by multiplier
                scaled = {k: v * mult for k, v in base_elements.items() if v != 0}
                comps.append({'label': label, 'elements': scaled})
                pos = m.end()
                matched = True
                break
        
        if not matched:
            # Unrecognized - capture rest as unknown
            if s[pos:].strip():
                comps.append({'label': s[pos:], 'elements': {}})
            break
    
    return comps


def _components_from_tokens(tokens: List, outer_mult: float = 1.0) -> List[dict]:
    """
    Recursively convert tokenized structure to component dicts.
    Uses token-based counting to handle groups like (H-2L)2 correctly.
    """
    comps = []
    
    for item in tokens:
        if isinstance(item, tuple):
            if item[0] == 'text':
                # Flat text segment - parse to components
                text_comps = _parse_flat_to_components(item[1])
                for c in text_comps:
                    # Scale elements by outer multiplier
                    if outer_mult != 1.0:
                        c['elements'] = {k: v * outer_mult for k, v in c['elements'].items()}
                    comps.append(c)
                    
            elif item[0] == 'group':
                # Nested group: ('group', tokens_list, multiplier)
                _, group_tokens, group_mult = item
                total_mult = outer_mult * group_mult
                
                # Get components from inner tokens
                inner_comps = _components_from_tokens(group_tokens, 1.0)
                
                # Compute total elements for the group
                total_elements: Dict[str, float] = {}
                inner_labels = []
                for c in inner_comps:
                    inner_labels.append(c.get('label', ''))
                    for k, v in c.get('elements', {}).items():
                        total_elements[k] = total_elements.get(k, 0.0) + v
                
                # Scale by group multiplier
                scaled_elements = {k: v * total_mult for k, v in total_elements.items()}
                
                # Create label like "(H-2L)2" 
                inner_label = ''.join(inner_labels)
                if group_mult == int(group_mult):
                    group_label = f"({inner_label}){int(group_mult)}"
                else:
                    group_label = f"({inner_label}){group_mult}"
                
                comps.append({'label': group_label, 'elements': scaled_elements})
                
        elif isinstance(item, list):
            # Ungrouped nested list (shouldn't happen normally)
            sub_comps = _components_from_tokens(item, outer_mult)
            comps.extend(sub_comps)
    
    return comps


def species_to_components(spec_label: str) -> List[dict]:
    """
    Convert species label to list of component dicts using TOKEN-BASED counting.
    
    This replaces string-repetition expansion with proper tokenization to handle:
    - Simple groups: (OH)3 → one component with elements scaled by 3
    - Deprotonated ligands: (H-2L)2 → one component with H:-4, L:2
    - Fractional groups: (M2O3)0.5 → one component with M:1, O:1.5
    - Nested groups: correctly handled via recursive tokenization
    
    IMPORTANT: Checks POLYMETAL_HOL_TOKENS first (before stripping annotations)
    so that phase markers like (s) are preserved for token matching.
    """
    s = strip_brackets(spec_label)
    
    if not s:
        return []
    
    # Priority 0: Check for polymetal tokens BEFORE stripping annotations
    # This allows tokens like "(As4O6)0.25(s)" to match with phase markers
    poly_result = _match_polymetal_token(s, 0)
    if poly_result:
        token_counts, end_pos = poly_result
        # Check if we matched the entire string (possibly with trailing phase marker)
        remainder = s[end_pos:]
        remainder_clean = strip_nonchemical_annotations(remainder)
        if not remainder_clean.strip():
            # Entire species is a polymetal token
            return [{'label': s[:end_pos], 'elements': token_counts}]
    
    # Now strip annotations for standard processing
    s = strip_nonchemical_annotations(s)
    
    if not s:
        return []
    
    # Handle special HOL groups first (like (H0O1L1))
    special_comps, s = apply_special_rules_to_components(s)
    comps = list(special_comps)
    
    if not s.strip():
        return comps
    
    # Convert braces to parens for uniform handling
    s = s.replace('{', '(').replace('}', ')')
    
    # Check if there are any parentheses to process
    if '(' not in s:
        # Simple flat formula - direct parsing
        flat_comps = _parse_flat_to_components(s)
        comps.extend(flat_comps)
    else:
        # Tokenize and recursively extract components
        tokens = _tokenize_with_groups(s)
        token_comps = _components_from_tokens(tokens)
        comps.extend(token_comps)
    
    return comps

def species_to_components_with_specials(spec_label: str) -> List[dict]:
    """Apply special rules then parse residual."""
    raw = strip_brackets(spec_label or "")
    if not raw:
        return []
    
    components = []
    residual = raw

    for rule in _SPECIAL_RULES:
        for m in rule.pattern.finditer(residual):
            comp = rule.handler(m)
            if comp and isinstance(comp, dict) and comp.get('elements'):
                components.append(comp)
        residual = rule.pattern.sub('', residual)

    if residual.strip():
        components.extend(species_to_components(residual))
    
    return components
