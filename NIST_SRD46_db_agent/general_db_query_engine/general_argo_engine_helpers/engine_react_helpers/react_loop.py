"""
ReAct loop — synchronous ``agent_turn()`` implementation.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable, Dict, List

from ..engine_config import get_config
from ..argo_client_caller import ArgoClient
from ..engine_tool_interface_helpers.tool_call_parser import extract_all_tool_calls
from .react_helpers import (
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


# ═══════════════════════════════════════════════════════════════
#  Main ReAct loop
# ═══════════════════════════════════════════════════════════════

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
    compaction_trigger_chars: int | None = None,
    compaction_interval: int | None = None,
    hooks: EngineHooks | None = None,
    is_subagent: bool = False,
    untimed_tools: set[str] | None = None,
    uncompacted_tools: set[str] | None = None,
    terminal_tools: set[str] | None = None,
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
        Legacy soft contract. If none of these tools was called, the final
        answer receives a provenance note; completion is not blocked. Use
        ``terminal_tools`` when a successful tool commit is mandatory.
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
        ``None`` (no exclusion — identical behaviour to before).
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
        from the legacy soft ``required_tools`` note.
    append_user_message : bool, optional
        Append ``user_message`` to ``memory`` before the first model call.
        Set false only when restoring a checksummed conversation whose first
        user turn is already present in ``memory``.
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

    if append_user_message:
        memory.append({"role": "user", "content": user_message})
        _anchor(mem_anchor.SYNC_USER_MESSAGE_APPEND, hooks,
                iteration=0, content=user_message)
    elif not memory:
        raise ValueError(
            "append_user_message=False requires restored conversation memory"
        )
    t0 = time.time()
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
    _last_context: str = ""     # raw LLM input+output for the final turn

    for iteration in range(1, _max_iter + 1):
        elapsed = time.time() - t0

        # Reserve the last model turn for a required terminal commit.  This is
        # injected before prompt construction so an agent that spent earlier
        # turns inspecting data still sees a concrete recovery instruction.
        if (
            _terminal_tools
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
                    "prose answer and do not perform another inspection. An "
                    "empty scientific change must still be committed with the "
                    "terminal tool's valid empty payload."
                ),
            })

        # ── Inspect cleanup: if batch cache is active but the last
        #    tool call was NOT inspect_batch_result, discard cached
        #    details from memory and remove the temporary tool. ──
        # Guard: give the LLM at least one full iteration AFTER
        # registration to actually observe and use inspect_batch_result.
        # (Cache is registered at end of iter N — at start of iter N+1
        # the LLM has not yet been called with the new tool visible, so
        # cleanup must wait until iter N+2 at the earliest.)
        if _batch_cache and tool_history and iteration > _batch_cache_registered_iter + 1:
            last_tool = tool_history[-1].get("tool", "")
            if last_tool != "inspect_batch_result":
                # Remove inspect_batch_result entries from memory
                memory[:] = [
                    m for m in memory
                    if "### inspect_batch_result" not in m.get("content", "")
                ]
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

        # ── 🔗 Anchor: LLM_RESPONSE_AFTER + ON_REASONING ───
        _anchor(ctx_anchor.SYNC_LLM_RESPONSE_AFTER, hooks, iteration, response)

        # Capture raw context as the LLM saw it
        _last_context = (
            f"## System Prompt\n{system_prompt}\n\n"
            f"{flat_prompt}\n\n"
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

        # ── Empty-wait guard: LLM emitted <wait/> with no tools ──
        if batch.wait_detected and not all_tool_calls:
            consecutive_empty_waits += 1
            log.warning("Empty <wait/> #%d (no tool calls before barrier)",
                        consecutive_empty_waits)
            memory.append({"role": "assistant", "content": response})
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
            elif batch.parse_errors:
                # The model DID place tool calls before <wait/> — they were
                # malformed.  Tell it exactly what failed, not to reorder.
                detail = "; ".join(batch.parse_errors[:3])
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
                memory.append({"role": "assistant", "content": response})
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

            successful_tools = _successful_tool_names(tool_history)
            if _terminal_tools and not (successful_tools & _terminal_tools):
                missing = ", ".join(sorted(_terminal_tools))
                log.warning(
                    "Iter %d: refusing premature final answer; terminal tool "
                    "still missing (%s)",
                    iteration,
                    missing,
                )
                memory.append({"role": "assistant", "content": response})
                memory.append({
                    "role": "user",
                    "content": (
                        "[TERMINAL COMMIT MISSING] Your prose was not accepted "
                        f"because none of these terminal tools completed "
                        f"successfully: {missing}. Call the appropriate tool "
                        "now with its documented arguments. If no changes are "
                        "needed, submit the tool's valid empty payload; do not "
                        "repeat the prose answer."
                    ),
                })
                continue

            # ── Soft fitting reminder ───────────────────────
            # If required_tools were specified but none were called,
            # append a note so the reader knows no actual fitting
            # was performed.  Does NOT block the answer — some
            # queries (data coverage, discovery) don't need fitting.
            tools_called = {h.get("tool") for h in tool_history}
            if required_tools and not (tools_called & required_tools):
                _missing = ", ".join(sorted(required_tools - tools_called))
                response += (
                    "\n\n---\n*Note: No fitting tools were called during "
                    "this run (%s). All numbers above come from database "
                    "queries only — no Redlich-Kister or other curve fits "
                    "were performed.*" % _missing
                )
                log.info("Fitting reminder appended (none of %s called)", required_tools)
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
                elapsed_seconds=time.time() - t0,
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

        for tc in all_tool_calls:
            tool_name = tc.get("name", "")
            raw_args = tc.get("arguments", {})
            fn = tools.get(tool_name)

            tool_t0 = time.time()

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

            tool_elapsed = time.time() - tool_t0
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

        batch_elapsed = time.time() - tool_t0 if len(all_tool_calls) == 1 else (
            time.time() - (t0 + elapsed)  # approximate batch wall time
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
        memory.append({
            "role": "user",
            "content": f"{TAG_TOOL_RESULT_OPEN}\n{combined_result}\n{TAG_TOOL_RESULT_CLOSE}",
        })
        _anchor(tool_anchor.SYNC_TOOL_RESULT_INJECT, hooks,
                iteration=iteration, result_chars=len(combined_result))

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

        if _interval_hit or _size_hit:
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
        elapsed_seconds=time.time() - t0,
        tool_history=tool_history,
        timed_out=True,
        final_context=_last_context,
    )
