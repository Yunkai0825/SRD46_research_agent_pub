"""
Constants, regex patterns, and type definitions for beta_definition parsing.
Extracted from SRD46_pd_parse_beta_definition_pip-3.py for modularity.
"""
import re
from typing import NamedTuple, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# VALID ELEMENTS (periodic table)
# ═══════════════════════════════════════════════════════════════════════════════
VALID_ELEMENTS = {
    "H","He","Li","Be","B","C","N","O","F","Ne","Na","Mg","Al","Si","P","S","Cl","Ar",
    "K","Ca","Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn","Ga","Ge","As","Se","Br",
    "Kr","Rb","Sr","Y","Zr","Nb","Mo","Tc","Ru","Rh","Pd","Ag","Cd","In","Sn","Sb","Te",
    "I","Xe","Cs","Ba","La","Ce","Pr","Nd","Pm","Sm","Eu","Gd","Tb","Dy","Ho","Er","Tm",
    "Yb","Lu","Hf","Ta","W","Re","Os","Ir","Pt","Au","Hg","Tl","Pb","Bi","Po","At","Rn",
    "Fr","Ra","Ac","Th","Pa","U","Np","Pu","Am","Cm","Bk","Cf","Es","Fm","Md","No","Lr",
    "Rf","Db","Sg","Bh","Hs","Mt","Ds","Rg","Cn","Nh","Fl","Mc","Lv","Ts","Og"
}

# ═══════════════════════════════════════════════════════════════════════════════
# NAMED TUPLE FOR PARSED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
class ParsedConst(NamedTuple):
    value: Optional[float]
    qualifier: Optional[str]
    lower: Optional[float]
    upper: Optional[float]
    uncertainty: Optional[float]
    note: Optional[str]

# ═══════════════════════════════════════════════════════════════════════════════
# CORE REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Numeric patterns
_NUMF = r'(?:\d+(?:\.\d+)?)'  # float or int
_RE_NUMBER = r'[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?'
_RE_WS = r'[ \t\u00A0\u2009]*'  # normal, nbsp, thin space

# Element patterns
_EL_NO_HOL = r'(?!H|O|Cl|Br|F|I|L)([A-Z][a-z]?)'  # element except H,O,halides,L

# Beta-definition preliminary parsing
PAT_EQ_SPLIT = r'/(?!sub|sup)'
PAT_SEGMENT_TOKEN = r'(\[.*?\]|&lt;sup&gt;.*?&lt;/sup&gt;)'
RE_EQ_SPLIT = re.compile(PAT_EQ_SPLIT)
RE_SEGMENT_TOKEN = re.compile(PAT_SEGMENT_TOKEN)

# HTML handling
RE_HTML_SUB_TAGS = re.compile(r'</?\s*sub\s*>', re.IGNORECASE)
HTML_SUP_OPEN = "<sup>"
HTML_SUP_CLOSE = "</sup>"

# Pure H/V/O formula detection
_HVO_PURE_RE = re.compile(r"^[HVO0-9(){}\.\-\s]+$", re.IGNORECASE)

# Brace/parenthesis expansion
_BRACE_INT_RE = re.compile(r"\{([^{}]+)\}([0-9]+)")
_FLOAT_GROUP_RE = re.compile(r'(\(([^()]+)\)|\{([^{}]+)\))\s*([0-9]+(?:\.[0-9]+)?)')
RE_PAREN_INT = re.compile(r'\(([^()]+)\)(\d*)')

# Element key validation
_ELEMENT_KEY_RE = re.compile(r'^(?:' + '|'.join(sorted(VALID_ELEMENTS, key=len, reverse=True)) + r')$')

# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN PATTERNS (used by flat scanner and component tokenizer)
# ═══════════════════════════════════════════════════════════════════════════════

# Common tokens with optional multiplicity
PAT_H2O_OPT = r'H2O(' + _NUMF + r')?'
PAT_OH_OPT = r'OH(' + _NUMF + r')?'
PAT_HL_BOTH = r'H([+-]?' + _NUMF + r')?L(' + _NUMF + r')?'
PAT_HL_SIGN = r'H([+-]?' + _NUMF + r')?L'
PAT_HL_N = r'HL(' + _NUMF + r')'
PAT_M_OPT = r'M(' + _NUMF + r')?'
PAT_L_OPT = r'L(' + _NUMF + r')?'
PAT_H_OPT = r'H([+-]?' + _NUMF + r')?'
PAT_O_OPT = r'O([+-]?' + _NUMF + r')?'  # Support negative subscripts like O-2
PAT_HALIDE = r'(Cl|Br|F|I)(' + _NUMF + r')?'
PAT_MET_OX = _EL_NO_HOL + r'O(\d+)'
PAT_ELEM = _EL_NO_HOL + r'(?:(' + _NUMF + r'))?'

# Flat-only integer variants
PAT_H2O_INT = r'H2O(\d*)'
PAT_OH_INT = r'OH(\d*)'
PAT_HL_INT_BOTH = r'H([+-]?\d*)L(\d+)'
PAT_HL_LITERAL = r'HL'

# Common anions
PAT_H2PO4 = r'H2PO4(\d*)'; PAT_HPO4 = r'HPO4(\d*)'; PAT_PO4 = r'PO4(\d*)'
PAT_HSO4 = r'HSO4(\d*)'; PAT_SO4 = r'SO4(\d*)'
PAT_HCO3 = r'HCO3(\d*)'; PAT_CO3 = r'CO3(\d*)'
PAT_NO2 = r'NO2(\d*)'; PAT_NO3 = r'NO3(\d*)'

# Oxoanion species
PAT_VO4 = r'VO4(\d*)'; PAT_VO3 = r'VO3(\d*)'; PAT_VO2 = r'VO2(\d*)'
PAT_H2VO4 = r'H2VO4(\d*)'; PAT_HVO4 = r'HVO4(\d*)'
PAT_MOO4 = r'MoO4(\d*)'; PAT_WO4 = r'WO4(\d*)'
PAT_CRO4 = r'CrO4(\d*)'; PAT_CRO5 = r'CrO5(\d*)'
PAT_MNO4 = r'MnO4(\d*)'; PAT_ASO4 = r'AsO4(\d*)'; PAT_ASO3 = r'AsO3(\d*)'
PAT_SEO4 = r'SeO4(\d*)'; PAT_SEO3 = r'SeO3(\d*)'; PAT_SIO4 = r'SiO4(\d*)'

# Halides
PAT_CL_INT = r'Cl(\d*)'; PAT_CLO4 = r'ClO4(\d*)'; PAT_CLO3 = r'ClO3(\d*)'; PAT_CLO2 = r'ClO2(\d*)'
PAT_BR_INT = r'Br(\d*)'; PAT_F_INT = r'F(\d*)'
# Iodine species (IO4/IO3 must come before I to avoid partial matching)
PAT_IO4 = r'IO4(\d*)'; PAT_IO3 = r'IO3(\d*)'; PAT_I_INT = r'I(\d*)'

# Optional flat-only variants
# Convention: "_" for subscript counting (e.g., O_4 = 4 oxygens)
#             "-" for negative values only (e.g., O-4 = -4 oxygens)
PAT_M_NUM = r'M(_?\d+(?:\.\d+)?|-\d+(?:\.\d+)?)?'
PAT_L_NUM = r'L(_?\d+(?:\.\d+)?|-\d+(?:\.\d+)?)?'
PAT_H_NUM = r'H(_?\d+(?:\.\d+)?|-\d+(?:\.\d+)?)?'
PAT_O_NUM = r'O(_?\d+(?:\.\d+)?|-\d+(?:\.\d+)?)?'

# MLH-only labels ("_" for subscript, "-" for negative)
# Note: -\d+ must come first to match before the empty _?\d* alternative
PAT_MLH_SEQ = r'^(?:([MLH])(-\d+|_?\d+)?)+$'
PAT_MLH_TOKEN = r'([MLH])(-\d+|_?\d+)?'
RE_MLH_SEQ_FULL = re.compile(PAT_MLH_SEQ)
RE_MLH_TOKEN = re.compile(PAT_MLH_TOKEN)

# Generic element fallback
PAT_GENERIC_ELEM_INT = r'(?!H|O|Cl|Br|F|I|L)([A-Z][a-z]?)(\d*)'

# Fractional group at position
PAT_FLOAT_GROUP_AT_POS = r'(?:\(([^()]+)\)|\{([^{}]+)\})\s*(' + _NUMF + r')'
RE_FLOAT_GROUP_AT_POS = re.compile(PAT_FLOAT_GROUP_AT_POS)

# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Stray words to drop
STRAY_WORDS_ALT = r'blue|red|cyclo'
PAT_STRAY_WORDS = rf'(?i)\b(?:{STRAY_WORDS_ALT})\b'

# Simple tags in parentheses
SIMPLE_TAGS_ALT = (
    r'aq|s|l|g|pyr\.|plan\.|cis|trans|fac|mer|oct\.|tet\.|sq|'
    r'red|blue|cyclo|linear|square|Td|D3h|C4v|Δ|Λ'
)
PAT_SIMPLE_TAG_PARENS = rf'\(\s*(?:{SIMPLE_TAGS_ALT})\s*\)'
PAT_PHASE_WITH_COLOR_PARENS = r'\(\s*(?:aq|s|l|g)\s*,[^()]*\)'
PAT_EMPTY_PARENS = r'\(\s*\)'
PAT_SPACES = r'\s+'

# Charge patterns
PAT_TRAILING_CHARGE = r'[+-]+$'
PAT_IONIC_CHARGE = r'\^\{[+-]\}'

# Precompiled cleanup regex
RE_TRAILING_CHARGE = re.compile(PAT_TRAILING_CHARGE)
RE_IONIC_CHARGE = re.compile(PAT_IONIC_CHARGE)
RE_STRAY_WORDS = re.compile(PAT_STRAY_WORDS)
RE_SIMPLE_TAG_PARENS = re.compile(PAT_SIMPLE_TAG_PARENS, re.IGNORECASE)
RE_PHASE_WITH_COLOR_PARENS = re.compile(PAT_PHASE_WITH_COLOR_PARENS, re.IGNORECASE)
RE_EMPTY_PARENS = re.compile(PAT_EMPTY_PARENS)
RE_SPACES = re.compile(PAT_SPACES)
RE_MET_OX_FULL = re.compile(r'^' + PAT_MET_OX + r'$')
RE_ELEM_FULL = re.compile(r'^' + PAT_ELEM + r'$')

# ═══════════════════════════════════════════════════════════════════════════════
# SPECIAL HOL GROUP (for strict parenthesized H_x O_y L_z patterns)
# ═══════════════════════════════════════════════════════════════════════════════
_SPECIAL_HOL_GROUP_RE = re.compile(
    r'\(\s*'
    r'H(?:<\s*sub\s*>\s*([+-]?\d+)\s*<\s*/\s*sub\s*>|([+-]?\d+))\s*'
    r'O(?:<\s*sub\s*>\s*([+-]?\d+)\s*<\s*/\s*sub\s*>|([+-]?\d+))\s*'
    r'L(?:<\s*sub\s*>\s*([+-]?\d+)\s*<\s*/\s*sub\s*>|([+-]?\d+))\s*'
    r'\)',
    flags=re.IGNORECASE
)

# ═══════════════════════════════════════════════════════════════════════════════
# POLYMETAL SPECIES → HOL BASIS COUNTS (special tokens for balance computation)
# ═══════════════════════════════════════════════════════════════════════════════
# Format: "species_formula": {"H": n, "O": n, "L": n}
# These are polymetal oxide clusters where:
#   - L represents the base ligand (e.g., MoO4²⁻ for molybdate, VO4³⁻ for vanadate)
#   - The O count is the "excess" oxygen relative to nL (can be negative)
#   - Example: Mo7O24 = 7×MoO4 - 4×O → {"H": 0, "O": -4, "L": 7}
#
# Chemistry basis (example for molybdate, L = MoO4²⁻):
#   Mo7O24⁶⁻ ↔ 7 MoO4²⁻ - 4 O²⁻  (condensation with loss of oxide)
#   So in HOL notation: H₀O₋₄L₇
#
# Annotation format: β=beta_definition_IDs, L=ligand_ID, M=metal_IDs
#
# The table itself lives in srd46_pipeline/manual_rules.py (rule BETA-04, single register of
# hand-made chemistry decisions, with validate()); it is re-exported here unchanged so the
# tokenizer code below did not have to change.
try:
    from srd46_pipeline import manual_rules as _mr
except ImportError:  # standalone use from inside the parser package: project root = 3 levels up
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from srd46_pipeline import manual_rules as _mr

POLYMETAL_HOL_TOKENS = {k: dict(v) for k, v in _mr.BETA_POLYMETAL_HOL_TOKENS.items()}

# Build regex patterns for polymetal tokens (sorted by length for greedy matching)
_POLYMETAL_TOKENS_SORTED = sorted(POLYMETAL_HOL_TOKENS.keys(), key=len, reverse=True)
POLYMETAL_TOKEN_PATTERN = re.compile(
    r'(' + '|'.join(re.escape(k) for k in _POLYMETAL_TOKENS_SORTED) + r')(\d*)',
    re.IGNORECASE
)

# Legacy alias for backward compatibility
POLYMETAL_HOL_RULES = POLYMETAL_HOL_TOKENS

# Pre-processing patterns for pip-1 auto-fix
CURLY_TO_PAREN_RE = re.compile(r'\{([^}]+)\}')
LEADING_PLUS_OXYANION_HTML_RE = re.compile(
    r'(?<=[A-Za-z0-9>])\+([A-Z][a-z]?O(?:<sub>\d+</sub>|\d+))',
    re.IGNORECASE
)
HYDRATE_DOT_HTML_RE = re.compile(
    r'\.((?:\d*)?H(?:<sub>2</sub>|2)O)',
    re.IGNORECASE
)
