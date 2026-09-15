"""Chemical search normalization for the standalone database browser."""

from __future__ import annotations

import re

_SUPERSCRIPT_MAP = str.maketrans({
    "\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3",
    "\u2074": "4", "\u2075": "5", "\u2076": "6", "\u2077": "7",
    "\u2078": "8", "\u2079": "9",
    "\u207a": "+", "\u207b": "-",
})
_BARE_SYM = r"(?P<sym>(?<![A-Za-z])[A-Z][a-z]?)"
_PATTERN_DIGIT_FIRST = re.compile(_BARE_SYM + r"\^?(?P<n>\d+)(?P<sign>[+-])(?!\])")
_PATTERN_SIGN_FIRST = re.compile(_BARE_SYM + r"\^?(?P<sign>[+-])(?P<n>\d+)(?!\])")
_PATTERN_BARE_SIGN = re.compile(_BARE_SYM + r"\^?(?P<sign>[+-])(?!\d)(?!\])")

def _to_canonical(sym: str, n: str, sign: str) -> str:
    return f"{sym}^[{(n or '1')}{sign}]"

def normalize_chem_query(q: str) -> str:
    if not q:
        return q
    s = q.translate(_SUPERSCRIPT_MAP)
    s = _PATTERN_DIGIT_FIRST.sub(lambda m: _to_canonical(m["sym"], m["n"], m["sign"]), s)
    s = _PATTERN_SIGN_FIRST.sub(lambda m: _to_canonical(m["sym"], m["n"], m["sign"]), s)
    s = _PATTERN_BARE_SIGN.sub(lambda m: _to_canonical(m["sym"], "1", m["sign"]), s)
    return s


__all__ = ["normalize_chem_query"]


def ligand_search_terms(query: str) -> list[str]:
    """Include the acid name for a familiar conjugate-base search term.

    This expands name lookup only; molecular structures and protonation states
    remain those recorded in the database.
    """
    aliases = {"citrate": "citric acid"}
    terms = [query]
    alias = aliases.get(query.casefold())
    if alias and alias != query:
        terms.append(alias)
    return terms
