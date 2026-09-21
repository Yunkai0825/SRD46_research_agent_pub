#!/usr/bin/env python
"""FastMCP claim-edit tools for regex validation refinement.

These tools validate and propose claim-list patch operations over a single
paragraph. They are intentionally stateless: the caller passes the current
paragraph text and claim list on each invocation, and the tool returns a
validated patch payload that can be merged by the caller.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

# Support direct subprocess launches as well as package imports.
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).absolute().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mcp.server.fastmcp import FastMCP

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.regex_support_helpers.models import CLAIM_TYPES

mcp = FastMCP(
    "RegexClaimPatch",
    instructions=(
        "You are a claim-editing MCP server for the SRD-46 regex claim pipeline. "
        "You validate add, edit, and delete operations over the current claim list. "
        "All claim text must be exact substrings of the provided paragraph."
    ),
    log_level="ERROR",
)


def _parse_claims_json(claims_json: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(claims_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"claims_json must be valid JSON: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError("claims_json must decode to a JSON array")
    claims: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("claims_json entries must be objects")
        claims.append(item)
    return claims


def _normalize_claim_type(claim_type: str) -> str:
    normalized = str(claim_type or "").strip().lower()
    if normalized not in CLAIM_TYPES:
        raise ValueError(f"claim_type must be one of {', '.join(CLAIM_TYPES)}")
    return normalized


def _anchor_text(paragraph: str, text: str) -> tuple[int, int, str]:
    snippet = str(text or "").strip()
    if not snippet:
        raise ValueError("text must be non-empty")

    start = paragraph.find(snippet)
    if start == -1:
        start = paragraph.lower().find(snippet.lower())
    if start == -1:
        raise ValueError("text must be an exact substring of the paragraph")
    end = start + len(snippet)
    return start, end, paragraph[start:end]


def _claim_span(claim: dict[str, Any], paragraph: str) -> tuple[int, int, str]:
    text = str(claim.get("text", "") or "")
    start = claim.get("start")
    end = claim.get("end")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(paragraph):
        if paragraph[start:end] == text:
            return start, end, text
    return _anchor_text(paragraph, text)


def _find_conflicts(
    claims: list[dict[str, Any]],
    paragraph: str,
    start: int,
    end: int,
    *,
    ignore_index: int | None = None,
) -> list[int]:
    conflicts: list[int] = []
    for idx, claim in enumerate(claims):
        if ignore_index is not None and idx == ignore_index:
            continue
        other_start, other_end, _ = _claim_span(claim, paragraph)
        if not (end <= other_start or start >= other_end):
            conflicts.append(idx)
    return conflicts


def _operation_result(operation: dict[str, Any]) -> str:
    return json.dumps({"ok": True, "operation": operation}, indent=2, ensure_ascii=False)


@mcp.tool(name="inspect_claim_entries")
def inspect_claim_entries(paragraph: str, claims_json: str) -> str:
    """Return the current claim entries with indices, anchored spans, and conflicts.

    Parameters
    ----------
    paragraph : original section text
    claims_json : JSON array of the current claim list
    """
    claims = _parse_claims_json(claims_json)
    rows: list[dict[str, Any]] = []
    for idx, claim in enumerate(claims):
        start, end, text = _claim_span(claim, paragraph)
        rows.append({
            "claim_index": idx,
            "start": start,
            "end": end,
            "text": text,
            "claim_type": _normalize_claim_type(str(claim.get("claim_type", ""))),
            "conflicts": _find_conflicts(claims, paragraph, start, end, ignore_index=idx),
        })
    return json.dumps({
        "ok": True,
        "claim_count": len(rows),
        "claims": rows,
        "paragraph_length": len(paragraph),
    }, indent=2, ensure_ascii=False)


@mcp.tool(name="add_claim_entry")
def add_claim_entry(
    paragraph: str,
    claims_json: str,
    text: str,
    claim_type: str,
) -> str:
    """Validate a new claim entry and return an add-operation payload."""
    claims = _parse_claims_json(claims_json)
    normalized_type = _normalize_claim_type(claim_type)
    start, end, anchored_text = _anchor_text(paragraph, text)
    conflicts = _find_conflicts(claims, paragraph, start, end)
    return _operation_result({
        "op": "add",
        "claim": {
            "start": start,
            "end": end,
            "text": anchored_text,
            "claim_type": normalized_type,
        },
        "conflicts": conflicts,
    })


@mcp.tool(name="edit_claim_entry")
def edit_claim_entry(
    paragraph: str,
    claims_json: str,
    claim_index: int,
    new_text: Optional[str] = None,
    new_claim_type: Optional[str] = None,
) -> str:
    """Validate an edit to an existing claim entry and return an edit operation."""
    claims = _parse_claims_json(claims_json)
    if not (0 <= claim_index < len(claims)):
        raise ValueError(f"claim_index must be between 0 and {len(claims) - 1}")

    existing = claims[claim_index]
    target_text = new_text if new_text is not None else str(existing.get("text", ""))
    target_type = new_claim_type if new_claim_type is not None else str(existing.get("claim_type", ""))
    normalized_type = _normalize_claim_type(target_type)
    start, end, anchored_text = _anchor_text(paragraph, target_text)
    conflicts = _find_conflicts(claims, paragraph, start, end, ignore_index=claim_index)
    return _operation_result({
        "op": "edit",
        "claim_index": int(claim_index),
        "claim": {
            "start": start,
            "end": end,
            "text": anchored_text,
            "claim_type": normalized_type,
        },
        "conflicts": conflicts,
    })


@mcp.tool(name="delete_claim_entry")
def delete_claim_entry(
    paragraph: str,
    claims_json: str,
    claim_index: int,
    reason: str = "",
) -> str:
    """Validate deletion of an existing claim entry and return a delete operation."""
    claims = _parse_claims_json(claims_json)
    if not (0 <= claim_index < len(claims)):
        raise ValueError(f"claim_index must be between 0 and {len(claims) - 1}")
    _claim_span(claims[claim_index], paragraph)
    return _operation_result({
        "op": "delete",
        "claim_index": int(claim_index),
        "reason": str(reason or ""),
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
