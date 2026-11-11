"""
ReAct loop — synchronous ``agent_turn()`` implementation.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import time
from typing import Callable, Dict, List, Optional

from ..engine_config import get_config
from ..argo_client_caller import ArgoClient
from ..engine_tool_interface_helpers.tool_call_parser import extract_all_tool_calls
from .react_helpers import (
    _bind_positional_args,
    _normalize_args,
    truncate_result,
    AgentTurnResult,
    _get_compaction_trigger_chars,
)
from ..engine_hooks_anchors import anchor as _anchor, EngineHooks, AGENT_RECORD_REFERENCES as _AGENT_RECORD_REFERENCES

from ...general_hooks_management_helpers.general_context_hooks.context_cleanup_compactor_hooks import (
    SUMMARY_BLOCK_RE as _SUMMARY_BLOCK_RE,
)
from ...general_hooks_management_helpers.general_context_hooks import _context_hooks_anchors_catalog as ctx_anchor
from ...general_hooks_management_helpers.general_context_hooks import history_tracking_hooks as _hr_mod
from ...general_hooks_management_helpers.general_memory_management_tools_hooks_helpers import _memory_hooks_anchors_catalog as mem_anchor
from ...general_tool_management_helpers import _tool_hooks_anchors_catalog as tool_anchor
from ...general_text_context_marker_catalog import MARKERS, ALL_CONTEXT_MARKERS_RE as _ALL_MARKERS_RE
from ...general_first_principle_API_call_reconstruct.runtime import (
    agent_scope as _reconstruction_agent_scope,
    clock as _reconstruction_time,
)

TAG_TOOL_CALL_OPEN = MARKERS.tool_call.open
TAG_TOOL_RESULT_OPEN = MARKERS.tool_result.open
TAG_TOOL_RESULT_CLOSE = MARKERS.tool_result.close
TAG_SUMMARY_OPEN = MARKERS.summary.open
TAG_SUMMARY_CLOSE = MARKERS.summary.close
TAG_COMPACT_NOTE_OPEN = MARKERS.compact_note.open
TAG_COMPACT_NOTE_CLOSE = MARKERS.compact_note.close
TAG_COMPACTION_REMINDER_OPEN = MARKERS.compaction_reminder.open
TAG_WAIT = MARKERS.wait_tag
TAG_SYSTEM_PROMPT_OPEN = MARKERS.system_prompt.open
TAG_SYSTEM_PROMPT_CLOSE = MARKERS.system_prompt.close
TAG_ANSWER_OPEN = MARKERS.answer.open
TAG_ANSWER_CLOSE = MARKERS.answer.close
TAG_MEMORY_OPEN = MARKERS.memory.open
TAG_MEMORY_CLOSE = MARKERS.memory.close
_COMPACT_NOTE_RE = MARKERS.compact_note_re
_COMPRESS_TAG_RE = MARKERS.compress_re
TAG_VALIDATION_OPEN = MARKERS.validation_guidance.open
TAG_VALIDATION_CLOSE = MARKERS.validation_guidance.close
_VALIDATION_GUIDANCE_RE = MARKERS.validation_guidance_re

# Regex that strips full <reasoning>…</reasoning> blocks (with content)
_REASONING_BLOCK_RE = MARKERS.reasoning_strip_re
# Regex that strips full <summary>…</summary> blocks (with content)
_SUMMARY_STRIP_RE = re.compile(r"<summary>.*?</summary>\s*", re.DOTALL)


def _clean_answer_text(raw: str) -> str:
    """Strip reasoning/summary blocks and leftover marker tags from a final answer."""
    text = _REASONING_BLOCK_RE.sub("", raw)
    text = _SUMMARY_STRIP_RE.sub("", text)
    text = _ALL_MARKERS_RE.sub("", text)
    return text.strip()


def _decode_leading_json(text: str):
    """Decode one leading JSON value while allowing a text appendix.

    Some tools intentionally return a machine-readable status object followed
    by Markdown evidence.  ``json.loads`` rejects that valid envelope with an
    ``Extra data`` error; ``raw_decode`` gives reference tracking the leading
    object without pretending that the trailing prose is JSON.
    """

    stripped = text.lstrip()
    value, end = json.JSONDecoder().raw_decode(stripped)
    return value, stripped[end:]


def _successful_tool_names(tool_history: list[dict]) -> set[str]:
    """Return tools whose recorded result was not an execution/rejection error."""

    successful: set[str] = set()
    for entry in tool_history:
        name = str(entry.get("tool") or "")
        result = str(entry.get("result_full") or "").lstrip()
        lowered = result.lower()
        if not name:
            continue
        if lowered.startswith("error:") or lowered.startswith('{"error"'):
            continue
        if lowered.startswith("[validation "):
            continue
        successful.add(name)
    return successful


def _strict_successful_tool_names(history: list[dict]) -> set[str]:
    """Recognise recorded terminal decisions without accepting JSON errors."""
    names = set()
    for entry in history:
        legacy = _successful_tool_names([entry])
        if not legacy:
            continue
        text = str(entry.get("result_full", "")).strip()
        try:
            payload, _appendix = _decode_leading_json(text)
        except (ValueError, TypeError):
            if text.startswith(("{", "[")):
                continue
            payload = None
        if isinstance(payload, dict) and (
            payload.get("error")
            or payload.get("ok") is False
            or payload.get("success") is False
            or str(payload.get("status", "")).lower() in {"error", "invalid", "failed", "failure"}
        ):
            continue
        names.update(legacy)
    return names


def _clean_validation_traces(memory: list[dict]) -> None:
    """Replace old ``<validation_guidance>`` blocks with a compact note,
    and collapse the matching prior assistant ``<tool_call>`` lines into a
    single stub.

    Scans user-role messages for ``<validation_guidance>…</validation_guidance>``
    tags.  Extracts the blocked tool names, then replaces the verbose guidance
    body with a one-liner noting which tools were blocked.

    For each compacted user message, also rewrites the immediately-preceding
    assistant message: any ``<tool_call>…</tool_call>`` blocks (which the
    LLM emitted but were rejected by validation) are collapsed to a single
    ``(failed tool calls — corrected next turn)`` stub line, while any
    ``<summary>`` and other narrative are preserved.

    This keeps context lean when the agent eventually fixes params: each
    rejected attempt costs ~1 line on the assistant side and ~1 line on
    the user side, instead of accumulating verbose tool_call XML + the
    full validation report on every retry.
    """
    _tool_call_block_re = re.compile(
        re.escape(MARKERS.tool_call.open) + r".*?" + re.escape(MARKERS.tool_call.close),
        re.DOTALL,
    )

    for i, msg in enumerate(memory):
        if msg["role"] != "user":
            continue
        content = msg["content"]
        if TAG_VALIDATION_OPEN not in content:
            continue

        def _compact_match(m: re.Match) -> str:
            body = m.group(0)
            # Strip the wrapper tags to get the guidance body
            body = body.replace(TAG_VALIDATION_OPEN, "").replace(TAG_VALIDATION_CLOSE, "")
            blocked = [
                line.split("**")[1].split("\u2717 ")[-1].strip()
                for line in body.split("\n")
                if "\u2717 " in line
            ]
            if blocked:
                names = ", ".join(blocked)
                return f"(validation blocked {names} earlier — corrected)"
            return "(validation fired earlier — corrected)"

        new_content = _VALIDATION_GUIDANCE_RE.sub(_compact_match, content)
        if new_content == content:
            continue
        msg["content"] = new_content

        # Collapse the matching prior assistant message's tool_call blocks.
        if i == 0:
            continue
        prev = memory[i - 1]
        if prev.get("role") != "assistant":
            continue
        prev_content = prev.get("content", "")
        if MARKERS.tool_call.open not in prev_content:
            continue
        n_calls = len(_tool_call_block_re.findall(prev_content))
        if n_calls == 0:
            continue
        stub = f"{MARKERS.tool_call.open}(failed {n_calls} tool call(s) — corrected next turn){MARKERS.tool_call.close}"
        prev["content"] = _tool_call_block_re.sub(stub, prev_content, count=1)
        # Drop any additional tool_call blocks beyond the first stub.
        prev["content"] = _tool_call_block_re.sub("", prev["content"]).strip()

log = logging.getLogger("NISTsrd46-UI")

# An empty model reply that reaches the loop is one the model itself produced
# (the client raises block envelopes and retries HTTP errors): the loop
# re-asks this many times, with this backoff, each time with a host notice
# appended to the prompt that names what the turn needs, before failing the
# turn.  From the second re-ask on the notice also reminds the model what
# the turn is gated on (its terminal and required tools not yet called, with
# a call skeleton each).  The engine config overrides the count through the
# field named below when it defines one.
MAX_EMPTY_MODEL_REPLIES = 4
EMPTY_REPLY_REASKS_CONFIG_FIELD = "EMPTY_REPLY_REASKS"
# A final answer stopped at the provider's output limit is continued this
# many times at most; the parts are joined into one answer.
MAX_ANSWER_CONTINUATIONS = 2
# A continuation that does not open with the requested excerpt is sent back
# this many times in all (per answer) before it is appended as is.
MAX_ANSWER_JOIN_REASKS = 2
ANSWER_CUT_NOTICE_TAG = "[ANSWER CUT OFF]"
ANSWER_JOIN_NOTICE_TAG = "[ANSWER JOIN FAILED]"
# The excerpt: about this many characters from the end of the answer so far,
# whole words, whitespace collapsed.
_ANSWER_EXCERPT_CHARS = 80
# The continuation must show at least the excerpt's last this-many words
# within its first _ANSWER_EXCERPT_SEARCH_CHARS characters.
_ANSWER_EXCERPT_MIN_WORDS = 4
_ANSWER_EXCERPT_SEARCH_CHARS = 300
EMPTY_MODEL_REPLY_BACKOFF_S = 1.0
EMPTY_REPLY_NOTICE_TAG = "[EMPTY REPLY]"
# A reply that reached the provider's output limit inside an incomplete
# tool call (the client's ``last_reply_unclosed`` record), a reply the
# provider stopped with a refusal (``last_reply_refused``), and a reply
# that wrote its tool call in a format the host does not read are each
# re-asked the same way, counted on their own against the same limit,
# with their own notice; none of them is recorded.
CUT_REPLY_NOTICE_TAG = "[REPLY CUT OFF]"
STOPPED_REPLY_NOTICE_TAG = "[REPLY STOPPED]"
TOOL_CALL_FORMAT_NOTICE_TAG = "[TOOL CALL FORMAT]"
# An ``<invoke name="...">`` element (optionally namespaced) written as
# the reply's tool call.
_FOREIGN_INVOKE_RE = re.compile(r'<(?:[A-Za-z_][\w.-]*:)?invoke\s+name\s*=\s*"([^"]+)"')

# A prose reply that ends the turn before ANY tool call while the caller
# names ``required_tools`` is sent back up to ``required_tools_reask`` times
# when the caller opts in. Each re-ask carries this notice. Prose is
# accepted with the soft-contract note after the re-asks.
NO_TOOL_CALL_NOTICE_TAG = "[NO TOOL CALLED]"


_CALL_VALUE_PLACEHOLDER = "<value>"


def _tool_call_skeleton(name: str, fn: Optional[Callable]) -> Optional[str]:
    """``<tool_call>{"name": ..., "arguments": {<param>: <value>, ...}}</tool_call>``
    built from ``fn``'s named parameters, or None when they cannot be read.

    The placeholder is not valid JSON on purpose: a copied skeleton fails
    to parse instead of running the tool with made-up arguments."""
    if fn is None:
        return None
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return None
    named = [
        p.name for p in params
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.name != "self"
    ]
    if not named and any(p.kind == p.VAR_KEYWORD for p in params):
        return None
    arguments = ", ".join(f'"{p}": {_CALL_VALUE_PLACEHOLDER}' for p in named)
    return (
        f'{MARKERS.tool_call.open}{{"name": "{name}", "arguments": {{{arguments}}}}}'
        f"{MARKERS.tool_call.close}"
    )


def _no_tool_call_notice(
    *,
    attempt: int,
    limit: int,
    required: list[str],
    tool_names: list[str],
    example_call: Optional[str] = None,
) -> str:
    """Host turn appended after a prose reply that called no tool.

    ``example_call`` is a skeleton of one expected call
    (``_tool_call_skeleton``); without it a generic one is shown."""
    call = example_call or (
        f'{MARKERS.tool_call.open}{{"name": "<tool>", "arguments": {{...}}}}'
        f"{MARKERS.tool_call.close}"
    )
    arguments_line = (
        '- "name" is the tool\'s name as listed. "arguments" is a JSON object '
        "keyed by the tool's parameter names, with valid JSON values"
    )
    if _CALL_VALUE_PLACEHOLDER in call:
        arguments_line += f"; replace each {_CALL_VALUE_PLACEHOLDER} with your own"
    return "\n".join([
        f"{NO_TOOL_CALL_NOTICE_TAG} Your reply ended this turn without calling "
        f"any tool (re-ask {attempt} of {limit}).",
        "The tools listed in your system prompt are available in this session; "
        "nothing has to be enabled.",
        "How tool calls work here: the host runs a tool only when your reply "
        "itself contains the call. Writing that you will call a tool, or "
        "describing the call, runs nothing: the turn ends with your reply, and "
        "no later turn comes unless the reply calls a tool. So make the call "
        "in this reply, after your summary:",
        call,
        MARKERS.wait_tag,
        arguments_line + ".",
        f"- To call several tools, write one {MARKERS.tool_call.open}…"
        f"{MARKERS.tool_call.close} per call, then a single {MARKERS.wait_tag}. "
        f"Text after {MARKERS.wait_tag} is not read.",
        "- The results come back in the next message, and you continue from there.",
        "Expected for this task: " + ", ".join(required) + ".",
        "Tools you can call now: " + ", ".join(tool_names) + ".",
        "Either call the tool(s) the task needs now, or, if you decline the "
        "task on its merits, give your final answer as plain text and state "
        "the reason; do not state that the tools are unavailable.",
    ])



def _empty_reply_notice(
    *,
    attempt: int,
    limit: int,
    usage: dict | None,
    tool_names: list[str],
    missing_terminal: list[str],
    gated: list[tuple[str, Optional[str]]] | None = None,
) -> str:
    """Host notice appended to the prompt after a reply without text.

    The first re-ask names the format.  Later re-asks add that unwritten
    reasoning is lost and, when ``gated`` names the tools the turn still
    needs, a reminder of those calls with a skeleton each; the agent keeps
    the choice of exploring first."""
    produced = ""
    if usage and usage.get("completion_tokens") is not None:
        produced = f" The provider counted {usage['completion_tokens']} completion tokens"
        if usage.get("reasoning_tokens") is not None:
            produced += f", {usage['reasoning_tokens']} of them reasoning"
        produced += ", none of them visible text."
    if attempt <= 1:
        first = (
            f"{EMPTY_REPLY_NOTICE_TAG} Your last reply contained no text "
            f"(re-ask {attempt} of {limit}).{produced} Nothing was recorded; "
            "the conversation above is unchanged."
        )
    else:
        first = (
            f"{EMPTY_REPLY_NOTICE_TAG} Your last reply again contained no text "
            f"(re-ask {attempt} of {limit}). It was not recorded; the "
            "conversation above is unchanged. Only the text you write out "
            "reaches the host; reasoning that is not written out is lost."
        )
    lines = [
        first,
        "Write your reply as visible text in the format your system prompt "
        f"specifies: reasoning inside {MARKERS.reasoning.open}…{MARKERS.reasoning.close}, "
        + (
            f"then tool calls inside {MARKERS.tool_call.open}…{MARKERS.tool_call.close} "
            f"followed by {MARKERS.wait_tag}."
            if missing_terminal else
            f"then either tool calls inside {MARKERS.tool_call.open}…{MARKERS.tool_call.close} "
            f"followed by {MARKERS.wait_tag}, or your final answer as plain text."
        ),
    ]
    reminder = _gated_reminder_lines(gated) if attempt > 1 else []
    # The reminder names the terminal tools itself; the terminal sentence of
    # the tool lines would repeat it.
    return "\n".join(
        lines + reminder
        + _tool_lines(tool_names, [] if reminder else missing_terminal)
    )


def _gated_calls(
    tools: Dict[str, Callable],
    missing_terminal: list[str],
    required_tools: set[str] | None,
    successful: set[str],
) -> list[tuple[str, Optional[str]]]:
    """``(name, skeleton)`` for each tool this turn is gated on and has not
    called successfully yet: the missing terminal tools first, then the
    required tools; the skeleton is None when the signature cannot be read."""
    names = list(missing_terminal)
    for name in sorted(required_tools or ()):
        if name not in successful and name not in names:
            names.append(name)
    return [(name, _tool_call_skeleton(name, tools.get(name))) for name in names]


def _gated_reminder_lines(gated: list[tuple[str, Optional[str]]] | None) -> list[str]:
    """The soft reminder of what the turn still needs, with one call
    skeleton per gated tool; empty when nothing is gated."""
    if not gated:
        return []
    names = ", ".join(name for name, _ in gated)
    ending = (
        "that call has succeeded. Its shape:" if len(gated) == 1
        else "those calls have succeeded. Their shapes:"
    )
    lines = [
        f"To succeed, this turn still needs a successful call of: {names}. "
        "You may inspect, read or explore first; the turn is complete only "
        f"once {ending}"
    ]
    for name, skeleton in gated:
        lines.append(skeleton or (
            f'{MARKERS.tool_call.open}{{"name": "{name}", "arguments": {{...}}}}'
            f"{MARKERS.tool_call.close}"
        ))
    lines.append(MARKERS.wait_tag)
    closing = (
        f"Replace each {_CALL_VALUE_PLACEHOLDER} with your own. "
        if any(_CALL_VALUE_PLACEHOLDER in (skeleton or "") for _, skeleton in gated)
        else ""
    )
    lines.append(
        closing + "If you decline the task on its merits, say so in one "
        "sentence as plain text with the reason."
    )
    return lines


def empty_reply_reask_limit(cfg) -> int:
    """How many times a reply without text is re-asked: the engine config's
    ``EMPTY_REPLY_REASKS`` when it defines a usable one, else
    ``MAX_EMPTY_MODEL_REPLIES``."""
    value = getattr(cfg, EMPTY_REPLY_REASKS_CONFIG_FIELD, None)
    if value is None or isinstance(value, bool):
        return MAX_EMPTY_MODEL_REPLIES
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return MAX_EMPTY_MODEL_REPLIES


class EmptyRepliesExhausted(RuntimeError):
    """The turn ended because every re-ask of a reply without text came
    back without text again: the model produced nothing, no agent decided."""


def _tool_lines(tool_names: list[str], missing_terminal: list[str]) -> list[str]:
    """The callable tools and the terminal tools a re-ask notice names."""
    lines = []
    if tool_names:
        lines.append("Tools you can call now: " + ", ".join(tool_names) + ".")
    if missing_terminal:
        lines.append(
            "This turn ends only with a successful call of one of: "
            + ", ".join(missing_terminal)
            + "; plain text is not accepted as the final answer."
        )
    return lines


def _limit_empty_reply_notice(
    *,
    attempt: int,
    limit: int,
    max_tokens,
    tool_names: list[str],
    missing_terminal: list[str],
) -> str:
    """Host notice appended to the prompt after a reply that spent the
    provider's output limit before writing any text."""
    cap = f" ({max_tokens} tokens)" if max_tokens is not None else ""
    lines = [
        f"{CUT_REPLY_NOTICE_TAG} Your previous reply reached the output limit"
        f"{cap} before any of it was written out, so nothing was executed "
        f"(re-ask {attempt} of {limit}). The reply was not recorded; the "
        "conversation above is unchanged. Keep this reply short and send "
        "your next step now.",
    ]
    return "\n".join(lines + _tool_lines(tool_names, missing_terminal))


def _cut_reply(client) -> dict | None:
    """The client's record of a reply cut inside a tool call, else None."""
    record = getattr(client, "last_reply_unclosed", None)
    return record if isinstance(record, dict) else None


def _stopped_reply(client) -> dict | None:
    """The client's record of a reply the provider refused, else None."""
    record = getattr(client, "last_reply_refused", None)
    return record if isinstance(record, dict) else None


def _foreign_tool_call(response: str) -> str | None:
    """Tool name of an ``<invoke name=...>`` call in a reply that has no
    ``<tool_call>`` block outside reasoning, else None."""
    visible = _REASONING_BLOCK_RE.sub("", str(response or ""))
    if MARKERS.tool_call.open in visible:
        return None
    match = _FOREIGN_INVOKE_RE.search(visible)
    return match.group(1) if match else None


def _cut_reply_notice(
    *, attempt: int, limit: int, raw_chars, max_tokens=None,
) -> str:
    """Host notice appended to the prompt after a reply that reached the
    provider's output limit inside an unclosed tool-call block."""
    cap = f" ({max_tokens} tokens)" if max_tokens is not None else ""
    length = f" after {raw_chars} characters" if raw_chars is not None else ""
    return (
        f"{CUT_REPLY_NOTICE_TAG} Your previous reply reached the output limit"
        f"{cap} inside a {MARKERS.tool_call.open} block{length}, so nothing "
        f"was executed (re-ask {attempt} of {limit}). The incomplete reply was "
        "not recorded; the conversation above is unchanged. Re-send the "
        "complete call with shorter reasoning and text arguments; close it "
        f"with {MARKERS.tool_call.close} and add {MARKERS.wait_tag} on its own line."
    )


def _stopped_reply_notice(
    *, attempt: int, limit: int, stop_reason, raw_chars,
) -> str:
    """Host notice appended to the prompt after a reply the provider
    stopped with a refusal or content-filter stop reason."""
    reason = f" (stop reason: {stop_reason})" if stop_reason else ""
    length = f" after {raw_chars} characters" if raw_chars is not None else ""
    return (
        f"{STOPPED_REPLY_NOTICE_TAG} The provider stopped your previous reply"
        f"{reason}{length}, so nothing in it was executed (re-ask {attempt} of "
        f"{limit}). The reply was not recorded; the conversation above is "
        "unchanged. Send your reply again."
    )


def _tool_call_format_notice(*, attempt: int, limit: int, tool_name: str) -> str:
    """Host notice appended to the prompt after a reply that wrote its
    tool call as an ``<invoke>`` element."""
    return (
        f"{TOOL_CALL_FORMAT_NOTICE_TAG} Your previous reply wrote a tool call as "
        f'<invoke name="{tool_name}">…</invoke>, a format this host does not '
        f"read, so nothing was executed (re-ask {attempt} of {limit}). The reply "
        "was not recorded; the conversation above is unchanged. Write each call "
        f'as {MARKERS.tool_call.open}{{"name": "{tool_name}", "arguments": '
        f'{{...}}}}{MARKERS.tool_call.close} followed by {MARKERS.wait_tag}.'
    )


def _answer_excerpt(text: str) -> str:
    """The last words of ``text`` (about ``_ANSWER_EXCERPT_CHARS``
    characters, whitespace collapsed) that a continuation must repeat."""
    flat = " ".join(str(text).split())
    tail = flat[-_ANSWER_EXCERPT_CHARS:]
    if len(flat) > _ANSWER_EXCERPT_CHARS and " " in tail:
        tail = tail[tail.index(" ") + 1:]
    return tail


def _answer_cut_notice(
    *, attempt: int, limit: int, record: dict, chars: int, excerpt: str,
) -> str:
    """Host notice asking for the rest of a final answer the provider
    stopped at its output limit, opening with ``excerpt``."""
    cap = record.get("max_tokens")
    cap = f" ({cap} tokens)" if cap is not None else ""
    return (
        f"{ANSWER_CUT_NOTICE_TAG} Your answer above reached the output limit"
        f"{cap} after {chars} characters and stops mid-way. Its last words "
        f"are: “{excerpt}”. The host keeps that text. Continue the answer: "
        "begin your reply with that excerpt, copied exactly, then go straight "
        "on with the rest of the answer from its last character. The host "
        "joins the parts where the excerpt ends. Do not repeat anything else "
        "already written, and use no tool calls. Keep your reasoning short so "
        f"the rest fits (continuation {attempt} of {limit})."
    )


def _answer_join_notice(
    *, attempt: int, limit: int, excerpt: str, opening: str,
) -> str:
    """Host notice sending back a continuation that did not open with the
    requested excerpt."""
    return (
        f"{ANSWER_JOIN_NOTICE_TAG} Your continuation could not be joined to "
        f"your answer above: it did not begin with the excerpt “{excerpt}” "
        f"(it began: “{opening}”). That reply was not kept. Send the "
        "continuation again: begin with the excerpt, copied exactly, then the "
        "rest of the answer from its last character, with no tool calls "
        f"(join re-ask {attempt} of {limit})."
    )


def _glue_answer(head: str, part: str, excerpt: str) -> Optional[str]:
    """``head`` joined with ``part`` where ``part`` repeats ``excerpt`` (the
    end of ``head``), else None.

    Reasoning, summary and marker tags are removed from ``part`` first.
    The excerpt is matched with any whitespace between words and must
    start within the first ``_ANSWER_EXCERPT_SEARCH_CHARS`` characters;
    a copy that leaves out leading words still counts while it keeps at
    least ``_ANSWER_EXCERPT_MIN_WORDS`` (or all) of them.  What precedes
    the match is dropped and what follows it is appended to ``head``.
    """
    body = _clean_answer_text(part)
    words = excerpt.split()
    if not body or not words:
        return None
    window = body[:_ANSWER_EXCERPT_SEARCH_CHARS + len(excerpt)]
    fewest = min(len(words), _ANSWER_EXCERPT_MIN_WORDS)
    for first in range(0, len(words) - fewest + 1):
        pattern = r"\s+".join(re.escape(w) for w in words[first:])
        match = re.search(pattern, window)
        if match is not None and match.start() <= _ANSWER_EXCERPT_SEARCH_CHARS:
            return head + body[match.end():]
    return None


def _continue_cut_answer(client, prompt: str, system: str, response: str) -> str:
    """Continue a final answer the provider stopped at its output limit.

    The prompt that produced ``response`` is re-sent with the answer so far
    as the assistant turn and an [ANSWER CUT OFF] notice that names the
    excerpt the continuation must open with; the continuation is glued on
    where that excerpt ends.  A continuation without the excerpt is sent
    back with an [ANSWER JOIN FAILED] notice (at most
    ``MAX_ANSWER_JOIN_REASKS`` times per answer), then appended as is.
    Stops early on an empty, refused or tool-calling continuation, keeping
    what was joined.  Nothing here is recorded in memory.
    """
    joined = response
    record = getattr(client, "last_reply_limited", None)
    continuation = 0
    join_reasks = 0
    while isinstance(record, dict) and continuation < MAX_ANSWER_CONTINUATIONS:
        continuation += 1
        excerpt = _answer_excerpt(_clean_answer_text(joined))
        log.warning(
            "Final answer reached the output limit after %d chars; asking for "
            "continuation %d/%d", len(joined), continuation, MAX_ANSWER_CONTINUATIONS,
        )
        notice = _answer_cut_notice(
            attempt=continuation, limit=MAX_ANSWER_CONTINUATIONS, record=record,
            chars=len(joined), excerpt=excerpt,
        )
        while True:
            try:
                part = client.call(
                    f"{prompt}\n\n## Assistant\n{joined}\n\n## User\n{notice}", system,
                )
            except Exception as exc:
                log.error("Answer continuation call failed: %s", exc)
                return joined
            batch = extract_all_tool_calls(part or "")
            if (
                not _clean_answer_text(part or "")
                or batch.calls or batch.wait_detected
                or isinstance(getattr(client, "last_reply_refused", None), dict)
            ):
                log.warning(
                    "Answer continuation %d gave no usable text; keeping the "
                    "answer as joined so far (%d chars)", continuation, len(joined),
                )
                return joined
            glued = _glue_answer(joined, part, excerpt)
            if glued is not None:
                joined = glued
                break
            if join_reasks >= MAX_ANSWER_JOIN_REASKS:
                log.warning(
                    "Answer continuation %d still lacks the excerpt after %d "
                    "join re-asks; appending it as is", continuation, join_reasks,
                )
                joined = joined + "\n\n" + _clean_answer_text(part)
                break
            join_reasks += 1
            log.warning(
                "Answer continuation %d did not open with the excerpt; "
                "re-asking (%d/%d) with the %s notice", continuation,
                join_reasks, MAX_ANSWER_JOIN_REASKS, ANSWER_JOIN_NOTICE_TAG,
            )
            notice = _answer_join_notice(
                attempt=join_reasks, limit=MAX_ANSWER_JOIN_REASKS, excerpt=excerpt,
                opening=" ".join(_clean_answer_text(part).split())[:80],
            )
        record = getattr(client, "last_reply_limited", None)
    if isinstance(record, dict):
        log.warning(
            "Final answer still at the output limit after %d continuations "
            "(%d chars); keeping it as joined", MAX_ANSWER_CONTINUATIONS, len(joined),
        )
    return joined


def _reask_notice(
    client,
    response: str,
    counts: dict,
    *,
    tool_names: list[str],
    missing_terminal: list[str],
    limit: int = MAX_EMPTY_MODEL_REPLIES,
    gated: list[tuple[str, Optional[str]]] | None = None,
) -> tuple[str, int, str] | None:
    """``(tag, attempt, notice)`` for a reply the loop re-asks, else None.

    A refused reply (with or without text), a reply cut at the output
    limit inside a tool call, a reply whose tool call is an ``<invoke>``
    element, and an empty reply are each re-asked up to ``limit`` times,
    counted in ``counts`` per tag.  An empty reply that spent the output
    limit counts as a cut reply.  ``gated`` (see ``_gated_calls``) feeds
    the reminder the empty-reply notice carries from its second re-ask on.
    """
    has_text = bool(str(response or "").strip())

    def take(tag: str) -> int | None:
        if counts.get(tag, 0) >= limit:
            return None
        counts[tag] = counts.get(tag, 0) + 1
        return counts[tag]

    stopped = _stopped_reply(client)
    if stopped is not None:
        attempt = take(STOPPED_REPLY_NOTICE_TAG)
        if attempt is not None:
            return STOPPED_REPLY_NOTICE_TAG, attempt, _stopped_reply_notice(
                attempt=attempt, limit=limit,
                stop_reason=stopped.get("stop_reason"),
                raw_chars=stopped.get("raw_chars"),
            )
    if has_text:
        cut = _cut_reply(client)
        if cut is not None:
            attempt = take(CUT_REPLY_NOTICE_TAG)
            if attempt is not None:
                return CUT_REPLY_NOTICE_TAG, attempt, _cut_reply_notice(
                    attempt=attempt, limit=limit,
                    raw_chars=cut.get("raw_chars"), max_tokens=cut.get("max_tokens"),
                )
        foreign = _foreign_tool_call(response)
        if foreign is not None:
            attempt = take(TOOL_CALL_FORMAT_NOTICE_TAG)
            if attempt is not None:
                return TOOL_CALL_FORMAT_NOTICE_TAG, attempt, _tool_call_format_notice(
                    attempt=attempt, limit=limit, tool_name=foreign,
                )
        return None
    empty = getattr(client, "last_empty_reply", None)
    if isinstance(empty, dict) and empty.get("limit_reached"):
        attempt = take(CUT_REPLY_NOTICE_TAG)
        if attempt is None:
            return None
        return CUT_REPLY_NOTICE_TAG, attempt, _limit_empty_reply_notice(
            attempt=attempt, limit=limit, max_tokens=empty.get("max_tokens"),
            tool_names=tool_names, missing_terminal=missing_terminal,
        )
    attempt = take(EMPTY_REPLY_NOTICE_TAG)
    if attempt is None:
        return None
    return EMPTY_REPLY_NOTICE_TAG, attempt, _empty_reply_notice(
        attempt=attempt, limit=limit,
        usage=getattr(client, "last_empty_reply", None),
        tool_names=tool_names, missing_terminal=missing_terminal, gated=gated,
    )


def _empty_replies_error(iteration: int, counts: dict) -> EmptyRepliesExhausted:
    """The error that ends a turn whose re-asks all came back empty."""
    empty = counts.get(EMPTY_REPLY_NOTICE_TAG, 0)
    cut = counts.get(CUT_REPLY_NOTICE_TAG, 0)
    stopped = counts.get(STOPPED_REPLY_NOTICE_TAG, 0)
    parts = []
    if empty or not cut:
        parts.append(f"{empty} re-asked with the {EMPTY_REPLY_NOTICE_TAG} notice")
    if cut:
        verb = "with" if parts else "re-asked with"
        parts.append(f"{cut} {verb} the {CUT_REPLY_NOTICE_TAG} notice")
    if stopped:
        parts.append(f"{stopped} with the {STOPPED_REPLY_NOTICE_TAG} notice")
    return EmptyRepliesExhausted(
        f"the model returned {empty + cut + 1} consecutive empty replies "
        f"at iteration {iteration} ({', '.join(parts)}); stopping this turn "
        "(the model produced no text, not an agent decision)"
    )


# ═══════════════════════════════════════════════════════════════
#  Main ReAct loop
# ═══════════════════════════════════════════════════════════════

@_reconstruction_agent_scope
def agent_turn(
    user_message: str,
    *,
    system_prompt: str,
    tools: Dict[str, Callable],
    memory: List[dict],
    client: ArgoClient | None = None,
    max_iterations: int | None = None,
    timeout: int | None = None,
    required_tools: set[str] | None = None,
    required_tools_reask: int = 0,
    compaction_trigger_chars: int | None = None,
    compaction_interval: int | None = None,
    hooks: EngineHooks | None = None,
    is_subagent: bool = False,
    untimed_tools: set[str] | None = None,
    uncompacted_tools: set[str] | None = None,
    terminal_tools: set[str] | None = None,
    terminal_turn_budget: bool = False,
    tool_completion_check: Callable[[list[dict]], bool] | None = None,
    append_user_message: bool = True,
    initial_tool_history: list[dict] | None = None,
) -> AgentTurnResult:
    """Execute one user turn in the ReAct agentic loop.

    Parameters
    ----------
    user_message : str
        The user's question or instruction.
    system_prompt : str
        System message for the LLM.
    tools : dict[str, Callable]
        Tool registry mapping tool names to callables.
    memory : list[dict]
        Mutable conversation history (role/content dicts). Modified in place.
    client : ArgoClient, optional
        LLM caller. Defaults to ArgoClient.for_l0().
    max_iterations : int, optional
        Override MAX_TOOL_ITERATIONS.
    timeout : int, optional
        Override the effective-time reminder scale ``MAX_TURN_SECONDS``.
        This value injects progressive reminders; it is not a deadline.
    required_tools : set[str], optional
        Soft contract. If none of these tools was called, the final
        answer receives a host note naming the tools that were expected and
        not called; completion is not blocked. Use ``terminal_tools`` when a
        successful tool commit is mandatory.
    required_tools_reask : int, optional
        How many times a prose reply that ends the turn before ANY tool
        call is sent back with the ``[NO TOOL CALLED]`` notice while
        ``required_tools`` are named and none was called. After the re-asks,
        prose is accepted with the soft note; the default 0 disables
        re-asking.
    compaction_trigger_chars : int, optional
        Override the default context-size threshold that triggers
        compaction.  Defaults to ``_COMPACTION_TRIGGER_CHARS``.
    compaction_interval : int, optional
        If set, run the LLM compactor every N tool calls regardless of
        context size.  The compactor's selection step can still choose
        to skip ("NONE") if nothing needs compacting.
    hooks : EngineHooks, optional
        Compiled hook bindings keyed by catalog-defined anchor types.
    is_subagent : bool, optional
        When True, the first user message in the flat prompt uses
        ``## Subagent`` instead of ``## User``.  Set by subagent
        delegation tools to mark delegated queries.

    untimed_tools : set[str], optional
        Names of tools whose wall-clock execution time must NOT count
        against the turn's reminder scale.  After each such tool returns,
        its elapsed seconds are credited back to the
        :class:`TimeBudgetTracker` via the
        ``SYNC_TIME_BUDGET_CREDIT_TOOL`` anchor, so a long-running
        deterministic tool (e.g. a full build+solve pipeline) cannot
        fire spurious time reminders.  Defaults to
        ``None`` (no exclusion).
    uncompacted_tools : set[str], optional
        Exact tool names whose results must remain in the normal combined
        result when they appear in a parallel batch.  A batch containing
        any named tool bypasses both the optional batch-summary hook and
        the generic stage-compaction table.  Per-tool result handling and
        later whole-context compaction are unchanged.  Defaults to
        ``None`` (the existing stage-compaction behaviour).
    terminal_tools : set[str], optional
        Strict terminal-tool contract.  At least one named tool must execute
        successfully before a prose answer may end the turn.  Premature prose
        receives an actionable retry message, and the final iteration is
        reserved with an explicit terminal-tool reminder.  This is separate
        from the soft ``required_tools`` note.
    terminal_turn_budget : bool, optional
        Opt-in bounded decision protocol. Show i/N on the final five review
        turns (all turns when N <= 5) and,
        only if still needed, expose one additional terminal-only turn.
        Stop on a recorded terminal decision. Keep full context; do not make
        model compaction or final-summary calls outside this N+1 bound.
        Existing callers retain their original behaviour by default.
    append_user_message : bool, optional
        Append ``user_message`` to ``memory`` before the first model call.
        Set false only when restoring a checksummed conversation whose first
        user turn is already present in ``memory``.
    tool_completion_check : callable, optional
        Stage-owned completion predicate receiving the current tool batch's
        recorded receipts. After the batch and its memory/history hooks,
        return normally if the predicate confirms a validated stage result.
        This adds no turns, reminders, prose requirements or compaction calls.
        Defaults to None; other callers keep their existing completion rules.
    initial_tool_history : list[dict], optional
        Previously committed tool receipts accompanying restored ``memory``.
        This prevents a resumed turn from forgetting that a required or
        terminal tool already completed.

    Returns
    -------
    AgentTurnResult
        The final answer, iteration count, timing, and tool history.
    """
    # Auto-detect subagent mode: if user_message starts with [Purpose:],
    # it was delegated by a parent agent via subagent_delegation_tools.
    _is_subagent = is_subagent or user_message.startswith("[Purpose:")

    if client is None:
        client = ArgoClient.with_tier("L0")

    # Build an argo_fn wrapper for the compactor (injects call semantics)
    def _argo_fn(prompt, system, stop=None):
        return client.call(prompt, system, stop=stop or [])

    _cfg = get_config()
    _max_iter = max_iterations or _cfg.MAX_TOOL_ITERATIONS
    _timeout = timeout or _cfg.MAX_TURN_SECONDS
    _uncompacted_tools = frozenset(uncompacted_tools or ())
    _terminal_tools = frozenset(terminal_tools or ())
    if terminal_turn_budget and not _terminal_tools:
        raise ValueError("terminal_turn_budget requires terminal_tools")
    _success_names = _strict_successful_tool_names if terminal_turn_budget else _successful_tool_names
    _loop_limit = _max_iter + int(terminal_turn_budget)
    _no_tool_reasks = 0
    _reask_limit = empty_reply_reask_limit(_cfg)

    if append_user_message:
        memory.append({"role": "user", "content": user_message})
        _anchor(mem_anchor.SYNC_USER_MESSAGE_APPEND, hooks,
                iteration=0, content=user_message)
    elif not memory:
        raise ValueError(
            "append_user_message=False requires restored conversation memory"
        )
    t0 = _reconstruction_time(time.time)
    _time_tracker = _anchor(
        ctx_anchor.SYNC_TIME_BUDGET_TRACKER_CREATE,
        hooks,
        timeout=_timeout,
        thresholds=_cfg.WARN_THRESHOLDS,
        max_warnings=_cfg.MAX_WRAP_WARNINGS,
    )
    tool_history: list[dict] = list(initial_tool_history or [])
    consecutive_empty_waits = 0               # stuck-loop detector
    _MAX_EMPTY_WAITS = _cfg.MAX_EMPTY_WAITS     # break after N consecutive empty waits

    # Stage-compaction cache for parallel batches.
    # When a batch is stage-compacted, full results are cached here
    # so `inspect_batch_result` can retrieve them on demand.
    _batch_cache: dict[int, str] = {}
    _batch_cache_registered_iter: int = -1  # iteration when cache + tool were registered
    # Tool-result messages of batches that called inspect_batch_result,
    # keyed by their exact content -> the content to keep at cleanup (the
    # same batch's ordinary results; "" = drop the whole message).
    _inspect_payload_durable: dict[str, str] = {}
    _last_context: str = ""     # raw LLM input+output for the final turn

    for iteration in range(1, _loop_limit + 1):
        elapsed = _reconstruction_time(time.time) - t0
        _terminal_only_turn = terminal_turn_budget and iteration > _max_iter
        if terminal_turn_budget:
            if _terminal_only_turn:
                reminder = (
                    "[FINAL DECISION TURN] The review limit has been reached. "
                    "Only one terminal decision is allowed now: "
                    + ", ".join(sorted(_terminal_tools))
                    + ". Use the existing evidence. Do not inspect, search, "
                    "calculate, or create another preview. If you cannot commit, "
                    "use the documented rejection or genuine human-question tool."
                )
            elif iteration >= max(1, _max_iter - 4):
                reminder = f"[REVIEW TURN {iteration}/{_max_iter}] Complete the review and record a terminal decision within the review limit."
            else:
                reminder = None
            if reminder:
                memory.append({"role": "user", "content": reminder})

        # Reserve the last model turn for a required terminal commit.  This is
        # injected before prompt construction so an agent that spent earlier
        # turns inspecting data still sees a concrete recovery instruction.
        if (
            _terminal_tools and not terminal_turn_budget
            and iteration == _max_iter
            and not (_successful_tool_names(tool_history) & _terminal_tools)
        ):
            names = ", ".join(sorted(_terminal_tools))
            memory.append({
                "role": "user",
                "content": (
                    "[TERMINAL TOOL REQUIRED — FINAL TURN] You have not "
                    f"successfully committed with {names}. Call one of those "
                    "tools now, using its documented schema. Do not return a "
                    "prose answer and do not perform another inspection. If "
                    "you have no change to make, record that with the tool."
                ),
            })

        # ── Inspect cleanup: if batch cache is active but the last
        #    BATCH called no inspect_batch_result, discard cached
        #    details from memory and remove the temporary tool. ──
        # Guard: give the LLM at least one full iteration AFTER
        # registration to actually observe and use inspect_batch_result.
        # (Cache is registered at end of iter N — at start of iter N+1
        # the LLM has not yet been called with the new tool visible, so
        # cleanup must wait until iter N+2 at the earliest.)
        # The whole last batch is read, not only its last call: a batch
        # [inspect_batch_result, <terminal tool held back>] ends with the
        # terminal tool. Judging by it alone would discard the inspected
        # results and the held-back notice before the model sees them.
        if _batch_cache and tool_history and iteration > _batch_cache_registered_iter + 1:
            _last_iter = tool_history[-1].get("iteration")
            _last_batch_inspected = False
            for _h in reversed(tool_history):
                if _h.get("iteration") != _last_iter:
                    break
                if _h.get("tool") == "inspect_batch_result":
                    _last_batch_inspected = True
                    break
            if not _last_batch_inspected:
                # Remove the inspected details from memory; a message that
                # also carried ordinary results of the same batch keeps them.
                _cleaned_memory: list[dict] = []
                for m in memory:
                    _content = m.get("content", "")
                    if _content in _inspect_payload_durable:
                        _durable = _inspect_payload_durable[_content]
                        if _durable:
                            _cleaned_memory.append({**m, "content": _durable})
                        continue
                    if "### inspect_batch_result" in _content:
                        continue  # rewritten since recorded: discard the inspection payload
                    _cleaned_memory.append(m)
                memory[:] = _cleaned_memory
                _inspect_payload_durable.clear()
                _batch_cache.clear()
                _batch_cache_registered_iter = -1
                tools.pop("inspect_batch_result", None)
                log.info("Stage inspect cleanup: cache cleared, tool removed")
        # Effective-time reminders never stop the loop or suppress tools.

        # ── Effective-time reminder hooks ────────────────────────
        _anchor(
            ctx_anchor.SYNC_TIME_BUDGET_WARNINGS_APPLY,
            hooks,
            tracker=_time_tracker,
            elapsed=elapsed,
            memory=memory,
        )

        # ── Build flat prompt ───────────────────────────────
        flat_parts: list[str] = []

        # ── 🔗 Anchor: WORKING_MEMORY_RENDER ───────────────
        # Inject persistent working memory (outside memory list)
        wm_chars = 0
        wm = _anchor(mem_anchor.SYNC_WORKING_MEMORY_RENDER, hooks, iteration=iteration)
        if wm:
            wm_part = (
                f"## Working Memory\n"
                f"{TAG_MEMORY_OPEN}\n{wm}\n{TAG_MEMORY_CLOSE}"
            )
            flat_parts.append(wm_part)
            wm_chars = len(wm_part)

        # ── 🔗 Anchor: FLAT_PROMPT_BUILD ───────────────────
        # Append conversation memory — first user turn uses "Subagent"
        # header when this is a delegated subagent call.
        _first_user_seen = False
        user_chars = 0
        asst_chars = 0
        turn_details: list[str] = []
        for turn in memory:
            if turn["role"] == "user" and _is_subagent and not _first_user_seen:
                tag = "Subagent"
                _first_user_seen = True
            elif turn["role"] == "user":
                tag = "User"
            else:
                tag = "Assistant"
            part = f"## {tag}\n{turn['content']}"
            flat_parts.append(part)
            plen = len(part)
            if turn["role"] == "user":
                user_chars += plen
            else:
                asst_chars += plen
            turn_details.append(f"{tag[:1]}:{plen}")

        flat_prompt = "\n\n".join(flat_parts)
        _anchor(ctx_anchor.SYNC_FLAT_PROMPT_BUILD, hooks,
                iteration=iteration, prompt_chars=len(flat_prompt))

        # ── Context breakdown table ─────────────────────────
        log.info(
            "CTX turn=%d | system=%d wm=%d user=%d asst=%d "
            "total_prompt=%d | turns=[%s]",
            iteration, len(system_prompt), wm_chars,
            user_chars, asst_chars, len(flat_prompt),
            ", ".join(turn_details),
        )

        # ── 🔗 Anchor: LLM_CALL_BEFORE ─────────────────────
        _anchor(ctx_anchor.SYNC_LLM_CALL_BEFORE, hooks, iteration=iteration)

        # ── Call LLM ────────────────────────────────────────
        _tagged_system = (
            f"{TAG_SYSTEM_PROMPT_OPEN}\n{system_prompt}\n{TAG_SYSTEM_PROMPT_CLOSE}"
        )
        response = client.call(flat_prompt, _tagged_system)

        # An empty reply here is one the model itself produced: the client
        # raises a block envelope, retries HTTP errors, and hands on every
        # HTTP-200 envelope without text at once, with or without usage.
        # Re-sending the identical request can repeat an empty reply, so
        # re-ask a bounded number of times with memory
        # untouched and a host notice appended to the prompt that names the
        # required format, the callable tools and any terminal tool still
        # missing; then fail the turn with the reason.
        # A reply the provider refused, a reply cut at the output limit
        # inside an incomplete tool call, and a reply whose tool call is an
        # <invoke> element are re-asked the same way, each counted on its
        # own with its own notice: none is recorded or replayed, and the
        # re-asks spend no turn of the budget.  A reply still cut or still
        # malformed after its re-asks goes on to the handling below.
        _reasks: dict = {}
        _sent_prompt = flat_prompt
        while True:
            _successful_so_far = _success_names(tool_history)
            _missing_terminal = sorted(_terminal_tools - _successful_so_far)
            _reask = _reask_notice(
                client, response, _reasks,
                tool_names=sorted(tools),
                missing_terminal=_missing_terminal,
                limit=_reask_limit,
                gated=_gated_calls(
                    tools, _missing_terminal, required_tools, _successful_so_far),
            )
            if _reask is None:
                break
            _tag, _attempt, _notice = _reask
            log.warning(
                "Iter %d: model reply needs re-ask %d/%d; re-asking with the %s notice",
                iteration, _attempt, _reask_limit, _tag,
            )
            time.sleep(EMPTY_MODEL_REPLY_BACKOFF_S * _attempt)
            _sent_prompt = f"{flat_prompt}\n\n## User\n{_notice}"
            response = client.call(_sent_prompt, _tagged_system)
        if not str(response or "").strip():
            raise _empty_replies_error(iteration, _reasks)

        # ── 🔗 Anchor: LLM_RESPONSE_AFTER + ON_REASONING ───
        _anchor(ctx_anchor.SYNC_LLM_RESPONSE_AFTER, hooks, iteration, response)

        # Capture raw context as the LLM saw it
        _last_context = (
            f"## System Prompt\n{system_prompt}\n\n"
            f"{_sent_prompt}\n\n"
            f"## LLM Response\n{response}"
        )
        _last_context = _anchor(
            ctx_anchor.SYNC_FINAL_CONTEXT_CAPTURED,
            hooks,
            iteration=iteration,
            final_context=_last_context,
            response=response,
        ) or _last_context

        # ── Extract tool call(s) or final answer ────────────
        batch = extract_all_tool_calls(response)
        all_tool_calls = batch.calls
        _bind_positional_args(all_tool_calls, tools)

        # ── Empty-wait guard: LLM emitted <wait/> with no tools ──
        if batch.wait_detected and not all_tool_calls:
            memory.append({"role": "assistant", "content": response})
            if batch.parse_errors:
                # The model DID place tool calls before <wait/> — they were
                # malformed.  Tell it exactly what failed every time, not to
                # reorder; [WAIT LOOP BREAK] counts waits with no call at all.
                consecutive_empty_waits = 0
                detail = "; ".join(batch.parse_errors[:3])
                log.warning("Malformed tool call(s) before <wait/>: %s", detail[:300])
                memory.append({
                    "role": "user",
                    "content": (
                        f"[MALFORMED TOOL CALL] Your {TAG_TOOL_CALL_OPEN} block(s) "
                        f"before {TAG_WAIT} could not be parsed: {detail}. "
                        "Re-emit each call as exactly ONE JSON object of the form "
                        '{"name": "tool_name", "arguments": { ... }} — every '
                        "parameter INSIDE \"arguments\"; inside string values "
                        "escape newlines as \\n and double quotes as \\\"; no text "
                        "after the closing brace; never truncate with an ellipsis."
                    ),
                })
                continue
            consecutive_empty_waits += 1
            log.warning("Empty <wait/> #%d (no tool calls before barrier)",
                        consecutive_empty_waits)
            if consecutive_empty_waits >= _MAX_EMPTY_WAITS:
                memory.append({
                    "role": "user",
                    "content": (
                        f"[WAIT LOOP BREAK] You have emitted {TAG_WAIT} without "
                        "any tool calls %d times consecutively.  You MUST "
                        f"either emit concrete {TAG_TOOL_CALL_OPEN} blocks or provide "
                        "your final answer NOW."
                    ) % consecutive_empty_waits,
                })
                log.error("Empty-wait stuck loop — forcing answer after %d empty waits",
                          consecutive_empty_waits)
            else:
                memory.append({
                    "role": "user",
                    "content": (
                        f"[EMPTY WAIT] You emitted {TAG_WAIT} but no tool calls "
                        f"preceded it.  Place your {TAG_TOOL_CALL_OPEN} blocks BEFORE "
                        f"{TAG_WAIT}, not after.  Re-emit the tool calls you need."
                    ),
                })
            continue

        if not all_tool_calls:
            # ── Parse-failure guard ─────────────────────────
            # If the LLM emitted <tool_call> tags but none parsed,
            # don't silently treat the response as the final answer
            # (which would surface raw tag text to the user).
            # Re-prompt with a corrective message.
            if TAG_TOOL_CALL_OPEN in response:
                log.warning(
                    "Iter %d: response contains %s but no tool calls "
                    "were parsed — re-prompting", iteration, TAG_TOOL_CALL_OPEN,
                )
                # Visible reasoning is discarded as on the normal path; the
                # unparsed call stays so the model can see what failed.
                memory.append({"role": "assistant", "content": (
                    _REASONING_BLOCK_RE.sub("", response).strip() or response
                )})
                _parse_detail = (
                    " Specific failure(s): " + "; ".join(batch.parse_errors[:3]) + "."
                    if batch.parse_errors else ""
                )
                memory.append({
                    "role": "user",
                    "content": (
                        f"[TOOL CALL PARSE ERROR] Your previous turn contained "
                        f"{TAG_TOOL_CALL_OPEN} blocks that could not be parsed."
                        f"{_parse_detail} "
                        f"Each {TAG_TOOL_CALL_OPEN} block must contain valid JSON, "
                        f"e.g. `{TAG_TOOL_CALL_OPEN}{{\"name\": \"tool_name\", "
                        f"\"arguments\": {{\"key\": \"value\"}}}}{MARKERS.tool_call.close}`. "
                        f"Re-emit the tool call(s) using JSON syntax, then "
                        f"add {TAG_WAIT} on its own line. If you intended to "
                        f"give a final answer, omit the {TAG_TOOL_CALL_OPEN} tags entirely."
                    ),
                })
                continue

            successful_tools = _success_names(tool_history)
            if _terminal_tools and not (successful_tools & _terminal_tools):
                missing = ", ".join(sorted(_terminal_tools))
                log.warning(
                    "Iter %d: refusing premature final answer; terminal tool "
                    "still missing (%s)",
                    iteration,
                    missing,
                )
                memory.append({"role": "assistant", "content": response})
                # "Available" only when every terminal tool is callable here.
                available = (
                    "These tools are available in this session; nothing has "
                    "to be enabled. "
                    if all(name in tools for name in _terminal_tools) else ""
                )
                memory.append({
                    "role": "user",
                    "content": (
                        "[TERMINAL COMMIT MISSING] Your prose was not accepted "
                        f"because none of these terminal tools completed "
                        f"successfully: {missing}. {available}Call one now by "
                        f"writing {MARKERS.tool_call.open}"
                        '{"name": "<tool>", "arguments": {...}}'
                        f"{MARKERS.tool_call.close} followed by {TAG_WAIT}, with "
                        "the arguments the tool's description lists. If you have "
                        "no change to make, record that with the tool; do not "
                        "repeat the prose answer."
                    ),
                })
                continue

            # ── Soft required-tools note ────────────────────
            # If required_tools were specified but none were called,
            # append a note naming them so the reader knows the answer
            # was produced without those tools.  Does NOT block the
            # answer (``terminal_tools`` is the strict contract): some
            # turns legitimately end in prose without them.
            tools_called = {h.get("tool") for h in tool_history}

            # ── No-tool-call re-ask (opt-in) ─────────────────
            # A prose reply that ends the turn before any tool call,
            # while the caller named required tools: send it back with
            # a host notice up to ``required_tools_reask`` times. A turn
            # that used other tools and then chose prose is a
            # decision and is not re-asked; after the re-asks the soft
            # note below applies.
            if (
                required_tools
                and not (tools_called & required_tools)
                and not tool_history
                and _no_tool_reasks < required_tools_reask
            ):
                _no_tool_reasks += 1
                log.warning(
                    "Iter %d: prose answer before any tool call; re-asking "
                    "(%d/%d) with the %s notice",
                    iteration, _no_tool_reasks, required_tools_reask,
                    NO_TOOL_CALL_NOTICE_TAG,
                )
                memory.append({"role": "assistant", "content": response})
                memory.append({
                    "role": "user",
                    "content": _no_tool_call_notice(
                        attempt=_no_tool_reasks, limit=required_tools_reask,
                        required=sorted(required_tools), tool_names=sorted(tools),
                        example_call=next((
                            skeleton for skeleton in (
                                _tool_call_skeleton(name, tools.get(name))
                                for name in sorted(required_tools)
                            ) if skeleton
                        ), None),
                    ),
                })
                continue

            # A final answer the provider stopped at its output limit is
            # continued and joined.  Not for terminal-tool turns, whose
            # deliverable is the committed tool payload.
            if not _terminal_tools:
                _joined = _continue_cut_answer(
                    client, _sent_prompt, _tagged_system, response,
                )
                if _joined is not response:
                    if _last_context.endswith(response):
                        _last_context = _last_context[: -len(response)] + _joined
                    response = _joined

            if required_tools and not (tools_called & required_tools):
                _missing = ", ".join(sorted(required_tools - tools_called))
                response += (
                    "\n\n---\n*Host note: this turn called none of the expected "
                    "tools (%s); the answer above was produced without their "
                    "results.*" % _missing
                )
                log.info("Required-tools note appended (none of %s called)", required_tools)
                _anchor(
                    ctx_anchor.SYNC_REQUIRED_TOOLS_NOTE_APPEND,
                    hooks,
                    iteration=iteration,
                    required_tools=sorted(required_tools),
                    missing_tools=sorted(required_tools - tools_called),
                )

            # ── 🔗 Anchor: FINAL_ANSWER_BEFORE ─────────────
            _anchor(ctx_anchor.SYNC_FINAL_ANSWER_BEFORE, hooks,
                    iteration=iteration, answer=response)

            # Strip reasoning/summary blocks and leftover marker tags
            _clean_answer = _clean_answer_text(response)

            # Final answer
            memory.append({"role": "assistant", "content": response})
            _anchor(ctx_anchor.SYNC_FINAL_ANSWER_AFTER, hooks,
                    iteration=iteration, answer=_clean_answer)
            return AgentTurnResult(
                answer=_clean_answer,
                iterations=iteration,
                elapsed_seconds=_reconstruction_time(time.time) - t0,
                tool_history=tool_history,
                final_context=_last_context,
            )

        # ── Execute tool(s) — parallel batch support ────────
        # If the LLM emitted multiple <tool_call> blocks, execute
        # all of them and bundle results into one <tool_result>.
        # This counts as ONE turn for compaction purposes.

        # Extract reasoning text before the first <tool_call>
        tc_idx_first = response.find(TAG_TOOL_CALL_OPEN)
        _reasoning_text = response[:tc_idx_first].strip() if tc_idx_first > 0 else ""

        result_parts: list[str] = []

        # ── Pre-execution validation gate ───────────────────
        # Fire SYNC_BATCH_PRE_VALIDATE before any tool executes.
        # If guidance is returned, inject it as the tool result
        # WITHOUT executing any tools — the agent must fix params.
        _pre_validate = _anchor(
            tool_anchor.SYNC_BATCH_PRE_VALIDATE,
            hooks,
            tool_calls=all_tool_calls,
            tools=tools,
            engine_hooks=hooks,
        )
        if terminal_turn_budget:
            terminal_count = sum(tc.get("name") in _terminal_tools for tc in all_tool_calls)
            if terminal_count > 1 or (
                _terminal_only_turn
                and (len(all_tool_calls) != 1 or terminal_count != 1)
            ):
                _pre_validate = (
                    "Terminal decision policy blocked this batch: submit exactly "
                    "one allowed terminal tool on the final decision turn; "
                    "multiple terminal decisions are never accepted together."
                )
        if _pre_validate is None:
            log.debug(
                "Batch pre-validation: %d tool(s) passed",
                len(all_tool_calls),
            )
        if _pre_validate is not None:
            # Tag the guidance so it can be cleaned up later
            combined_result = (
                f"{TAG_VALIDATION_OPEN}\n{_pre_validate}\n{TAG_VALIDATION_CLOSE}"
            )
            log.info(
                "Batch pre-validation: guidance emitted for %d tool(s), "
                "skipping execution",
                len(all_tool_calls),
            )

            # Record in tool_history so the browser terminal sees it.
            # Tag each entry with its individual validation status so
            # the agent (and the human) can see which tool was blocked
            # vs. which was just held back by the batch.
            _blocked_names = {
                line.split("**")[1].split("\u2717 ")[-1].strip()
                for line in _pre_validate.split("\n")
                if "\u2717 " in line
            }
            for tc in all_tool_calls:
                _tn = tc.get("name", "?")
                _status = (
                    "blocked" if _tn in _blocked_names
                    else "held-back-by-batch"
                )
                # Extract per-tool detail from the report (section between this
                # tool's header and the next header / end of report).
                _per_tool_detail = ""
                _marker = f"**\u2717 {_tn}**"
                _idx_start = _pre_validate.find(_marker)
                if _idx_start >= 0:
                    _idx_end = _pre_validate.find("\n\n**", _idx_start + len(_marker))
                    _per_tool_detail = (
                        _pre_validate[_idx_start:_idx_end].strip()
                        if _idx_end > 0
                        else _pre_validate[_idx_start:].strip()
                    )

                tool_history.append({
                    "iteration": iteration,
                    "tool": _tn,
                    "args_keys": sorted(tc.get("arguments", {}).keys()),
                    "arguments": tc.get("arguments", {}),
                    "result_chars": len(_pre_validate),
                    "result_full": f"[validation {_status}] {_per_tool_detail or _pre_validate[:300]}",
                    "reasoning": _reasoning_text if tc is all_tool_calls[0] else "",
                    "elapsed_s": 0.0,
                })
                _anchor(tool_anchor.SYNC_TOOL_VALIDATION_BLOCKED, hooks,
                        iteration=iteration, tool_name=_tn,
                        status=_status,
                        detail=_per_tool_detail or _pre_validate[:500],
                        args=tc.get("arguments", {}))

            # Skip the entire execution loop — jump to memory injection.
            # We still need to record the assistant message + tool_result.
            compact_tc = _anchor(
                tool_anchor.SYNC_TOOL_CALLS_MEMORY_COMPACT,
                hooks,
                tool_calls=all_tool_calls,
                deferred_count=batch.deferred_count,
            )

            kept_prefix = ""
            if tc_idx_first > 0:
                pre_tc = response[:tc_idx_first]
                sm = _SUMMARY_BLOCK_RE.search(pre_tc)
                summary_text = sm.group(1).strip() if sm else ""
                if len(summary_text) > _cfg.SUMMARY_MAX_CHARS:
                    summary_text = summary_text[:_cfg.SUMMARY_MAX_CHARS] + "…"
                _preserved_tags = []
                for _tag_pattern in (_COMPACT_NOTE_RE, _COMPRESS_TAG_RE):
                    for _tm in _tag_pattern.finditer(pre_tc):
                        _preserved_tags.append(_tm.group())
                kept_parts = []
                if summary_text:
                    kept_parts.append(f"{TAG_SUMMARY_OPEN}{summary_text}{TAG_SUMMARY_CLOSE}")
                for _tag in _preserved_tags:
                    kept_parts.append(_tag)
                kept_prefix = "\n".join(kept_parts) if kept_parts else ""

            response = (kept_prefix + "\n" + compact_tc) if kept_prefix else compact_tc
            memory.append({"role": "assistant", "content": response})
            _anchor(mem_anchor.SYNC_ASSISTANT_MESSAGE_APPEND, hooks,
                    iteration=iteration, content=response)
            memory.append({
                "role": "user",
                "content": f"{TAG_TOOL_RESULT_OPEN}\n{combined_result}\n{TAG_TOOL_RESULT_CLOSE}",
            })
            _anchor(tool_anchor.SYNC_TOOL_RESULT_INJECT, hooks,
                    iteration=iteration, result_chars=len(combined_result))
            consecutive_empty_waits = 0
            continue

        # ── Validation passed — clean old guidance traces ───────
        # Replace verbose <validation_guidance> blocks in earlier
        # memory entries with a compact note so context stays lean.
        _clean_validation_traces(memory)

        # ── Terminal-tool batch guard ────────────────────────
        # A terminal commit authored in the same batch as data-gathering
        # calls cannot be grounded in their results (the payload was
        # written before any of them executed).  Hold the terminal
        # call(s) back — execute the data tools, return an actionable
        # error for the terminal slot — so the agent re-commits alone
        # next turn after observing the evidence.
        _batch_names_all = {tc.get("name", "") for tc in all_tool_calls}
        _terminal_mixed_batch = bool(
            _terminal_tools
            and len(all_tool_calls) > 1
            and (_batch_names_all & _terminal_tools)
            and (_batch_names_all - _terminal_tools)
        )
        if _terminal_mixed_batch:
            log.info(
                "Terminal tool(s) %s held back — batched with data tool(s) %s",
                sorted(_batch_names_all & _terminal_tools),
                sorted(_batch_names_all - _terminal_tools),
            )

        _batch_history_start = len(tool_history)
        for tc in all_tool_calls:
            tool_name = tc.get("name", "")
            raw_args = tc.get("arguments", {})
            fn = tools.get(tool_name)

            tool_t0 = _reconstruction_time(time.time)

            if _terminal_mixed_batch and tool_name in _terminal_tools:
                _others = ", ".join(sorted(_batch_names_all - _terminal_tools))
                one_result = (
                    f"ERROR: [TERMINAL_TOOL_HELD_BACK] `{tool_name}` was NOT "
                    f"executed because it was batched with data-gathering "
                    f"tool(s) ({_others}). A terminal commit must be authored "
                    "AFTER observing those results — a payload written in the "
                    "same turn cannot be grounded in them. Review the other "
                    f"tool results in this batch, then re-call `{tool_name}` "
                    "ALONE (a single tool call with nothing else in the batch)."
                )
            elif fn is None:
                one_result = json.dumps({
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": sorted(tools.keys()),
                })
            else:
                args = _normalize_args(tool_name, raw_args, fn)
                try:
                    result = fn(**args)
                    if isinstance(result, dict):
                        one_result = json.dumps(result, indent=2, default=str)
                        if len(one_result) > 2000:
                            log.debug(
                                "Tool %s returned a raw dict (%d chars) — "
                                "skip-subagent tool (normal for L2)",
                                tool_name, len(one_result),
                            )
                    elif isinstance(result, str):
                        one_result = result
                    else:
                        one_result = str(result)
                except Exception as e:
                    log.error("Tool %s execution failed: %s", tool_name, e, exc_info=True)
                    one_result = json.dumps({"error": str(e)})

            tool_elapsed = _reconstruction_time(time.time) - tool_t0
            one_result = truncate_result(one_result)

            # ── 🔗 Anchor: TIME_BUDGET_CREDIT_TOOL ─────────────
            # Exclude this tool's wall-clock time from the reminder clock
            # when the caller flagged it as "untimed" (e.g. a long
            # build+solve pipeline). The hook credits the elapsed back to
            # the tracker so only the agent's own reasoning time counts.
            if untimed_tools and tool_name in untimed_tools:
                _anchor(
                    ctx_anchor.SYNC_TIME_BUDGET_CREDIT_TOOL,
                    hooks,
                    tracker=_time_tracker,
                    tool=tool_name,
                    elapsed_s=tool_elapsed,
                )

            tool_history.append({
                "iteration": iteration,
                "tool": tool_name,
                "args_keys": sorted(raw_args.keys()) if raw_args else [],
                "arguments": raw_args,
                "result_chars": len(one_result),
                "result_full": one_result,
                "reasoning": _reasoning_text if tc is all_tool_calls[0] else "",
                "elapsed_s": round(tool_elapsed, 1),
            })

            # ── 🔗 Anchor: ON_TOOL_RESULT (stats) ──────────────
            _anchor(tool_anchor.SYNC_TOOL_RESULT_RECORDED, hooks,
                  iteration=iteration, tool_name=tool_name,
                  args=raw_args or {}, raw_result_chars=len(one_result),
                  elapsed_s=round(tool_elapsed, 1))

            # ── 🔗 Anchor: AGENT_RECORD_REFERENCES (entity/DOI) ──
            # Fire on dict results so log_entity_references / log_doi_block_references
            # can extract compound/property/DOI references automatically.
            # Only attempt JSON parse when the result looks like JSON;
            # compacted tool results are markdown and should not be parsed.
            _raw_dict = None
            if isinstance(one_result, str) and one_result.lstrip()[:1] in ('{', '['):
                try:
                    _raw_dict, _json_appendix = _decode_leading_json(one_result)
                    if _json_appendix.strip():
                        log.debug(
                            "Reference tracking decoded leading JSON for %s "
                            "and ignored a %d-character text appendix",
                            tool_name,
                            len(_json_appendix),
                        )
                except (json.JSONDecodeError, ValueError) as exc:
                    log.error(
                        "Reference-tracking JSON parse failed for %s: %s  |  context_preview=%.300r",
                        tool_name, exc, one_result, exc_info=True,
                    )
                    _hr_mod.history_recorder.log_internal_error(
                        source="react_loop",
                        error_type="json_parse",
                        tool_name=tool_name,
                        message=f"{type(exc).__name__}: {exc}",
                        context_preview=one_result[:500],
                    )
            if isinstance(_raw_dict, dict):
                try:
                    _anchor(_AGENT_RECORD_REFERENCES, hooks,
                            tool_name=tool_name, raw_result=_raw_dict)
                except Exception as exc:
                    log.error(
                        "Reference-tracking anchor failed for %s: %s",
                        tool_name, exc, exc_info=True,
                    )
                    _hr_mod.history_recorder.log_internal_error(
                        source="react_loop",
                        error_type="reference_tracking",
                        tool_name=tool_name,
                        message=f"{type(exc).__name__}: {exc}",
                        context_preview=repr(_raw_dict)[:500],
                    )

            _is_json_err = '{"error"' in one_result[:20]
            _is_purpose_err = one_result.startswith("ERROR: Tool") and "purpose" in one_result[:200]
            if _is_purpose_err:
                # ── 🔗 Anchor: ON_PURPOSE_ERROR ────────────
                    _anchor(tool_anchor.SYNC_TOOL_PURPOSE_ERROR_RECORDED, hooks,
                      iteration=iteration, tool_name=tool_name,
                      error_text=one_result[:2000])
            elif _is_json_err:
                # ── 🔗 Anchor: ON_TOOL_ERROR ───────────────
                    _anchor(tool_anchor.SYNC_TOOL_ERROR_RECORDED, hooks,
                      iteration=iteration, tool_name=tool_name,
                      error_text=one_result[:2000], args=raw_args)
            else:
                # ── 🔗 Anchor: ON_TOOL_CALL ────────────────
                    _anchor(tool_anchor.SYNC_TOOL_CALL_RECORDED, hooks,
                      iteration=iteration, tool_name=tool_name,
                      args=raw_args or {}, result_chars=len(one_result),
                      elapsed_s=round(tool_elapsed, 1),
                      result_preview=one_result[:500])

            log.info(
                "🔧 %s(%s) → %d chars in %.1fs",
                tool_name,
                ", ".join(f"{k}=..." for k in sorted(raw_args.keys())[:3]),
                len(one_result),
                tool_elapsed,
            )

            # Label each result when running a parallel batch
            if len(all_tool_calls) > 1:
                result_parts.append(f"### {tool_name}\n{one_result}")
            else:
                result_parts.append(one_result)

        combined_result = "\n\n".join(result_parts)
        # The ordinary results of a batch that also inspected cached output
        # (one part per call, in call order); the inspect cleanup keeps them.
        _durable_result = "\n\n".join(
            part for tc, part in zip(all_tool_calls, result_parts)
            if tc.get("name") != "inspect_batch_result"
        )

        # A caller can opt specific tools out of parallel-batch shaping.
        # Protect the entire batch when even one call is named: replacing
        # only the protected member would still destroy its full result.
        _batch_tool_names = {
            tc.get("name", "") for tc in all_tool_calls
        }
        _batch_has_uncompacted_tool = bool(
            len(all_tool_calls) > 1
            and (
                "inspect_batch_result" in _batch_tool_names
                or _uncompacted_tools.intersection(_batch_tool_names)
            )
        )

        # ── Batch summary hook (menu tool batches) ──────────
        # When a batch_summary_hook is provided, give it first crack
        # at summarising the batch.  If it returns a string, use that
        # and skip the generic stage compaction.
        _hook_handled = False
        if len(all_tool_calls) > 1 and not _batch_has_uncompacted_tool:
            try:
                _hook_result = _anchor(
                    tool_anchor.SYNC_BATCH_SUMMARY_BUILD,
                    hooks,
                    tool_calls=all_tool_calls,
                    result_parts=result_parts,
                )
                if _hook_result is not None:
                    orig_chars = len(combined_result)
                    combined_result = _hook_result
                    _hook_handled = True
                    log.info(
                        "Batch summary hook: %d tools, %d → %d chars",
                        len(all_tool_calls), orig_chars, len(combined_result),
                    )
            except Exception as exc:
                log.warning("Batch summary hook failed: %s — falling through", exc, exc_info=True)

        # ── Stage compaction for parallel batches ───────────
        # When a multi-tool batch produces a large combined result,
        # replace it with a compact summary table.  The full results
        # are cached so the agent can inspect specific ones on demand.
        if (not _hook_handled
                and not _batch_has_uncompacted_tool
                and len(all_tool_calls) > 1
                and len(combined_result) > _cfg.STAGE_COMPACT_BUDGET):
            _batch_cache.clear()
            for idx, rt in enumerate(result_parts, 1):
                _batch_cache[idx] = rt

            orig_chars = len(combined_result)
            combined_result = _anchor(
                tool_anchor.SYNC_STAGE_COMPACTION_BUILD,
                hooks,
                tool_calls=all_tool_calls,
                result_parts=result_parts,
                note_chars=_cfg.STAGE_NOTE_CHARS,
            )
            combined_result += (
                "\n*Use `inspect_batch_result(tool_number)` to read "
                "the full output of any tool above before proceeding.*"
            )

            # Register the temporary inspect tool
            def inspect_batch_result(tool_number: Optional[int] = None) -> str:
                """Read the full result of a specific tool from the last
                parallel batch. Use the tool_number from the summary table.

                Parameters
                ----------
                tool_number : int
                    1-based index from the batch summary table.
                """
                valid = sorted(_batch_cache.keys())
                if tool_number is None:
                    return (
                        "inspect_batch_result needs a 1-based `tool_number` "
                        f"argument. Valid numbers: {valid}. "
                        "Example: inspect_batch_result(tool_number=1)"
                    )
                try:
                    key = int(tool_number)
                except (TypeError, ValueError):
                    return (f"Invalid tool_number {tool_number!r}. "
                            f"Valid numbers: {valid}")
                cached = _batch_cache.get(key)
                if cached:
                    return cached
                return f"No result #{key}. Valid numbers: {valid}"
            tools["inspect_batch_result"] = inspect_batch_result
            _batch_cache_registered_iter = iteration

            log.info(
                "Stage compaction: %d tools, %d → %d chars. "
                "inspect_batch_result registered.",
                len(all_tool_calls), orig_chars, len(combined_result),
            )

            # ── 🔗 Anchor: ON_STAGE_COMPACT ────────────────
            _anchor(tool_anchor.SYNC_STAGE_COMPACTION_RECORDED, hooks,
                  iteration=iteration, n_tools=len(all_tool_calls),
                  before_chars=orig_chars, after_chars=len(combined_result))
        elif (_batch_has_uncompacted_tool
                and len(combined_result) > _cfg.STAGE_COMPACT_BUDGET):
            protected_names = set(
                _uncompacted_tools.intersection(_batch_tool_names)
            )
            if "inspect_batch_result" in _batch_tool_names:
                protected_names.add("inspect_batch_result")
            log.info(
                "Stage compaction bypassed for parallel batch because it "
                "contains uncompacted tool(s): %s",
                ", ".join(sorted(protected_names)),
            )

        # Reset empty-wait counter — we successfully executed tools
        consecutive_empty_waits = 0

        batch_elapsed = _reconstruction_time(time.time) - tool_t0 if len(all_tool_calls) == 1 else (
            _reconstruction_time(time.time) - (t0 + elapsed)  # approximate batch wall time
        )

        if len(all_tool_calls) > 1:
            log.info("Parallel batch: %d tools executed in turn %d",
                     len(all_tool_calls), iteration)

        # ── Wait barrier feedback ───────────────────────────
        # When <wait/> was detected, append a status note so the LLM
        # knows the pre-wait tools are done and it should re-plan.
        if batch.wait_detected:
            tool_names = [tc.get("name", "?") for tc in all_tool_calls]
            wait_note = (
                f"\n\n[WAIT BARRIER COMPLETE] {len(all_tool_calls)} tool(s) "
                f"finished ({', '.join(tool_names)}). "
                f"{batch.deferred_count} deferred call(s) were discarded. "
                f"Use the results above to plan your next tool calls with "
                f"correct IDs/DOIs — do NOT guess."
            )
            combined_result += wait_note
            if _durable_result:
                _durable_result += wait_note
            log.info("Wait barrier complete: %d executed, %d deferred",
                     len(all_tool_calls), batch.deferred_count)

        # ── Append to conversation memory ───────────────────
        # Hardcode-strip <reasoning> blocks entirely and replace
        # verbose <tool_call> XML with compact name(key_args) form.
        compact_tc = _anchor(
            tool_anchor.SYNC_TOOL_CALLS_MEMORY_COMPACT,
            hooks,
            tool_calls=all_tool_calls,
            deferred_count=batch.deferred_count,
        )

        kept_prefix = ""
        if tc_idx_first > 0:
            pre_tc = response[:tc_idx_first]
            # Extract <summary> block if present
            sm = _SUMMARY_BLOCK_RE.search(pre_tc)
            summary_text = sm.group(1).strip() if sm else ""
            if len(summary_text) > _cfg.SUMMARY_MAX_CHARS:
                summary_text = summary_text[:_cfg.SUMMARY_MAX_CHARS] + "…"
            # Extract compaction tags
            _preserved_tags = []
            for _tag_pattern in (
                _COMPACT_NOTE_RE,
                _COMPRESS_TAG_RE,
            ):
                for _tm in _tag_pattern.finditer(pre_tc):
                    _preserved_tags.append(_tm.group())
            # Rebuild: summary + tags only (reasoning discarded)
            kept_parts = []
            if summary_text:
                kept_parts.append(f"{TAG_SUMMARY_OPEN}{summary_text}{TAG_SUMMARY_CLOSE}")
            for _tag in _preserved_tags:
                kept_parts.append(_tag)
            kept_prefix = "\n".join(kept_parts) if kept_parts else ""

        response = (kept_prefix + "\n" + compact_tc) if kept_prefix else compact_tc
        # ── 🔗 Anchor: MEMORY_APPEND_ASSISTANT ─────────────
        memory.append({"role": "assistant", "content": response})
        _anchor(mem_anchor.SYNC_ASSISTANT_MESSAGE_APPEND, hooks,
                iteration=iteration, content=response)
        # ── 🔗 Anchor: TOOL_RESULT_INJECT ──────────────────
        _result_content = (
            f"{TAG_TOOL_RESULT_OPEN}\n{combined_result}\n{TAG_TOOL_RESULT_CLOSE}"
        )
        if "inspect_batch_result" in _batch_tool_names:
            _inspect_payload_durable[_result_content] = (
                f"{TAG_TOOL_RESULT_OPEN}\n{_durable_result}\n{TAG_TOOL_RESULT_CLOSE}"
                if _durable_result else ""
            )
        memory.append({
            "role": "user",
            "content": _result_content,
        })
        _anchor(tool_anchor.SYNC_TOOL_RESULT_INJECT, hooks,
                iteration=iteration, result_chars=len(combined_result))

        _stage_complete = bool(tool_completion_check and tool_completion_check(
            tool_history[_batch_history_start:]
        ))
        if _stage_complete or (terminal_turn_budget and (_success_names(tool_history) & _terminal_tools)):
            # The actual response and full tool receipt have already passed
            # native capture, history and memory hooks. No narration call is
            # required to make the terminal decision effective.
            _anchor(ctx_anchor.SYNC_FINAL_ANSWER_AFTER, hooks,
                    iteration=iteration, answer="")
            return AgentTurnResult(
                answer="", iterations=iteration,
                elapsed_seconds=_reconstruction_time(time.time) - t0,
                tool_history=tool_history, final_context=_last_context,
            )

        # ── LLM-driven context compaction ────────────────────────
        # Two triggers (either can fire):
        #   1. Interval-based: every N turns (compaction_interval)
        #   2. Size-based: when total context exceeds char threshold
        # The LLM selection step can still choose "NONE" to skip.
        # Note: iteration counts LLM turns, not individual tool calls.
        total_chars = sum(len(m["content"]) for m in memory)
        _trigger = compaction_trigger_chars or _get_compaction_trigger_chars()
        _interval_hit = (compaction_interval
                         and iteration >= compaction_interval
                         and iteration % compaction_interval == 0)
        _size_hit = total_chars > _trigger

        if (_interval_hit or _size_hit) and not terminal_turn_budget:
            reason = (f"interval={compaction_interval}" if _interval_hit
                      else f"chars={total_chars}>{_trigger}")
            log.info("Compaction triggered (%s, turn %d) — requesting guidance",
                     reason, iteration)

            # ── Guidance hook: ask the main agent for purpose/tasks ──
            purpose = ""
            tasks = ""
            reminder_msg = _anchor(
                ctx_anchor.SYNC_COMPACTION_REMINDER_BUILD,
                hooks,
                total_chars=total_chars,
                iteration=iteration,
            )
            memory.append({"role": "user", "content": reminder_msg})
            try:
                _guidance_parts = []
                _wm = _anchor(mem_anchor.SYNC_WORKING_MEMORY_RENDER, hooks, iteration=iteration)
                if _wm:
                    _guidance_parts.append(f"## Working Memory\n{_wm}")
                for _t in memory:
                    _tag = "User" if _t["role"] == "user" else "Assistant"
                    _guidance_parts.append(f"## {_tag}\n{_t['content']}")
                _guidance_prompt = "\n\n".join(_guidance_parts)
                _guidance_resp = client.call(
                    _guidance_prompt, system_prompt,
                    max_tokens=_cfg.GUIDANCE_MAX_TOKENS,
                )
                _anchor(
                    ctx_anchor.SYNC_COMPACTION_GUIDANCE_RESPONSE,
                    hooks,
                    iteration,
                    _guidance_resp,
                    source="compaction-guidance",
                )
                purpose, tasks = _anchor(
                    ctx_anchor.SYNC_COMPACTION_GUIDANCE_PARSE,
                    hooks,
                    guidance_response=_guidance_resp,
                ) or ("", "")
                if tasks.upper().strip() == "SKIP":
                    log.info("Agent requested SKIP compaction this round")
                    memory.pop()  # remove reminder before continue
                    _anchor(ctx_anchor.SYNC_COMPACTION_SKIPPED, hooks,
                          iteration=iteration, before_chars=total_chars,
                          after_chars=total_chars, trigger=reason,
                          purpose=purpose, tasks="SKIP",
                          outcome="skipped_by_agent")
                    continue  # skip compaction entirely
                log.info("Compaction guidance — PURPOSE: %s | TASKS: %s",
                         purpose[:80], tasks[:80])
            except Exception as e:
                log.warning("Guidance hook failed (%s) — proceeding without", e, exc_info=True)
            finally:
                # Always strip the reminder from memory
                if memory and memory[-1]["role"] == "user" \
                        and TAG_COMPACTION_REMINDER_OPEN in memory[-1]["content"]:
                    memory.pop()

            try:
                _receipt = _anchor(
                    ctx_anchor.SYNC_COMPACTION_EXECUTE,
                    hooks,
                    memory=memory,
                    argo_fn=_argo_fn,
                    purpose=purpose,
                    tasks=tasks,
                ) or ""
                new_total = sum(len(m["content"]) for m in memory)
                _outcome = "compacted" if _receipt else "skipped_by_selector"
                log.info("Compaction done: %d → %d chars (%s)",
                         total_chars, new_total, _outcome)
                if _receipt:
                    memory.append({
                        "role": "user",
                        "content": f"{TAG_COMPACT_NOTE_OPEN}{_receipt}{TAG_COMPACT_NOTE_CLOSE}",
                    })
                    log.info("Compaction receipt injected: %s", _receipt[:120])
                # ── 🔗 Anchor: ON_COMPACTION_STATS + ON_COMPACTION ─
                _anchor(ctx_anchor.SYNC_COMPACTION_STATS_RECORDED, hooks,
                      before_chars=total_chars, after_chars=new_total,
                      trigger=reason)
                _anchor(ctx_anchor.SYNC_COMPACTION_RECORDED, hooks,
                      iteration=iteration, before_chars=total_chars,
                      after_chars=new_total, trigger=reason,
                      purpose=purpose, tasks=tasks,
                      receipt=_receipt, outcome=_outcome)
            except Exception as e:
                log.warning("Compaction failed (%s) — falling back to trimming", e, exc_info=True)
                _anchor(
                    ctx_anchor.SYNC_COMPACTION_TRIM_FALLBACK,
                    hooks,
                    memory=memory,
                    keep_recent=_cfg.KEEP_RECENT_RESULTS,
                    preview_chars=_cfg.TRIMMED_PREVIEW_CHARS,
                )

    if terminal_turn_budget:
        _anchor(ctx_anchor.SYNC_HARD_STOP_FINAL_ANSWER_AFTER, hooks,
                iteration=_loop_limit, answer="", timed_out=True)
        return AgentTurnResult(
            answer="", iterations=_loop_limit,
            elapsed_seconds=_reconstruction_time(time.time) - t0,
            tool_history=tool_history, timed_out=True, final_context=_last_context,
        )

    # The explicit maximum-turn contract remains a hard bound. It is
    # independent of the effective-time reminder scale.
    memory.append({
        "role": "user",
        "content": (
            "[ITERATION LIMIT] Maximum tool-turn count reached. "
            "Summarise ALL findings from tool results so far into a "
            "complete answer. Do NOT call any more tools."
        ),
    })
    try:
        final_response = client.call(
            "\n\n".join(
                f"## {'User' if t['role'] == 'user' else 'Assistant'}\n{t['content']}"
                for t in memory
            ),
            system_prompt,
        )
        if not _terminal_tools:
            final_response = _continue_cut_answer(
                client,
                "\n\n".join(
                    f"## {'User' if t['role'] == 'user' else 'Assistant'}\n{t['content']}"
                    for t in memory
                ),
                system_prompt,
                final_response,
            )
    except Exception as exc:
        log.error("Final summary call failed: %s", exc)
        final_response = "(Max iterations reached — returning partial results)"
    _last_context = (
        f"## System Prompt\n{system_prompt}\n\n"
        + "\n\n".join(
            f"## {'User' if t['role'] == 'user' else 'Assistant'}\n{t['content']}"
            for t in memory
        )
        + f"\n\n## LLM Response\n{final_response}"
    )
    _last_context = _anchor(
        ctx_anchor.SYNC_FINAL_CONTEXT_CAPTURED,
        hooks,
        iteration=_max_iter,
        final_context=_last_context,
        response=final_response,
        timed_out=True,
    ) or _last_context
    _clean_final = _clean_answer_text(final_response)
    _anchor(ctx_anchor.SYNC_HARD_STOP_FINAL_ANSWER_AFTER, hooks,
            iteration=_max_iter, answer=_clean_final, timed_out=True)
    return AgentTurnResult(
        answer=_clean_final,
        iterations=_max_iter,
        elapsed_seconds=_reconstruction_time(time.time) - t0,
        tool_history=tool_history,
        timed_out=True,
        final_context=_last_context,
    )
