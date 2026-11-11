"""Pure-regex extraction of numeric values, canonical IDs, and chemical
names from markdown text.

This module shares numeric-token conventions with the live claim-grounding
pipeline and the repository's reference-ID coverage fixtures.
"""
from __future__ import annotations

import re
from typing import Sequence

from .models import ChemSpan, IdSpan, NumericSpan, TokenSpan

# ---------------------------------------------------------------------------
# Numeric extraction (mirrors grounding.py patterns)
# ---------------------------------------------------------------------------

NUMERIC_TOKEN_RE = re.compile(
    r"(?<![\w.])(?P<number>[−\-]?\d+(?:\.\d+)?)(?!(?:\.\d)|[\w])"
)

# Context-based quantity type inference (simplified from grounding.py)
_QUANTITY_CONTEXT: list[tuple[str, re.Pattern[str]]] = [
    ("log_K",           re.compile(r"(?:log\s*(?:k|β|beta|K))", re.I)),
    ("pKa",             re.compile(r"\bpKa\b", re.I)),
    ("temperature",     re.compile(r"(?:°\s*C|temperature|temp\b)", re.I)),
    ("ionic_strength",  re.compile(r"(?:ionic\s*strength|\bI\s*=|\bmol/[Ll])", re.I)),
    ("delta_H",         re.compile(r"(?:ΔH|δH|delta\s*H|kJ/mol)", re.I)),
    ("delta_S",         re.compile(r"(?:ΔS|δS|delta\s*S|J/\(?mol)", re.I)),
    ("delta_G",         re.compile(r"(?:ΔG|δG|delta\s*G)", re.I)),
]


def _infer_quantity_type(context: str) -> str | None:
    """Return the most likely quantity type from surrounding text."""
    for qty, pat in _QUANTITY_CONTEXT:
        if pat.search(context):
            return qty
    return None


def extract_numbers(text: str) -> list[NumericSpan]:
    """Extract all numeric tokens with character-level positions."""
    spans: list[NumericSpan] = []
    for m in NUMERIC_TOKEN_RE.finditer(text):
        raw = m.group("number").replace("−", "-")
        try:
            value = float(raw)
        except ValueError:
            continue
        # Use surrounding 60-char window for context inference
        ctx_start = max(0, m.start() - 60)
        ctx_end = min(len(text), m.end() + 60)
        context = text[ctx_start:ctx_end]
        qty = _infer_quantity_type(context)
        spans.append(NumericSpan(
            start=m.start(), end=m.end(), text=m.group(0),
            span_type="numeric", value=value, quantity_type=qty,
        ))
    return spans


# ---------------------------------------------------------------------------
# Canonical-ID extraction
# ---------------------------------------------------------------------------

_ID_PREFIX_MAP: dict[str, str] = {
    "metal":    "metal",
    "ligand":   "ligand",
    "vlm":      "vlm",
    "beta_def": "beta_def",
    "pka":      "pka",
    "ref_eq_net": "network",
    "ref_eq_map": "map",
    "lit":      "literature",
}

# Match patterns like metal_41, vlm_93847, beta_def_812, ref_eq_net_86
PREFIXED_ID_RE = re.compile(
    r"\b(?P<prefix>metal|ligand|vlm|beta_def|pka|ref_eq_net|ref_eq_map|lit)"
    r"_(?P<id>\d+)\b"
)


def extract_prefixed_ids(text: str) -> list[IdSpan]:
    """Extract all canonical prefixed entity IDs."""
    spans: list[IdSpan] = []
    for m in PREFIXED_ID_RE.finditer(text):
        prefix = m.group("prefix")
        entity_type = _ID_PREFIX_MAP.get(prefix, prefix)
        spans.append(IdSpan(
            start=m.start(), end=m.end(), text=m.group(0),
            span_type="id", entity_type=entity_type,
            raw_id=int(m.group("id")),
        ))
    return spans


# ---------------------------------------------------------------------------
# Chemical name extraction
# ---------------------------------------------------------------------------

# Common ligand abbreviations (supplemented at runtime from DB)
_COMMON_ABBREVIATIONS = {
    "EDTA", "NTA", "DTPA", "HEDTA", "CDTA", "EGTA", "TTHA",
    "IDA", "MIDA", "ODA", "TDA", "HIMDA", "ADA",
}

# Ion/formula patterns: Cu²⁺, Fe³⁺, Zn2+, OH⁻, H₂O, NH₃, etc.
_ION_RE = re.compile(
    r"\b[A-Z][a-z]?"                       # element symbol
    r"(?:[₂₃₄₅₆₇₈₉\d])*"                 # subscript digits
    r"(?:[²³⁴⁺⁻\d]*[⁺⁻+\-])"             # charge
)

# IUPAC-style chemical names with parentheses, hyphens, greek letters
_CHEM_NAME_RE = re.compile(
    r"\b(?:"
    # Element names (≥3 chars, capitalized)
    r"(?:copper|zinc|iron|nickel|cobalt|manganese|cadmium|lead|mercury|silver|"
    r"chromium|alumin(?:i?um)|calcium|magnesium|barium|strontium|beryllium|"
    r"titanium|vanadium|platinum|palladium|gold|tin|arsenic|antimony|bismuth|"
    r"uranium|thorium|cerium|lanthanum|neodymium|europium|gadolinium|"
    r"terbium|dysprosium|holmium|erbium|thulium|ytterbium|lutetium|"
    r"yttrium|scandium|zirconium|hafnium|niobium|tantalum|molybdenum|"
    r"tungsten|rhenium|osmium|iridium|rhodium|ruthenium|"
    # Common ligand names
    r"glycine|alanine|histidine|cysteine|glutamate|aspartate|"
    r"oxalate|citrate|tartrate|malonate|succinate|acetate|formate|"
    r"sulfate|nitrate|chloride|bromide|iodide|fluoride|hydroxide|"
    r"ammonia|pyridine|bipyridine|phenanthroline|"
    r"ethylenediamine|diethylenetriamine|triethylenetetramine|"
    r"salicylate|catechol|picolinate|"
    # Abbreviations captured separately below
    r"thiocyanate|thiosulfate|phosphate|carbonate|bicarbonate|cyanide)"
    r")"
    r"(?:\s*\([^)]{1,40}\))?",  # optional parenthetical (e.g. "(II)")
    re.IGNORECASE,
)

# Abbreviation pattern (separate for exact-case matching)
_ABBREV_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(a) for a in sorted(_COMMON_ABBREVIATIONS, key=len, reverse=True)) + r")\b"
)

# Simple formula pattern: H2L, ML2, Cu(OH)2, [Cu(NH3)4]2+
_FORMULA_RE = re.compile(
    r"(?:"
    r"\[?[A-Z][a-z]?"                       # element or bracket-element
    r"(?:\([A-Za-z0-9]+\)\d*|\d)*"           # groups like (OH)2
    r"(?:[A-Z][a-z]?(?:\d+)?)*"             # additional elements
    r"\]?"
    r"(?:\d*[⁺⁻+\-])?)"                     # optional charge
)


def extract_chemical_names(
    text: str,
    extra_names: Sequence[str] = (),
) -> list[ChemSpan]:
    """Extract chemical names, formulas, and abbreviations.

    Parameters
    ----------
    extra_names
        Additional ligand/metal names to match (e.g. from DB ligand_card).
    """
    seen: set[tuple[int, int]] = set()
    spans: list[ChemSpan] = []

    def _add(m: re.Match[str], normalized: str = "") -> None:
        key = (m.start(), m.end())
        if key in seen:
            return
        # Skip very short matches that are likely false positives
        if len(m.group(0).strip()) < 2:
            return
        seen.add(key)
        spans.append(ChemSpan(
            start=m.start(), end=m.end(), text=m.group(0),
            span_type="chem", normalized_name=normalized or m.group(0).strip(),
        ))

    # Named chemicals (glycine, copper, EDTA, …)
    for m in _CHEM_NAME_RE.finditer(text):
        _add(m, m.group(0).strip().lower())

    # Abbreviations (EDTA, NTA, …)
    for m in _ABBREV_RE.finditer(text):
        _add(m, m.group(0).strip().upper())

    # Ion patterns (Cu²⁺, Fe3+, …)
    for m in _ION_RE.finditer(text):
        _add(m)

    # Extra names from DB (sorted long→short to prefer longer matches)
    if extra_names:
        escaped = sorted(extra_names, key=len, reverse=True)
        # Build chunked pattern to avoid regex size limits
        for chunk_start in range(0, len(escaped), 200):
            chunk = escaped[chunk_start:chunk_start + 200]
            pat = re.compile(
                r"\b(?:" + "|".join(re.escape(n) for n in chunk) + r")\b",
                re.IGNORECASE,
            )
            for m in pat.finditer(text):
                _add(m, m.group(0).strip())

    spans.sort(key=lambda s: (s.start, -s.end))
    return spans


# ---------------------------------------------------------------------------
# Unified extraction
# ---------------------------------------------------------------------------

def extract_all_spans(
    text: str,
    extra_chem_names: Sequence[str] = (),
) -> list[TokenSpan]:
    """Run all extractors and return merged, de-duplicated spans.

    Longer spans take priority when overlapping.
    """
    all_spans: list[TokenSpan] = []
    all_spans.extend(extract_numbers(text))
    all_spans.extend(extract_prefixed_ids(text))
    all_spans.extend(extract_chemical_names(text, extra_chem_names))
    return _deduplicate_spans(all_spans)


def _deduplicate_spans(spans: list[TokenSpan]) -> list[TokenSpan]:
    """Remove overlapping spans, preferring longer ones and IDs > chem > numeric."""
    priority = {"id": 0, "chem": 1, "numeric": 2}
    sorted_spans = sorted(
        spans,
        key=lambda s: (-((s.end - s.start)), priority.get(s.span_type, 9), s.start),
    )
    accepted: list[TokenSpan] = []
    occupied: list[tuple[int, int]] = []

    for span in sorted_spans:
        overlaps = any(
            not (span.end <= occ_start or span.start >= occ_end)
            for occ_start, occ_end in occupied
        )
        if not overlaps:
            accepted.append(span)
            occupied.append((span.start, span.end))

    accepted.sort(key=lambda s: s.start)
    return accepted
