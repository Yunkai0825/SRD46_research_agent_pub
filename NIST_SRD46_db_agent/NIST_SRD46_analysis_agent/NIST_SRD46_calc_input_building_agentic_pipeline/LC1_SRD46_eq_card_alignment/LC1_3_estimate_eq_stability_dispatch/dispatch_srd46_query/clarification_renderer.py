"""Render narrow chemistry follow-ups without exposing parser machinery."""

from __future__ import annotations

from typing import Iterable


_TOPIC_TEXT = {
    "target_equilibrium_definition": "which target equilibrium definition the estimate applies to",
    "estimated_log10_K": "the numerical log10 K estimate",
    "uncertainty": "a defensible uncertainty in log10 units",
    "estimation_method": "the chemistry-based estimation method",
    "assumptions": "the chemical and reference-state assumptions",
    "rationale": "the chemical rationale for transferring the evidence",
    "supporting_evidence": "the SRD-46 records, networks, or citations used as evidence",
    "plain_chemistry_conclusion": "the chemistry conclusion in ordinary prose",
}
KNOWN_CLARIFICATION_TOPICS = frozenset(_TOPIC_TEXT)


def render_query_clarification(missing_topics: Iterable[str]) -> str:
    topics = sorted({str(value).strip() for value in missing_topics if str(value).strip()})
    if not topics:
        raise ValueError("at least one missing chemistry topic is required")
    unknown = sorted(set(topics) - KNOWN_CLARIFICATION_TOPICS)
    if unknown:
        raise ValueError(f"unknown chemistry clarification topics: {unknown}")
    descriptions = [_TOPIC_TEXT[topic] for topic in topics]
    if len(descriptions) == 1:
        requested = descriptions[0]
    else:
        requested = ", ".join(descriptions[:-1]) + ", and " + descriptions[-1]
    return (
        "Please add only the missing chemistry information for your preceding "
        f"estimate: {requested}. Do not repeat the full preceding answer unless "
        "you need to correct it, and clearly identify any correction."
    )


__all__ = ["KNOWN_CLARIFICATION_TOPICS", "render_query_clarification"]
