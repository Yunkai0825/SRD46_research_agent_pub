"""Regex-first MCP review helpers for the claim classifier ReAct loop.

These helpers feed the classifier's review-edit loop: regex coverage
findings, tool-call extraction, parallel-safety checks, and applying
add/edit/delete operations to a Claim list. The MCP tool server lives
in ``claim_patch_server.py`` next to this module.

Note: these helpers DO mutate claim text/type — that is the classifier's
job. Reference fields (canonical_ids, support_class, evidence_snippet,
tool_snippets) are owned by the grounder ReAct loop.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..regex_support_helpers.models import CLAIM_TYPES, Claim

log = logging.getLogger("claim_classifier_react")

_TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\[.*?\]|\{.*?\})\s*</tool_call>", re.DOTALL
)
_BARE_TOOL_CALL_PATTERN = re.compile(
    r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}'
)
_SUBSTANTIVE_RE = re.compile(r"[A-Za-z0-9]")

_REGEX_MCP_SERVER_PATH = Path(__file__).resolve().parent / "claim_patch_server.py"
_REGEX_MCP_MODULE = None
_REGEX_MCP_TOOL_CATALOG: str | None = None


# ---------------------------------------------------------------------------
# MCP loading + tool catalog
# ---------------------------------------------------------------------------

def _load_regex_mcp_module():
    global _REGEX_MCP_MODULE
    if _REGEX_MCP_MODULE is not None:
        return _REGEX_MCP_MODULE
    spec = importlib.util.spec_from_file_location(
        "_regex_claim_patch_server", _REGEX_MCP_SERVER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load regex MCP tools from {_REGEX_MCP_SERVER_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _REGEX_MCP_MODULE = module
    return module


def _build_tool_catalog() -> str:
    global _REGEX_MCP_TOOL_CATALOG
    if _REGEX_MCP_TOOL_CATALOG is not None:
        return _REGEX_MCP_TOOL_CATALOG
    module = _load_regex_mcp_module()
    tools = asyncio.run(module.mcp.list_tools())
    lines: list[str] = []
    for tool in sorted(tools, key=lambda item: item.name):
        params = tool.inputSchema.get("properties", {})
        required = set(tool.inputSchema.get("required", []))
        signature: list[str] = []
        for name, info in params.items():
            suffix = "" if name in required else "?"
            signature.append(f"{name}{suffix}: {info.get('type', 'any')}")
        lines.append(f"  {tool.name}({', '.join(signature)})")
        description = (tool.description or "").strip()
        for line in description.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(f"    {stripped}")
    _REGEX_MCP_TOOL_CATALOG = "\n".join(lines)
    return _REGEX_MCP_TOOL_CATALOG


class RegexMCPManager:
    """Small in-process tool manager for the classifier MCP tools."""

    def __init__(self) -> None:
        self.module = _load_regex_mcp_module()
        self.tool_index = {
            "inspect_claim_entries": self.module.inspect_claim_entries,
            "add_claim_entry": self.module.add_claim_entry,
            "edit_claim_entry": self.module.edit_claim_entry,
            "delete_claim_entry": self.module.delete_claim_entry,
        }

    def call_tool_safe(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        impl = self.tool_index.get(tool_name)
        if impl is None:
            return False, f"[TOOL ERROR] {tool_name}: tool not found"
        try:
            return True, impl(**args)
        except Exception as exc:  # pragma: no cover - surfaced as text
            return False, f"[TOOL ERROR] {tool_name}: {exc}"


# ---------------------------------------------------------------------------
# Claim helpers
# ---------------------------------------------------------------------------

def _claim_signature(claim: Claim) -> tuple[int, int, str, str]:
    return (claim.start, claim.end, claim.text, claim.claim_type)


def _clone_claim(claim: Claim) -> Claim:
    return Claim(
        start=claim.start,
        end=claim.end,
        text=claim.text,
        claim_type=claim.claim_type,
        metadata=dict(claim.metadata),
    )


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


def _claims_to_json(claims: list[Claim]) -> str:
    return json.dumps([
        {
            "start": claim.start,
            "end": claim.end,
            "text": claim.text,
            "claim_type": claim.claim_type,
            "metadata": claim.metadata,
        }
        for claim in claims
    ], ensure_ascii=False)


def _sorted_claims(claims: list[Claim]) -> list[Claim]:
    return sorted(
        claims,
        key=lambda claim: (claim.start, claim.end, claim.text, claim.claim_type),
    )


def _validate_claim_list(paragraph: str, claims: list[Claim]) -> bool:
    valid, _ = _validate_claim_list_reason(paragraph, claims)
    return valid


def _validate_claim_list_reason(
    paragraph: str,
    claims: list[Claim],
) -> tuple[bool, str | None]:
    sorted_claims = _sorted_claims(claims)
    for idx, claim in enumerate(sorted_claims):
        if claim.claim_type not in CLAIM_TYPES:
            return False, f"claim {idx} has invalid claim_type {claim.claim_type!r}"
        if paragraph[claim.start:claim.end] != claim.text:
            actual_text = paragraph[claim.start:claim.end]
            return False, (
                f"claim {idx} text/span mismatch at [{claim.start}, {claim.end}): "
                f"claim_text={claim.text!r}, paragraph_text={actual_text!r}"
            )
        if idx > 0 and claim.start < sorted_claims[idx - 1].end:
            prev_claim = sorted_claims[idx - 1]
            return False, (
                f"claim {idx - 1} [{prev_claim.start}, {prev_claim.end}) overlaps "
                f"claim {idx} [{claim.start}, {claim.end})"
            )
    return True, None


# ---------------------------------------------------------------------------
# Regex findings (coverage gaps + duplicates)
# ---------------------------------------------------------------------------

def _find_uncovered_substantive_spans(
    paragraph: str, claims: list[Claim]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cursor = 0
    for claim in _sorted_claims(claims):
        if cursor < claim.start:
            gap = paragraph[cursor:claim.start]
            if _SUBSTANTIVE_RE.search(gap):
                trimmed_left = len(gap) - len(gap.lstrip())
                trimmed_right = len(gap.rstrip())
                start = cursor + trimmed_left
                end = cursor + trimmed_right
                if start < end:
                    findings.append({
                        "kind": "uncovered_substantive",
                        "start": start,
                        "end": end,
                        "text": paragraph[start:end],
                        "message": "Substantive text is not covered by any claim.",
                    })
        cursor = max(cursor, claim.end)
    if cursor < len(paragraph):
        gap = paragraph[cursor:]
        if _SUBSTANTIVE_RE.search(gap):
            trimmed_left = len(gap) - len(gap.lstrip())
            trimmed_right = len(gap.rstrip())
            start = cursor + trimmed_left
            end = cursor + trimmed_right
            if start < end:
                findings.append({
                    "kind": "uncovered_substantive",
                    "start": start,
                    "end": end,
                    "text": paragraph[start:end],
                    "message": "Substantive text is not covered by any claim.",
                })
    return findings


def _find_duplicate_claims(claims: list[Claim]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], int] = {}
    for idx, claim in enumerate(_sorted_claims(claims)):
        key = (claim.text, claim.claim_type)
        if key in seen:
            findings.append({
                "kind": "duplicate_claim",
                "claim_index": idx,
                "original_index": seen[key],
                "text": claim.text,
                "message": "Duplicate claim text and type detected.",
            })
        else:
            seen[key] = idx
    return findings


def _build_regex_findings(
    paragraph: str, claims: list[Claim]
) -> list[dict[str, Any]]:
    findings = _find_uncovered_substantive_spans(paragraph, claims)
    findings.extend(_find_duplicate_claims(claims))
    return findings


# ---------------------------------------------------------------------------
# Tool-call extraction + parallel-safety
# ---------------------------------------------------------------------------

def _extract_tool_call(text: str) -> Any | None:
    match = _TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    bare = _BARE_TOOL_CALL_PATTERN.search(text)
    if bare:
        try:
            return json.loads(bare.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _coerce_tool_calls(parsed_call: Any) -> list[dict[str, Any]]:
    if parsed_call is None:
        return []
    if isinstance(parsed_call, dict):
        return [parsed_call]
    if isinstance(parsed_call, list):
        return [item for item in parsed_call if isinstance(item, dict)]
    return []


def _tool_target_range(
    tool_call: dict[str, Any], claims: list[Claim], paragraph: str
) -> tuple[int, int] | None:
    tool_name = str(tool_call.get("name", ""))
    arguments = tool_call.get("arguments", {}) or {}
    if tool_name == "delete_claim_entry":
        return None
    if tool_name == "edit_claim_entry":
        try:
            claim_index = int(arguments.get("claim_index", -1))
        except (TypeError, ValueError):
            return None
        if not (0 <= claim_index < len(claims)):
            return None
        new_text = arguments.get("new_text")
        if new_text is None:
            return claims[claim_index].start, claims[claim_index].end
        try:
            start, end, _ = _anchor_text(paragraph, str(new_text))
        except ValueError:
            return None
        return start, end
    if tool_name == "add_claim_entry":
        try:
            start, end, _ = _anchor_text(paragraph, str(arguments.get("text", "")))
        except ValueError:
            return None
        return start, end
    return None


def _can_parallelize_tool_calls(
    tool_calls: list[dict[str, Any]], claims: list[Claim], paragraph: str
) -> bool:
    if len(tool_calls) < 2:
        return False
    write_calls = [tc for tc in tool_calls if tc.get("name") != "inspect_claim_entries"]
    if len(write_calls) < 2:
        return False

    seen_indices: set[int] = set()
    ranges: list[tuple[int, int]] = []
    for tool_call in write_calls:
        name = str(tool_call.get("name", ""))
        arguments = tool_call.get("arguments", {}) or {}
        if name in {"edit_claim_entry", "delete_claim_entry"}:
            try:
                claim_index = int(arguments.get("claim_index", -1))
            except (TypeError, ValueError):
                return False
            if claim_index in seen_indices:
                return False
            seen_indices.add(claim_index)
        target = _tool_target_range(tool_call, claims, paragraph)
        if target is not None:
            start, end = target
            for other_start, other_end in ranges:
                if not (end <= other_start or start >= other_end):
                    return False
            ranges.append(target)
    return True


# ---------------------------------------------------------------------------
# Operation application
# ---------------------------------------------------------------------------

def _claim_from_operation(
    op_claim: dict[str, Any],
    *,
    round_index: int,
    strategy_version: str,
    op_name: str,
    stage: str = "review",
    operation_key: str = "classifier_review_operation",
) -> Claim:
    metadata = dict(op_claim.get("metadata", {}) or {})
    metadata.update({
        "classifier_strategy_version": strategy_version,
        "classifier_stage": stage,
        "classifier_round": round_index,
        operation_key: op_name,
    })
    return Claim(
        start=int(op_claim["start"]),
        end=int(op_claim["end"]),
        text=str(op_claim["text"]),
        claim_type=str(op_claim["claim_type"]),
        metadata=metadata,
    )


def _apply_operation_batch(
    claims: list[Claim],
    operations: list[dict[str, Any]],
    paragraph: str,
    *,
    round_index: int,
    strategy_version: str,
    stage: str = "review",
    operation_key: str = "classifier_review_operation",
) -> tuple[list[Claim] | None, str | None]:
    originals = [_clone_claim(claim) for claim in claims]
    replacements: dict[int, Claim | None] = {}
    additions: list[Claim] = []

    for op in operations:
        op_name = str(op.get("op", ""))
        if op_name == "delete":
            try:
                claim_index = int(op["claim_index"])
            except (KeyError, TypeError, ValueError):
                return None, "delete operation missing a valid claim_index"
            if not (0 <= claim_index < len(originals)):
                return None, f"delete operation claim_index {claim_index} is out of range"
            if claim_index in replacements:
                return None, f"multiple operations target claim_index {claim_index}"
            replacements[claim_index] = None
        elif op_name == "edit":
            try:
                claim_index = int(op["claim_index"])
            except (KeyError, TypeError, ValueError):
                return None, "edit operation missing a valid claim_index"
            if not (0 <= claim_index < len(originals)):
                return None, f"edit operation claim_index {claim_index} is out of range"
            if claim_index in replacements:
                return None, f"multiple operations target claim_index {claim_index}"
            try:
                replacement_claim = _claim_from_operation(
                    dict(op["claim"]),
                    round_index=round_index,
                    strategy_version=strategy_version,
                    op_name="edit",
                    stage=stage,
                    operation_key=operation_key,
                )
            except (KeyError, TypeError, ValueError) as exc:
                return None, f"edit operation for claim_index {claim_index} is invalid: {exc}"
            replacements[claim_index] = replacement_claim
        elif op_name == "add":
            try:
                additions.append(_claim_from_operation(
                    dict(op["claim"]),
                    round_index=round_index,
                    strategy_version=strategy_version,
                    op_name="add",
                    stage=stage,
                    operation_key=operation_key,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                return None, f"add operation is invalid: {exc}"
        else:
            return None, f"unsupported operation {op_name!r}"

    updated: list[Claim] = []
    for idx, claim in enumerate(originals):
        if idx in replacements:
            replacement = replacements[idx]
            if replacement is not None:
                updated.append(replacement)
            continue
        updated.append(claim)
    updated.extend(additions)
    updated = _sorted_claims(updated)

    deduped: list[Claim] = []
    seen: set[tuple[int, int, str, str]] = set()
    for claim in updated:
        sig = _claim_signature(claim)
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(claim)

    is_valid, reason = _validate_claim_list_reason(paragraph, deduped)
    if not is_valid:
        return None, reason
    return deduped, None


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _parse_tool_operation(raw_result: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    operation = payload.get("operation")
    return operation if isinstance(operation, dict) else None


def _run_tool_calls(
    manager: RegexMCPManager,
    tool_calls: list[dict[str, Any]],
    claims: list[Claim],
    paragraph: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_args = {
        "paragraph": paragraph,
        "claims_json": _claims_to_json(claims),
    }
    can_parallel = _can_parallelize_tool_calls(tool_calls, claims, paragraph)
    results: list[dict[str, Any]] = []

    def _execute(tool_call: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(tool_call.get("name", ""))
        tool_args = dict(base_args)
        tool_args.update(tool_call.get("arguments", {}) or {})
        ok, raw_result = manager.call_tool_safe(tool_name, tool_args)
        return {
            "tool": tool_name,
            "arguments": tool_args,
            "ok": ok,
            "raw_result": raw_result,
            "operation": _parse_tool_operation(raw_result) if ok else None,
        }

    if can_parallel:
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
            futures = [pool.submit(_execute, tc) for tc in tool_calls]
            for future in futures:
                results.append(future.result())
    else:
        for tc in tool_calls:
            results.append(_execute(tc))

    operations = [
        result["operation"]
        for result in results
        if isinstance(result.get("operation"), dict)
    ]
    return operations, results
