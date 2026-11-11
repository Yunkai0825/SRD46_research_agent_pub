"""
Metal name resolution helpers for SRD-46.

Handles English element names, oxidation-state suffixes, charge notation,
DB-format names (``Cu^[2+]``), and common aliases (``ferric`` → ``Fe3+``).
"""

import re as _re


# ── Element name → symbol mapping ────────────────────────────────────

_ELEMENT_SYMBOLS: dict[str, str] = {
    "hydrogen": "H", "lithium": "Li", "beryllium": "Be", "boron": "B",
    "sodium": "Na", "magnesium": "Mg", "aluminum": "Al", "aluminium": "Al",
    "silicon": "Si", "potassium": "K", "calcium": "Ca",
    "scandium": "Sc", "titanium": "Ti", "vanadium": "V",
    "chromium": "Cr", "manganese": "Mn", "iron": "Fe",
    "cobalt": "Co", "nickel": "Ni", "copper": "Cu",
    "zinc": "Zn", "gallium": "Ga", "germanium": "Ge",
    "arsenic": "As", "selenium": "Se", "rubidium": "Rb",
    "strontium": "Sr", "yttrium": "Y", "zirconium": "Zr",
    "niobium": "Nb", "molybdenum": "Mo", "technetium": "Tc",
    "ruthenium": "Ru", "rhodium": "Rh", "palladium": "Pd",
    "silver": "Ag", "cadmium": "Cd", "indium": "In",
    "tin": "Sn", "antimony": "Sb", "tellurium": "Te",
    "cesium": "Cs", "caesium": "Cs", "barium": "Ba",
    "lanthanum": "La", "cerium": "Ce", "praseodymium": "Pr",
    "neodymium": "Nd", "promethium": "Pm", "samarium": "Sm",
    "europium": "Eu", "gadolinium": "Gd", "terbium": "Tb",
    "dysprosium": "Dy", "holmium": "Ho", "erbium": "Er",
    "thulium": "Tm", "ytterbium": "Yb", "lutetium": "Lu",
    "hafnium": "Hf", "tantalum": "Ta", "tungsten": "W",
    "rhenium": "Re", "osmium": "Os", "iridium": "Ir",
    "platinum": "Pt", "gold": "Au", "mercury": "Hg",
    "thallium": "Tl", "lead": "Pb", "bismuth": "Bi",
    "polonium": "Po", "radium": "Ra", "actinium": "Ac",
    "thorium": "Th", "protactinium": "Pa", "uranium": "U",
    "neptunium": "Np", "plutonium": "Pu", "americium": "Am",
    "curium": "Cm", "berkelium": "Bk", "californium": "Cf",
}


# ── Common metal query aliases ───────────────────────────────────────

_METAL_QUERY_ALIASES: dict[str, str] = {
    "h+": "H+", "h +": "H+",
    "proton": "H+", "protons": "H+",
    "hydrogen cation": "H+", "hydrogen ion": "H+", "hydron": "H+",
    "cu(i)": "Cu+", "copper(i)": "Cu+", "cuprous": "Cu+", "cuprous ion": "Cu+",
    "cu(ii)": "Cu2+", "copper(ii)": "Cu2+", "cupric": "Cu2+", "cupric ion": "Cu2+",
    "fe(ii)": "Fe2+", "iron(ii)": "Fe2+", "ferrous": "Fe2+", "ferrous ion": "Fe2+",
    "fe(iii)": "Fe3+", "iron(iii)": "Fe3+", "ferric": "Fe3+", "ferric ion": "Fe3+",
    "co(ii)": "Co2+", "cobalt(ii)": "Co2+", "cobaltous": "Co2+", "cobaltous ion": "Co2+",
    "co(iii)": "Co3+", "cobalt(iii)": "Co3+", "cobaltic": "Co3+", "cobaltic ion": "Co3+",
    "ni(ii)": "Ni2+", "nickel(ii)": "Ni2+", "nickelous": "Ni2+", "nickelous ion": "Ni2+",
    "cr(ii)": "Cr2+", "chromium(ii)": "Cr2+", "chromous": "Cr2+", "chromous ion": "Cr2+",
    "cr(iii)": "Cr3+", "chromium(iii)": "Cr3+", "chromic": "Cr3+", "chromic ion": "Cr3+",
    "sn(ii)": "Sn2+", "tin(ii)": "Sn2+", "stannous": "Sn2+", "stannous ion": "Sn2+",
    "sn(iv)": "Sn4+", "tin(iv)": "Sn4+", "stannic": "Sn4+", "stannic ion": "Sn4+",
    "pb(ii)": "Pb2+", "lead(ii)": "Pb2+", "plumbous": "Pb2+", "plumbous ion": "Pb2+",
    "pb(iv)": "Pb4+", "lead(iv)": "Pb4+", "plumbic": "Pb4+", "plumbic ion": "Pb4+",
    "hg(i)": "Hg+", "mercury(i)": "Hg+", "mercurous": "Hg+", "mercurous ion": "Hg+",
    "hg(ii)": "Hg2+", "mercury(ii)": "Hg2+", "mercuric": "Hg2+", "mercuric ion": "Hg2+",
    "au(i)": "Au+", "gold(i)": "Au+", "aurous": "Au+", "aurous ion": "Au+",
    "au(iii)": "Au3+", "gold(iii)": "Au3+", "auric": "Au3+", "auric ion": "Au3+",
}


# ── Roman numeral → integer ──────────────────────────────────────────

_ROMAN_TO_INT = {
    "I": 1, "II": 2, "III": 3, "IV": 4,
    "V": 5, "VI": 6, "VII": 7, "VIII": 8,
}


# ── Compiled regex patterns ──────────────────────────────────────────

_OX_STATE_RE = _re.compile(
    r"^\s*(.*?)\s*\("
    r"(I{1,4}V?|VI{0,3}|\d+\+?)"
    r"\)\s*$",
    _re.IGNORECASE,
)

_CHARGE_SUFFIX_RE = _re.compile(r"(\d*[+-])\s*$")

_DB_FORMAT_RE = _re.compile(r"^([A-Z][a-z]?)\^\[(\d*[+-])\]$")

_TRAILING_METAL_WORDS_RE = _re.compile(
    r"\s+(?:ion|cation|metal|metal\s+ion)\s*$", _re.IGNORECASE,
)

_STRUCTURED_METAL_FORMULA_RE = _re.compile(
    r"(?:\^\[|_\[|[A-Z][a-z]?[A-Z][A-Za-z0-9]*[+-]?$)"
)


# ── Public functions ─────────────────────────────────────────────────

def _normalize_metal_query(name: str | None) -> str:
    """Clean common LLM phrasing to a compact metal query string."""
    if name is None:
        return ""
    if not isinstance(name, str):
        name = str(name)
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        return ""
    alias = _METAL_QUERY_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    if _STRUCTURED_METAL_FORMULA_RE.search(cleaned):
        return cleaned
    cleaned = _TRAILING_METAL_WORDS_RE.sub("", cleaned)
    alias = _METAL_QUERY_ALIASES.get(cleaned.lower())
    return alias or cleaned


def _oxidation_token_to_charge(token: str) -> str | None:
    """Convert '(III)' or '(2+)' suffix tokens to a charge string like '3+'."""
    token = token.strip().upper()
    if token.endswith("+"):
        digits = token[:-1]
        if digits.isdigit():
            return f"{digits}+"
    if token.isdigit():
        return f"{token}+"
    return f"{_ROMAN_TO_INT[token]}+" if token in _ROMAN_TO_INT else None


def _expand_metal_name(name: str) -> list[str]:
    """Return search terms for a metal name query.

    Handles many input forms and expands to match the DB format
    ``symbol^[charge]`` (e.g. ``Cu^[2+]``).

    Examples::

        copper       -> ['copper', 'Cu']
        copper(II)   -> ['copper(II)', 'copper', 'Cu2+', 'Cu^[2+]']
        Cu2+         -> ['Cu2+', 'Cu', 'Cu^[2+]']
        ferric       -> ['Fe3+', 'Fe', 'Fe^[3+]']
        Cu^[2+]      -> ['Cu^[2+]', 'Cu', 'Cu2+', 'copper']
    """
    name = _normalize_metal_query(name)
    terms_set: set[str] = set()
    terms_set.add(name)

    # --- 0. Parse DB format: "Cu^[2+]" -> base="Cu", charge="2+"
    db_m = _DB_FORMAT_RE.match(name)
    if db_m:
        base = db_m.group(1)
        charge = db_m.group(2)
        terms_set.add(base)
        terms_set.add(f"{base}{charge}")
        for elem_name, elem_sym in _ELEMENT_SYMBOLS.items():
            if elem_sym.lower() == base.lower():
                terms_set.add(elem_name)
                break
        return list(terms_set)

    # --- 1. Parse parenthesised oxidation state: "copper(II)" -> base+charge
    base = name
    charge = None
    ox_m = _OX_STATE_RE.match(name)
    if ox_m:
        base = ox_m.group(1).strip() or name
        charge = _oxidation_token_to_charge(ox_m.group(2))
        if charge:
            terms_set.add(f"{base}{charge}")
    terms_set.add(base)

    # --- 2. Strip bare charge suffix: "Cu2+" -> "Cu", charge="2+"
    m = _CHARGE_SUFFIX_RE.search(base)
    if m:
        charge = m.group(1)
        base = base[: m.start()].strip()
        terms_set.add(base)
        terms_set.add(f"{base}^[{charge}]")

    # --- 3. Element-name → symbol lookup
    sym = _ELEMENT_SYMBOLS.get(base.lower())
    if sym:
        terms_set.add(sym)
        if charge:
            terms_set.add(f"{sym}{charge}")
            terms_set.add(f"{sym}^[{charge}]")

    # --- 4. Reverse lookup: symbol → element name (e.g. Cu -> copper)
    if not sym:
        for elem_name, elem_sym in _ELEMENT_SYMBOLS.items():
            if elem_sym.lower() == base.lower():
                terms_set.add(elem_name)
                break

    return list(terms_set)


def _extract_symbol_charge_query(symbol: str) -> tuple[str | None, int | None]:
    """Extract a base symbol and optional charge from inputs like Fe2+ or Cu^[2+]."""
    normalized = _normalize_metal_query(symbol)

    db_match = _DB_FORMAT_RE.match(normalized)
    if db_match:
        base_symbol = db_match.group(1)
        charge_token = db_match.group(2)
        digits = "".join(ch for ch in charge_token if ch.isdigit())
        return base_symbol, int(digits) if digits else 1

    charge_match = _CHARGE_SUFFIX_RE.search(normalized)
    if charge_match:
        charge_token = charge_match.group(1)
        base_symbol = normalized[: charge_match.start()].strip() or None
        digits = "".join(ch for ch in charge_token if ch.isdigit())
        return base_symbol, int(digits) if digits else 1

    if normalized:
        return normalized, None
    return None, None
