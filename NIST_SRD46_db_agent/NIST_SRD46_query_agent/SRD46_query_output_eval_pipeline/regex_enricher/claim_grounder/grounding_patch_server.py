#!/usr/bin/env python
"""FastMCP grounding-reference patch tools for the grounder ReAct loop.

These tools propose patches to the *reference / grounding* fields of an
already-classified claim:
    canonical_ids, support_class, evidence_snippet, tool_snippets

They MUST NOT change the claim text or claim_type; that is the classifier's
responsibility. The claim list is passed read-only for context only.
"""
from __future__ import annotations

import json
from typing import Any, Optional

# Support direct subprocess launches as well as package imports.
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).absolute().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mcp.server.fastmcp import FastMCP

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.regex_support_helpers.models import SUPPORT_CLASSES

mcp = FastMCP(
    "RegexGroundingPatch",
    instructions=(
        "You are a grounding-reference editor for the SRD-46 claim pipeline. "
        "You may patch only the reference fields of an existing grounded claim: "
        "canonical_ids, support_class, evidence_snippet, and tool_snippets. "
        "You MUST NOT change the claim text or claim_type."
    ),
    log_level="ERROR",
)


def _parse_json_list(payload: str, name: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError(f"{name} must decode to a JSON array")
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{name} entries must be objects")
        items.append(item)
    return items


def _find_grounded(grounded: list[dict[str, Any]], claim_index: int) -> dict[str, Any]:
    for item in grounded:
        if int(item.get("claim_index", -1)) == claim_index:
            return item
    raise ValueError(f"claim_index {claim_index} not present in grounded list")


def _normalize_support_class(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in SUPPORT_CLASSES:
        raise ValueError(
            f"support_class must be one of {', '.join(SUPPORT_CLASSES)}"
        )
    return normalized


def _normalize_canonical_ids(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("canonical_ids must be a JSON array of strings")
    out: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("canonical_ids entries must be non-empty strings")
        out.append(item.strip())
    return out


def _normalize_tool_snippets(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("tool_snippets must be a JSON array of objects")
    out: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("tool_snippets entries must be objects")
        snippet = item.get("snippet")
        if not isinstance(snippet, str) or not snippet.strip():
            raise ValueError("tool_snippets entries must include a non-empty 'snippet' string")
        out.append({
            "step": str(item.get("step", "") or "")[:20],
            "tool": str(item.get("tool", "") or "")[:60],
            "snippet": snippet.strip()[:300],
        })
    return out


def _operation_result(operation: dict[str, Any]) -> str:
    return json.dumps({"ok": True, "operation": operation}, indent=2, ensure_ascii=False)


@mcp.tool(name="inspect_grounded_claims")
def inspect_grounded_claims(claims_json: str, grounded_json: str) -> str:
    """Return the current claims joined with their grounding references.

    Parameters
    ----------
    claims_json : JSON array of the (immutable) classified claims
    grounded_json : JSON array of the current GroundedClaim entries
    """
    claims = _parse_json_list(claims_json, "claims_json")
    grounded = _parse_json_list(grounded_json, "grounded_json")
    rows: list[dict[str, Any]] = []
    for idx, claim in enumerate(claims):
        try:
            ref = _find_grounded(grounded, idx)
        except ValueError:
            ref = {
                "canonical_ids": [],
                "support_class": "unsupported",
                "evidence_snippet": "",
                "tool_snippets": [],
            }
        rows.append({
            "claim_index": idx,
            "claim_text": str(claim.get("text", "")),
            "claim_type": str(claim.get("claim_type", "")),
            "canonical_ids": list(ref.get("canonical_ids", [])),
            "support_class": str(ref.get("support_class", "unsupported")),
            "evidence_snippet": str(ref.get("evidence_snippet", "")),
            "tool_snippets": list(ref.get("tool_snippets", [])),
        })
    return json.dumps(
        {"ok": True, "claim_count": len(rows), "rows": rows},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool(name="set_support_class")
def set_support_class(
    grounded_json: str,
    claim_index: int,
    new_support_class: str,
    reason: str = "",
) -> str:
    """Validate a support_class change and return a set_support_class operation."""
    grounded = _parse_json_list(grounded_json, "grounded_json")
    _find_grounded(grounded, int(claim_index))
    normalized = _normalize_support_class(new_support_class)
    return _operation_result({
        "op": "set_support_class",
        "claim_index": int(claim_index),
        "support_class": normalized,
        "reason": str(reason or ""),
    })


@mcp.tool(name="set_evidence")
def set_evidence(
    grounded_json: str,
    claim_index: int,
    new_evidence_snippet: Optional[str] = None,
    new_canonical_ids_json: Optional[str] = None,
) -> str:
    """Validate an evidence_snippet and/or canonical_ids change.

    Pass ``new_evidence_snippet`` to replace the evidence string (capped at 200
    chars). Pass ``new_canonical_ids_json`` as a JSON array of strings to
    replace the canonical_ids list. Omitted fields are left unchanged.
    """
    grounded = _parse_json_list(grounded_json, "grounded_json")
    _find_grounded(grounded, int(claim_index))
    operation: dict[str, Any] = {
        "op": "set_evidence",
        "claim_index": int(claim_index),
    }
    if new_evidence_snippet is not None:
        operation["evidence_snippet"] = str(new_evidence_snippet)[:200]
    if new_canonical_ids_json is not None:
        try:
            parsed_ids = json.loads(new_canonical_ids_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"new_canonical_ids_json must be valid JSON: {exc}"
            ) from exc
        operation["canonical_ids"] = _normalize_canonical_ids(parsed_ids)
    if "evidence_snippet" not in operation and "canonical_ids" not in operation:
        raise ValueError(
            "set_evidence requires at least one of new_evidence_snippet or new_canonical_ids_json"
        )
    return _operation_result(operation)


@mcp.tool(name="replace_tool_snippets")
def replace_tool_snippets(
    grounded_json: str,
    claim_index: int,
    new_tool_snippets_json: str,
) -> str:
    """Validate a full replacement of tool_snippets and return the operation.

    ``new_tool_snippets_json`` must be a JSON array of objects, each with
    a non-empty ``snippet`` string and optional ``step``/``tool`` strings.
    """
    grounded = _parse_json_list(grounded_json, "grounded_json")
    _find_grounded(grounded, int(claim_index))
    try:
        parsed = json.loads(new_tool_snippets_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"new_tool_snippets_json must be valid JSON: {exc}"
        ) from exc
    snippets = _normalize_tool_snippets(parsed)
    return _operation_result({
        "op": "replace_tool_snippets",
        "claim_index": int(claim_index),
        "tool_snippets": snippets,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
