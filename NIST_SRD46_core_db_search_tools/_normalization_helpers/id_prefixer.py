"""
ID-prefix normalization for SRD-46 search outputs.

All public API functions return entity IDs as prefixed strings
(e.g. ``"metal_41"``, ``"vlm_93847"``, ``"beta_def_812"``) instead
of raw integers.  This module holds the canonical mapping and the
helper functions used by every output path.

Prefix catalogue
----------------
=================  ============  ========================
DB column          Prefix        Example
=================  ============  ========================
metal_id           metal         metal_41
ligand_id          ligand        ligand_5760
vlm_id             vlm           vlm_93847
beta_definition_id beta_def      beta_def_812
pka_id             pka           pka_1
map_id             ref_eq_map    ref_eq_map_14
network_db_id      ref_eq_net    ref_eq_net_86
literature_alt_id  lit           lit_4321
=================  ============  ========================
"""

from __future__ import annotations

from typing import Any


# ── Column → prefix mapping ─────────────────────────────────────────

_COLUMN_TO_PREFIX: dict[str, str] = {
    "metal_id":           "metal",
    "ligand_id":          "ligand",
    "vlm_id":             "vlm",
    "source_vlm_id":      "vlm",             # pKa → source H+ VLM
    "example_vlm_id":     "vlm",             # citation → representative VLM
    "beta_definition_id": "beta_def",
    "pka_id":             "pka",
    "map_id":             "ref_eq_map",
    "network_db_id":      "ref_eq_net",
    "network_id":         "ref_eq_net",       # alias used in card_inspect
    "node_id":            "eq_node",          # alias used in card_inspect
    "literature_alt_id":  "lit",
}

# Reverse: prefix → canonical column name
_PREFIX_TO_COLUMN: dict[str, str] = {
    "metal":      "metal_id",
    "ligand":     "ligand_id",
    "vlm":        "vlm_id",
    "beta_def":   "beta_definition_id",
    "pka":        "pka_id",
    "ref_eq_map": "map_id",
    "ref_eq_net": "network_db_id",
    "lit":        "literature_alt_id",
}

_KNOWN_PREFIXES_LONGEST_FIRST = sorted(_PREFIX_TO_COLUMN, key=len, reverse=True)


# ── Prefixing  (int → str) ──────────────────────────────────────────

def prefix_id_value(column_name: str, value: Any) -> Any:
    """``('metal_id', 41)`` → ``'metal_41'``.

    Returns *value* unchanged when the column is not in the mapping or
    the value is ``None``.
    """
    prefix = _COLUMN_TO_PREFIX.get(column_name)
    if prefix is None or value is None:
        return value
    return f"{prefix}_{value}"


def prefix_ids_in_row(row: dict) -> dict:
    """Transform every known ID column in *row* to its prefixed form (in-place)."""
    for col, prefix in _COLUMN_TO_PREFIX.items():
        if col in row and row[col] is not None:
            row[col] = f"{prefix}_{row[col]}"
    return row


def prefix_ids_in_rows(rows: list[dict]) -> list[dict]:
    """Apply :func:`prefix_ids_in_row` to each dict in *rows*."""
    for row in rows:
        prefix_ids_in_row(row)
    return rows


# ── Compact display → canonical expansion ────────────────────────────

import re as _re

_COMPACT_RE = _re.compile(
    r'^(\w+?)_\(\s*'          # prefix_(
    r'([\d\s,]+)'             # comma-separated numeric ids
    r'\s*\)$'                 # )
)

_DIFF_RE = _re.compile(
    r'^(\d+)\s+diff(?:erent)?\s+(\w+)$',   # "5 diff beta_def" or "5 different beta_def"
    _re.IGNORECASE,
)


def normalize_id_input(value: str) -> list[str]:
    """Expand compact display formats to a list of canonical prefixed IDs.

    Handles three cases:

    1. **Already canonical** — ``"beta_def_812"`` → ``["beta_def_812"]``
    2. **Compact tuple** — ``"beta_def_(32, 79)"`` → ``["beta_def_32", "beta_def_79"]``
    3. **Diff summary** — ``"5 diff beta_def"`` → ``[]`` (no IDs recoverable)

    Examples
    --------
    >>> normalize_id_input("beta_def_(32, 79)")
    ['beta_def_32', 'beta_def_79']
    >>> normalize_id_input("metal_(41)")
    ['metal_41']
    >>> normalize_id_input("5 diff beta_def")
    []
    >>> normalize_id_input("vlm_93847")
    ['vlm_93847']
    """
    value = str(value).strip()

    # Case 2: compact tuple — prefix_(id1, id2, ...)
    m = _COMPACT_RE.match(value)
    if m:
        prefix = m.group(1)
        nums = [n.strip() for n in m.group(2).split(",") if n.strip()]
        return [f"{prefix}_{n}" for n in nums]

    # Case 3: diff summary — "N diff prefix" — no recoverable IDs
    if _DIFF_RE.match(value):
        return []

    # Case 1: already canonical — return as single-element list
    return [value]


# ── Parsing  (str → prefix + int) ───────────────────────────────────

def parse_prefixed_id(prefixed: str) -> tuple[str, int]:
    """Parse a prefixed-id string into its ``(prefix, numeric_id)`` pair.

    Also accepts compact display formats produced by compactors:
    ``"beta_def_(812)"`` is normalized to ``"beta_def_812"`` before
    parsing.  Multi-ID compacts like ``"beta_def_(32, 79)"`` use only
    the **first** ID.

    Examples
    --------
    >>> parse_prefixed_id("metal_41")
    ('metal', 41)
    >>> parse_prefixed_id("beta_def_812")
    ('beta_def', 812)
    >>> parse_prefixed_id("beta_def_(812)")
    ('beta_def', 812)
    >>> parse_prefixed_id("beta_def_(32, 79)")
    ('beta_def', 32)
    >>> parse_prefixed_id("ref_eq_net_86")
    ('ref_eq_net', 86)

    Raises :class:`ValueError` when the string does not start with a
    known prefix.
    """
    prefixed = str(prefixed).strip()

    # Try compact-display expansion first
    expanded = normalize_id_input(prefixed)
    if expanded and expanded[0] != prefixed:
        prefixed = expanded[0]
    elif not expanded:
        raise ValueError(
            f"No recoverable ID from display string '{prefixed}'."
        )
    for pfx in _KNOWN_PREFIXES_LONGEST_FIRST:
        tag = pfx + "_"
        if prefixed.startswith(tag):
            remainder = prefixed[len(tag):]
            try:
                return pfx, int(remainder)
            except ValueError:
                raise ValueError(
                    f"Non-numeric ID after prefix '{pfx}': '{remainder}'"
                ) from None
    raise ValueError(
        f"Unknown prefix in '{prefixed}'. "
        f"Known prefixes: {', '.join(_KNOWN_PREFIXES_LONGEST_FIRST)}"
    )


def unprefix_id(value) -> int:
    """Extract raw integer from either a prefixed string or a plain int.

    Useful inside internal helpers that receive output from a public
    function that already applied prefixing.

    >>> unprefix_id("ligand_5760")
    5760
    >>> unprefix_id(5760)
    5760
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        _, n = parse_prefixed_id(value)
        return n
    return int(value)
