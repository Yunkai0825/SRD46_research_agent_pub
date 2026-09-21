"""
Tool call parsing utilities  (tool_call_parser.py)
====================================================
Parses LLM responses for ``<tool_call>`` blocks in both JSON and Python
function-call syntax.  Called by ``react_loop.agent_turn()`` after each
LLM response to extract tool invocations.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from ...general_text_context_marker_catalog import MARKERS

log = logging.getLogger("NISTsrd46-UI")

# ─── Regex patterns (imported from general_text_context_marker_catalog) ──
_TOOL_CALL_RE = MARKERS.tool_call_re
_ANY_TOOL_CALL_RE = MARKERS.any_tool_call_re
_WAIT_TAG_RE = MARKERS.wait_re
_BARE_TOOL_CALL_RE = MARKERS.bare_tool_call_re


# ─── Parsers ─────────────────────────────────────────────────

def _parse_python_call(text: str) -> Optional[dict]:
    """Parse Python function-call syntax like name(arg=val, ...) into a tool call dict.

    Handles: query_blocks(compounds=["ethanol"], properties=["viscosity"])
    Returns: {"name": "query_blocks", "arguments": {"compounds": ["ethanol"], ...}}

    Lenient mode: if a keyword's value is not a literal (e.g. bare ``Name``
    like ``path=enumerate`` or ``Call`` like ``name=iron(II)``), the value
    is coerced to its source-text string form via ``ast.unparse``.  This
    matches the compact memory-render format the agent itself sees in
    prior turns (see ``compact_tool_calls_for_memory``), so the model can
    safely imitate it without breaking parsing.
    """
    text = text.strip()
    if not text or text.startswith("{"):
        return None  # Already JSON, skip
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        log.debug("Failed to parse Python-style tool call %r: %s", text[:120], exc)
        return None
    if not isinstance(tree.body, ast.Call):
        return None
    call = tree.body
    if not isinstance(call.func, ast.Name):
        return None
    name = call.func.id
    args: dict = {}
    for kw in call.keywords:
        if kw.arg is None:
            continue
        try:
            args[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, TypeError):
            # Lenient fallback — bareword Name, Call, or other
            # non-literal node: keep its source text as a string.
            try:
                args[kw.arg] = ast.unparse(kw.value)
            except Exception as exc:
                log.debug(
                    "Failed to coerce keyword %r in tool call %r: %s",
                    kw.arg, text[:120], exc,
                )
                args[kw.arg] = ""
    return {"name": name, "arguments": args}


def _wrap_top_level_arguments(obj: dict) -> dict:
    """Fold stray top-level parameters into ``arguments``.

    LLMs sometimes emit ``{"name": "tool", "param": ...}`` instead of
    ``{"name": "tool", "arguments": {"param": ...}}``.  The intent is
    unambiguous, so normalize it (logged loudly, never silently).
    """
    extras = {k: v for k, v in obj.items() if k not in ("name", "arguments")}
    if not extras:
        return obj
    arguments = obj.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    merged = {**extras, **arguments}
    log.info(
        "Tool call %r: folded stray top-level parameter(s) %s into 'arguments'",
        obj.get("name"), sorted(extras),
    )
    return {"name": obj["name"], "arguments": merged}


def _try_parse_tool_block(content: str) -> tuple[Optional[dict], Optional[str]]:
    """Try JSON first, then Python function-call syntax.

    Tolerates trailing commas in JSON (common LLM output).  Returns
    ``(parsed, error_reason)`` — ``error_reason`` is a short actionable
    string when the block could not be parsed at all.
    """
    content = content.strip()
    json_error: Optional[str] = None
    # Attempt 1: JSON
    try:
        obj = json.loads(content)
        if isinstance(obj, dict) and "name" in obj:
            return _wrap_top_level_arguments(obj), None
    except json.JSONDecodeError:
        # Attempt 1b: strip trailing commas and retry
        cleaned = re.sub(r",\s*([}\]])", r"\1", content)
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict) and "name" in obj:
                return _wrap_top_level_arguments(obj), None
        except json.JSONDecodeError as exc:
            json_error = str(exc)
            # Attempt 1c: salvage a complete leading JSON object followed
            # by stray trailing text ("Extra data").  Loudly logged.
            try:
                obj, end = json.JSONDecoder().raw_decode(content)
                if isinstance(obj, dict) and "name" in obj:
                    log.info(
                        "Tool call %r: decoded leading JSON object, ignored "
                        "%d trailing character(s)",
                        obj.get("name"), len(content) - end,
                    )
                    return _wrap_top_level_arguments(obj), None
            except json.JSONDecodeError:
                pass
            log.debug("Failed to parse tool-call JSON block %r: %s", content[:120], exc)
    # Attempt 2: Python function-call syntax
    parsed = _parse_python_call(content)
    if parsed:
        log.debug("Parsed tool call from Python syntax: %s", parsed["name"])
        return parsed, None
    if json_error is not None:
        return None, f"invalid JSON ({json_error})"
    return None, "not a JSON object with a 'name' key and not a Python-style call"


# ─── Data structures ─────────────────────────────────────────

@dataclass
class ToolBatchResult:
    """Result of parsing tool calls from an LLM response."""
    calls: list[dict]
    wait_detected: bool = False
    deferred_count: int = 0  # tool calls after the <wait/> tag
    parse_errors: list[str] = field(default_factory=list)


# ─── Extractors ──────────────────────────────────────────────

def extract_tool_call(text: str) -> Optional[dict]:
    """Return the first <tool_call> block as a parsed dict, or None."""
    m = _ANY_TOOL_CALL_RE.search(text)
    if m:
        result, _err = _try_parse_tool_block(m.group(1))
        if result:
            return result
    m2 = _BARE_TOOL_CALL_RE.search(text)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            if "name" in obj and "arguments" in obj:
                return obj
        except json.JSONDecodeError as exc:
            log.debug("Failed to parse bare tool-call JSON %r: %s", m2.group(0)[:120], exc)
    return None


def extract_all_tool_calls(text: str) -> ToolBatchResult:
    """Return <tool_call> blocks as parsed dicts, stopping at ``<wait/>``.

    If the LLM emits a ``<wait/>`` tag between tool_call blocks, only
    the calls *before* the first ``<wait/>`` are returned.  This lets
    the LLM explicitly batch its calls — tools after ``<wait/>`` are
    discarded (the LLM will re-emit them with correct IDs on the next
    iteration after seeing results from the first batch).

    Supports both JSON format and Python function-call syntax inside <tool_call> tags.
    Returns a ToolBatchResult with the calls, wait flag, and deferred count.
    """
    # Find the <wait/> boundary (if any)
    wait_pos = _WAIT_TAG_RE.search(text)
    search_text = text[:wait_pos.start()] if wait_pos else text

    calls = []
    parse_errors: list[str] = []
    for i, m in enumerate(_ANY_TOOL_CALL_RE.finditer(search_text), 1):
        parsed, err = _try_parse_tool_block(m.group(1))
        if parsed:
            calls.append(parsed)
        elif err:
            preview = " ".join(m.group(1).strip()[:100].split())
            parse_errors.append(f"block {i} starting `{preview}…`: {err}")
    if not calls:
        single = extract_tool_call(search_text)
        if single:
            calls.append(single)

    # Count deferred calls (after the <wait/> tag)
    deferred_count = 0
    if wait_pos:
        after_wait = text[wait_pos.end():]
        deferred_count = len(_ANY_TOOL_CALL_RE.findall(after_wait))

    if wait_pos and calls:
        log.info("<wait/> detected — executing %d tools before barrier, "
                 "deferring %d to next iteration", len(calls), deferred_count)
    elif wait_pos and not calls:
        log.warning("<wait/> detected but NO tool calls before it — empty wait")

    return ToolBatchResult(
        calls=calls,
        wait_detected=bool(wait_pos),
        deferred_count=deferred_count,
        parse_errors=parse_errors,
    )
