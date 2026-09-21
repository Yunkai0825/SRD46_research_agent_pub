"""Shared tiny helpers for markdown table rendering.

Every per-entity compactor (stability, network, citation,
similar_ligand, pka_values, pka_ligands) imports these instead of
duplicating formatting logic.

Helpers
-------
``_cell(val, max_len)``
    Stringify *val* for a markdown table cell; returns ``***`` for
    None / blank / ``\\N``; truncates with ``…`` beyond *max_len*.
``_esc(val)``
    Like ``_cell`` but wraps the result in backticks when it contains
    ``[`` or ``]`` (which would break markdown links).
``_ctype(raw)``
    Map single-char constant-type codes (``K`` → logK, ``H`` → ΔH,
    ``S`` → ΔS) to human-readable labels.
``_num(val)``
    Format a numeric value: round floats to 4 decimal places with
    trailing-zero suppression; pass-through ints; ``***`` for None.
``_range_str(lo, hi)``
    Format a lo~hi range, collapsing to a single value when equal.
"""
from __future__ import annotations

from typing import Any


def _cell(val: Any, max_len: int = 80) -> str:
    """Stringify a value for a markdown table cell, truncating if needed."""
    if val is None or str(val).strip() == "" or str(val).strip() == "\\N":
        return "***"
    s = str(val)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _esc(val: Any) -> str:
    """Wrap value in backticks if it contains markdown-sensitive brackets."""
    s = _cell(val)
    if s == "***":
        return s
    if "[" in s or "]" in s:
        return f"`{s}`"
    return s


_CTYPE_MAP = {"K": "logK", "H": "ΔH", "S": "ΔS"}


def _ctype(raw: Any) -> str:
    """Map constant_type code to readable label."""
    return _CTYPE_MAP.get(str(raw), str(raw) if raw else "?")


def _num(val: Any) -> str:
    """Format a numeric value: round floats, pass-through ints."""
    if val is None:
        return "***"
    if isinstance(val, float):
        return f"{round(val, 4):g}"
    return str(val)


def _range_str(lo: Any, hi: Any) -> str:
    """Format a lo~hi range, collapsing when equal."""
    s_lo, s_hi = _num(lo), _num(hi)
    if s_lo == s_hi:
        return s_lo
    return f"{s_lo}~{s_hi}"


# ── speciation reasoning hint (anti-hallucination footer) ─────────
#
# Appended by every public ``compact_search_*`` / ``compact_db_*`` /
# ``compact_execute_srd46_sql`` / ``compact_inspect_card`` /
# ``compact_system_catalog`` compactor as a *weak hint*: it reminds the
# downstream agent that any speciation facet ABSENT from the rows above
# must be fetched explicitly, never inferred. The 7 primary facets are
# the minimal token set needed for non-hallucinated aqueous-speciation
# reasoning; secondary facets (citations, networks, pKa ladders) are
# critical context but may be lazily retrieved.
_SPECIATION_HINT_LINES = [
    "<speciation_hint>",
    "For your context, aqueous-speciation reasoning generally requires the full facet set." 
    "Consider those facets when compacting the tool results."
    "NEVER infer or hallucinate values that are not listed in the tool results.",
    "  PRIMARY (must all be grounded in returned rows):",
    "    1. ligand structure   — SMILES / InChI / HxL definition",
    "    2. ligand identity    — name, ligand_id, ligand_class_name",
    "    3. complex stoichiometry — M_pL_qH_r, beta_definition_id",
    "    4. equilibrium equation — equation_str / reaction_type",
    "    5. stability constant value — log K (`constant_type='K'`; ΔH='H', ΔS='S' — no separate β code, stepwise vs overall distinguished by `beta_definition_id`)",
    "    6. measurement temperature — temperature_c",
    "    7. ionic strength + medium — ionic_strength_mol_l, electrolyte",
    "  SECONDARY (critical context, may be fetched on demand):",
    "    • literature citations (search_citations / inspect_card)",
    "    • equilibrium networks (search_networks)",
    "    • pKa ladder of the ligand (search_pka_ligands)",
    "</speciation_hint>",
]


def speciation_context_hint() -> str:
    """Return the standard anti-hallucination speciation-context footer.

    Appended by every top-level public compactor so the orchestrator and
    sub-agents are reminded — at the point of consuming each tool result
    — that missing facets must be fetched, not invented.
    """
    return "\n".join(_SPECIATION_HINT_LINES) + "\n"
