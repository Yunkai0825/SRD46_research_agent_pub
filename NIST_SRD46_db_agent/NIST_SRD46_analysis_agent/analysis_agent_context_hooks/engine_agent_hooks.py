"""
Analysis-agent engine hooks — self-contained ``build_agent_hooks``.
==================================================================
Previously the analysis agent (L0 orchestrator + L1 sub-agent) reached
into the *sibling* query agent for its engine hooks::

    from ....NIST_SRD46_query_agent.query_agent_context_hooks.hook_catalog \\
        import build_agent_hooks

That cross-agent import made the analysis agent un-importable whenever the
query agent's ``query_agent_context_hooks`` package was absent or mid-
refactor.  This module removes that coupling: it builds the same engine
hook collection using **only** the shared ``general_db_query_engine`` and
analysis-local recorder singletons.

The behaviour mirrors the query agent's hooks with two deliberate
differences:

1. No query-tool-specific guidance hooks are bound (the analysis agent's
   only meaningful tool is ``dispatch_l1_pipeline`` / the L1 pipeline
   tools, none of which need entity/quick-fact guidance).  Callers pass
   ``guidance_hooks=[]``.
2. No verdict / final-context lifecycle runner is bound here — the L0
   orchestrator runs its own verdict pass explicitly after ``agent_turn``.

Public API
----------
``build_agent_hooks(history=None, stats=None, reasoning=None, *,
                    working_memory_loader=None, compactor=None,
                    batch_summary=None, batch_validator=None,
                    guidance_hooks=None) -> AnalysisAgentHooks``
    Returns an :class:`AnalysisAgentHooks` whose ``.engine_hooks`` is the
    compiled dispatch map consumed by ``agent_turn(..., hooks=...)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# ── Shared engine: hook primitives ──────────────────────────────────
from ...general_db_query_engine.general_argo_engine_helpers.engine_hooks_anchors import (
    AgentHookCollection,
    EngineHooks,
    bind_hook,
    build_agent_lifecycle_bindings,
    compile_hooks,
)

# ── Shared engine: base recorder implementations ────────────────────
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks.history_tracking_hooks import (
    HistoryRecorder,
)
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks.stats_references_tracking_hooks import (
    StatsRecorder,
)
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks.reasoning_token_tracking_hooks import (
    ReasoningTokenTracker,
)

# ── Shared engine: context-management hook callables ────────────────
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks.context_cleanup_compactor_hooks import (
    compact_tool_calls_for_memory,
    stage_compact_batch,
    trim_old_tool_results,
)
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks.self_compactor_interactive_hooks import (
    build_compaction_reminder,
    compact_memory,
    parse_compaction_guidance,
)
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks.time_budget_reminder_hooks import (
    TimeBudgetTracker,
)

# ── Shared engine: anchor catalogs ──────────────────────────────────
from ...general_db_query_engine.general_hooks_management_helpers.general_context_hooks import (
    _context_hooks_anchors_catalog as ctx_anchor,
)
from ...general_db_query_engine.general_hooks_management_helpers.general_memory_management_tools_hooks_helpers import (
    _memory_hooks_anchors_catalog as mem_anchor,
)
from ...general_db_query_engine.general_tool_management_helpers import (
    _tool_hooks_anchors_catalog as tool_anchor,
)
from ...general_db_query_engine.general_tool_management_helpers.general_tool_options_interactive_hooks import (
    validate_batch_args,
)


# ════════════════════════════════════════════════════════════════════
#  Analysis-local engine-anchor recorder singletons
#  (base general-engine recorders — same classes the query agent's
#  thin subclasses wrap, so behaviour is identical but namespace-local)
# ════════════════════════════════════════════════════════════════════

analysis_history_recorder = HistoryRecorder()
analysis_stats_recorder = StatsRecorder()
analysis_reasoning_tracker = ReasoningTokenTracker()


def _compile_engine_hooks(
    *,
    history,
    stats,
    reasoning,
    working_memory_loader=None,
    compactor=None,
    batch_summary=None,
    batch_validator=None,
    verdict_runner=None,
    final_context_saver=None,
    anchors=None,
    guidance_hooks=None,
) -> EngineHooks:
    """Compile the engine hook dispatch map for an analysis agent turn.

    Mirrors the query agent's compiler but binds no query-tool guidance
    and (by default) no verdict/final-context lifecycle runner.
    """
    h = history
    s = stats
    r = reasoning
    effective_compactor = compactor or compact_memory

    bindings = [
        bind_hook(
            r.log_reasoning_from_response,
            ctx_anchor.SYNC_LLM_RESPONSE_AFTER.anchor_type,
            ctx_anchor.SYNC_COMPACTION_GUIDANCE_RESPONSE.anchor_type,
            ctx_anchor.ASYNC_LLM_RESPONSE_AFTER.anchor_type,
        ),
        bind_hook(
            s.log_tool_result,
            tool_anchor.SYNC_TOOL_RESULT_RECORDED.anchor_type,
            tool_anchor.ASYNC_TOOL_RESULT_RECORDED.anchor_type,
        ),
        bind_hook(
            h.log_tool_call,
            tool_anchor.SYNC_TOOL_CALL_RECORDED.anchor_type,
            tool_anchor.ASYNC_TOOL_CALL_RECORDED.anchor_type,
        ),
        bind_hook(
            h.log_error,
            tool_anchor.SYNC_TOOL_ERROR_RECORDED.anchor_type,
            tool_anchor.ASYNC_TOOL_ERROR_RECORDED.anchor_type,
        ),
        bind_hook(
            h.log_validation_block,
            tool_anchor.SYNC_TOOL_VALIDATION_BLOCKED.anchor_type,
        ),
        bind_hook(
            h.log_purpose_tasks_error,
            tool_anchor.SYNC_TOOL_PURPOSE_ERROR_RECORDED.anchor_type,
            tool_anchor.ASYNC_TOOL_PURPOSE_ERROR_RECORDED.anchor_type,
        ),
        bind_hook(
            h.log_stage_compaction,
            tool_anchor.SYNC_STAGE_COMPACTION_RECORDED.anchor_type,
        ),
        bind_hook(
            h.log_compaction,
            ctx_anchor.SYNC_COMPACTION_RECORDED.anchor_type,
            ctx_anchor.SYNC_COMPACTION_SKIPPED.anchor_type,
        ),
        bind_hook(
            s.log_compaction,
            ctx_anchor.SYNC_COMPACTION_STATS_RECORDED.anchor_type,
        ),
        bind_hook(
            lambda timeout, thresholds, max_warnings, **_: TimeBudgetTracker(
                timeout=timeout,
                thresholds=list(thresholds),
                max_warnings=max_warnings,
            ),
            ctx_anchor.SYNC_TIME_BUDGET_TRACKER_CREATE.anchor_type,
            name="build_time_budget_tracker",
        ),
        bind_hook(
            lambda tracker, elapsed, memory, **_: tracker.check_and_inject_warnings(elapsed, memory),
            ctx_anchor.SYNC_TIME_BUDGET_WARNINGS_APPLY.anchor_type,
            name="apply_time_budget_warnings",
        ),
        bind_hook(
            lambda tracker, elapsed_s, **_: tracker.credit(elapsed_s),
            ctx_anchor.SYNC_TIME_BUDGET_CREDIT_TOOL.anchor_type,
            name="credit_untimed_tool_time",
        ),
        bind_hook(
            lambda **_: working_memory_loader() if working_memory_loader else None,
            mem_anchor.SYNC_WORKING_MEMORY_RENDER.anchor_type,
            mem_anchor.ASYNC_WORKING_MEMORY_RENDER.anchor_type,
            name="render_working_memory",
        ),
        bind_hook(
            lambda tool_calls, deferred_count, **_: compact_tool_calls_for_memory(tool_calls, deferred_count),
            tool_anchor.SYNC_TOOL_CALLS_MEMORY_COMPACT.anchor_type,
            tool_anchor.ASYNC_TOOL_CALLS_MEMORY_COMPACT.anchor_type,
            name="compact_tool_calls_for_memory",
        ),
        bind_hook(
            lambda tool_calls, result_parts, note_chars, **_: stage_compact_batch(
                tool_calls, result_parts, note_chars=note_chars,
            ),
            tool_anchor.SYNC_STAGE_COMPACTION_BUILD.anchor_type,
            name="stage_compact_batch",
        ),
        bind_hook(
            lambda total_chars, iteration, **_: build_compaction_reminder(total_chars, iteration),
            ctx_anchor.SYNC_COMPACTION_REMINDER_BUILD.anchor_type,
            name="build_compaction_reminder",
        ),
        bind_hook(
            lambda guidance_response, **_: parse_compaction_guidance(guidance_response),
            ctx_anchor.SYNC_COMPACTION_GUIDANCE_PARSE.anchor_type,
            name="parse_compaction_guidance",
        ),
        bind_hook(
            lambda memory, argo_fn, purpose="", tasks="", **_: effective_compactor(
                memory, argo_fn, purpose=purpose, tasks=tasks,
            ),
            ctx_anchor.SYNC_COMPACTION_EXECUTE.anchor_type,
            ctx_anchor.ASYNC_COMPACTION_EXECUTE.anchor_type,
            name="execute_context_compaction",
        ),
        bind_hook(
            lambda memory, keep_recent, preview_chars, **_: trim_old_tool_results(
                memory,
                keep_recent=keep_recent,
                preview_chars=preview_chars,
            ),
            ctx_anchor.SYNC_COMPACTION_TRIM_FALLBACK.anchor_type,
            ctx_anchor.ASYNC_COMPACTION_TRIM_FALLBACK.anchor_type,
            name="trim_old_tool_results",
        ),
    ]
    if batch_summary is not None:
        bindings.append(bind_hook(
            lambda tool_calls, result_parts, **_: batch_summary(tool_calls, result_parts),
            tool_anchor.SYNC_BATCH_SUMMARY_BUILD.anchor_type,
            name="build_batch_summary",
        ))
    # Generic malformed-arg validation for every batch (single calls
    # included).  Auto-fixes coercible mistakes in place and blocks with
    # per-tool guidance otherwise, so the agent reacts by correcting its
    # arguments instead of executing a silently-mangled call.  Bound
    # BEFORE any custom batch_validator so a domain validator's non-None
    # verdict takes precedence (anchor returns the last non-None result).
    bindings.append(bind_hook(
        lambda tool_calls, tools, engine_hooks=None, **_: validate_batch_args(
            tool_calls, tools,
        ),
        tool_anchor.SYNC_BATCH_PRE_VALIDATE.anchor_type,
        name="validate_batch_arg_schema",
    ))
    if batch_validator is not None:
        bindings.append(bind_hook(
            lambda tool_calls, tools, engine_hooks=None, **_: batch_validator(
                tool_calls, tools, hooks=engine_hooks,
            ),
            tool_anchor.SYNC_BATCH_PRE_VALIDATE.anchor_type,
            name="batch_pre_validate",
        ))

    # Per-tool pre-execution guidance hooks. The analysis agent binds none
    # by default (its tools need no entity/quick-fact guidance), so callers
    # pass ``guidance_hooks=[]``. We never lazy-import query-agent guidance.
    for hook in (guidance_hooks or []):
        hook_name = getattr(hook, "__name__", None) or type(hook).__name__
        bindings.append(bind_hook(
            hook,
            tool_anchor.SYNC_TOOL_GUIDANCE_CHECK.anchor_type,
            name=hook_name,
        ))

    bindings.extend(build_agent_lifecycle_bindings(
        history=history,
        stats=stats,
        reasoning=reasoning,
        verdict_runner=verdict_runner,
        final_context_saver=final_context_saver,
        anchors=anchors,
    ))
    return compile_hooks(bindings)


@dataclass
class AnalysisAgentHooks(AgentHookCollection):
    """Analysis-agent hook collection — compiles general-engine hooks."""

    history: HistoryRecorder = field(default_factory=lambda: analysis_history_recorder)
    stats: StatsRecorder = field(default_factory=lambda: analysis_stats_recorder)
    reasoning: ReasoningTokenTracker = field(default_factory=lambda: analysis_reasoning_tracker)
    working_memory_loader: Callable[[], str] | None = None
    compactor: Callable[..., Any] | None = None
    batch_summary: Callable[..., Any] | None = None
    batch_validator: Callable[..., Any] | None = None
    verdict_runner: Callable[..., Any] | None = None
    final_context_saver: Callable[..., Any] | None = None
    guidance_hooks: list | None = None

    def build_engine_hooks(self) -> EngineHooks:
        return _compile_engine_hooks(
            history=self.history,
            stats=self.stats,
            reasoning=self.reasoning,
            working_memory_loader=self.working_memory_loader,
            compactor=self.compactor,
            batch_summary=self.batch_summary,
            batch_validator=self.batch_validator,
            verdict_runner=self.verdict_runner,
            final_context_saver=self.final_context_saver,
            anchors=self.anchors,
            guidance_hooks=self.guidance_hooks,
        )


def build_agent_hooks(
    history=None,
    stats=None,
    reasoning=None,
    *,
    working_memory_loader=None,
    compactor=None,
    batch_summary=None,
    batch_validator=None,
    guidance_hooks=None,
) -> AnalysisAgentHooks:
    """Build the analysis agent's engine hook collection.

    All arguments are optional; the defaults wire the analysis-local
    recorder singletons and no guidance hooks. The returned object's
    ``.engine_hooks`` attribute is the compiled dispatch map passed to
    ``agent_turn(..., hooks=...)``.
    """
    return AnalysisAgentHooks(
        history=history or analysis_history_recorder,
        stats=stats or analysis_stats_recorder,
        reasoning=reasoning or analysis_reasoning_tracker,
        working_memory_loader=working_memory_loader,
        compactor=compactor,
        batch_summary=batch_summary,
        batch_validator=batch_validator,
        guidance_hooks=guidance_hooks,
    )


__all__ = [
    "AnalysisAgentHooks",
    "build_agent_hooks",
    "analysis_history_recorder",
    "analysis_stats_recorder",
    "analysis_reasoning_tracker",
]
