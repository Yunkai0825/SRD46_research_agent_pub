"""Shared recognition of an explicit scientific no-estimate conclusion.

The dispatch auditor and the isolated answer parser must agree on this
decision.  Keep the recognizer deliberately narrower than a search-status
statement: ``no exact-pair estimate was found`` does not rule out an analogue
estimate and therefore is not a terminal no-estimate conclusion.
"""

from __future__ import annotations

import re
from enum import Enum

from .answer_context import (
    markdown_heading_ancestry,
    role_is_disqualified,
    span_is_contextual,
)


NO_ESTIMATE_CONCLUSION_RE = re.compile(
    r"(?:"
    # A plain *numerical* no-estimate statement is unambiguous.  For the
    # shorter word ``estimate``, require a scientific qualifier so an
    # intermediate search observation is not mistaken for the conclusion.
    r"\bno\s+(?:numerical\s+estimate|"
    r"(?:(?:admissible|defensible|reliable|supported|reproducible|"
    r"justified|grounded|SRD46[-\s]grounded|scientifically\s+justified)\s+){1,3}"
    r"(?:numerical\s+)?estimate)\b"
    r"|\bno[-\s]estimate\s+(?:conclusion|outcome|result)\b"
    r"|\bno\s+estimate\s+(?:(?:is|was)\s+)?"
    r"(?:defended|proposed|assigned|reported|supported)\b"
    r"|\bcannot\s+(?:defensibly\s+|reliably\s+|reproducibly\s+)?estimate\b"
    r"|\binsufficient\s+evidence\s+(?:for|to\s+support)\s+"
    r"(?:a\s+)?(?:numerical\s+)?estimate\b"
    r"|\bevidence\s+is\s+insufficient\s+(?:for|to\s+support)\s+"
    r"(?:a\s+)?(?:numerical\s+)?estimate\b"
    r")",
    re.IGNORECASE,
)


class EstimateConclusion(str, Enum):
    """Operative conclusion of a query-agent answer."""

    ESTIMATE = "estimate"
    NO_ESTIMATE = "no_estimate"
    CONTRADICTORY = "contradictory"
    ABSENT = "absent"


_BETA_ANCHOR_RE = re.compile(r"\bbeta_def_\d+\b", re.IGNORECASE)
_LABELLED_ESTIMATE_RE = re.compile(
    r"\b(?:constant_value(?:\s*\(\s*log(?:10)?\s*K\s*\))?|"
    r"(?:proposed|estimated)\s+(?:target\s+)?(?:log(?:10)?\s*K|"
    r"stability\s+constant))\s*(?:=|:|of\s+|is\s+)?\s*"
    r"(?:\*\*|`)?[+\-−]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?"
    r"(?:\*\*|`)?",
    re.IGNORECASE,
)
_TARGET_CANDIDATE_START_RE = re.compile(
    r"(?:\bcandidate\s+equilibrium\b|"
    r"\b(?:propos(?:e|ed)|estimated)\s+(?:a\s+)?(?:target\s+)?"
    r"(?:(?:numerical|stability)\s+)?(?:candidate|equilibrium|estimate|"
    r"constant|beta_def_\d+)|\bthe\s+(?:target\s+)?estimate\b|"
    r"<estimated_speciation>)",
    re.IGNORECASE,
)
_DIRECT_PROPOSED_LABEL_RE = re.compile(
    r"\b(?:proposed|estimated)\s+(?:target\s+)?\s*$",
    re.IGNORECASE,
)
_ESTIMATION_CONCLUSION_RE = re.compile(
    r"^[ \t]*estimation\s+conclusion\s*:\s*(?:"
    r"(?P<no>no\s+(?:numerical\s+)?estimate)|"
    r"(?P<yes>(?:a\s+)?(?:numerical\s+)?estimate"
    r"(?:\s+(?:reported|proposed|supported))?))\b[.!]?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_FENCED_BLOCK_RE = re.compile(
    r"(?ms)^[ \t]*(?:`{3,}|~{3,})[^\r\n]*\r?\n.*?"
    r"^[ \t]*(?:`{3,}|~{3,})[ \t]*(?:\r?\n|$)"
)
_WITHDRAWAL_RE = re.compile(
    r"\b(?:withdraw(?:n|ing)?|reject(?:ed|ing)?|discard(?:ed|ing)?|"
    r"do\s+not\s+(?:use|report|adopt)|must\s+not\s+be\s+used|"
    r"(?:candidate|estimate)\s+(?:is|was)\s+(?:invalid|withdrawn|rejected)|"
    r"not\s+adopt(?:ed|ing)?)\b",
    re.IGNORECASE,
)
_NEGATING_PREFIX_RE = re.compile(
    r"\b(?:not|isn't|wasn't|reject(?:ed)?|deny|denied|false|incorrect)\s*$",
    re.IGNORECASE,
)
_NEGATING_SUFFIX_RE = re.compile(
    r"^\s*(?:exists?\s+)?(?:is|was|would\s+be)?\s*"
    r"(?:incorrect|false|inapplicable|rejected|denied|not\s+(?:our\s+)?conclusion)\b",
    re.IGNORECASE,
)


def _is_quoted_or_negated(text: str, start: int, end: int) -> bool:
    """Reject mentions of the phrase rather than scientific conclusions."""

    if span_is_contextual(text, start, end):
        return True
    prefix = text[max(0, start - 24):start]
    if _NEGATING_PREFIX_RE.search(prefix) or role_is_disqualified(prefix):
        return True
    if any(
        role_is_disqualified(title)
        for title in markdown_heading_ancestry(text, start)
    ):
        return True
    suffix = text[end:min(len(text), end + 60)]
    if _NEGATING_SUFFIX_RE.search(suffix):
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line_end_raw = text.find("\n", end)
    line_end = len(text) if line_end_raw < 0 else line_end_raw
    if text[line_start:start].lstrip().startswith(">"):
        return True
    if any(
        match.start() <= start < match.end()
        for match in _FENCED_BLOCK_RE.finditer(text)
    ):
        return True
    for left, right in (('"', '"'), ("‘", "’"), ("“", "”")):
        left_pos = text.rfind(left, 0, start)
        right_pos = text.find(right, end)
        if left_pos >= line_start and 0 <= right_pos <= line_end:
            return True
    # Keep straight-apostrophe matching local so a contraction in an earlier
    # clause cannot suppress a real conclusion.
    left_pos = text.rfind("'", 0, start)
    right_pos = text.find("'", end)
    if (
        left_pos >= 0
        and right_pos >= 0
        and start - left_pos <= 3
        and right_pos - end <= 3
    ):
        return True
    return False


def _candidate_end(text: str) -> int | None:
    """Return the end of the last explicitly proposed target candidate."""

    beta_matches = [
        match for match in _BETA_ANCHOR_RE.finditer(text)
        if not _is_quoted_or_negated(text, match.start(), match.end())
    ]
    if not beta_matches:
        return None
    ends: list[int] = []
    for match in _LABELLED_ESTIMATE_RE.finditer(text):
        if _is_quoted_or_negated(text, match.start(), match.end()):
            continue
        preceding_betas = [
            beta for beta in beta_matches if beta.start() < match.start()
        ]
        if not preceding_betas:
            continue
        direct_prefix = text[max(0, match.start() - 40):match.start()]
        if _DIRECT_PROPOSED_LABEL_RE.search(direct_prefix):
            ends.append(match.end())
            continue
        # Candidate sections can legitimately contain a long derivation
        # between the target proposal and its final labelled value.  Bind to
        # an explicit target-estimate/candidate-equilibrium start anywhere
        # before the associated beta, rather than a brittle character window.
        beta_end = preceding_betas[-1].end()
        positive_starts = [
            signal.start()
            for signal in _TARGET_CANDIDATE_START_RE.finditer(
                text[:beta_end]
            )
        ]
        if positive_starts:
            ends.append(match.end())
    return max(ends) if ends else None


def has_numerical_estimate_conclusion_marker(text: str | None) -> bool:
    """Return whether exactly one operative standalone positive marker exists."""

    body = text or ""
    markers = [
        match
        for match in _ESTIMATION_CONCLUSION_RE.finditer(body)
        if not _is_quoted_or_negated(body, match.start(), match.end())
    ]
    if len(markers) != 1 or markers[0].group("yes") is None:
        return False
    marker = markers[0]
    if (_candidate_end(body) or -1) > marker.end():
        return False
    later_surface = body[marker.end():]
    if _has_unnegated_withdrawal(later_surface):
        return False
    return not any(
        not _is_quoted_or_negated(body, match.start(), match.end())
        for match in NO_ESTIMATE_CONCLUSION_RE.finditer(
            body, marker.end()
        )
    )


def _has_unnegated_withdrawal(text: str) -> bool:
    for match in _WITHDRAWAL_RE.finditer(text):
        prefix = text[max(0, match.start() - 12):match.start()]
        if not re.search(r"\bnot\s*$", prefix, re.IGNORECASE):
            return True
    return False


def classify_estimate_conclusion(text: str | None) -> EstimateConclusion:
    """Classify the final operative estimate conclusion in *text*.

    A search-local statement such as ``no numerical estimate from the exact
    pair`` is not terminal when a later, labelled candidate is proposed.  A
    candidate followed by an unqualified no-estimate conclusion is
    contradictory and must be repaired; it becomes a valid no-estimate only
    when the answer explicitly withdraws or rejects that candidate.
    """

    body = text or ""
    no_estimate_matches = [
        match
        for match in NO_ESTIMATE_CONCLUSION_RE.finditer(body)
        if not _is_quoted_or_negated(body, match.start(), match.end())
    ]
    candidate_end = _candidate_end(body)
    conclusion_markers = [
        match
        for match in _ESTIMATION_CONCLUSION_RE.finditer(body)
        if not _is_quoted_or_negated(body, match.start(), match.end())
    ]

    if conclusion_markers:
        final_marker = conclusion_markers[-1]
        if final_marker.group("yes") is not None:
            later_surface = body[final_marker.end():]
            if _has_unnegated_withdrawal(later_surface):
                return EstimateConclusion.NO_ESTIMATE
            if any(
                match.start() >= final_marker.end()
                for match in no_estimate_matches
            ):
                return EstimateConclusion.CONTRADICTORY
            if (candidate_end or -1) > final_marker.end():
                return EstimateConclusion.CONTRADICTORY
            return EstimateConclusion.ESTIMATE
        if candidate_end is None:
            return EstimateConclusion.NO_ESTIMATE
        if candidate_end > final_marker.end():
            # A later proposal supersedes what was not, in fact, the final
            # operative marker.
            return EstimateConclusion.ESTIMATE
        if _has_unnegated_withdrawal(
            body[candidate_end:final_marker.end()]
        ):
            return EstimateConclusion.NO_ESTIMATE
        return EstimateConclusion.CONTRADICTORY

    if candidate_end is None:
        return (
            EstimateConclusion.NO_ESTIMATE
            if no_estimate_matches
            else EstimateConclusion.ABSENT
        )
    if not no_estimate_matches:
        return EstimateConclusion.ESTIMATE

    later_no_estimate = [
        match for match in no_estimate_matches if match.start() >= candidate_end
    ]
    if not later_no_estimate:
        return EstimateConclusion.ESTIMATE

    last_conclusion = later_no_estimate[-1]
    withdrawal_surface = body[candidate_end:last_conclusion.end()]
    if _has_unnegated_withdrawal(withdrawal_surface):
        return EstimateConclusion.NO_ESTIMATE
    return EstimateConclusion.CONTRADICTORY


def has_no_estimate_conclusion(text: str | None) -> bool:
    """Return whether *text* contains a terminal no-estimate conclusion."""

    return classify_estimate_conclusion(text) is EstimateConclusion.NO_ESTIMATE


__all__ = [
    "EstimateConclusion",
    "NO_ESTIMATE_CONCLUSION_RE",
    "classify_estimate_conclusion",
    "has_numerical_estimate_conclusion_marker",
    "has_no_estimate_conclusion",
]
