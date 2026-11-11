"""Shared chemistry-query string normalization.

Used by:
  - the SRD46 browser (free-text ``q=`` boxes), and
  - ``_sql_ast.normalize_chem_literals`` (string literals inside WHERE
    clauses targeting metal-name columns).

The DB stores metal symbols in the canonical form ``Cu^[2+]``.  Users
type many shorthands (``Cu2+``, ``Cu²⁺``, ``Cu+2``, ``Cu^2+``, ``Cu+``);
this helper folds those variants to the canonical form so a single
``=`` or ``LIKE`` comparison matches the stored value.

The transformation is idempotent and leaves anything that doesn't look
like ``Sym[charge]`` unchanged.
"""

from __future__ import annotations

import re

# Unicode superscript digits / sign characters mapped to ASCII equivalents.
_SUPERSCRIPT_MAP = str.maketrans({
    "\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3",
    "\u2074": "4", "\u2075": "5", "\u2076": "6", "\u2077": "7",
    "\u2078": "8", "\u2079": "9",
    "\u207a": "+", "\u207b": "-",
})

#   Sym = uppercase letter + optional lowercase letter (e.g. C, Cu, Fe, Cl)
#   Charge variants accepted (post-superscript folding):
#     Cu2+   Cu+2   Cu^2+   Cu^+2   Cu+   Cu^+
_BARE_SYM = r"(?P<sym>(?<![A-Za-z])[A-Z][a-z]?)"
_PATTERN_DIGIT_FIRST = re.compile(_BARE_SYM + r"\^?(?P<n>\d+)(?P<sign>[+-])(?!\])")
_PATTERN_SIGN_FIRST = re.compile(_BARE_SYM + r"\^?(?P<sign>[+-])(?P<n>\d+)(?!\])")
_PATTERN_BARE_SIGN = re.compile(_BARE_SYM + r"\^?(?P<sign>[+-])(?!\d)(?!\])")


def _to_canonical(sym: str, n: str, sign: str) -> str:
    n = n or "1"
    return f"{sym}^[{n}{sign}]"


def normalize_chem_query(q: str) -> str:
    """Fold common metal-charge shorthands to ``Sym^[N+]`` canonical form.

    Idempotent. Empty / non-matching input is returned unchanged.
    """
    if not q:
        return q
    s = q.translate(_SUPERSCRIPT_MAP)
    s = _PATTERN_DIGIT_FIRST.sub(
        lambda m: _to_canonical(m["sym"], m["n"], m["sign"]), s,
    )
    s = _PATTERN_SIGN_FIRST.sub(
        lambda m: _to_canonical(m["sym"], m["n"], m["sign"]), s,
    )
    s = _PATTERN_BARE_SIGN.sub(
        lambda m: _to_canonical(m["sym"], "1", m["sign"]), s,
    )
    return s
