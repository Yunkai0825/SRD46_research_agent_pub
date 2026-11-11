"""Argo LLM-based claim grounding against tool results.

Pass 2 of the claim pipeline: given classified claims and the tool
results context, determines which canonical IDs support each claim.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..regex_support_helpers.models import Claim, GroundedClaim

log = logging.getLogger("claim_grounder")

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a grounding verification assistant for thermodynamic stability
constant data.  You will receive:
1. A SECTION from an LLM answer (may include headings, prose, AND tables).
2. A list of claims identified in that section (with indices).
3. Tool results — raw database output containing tables, canonical IDs
   (metal_41, vlm_175400, ligand_5760, beta_def_812, etc.), measurements,
   conditions (T, I, electrolyte), and values (logK, pKa, ΔH, ΔS).

For EACH claim, return:
- **canonical_ids**: prefixed IDs from tool results that support the claim.
  Use exact prefixed forms (e.g. "metal_41", "vlm_175400", "beta_def_32").
  For table row claims → find the matching vlm_/beta_def_ IDs by matching
  the values (logK, T, I, ΔH, ΔS) in the tool results.
  If no ID can be identified, use an EMPTY array [].
- **support_class**: one of:
  - "direct" — claim value appears verbatim in tool results
  - "inferred" — claim can be derived from tool results but is not verbatim
  - "domain_knowledge" — claim is established chemistry / physics knowledge
    that is consistent with the tool results but not stated directly in
    database rows. Use this especially for sound `domain_reasoning` claims.
    Prefer this over "unsupported" for valid background reasoning; use
    "unsupported" for claims that should come from the data but cannot be
    verified there.
  - "unsupported" — claim cannot be verified from tool results AND is not
    recognisable established domain knowledge (treat as potential hallucination)
  - "no_tool_data" — no tool was called that could verify this type of claim
- **evidence_snippet**: ≤200 char quote from the tool results that supports
  the claim (the actual table row, value, or measurement).
  If unsupported or no_tool_data, explain briefly what is missing.
- **tool_snippets**: array of objects linking the claim to specific tool
  result steps.  Each object:
    {"step": "Step N", "tool": "tool_name",
     "snippet": "<relevant row or value from that step's output, ≤300 chars>"}
  Include 1–3 of the most relevant tool result snippets per claim.
  Copy the ACTUAL data (table rows, values, conditions) — not summaries.
  If no tool result is relevant, use an EMPTY array [].

Your returned evidence will be regex-validated against the claim text and
the raw tool results. For DIRECT numeric claims, the cited evidence_snippet
and tool_snippets must contain the actual matching values. If you are unsure,
return a narrower, exact row/value quote or downgrade the support class.

DATA CONVENTIONS:
- **Numeric equivalence**: trailing zeros after a decimal point are NOT
  significant for matching.  Treat values as equal when they round to the
  same number at the precision of the LESS precise value:
    15.10 ≡ 15.1   |   8.560 ≡ 8.56   |   0.10 ≡ 0.1   |   1.0 ≡ 1
  Always compare numbers by VALUE, not by string form.  If a claim says
  "log β₂ = 15.10" and a row shows "15.1", that is a DIRECT match.
- **Database provenance**: "SRD-46", "NIST Standard Reference Database 46",
    and "the database" refer to the source database context for this run.
    The "46" in "SRD-46" / "Database 46" is part of the database NAME, not a
    measured value. Do NOT treat it as a numeric fact that must appear in a
    citation row. Source lines such as "from the NIST SRD-46 database" or
    "Source: NIST Standard Reference Database 46 (SRD-46)" are valid
    provenance claims whenever tool results are present from this run.
- **Missing values** are displayed as "***" or "—" in tool results. If a
  column shows "***", that measurement was not available in the database.
- **Table section headers** provide default context. For example:
  - "Thermodynamic Parameters (at 25 °C unless noted)" → rows without T column
    are at T=25°C by default.
  - "(at I = 0)" → rows without I column are at ionic strength 0.
  If a claim's condition (e.g. 25°C) matches the section header default, the
  row is valid evidence even without that column shown explicitly.  When the
  answer section you are grounding includes a table together with its heading
  (e.g. "## Thermodynamic Parameters (at 25 °C unless noted)"), the heading
  is part of the same claim unit as the rows beneath it.
- **Beta definitions** can have naming flexibility: "CuL (β₁)", "ML", "M+L→ML"
  are equivalent for β₁. Match by stoichiometry and logK values.
- **Ionic strength** may appear as I=0, I(M), I(mol/L), or μ.
- **`execute_srd46_sql` results** are raw SQL query outputs and frequently
  arrive WITHOUT a task description, table title, or column legend in the
  rendered output. To understand what each column means and which table the
  rows came from, you MUST read the `sql_query` text in that step's
  `**Args:**` JSON block. The SELECT list, FROM/JOIN clauses, aliases (e.g.
  `c.metal_name_SRD AS metal`, `s.constant_value AS logK`), and WHERE
  filters are the authoritative legend for the result columns and for the
  conditions that already filter every returned row (e.g. a WHERE clause
  pinning `s.constant_type = 'K'` means every row in that result is a logK
  even if the column is unnamed). When grounding a claim against an
  `execute_srd46_sql` step, cite the matching row AND, when ambiguous, also
  reference the relevant SELECT/WHERE fragment from `sql_query` in
  `evidence_snippet` so the column meaning is unambiguous.
- **Domain reasoning**: claims of claim_type "domain_reasoning" are NOT
    expected to appear verbatim in the database. Prefer
    support_class="domain_knowledge" when the chemistry is sound and the
    database does not contradict it; use "unsupported" for unverified
    data-like claims or when the database conflicts with the reasoning.
- **Trend**: claims of claim_type "trend" describe directional patterns such
    as increase, decrease, ordering, or monotonic change across values or
    conditions. Mark them "direct" only when the trend is explicitly stated in
    tool results; otherwise use "inferred" when the pattern is derived from
    multiple cited rows/values.
- **Filler**: claims of claim_type "filler" are intentionally non-factual or
    non-useful text fragments. They should ALWAYS return support_class=
    "no_tool_data", canonical_ids=[], and no tool snippets. Do not try to
    validate or salvage filler against the database.

Return ONLY a JSON array.  Each element:
  {"claim_index": <int>, "canonical_ids": ["id1", ...],
   "support_class": "direct"|"inferred"|"domain_knowledge"|"unsupported"|"no_tool_data",
   "evidence_snippet": "<brief quote or explanation>",
   "tool_snippets": [{"step": "Step N", "tool": "name", "snippet": "..."}]}

Rules:
- You MUST return one entry per claim_index (do not skip any).
- canonical_ids must use exact prefixed forms from tool results.
- Search the ENTIRE tool results for relevant data — values, IDs, rows.
- For table row claims: match by value columns (logK, T°C, I(M), ΔH, ΔS).
  Even if the answer uses different column names, match on numeric values.
- A claim about a count, value, or entity MUST cite the tool result rows.
- When a claim cannot be verified, say so explicitly in evidence_snippet.
- Read table section headers ("at 25 °C unless noted", "at I=0") to understand
  default conditions that may not be repeated in every row.
- Do NOT wrap in markdown fences.  Only return JSON.
"""

_MAX_TOKENS = 8000
_MAX_JSON_RETRIES = 2
_MAX_VALIDATION_REPAIRS = 1
_CONTEXT_CHAR_LIMIT = 100000  # GPT-5 can handle large context


# ---------------------------------------------------------------------------
# Model candidates
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
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import GROUNDER_MODEL_FALLBACKS  # type: ignore

        for fallback in GROUNDER_MODEL_FALLBACKS:
            candidate = str(fallback).strip()
            if candidate and candidate not in out:
                out.append(candidate)
    except (ImportError, AttributeError, TypeError):
        pass
    return out


# ---------------------------------------------------------------------------
# JSON parsing (same strategy as claim_classifier)
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
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _parse_response(raw: str) -> list[dict] | None:
    """Parse a grounding response.

    Returns the parsed list (possibly empty) on success, or ``None`` if no
    JSON array could be extracted. Empty list is a valid response (the model
    declined to ground anything) and must NOT trigger a retry.
    """
    cleaned = raw.strip()
    candidates: list[str] = [cleaned]
    for block in re.findall(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.I | re.DOTALL):
        if block.strip():
            candidates.append(block.strip())
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
            return items

    recovered = _recover_items(cleaned)
    if recovered:
        log.warning("Recovered %d grounding objects from malformed JSON", len(recovered))
        return recovered

    log.warning("Claim grounder returned non-JSON: %.200s", raw)
    return None


# ---------------------------------------------------------------------------
# Context preparation
# ---------------------------------------------------------------------------

def _truncate_tool_context(tool_eval_text: str) -> str:
    """Truncate tool eval context to fit Argo prompt size limits."""
    if len(tool_eval_text) <= _CONTEXT_CHAR_LIMIT:
        return tool_eval_text

    # Keep the beginning (header + first few tool results)
    # and truncate with an indicator
    return tool_eval_text[:_CONTEXT_CHAR_LIMIT] + "\n\n[… truncated …]"


def _build_prompt(
    paragraph: str,
    claims: list[Claim],
    tool_eval_text: str,
) -> str:
    """Build the user prompt combining paragraph, claims, and tool context."""
    claims_json = json.dumps(
        [{"index": i, "text": c.text, "claim_type": c.claim_type}
         for i, c in enumerate(claims)],
        indent=2,
        ensure_ascii=False,
    )

    context = _truncate_tool_context(tool_eval_text)

    return (
        f"## Answer Section\n{paragraph}\n\n"
        f"## Claims identified in this section\n{claims_json}\n\n"
        f"## Tool Results (database output the LLM had access to)\n{context}"
    )


_NUMERIC_RE = re.compile(r"(?<![\w.])(?P<number>[−-]?\d+(?:\.\d+)?)(?!(?:\.\d)|[\w])")
_STEP_HEADING_RE = re.compile(r"^#{2,3}\s+Step\s+(?P<step>\d+)\b.*?(?:`(?P<tool>[^`]+)`)?", re.IGNORECASE)
_TOOL_SECTION_RE = re.compile(r"^##\s+(?P<tool>.+?)\s+[—-]\s+")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?[\-\s:|]+\|?$")
_DATABASE_NAME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bNIST\s+Standard\s+Reference\s+Database\s+46\b"), "NIST Standard Reference Database"),
    (re.compile(r"(?i)\bStandard\s+Reference\s+Database\s+46\b"), "Standard Reference Database"),
    (re.compile(r"(?i)\bSRD\s*[-–]?\s*46\b"), "SRD"),
)
_DATABASE_PROVENANCE_RE = re.compile(
    r"(?i)(?:\bsource\b.*\b(?:srd\s*[-–]?\s*46|standard\s+reference\s+database\s+46)\b|"
    r"\b(?:nists+)?srd\s*[-–]?\s*46\b|\bstandard\s+reference\s+database\s+46\b|\bthe\s+database\b)"
)
_FULL_JOURNAL_RE = re.compile(r"(?i)journal\s+of\s+chemical\s+(?:&|and)\s+engineering\s+data")

# Patterns for missing value detection
_MISSING_VALUE_PATTERNS = re.compile(
    r"(?i)(?:\b(?:missing|unavailable|not\s+(?:available|reported|measured|found)|"
    r"no\s+(?:data|value|measurement|entry)|N/?A|none)\b|[—–\u2014\u2013]|\*{3})"
)

# Patterns for extracting default context from table headers
_TABLE_HEADER_TEMP_RE = re.compile(r"(?i)(?:at|@)\s*(?:T\s*[=:]?\s*)?(\d+(?:\.\d+)?)\s*°?\s*C(?:\s+unless\s+noted)?")
_TABLE_HEADER_IONIC_RE = re.compile(r"(?i)(?:at|@)\s*I\s*[=:]\s*(\d+(?:\.\d+)?)")


def _claim_mentions_missing_data(claim_text: str) -> bool:
    """Return True if the claim is about missing/unavailable data."""
    return bool(_MISSING_VALUE_PATTERNS.search(claim_text))


def _strip_database_name_numbers(text: str) -> str:
    normalized = text or ""
    for pattern, replacement in _DATABASE_NAME_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _normalize_text_for_match(text: str) -> str:
    normalized = _strip_database_name_numbers(text or "")
    normalized = _FULL_JOURNAL_RE.sub("J Chem Eng Data", normalized)
    normalized = re.sub(r"[*_`~#]", "", normalized)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9_+.-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _extract_claim_value_text(claim_text: str) -> str:
    stripped = (claim_text or "").strip()
    if "|" not in stripped:
        return stripped
    parts = [cell.strip() for cell in stripped.strip("|").split("|")]
    if len(parts) >= 2:
        return parts[-1]
    return stripped


def _is_database_provenance_claim(text: str) -> bool:
    return bool(_DATABASE_PROVENANCE_RE.search(text or ""))


def _extract_context_defaults(tool_eval_text: str) -> dict[str, float]:
    """
    Extract default conditions from table section headers.
    E.g. "Thermodynamic Parameters (at 25 °C unless noted)" → {"default_T": 25.0}
    """
    defaults: dict[str, float] = {}
    
    # Look for section headers with default temperature
    for match in _TABLE_HEADER_TEMP_RE.finditer(tool_eval_text):
        temp_val = float(match.group(1))
        defaults["default_T"] = temp_val
        break  # Use first match
    
    # Look for section headers with default ionic strength
    for match in _TABLE_HEADER_IONIC_RE.finditer(tool_eval_text):
        ionic_val = float(match.group(1))
        defaults["default_I"] = ionic_val
        break
    
    return defaults


def _is_context_implied_value(
    raw: str,
    value: float,
    context_defaults: dict[str, float],
) -> bool:
    """
    Check if a numeric value from the claim is likely a context-implied default.
    E.g. "25" for temperature when table header says "at 25 °C unless noted".
    """
    tolerance = 0.5
    # Common temperature values
    if abs(value - 25) < tolerance and context_defaults.get("default_T", -999) == 25:
        return True
    if abs(value - 37) < tolerance and context_defaults.get("default_T", -999) == 37:
        return True
    # Ionic strength = 0 is very common default
    if abs(value) < 0.01 and context_defaults.get("default_I", -999) == 0:
        return True
    return False


def _extract_numeric_tokens(text: str) -> list[tuple[str, float]]:
    seen: set[tuple[str, float]] = set()
    tokens: list[tuple[str, float]] = []
    normalized = _strip_database_name_numbers((text or "").replace("–", "-"))
    for match in _NUMERIC_RE.finditer(normalized):
        raw = match.group("number").replace("−", "-")
        token = (raw, float(raw))
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _numeric_tolerance(raw: str) -> float:
    normalized = raw.lstrip("-")
    if "." not in normalized:
        return 0.0
    decimals = len(normalized.split(".", 1)[1])
    if decimals >= 2:
        return 0.05
    return 0.15


def _matching_numeric_count(
    claim_tokens: list[tuple[str, float]],
    candidate_tokens: list[tuple[str, float]],
) -> int:
    matches = 0
    for claim_raw, claim_value in claim_tokens:
        tolerance = _numeric_tolerance(claim_raw)
        if any(abs(candidate_value - claim_value) <= max(tolerance, _numeric_tolerance(candidate_raw))
               for candidate_raw, candidate_value in candidate_tokens):
            matches += 1
    return matches


def _claim_keywords(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", text or "")
        if token.lower() not in {"step", "tool", "value", "values", "claim", "direct", "inferred", "database", "srd", "nists"}
    }


def _grounded_to_payload(grounded: GroundedClaim) -> dict[str, Any]:
    return {
        "claim_index": grounded.claim_index,
        "canonical_ids": grounded.canonical_ids,
        "support_class": grounded.support_class,
        "evidence_snippet": grounded.evidence_snippet,
        "tool_snippets": grounded.tool_snippets,
    }


def _iter_tool_result_lines(tool_eval_text: str) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    current_step = ""
    current_tool = ""

    for raw_line in tool_eval_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        step_match = _STEP_HEADING_RE.match(stripped)
        if step_match:
            current_step = f"Step {step_match.group('step')}"
            if step_match.group('tool'):
                current_tool = step_match.group('tool')
            continue

        tool_match = _TOOL_SECTION_RE.match(stripped)
        if tool_match:
            current_tool = tool_match.group('tool').strip()
            continue

        if stripped.startswith("#") or _TABLE_SEPARATOR_RE.fullmatch(stripped):
            continue

        lines.append({
            "step": current_step,
            "tool": current_tool,
            "snippet": stripped[:300],
        })
    return lines


def _best_regex_candidates(
    claim: Claim,
    grounded: GroundedClaim,
    tool_eval_text: str,
    *,
    limit: int = 3,
) -> list[dict[str, str]]:
    claim_tokens = _extract_numeric_tokens(claim.text)
    claim_ids = set(grounded.canonical_ids)
    claim_words = _claim_keywords(claim.text)
    ranked: list[tuple[int, dict[str, str]]] = []

    for candidate in _iter_tool_result_lines(tool_eval_text):
        snippet = candidate["snippet"]
        candidate_tokens = _extract_numeric_tokens(snippet)
        numeric_matches = _matching_numeric_count(claim_tokens, candidate_tokens)
        id_matches = sum(1 for canonical_id in claim_ids if canonical_id in snippet)
        word_matches = len(claim_words & _claim_keywords(snippet))
        score = numeric_matches * 100 + id_matches * 25 + min(word_matches, 10)
        if score <= 0:
            continue
        ranked.append((score, candidate))

    ranked.sort(key=lambda item: (-item[0], len(item[1]["snippet"])))
    best: list[dict[str, str]] = []
    seen_snippets: set[str] = set()
    for _, candidate in ranked:
        snippet = candidate["snippet"]
        if snippet in seen_snippets:
            continue
        seen_snippets.add(snippet)
        best.append(candidate)
        if len(best) >= limit:
            break
    return best


def _find_regex_mismatches(
    claims: list[Claim],
    grounded: list[GroundedClaim],
    tool_eval_text: str,
) -> list[dict[str, Any]]:
    grounded_map = {item.claim_index: item for item in grounded}
    mismatches: list[dict[str, Any]] = []
    
    # Extract default context from table headers (e.g. "at 25 °C unless noted")
    context_defaults = _extract_context_defaults(tool_eval_text)

    for claim_index, claim in enumerate(claims):
        grounded_item = grounded_map.get(claim_index)
        if grounded_item is None or grounded_item.support_class != "direct":
            continue
        
        # Skip validation for claims about missing/unavailable data
        if _claim_mentions_missing_data(claim.text):
            continue

        claim_tokens = _extract_numeric_tokens(claim.text)
        if not claim_tokens:
            continue

        evidence_parts = [grounded_item.evidence_snippet]
        evidence_parts.extend(snippet.get("snippet", "") for snippet in grounded_item.tool_snippets)
        evidence_tokens: list[tuple[str, float]] = []
        for part in evidence_parts:
            evidence_tokens.extend(_extract_numeric_tokens(part))

        matched_count = _matching_numeric_count(claim_tokens, evidence_tokens)
        if matched_count == len(claim_tokens):
            continue

        # Find missing values, excluding context-implied defaults
        missing_values = []
        for raw, value in claim_tokens:
            # Check if value matches any evidence token
            found_in_evidence = any(
                abs(candidate_value - value) <= max(_numeric_tolerance(raw), _numeric_tolerance(candidate_raw))
                for candidate_raw, candidate_value in evidence_tokens
            )
            if found_in_evidence:
                continue
            
            # Check if value is a context-implied default (e.g. T=25 from header)
            if _is_context_implied_value(raw, value, context_defaults):
                continue
            
            missing_values.append(raw)
        
        # If all missing values were context-implied, no mismatch
        if not missing_values:
            continue

        mismatches.append({
            "claim_index": claim_index,
            "claim_text": claim.text,
            "claim_type": claim.claim_type,
            "missing_numeric_values": missing_values,
            "original_grounding": _grounded_to_payload(grounded_item),
            "best_regex_candidates": _best_regex_candidates(claim, grounded_item, tool_eval_text),
        })

    return mismatches


def _build_repair_prompt(
    paragraph: str,
    claims: list[Claim],
    mismatches: list[dict[str, Any]],
    tool_eval_text: str,
) -> str:
    delta_payload = json.dumps(
        [
            {
                "claim_index": item["claim_index"],
                "text": claims[item["claim_index"]].text,
                "claim_type": claims[item["claim_index"]].claim_type,
                "regex_validation": {
                    "missing_numeric_values": item["missing_numeric_values"],
                    "best_regex_candidates": item["best_regex_candidates"],
                },
                "original_grounding": item["original_grounding"],
            }
            for item in mismatches
        ],
        indent=2,
        ensure_ascii=False,
    )
    context = _truncate_tool_context(tool_eval_text)
    context_defaults = _extract_context_defaults(tool_eval_text)
    context_note = ""
    if context_defaults:
        parts = []
        if "default_T" in context_defaults:
            parts.append(f"T={context_defaults['default_T']}°C")
        if "default_I" in context_defaults:
            parts.append(f"I={context_defaults['default_I']}")
        if parts:
            context_note = f"\n\nNOTE: Table headers indicate default conditions ({', '.join(parts)}) that may not appear explicitly in each row.\n"
    
    return (
        "Your previous grounding returned DIRECT evidence whose numeric values failed regex validation. "
        "Repair ONLY the listed claim_index entries below. Compare your original evidence with the best regex "
        "candidates. If a best regex candidate is the correct support, use it. Otherwise search the tool results "
        "context again and return corrected evidence. If you cannot find exact direct support, downgrade the "
        "support_class to 'inferred' (if derivable) or 'unsupported'. "
        f"Return ONLY a JSON array with entries for the listed claim_index values.{context_note}\n\n"
        f"## Answer Section\n{paragraph}\n\n"
        f"## Claims requiring regex repair\n{delta_payload}\n\n"
        f"## Tool Results (database output the LLM had access to)\n{context}"
    )


def _merge_grounded_claims(
    original: list[GroundedClaim],
    repaired: list[GroundedClaim],
) -> list[GroundedClaim]:
    merged = {item.claim_index: item for item in original}
    for item in repaired:
        merged[item.claim_index] = item
    return [merged[index] for index in sorted(merged)]


def _demote_regex_mismatches(
    grounded: list[GroundedClaim],
    mismatches: list[dict[str, Any]],
) -> list[GroundedClaim]:
    mismatch_indices = {item["claim_index"] for item in mismatches}
    demoted: list[GroundedClaim] = []
    for item in grounded:
        if item.claim_index in mismatch_indices:
            demoted.append(GroundedClaim(
                claim_index=item.claim_index,
                support_class="unsupported",
                evidence_snippet="Regex validation failed: returned evidence did not contain the claim value(s).",
            ))
        else:
            demoted.append(item)
    return demoted


def _normalize_special_claim_types(
    claims: list[Claim],
    grounded: list[GroundedClaim],
) -> list[GroundedClaim]:
    grounded_map = {item.claim_index: item for item in grounded}
    normalized: list[GroundedClaim] = []

    for claim_index, claim in enumerate(claims):
        item = grounded_map.get(claim_index)
        if claim.claim_type == "filler":
            normalized.append(GroundedClaim(
                claim_index=claim_index,
                support_class="no_tool_data",
                evidence_snippet="Filler span: no useful database-groundable information.",
            ))
            continue
        if item is not None:
            normalized.append(item)

    seen = {g.claim_index for g in normalized}
    for item in grounded:
        if item.claim_index not in seen:
            normalized.append(item)
    return sorted(normalized, key=lambda g: g.claim_index)


# Claim types whose support_class can be auto-promoted from "inferred" to
# "direct" when regex confirms numeric value equivalence (e.g. 15.10 \u2261 15.1).
_PROMOTABLE_TYPES = {"exact_value", "listing", "calculation"}


def _promote_regex_matches(
    claims: list[Claim],
    grounded: list[GroundedClaim],
    tool_eval_text: str,
) -> list[GroundedClaim]:
    """Upgrade ``inferred`` claims to ``direct`` when regex confirms that
    every numeric token in the claim is matched (within tolerance) by a
    numeric token in the cited evidence.  This corrects cases where the
    LLM downgrades a claim purely because of cosmetic differences such as
    trailing zeros (e.g. ``15.10`` vs ``15.1``).
    """
    grounded_map = {item.claim_index: item for item in grounded}
    promoted: list[GroundedClaim] = []

    for claim_index, claim in enumerate(claims):
        item = grounded_map.get(claim_index)
        if item is None:
            continue
        if item.support_class != "inferred":
            promoted.append(item)
            continue
        if claim.claim_type not in _PROMOTABLE_TYPES:
            promoted.append(item)
            continue
        claim_tokens = _extract_numeric_tokens(claim.text)
        if not claim_tokens:
            promoted.append(item)
            continue

        evidence_parts = [item.evidence_snippet]
        evidence_parts.extend(s.get("snippet", "") for s in item.tool_snippets)
        evidence_tokens: list[tuple[str, float]] = []
        for part in evidence_parts:
            evidence_tokens.extend(_extract_numeric_tokens(part))

        matched = _matching_numeric_count(claim_tokens, evidence_tokens)
        if matched == len(claim_tokens):
            promoted.append(GroundedClaim(
                claim_index=item.claim_index,
                canonical_ids=item.canonical_ids,
                support_class="direct",
                evidence_snippet=item.evidence_snippet,
                tool_snippets=item.tool_snippets,
            ))
        else:
            promoted.append(item)

    # Preserve original ordering / include any items not in the loop above
    # (e.g. if claims length somehow differs)
    seen = {g.claim_index for g in promoted}
    for item in grounded:
        if item.claim_index not in seen:
            promoted.append(item)
    return sorted(promoted, key=lambda g: g.claim_index)


def _call_grounder_once(
    prompt: str,
    *,
    num_claims: int,
    call_argo_fn,
    model: str | None,
) -> list[GroundedClaim]:
    models_to_try = _model_candidates(model)

    for attempt in range(_MAX_JSON_RETRIES + 1):
        actual_prompt = prompt
        if attempt > 0:
            actual_prompt = (
                "Your previous response was not valid JSON. Return ONLY a JSON array.\n\n"
                f"{prompt}"
            )

        raw: str | None = None
        last_err: Exception | None = None
        for candidate in models_to_try:
            try:
                raw = call_argo_fn(
                    prompt=actual_prompt,
                    system=_SYSTEM_PROMPT,
                    stop=[],
                    model=candidate,
                    max_tokens=_MAX_TOKENS,
                )
                break
            except Exception as exc:
                last_err = exc
                log.warning("Argo ground failed model=%s: %s", candidate, exc)

        if raw is None:
            raise RuntimeError(
                f"Argo claim grounding failed for all models {models_to_try}: {last_err}"
            ) from last_err

        items = _parse_response(raw)
        if items is not None:
            return _items_to_grounded(items, num_claims)

    raise RuntimeError(
        f"Argo claim grounding produced unparseable JSON after {_MAX_JSON_RETRIES + 1} attempts"
    )


# ---------------------------------------------------------------------------
# Convert raw items to GroundedClaim objects
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"\b(?:metal|ligand|vlm|beta_def|pka|ref_eq_net|ref_eq_map|lit)_\d+\b")
_CITATION_ROW_RE = re.compile(r"^\|\s*vlm_\d+\s*\|\s*\d+\s*\|\s*lit_\d+\s*\|", re.IGNORECASE)


def _iter_citation_rows(tool_eval_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current_step = ""
    current_tool = ""
    for raw_line in tool_eval_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        step_match = _STEP_HEADING_RE.match(stripped)
        if step_match:
            current_step = f"Step {step_match.group('step')}"
            if step_match.group('tool'):
                current_tool = step_match.group('tool')
            continue
        tool_match = _TOOL_SECTION_RE.match(stripped)
        if tool_match:
            current_tool = tool_match.group('tool').strip()
            continue
        if _CITATION_ROW_RE.match(stripped):
            rows.append({
                "step": current_step,
                "tool": current_tool or "search_citations",
                "snippet": stripped[:300],
            })
    return rows


def _best_citation_row_for_claim(claim: Claim, tool_eval_text: str) -> dict[str, str] | None:
    claim_value = _extract_claim_value_text(claim.text)
    claim_norm = _normalize_text_for_match(claim.text)
    value_norm = _normalize_text_for_match(claim_value)
    claim_ids = set(_ID_RE.findall(claim.text))
    claim_tokens = _extract_numeric_tokens(claim_value or claim.text)
    claim_words = _claim_keywords(value_norm or claim_norm)
    ranked: list[tuple[int, dict[str, str]]] = []

    for row in _iter_citation_rows(tool_eval_text):
        snippet = row["snippet"]
        row_norm = _normalize_text_for_match(snippet)
        score = 0
        if value_norm and value_norm in row_norm:
            score += 200
        if claim_ids:
            score += 75 * sum(1 for claim_id in claim_ids if claim_id in snippet)
        if claim_tokens:
            score += 100 * _matching_numeric_count(claim_tokens, _extract_numeric_tokens(snippet))
        if claim_words:
            score += min(20, len(claim_words & _claim_keywords(row_norm)) * 4)
        if score > 0:
            ranked.append((score, row))

    if ranked:
        ranked.sort(key=lambda item: (-item[0], len(item[1]["snippet"])))
        return ranked[0][1]
    return None


def _salvage_unsupported_claims(
    claims: list[Claim],
    grounded: list[GroundedClaim],
    tool_eval_text: str,
) -> list[GroundedClaim]:
    grounded_map = {item.claim_index: item for item in grounded}
    salvaged: list[GroundedClaim] = []

    for claim_index, claim in enumerate(claims):
        item = grounded_map.get(claim_index)
        if item is None:
            continue
        if item.support_class != "unsupported" or item.evidence_snippet or item.tool_snippets:
            salvaged.append(item)
            continue

        best_row = None
        support_class = "direct"
        if claim.claim_type in {"citation", "counting", "listing"}:
            best_row = _best_citation_row_for_claim(claim, tool_eval_text)
        if best_row is None and _is_database_provenance_claim(claim.text):
            rows = _iter_citation_rows(tool_eval_text)
            if rows:
                best_row = rows[0]
                support_class = "inferred"

        if best_row is None:
            salvaged.append(item)
            continue

        canonical_ids = [cid for cid in _ID_RE.findall(best_row["snippet"])]
        evidence = best_row["snippet"]
        if support_class == "inferred" and _is_database_provenance_claim(claim.text):
            evidence = f"SRD-46 is the database context for this tool result; citation row: {best_row['snippet']}"

        salvaged.append(GroundedClaim(
            claim_index=item.claim_index,
            canonical_ids=canonical_ids,
            support_class=support_class,
            evidence_snippet=evidence[:200],
            tool_snippets=[best_row],
        ))

    seen = {g.claim_index for g in salvaged}
    for item in grounded:
        if item.claim_index not in seen:
            salvaged.append(item)
    return sorted(salvaged, key=lambda g: g.claim_index)


def _items_to_grounded(
    items: list[dict],
    num_claims: int,
) -> list[GroundedClaim]:
    """Convert parsed JSON items to GroundedClaim objects."""
    grounded: list[GroundedClaim] = []
    seen_indices: set[int] = set()

    for item in items:
        idx = item.get("claim_index")
        if not isinstance(idx, int) or idx < 0 or idx >= num_claims:
            continue
        if idx in seen_indices:
            continue
        seen_indices.add(idx)

        raw_ids = item.get("canonical_ids", [])
        # Validate that IDs look like real canonical IDs
        canonical_ids = [
            str(cid) for cid in raw_ids
            if isinstance(cid, str) and _ID_RE.fullmatch(cid)
        ]

        support_class = str(item.get("support_class", "unsupported")).lower()
        if support_class not in ("direct", "inferred", "domain_knowledge", "unsupported", "no_tool_data"):
            support_class = "unsupported"

        evidence = str(item.get("evidence_snippet", ""))[:200]

        # Extract tool_snippets
        raw_snippets = item.get("tool_snippets", [])
        tool_snippets: list[dict[str, str]] = []
        if isinstance(raw_snippets, list):
            for ts in raw_snippets:
                if isinstance(ts, dict) and ts.get("snippet"):
                    tool_snippets.append({
                        "step": str(ts.get("step", ""))[:20],
                        "tool": str(ts.get("tool", ""))[:60],
                        "snippet": str(ts["snippet"])[:300],
                    })

        grounded.append(GroundedClaim(
            claim_index=idx,
            canonical_ids=canonical_ids,
            support_class=support_class,
            evidence_snippet=evidence,
            tool_snippets=tool_snippets,
        ))

    return grounded


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ground_claims(
    paragraph: str,
    claims: list[Claim],
    tool_eval_text: str,
    *,
    call_argo_fn=None,
    model: str | None = None,
) -> list[GroundedClaim]:
    """Ground classified claims against tool results using Argo.

    Returns a list of ``GroundedClaim`` objects (one per claim that
    the LLM was able to analyse).  Claims not returned by the LLM
    are implicitly unsupported.
    """
    if call_argo_fn is None:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import call_argo as call_argo_fn

    if not claims:
        return []

    prompt = _build_prompt(paragraph, claims, tool_eval_text)
    grounded = _call_grounder_once(
        prompt,
        num_claims=len(claims),
        call_argo_fn=call_argo_fn,
        model=model,
    )
    grounded = _normalize_special_claim_types(claims, grounded)
    if not grounded:
        return []

    mismatches = _find_regex_mismatches(claims, grounded, tool_eval_text)
    for repair_round in range(_MAX_VALIDATION_REPAIRS):
        if not mismatches:
            break

        log.info(
            "Regex validation found %d mismatched direct claim(s); requesting delta repair round %d",
            len(mismatches),
            repair_round + 1,
        )
        repaired = _call_grounder_once(
            _build_repair_prompt(paragraph, claims, mismatches, tool_eval_text),
            num_claims=len(claims),
            call_argo_fn=call_argo_fn,
            model=model,
        )
        if not repaired:
            break
        grounded = _merge_grounded_claims(grounded, repaired)
        mismatches = _find_regex_mismatches(claims, grounded, tool_eval_text)

    if mismatches:
        log.warning(
            "Regex validation demoting %d direct claim(s) with unresolved evidence mismatches",
            len(mismatches),
        )
        grounded = _demote_regex_mismatches(grounded, mismatches)

    # Final pass: promote inferred numeric claims to direct when regex confirms
    # that all claim values appear (within tolerance) in the cited evidence.
    # This corrects cosmetic downgrades like 15.10 vs 15.1.
    grounded = _promote_regex_matches(claims, grounded, tool_eval_text)
    grounded = _salvage_unsupported_claims(claims, grounded, tool_eval_text)
    grounded = _normalize_special_claim_types(claims, grounded)

    # ReAct loop: regex-first MCP edits over the *reference* fields only.
    from .claim_grounder_ReAct import _react_patch_grounded

    grounded = _react_patch_grounded(
        paragraph,
        claims,
        grounded,
        tool_eval_text,
        call_argo_fn=call_argo_fn,
        model=model,
    )

    return grounded

