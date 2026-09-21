"""Bind parser-written draft fields to exact QueryAgent answer text."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any, Iterable

from .candidate_schema import EquilibriumDraft
from .canonical_topology import (
    TopologyResolutionError,
    validate_topology_resolution_receipt,
)


_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)

_SOURCE_BINDING_PROFILE = "contiguous_nfkc_whitespace_markdown_emphasis_v1"
_TYPOGRAPHIC_HYPHENS = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2212": "-",  # mathematical minus sign
})
_PAIRED_MARKDOWN_FORMATTING = (
    re.compile(r"(?s)(?<!\w)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\w)"),
    re.compile(r"(?s)(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)"),
    re.compile(r"(?s)(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])"),
    re.compile(r"(?s)(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])"),
    re.compile(r"`([^`\r\n]+)`"),
)


class SourceGroundingError(ValueError):
    pass


def is_admissible_query_agent_prose(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if re.search(r"<\/?estimated_speciation\b", text, flags=re.I):
        return False
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return True
    return not isinstance(decoded, (dict, list))


def compose_answer_transcript(answers: Iterable[str]) -> str:
    """Join assistant answers only; prompts and tool payloads never enter."""

    return "\n\n".join(str(answer).strip() for answer in answers if str(answer).strip())


def _canonical_source_text(value: Any) -> str:
    """Normalize rendering-only differences without rewriting source prose."""

    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.translate(_TYPOGRAPHIC_HYPHENS)
    for pattern in _PAIRED_MARKDOWN_FORMATTING:
        # Repeat because a span may be nested, e.g. ***important***.
        while True:
            normalized = pattern.sub(r"\1", text)
            if normalized == text:
                break
            text = normalized
    return " ".join(text.split())


def _source_excerpt(transcript: str, value: Any, label: str) -> str:
    excerpt = str(value or "").strip()
    if not excerpt:
        raise SourceGroundingError(f"{label} source excerpt is missing")
    if excerpt not in transcript:
        canonical_excerpt = _canonical_source_text(excerpt)
        canonical_transcript = _canonical_source_text(transcript)
        if not canonical_excerpt or canonical_excerpt not in canonical_transcript:
            raise SourceGroundingError(
                f"{label} source excerpt is not traceable to one contiguous "
                "answer span after allowed formatting normalization"
            )
    return excerpt


def _source_contains(container: str, value: Any) -> bool:
    needle = _canonical_source_text(value)
    return bool(needle) and needle in _canonical_source_text(container)


def _bind_number(excerpt: str, expected: float, label: str) -> None:
    observed = [
        float(match.group(0))
        for match in _NUMBER_RE.finditer(_canonical_source_text(excerpt))
    ]
    if not any(math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-12) for value in observed):
        raise SourceGroundingError(
            f"{label}={expected!r} does not occur in its source excerpt"
        )


def validate_draft_source_bindings(
    *, transcript: str, draft: EquilibriumDraft
) -> list[dict[str, Any]]:
    """Return auditable field receipts or fail if the parser invented content."""

    excerpts = draft.source_excerpts
    topology_excerpt: str | None = None
    topology_receipt: dict[str, Any] | None = None
    beta_excerpt: str | None = None
    if draft.topology_resolution is not None:
        topology_excerpt = _source_excerpt(
            transcript, excerpts.get("topology_excerpt"), "reaction topology"
        )
        try:
            topology_receipt = validate_topology_resolution_receipt(
                draft.topology_resolution,
                beta_definition_id=int(draft.beta_definition_id or 0),
                beta_definition_name=str(
                    draft.topology_resolution.get("beta_definition_name") or ""
                ),
                equation_python=str(
                    draft.topology_resolution.get("equation_python") or ""
                ),
                query_id=str(
                    draft.topology_resolution.get("authorization_context_id") or ""
                ),
                answer_sha256=str(
                    draft.topology_resolution.get("answer_sha256") or ""
                ),
            )
        except TopologyResolutionError as exc:
            raise SourceGroundingError(str(exc)) from exc
    else:
        beta_excerpt = _source_excerpt(
            transcript, excerpts.get("beta_definition_excerpt"), "beta_definition_id"
        )
        if draft.beta_definition_id is None or not re.search(
            rf"(?i)\bbeta_def_{int(draft.beta_definition_id)}\b",
            _canonical_source_text(beta_excerpt),
        ):
            raise SourceGroundingError(
                "beta_definition_id does not occur in its source excerpt"
            )
    constant_excerpt = _source_excerpt(
        transcript, excerpts.get("constant_value_excerpt"), "constant_value"
    )
    uncertainty_excerpt = _source_excerpt(
        transcript, excerpts.get("uncertainty_excerpt"), "uncertainty_log10"
    )
    assert draft.constant_value is not None
    assert draft.uncertainty_log10 is not None
    beta_pattern = re.compile(
        rf"(?i)\bbeta_def_{int(draft.beta_definition_id)}\b"
    )
    if topology_excerpt is not None:
        if not _source_contains(constant_excerpt, topology_excerpt):
            raise SourceGroundingError(
                "constant_value excerpt does not contain its resolved reaction topology"
            )
        if not _source_contains(uncertainty_excerpt, topology_excerpt):
            raise SourceGroundingError(
                "uncertainty excerpt does not contain its resolved reaction topology"
            )
    elif not beta_pattern.search(_canonical_source_text(constant_excerpt)):
        raise SourceGroundingError(
            "constant_value excerpt does not identify its beta_definition_id"
        )
    transcript_beta_ids = {
        int(match.group(1))
        for match in re.finditer(
            r"(?i)\bbeta_def_(\d+)\b",
            _canonical_source_text(transcript),
        )
    }
    if topology_excerpt is None and len(transcript_beta_ids) > 1 and not beta_pattern.search(
        _canonical_source_text(uncertainty_excerpt)
    ):
        raise SourceGroundingError(
            "uncertainty excerpt does not identify its beta_definition_id in "
            "a multi-beta answer"
        )
    _bind_number(constant_excerpt, float(draft.constant_value), "constant_value")
    _bind_number(
        uncertainty_excerpt, float(draft.uncertainty_log10), "uncertainty_log10"
    )

    evidence_excerpt = _source_excerpt(
        transcript, excerpts.get("evidence_excerpt"), "evidence"
    )
    canonical_evidence_excerpt = _canonical_source_text(evidence_excerpt)
    for prefix, values in (
        ("vlm", draft.evidence_vlm_ids),
        ("ref_eq_net", draft.evidence_network_ids),
        ("lit", draft.evidence_citation_ids),
    ):
        for identifier in values:
            if not re.search(
                rf"(?i)\b{re.escape(prefix)}_{int(identifier)}\b",
                canonical_evidence_excerpt,
            ):
                raise SourceGroundingError(
                    f"{prefix}_{identifier} is absent from the evidence "
                    f"excerpt: every cited ID must appear fully prefixed "
                    f"(the literal token {prefix}_{identifier}). Prose "
                    f"lists that write the prefix once and elide it for "
                    f"later IDs bind only the first ID. Either choose an "
                    f"evidence excerpt span in which each cited ID occurs "
                    f"fully prefixed, or cite only the IDs whose fully "
                    f"prefixed tokens occur in the excerpt."
                )

    method_excerpt = _source_excerpt(
        transcript, excerpts.get("estimation_method_excerpt"), "estimation_method"
    )
    if not _source_contains(method_excerpt, draft.estimation_method):
        raise SourceGroundingError(
            "estimation_method is not copied from its source excerpt"
        )
    rationale_excerpt = _source_excerpt(
        transcript, excerpts.get("rationale_excerpt"), "rationale"
    )
    if not _source_contains(rationale_excerpt, draft.rationale):
        raise SourceGroundingError("rationale is not copied from its source excerpt")

    raw_assumption_excerpts = excerpts.get("assumption_excerpts")
    if not isinstance(raw_assumption_excerpts, list):
        raise SourceGroundingError("assumption_excerpts must be a list")
    assumption_excerpts = [
        _source_excerpt(transcript, value, "assumption")
        for value in raw_assumption_excerpts
    ]
    if len(assumption_excerpts) != len(draft.assumptions):
        raise SourceGroundingError(
            "assumption excerpts do not correspond one-to-one with assumptions"
        )
    for assumption, excerpt in zip(draft.assumptions, assumption_excerpts):
        if not _source_contains(excerpt, assumption):
            raise SourceGroundingError(
                "an assumption is not copied from its source excerpt"
            )
    return [{
        "draft_id": draft.draft_id,
        "source_binding_profile": _SOURCE_BINDING_PROFILE,
        "topology_excerpt": topology_excerpt,
        "topology_resolution_receipt": topology_receipt,
        "beta_definition_excerpt": beta_excerpt,
        "constant_value_excerpt": constant_excerpt,
        "uncertainty_excerpt": uncertainty_excerpt,
        "evidence_excerpt": evidence_excerpt,
        "estimation_method_excerpt": method_excerpt,
        "assumption_excerpts": assumption_excerpts,
        "rationale_excerpt": rationale_excerpt,
    }]


__all__ = [
    "SourceGroundingError",
    "compose_answer_transcript",
    "is_admissible_query_agent_prose",
    "validate_draft_source_bindings",
]
