"""Grounder ReAct loop with MCP grounding-patch tools.

Edits the *reference* fields of grounded claims only (canonical_ids,
support_class, evidence_snippet, tool_snippets). Claim text and
claim_type are immutable here — the classifier owns those.
"""
from __future__ import annotations

import asyncio as _asyncio
import importlib.util as _importlib_util
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..regex_support_helpers.models import Claim, GroundedClaim
from .claim_grounder import (
    _find_regex_mismatches,
    _grounded_to_payload,
    _model_candidates,
    _truncate_tool_context,
)

log = logging.getLogger("claim_grounder_react")

_GROUNDER_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\[.*?\]|\{.*?\})\s*</tool_call>", re.DOTALL
)
_GROUNDER_BARE_TOOL_CALL_RE = re.compile(
    r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}'
)
_GROUNDER_REACT_DEFAULT_ROUNDS = 1
_GROUNDER_REACT_MAX_ROUNDS = 3
_GROUNDER_REACT_DEFAULT_TURNS = 4
_GROUNDER_REACT_MAX_TURNS = 8
_GROUNDER_REACT_MAX_TOKENS = 6000
_GROUNDING_MCP_SERVER_PATH = Path(__file__).resolve().parent / "grounding_patch_server.py"
_GROUNDING_MCP_MODULE = None
_GROUNDING_TOOL_CATALOG: str | None = None

_GROUNDER_REACT_SYSTEM_PROMPT_TEMPLATE = """\
You are a grounding-reference editor for the SRD-46 claim pipeline.
Your job is to refine the GROUNDING REFERENCES of an already-classified
claim list for a single ORIGINAL SECTION. Use the provided MCP tools to
patch only the reference fields.

You MUST NOT change claim text or claim_type. Those are immutable here.
You may patch only:
  canonical_ids, support_class, evidence_snippet, tool_snippets

TOOL CALL FORMAT:
Emit either:
<tool_call>{{"name": "tool_name", "arguments": {{...}}}}</tool_call>
or
<tool_call>[{{"name": "tool_name", "arguments": {{...}}}}, {{"name": "tool_name", "arguments": {{...}}}}]</tool_call>

Multiple tool calls in one response are allowed only when the edits target
different claim_index values. If they target the same claim_index, emit them
one at a time across separate turns.

TOOLS:
{tool_catalog}

RULES:
- The TOOL RESULTS section is the only source of evidence.
- For `execute_srd46_sql` steps, the rendered table often has no task
  description or column legend. Read the `sql_query` text inside that
  step's `**Args:**` JSON to learn what each column means (SELECT list and
  aliases) and what conditions are already pinned for every row (WHERE
  clause, e.g. `s.constant_type = 'K'`). Use that to interpret rows before
  judging support, and when citing such a row prefer including the
  relevant SELECT/WHERE fragment in `evidence_snippet` if the column
  meaning would otherwise be ambiguous.
- Use set_support_class to demote a direct claim that has missing numeric
  evidence, or to escalate an unsupported claim that does have evidence.
- Use set_evidence to fix evidence_snippet or canonical_ids.
- Use replace_tool_snippets to attach the correct tool result rows.
- Use inspect_grounded_claims if you need a refreshed indexed view.
- Prefer minimal edits that resolve the regex findings.
- When the grounding is acceptable, answer with DONE and a short reason.
  Do not emit a tool call.
"""


def resolve_grounder_react_rounds(value: int | None = None) -> int:
    """Resolve and clamp the configured grounder ReAct edit-round budget."""
    if value is None:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import GROUNDER_REACT_ROUNDS  # type: ignore

            value = GROUNDER_REACT_ROUNDS
        except (ImportError, AttributeError):
            value = _GROUNDER_REACT_DEFAULT_ROUNDS
    try:
        rounds = int(value)
    except (TypeError, ValueError):
        rounds = _GROUNDER_REACT_DEFAULT_ROUNDS
    return max(0, min(rounds, _GROUNDER_REACT_MAX_ROUNDS))


def resolve_grounder_react_tool_turns(value: int | None = None) -> int:
    """Resolve and clamp the maximum MCP edit turns per ReAct round."""
    if value is None:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import GROUNDER_REACT_MAX_TOOL_ITERATIONS  # type: ignore

            value = GROUNDER_REACT_MAX_TOOL_ITERATIONS
        except (ImportError, AttributeError):
            value = _GROUNDER_REACT_DEFAULT_TURNS
    try:
        turns = int(value)
    except (TypeError, ValueError):
        turns = _GROUNDER_REACT_DEFAULT_TURNS
    return max(1, min(turns, _GROUNDER_REACT_MAX_TURNS))


def _load_grounding_mcp_module():
    global _GROUNDING_MCP_MODULE
    if _GROUNDING_MCP_MODULE is not None:
        return _GROUNDING_MCP_MODULE
    spec = _importlib_util.spec_from_file_location(
        "_grounding_patch_server", _GROUNDING_MCP_SERVER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load grounding MCP tools from {_GROUNDING_MCP_SERVER_PATH}"
        )
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _GROUNDING_MCP_MODULE = module
    return module


def _build_grounding_tool_catalog() -> str:
    global _GROUNDING_TOOL_CATALOG
    if _GROUNDING_TOOL_CATALOG is not None:
        return _GROUNDING_TOOL_CATALOG
    module = _load_grounding_mcp_module()
    tools = _asyncio.run(module.mcp.list_tools())
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
    _GROUNDING_TOOL_CATALOG = "\n".join(lines)
    return _GROUNDING_TOOL_CATALOG


class _GroundingMCPManager:
    """Small in-process tool manager for the grounding-patch MCP tools."""

    def __init__(self) -> None:
        self.module = _load_grounding_mcp_module()
        self.tool_index = {
            "inspect_grounded_claims": self.module.inspect_grounded_claims,
            "set_support_class": self.module.set_support_class,
            "set_evidence": self.module.set_evidence,
            "replace_tool_snippets": self.module.replace_tool_snippets,
        }

    def call_tool_safe(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        impl = self.tool_index.get(tool_name)
        if impl is None:
            return False, f"[TOOL ERROR] {tool_name}: tool not found"
        try:
            return True, impl(**args)
        except Exception as exc:
            return False, f"[TOOL ERROR] {tool_name}: {exc}"


def _extract_tool_call(text: str) -> Any | None:
    match = _GROUNDER_TOOL_CALL_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    bare = _GROUNDER_BARE_TOOL_CALL_RE.search(text)
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


def _claims_to_json_for_react(claims: list[Claim]) -> str:
    return json.dumps(
        [
            {
                "claim_index": idx,
                "text": claim.text,
                "claim_type": claim.claim_type,
            }
            for idx, claim in enumerate(claims)
        ],
        ensure_ascii=False,
    )


def _grounded_to_json_for_react(grounded: list[GroundedClaim]) -> str:
    return json.dumps(
        [_grounded_to_payload(item) for item in grounded],
        ensure_ascii=False,
    )


def _build_grounder_findings(
    claims: list[Claim],
    grounded: list[GroundedClaim],
    tool_eval_text: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    grounded_map = {item.claim_index: item for item in grounded}
    mismatches = _find_regex_mismatches(claims, grounded, tool_eval_text)
    for mismatch in mismatches:
        findings.append({
            "kind": "numeric_mismatch",
            "claim_index": int(mismatch["claim_index"]),
            "claim_text": mismatch["claim_text"],
            "missing_numeric_values": mismatch["missing_numeric_values"],
            "best_regex_candidates": mismatch.get("best_regex_candidates", []),
            "message": (
                "Cited evidence is missing numeric values present in the claim."
            ),
        })
    for idx, claim in enumerate(claims):
        ref = grounded_map.get(idx)
        if ref is None:
            continue
        if ref.support_class in ("direct", "inferred"):
            if not ref.evidence_snippet.strip() and not ref.tool_snippets:
                findings.append({
                    "kind": "missing_evidence",
                    "claim_index": idx,
                    "claim_text": claim.text,
                    "support_class": ref.support_class,
                    "message": (
                        "Claim is marked as supported but has no evidence_snippet or tool_snippets."
                    ),
                })
    return findings


def _build_grounder_react_prompt(
    paragraph: str,
    claims: list[Claim],
    grounded: list[GroundedClaim],
    findings: list[dict[str, Any]],
    tool_eval_text: str,
    *,
    round_index: int,
) -> str:
    claims_payload = json.dumps(
        [
            {
                "claim_index": idx,
                "text": claim.text,
                "claim_type": claim.claim_type,
            }
            for idx, claim in enumerate(claims)
        ],
        ensure_ascii=False,
        indent=2,
    )
    grounded_payload = json.dumps(
        [_grounded_to_payload(item) for item in grounded],
        ensure_ascii=False,
        indent=2,
    )
    findings_payload = json.dumps(findings, ensure_ascii=False, indent=2)
    truncated_tool_eval = _truncate_tool_context(tool_eval_text)
    return (
        f"Grounder ReAct round {round_index}. Regex cross-validation has already run.\n\n"
        "ORIGINAL SECTION:\n"
        "<<<ORIGINAL_SECTION\n"
        f"{paragraph}\n"
        ">>>ORIGINAL_SECTION\n\n"
        "CLAIMS (read-only — text and claim_type are immutable):\n"
        f"{claims_payload}\n\n"
        "CURRENT GROUNDED REFERENCES (mutable via MCP tools):\n"
        f"{grounded_payload}\n\n"
        "REGEX FINDINGS:\n"
        f"{findings_payload}\n\n"
        "TOOL RESULTS:\n"
        "<<<TOOL_RESULTS\n"
        f"{truncated_tool_eval}\n"
        ">>>TOOL_RESULTS\n\n"
        "If the grounding needs fixes, emit MCP tool calls to patch reference fields.\n"
        "If the grounding is acceptable, answer DONE with a short reason and no tool call.\n"
    )


def _can_parallelize_grounder_calls(tool_calls: list[dict[str, Any]]) -> bool:
    if len(tool_calls) < 2:
        return False
    write_calls = [tc for tc in tool_calls if tc.get("name") != "inspect_grounded_claims"]
    if len(write_calls) < 2:
        return False
    seen: set[int] = set()
    for tc in write_calls:
        args = tc.get("arguments", {}) or {}
        try:
            idx = int(args.get("claim_index", -1))
        except (TypeError, ValueError):
            return False
        if idx in seen:
            return False
        seen.add(idx)
    return True


def _parse_tool_operation(raw_result: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    operation = payload.get("operation")
    return operation if isinstance(operation, dict) else None


def _run_grounder_tool_calls(
    manager: _GroundingMCPManager,
    tool_calls: list[dict[str, Any]],
    claims: list[Claim],
    grounded: list[GroundedClaim],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_args = {
        "claims_json": _claims_to_json_for_react(claims),
        "grounded_json": _grounded_to_json_for_react(grounded),
    }
    can_parallel = _can_parallelize_grounder_calls(tool_calls)
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
        with _ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
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


def _clone_grounded(item: GroundedClaim) -> GroundedClaim:
    return GroundedClaim(
        claim_index=item.claim_index,
        canonical_ids=list(item.canonical_ids),
        support_class=item.support_class,
        evidence_snippet=item.evidence_snippet,
        tool_snippets=[dict(snippet) for snippet in item.tool_snippets],
    )


def _apply_grounder_operations(
    grounded: list[GroundedClaim],
    operations: list[dict[str, Any]],
) -> list[GroundedClaim] | None:
    by_index = {item.claim_index: _clone_grounded(item) for item in grounded}
    touched: set[int] = set()

    for op in operations:
        op_name = str(op.get("op", ""))
        try:
            claim_index = int(op["claim_index"])
        except (KeyError, TypeError, ValueError):
            return None
        if claim_index in touched:
            return None
        target = by_index.get(claim_index)
        if target is None:
            return None
        if op_name == "set_support_class":
            target.support_class = str(op["support_class"])
        elif op_name == "set_evidence":
            if "evidence_snippet" in op:
                target.evidence_snippet = str(op["evidence_snippet"])[:200]
            if "canonical_ids" in op:
                ids = op["canonical_ids"]
                if not isinstance(ids, list):
                    return None
                target.canonical_ids = [str(cid) for cid in ids]
        elif op_name == "replace_tool_snippets":
            snippets = op.get("tool_snippets", [])
            if not isinstance(snippets, list):
                return None
            target.tool_snippets = [dict(s) for s in snippets]
        else:
            return None
        touched.add(claim_index)

    return sorted(by_index.values(), key=lambda g: g.claim_index)


def _grounded_signature(grounded: list[GroundedClaim]) -> tuple:
    return tuple(
        (
            item.claim_index,
            item.support_class,
            tuple(item.canonical_ids),
            item.evidence_snippet,
            tuple(
                (s.get("step", ""), s.get("tool", ""), s.get("snippet", ""))
                for s in item.tool_snippets
            ),
        )
        for item in sorted(grounded, key=lambda g: g.claim_index)
    )


def _react_patch_grounded(
    paragraph: str,
    claims: list[Claim],
    grounded: list[GroundedClaim],
    tool_eval_text: str,
    *,
    call_argo_fn,
    model: str | None,
    max_rounds: int | None = None,
) -> list[GroundedClaim]:
    """Run a regex-first MCP ReAct loop that patches grounding references only."""
    rounds = resolve_grounder_react_rounds(max_rounds)
    if rounds <= 0 or not grounded or not tool_eval_text.strip():
        return grounded

    current = [_clone_grounded(item) for item in grounded]
    manager = _GroundingMCPManager()
    system_prompt = _GROUNDER_REACT_SYSTEM_PROMPT_TEMPLATE.format(
        tool_catalog=_build_grounding_tool_catalog()
    )
    max_turns = resolve_grounder_react_tool_turns()
    models_to_try = _model_candidates(model)

    for round_index in range(1, rounds + 1):
        findings = _build_grounder_findings(claims, current, tool_eval_text)
        if not findings:
            break

        turns_used = 0
        while turns_used < max_turns:
            prompt = _build_grounder_react_prompt(
                paragraph,
                claims,
                current,
                findings,
                tool_eval_text,
                round_index=round_index,
            )

            response: str | None = None
            last_err: Exception | None = None
            for candidate in models_to_try:
                try:
                    response = call_argo_fn(
                        prompt=prompt,
                        system=system_prompt,
                        stop=["</tool_call>"],
                        model=candidate,
                        max_tokens=_GROUNDER_REACT_MAX_TOKENS,
                    )
                    break
                except Exception as exc:
                    last_err = exc
                    log.warning("Argo grounder ReAct failed model=%s: %s", candidate, exc)
            if response is None:
                raise RuntimeError(
                    f"Grounder ReAct round {round_index} failed for all models "
                    f"{models_to_try}: {last_err}"
                ) from last_err

            tool_calls = _coerce_tool_calls(_extract_tool_call(response))
            if not tool_calls:
                break

            operations, _results = _run_grounder_tool_calls(
                manager, tool_calls, claims, current
            )
            turns_used += 1
            if not operations:
                log.info(
                    "Grounder ReAct round %d produced no applicable operations",
                    round_index,
                )
                break

            updated = _apply_grounder_operations(current, operations)
            if updated is None:
                log.info(
                    "Grounder ReAct round %d rejected an invalid patch batch",
                    round_index,
                )
                break

            if _grounded_signature(updated) == _grounded_signature(current):
                break

            current = updated
            findings = _build_grounder_findings(claims, current, tool_eval_text)
            if not findings:
                break

        if not _build_grounder_findings(claims, current, tool_eval_text):
            break

    return current
