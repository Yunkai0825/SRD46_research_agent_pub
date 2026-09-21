# =============================================================
#  Agent API and agentic loop
# =============================================================

import asyncio
import contextvars
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol


log = logging.getLogger("SRD46-UI")


_compactor_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "compactor_run_id",
    default=None,
)

_COMPACTOR_EXTRA_FIELDS = (
    "for_tool",
    "event_kind",
    "round_kind",
    "outcome",
    "candidate_idx",
    "candidate_tool",
    "attempts_used",
    "candidates_selected",
    "candidate_count",
    "tasks_run",
    "context_chars_before",
    "context_chars_after",
    "context_turns_before",
    "context_turns_after",
    "selection_duration_s",
    "round_duration_s",
    "duration_s",
    "original_chars",
    "final_chars",
)


class _CompactorCapture(logging.Handler):
    """Capture compactor events per run context, falling back to per thread."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self._events_by_scope: dict[tuple[str, str | int], list[dict]] = {}
        self._lock = threading.Lock()

    def _scope_key(self, *, run_id: Optional[str] = None, thread_id: Optional[int] = None) -> tuple[str, str | int]:
        resolved_run_id = _compactor_run_id_var.get() if run_id is None else run_id
        if resolved_run_id is not None:
            return ("run", resolved_run_id)
        resolved_thread_id = threading.get_ident() if thread_id is None else thread_id
        return ("thread", resolved_thread_id)

    def emit(self, record: logging.LogRecord) -> None:
        event = {
            "time": record.created,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in _COMPACTOR_EXTRA_FIELDS:
            if hasattr(record, field):
                event[field] = getattr(record, field)
        with self._lock:
            scope_key = self._scope_key(thread_id=record.thread)
            self._events_by_scope.setdefault(scope_key, []).append(event)

    def drain(self, *, run_id: Optional[str] = None, thread_id: Optional[int] = None) -> list[dict]:
        scope_key = self._scope_key(run_id=run_id, thread_id=thread_id)
        with self._lock:
            return list(self._events_by_scope.pop(scope_key, []))


_compactor_capture = _CompactorCapture()
_compactor_logger = logging.getLogger("SRD46-compactor")
if not any(isinstance(h, _CompactorCapture) for h in _compactor_logger.handlers):
    _compactor_logger.addHandler(_compactor_capture)


@dataclass
class AgentRunResult:
    answer: str
    memory: List[Dict[str, str]]
    tool_history: List[dict]
    compactor_events: List[dict]
    elapsed: float
    model_history: List[dict] = field(default_factory=list)


class ToolCallPolicy(Protocol):
    """Caller-supplied, synchronous authorization policy for tool calls.

    ``authorize`` receives the tool name and its normalized arguments. It
    must return ``True`` to allow the call or ``False`` to deny it. A policy
    may additionally define ``observe_result(tool_name, arguments, result,
    is_error)``; the agent calls that optional method after an allowed
    execution without letting observer failures alter the agent workflow.
    """

    def authorize(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> bool:
        """Return whether the normalized tool call may be executed."""


def _build_flat_prompt(memory: List[Dict[str, str]]) -> str:
    parts = []
    for turn in memory:
        tag = "User" if turn["role"] == "user" else "Assistant"
        parts.append(f"## {tag}\n{turn['content']}")
    return "\n\n".join(parts)


def _compact_response_with_tool_call(
    response: str,
    tool_payload: dict,
    tool_call_match,
    reasoning_cap: int,
) -> str:
    if not tool_call_match:
        return response
    tc_xml = f"<tool_call>{json.dumps(tool_payload)}</tool_call>"
    prefix = response[: tool_call_match.start()]
    if len(prefix) > reasoning_cap:
        prefix = prefix[:reasoning_cap] + "\n...[reasoning trimmed]...\n"
    return prefix + tc_xml


def _parse_l0_compression_hints(preplan_result: str) -> dict:
    """Extract l0_compression_hints from a preplan JSON result."""
    try:
        body = preplan_result
        if body.startswith("[PREPLAN]"):
            body = body[body.index("\n") + 1:]
        data = json.loads(body)
        hints = data.get("l0_compression_hints", {})
        return hints if isinstance(hints, dict) else {}
    except Exception:
        return {}


def _phase_error_message(
    tool_name: str,
    *,
    preplan_called: bool,
    plan_called: bool,
    l0_called: set,
    l0_required: set,
    preplan_tool: str,
    plan_tool: str,
    l0_discovery_tools: set,
) -> Optional[str]:
    if tool_name == preplan_tool:
        return None
    if tool_name in l0_discovery_tools:
        if not preplan_called:
            return (
                "[PHASE ERROR] Call 0_preplan_decision first "
                "to triage the question before L0 searches."
            )
        return None
    if tool_name == plan_tool:
        missing = l0_required - l0_called
        if missing:
            return (
                "[PHASE ERROR] Cannot call planner yet. "
                f"You must first call these L0 tools: {', '.join(sorted(missing))}."
            )
        return None
    if not plan_called:
        missing = l0_required - l0_called
        if missing:
            return (
                f"[PHASE ERROR] Tool '{tool_name}' is not available yet. "
                f"Complete PHASE 1 first: call {', '.join(sorted(missing))}, "
                "then call 0_plan_search_strategy."
            )
        if not l0_required and preplan_called:
            return None
        return (
            f"[PHASE ERROR] Tool '{tool_name}' is not available yet. "
            "You must call 0_plan_search_strategy first (PHASE 2) before "
            "using the execution tools."
        )
    return None


async def run_agent_query(
    user_message: str,
    *,
    memory: Optional[List[Dict[str, str]]] = None,
    timeout: int | None = None,
    on_step: Optional[Callable[[dict], None]] = None,
    max_tool_iterations: int | None = None,
    system_prompt_override: str | None = None,
    planner_system_prompt_module: str | None = None,
    pre_resolved_workflow: bool = False,
    require_fresh_plan: bool = False,
    enable_memory_compaction: bool = True,
    model_override: str | None = None,
    tool_call_policy: ToolCallPolicy | None = None,
) -> AgentRunResult:
    """Run one full user query through the main agent API.

    The optional workflow overrides are used only by embedded callers that
    already performed deterministic ID/scope resolution. Defaults preserve the
    ordinary interactive query workflow exactly. When
    ``planner_system_prompt_module`` is non-``None``, its value is injected
    deterministically into calls to ``0_plan_search_strategy`` as a
    lower-priority supplement to the established planner and evaluator system
    prompts; it does not alter the main agent system prompt. A pre-resolved continuation
    may set ``require_fresh_plan=True`` to retain its existing conversation and
    resolved identifiers while resetting the Phase-2 gate: discovery remains
    disabled, and no execution tool or model-authored final answer is accepted
    until a fresh successful ``0_plan_search_strategy`` call completes.
    ``enable_memory_compaction``
    may be disabled by an embedded workflow that must preserve exact evidence
    identifiers across turns; immediate per-tool result compaction is not
    affected. ``tool_call_policy`` is an
    optional caller boundary: its synchronous ``authorize(tool_name,
    normalized_arguments) -> bool`` runs immediately before MCP execution.
    A denied call is returned to the model as a workflow authorization error,
    so the model may correct its tool or arguments. Policies may optionally
    expose ``observe_result(tool_name, normalized_arguments, raw_result,
    is_error)`` for post-execution auditing. Every authorized tool call is
    executed by the SRD-46 MCP manager; embedded callers cannot inject an
    additional analysis-pipeline tool surface.
    """
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import MAX_TOOL_ITERATIONS, MAX_TURN_SECONDS, MODEL, REASONING_CAP
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import call_argo
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import (
        MCPManager,
        L0_DISCOVERY_TOOLS,
        PLAN_TOOL_NAME,
        PREPLAN_TOOL_NAME,
        SYSTEM_PROMPT,
        TOOL_CALL_PATTERN,
        coerce_tool_calls,
        extract_tool_call,
        infer_required_l0_tools,
        mark_plans_complete,
    )
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_tools.tool_arg_normalizer import normalize_tool_arguments
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_tools.compactor import compact_memory, compact_l0_with_hints, compact_tool_result_immediately

    if require_fresh_plan and not pre_resolved_workflow:
        raise ValueError(
            "require_fresh_plan=True is valid only when "
            "pre_resolved_workflow=True"
        )

    conversation = memory if memory is not None else []
    conversation.append({"role": "user", "content": user_message})
    tool_history: list[dict] = []
    compactor_events: list[dict] = []
    model_history: list[dict] = []
    response = ""
    turn_t0 = time.time()
    turn_timeout = timeout if timeout is not None else MAX_TURN_SECONDS
    max_iterations = max_tool_iterations if max_tool_iterations is not None else MAX_TOOL_ITERATIONS
    if max_iterations <= 0:
        raise ValueError("max_tool_iterations must be a positive integer")
    compactor_run_id = uuid.uuid4().hex
    compactor_run_token = _compactor_run_id_var.set(compactor_run_id)
    effective_system_prompt = (
        SYSTEM_PROMPT
        if system_prompt_override is None
        else str(system_prompt_override)
    )
    effective_planner_system_prompt_module = (
        None
        if planner_system_prompt_module is None
        else str(planner_system_prompt_module).strip()
    )

    def _apply_planner_system_prompt_module(
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply only a host-configured module, never model-authored text."""
        if tool_name == PLAN_TOOL_NAME:
            for key in (
                "system_prompt_module",
                "planner_system_prompt_module",
                "planning_system_prompt_module",
                "prompt_module",
            ):
                tool_args.pop(key, None)
            if effective_planner_system_prompt_module:
                tool_args["system_prompt_module"] = (
                    effective_planner_system_prompt_module
                )
        return tool_args

    def _call_model(
        prompt: str,
        system: str,
        *args: Any,
        reason: str,
        iteration: int,
        **kwargs: Any,
    ) -> str:
        """Call Argo while retaining the exact model-round context."""
        started_at = time.time()
        record: dict[str, Any] = {
            "prompt": prompt,
            "system": system,
            "response": None,
            "reason": reason,
            "iteration": iteration,
            "timestamp": started_at,
            "model": str(model_override or kwargs.get("model") or MODEL),
        }
        try:
            if model_override:
                kwargs.setdefault("model", str(model_override))
            model_response = call_argo(prompt, system, *args, **kwargs)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        else:
            record["response"] = model_response
            return model_response
        finally:
            record["duration_s"] = time.time() - started_at
            model_history.append(record)

    _compactor_capture.drain(run_id=compactor_run_id)

    wrap_up_messages = [
        ("[SYSTEM NOTE - First Notice: time budget exceeded] "
         "You have exceeded the time budget for this turn. "
         "You have 3 more chances (including this one) to respond. "
         "You may make one more critical tool call if truly needed, "
         "but start wrapping up. If your data is sufficient, produce a "
         "final answer now. If incomplete, say so and suggest a follow-up."),
        ("[SYSTEM NOTE - Second Notice: time budget exceeded] "
         "This is your second warning. You have ONE more chance after this. "
         "If you still need one critical tool call, make it now - but your "
         "NEXT response MUST be a final answer with no tool calls."),
        ("[SYSTEM NOTE - FINAL NOTICE, time budget exceeded] "
         "This is your LAST chance. You MUST produce a final answer NOW. "
         "Any tool call will be discarded."),
    ]
    wrap_up_warnings = 0

    preplan_called = bool(pre_resolved_workflow)
    l0_called: set = set()
    l0_required: set = (
        set() if pre_resolved_workflow else set(L0_DISCOVERY_TOOLS)
    )
    l0_compression_hints: dict = {}
    l0_compression_done = bool(pre_resolved_workflow)
    fresh_plan_pending = bool(pre_resolved_workflow and require_fresh_plan)
    plan_called = bool(pre_resolved_workflow and not fresh_plan_pending)
    plan_completed_iteration: int | None = None

    def _planning_gate_failure(reason: str) -> AgentRunResult:
        """Return a deterministic failure instead of unplanned model prose."""
        failure = (
            "[WORKFLOW PLANNING ERROR] This pre-resolved continuation "
            "required a fresh successful 0_plan_search_strategy call before "
            "execution or a final answer, but the planning gate remained "
            f"incomplete ({reason})."
        )
        conversation.append({"role": "assistant", "content": failure})
        return AgentRunResult(
            answer=failure,
            memory=conversation,
            tool_history=tool_history,
            compactor_events=compactor_events,
            elapsed=time.time() - turn_t0,
            model_history=model_history,
        )

    def _current_phase_error(
        tool_name: str,
        *,
        iteration: int | None = None,
    ) -> Optional[str]:
        if (
            pre_resolved_workflow
            and not fresh_plan_pending
            and tool_name in {
                PREPLAN_TOOL_NAME,
                PLAN_TOOL_NAME,
                *L0_DISCOVERY_TOOLS,
            }
        ):
            return (
                "[WORKFLOW MODE ERROR] Deterministic compound/scope resolution "
                "and planning are already complete for this embedded run. Use "
                "the scoped SRD46 evidence tools directly."
            )
        if pre_resolved_workflow and tool_name in {
            PREPLAN_TOOL_NAME,
            *L0_DISCOVERY_TOOLS,
        }:
            return (
                "[WORKFLOW MODE ERROR] Deterministic compound/scope resolution "
                "is already complete for this embedded run. Use the resolved "
                "scope rather than restarting discovery."
            )
        if pre_resolved_workflow and tool_name == PLAN_TOOL_NAME:
            if fresh_plan_pending and not plan_called:
                return None
            return (
                "[WORKFLOW MODE ERROR] Planning is already complete for this "
                "embedded run. Use the scoped SRD46 evidence tools directly."
            )
        if fresh_plan_pending and (
            not plan_called
            or (
                iteration is not None
                and plan_completed_iteration == iteration
            )
        ):
            if plan_called:
                return (
                    f"[PHASE ERROR] Tool '{tool_name}' cannot run in the same "
                    "model round as 0_plan_search_strategy. Consume the "
                    "successful planner result, then issue execution calls in "
                    "a subsequent round."
                )
            return (
                f"[PHASE ERROR] Tool '{tool_name}' is not available yet. "
                "This continuation must first complete a fresh successful "
                "0_plan_search_strategy call (PHASE 2)."
            )
        return _phase_error_message(
            tool_name,
            preplan_called=preplan_called,
            plan_called=plan_called,
            l0_called=l0_called,
            l0_required=l0_required,
            preplan_tool=PREPLAN_TOOL_NAME,
            plan_tool=PLAN_TOOL_NAME,
            l0_discovery_tools=L0_DISCOVERY_TOOLS,
        )

    def _authorization_error(
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str | None:
        if tool_call_policy is None:
            return None
        try:
            decision = tool_call_policy.authorize(tool_name, dict(tool_args))
        except Exception as exc:
            log.warning(
                "[!] Tool authorization policy failed closed for %s: %s",
                tool_name,
                exc,
            )
            return (
                "[WORKFLOW AUTHORIZATION ERROR] "
                f"Tool '{tool_name}' was denied because the caller's "
                "authorization policy raised "
                f"{type(exc).__name__}: {exc}. Revise the tool or arguments "
                "and continue."
            )
        if not isinstance(decision, bool):
            log.warning(
                "[!] Tool authorization policy returned non-bool for %s: %r",
                tool_name,
                decision,
            )
            return (
                "[WORKFLOW AUTHORIZATION ERROR] "
                f"Tool '{tool_name}' was denied because the caller's "
                "authorization policy returned a non-boolean decision. "
                "Revise the tool or arguments and continue."
            )
        if decision:
            return None
        detail = ""
        explainer = getattr(tool_call_policy, "denial_reason", None)
        if callable(explainer):
            try:
                reason = explainer(tool_name, dict(tool_args))
            except Exception as exc:
                log.warning(
                    "[!] Tool authorization denial explainer failed for %s: %s",
                    tool_name,
                    exc,
                )
            else:
                if isinstance(reason, str) and reason.strip():
                    detail = f" Reason: {reason.strip()[:500]}."
        return (
            "[WORKFLOW AUTHORIZATION ERROR] "
            f"Tool '{tool_name}' was denied by the caller's authorization "
            f"policy.{detail} Revise the tool or arguments and continue."
        )

    def _observe_tool_result(
        tool_name: str,
        tool_args: dict[str, Any],
        raw_result: str,
        tool_errored: bool,
    ) -> None:
        if tool_call_policy is None:
            return
        observer = getattr(tool_call_policy, "observe_result", None)
        if not callable(observer):
            return
        try:
            observer(
                tool_name,
                dict(tool_args),
                raw_result,
                bool(tool_errored),
            )
        except Exception as exc:
            log.warning(
                "[!] Tool result observer failed for %s: %s",
                tool_name,
                exc,
            )

    async def _call_tool_with_policy(
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[str, bool, bool]:
        authorization_error = _authorization_error(tool_name, tool_args)
        if authorization_error is not None:
            log.warning("[!] %s", authorization_error)
            return authorization_error, True, True

        raw_tool_result = await mcp_manager.call_tool_safe(tool_name, tool_args)
        raw_result = raw_tool_result.content[0].text
        tool_errored = bool(getattr(raw_tool_result, "is_error", False))
        _observe_tool_result(tool_name, tool_args, raw_result, tool_errored)
        return raw_result, tool_errored, False

    mcp_manager = MCPManager()
    await mcp_manager.setup()
    try:
        for iteration in range(1, max_iterations + 1):
            elapsed_total = time.time() - turn_t0
            if elapsed_total > turn_timeout and wrap_up_warnings == 0:
                wrap_up_warnings = 1
                log.warning("[!] Time limit reached (%.1fs > %ds), wrap-up warning %d/3.",
                            elapsed_total, turn_timeout, wrap_up_warnings)
                conversation.append({"role": "user", "content": wrap_up_messages[0]})
            elif elapsed_total > turn_timeout and wrap_up_warnings >= len(wrap_up_messages):
                log.warning("[!] All wrap-up warnings exhausted (%.1fs). Hard stop.", elapsed_total)
                break

            iter_t0 = time.time()
            flat_prompt = _build_flat_prompt(conversation)
            log.info("[>] agent iter=%d prompt_len=%d memory_turns=%d elapsed=%.1fs",
                     iteration, len(flat_prompt), len(conversation), elapsed_total)

            response = _call_model(
                flat_prompt,
                effective_system_prompt,
                reason="agent_iteration",
                iteration=iteration,
            )
            tool_calls = coerce_tool_calls(extract_tool_call(response))

            # Embedded pre-resolved workflows depend on evidence calls before
            # they may emit an empty estimation result.  If the model clearly
            # attempted a tool call but produced malformed XML/JSON, do not
            # misclassify that text as a final answer; keep the same memory and
            # give it one ordinary in-turn correction opportunity.  The
            # default interactive workflow retains its established behavior.
            if (
                pre_resolved_workflow
                and not tool_calls
                and "<tool_call>" in response
                and iteration < max_iterations
            ):
                conversation.append({"role": "assistant", "content": response})
                conversation.append({
                    "role": "user",
                    "content": (
                        "[WORKFLOW TOOL-CALL FORMAT ERROR] Your preceding "
                        "<tool_call> could not be parsed. Reissue exactly one "
                        "valid JSON object or JSON array inside the tool_call "
                        "tags, with no extra braces or trailing text."
                    ),
                })
                continue

            if not tool_calls:
                plan_skippable = (
                    not fresh_plan_pending
                    and not l0_required
                    and preplan_called
                )
                if not plan_called and not plan_skippable:
                    if fresh_plan_pending:
                        if iteration >= max_iterations:
                            return _planning_gate_failure(
                                "the iteration limit was reached"
                            )
                        nudge = (
                            "[SYSTEM NOTE] You have NOT completed the mandatory workflow. "
                            "You must call a fresh 0_plan_search_strategy (Phase 2) and then use "
                            "the execution tools (Phase 3) to retrieve the actual data "
                            "before giving a final answer. Continue now."
                        )
                    elif iteration < max_iterations - 1:
                        # Preserve the ordinary query agent's established
                        # final-iteration behavior.  The stricter deterministic
                        # failure applies only to the opt-in continuation gate.
                        nudge = (
                            "[SYSTEM NOTE] You have NOT completed the mandatory workflow. "
                            "You must call 0_plan_search_strategy (Phase 2) and then use "
                            "the execution tools (Phase 3) to retrieve the actual data "
                            "before giving a final answer. Continue now."
                        )
                    else:
                        nudge = None
                    if nudge is not None:
                        log.warning(
                            "[!] Agent answered before planner ran. Nudging to continue."
                        )
                        conversation.append({"role": "assistant", "content": response})
                        conversation.append({"role": "user", "content": nudge})
                        continue
                conversation.append({"role": "assistant", "content": response})
                mark_plans_complete(conversation)
                return AgentRunResult(
                    answer=response,
                    memory=conversation,
                    tool_history=tool_history,
                    compactor_events=compactor_events,
                    elapsed=time.time() - turn_t0,
                    model_history=model_history,
                )

            if wrap_up_warnings > 0:
                wrap_up_warnings += 1
                if wrap_up_warnings > len(wrap_up_messages):
                    log.warning("[!] Tool call after final warning. Forcing final answer.")
                    if fresh_plan_pending and not plan_called:
                        return _planning_gate_failure(
                            "the time budget was exhausted"
                        )
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({
                        "role": "user",
                        "content": (
                            "[SYSTEM NOTE] All tool calls discarded — time budget exhausted. "
                            "Synthesize a COMPLETE final answer from the data you have already "
                            "gathered. Summarize all findings. Do NOT leave sentences unfinished."
                        ),
                    })
                    response = _call_model(
                        _build_flat_prompt(conversation),
                        effective_system_prompt,
                        reason="time_budget_final_after_discarded_tool_call",
                        iteration=iteration,
                    )
                    conversation.append({"role": "assistant", "content": response})
                    mark_plans_complete(conversation)
                    return AgentRunResult(
                        answer=response,
                        memory=conversation,
                        tool_history=tool_history,
                        compactor_events=compactor_events,
                        elapsed=time.time() - turn_t0,
                        model_history=model_history,
                    )

                if wrap_up_warnings >= 3:
                    # Warning 2+: block tool execution, force final answer
                    log.warning("[!] Blocking tool execution at warning %d/3. "
                                "Forcing final answer.", wrap_up_warnings - 1)
                    if fresh_plan_pending and not plan_called:
                        return _planning_gate_failure(
                            "the time budget was exhausted"
                        )
                    fake_results = "; ".join(
                        f'{c.get("name", "?")}: [DISCARDED — time budget exceeded]'
                        for c in tool_calls
                    )
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({
                        "role": "user",
                        "content": (
                            f"[SYSTEM NOTE] Tool calls blocked (time budget). "
                            f"Results: {fake_results}. "
                            "Synthesize a COMPLETE final answer from the data you "
                            "have already gathered. Summarize all findings. "
                            "Do NOT leave sentences unfinished."
                        ),
                    })
                    response = _call_model(
                        _build_flat_prompt(conversation),
                        effective_system_prompt,
                        reason="time_budget_final_after_blocked_tool_call",
                        iteration=iteration,
                    )
                    conversation.append({"role": "assistant", "content": response})
                    mark_plans_complete(conversation)
                    return AgentRunResult(
                        answer=response,
                        memory=conversation,
                        tool_history=tool_history,
                        compactor_events=compactor_events,
                        elapsed=time.time() - turn_t0,
                        model_history=model_history,
                    )

            log.info("   [iter %d] Tool call(s): %s",
                     iteration, ", ".join(call.get("name", "?") for call in tool_calls))

            tc_match = TOOL_CALL_PATTERN.search(response)
            parsed_payloads = tool_calls
            if tc_match:
                try:
                    parsed_payloads = coerce_tool_calls(json.loads(tc_match.group(1)))
                except Exception:
                    parsed_payloads = tool_calls

            # --- decide parallel vs sequential execution ---
            # Tools whose results gate subsequent phases — must run alone.
            _NEVER_PARALLEL = {
                PREPLAN_TOOL_NAME, PLAN_TOOL_NAME,
                "build_system_catalog",
            }

            tool_names_this_turn = [
                tc.get("name", "") for tc in tool_calls
            ]
            has_phase_errors = any(
                _current_phase_error(n, iteration=iteration)
                for n in tool_names_this_turn
            )
            can_parallel = (
                len(tool_calls) > 1
                and not has_phase_errors
                and not any(n in _NEVER_PARALLEL for n in tool_names_this_turn)
            )

            if can_parallel:
                log.info("   [iter %d] Running %d tools in PARALLEL: %s",
                         iteration, len(tool_calls),
                         ", ".join(tool_names_this_turn))

            # --- execute (parallel or sequential) ---
            if can_parallel:
                all_args = [
                    _apply_planner_system_prompt_module(
                        tc.get("name", ""),
                        normalize_tool_arguments(
                            tc.get("name", ""),
                            tc.get("arguments", {}),
                        ),
                    )
                    for tc in tool_calls
                ]
                async def _timed_call(
                    tool_name: str,
                    tool_args: dict[str, Any],
                ) -> tuple[str, bool, bool, float]:
                    _t0 = time.time()
                    raw, errored, authorization_error = (
                        await _call_tool_with_policy(tool_name, tool_args)
                    )
                    return (
                        raw,
                        errored,
                        authorization_error,
                        time.time() - _t0,
                    )

                timed_results = await asyncio.gather(*(
                    _timed_call(name, args)
                    for name, args in zip(tool_names_this_turn, all_args)
                ))
                parallel_done_at = time.time() - turn_t0

                for tool_index, (
                    tool_call,
                    (
                        raw_result,
                        tool_errored,
                        authorization_error,
                        tool_duration,
                    ),
                    tool_args,
                ) in enumerate(
                    zip(tool_calls, timed_results, all_args)
                ):
                    tool_name = tool_call.get("name", "")
                    if tool_errored:
                        log.warning("[!] Tool error (parallel): %s — %s",
                                    tool_name, raw_result[:200])
                        memory_result = raw_result
                        immediate_compacted = False
                        compaction_kind = None
                    else:
                        memory_result, immediate_compacted, compaction_kind = (
                            compact_tool_result_immediately(tool_name, raw_result)
                        )
                    if tool_name in L0_DISCOVERY_TOOLS and not tool_errored:
                        l0_called.add(tool_name)

                    payload = (
                        parsed_payloads[tool_index]
                        if tool_index < len(parsed_payloads)
                        else tool_call
                    )
                    conversation.append({
                        "role": "assistant",
                        "content": _compact_response_with_tool_call(
                            response, payload, tc_match, REASONING_CAP,
                        ),
                    })
                    conversation.append({
                        "role": "user",
                        "content": f"<tool_result>\n{memory_result}\n</tool_result>",
                    })

                    step = {
                        "iteration": iteration,
                        "tool": tool_name or "?",
                        "arguments": tool_args,
                        "result_chars": len(raw_result),
                        "result_full": raw_result,
                        "display_result": memory_result,
                        "display_result_chars": len(memory_result),
                        "memory_result": memory_result,
                        "immediate_compacted": immediate_compacted,
                        "compaction_kind": compaction_kind,
                        "elapsed_at": parallel_done_at,
                        "duration_s": tool_duration,
                        "parallel": True,
                        "parallel_group": len(tool_calls),
                        "is_error": tool_errored,
                    }
                    if authorization_error:
                        step.update({
                            "authorization_error": True,
                            "error_kind": "workflow_authorization",
                        })
                    tool_history.append(step)

            else:
                for tool_index, tool_call in enumerate(tool_calls):
                    tool_name = tool_call.get("name", "")
                    phase_error = _current_phase_error(
                        tool_name,
                        iteration=iteration,
                    )

                    tool_errored = False
                    authorization_error = False
                    tool_t0 = time.time()
                    if phase_error:
                        raw_result = phase_error
                        memory_result = phase_error
                        immediate_compacted = False
                        compaction_kind = None
                        tool_errored = True
                        log.warning("[!] %s", phase_error)
                    else:
                        tool_args = _apply_planner_system_prompt_module(
                            tool_name,
                            normalize_tool_arguments(
                                tool_name,
                                tool_call.get("arguments", {}),
                            ),
                        )
                        (
                            raw_result,
                            tool_errored,
                            authorization_error,
                        ) = await _call_tool_with_policy(
                            tool_name,
                            tool_args,
                        )
                        if tool_errored:
                            log.warning("[!] Tool error: %s — %s",
                                        tool_name, raw_result[:200])
                            memory_result = raw_result
                            immediate_compacted = False
                            compaction_kind = None
                        else:
                            memory_result, immediate_compacted, compaction_kind = (
                                compact_tool_result_immediately(tool_name, raw_result)
                            )
                        if not tool_errored:
                            if tool_name == PREPLAN_TOOL_NAME:
                                preplan_called = True
                                l0_required = infer_required_l0_tools(raw_result)
                                l0_compression_hints = _parse_l0_compression_hints(raw_result)
                                log.info("[PG] Preplan set l0_required=%s, l0_hints=%s",
                                         sorted(l0_required) if l0_required else "(none)",
                                         list(l0_compression_hints.keys()) if l0_compression_hints else "(none)")
                            elif tool_name in L0_DISCOVERY_TOOLS:
                                l0_called.add(tool_name)
                            elif tool_name == PLAN_TOOL_NAME:
                                plan_called = True
                                if fresh_plan_pending:
                                    plan_completed_iteration = iteration

                    payload = (
                        parsed_payloads[tool_index]
                        if tool_index < len(parsed_payloads)
                        else tool_call
                    )
                    conversation.append({
                        "role": "assistant",
                        "content": _compact_response_with_tool_call(
                            response, payload, tc_match, REASONING_CAP,
                        ),
                    })
                    conversation.append({
                        "role": "user",
                        "content": f"<tool_result>\n{memory_result}\n</tool_result>",
                    })

                    tool_duration = time.time() - tool_t0
                    step = {
                        "iteration": iteration,
                        "tool": tool_name or "?",
                        "arguments": tool_args if not phase_error else tool_call.get("arguments", {}),
                        "result_chars": len(raw_result),
                        "result_full": raw_result,
                        "display_result": memory_result,
                        "display_result_chars": len(memory_result),
                        "memory_result": memory_result,
                        "immediate_compacted": immediate_compacted,
                        "compaction_kind": compaction_kind,
                        "elapsed_at": time.time() - turn_t0,
                        "duration_s": tool_duration,
                        "parallel": False,
                        "is_error": tool_errored,
                    }
                    if authorization_error:
                        step.update({
                            "authorization_error": True,
                            "error_kind": "workflow_authorization",
                        })
                    tool_history.append(step)

            if (not l0_compression_done
                    and preplan_called
                    and l0_required
                    and not (l0_required - l0_called)
                    and l0_compression_hints):
                l0_compression_done = True
                log.info("[PG] L0 complete — running hint-driven compression")
                await compact_l0_with_hints(
                    conversation,
                    l0_compression_hints,
                    argo_fn=lambda prompt, system, *args, **kwargs: _call_model(
                        prompt,
                        system,
                        *args,
                        reason="l0_hint_compaction",
                        iteration=iteration,
                        **kwargs,
                    ),
                )

            if (
                enable_memory_compaction
                and plan_called
                and wrap_up_warnings == 0
            ):
                await compact_memory(
                    conversation,
                    argo_fn=lambda prompt, system, *args, **kwargs: _call_model(
                        prompt,
                        system,
                        *args,
                        reason="memory_compaction",
                        iteration=iteration,
                        **kwargs,
                    ),
                )
            new_events = _compactor_capture.drain(run_id=compactor_run_id)
            for event in new_events:
                event["after_iteration"] = iteration
            compactor_events.extend(new_events)

            if on_step:
                on_step({
                    "tool_history": tool_history,
                    "compactor_events": new_events,
                    "iteration": iteration,
                    "elapsed": time.time() - turn_t0,
                })

            log.info("   [iter %d] completed in %.1fs (total %.1fs)",
                     iteration, time.time() - iter_t0, time.time() - turn_t0)

            if wrap_up_warnings > 0:
                idx = min(wrap_up_warnings - 1, len(wrap_up_messages) - 1)
                conversation.append({"role": "user", "content": wrap_up_messages[idx]})

        log.warning("[!] Reached limit (elapsed=%.1fs), returning best answer.",
                    time.time() - turn_t0)
        if fresh_plan_pending and not plan_called:
            return _planning_gate_failure(
                "the time or iteration limit was reached"
            )
        if tool_calls:
            conversation.append({"role": "assistant", "content": response})
            conversation.append({
                "role": "user",
                "content": (
                    "[SYSTEM NOTE] Time/iteration limit reached. Synthesize a COMPLETE "
                    "final answer from ALL data gathered. Do NOT leave sentences unfinished."
                ),
            })
            response = _call_model(
                _build_flat_prompt(conversation),
                effective_system_prompt,
                reason="iteration_limit_final_answer",
                iteration=max_iterations,
            )
            conversation.append({"role": "assistant", "content": response})
        mark_plans_complete(conversation)
        return AgentRunResult(
            answer=response,
            memory=conversation,
            tool_history=tool_history,
            compactor_events=compactor_events,
            elapsed=time.time() - turn_t0,
            model_history=model_history,
        )
    finally:
        _compactor_capture.drain(run_id=compactor_run_id)
        _compactor_run_id_var.reset(compactor_run_token)
        await mcp_manager.close()


def run_agent_query_sync(
    user_message: str,
    *,
    memory: Optional[List[Dict[str, str]]] = None,
    timeout: int | None = None,
    on_step: Optional[Callable[[dict], None]] = None,
    max_tool_iterations: int | None = None,
    system_prompt_override: str | None = None,
    planner_system_prompt_module: str | None = None,
    pre_resolved_workflow: bool = False,
    require_fresh_plan: bool = False,
    enable_memory_compaction: bool = True,
    model_override: str | None = None,
    tool_call_policy: ToolCallPolicy | None = None,
) -> AgentRunResult:
    """Synchronous wrapper around the main agent API."""
    return asyncio.run(
        run_agent_query(
            user_message,
            memory=memory,
            timeout=timeout,
            on_step=on_step,
            max_tool_iterations=max_tool_iterations,
            system_prompt_override=system_prompt_override,
            planner_system_prompt_module=planner_system_prompt_module,
            pre_resolved_workflow=pre_resolved_workflow,
            require_fresh_plan=require_fresh_plan,
            enable_memory_compaction=enable_memory_compaction,
            model_override=model_override,
            tool_call_policy=tool_call_policy,
        )
    )


async def agent_turn(
    user_message: str,
    memory: List[Dict[str, str]],
    timeout: int | None = None,
    max_tool_iterations: int | None = None,
) -> str:
    """Compatibility wrapper for the terminal UI."""
    result = await run_agent_query(
        user_message,
        memory=memory,
        timeout=timeout,
        max_tool_iterations=max_tool_iterations,
    )
    return result.answer
