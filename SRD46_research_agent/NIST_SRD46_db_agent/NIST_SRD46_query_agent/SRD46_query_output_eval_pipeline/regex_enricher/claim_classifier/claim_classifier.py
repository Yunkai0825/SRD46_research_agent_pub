"""Argo LLM-based claim identification and classification.

Pass 1 of the claim pipeline: reads an answer paragraph and identifies
every distinct factual claim plus any explicit filler spans, classifying
each by type.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..regex_support_helpers.models import CLAIM_TYPES, Claim

log = logging.getLogger("claim_classifier")

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a scientific text analysis assistant.  Given a SECTION from an
answer about thermodynamic stability constants (NIST SRD-46 data),
identify every distinct factual claim plus any explicit filler spans, 
classifying each by type.

Goal:
- Extract every checkable factual span as one claim.
- Mark leftover non-factual text as filler.
- Avoid silently missing a factual span.

Context:
- Unless the text says otherwise, phrases such as "reported", "measured",
    "available", "in the database", and bare "SRD-46" refer to SRD-46 records.
- A bare mention of "SRD-46" is a citation claim only when the sentence is
    about source or provenance.

Split prose into the smallest independently checkable spans.
Split at appositives, parentheticals, relative clauses, and conjunctions that
add a separate fact. Do not keep one large sentence when smaller grounded
spans exist.

Claim types:
- counting: quantity of records, entries, measurements, or entities.
- comparison: compares values or entities.
- trend: directional or monotonic pattern across values, species, or conditions.
- listing: enumerates names, IDs, species, or conditions.
- range: numeric interval or span.
- exact_value: one specific numeric value such as log K, pKa, T, I, year, page.
- property_attribution: assigns a property or characteristic to an entity.
- existence_absence: says data or entities are present or absent.
- calculation: computed or derived value.
- citation: author, paper, journal, literature ID, or provenance/source statement.
- domain_reasoning: chemistry or physics interpretation/mechanism that is
    background knowledge rather than a retrieved database row.
- filler: titles, transitions, scaffolding, or leftover wording with no
    standalone factual content.

Examples:
- "H. A. Pohl" -> citation
- "published in the Journal of Chemical and Engineering Data" -> citation
- "in 1962" -> citation
- "two measurements available" -> counting
- "referenced in 16 equilibrium measurements" -> counting
- "stability increases with ligand denticity" -> trend
- "no stability constants are available for crown ethers" -> existence_absence
- "EDTA is a hexadentate chelator" -> property_attribution
- "log β₂ = log K₁ + log K₂ = 8.19 + 6.91 = 15.10" -> calculation
- "the positive ΔS reflects release of coordinated water molecules" -> domain_reasoning

Tables:
- Treat each markdown DATA ROW as one claim snippet using the full pipe-delimited row text.
- Row with a numeric value -> exact_value.
- Row listing species, conditions, or entities -> listing.
- Header and separator rows -> skip.
- Keep nearby prose claims too; do not drop intro prose just because a table follows.
- Keep prose counts, availability statements, definitions, whole-table conditions,
    and provenance/source statements.

Return ONLY a JSON array:
    {"text": "<exact verbatim substring from the section>",
     "claim_type": "<one of the types above>"}

Rules:
- `text` must be an exact substring of the section.
- One claim per assertion or per data row.
- Prefer smaller clause-sized spans when they can be grounded independently.
- Use filler to cover leftover non-informational text.
- If the section has only non-factual text, return filler entries, not [].
- Return [] only for empty or whitespace-only input.
- Do not use markdown fences or explanation text.

Coverage check:
Re-read the section before returning. Every factual sentence, clause, and data
row should appear at least once. When uncertain, include the span rather than
omit it.
"""

_CLASSIFIER_REACT_SYSTEM_PROMPT_TEMPLATE = """\
You revise one paragraph's claim list after the initial SRD-46 classifier pass.

Inputs:
- UNCLASSIFIED SNIPPETS: optional list of uncovered ``(j{{...}}j)`` spans.
- SECTION: the original paragraph with inline markers.
    - ``[iX{{...}}iX]`` = existing claim ``i`` with type code ``X``.
    - ``(j{{...}}j)`` = uncovered substantive span ``j`` that is not yet a claim.

Type codes:
- ``[iC[`` counting
- ``[iCM[`` comparison
- ``[iT[`` trend
- ``[iL[`` listing
- ``[iR[`` range
- ``[iV[`` exact_value
- ``[iP[`` property_attribution
- ``[iEA[`` existence_absence
- ``[iK[`` calculation
- ``[iCI[`` citation
- ``[iD[`` domain_reasoning
- ``[iF[`` filler

Output either DONE with a short reason, or a tool call:
<tool_call>{{"name": "tool_name", "arguments": {{...}}}}</tool_call>
or
<tool_call>[{{"name": "tool_name", "arguments": {{...}}}}, {{"name": "tool_name", "arguments": {{...}}}}]</tool_call>

Emit multiple tool calls together only when they are independent: different
claim indices and non-overlapping target spans.

TOOLS:
{tool_catalog}

Rules:
- The paragraph text is the source of truth.
- Every claim text must be an exact substring of the paragraph.
- ``add_claim_entry`` for missed factual or filler spans, usually ``(j{{...}}j)`` gaps.
- ``edit_claim_entry`` to split, shrink, expand, or re-type an existing claim.
- ``delete_claim_entry`` to remove wrong or redundant claims.
- Prefer minimal edits. Never emit a full replacement JSON array.
- Use ``inspect_claim_entries`` if you need a refreshed indexed view.
"""

_MAX_TOKENS = 8000
_MAX_RETRIES = 2
_DEFAULT_MAX_REVIEW_ROUNDS = 0
_MAX_REVIEW_ROUNDS = 3
CLAIM_CLASSIFIER_STRATEGY_VERSION = "react-v7-schema-salvage-markdown-anchor"

_CLAIM_TYPE_CODES: dict[str, str] = {
    "counting": "C",
    "comparison": "CM",
    "trend": "T",
    "listing": "L",
    "range": "R",
    "exact_value": "V",
    "property_attribution": "P",
    "existence_absence": "EA",
    "calculation": "K",
    "citation": "CI",
    "domain_reasoning": "D",
    "filler": "F",
}


# ---------------------------------------------------------------------------
# Model candidates (same fallback pattern as argo_enricher)
# ---------------------------------------------------------------------------

def _model_candidates(model: str | None) -> list[str | None]:
    if not model:
        return [None]
    m = model.strip()
    out: list[str | None] = [m]
    alias_map = {
        "gpt41": ["gpt4.1", "gpt-4.1"],
        "gpt4.1": ["gpt41", "gpt-4.1"],
        "gpt-4.1": ["gpt41", "gpt4.1"],
    }
    for alias in alias_map.get(m.lower(), []):
        if alias not in out:
            out.append(alias)

    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import CLAIM_CLASSIFIER_MODEL_FALLBACKS  # type: ignore

        for fallback in CLAIM_CLASSIFIER_MODEL_FALLBACKS:
            candidate = str(fallback).strip()
            if candidate and candidate not in out:
                out.append(candidate)
    except (ImportError, AttributeError, TypeError):
        pass
    return out


# ---------------------------------------------------------------------------
# JSON parsing (reuse patterns from argo_enricher)
# ---------------------------------------------------------------------------

def _try_load_json_array(text: str) -> list[dict] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return None


def _extract_first_balanced_array(text: str) -> str | None:
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaping = False
    for idx, ch in enumerate(text[start:], start=start):
        if in_string:
            if escaping:
                escaping = False
            elif ch == "\\":
                escaping = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def _recover_items(text: str) -> list[dict]:
    items: list[dict] = []
    for m in re.finditer(r"\{[^{}]*\}", text, flags=re.DOTALL):
        block = m.group(0)
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            obj = _recover_malformed_claim_object(block)
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _recover_malformed_claim_object(block: str) -> dict[str, Any] | None:
    text_match = re.search(
        r'"text"\s*:\s*("(?:\\.|[^"\\])*")',
        block,
        flags=re.DOTALL,
    )
    if not text_match:
        return None

    try:
        text_value = json.loads(text_match.group(1))
    except json.JSONDecodeError:
        return None

    claim_type = ""

    claim_type_match = re.search(
        r'"claim_type"\s*:\s*"([a-z_]+)"',
        block,
        flags=re.IGNORECASE,
    )
    if claim_type_match:
        claim_type = claim_type_match.group(1).strip().lower()

    if claim_type not in CLAIM_TYPES:
        alias_match = re.search(
            r',\s*"([a-z_]+)"\s*:\s*"([a-z_]+|true|false)"\s*\}\s*$',
            block,
            flags=re.IGNORECASE,
        )
        if alias_match:
            key_type = alias_match.group(1).strip().lower()
            value_type = alias_match.group(2).strip().lower()
            if key_type in CLAIM_TYPES:
                claim_type = key_type
            elif value_type in CLAIM_TYPES:
                claim_type = value_type

    if claim_type not in CLAIM_TYPES:
        shorthand_match = re.search(
            r',\s*"([a-z_]+)"\s*\}\s*$',
            block,
            flags=re.IGNORECASE,
        )
        if shorthand_match:
            shorthand_type = shorthand_match.group(1).strip().lower()
            if shorthand_type in CLAIM_TYPES:
                claim_type = shorthand_type

    if claim_type not in CLAIM_TYPES:
        return None

    return {
        "text": text_value,
        "claim_type": claim_type,
    }


def _normalize_claim_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    claim_type = str(normalized.get("claim_type", "")).strip().lower()
    if claim_type in CLAIM_TYPES:
        normalized["claim_type"] = claim_type
        return normalized

    for alias_field in ("type", "category", "label", "kind"):
        alias_value = str(normalized.get(alias_field, "")).strip().lower()
        if alias_value in CLAIM_TYPES:
            normalized["claim_type"] = alias_value
            return normalized

    explicit_type_keys: list[str] = []
    for key in normalized:
        key_norm = str(key).strip().lower()
        if key_norm in CLAIM_TYPES and key_norm not in explicit_type_keys:
            explicit_type_keys.append(key_norm)
    if len(explicit_type_keys) == 1:
        normalized["claim_type"] = explicit_type_keys[0]
        return normalized

    for key, value in normalized.items():
        key_norm = str(key).strip().lower()
        if key_norm == "text":
            continue
        value_norm = str(value).strip().lower()
        if key_norm in CLAIM_TYPES and (not value_norm or value_norm == key_norm or value is True):
            normalized["claim_type"] = key_norm
            return normalized
        if value_norm in CLAIM_TYPES:
            normalized["claim_type"] = value_norm
            return normalized

    return normalized


def _normalize_claim_items(items: list[dict]) -> list[dict]:
    normalized_items: list[dict] = []
    salvaged = 0
    for item in items:
        before = str(item.get("claim_type", "")).strip().lower()
        normalized = _normalize_claim_item(item)
        after = str(normalized.get("claim_type", "")).strip().lower()
        if before not in CLAIM_TYPES and after in CLAIM_TYPES:
            salvaged += 1
        normalized_items.append(normalized)
    if salvaged:
        log.warning("Salvaged claim_type for %d classifier item(s)", salvaged)
    return normalized_items


def _collapse_whitespace_text(text: str) -> str:
    return " ".join(text.split())


def _collapse_whitespace_with_mapping(
    text: str,
    mapping: list[int],
) -> tuple[str, list[int]]:
    collapsed_chars: list[str] = []
    collapsed_mapping: list[int] = []
    pending_space = False
    pending_space_index: int | None = None

    for idx, ch in enumerate(text):
        original_index = mapping[idx]
        if ch.isspace():
            if collapsed_chars and not pending_space:
                pending_space = True
                pending_space_index = original_index
            continue

        if pending_space:
            collapsed_chars.append(" ")
            collapsed_mapping.append(
                pending_space_index if pending_space_index is not None else original_index
            )
            pending_space = False
            pending_space_index = None

        collapsed_chars.append(ch)
        collapsed_mapping.append(original_index)

    return "".join(collapsed_chars), collapsed_mapping


def _strip_markdown_for_anchor(text: str) -> tuple[str, list[int]]:
    stripped_chars: list[str] = []
    mapping: list[int] = []
    idx = 0
    line_start = True

    while idx < len(text):
        if line_start:
            start = idx
            while start < len(text) and text[start] in " \t":
                start += 1
            hash_end = start
            while hash_end < len(text) and text[hash_end] == "#":
                hash_end += 1
            space_end = hash_end
            while space_end < len(text) and text[space_end] in " \t":
                space_end += 1
            if hash_end > start and space_end > hash_end:
                idx = space_end
                line_start = False
                continue

        ch = text[idx]
        if ch in "*`~":
            idx += 1
            continue

        stripped_chars.append(ch)
        mapping.append(idx)
        line_start = ch == "\n"
        idx += 1

    return "".join(stripped_chars), mapping


def _expand_markdown_anchor_range(paragraph: str, start: int, end: int) -> tuple[int, int]:
    line_start = paragraph.rfind("\n", 0, start) + 1
    prefix = paragraph[line_start:start]
    if re.fullmatch(r"[ \t]{0,3}#{1,6}[ \t]+", prefix):
        start = line_start

    while start > 0 and paragraph[start - 1] in "*`~":
        start -= 1
    while end < len(paragraph) and paragraph[end] in "*`~":
        end += 1

    return start, end


def _find_span_with_mapping(
    haystack: str,
    haystack_mapping: list[int],
    needle: str,
    paragraph: str,
) -> tuple[int, int] | None:
    if not needle:
        return None

    for candidate_haystack, candidate_needle in (
        (haystack, needle),
        (haystack.lower(), needle.lower()),
    ):
        pos = candidate_haystack.find(candidate_needle)
        if pos != -1:
            start = haystack_mapping[pos]
            end = haystack_mapping[pos + len(needle) - 1] + 1
            return _expand_markdown_anchor_range(paragraph, start, end)

    collapsed_haystack, collapsed_mapping = _collapse_whitespace_with_mapping(
        haystack,
        haystack_mapping,
    )
    collapsed_needle = _collapse_whitespace_text(needle)
    if not collapsed_needle:
        return None

    for candidate_haystack, candidate_needle in (
        (collapsed_haystack, collapsed_needle),
        (collapsed_haystack.lower(), collapsed_needle.lower()),
    ):
        pos = candidate_haystack.find(candidate_needle)
        if pos != -1:
            start = collapsed_mapping[pos]
            end = collapsed_mapping[pos + len(collapsed_needle) - 1] + 1
            return _expand_markdown_anchor_range(paragraph, start, end)

    return None


def _find_claim_span(paragraph: str, text: str) -> tuple[int, int] | None:
    if not text:
        return None

    pos = paragraph.find(text)
    if pos != -1:
        return pos, pos + len(text)

    pos = paragraph.lower().find(text.lower())
    if pos != -1:
        return pos, pos + len(text)

    identity_mapping = list(range(len(paragraph)))
    whitespace_span = _find_span_with_mapping(paragraph, identity_mapping, text, paragraph)
    if whitespace_span is not None:
        return whitespace_span

    stripped_paragraph, stripped_mapping = _strip_markdown_for_anchor(paragraph)
    stripped_text, _ = _strip_markdown_for_anchor(text)
    if stripped_text:
        markdown_span = _find_span_with_mapping(
            stripped_paragraph,
            stripped_mapping,
            stripped_text,
            paragraph,
        )
        if markdown_span is not None:
            return markdown_span

    return None


def _parse_response(raw: str) -> tuple[list[dict], bool]:
    """Multi-strategy JSON array extraction with parse-success status."""
    cleaned = raw.strip()
    candidates: list[str] = [cleaned]

    # Fenced JSON blocks
    for block in re.findall(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.I | re.DOTALL):
        if block.strip():
            candidates.append(block.strip())

    # Balanced array extraction
    for c in list(candidates):
        arr = _extract_first_balanced_array(c)
        if arr and arr != c:
            candidates.append(arr)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        items = _try_load_json_array(candidate)
        if items is not None:
            return _normalize_claim_items(items), True

    recovered = _recover_items(cleaned)
    if recovered:
        log.warning("Recovered %d claim objects from malformed JSON", len(recovered))
        return _normalize_claim_items(recovered), True

    log.warning("Claim classifier returned non-JSON: %.200s", raw)
    return [], False


# ---------------------------------------------------------------------------
# Anchoring: find exact offsets in paragraph
# ---------------------------------------------------------------------------

def _anchor_claims(items: list[dict], paragraph: str) -> list[Claim]:
    """Convert parsed JSON items to Claim objects with verified text offsets."""
    claims: list[Claim] = []
    used_ranges: list[tuple[int, int]] = []

    for item in items:
        text = str(item.get("text", "")).strip()
        claim_type = str(item.get("claim_type", "")).strip().lower()
        if not text or claim_type not in CLAIM_TYPES:
            continue

        span = _find_claim_span(paragraph, text)
        if span is None:
            log.debug("Claim text not found in paragraph: %.60s", text)
            continue

        start, end = span

        # Avoid overlapping claims — keep the first one
        overlap = any(not (end <= us or start >= ue) for us, ue in used_ranges)
        if overlap:
            continue
        used_ranges.append((start, end))

        claims.append(Claim(
            start=start,
            end=end,
            text=paragraph[start:end],  # use actual paragraph slice
            claim_type=claim_type,
        ))

    return sorted(claims, key=lambda c: c.start)


def resolve_claim_classifier_review_rounds(value: int | None = None) -> int:
    """Resolve and clamp the configured number of classifier review rounds."""
    if value is None:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import CLAIM_CLASSIFIER_REVIEW_ROUNDS

            value = CLAIM_CLASSIFIER_REVIEW_ROUNDS
        except (ImportError, AttributeError):
            value = _DEFAULT_MAX_REVIEW_ROUNDS

    try:
        rounds = int(value)
    except (TypeError, ValueError):
        rounds = _DEFAULT_MAX_REVIEW_ROUNDS

    return max(0, min(rounds, _MAX_REVIEW_ROUNDS))


def _call_classifier_items(
    *,
    prompt: str,
    system_prompt: str,
    call_argo_fn,
    models_to_try: list[str | None],
) -> list[dict] | None:
    for attempt in range(_MAX_RETRIES + 1):
        current_prompt = prompt
        if attempt > 0:
            current_prompt = (
                "Your previous response was not valid JSON. "
                "Please try again. Return ONLY a JSON array.\n\n"
                f"{prompt}"
            )

        raw: str | None = None
        last_err: Exception | None = None
        for candidate in models_to_try:
            try:
                raw = call_argo_fn(
                    prompt=current_prompt,
                    system=system_prompt,
                    stop=[],
                    model=candidate,
                    max_tokens=_MAX_TOKENS,
                )
                break
            except Exception as exc:
                last_err = exc
                log.warning("Argo classify failed model=%s: %s", candidate, exc)

        if raw is None:
            raise RuntimeError(
                f"Argo claim classify failed for all models {models_to_try}: {last_err}"
            ) from last_err

        items, parsed = _parse_response(raw)
        if parsed:
            return items

    raise RuntimeError(
        f"Argo claim classify produced unparseable JSON after {_MAX_RETRIES + 1} attempts"
    )


def _call_classifier_react_response(
    *,
    prompt: str,
    system_prompt: str,
    call_argo_fn,
    models_to_try: list[str | None],
) -> str | None:
    raw: str | None = None
    last_err: Exception | None = None
    for candidate in models_to_try:
        try:
            raw = call_argo_fn(
                prompt=prompt,
                system=system_prompt,
                stop=["</tool_call>"],
                model=candidate,
                max_tokens=_MAX_TOKENS,
            )
            break
        except Exception as exc:
            last_err = exc
            log.warning("Argo classifier review failed model=%s: %s", candidate, exc)

    if raw is None:
        raise RuntimeError(
            f"Argo classifier review failed for all models {models_to_try}: {last_err}"
        ) from last_err
    return raw


def _annotate_claims(
    claims: list[Claim],
    *,
    round_index: int,
    stage: str,
) -> list[Claim]:
    annotated: list[Claim] = []
    for claim in claims:
        metadata = dict(claim.metadata)
        metadata.update({
            "classifier_strategy_version": CLAIM_CLASSIFIER_STRATEGY_VERSION,
            "classifier_round": round_index,
            "classifier_stage": stage,
        })
        annotated.append(Claim(
            start=claim.start,
            end=claim.end,
            text=claim.text,
            claim_type=claim.claim_type,
            metadata=metadata,
        ))
    return annotated


def _claim_signatures(claims: list[Claim]) -> tuple[tuple[int, int, str, str], ...]:
    return tuple((claim.start, claim.end, claim.text, claim.claim_type) for claim in claims)


def _claim_coverage(claims: list[Claim], *, include_filler: bool) -> int:
    covered: set[int] = set()
    for claim in claims:
        if not include_filler and claim.claim_type == "filler":
            continue
        for idx in range(claim.start, claim.end):
            covered.add(idx)
    return len(covered)


def _should_accept_review(current: list[Claim], candidate: list[Claim]) -> bool:
    if _claim_signatures(candidate) == _claim_signatures(current):
        return False
    if len(candidate) < len(current):
        return False
    if _claim_coverage(candidate, include_filler=False) < _claim_coverage(current, include_filler=False):
        return False
    if _claim_coverage(candidate, include_filler=True) < _claim_coverage(current, include_filler=True):
        return False
    return True


def _has_uncovered_substantive_text(paragraph: str, claims: list[Claim]) -> bool:
    covered = [False] * len(paragraph)
    for claim in claims:
        for idx in range(max(0, claim.start), min(len(paragraph), claim.end)):
            covered[idx] = True

    for idx, ch in enumerate(paragraph):
        if covered[idx]:
            continue
        if ch.isalnum():
            return True
    return False


def _claim_type_code(claim_type: str) -> str:
    return _CLAIM_TYPE_CODES.get(claim_type, "?")


def _claim_type_code_hint() -> str:
    ordered_types = (
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
        "domain_reasoning",
        "filler",
    )
    return ", ".join(f"{_claim_type_code(claim_type)}={claim_type}" for claim_type in ordered_types)


def _render_marked_paragraph(
    paragraph: str,
    claims: list[Claim],
    findings: list[dict[str, Any]] | None = None,
) -> tuple[str, list[str]]:
    """Inline-mark the paragraph using compact type-coded claim markers.

    Claims use ``[iX{<text>}iX]`` where ``i`` is the actual claim_index and
    ``X`` is a 1-2 character claim-type code. Uncovered substantive spans use
    ``(j{<text>}j)`` with the actual gap index.
    """
    sorted_claims = sorted(claims, key=lambda c: (c.start, c.end))
    events: list[tuple[int, int, int, str, str]] = []
    gap_snippets: list[str] = []
    for idx, claim in enumerate(sorted_claims):
        code = _claim_type_code(claim.claim_type)
        events.append((
            claim.start,
            claim.end,
            0,
            f"[{idx}{code}{{",
            f"}}{idx}{code}]",
        ))
    if findings:
        gap_idx = 0
        for finding in findings:
            if finding.get("kind") != "uncovered_substantive":
                continue
            try:
                gap_start = int(finding["start"])
                gap_end = int(finding["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if gap_end <= gap_start:
                continue
            gap_marker = f"({gap_idx}{{{paragraph[gap_start:gap_end]}}}{gap_idx})"
            gap_snippets.append(gap_marker)
            events.append((
                gap_start,
                gap_end,
                1,
                f"({gap_idx}{{",
                f"}}{gap_idx})",
            ))
            gap_idx += 1

    events.sort(key=lambda item: (item[0], item[2], item[1]))

    parts: list[str] = []
    cursor = 0
    for start, end, _, start_marker, end_marker in events:
        if start < cursor:
            # Overlap with a prior wrapped span; skip to keep markers well-formed.
            continue
        parts.append(paragraph[cursor:start])
        parts.append(start_marker)
        parts.append(paragraph[start:end])
        parts.append(end_marker)
        cursor = end
    parts.append(paragraph[cursor:])
    return "".join(parts), gap_snippets


def _summarize_duplicate_findings(findings: list[dict[str, Any]]) -> str:
    duplicates = [f for f in findings if f.get("kind") == "duplicate_claim"]
    if not duplicates:
        return ""
    lines = []
    for f in duplicates:
        idx = f.get("claim_index")
        original = f.get("original_index")
        lines.append(f"  - claim {idx} duplicates claim {original}")
    return "Duplicate claim markers detected (resolve via delete_claim_entry):\n" + "\n".join(lines)


def _build_review_prompt(
    paragraph: str,
    claims: list[Claim],
    findings: list[dict[str, Any]],
    review_round: int,
) -> str:
    marked_paragraph, gap_snippets = _render_marked_paragraph(paragraph, claims, findings)
    duplicate_note = _summarize_duplicate_findings(findings)
    sections = [
        f"Classifier review round {review_round}.",
        (
            "SECTION shows the original paragraph with inline markers. "
            "`[iX{…}iX]` marks claim_index i with type code X, and `(j{…}j)` "
            "marks uncovered gap j."
        ),
        f"Type codes: {_claim_type_code_hint()}",
    ]
    if gap_snippets:
        sections.extend([
            "UNCLASSIFIED SNIPPETS:",
            *[f"- {snippet}" for snippet in gap_snippets],
        ])
    sections.extend([
        "<<<SECTION",
        marked_paragraph,
        ">>>SECTION",
    ])
    if duplicate_note:
        sections.append(duplicate_note)
    sections.append(
        "If edits are needed, emit MCP tool calls. Otherwise reply DONE with a short reason and no tool call."
    )
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_claims(
    paragraph: str,
    *,
    call_argo_fn=None,
    model: str | None = None,
    max_review_rounds: int | None = None,
) -> list[Claim]:
    """Identify and classify claims in *paragraph* using Argo.

    Returns a list of ``Claim`` objects sorted by start offset.
    Retries up to ``_MAX_RETRIES`` times on parse failure.
    """
    if call_argo_fn is None:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import call_argo as call_argo_fn

    if not paragraph.strip():
        return []

    models_to_try = _model_candidates(model)
    initial_items = _call_classifier_items(
        prompt=paragraph,
        system_prompt=_SYSTEM_PROMPT,
        call_argo_fn=call_argo_fn,
        models_to_try=models_to_try,
    )
    if initial_items is None:
        raise RuntimeError(
            "Classifier initial pass returned no parsable response — refusing to silently "
            "emit zero claims for a non-empty paragraph."
        )

    current_claims = _annotate_claims(
        _anchor_claims(initial_items, paragraph),
        round_index=0,
        stage="initial",
    )
    review_rounds = resolve_claim_classifier_review_rounds(max_review_rounds)

    if review_rounds > 0 and current_claims:
        from .claim_classifier_ReAct import (
            RegexMCPManager,
            _apply_operation_batch,
            _build_regex_findings,
            _build_tool_catalog,
            _coerce_tool_calls,
            _extract_tool_call,
            _run_tool_calls,
        )

        manager = RegexMCPManager()
        review_system_prompt = _CLASSIFIER_REACT_SYSTEM_PROMPT_TEMPLATE.format(tool_catalog=_build_tool_catalog())
        had_review_edits = False
        last_review_round = 0

        for review_round in range(1, review_rounds + 1):
            last_review_round = review_round
            findings = _build_regex_findings(paragraph, current_claims)
            if not findings:
                break
            response = _call_classifier_react_response(
                prompt=_build_review_prompt(paragraph, current_claims, findings, review_round),
                system_prompt=review_system_prompt,
                call_argo_fn=call_argo_fn,
                models_to_try=models_to_try,
            )
            if response is None:
                break

            tool_calls = _coerce_tool_calls(_extract_tool_call(response))
            if not tool_calls:
                break

            operations, results = _run_tool_calls(manager, tool_calls, current_claims, paragraph)
            if not operations:
                log.info("Claim classifier review round %d produced no applicable operations", review_round)
                break

            updated_claims, rejection_reason = _apply_operation_batch(
                current_claims,
                operations,
                paragraph,
                round_index=review_round,
                strategy_version=CLAIM_CLASSIFIER_STRATEGY_VERSION,
                stage="review",
                operation_key="classifier_review_operation",
            )
            if updated_claims is None:
                log.warning(
                    "Claim classifier review round %d rejected invalid patch batch: %s | operations=%s | tool_results=%s",
                    review_round,
                    rejection_reason or "unknown reason",
                    json.dumps(operations, ensure_ascii=False, sort_keys=True),
                    json.dumps(results, ensure_ascii=False, sort_keys=True),
                )
                break

            if _claim_signatures(updated_claims) == _claim_signatures(current_claims):
                break

            current_claims = _annotate_claims(updated_claims, round_index=review_round, stage="review")
            had_review_edits = True
            log.info("Claim classifier review round %d accepted (%d claims)", review_round, len(current_claims))

            if not _build_regex_findings(paragraph, current_claims):
                break

            if all(result.get("operation") is None for result in results):
                break

        if had_review_edits:
            current_claims = _annotate_claims(current_claims, round_index=last_review_round, stage="review_final")

    return current_claims
