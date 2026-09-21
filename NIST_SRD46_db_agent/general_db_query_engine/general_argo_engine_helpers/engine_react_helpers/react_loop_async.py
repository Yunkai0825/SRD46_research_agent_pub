"""
Async ReAct loop — ``async_agent_turn()`` for parallel L2 subagent dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable, Dict, List

from ..engine_config import get_config
from ..argo_client_caller import ArgoClient
from ..engine_tool_interface_helpers.tool_call_parser import extract_tool_call
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
from ...general_hooks_management_helpers.general_memory_management_tools_hooks_helpers import _memory_hooks_anchors_catalog as mem_anchor
from ...general_tool_management_helpers import _tool_hooks_anchors_catalog as tool_anchor
from ...general_text_context_marker_catalog import MARKERS, ALL_CONTEXT_MARKERS_RE as _ALL_MARKERS_RE
from .react_loop import _clean_answer_text
from ...general_hooks_management_helpers.general_context_hooks.time_budget_reminder_hooks import (
    TimeBudgetTracker,
)

TAG_TOOL_CALL_OPEN = MARKERS.tool_call.open
TAG_TOOL_RESULT_OPEN = MARKERS.tool_result.open
TAG_TOOL_RESULT_CLOSE = MARKERS.tool_result.close
TAG_SUMMARY_OPEN = MARKERS.summary.open
TAG_SUMMARY_CLOSE = MARKERS.summary.close
TAG_SYSTEM_PROMPT_OPEN = MARKERS.system_prompt.open
TAG_SYSTEM_PROMPT_CLOSE = MARKERS.system_prompt.close
TAG_MEMORY_OPEN = MARKERS.memory.open
TAG_MEMORY_CLOSE = MARKERS.memory.close

log = logging.getLogger("NISTsrd46-UI")

async def async_agent_turn(
    user_message: str,
    *,
    system_prompt: str,
    tools: Dict[str, Callable],
    memory: List[dict],
    client: ArgoClient | None = None,
    max_iterations: int | None = None,
    timeout: int | None = None,
    hooks: EngineHooks | None = None,
    is_subagent: bool = False,
) -> AgentTurnResult:
    """Async version of agent_turn() using ArgoClient.acall().

    Designed for use with asyncio.gather() to run multiple L2
    subagent evaluations in parallel.  Same ReAct loop logic as
    agent_turn(), but uses the async (thread-wrapped) endpoint.
    """
    if client is None:
        client = ArgoClient.with_tier("L2")

    # Build an argo_fn wrapper for the compactor (same as sync loop)
    def _argo_fn(prompt, system, stop=None):
        return client.call(prompt, system, stop=stop or [])

    _cfg = get_config()
    _max_iter = max_iterations or _cfg.L2_MAX_ITERATIONS
    _timeout = timeout or _cfg.L2_MAX_SECONDS

    memory.append({"role": "user", "content": user_message})
    _anchor(mem_anchor.ASYNC_USER_MESSAGE_APPEND, hooks,
            iteration=0, content=user_message)
    t0 = time.time()
    time_tracker = TimeBudgetTracker(
        timeout=_timeout,
        thresholds=list(_cfg.WARN_THRESHOLDS),
        max_warnings=_cfg.MAX_WRAP_WARNINGS,
    )
    tool_history: list[dict] = []

    for iteration in range(1, _max_iter + 1):
        elapsed = time.time() - t0
        # The async loop follows the same reminder-only contract as the
        # synchronous loop: crossing the scale never suppresses a tool call.
        time_tracker.check_and_inject_warnings(elapsed, memory)

        # ── 🔗 Build flat prompt with anchors ────────────
        flat_parts = []
        wm_chars = 0
        wm = _anchor(mem_anchor.ASYNC_WORKING_MEMORY_RENDER, hooks, iteration=iteration)
        if wm:
            wm_part = (
                f"## Working Memory\n"
                f"{TAG_MEMORY_OPEN}\n{wm}\n{TAG_MEMORY_CLOSE}"
            )
            flat_parts.append(wm_part)
            wm_chars = len(wm_part)
        _first_user_seen = False
        user_chars = 0
        asst_chars = 0
        turn_details: list[str] = []
        for turn in memory:
            if turn["role"] == "user" and is_subagent and not _first_user_seen:
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
        _anchor(ctx_anchor.ASYNC_FLAT_PROMPT_BUILD, hooks,
                iteration=iteration, prompt_chars=len(flat_prompt))

        log.info(
            "CTX turn=%d | system=%d wm=%d user=%d asst=%d "
            "total_prompt=%d | turns=[%s]",
            iteration, len(system_prompt), wm_chars,
            user_chars, asst_chars, len(flat_prompt),
            ", ".join(turn_details),
        )

        # ── 🔗 Anchor: LLM_CALL_BEFORE ─────────────────────
        _anchor(ctx_anchor.ASYNC_LLM_CALL_BEFORE, hooks, iteration=iteration)

        # Async LLM call
        _tagged_system = (
            f"{TAG_SYSTEM_PROMPT_OPEN}\n{system_prompt}\n{TAG_SYSTEM_PROMPT_CLOSE}"
        )
        response = await client.acall(flat_prompt, _tagged_system)

        # ── 🔗 Anchor: LLM_RESPONSE_AFTER + ON_REASONING ───
        _anchor(ctx_anchor.ASYNC_LLM_RESPONSE_AFTER, hooks, iteration, response)

        tool_call = extract_tool_call(response)
        if tool_call is None:
            # ── Parse-failure guard ─────────────────────────
            # If the LLM emitted <tool_call> tags but none parsed,
            # don't silently treat the response as the final answer
            # (which would surface raw tag text to the user).
            # Re-prompt with a corrective message.
            if TAG_TOOL_CALL_OPEN in response:
                log.warning(
                    "Iter %d (async): response contains %s but no tool calls "
                    "were parsed — re-prompting", iteration, TAG_TOOL_CALL_OPEN,
                )
                memory.append({"role": "assistant", "content": response})
                memory.append({
                    "role": "user",
                    "content": (
                        f"[TOOL CALL PARSE ERROR] Your previous turn contained "
                        f"{TAG_TOOL_CALL_OPEN} blocks that could not be parsed. "
                        f"Each {TAG_TOOL_CALL_OPEN} block must contain valid JSON, "
                        f"e.g. `{TAG_TOOL_CALL_OPEN}{{\"name\": \"tool_name\", "
                        f"\"arguments\": {{\"key\": \"value\"}}}}{MARKERS.tool_call.close}`. "
                        f"Re-emit the tool call(s) using JSON syntax. "
                        f"If you intended to give a final answer, omit the "
                        f"{TAG_TOOL_CALL_OPEN} tags entirely."
                    ),
                })
                continue

            _anchor(ctx_anchor.ASYNC_FINAL_ANSWER_BEFORE, hooks,
                iteration=iteration, answer=response)
            _clean_answer = _clean_answer_text(response)
            memory.append({"role": "assistant", "content": response})
            _anchor(ctx_anchor.ASYNC_FINAL_ANSWER_AFTER, hooks,
                iteration=iteration, answer=_clean_answer)
            return AgentTurnResult(
                answer=_clean_answer,
                iterations=iteration,
                elapsed_seconds=time.time() - t0,
                tool_history=tool_history,
            )

        # Execute tool (tools are sync — run in thread to not block)
        tool_name = tool_call.get("name", "")
        raw_args = tool_call.get("arguments", {})
        fn = tools.get(tool_name)

        tool_t0 = time.time()
        if fn is None:
            tool_result = json.dumps({
                "error": f"Unknown tool: {tool_name}",
                "available_tools": sorted(tools.keys()),
            })
        else:
            args = _normalize_args(tool_name, raw_args, fn)
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: fn(**args)
                )
                if isinstance(result, dict):
                    tool_result = json.dumps(result, indent=2, default=str)
                    if len(tool_result) > 2000:
                        log.debug(
                            "Tool %s returned a raw dict (%d chars) — "
                            "skip-subagent tool (normal for L2)",
                            tool_name, len(tool_result),
                        )
                elif isinstance(result, str):
                    tool_result = result
                else:
                    tool_result = str(result)
            except Exception as e:
                log.error("Tool %s execution failed: %s", tool_name, e, exc_info=True)
                tool_result = json.dumps({"error": str(e)})

        tool_result = truncate_result(tool_result)
        tool_elapsed = time.time() - tool_t0

        tool_history.append({
            "iteration": iteration,
            "tool": tool_name,
            "args_keys": sorted(raw_args.keys()) if raw_args else [],
            "arguments": raw_args or {},
            "result_chars": len(tool_result),
            "result_full": tool_result,
            "elapsed_s": round(tool_elapsed, 1),
        })

        # ── 🔗 Anchor: tool execution hooks ──────────────
        _anchor(tool_anchor.ASYNC_TOOL_RESULT_RECORDED, hooks,
              iteration=iteration, tool_name=tool_name,
              args=raw_args or {}, raw_result_chars=len(tool_result),
              elapsed_s=round(tool_elapsed, 1))

        # ── 🔗 Anchor: AGENT_RECORD_REFERENCES (entity/DOI) ──
        try:
            _raw_dict = json.loads(tool_result) if isinstance(tool_result, str) else None
            if isinstance(_raw_dict, dict):
                _anchor(_AGENT_RECORD_REFERENCES, hooks,
                        tool_name=tool_name, raw_result=_raw_dict)
        except Exception as exc:
            log.error("Reference-tracking failed for %s: %s", tool_name, exc, exc_info=True)

        _is_json_err = '{"error"' in tool_result[:20]
        _is_purpose_err = tool_result.startswith("ERROR: Tool") and "purpose" in tool_result[:200]
        if _is_purpose_err:
            _anchor(tool_anchor.ASYNC_TOOL_PURPOSE_ERROR_RECORDED, hooks,
                  iteration=iteration, tool_name=tool_name,
                  error_text=tool_result[:2000])
        elif _is_json_err:
            _anchor(tool_anchor.ASYNC_TOOL_ERROR_RECORDED, hooks,
                  iteration=iteration, tool_name=tool_name,
                  error_text=tool_result[:2000], args=raw_args)
        else:
            _anchor(tool_anchor.ASYNC_TOOL_CALL_RECORDED, hooks,
                  iteration=iteration, tool_name=tool_name,
                  args=raw_args or {}, result_chars=len(tool_result),
                  elapsed_s=round(tool_elapsed, 1),
                  result_preview=tool_result[:500])

        # Compact tool call XML for memory (same as sync loop)
        compact_tc = _anchor(
            tool_anchor.ASYNC_TOOL_CALLS_MEMORY_COMPACT,
            hooks,
            tool_calls=[tool_call],
            deferred_count=0,
        )
        tc_idx = response.find(TAG_TOOL_CALL_OPEN)
        kept_prefix = ""
        if tc_idx > 0:
            pre_tc = response[:tc_idx]
            sm = _SUMMARY_BLOCK_RE.search(pre_tc)
            summary_text = sm.group(1).strip() if sm else ""
            if len(summary_text) > _cfg.SUMMARY_MAX_CHARS:
                summary_text = summary_text[:_cfg.SUMMARY_MAX_CHARS] + "…"
            if summary_text:
                kept_prefix = f"{TAG_SUMMARY_OPEN}{summary_text}{TAG_SUMMARY_CLOSE}"
        response = (kept_prefix + "\n" + compact_tc) if kept_prefix else compact_tc
        # ── 🔗 Anchor: MEMORY_APPEND_ASSISTANT ─────────────
        memory.append({"role": "assistant", "content": response})
        _anchor(mem_anchor.ASYNC_ASSISTANT_MESSAGE_APPEND, hooks,
                iteration=iteration, content=response)
        # ── 🔗 Anchor: TOOL_RESULT_INJECT ──────────────────
        memory.append({
            "role": "user",
            "content": f"{TAG_TOOL_RESULT_OPEN}\n{tool_result}\n{TAG_TOOL_RESULT_CLOSE}",
        })
        _anchor(tool_anchor.ASYNC_TOOL_RESULT_INJECT, hooks,
                iteration=iteration, result_chars=len(tool_result))

        # ── LLM-driven context compaction (same as sync loop) ──
        total_chars = sum(len(m["content"]) for m in memory)
        if total_chars > _get_compaction_trigger_chars():
            log.info("[async] Context at %d chars — triggering LLM compaction", total_chars)
            try:
                _anchor(
                    ctx_anchor.ASYNC_COMPACTION_EXECUTE,
                    hooks,
                    memory=memory,
                    argo_fn=_argo_fn,
                )
            except Exception as e:
                log.warning("[async] Compaction failed (%s) — falling back to trimming", e, exc_info=True)
                _anchor(
                    ctx_anchor.ASYNC_COMPACTION_TRIM_FALLBACK,
                    hooks,
                    memory=memory,
                    keep_recent=_cfg.KEEP_RECENT_RESULTS,
                    preview_chars=_cfg.TRIMMED_PREVIEW_CHARS,
                )

    return AgentTurnResult(
        answer="(Max iterations reached — returning partial results)",
        iterations=_max_iter,
        elapsed_seconds=time.time() - t0,
        tool_history=tool_history,
        timed_out=True,
    )
