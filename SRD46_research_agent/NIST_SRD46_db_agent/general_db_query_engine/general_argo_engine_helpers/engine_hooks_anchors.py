"""
Engine hook dispatch primitives.
================================
The engine does not define concrete anchors or hook implementations.
It only provides the data structures used by the anchor catalogs and
the dispatch helpers consumed by the ReAct loops.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..general_hooks_management_helpers.general_context_hooks import (
    history_tracking_hooks as _hr_mod,
)

from ..general_hooks_management_helpers.general_context_hooks.stats_references_tracking_hooks import (
    set_active_recorder as _set_active_recorder,
    clear_active_recorder as _clear_active_recorder,
)
from ..general_hooks_management_helpers.general_context_hooks.reasoning_token_tracking_hooks import (
    set_active_reasoning_tracker as _set_active_reasoning,
    clear_active_reasoning_tracker as _clear_active_reasoning,
)

log = logging.getLogger("ENGINE-HOOKS")


@dataclass(frozen=True)
class AnchorPoint:
    """A concrete anchor point declared by one of the anchor catalogs."""

    name: str
    anchor_types: tuple[str, ...]

    @property
    def anchor_type(self) -> str:
        return self.anchor_types[0]


@dataclass(frozen=True)
class AnchorCollection:
    """Named collection of anchor points declared by an anchor catalog."""

    points: Mapping[str, AnchorPoint]

    def get(self, name: str) -> AnchorPoint:
        return self.points[name]

    @property
    def anchor_types(self) -> tuple[str, ...]:
        seen: list[str] = []
        for point in self.points.values():
            for anchor_type in point.anchor_types:
                if anchor_type not in seen:
                    seen.append(anchor_type)
        return tuple(seen)


@dataclass(frozen=True)
class HookBinding:
    """A callback together with the anchor types it applies to."""

    callback: Callable[..., Any]
    anchor_types: tuple[str, ...]
    name: str = ""


EngineHooks = Mapping[str, tuple[Callable[..., Any], ...]]


AGENT_START_TRACKING = AnchorPoint(
    name="agent_start_tracking",
    anchor_types=("agent_start_tracking",),
)
AGENT_FINALIZE_TRACKING = AnchorPoint(
    name="agent_finalize_tracking",
    anchor_types=("agent_finalize_tracking",),
)
AGENT_RECORD_REFERENCES = AnchorPoint(
    name="agent_record_references",
    anchor_types=("agent_record_references",),
)
AGENT_SAVE_FINAL_CONTEXT = AnchorPoint(
    name="agent_save_final_context",
    anchor_types=("agent_save_final_context",),
)
AGENT_RUN_VERDICT = AnchorPoint(
    name="agent_run_verdict",
    anchor_types=("agent_run_verdict",),
)


@dataclass(frozen=True)
class AgentAnchorCollection:
    start_tracking: AnchorPoint = AGENT_START_TRACKING
    finalize_tracking: AnchorPoint = AGENT_FINALIZE_TRACKING
    record_references: AnchorPoint = AGENT_RECORD_REFERENCES
    save_final_context: AnchorPoint = AGENT_SAVE_FINAL_CONTEXT
    run_verdict: AnchorPoint = AGENT_RUN_VERDICT


@dataclass
class AgentHookCollection:
    """Shared agent hook collection with compiled engine hooks."""

    engine_hooks: EngineHooks = field(init=False, default_factory=dict)
    anchors: AgentAnchorCollection = field(default_factory=AgentAnchorCollection)
    history: Any = None
    stats: Any = None
    reasoning: Any = None
    working_memory_loader: Callable[[], str] | None = None
    compactor: Callable[..., Any] | None = None
    batch_summary: Callable[..., Any] | None = None
    verdict_runner: Callable[..., Any] | None = None
    final_context_saver: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        self.rebuild_engine_hooks()

    def build_engine_hooks(self) -> Iterable[HookBinding] | EngineHooks | None:
        return EMPTY_HOOKS

    def rebuild_engine_hooks(self) -> EngineHooks:
        self.engine_hooks = compile_hooks(self.build_engine_hooks())
        return self.engine_hooks


def define_anchor(name: str, *anchor_types: str) -> AnchorPoint:
    """Create an anchor point for use in an anchor catalog."""
    types = tuple(anchor_types) or (name,)
    return AnchorPoint(name=name, anchor_types=types)


def define_anchor_collection(**points: AnchorPoint) -> AnchorCollection:
    """Create a named anchor collection for a catalog."""
    return AnchorCollection(points=dict(points))


def build_agent_lifecycle_bindings(
    *,
    history: Any = None,
    stats: Any = None,
    reasoning: Any = None,
    verdict_runner: Callable[..., Any] | None = None,
    final_context_saver: Callable[..., Any] | None = None,
    anchors: AgentAnchorCollection | None = None,
) -> tuple[HookBinding, ...]:
    """Build generic lifecycle bindings for an agent hook collection."""
    anchor_set = anchors or AgentAnchorCollection()

    def _start_tracking(
        *,
        agent: str,
        prompt: str = "",
        history_out_path: str | Path | None = None,
        stats_out_path: str | Path | None = None,
        reasoning_out_path: str | Path | None = None,
        **_: Any,
    ) -> None:
        if history is not None and history_out_path is not None:
            history.start_run(agent=agent, prompt=prompt, out_path=str(history_out_path))
            # Patch the shared module singleton so react_loop / stats hooks
            # route log_internal_error() to the active agent's recorder.
            _hr_mod.history_recorder = history
        if stats is not None and stats_out_path is not None:
            stats.start_run(agent, out_path=Path(stats_out_path))
            _set_active_recorder(stats)
        if reasoning is not None and reasoning_out_path is not None:
            reasoning.start_run(agent, out_path=str(reasoning_out_path))
            _set_active_reasoning(reasoning)

    def _finalize_tracking(
        *,
        status: str,
        stats_path: str | Path | None = None,
        flush_history: bool = True,
        **_: Any,
    ) -> None:
        if history is not None and flush_history:
            history.set_final_status(status)
            history.flush()
            history.reset()
        if stats is not None:
            if stats_path is not None:
                stats.flush(str(stats_path))
            stats.reset()
            _clear_active_recorder()
        if reasoning is not None:
            reasoning.set_final_status(status)
            reasoning.flush()
            reasoning.reset()
            _clear_active_reasoning()

    def _record_references(*, tool_name: str, raw_result: dict, **_: Any) -> None:
        if stats is None:
            return
        # Core reference tracking — must always run
        stats.log_doi_block_references(tool_name, raw_result)
        stats.log_entity_references(tool_name, raw_result)
        # Raw counters are secondary stats — errors must not block above
        try:
            stats.log_raw_counters(tool_name, raw_result)
        except Exception as exc:
            log.error("log_raw_counters failed for %s: %s", tool_name, exc, exc_info=True)

    def _save_final_context(
        *,
        session_dir: str | Path,
        final_context: str,
        filename: str = "final_full_context.md",
        **_: Any,
    ) -> None:
        if final_context_saver is not None:
            final_context_saver(session_dir, final_context, filename=filename)

    def _run_verdict(*args: Any, **kwargs: Any) -> Any:
        if verdict_runner is None:
            return None
        return verdict_runner(*args, **kwargs)

    return (
        bind_hook(_start_tracking, anchor_set.start_tracking.anchor_type, name="start_tracking"),
        bind_hook(_finalize_tracking, anchor_set.finalize_tracking.anchor_type, name="finalize_tracking"),
        bind_hook(_record_references, anchor_set.record_references.anchor_type, name="record_references"),
        bind_hook(_save_final_context, anchor_set.save_final_context.anchor_type, name="save_final_context"),
        bind_hook(_run_verdict, anchor_set.run_verdict.anchor_type, name="run_verdict"),
    )


def bind_hook(
    callback: Callable[..., Any],
    *anchor_types: str,
    name: str = "",
) -> HookBinding:
    """Declare which anchor types a callback applies to."""
    if not anchor_types:
        raise ValueError("bind_hook() requires at least one anchor type")
    return HookBinding(
        callback=callback,
        anchor_types=tuple(anchor_types),
        name=name or getattr(callback, "__name__", "hook"),
    )


def compile_hooks(
    bindings: Iterable[HookBinding] | EngineHooks | None,
) -> EngineHooks:
    """Compile hook bindings into the dispatch structure used by anchor()."""
    if bindings is None:
        return EMPTY_HOOKS
    if isinstance(bindings, Mapping):
        return bindings

    compiled: dict[str, list[Callable[..., Any]]] = defaultdict(list)
    for binding in bindings:
        for anchor_type in binding.anchor_types:
            compiled[anchor_type].append(binding.callback)
    return {anchor_type: tuple(callbacks) for anchor_type, callbacks in compiled.items()}


def anchor(
    point: AnchorPoint,
    hooks: EngineHooks | None,
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Dispatch a catalog-defined anchor point against the compiled hooks map."""
    if not hooks:
        return None

    result = None
    for anchor_type in point.anchor_types:
        for callback in hooks.get(anchor_type, ()):  # pragma: no branch
            try:
                value = callback(*args, **kwargs)
            except Exception as exc:
                _cb_name = getattr(callback, '__name__', repr(callback))
                log.error(
                    "Anchor %s callback %s failed: %s",
                    anchor_type, _cb_name, exc, exc_info=True,
                )
                _hr_mod.history_recorder.log_internal_error(
                    source="engine_hooks",
                    error_type="anchor_callback",
                    tool_name=f"{anchor_type}/{_cb_name}",
                    message=f"{type(exc).__name__}: {exc}",
                    context_preview=repr(kwargs)[:500],
                )
                continue
            if value is not None:
                result = value
    return result


# ═══════════════════════════════════════════════════════════════
#  Empty hooks dict (useful as default)
# ═══════════════════════════════════════════════════════════════

EMPTY_HOOKS: EngineHooks = {}


__all__ = [
    "AnchorPoint",
    "AnchorCollection",
    "AgentAnchorCollection",
    "HookBinding",
    "EngineHooks",
    "AgentHookCollection",
    "AGENT_START_TRACKING",
    "AGENT_FINALIZE_TRACKING",
    "AGENT_RECORD_REFERENCES",
    "AGENT_SAVE_FINAL_CONTEXT",
    "AGENT_RUN_VERDICT",
    "define_anchor",
    "define_anchor_collection",
    "bind_hook",
    "build_agent_lifecycle_bindings",
    "compile_hooks",
    "anchor",
    "EMPTY_HOOKS",
]
