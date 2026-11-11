"""Argo LLM-assisted span identification.

Calls the Argo API to identify exact chemical-name tokens, numerical
values, and canonical IDs in each paragraph.  The LLM output is merged
with the regex-based spans from ``token_extractor`` to form the final
annotation set.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from .regex_support_helpers.models import ChemSpan, IdSpan, NumericSpan, TokenSpan
from .regex_support_helpers.token_extractor import _deduplicate_spans

log = logging.getLogger("regex_enricher.argo")

# ---------------------------------------------------------------------------
# Argo system prompt for span identification
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a scientific text annotation assistant.  Given a paragraph from
an answer about thermodynamic stability constants (NIST SRD-46 data),
identify every occurrence of:

1. **Numerical values** — any number that represents a measurement
   (log K, pKa, ΔH, ΔS, ΔG, temperature, ionic strength, etc.).
   Return the exact text token and its quantity type.

2. **Chemical names** — element names, ligand names, ion formulas,
   IUPAC names, or common abbreviations (EDTA, glycine, Cu²⁺, etc.).
   Return the exact text token and a normalised form.

3. **Canonical IDs** — prefixed identifiers like metal_41, vlm_93847,
   beta_def_812, ligand_5760, ref_eq_net_86, etc.  Return the exact
   text token and entity type.

Respond ONLY with a JSON array.  Each element must have:
  {"text": "<exact token>", "type": "numeric"|"chem"|"id",
   "detail": "<quantity_type or normalized_name or entity_type>"}

If nothing is found, return [].  Do NOT explain, only return JSON.
"""

_ARGO_MAX_TOKENS = 700


def _model_candidates(model: str | None) -> list[str | None]:
    """Return model fallback candidates for Argo naming variants."""
    if not model:
        return [None]

    m = model.strip()
    out: list[str | None] = [m]
    low = m.lower()

    alias_map = {
        "gpt41": ["gpt4.1", "gpt-4.1"],
        "gpt4.1": ["gpt41", "gpt-4.1"],
        "gpt-4.1": ["gpt41", "gpt4.1"],
    }
    for alias in alias_map.get(low, []):
        if alias not in out:
            out.append(alias)
    return out


def enrich_paragraph_with_argo(
    paragraph: str,
    *,
    call_argo_fn=None,
    model: str | None = None,
) -> list[TokenSpan]:
    """Call Argo to identify spans in *paragraph*, return parsed spans.

    Parameters
    ----------
    call_argo_fn
        Callable matching ``call_argo(prompt, system, ...)`` signature.
        If *None*, imports from ``argo_client``.
    model
        Argo model override (default uses ``argo_config.MODEL``).
    """
    if call_argo_fn is None:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import call_argo as call_argo_fn

    if not paragraph.strip():
        return []

    raw: str | None = None
    last_err: Exception | None = None
    models_to_try = _model_candidates(model)
    for candidate in models_to_try:
        try:
            raw = call_argo_fn(
                prompt=paragraph,
                system=_SYSTEM_PROMPT,
                stop=[],
                model=candidate,
                max_tokens=_ARGO_MAX_TOKENS,
            )
            break
        except Exception as exc:
            last_err = exc
            log.debug("Argo call failed with model=%s: %s", candidate, exc)

    if raw is None:
        log.warning(
            "Argo call failed for paragraph (%.40s…) using models=%s; last error=%s",
            paragraph,
            models_to_try,
            last_err,
        )
        return []

    return _parse_argo_response(raw, paragraph)


def _try_load_json_array(text: str) -> list[dict[str, Any]] | None:
    """Return parsed list if *text* is a JSON array of dicts, else None."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return None


def _extract_first_balanced_array(text: str) -> str | None:
    """Extract first balanced JSON array slice from arbitrary text."""
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


def _recover_items_from_fragments(text: str) -> list[dict[str, Any]]:
    """Recover JSON objects from malformed array output.

    This tolerates truncated responses by parsing complete ``{...}``
    fragments that still decode as valid JSON dict objects.
    """
    items: list[dict[str, Any]] = []
    for m in re.finditer(r"\{[^{}]*\}", text, flags=re.DOTALL):
        frag = m.group(0)
        try:
            obj = json.loads(frag)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _items_to_spans(items: list[dict[str, Any]], paragraph: str) -> list[TokenSpan]:
    """Convert parsed Argo item dicts to token spans."""
    spans: list[TokenSpan] = []

    for item in items:
        text = str(item.get("text", ""))
        span_type = str(item.get("type", "")).strip().lower()
        detail = str(item.get("detail", ""))
        if not text or span_type not in ("numeric", "chem", "id"):
            continue

        # Find the exact position in the paragraph
        pos = paragraph.find(text)
        if pos == -1:
            # Try case-insensitive search
            lower_para = paragraph.lower()
            pos = lower_para.find(text.lower())
        if pos == -1:
            continue

        start, end = pos, pos + len(text)

        if span_type == "numeric":
            try:
                value = float(re.sub(r"[−–]", "-", text).strip())
            except ValueError:
                value = 0.0
            spans.append(NumericSpan(
                start=start, end=end, text=text,
                span_type="numeric", value=value,
                quantity_type=detail or None,
            ))
        elif span_type == "chem":
            spans.append(ChemSpan(
                start=start, end=end, text=text,
                span_type="chem", normalized_name=detail or text,
            ))
        elif span_type == "id":
            raw_id = 0
            m = re.search(r"(\d+)$", text)
            if m:
                raw_id = int(m.group(1))
            spans.append(IdSpan(
                start=start, end=end, text=text,
                span_type="id", entity_type=detail or "",
                raw_id=raw_id,
            ))

    return spans


def _parse_argo_response(raw: str, paragraph: str) -> list[TokenSpan]:
    """Parse the JSON array returned by Argo into TokenSpan objects."""
    cleaned = raw.strip()

    # Candidates: direct output, fenced JSON block content, and first
    # balanced JSON array slice.
    candidates: list[str] = [cleaned]

    fenced_blocks = re.findall(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())

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
            return _items_to_spans(items, paragraph)

    recovered = _recover_items_from_fragments(cleaned)
    if recovered:
        log.warning(
            "Argo returned malformed JSON; recovered %d objects from response",
            len(recovered),
        )
        return _items_to_spans(recovered, paragraph)

    log.warning("Argo returned non-JSON: %.200s", raw)
    return []


# ---------------------------------------------------------------------------
# Merge regex + Argo spans
# ---------------------------------------------------------------------------

def merge_spans(
    regex_spans: list[TokenSpan],
    argo_spans: list[TokenSpan],
) -> list[TokenSpan]:
    """Union regex and Argo spans, de-duplicating overlaps.

    Regex spans are trusted as precise; Argo spans fill gaps the regex
    missed (especially chemical names with unusual spelling).
    """
    combined = list(regex_spans) + list(argo_spans)
    return _deduplicate_spans(combined)
