"""Data classes for the regex enrichment pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ── Span type tag → class map (for deserialization) ─────────

_SPAN_CLS_TAG = {
    "NumericSpan": "numeric",
    "IdSpan": "id",
    "ChemSpan": "chem",
    "TokenSpan": "generic",
}


@dataclass(slots=True)
class TokenSpan:
    """A single annotated span in source text."""
    start: int
    end: int
    text: str
    span_type: str          # "numeric", "id", "chem"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NumericSpan(TokenSpan):
    """A numeric value extracted from text."""
    value: float = 0.0
    quantity_type: str | None = None   # log_K, pKa, temperature, …


@dataclass(slots=True)
class IdSpan(TokenSpan):
    """A canonical prefixed ID (e.g. ``metal_41``)."""
    entity_type: str = ""
    raw_id: int = 0


@dataclass(slots=True)
class ChemSpan(TokenSpan):
    """A chemical name or formula token."""
    normalized_name: str = ""


@dataclass(slots=True)
class NumericMatch:
    """One entry in the top-10 closest DB measurement list."""
    db_value: float
    distance: float
    source_id: str           # prefixed_id (e.g. vlm_123)
    source_type: str         # table / card type
    measurement_detail: str  # e.g. "logK @ 25°C, I=0.1"


@dataclass(slots=True)
class ParagraphAnnotation:
    """All annotations for a single paragraph (text block)."""
    paragraph_index: int
    text: str
    spans: list[TokenSpan] = field(default_factory=list)
    numeric_matches: dict[int, list[NumericMatch]] = field(default_factory=dict)
    # key = index into self.spans for NumericSpan entries


@dataclass(slots=True)
class EnrichedDocument:
    """Fully annotated document (one of result / history / ref_ids)."""
    source_file: str
    doc_type: str            # "result", "history", "ref_ids"
    paragraphs: list[ParagraphAnnotation] = field(default_factory=list)


# =====================================================================
# Claim-based annotation models
# =====================================================================

CLAIM_TYPES = (
    "counting",
    "comparison",
    "trend",
    "listing",
    "range",
    "exact_value",
    "property_attribution",
    "existence_absence",
    "calculation",
    "citation",
    "domain_reasoning",       # interpretation/mechanism rooted in established chemistry/physics knowledge
    "filler",                 # no useful / groundable information; discourse or formatting residue
)

# Allowed support_class values for GroundedClaim:
#   direct          — claim value appears verbatim in tool results
#   inferred        — claim derivable from tool results, not verbatim
#   domain_knowledge— claim is general scientific knowledge (textbook chemistry/physics);
#                     not contradicted by tool results, but not directly derivable from them
#   unsupported     — cannot be verified AND not recognised domain knowledge (potential hallucination)
#   no_tool_data    — no tool was called that could verify this type of claim
SUPPORT_CLASSES = (
    "direct",
    "inferred",
    "domain_knowledge",
    "unsupported",
    "no_tool_data",
)


@dataclass(slots=True)
class Claim:
    """A single identified claim / assertion in an answer paragraph."""
    start: int
    end: int
    text: str
    claim_type: str                     # one of CLAIM_TYPES
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GroundedClaim:
    """Result of grounding a Claim against tool results / canonical IDs."""
    claim_index: int                    # index into ClaimParagraph.claims
    canonical_ids: list[str] = field(default_factory=list)   # e.g. ["metal_41", "vlm_175400"]
    support_class: str = "unsupported"  # one of SUPPORT_CLASSES
    evidence_snippet: str = ""
    tool_snippets: list[dict[str, str]] = field(default_factory=list)
    # Each entry: {"step": "Step 5", "tool": "build_system_catalog",
    #              "snippet": "vlm_157439 | logK=8.56 | T=25 | I=0"}


@dataclass(slots=True)
class ClaimParagraph:
    """All claim annotations for a single paragraph."""
    paragraph_index: int
    text: str
    claims: list[Claim] = field(default_factory=list)
    grounded_claims: list[GroundedClaim] = field(default_factory=list)


@dataclass(slots=True)
class ClaimAnnotatedDocument:
    """Fully claim-annotated document (typically just the answer body)."""
    source_file: str
    doc_type: str                       # "answer"
    paragraphs: list[ClaimParagraph] = field(default_factory=list)


# =====================================================================
# Serialization helpers (for eval_cache JSON round-trip)
# =====================================================================

def _span_to_dict(span: TokenSpan) -> dict:
    """Serialize a TokenSpan subclass to a plain dict with a ``_cls`` tag."""
    d = asdict(span)
    d["_cls"] = type(span).__name__
    return d


def _span_from_dict(d: dict) -> TokenSpan:
    """Re-hydrate a TokenSpan subclass from a serialized dict."""
    cls_name = d.pop("_cls", "TokenSpan")
    d.pop("metadata", None)  # rebuild cleanly
    if cls_name == "NumericSpan":
        return NumericSpan(**{k: v for k, v in d.items() if k in NumericSpan.__dataclass_fields__})
    if cls_name == "IdSpan":
        return IdSpan(**{k: v for k, v in d.items() if k in IdSpan.__dataclass_fields__})
    if cls_name == "ChemSpan":
        return ChemSpan(**{k: v for k, v in d.items() if k in ChemSpan.__dataclass_fields__})
    return TokenSpan(**{k: v for k, v in d.items() if k in TokenSpan.__dataclass_fields__})


def _nm_to_dict(nm: NumericMatch) -> dict:
    return asdict(nm)


def _nm_from_dict(d: dict) -> NumericMatch:
    return NumericMatch(**d)


def paragraph_to_dict(pa: ParagraphAnnotation) -> dict:
    return {
        "paragraph_index": pa.paragraph_index,
        "text": pa.text,
        "spans": [_span_to_dict(s) for s in pa.spans],
        "numeric_matches": {
            str(k): [_nm_to_dict(m) for m in v]
            for k, v in pa.numeric_matches.items()
        },
    }


def paragraph_from_dict(d: dict) -> ParagraphAnnotation:
    return ParagraphAnnotation(
        paragraph_index=d["paragraph_index"],
        text=d["text"],
        spans=[_span_from_dict(s) for s in d.get("spans", [])],
        numeric_matches={
            int(k): [_nm_from_dict(m) for m in v]
            for k, v in d.get("numeric_matches", {}).items()
        },
    )


def document_to_dict(doc: EnrichedDocument) -> dict:
    return {
        "source_file": doc.source_file,
        "doc_type": doc.doc_type,
        "paragraphs": [paragraph_to_dict(p) for p in doc.paragraphs],
    }


def document_from_dict(d: dict) -> EnrichedDocument:
    return EnrichedDocument(
        source_file=d["source_file"],
        doc_type=d["doc_type"],
        paragraphs=[paragraph_from_dict(p) for p in d.get("paragraphs", [])],
    )


# =====================================================================
# Claim serialization helpers
# =====================================================================

def _claim_to_dict(c: Claim) -> dict:
    return {
        "start": c.start, "end": c.end, "text": c.text,
        "claim_type": c.claim_type, "metadata": c.metadata,
    }


def _claim_from_dict(d: dict) -> Claim:
    return Claim(
        start=d["start"], end=d["end"], text=d["text"],
        claim_type=d["claim_type"],
        metadata=d.get("metadata", {}),
    )


def _grounded_to_dict(g: GroundedClaim) -> dict:
    return {
        "claim_index": g.claim_index,
        "canonical_ids": g.canonical_ids,
        "support_class": g.support_class,
        "evidence_snippet": g.evidence_snippet,
        "tool_snippets": g.tool_snippets,
    }


def _grounded_from_dict(d: dict) -> GroundedClaim:
    return GroundedClaim(
        claim_index=d["claim_index"],
        canonical_ids=d.get("canonical_ids", []),
        support_class=d.get("support_class", "unsupported"),
        evidence_snippet=d.get("evidence_snippet", ""),
        tool_snippets=d.get("tool_snippets", []),
    )


def claim_paragraph_to_dict(cp: ClaimParagraph) -> dict:
    return {
        "paragraph_index": cp.paragraph_index,
        "text": cp.text,
        "claims": [_claim_to_dict(c) for c in cp.claims],
        "grounded_claims": [_grounded_to_dict(g) for g in cp.grounded_claims],
    }


def claim_paragraph_from_dict(d: dict) -> ClaimParagraph:
    return ClaimParagraph(
        paragraph_index=d["paragraph_index"],
        text=d["text"],
        claims=[_claim_from_dict(c) for c in d.get("claims", [])],
        grounded_claims=[_grounded_from_dict(g) for g in d.get("grounded_claims", [])],
    )


def claim_doc_to_dict(doc: ClaimAnnotatedDocument) -> dict:
    return {
        "source_file": doc.source_file,
        "doc_type": doc.doc_type,
        "paragraphs": [claim_paragraph_to_dict(p) for p in doc.paragraphs],
    }


def claim_doc_from_dict(d: dict) -> ClaimAnnotatedDocument:
    return ClaimAnnotatedDocument(
        source_file=d["source_file"],
        doc_type=d["doc_type"],
        paragraphs=[claim_paragraph_from_dict(p) for p in d.get("paragraphs", [])],
    )
