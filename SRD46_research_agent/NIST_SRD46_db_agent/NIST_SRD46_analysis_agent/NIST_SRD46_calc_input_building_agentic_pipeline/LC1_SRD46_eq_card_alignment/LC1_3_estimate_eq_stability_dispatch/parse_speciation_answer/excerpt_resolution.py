"""Host-side resolution of parser excerpts that point at an answer line.

The parser's excerpts must be contiguous spans of the QueryAgent answer; the
gates check that literally. Retyping a long Unicode table row for every
excerpt key can hit the reply cap or introduce ASCII respellings of charges
and arrows. This module lets the host do the mechanical copy while the parser
keeps the choice of row:

* **prefix** - for a row-bound excerpt key, the opening characters of exactly
  one table row or reaction line (at least ``EXCERPT_PREFIX_MIN_CHARS``
  characters, verbatim) stand for that whole line;
* **nearest_match** - an excerpt that is not the answer's text but resembles
  exactly one answer line at ``EXCERPT_MATCH_MIN_SIMILARITY`` or better (the
  usual ASCII respelling of one row) stands for that line;
* **ambiguous** - an excerpt that opens or resembles several distinct lines is
  stored as sent and the candidates are reported, so the parser sends more of
  the line it means;
* **literal** / **unresolved** - stored as sent.

The host stores the transcript's own line, so traceability and number binding
are checked on the stored span; what the host did is recorded on the draft
(``host_resolved_excerpts``) and in the create/update receipt, and the parser
is asked to confirm the stored line is the row it meant.
"""

from __future__ import annotations

import difflib
from typing import Any

from .canonical_topology import has_reaction_arrow
from .source_grounding import _canonical_source_text, _source_contains

EXCERPT_PREFIX_MIN_CHARS = 20
EXCERPT_MATCH_MIN_SIMILARITY = 0.9
# Keys whose span is normally one table row or reaction line of the answer;
# only these accept the opening characters of a line.  Prose-bound keys
# (method, rationale, assumptions) keep literal semantics: a partial span
# there is the parser's deliberate choice of sub-span.
ROW_BOUND_EXCERPT_KEYS = frozenset({
    "topology_excerpt",
    "beta_definition_excerpt",
    "constant_value_excerpt",
    "uncertainty_excerpt",
    "evidence_excerpt",
})
_LINE_HEAD = 240
_QUICK_RATIO_FLOOR = 0.3

EXCERPT_RESOLUTION_RULE = (
    "For topology_excerpt, beta_definition_excerpt, constant_value_excerpt, "
    "uncertainty_excerpt and evidence_excerpt you may send only the opening "
    f"characters of the table row or reaction line you mean (at least "
    f"{EXCERPT_PREFIX_MIN_CHARS}, copied verbatim): when they open exactly one "
    "answer line, the host stores that whole line. For any excerpt key, text "
    "that is not the answer's own but closely resembles exactly one answer "
    f"line (similarity >= {EXCERPT_MATCH_MIN_SIMILARITY}) is replaced by that "
    "line. The receipt lists every such replacement under "
    "host_resolved_excerpts with the stored line: confirm it is the row you "
    "meant, and if not, patch that key with the opening characters of the "
    "right line. An excerpt that opens or resembles several answer lines is "
    "stored as sent and the receipt lists the candidates under "
    "unresolved_excerpts. Gates still check the stored span literally."
)


def transcript_lines(transcript: str) -> list[str]:
    """Distinct non-empty lines of the answer transcript, in order."""

    seen: set[str] = set()
    lines: list[str] = []
    for raw in str(transcript or "").splitlines():
        line = raw.strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def _is_row_line(line: str) -> bool:
    return line.lstrip().startswith("|") or has_reaction_arrow(line)


def _head(text: str) -> str:
    return text if len(text) <= _LINE_HEAD else text[:_LINE_HEAD] + "…"


def resolve_excerpt(key: str, sent: Any, transcript: str) -> dict[str, Any]:
    """Resolve one excerpt against the transcript.

    Returns ``{"how", "stored", "sent", "similarity", "candidates"}`` where
    ``how`` is ``literal``, ``prefix``, ``nearest_match``, ``ambiguous`` or
    ``unresolved``; ``stored`` is the text to keep on the draft (the
    transcript's own line for ``prefix`` and ``nearest_match``, the sent text
    otherwise).
    """

    text = str(sent or "").strip()
    result: dict[str, Any] = {
        "how": "unresolved", "stored": text, "sent": _head(text),
        "similarity": None, "candidates": [],
    }
    if not text:
        return result
    target = _canonical_source_text(text)
    lines = transcript_lines(transcript)

    # 1. Opening characters of one row (row-bound keys only).
    if key in ROW_BOUND_EXCERPT_KEYS and len(target) >= EXCERPT_PREFIX_MIN_CHARS:
        opened = [
            line for line in lines
            if _is_row_line(line)
            and (canonical := _canonical_source_text(line)) != target
            and canonical.startswith(target)
        ]
        distinct = list(dict.fromkeys(_canonical_source_text(line) for line in opened))
        if len(distinct) == 1:
            result.update(how="prefix", stored=opened[0])
            return result
        if len(distinct) > 1:
            result.update(
                how="ambiguous",
                candidates=[{"row": _head(line)} for line in opened[:4]],
            )
            return result

    # 2. The answer's own text (after the rendering normalization the gates use).
    if _source_contains(transcript, text):
        result["how"] = "literal"
        return result

    # 3. One close match among the answer lines.
    scored: list[tuple[float, str]] = []
    for line in lines:
        matcher = difflib.SequenceMatcher(None, _canonical_source_text(line), target)
        if matcher.quick_ratio() < _QUICK_RATIO_FLOOR:
            continue
        scored.append((matcher.ratio(), line))
    scored.sort(key=lambda item: -item[0])
    close = [
        (score, line) for score, line in scored
        if score >= EXCERPT_MATCH_MIN_SIMILARITY
    ]
    if len(close) == 1:
        score, line = close[0]
        result.update(how="nearest_match", stored=line, similarity=round(score, 2))
        return result
    if len(close) > 1:
        result.update(
            how="ambiguous",
            candidates=[
                {"row": _head(line), "similarity": round(score, 2)}
                for score, line in close[:4]
            ],
        )
    return result


def resolve_source_excerpts(
    excerpts: dict[str, Any], transcript: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Resolve a ``source_excerpts`` patch.

    Returns ``(patched_excerpts, resolved, unresolved)``: the patch with
    resolved spans substituted, the notes for the keys the host replaced
    (``{key: {how, similarity, stored_line, sent}}``) and the notes for the
    ambiguous ones (``{key: {sent, candidates}}``).  Values that are not
    strings (or, for ``assumption_excerpts``, not a list of strings) are left
    untouched so the draft's own type errors still fire.
    """

    patched = dict(excerpts)
    resolved: dict[str, Any] = {}
    unresolved: dict[str, Any] = {}

    def note(label: str, outcome: dict[str, Any]) -> None:
        if outcome["how"] in {"prefix", "nearest_match"}:
            resolved[label] = {
                "how": outcome["how"],
                "similarity": outcome["similarity"],
                "stored_line": _head(outcome["stored"]),
                "sent": outcome["sent"],
            }
        elif outcome["how"] == "ambiguous":
            unresolved[label] = {
                "sent": outcome["sent"],
                "candidates": outcome["candidates"],
            }

    for key, value in excerpts.items():
        if value is None:
            continue
        if key == "assumption_excerpts":
            if not isinstance(value, list) or any(
                not isinstance(item, str) for item in value
            ):
                continue
            items: list[str] = []
            for index, item in enumerate(value):
                outcome = resolve_excerpt(key, item, transcript)
                note(f"{key}[{index}]", outcome)
                items.append(
                    outcome["stored"] if outcome["how"] in {"prefix", "nearest_match"}
                    else item
                )
            patched[key] = items
            continue
        if not isinstance(value, str):
            continue
        outcome = resolve_excerpt(key, value, transcript)
        note(key, outcome)
        if outcome["how"] in {"prefix", "nearest_match"}:
            patched[key] = outcome["stored"]
    return patched, resolved, unresolved


__all__ = [
    "EXCERPT_MATCH_MIN_SIMILARITY",
    "EXCERPT_PREFIX_MIN_CHARS",
    "EXCERPT_RESOLUTION_RULE",
    "ROW_BOUND_EXCERPT_KEYS",
    "resolve_excerpt",
    "resolve_source_excerpts",
    "transcript_lines",
]
