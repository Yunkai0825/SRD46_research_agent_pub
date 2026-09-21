"""
AgentToolCatalog — base class for agent-specific tool registries.
=================================================================

Central authority for what tools an agent layer owns, how each tool's
raw dict output is compacted, and whether that compacted markdown is
further triaged by the LLM KEEP/DISCARD subagent.

Two-stage compaction pipeline
-----------------------------
For every tool call that returns a ``dict``:

1. **Layer 1 — hardcoded compactor** (``compact_tool_result``)
   Looks up ``ToolEntry.compactor_fn`` and converts the dict to
   concise markdown.  Falls back to a truncated JSON dump when no
   compactor is registered or the compactor raises.
   Skipped when ``ToolEntry.skip_compactor`` is True.

   **Condensation levels** — some tools support tiered compaction:

   - ``"full"`` — default, uses ``compactor_fn``.
   - ``"condense"`` — uses ``condense_fn`` (lighter, strips data rows).
   - ``"ultra_condense"`` — uses ``ultra_condense_fn`` (one-liner per block).
   - ``adaptive_condense`` — compactor_fn handles levels internally
     based on output size (e.g. via ``_apply_block_condensation``).

2. **Layer 2 — agentic subagent** (``call_subagent``)
   Sends the markdown to a lightweight ReAct LLM subagent that
   decides KEEP (extract tables / key identifiers) or DISCARD
   (explain + suggest refinement).
   Skipped when ``ToolEntry.skip_subagent`` is True.

Subclasses should set:
  * ``pipeline_label`` — ``"query"`` or ``"analysis"``

and call ``register`` / ``register_many`` in ``__init__``.

Usage example (agent subclass)::

    class QueryL1Catalog(AgentToolCatalog):
        pipeline_label = "query"

        def __init__(self, *, client_factory, cfg):
            super().__init__(client_factory=client_factory, cfg=cfg)
            self.register_many([
                ToolEntry("resolve_ids", resolve_ids,
                          group="id_resolution",
                          compactor_fn=compact_resolve_ids),
                ToolEntry("L2_comp_eval", dispatch_l2_comp_eval,
                          group="L2_subagent",
                          skip_compactor=True, skip_subagent=True),
            ])

Then the dispatch code can call::

    catalog = QueryL1Catalog(client_factory=..., cfg=...)
    # Raw tool dict for agent_turn():
    agent_turn(..., tools=catalog.wrapped_tools(), ...)
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, Iterable, Optional

from .tool_entry import ToolEntry
from .agent_tool_compactor_hooks_catalog import CompactorCatalog
from ..general_tool_results_compactor_agentic_hooks import (
    ToolResult, ToolResultCompactor,
)
from .. import _tool_hooks_anchors_catalog as _tool_anchor
from ...general_argo_engine_helpers.engine_hooks_anchors import anchor as _anchor

log = logging.getLogger("agent-tool-catalog")


class AgentToolCatalog:
    """Base class for every agent-level tool catalog."""

    pipeline_label: str = "agent"

    # ── Construction ────────────────────────────────────────────

    def __init__(
        self,
        *,
        client_factory: Optional[Callable] = None,
        cfg: Any = None,
        entries: Optional[Iterable[ToolEntry]] = None,
        extra_compactors: Optional[Dict[str, Callable]] = None,
        compactor_catalog: Optional[CompactorCatalog] = None,
    ) -> None:
        self._entries: Dict[str, ToolEntry] = {}
        self._extra_compactors: Dict[str, Callable] = dict(extra_compactors or {})
        self._client_factory = client_factory
        self._cfg = cfg
        self._compactor_catalog = compactor_catalog
        # Lazily built — invalidated when entries change
        self._compactor_obj: Optional[Any] = None
        if entries:
            self.register_many(entries)

    # ── Entry management ────────────────────────────────────────

    def register(self, entry: ToolEntry) -> None:
        """Add or replace a single tool entry.

        When a ``compactor_catalog`` was provided at construction,
        entries without an explicit ``compactor_fn`` are auto-resolved
        from the catalog by matching ``entry.name``.
        """
        if self._compactor_catalog is not None:
            entry = self._resolve_entry_compactor(entry)
        self._entries[entry.name] = entry
        self._compactor_obj = None  # invalidate

    def register_many(self, entries: Iterable[ToolEntry]) -> None:
        for e in entries:
            self.register(e)
        self._compactor_obj = None

    def add_extra_compactor(self, tool_name: str, fn: Callable) -> None:
        """Register a compactor for a name that has no ToolEntry.

        Useful when an agent needs compactor coverage for intermediate
        result keys that aren't standalone tools (e.g. analysis agent's
        ``resolve_compounds`` which is a sub-step of ``query_thermoml``).
        """
        self._extra_compactors[tool_name] = fn
        self._compactor_obj = None

    def _resolve_entry_compactor(self, entry: ToolEntry) -> ToolEntry:
        """Auto-resolve compactor_fn from ``self._compactor_catalog``.

        If the entry already has a ``compactor_fn`` or ``skip_compactor``
        is True, returns the entry unchanged.  Otherwise looks up
        ``entry.name`` in the compactor catalog and returns a new
        ToolEntry with ``compactor_fn`` filled in.
        """
        if entry.compactor_fn is not None or entry.skip_compactor:
            return entry
        cat = self._compactor_catalog
        if cat is not None and entry.name in cat:
            fn = cat.registry[entry.name]
            # Frozen dataclass — rebuild with the resolved compactor
            return ToolEntry(
                name=entry.name,
                fn=entry.fn,
                group=entry.group,
                compactor_fn=fn,
                condense_fn=entry.condense_fn,
                ultra_condense_fn=entry.ultra_condense_fn,
                adaptive_condense=entry.adaptive_condense,
                skip_compactor=entry.skip_compactor,
                skip_subagent=entry.skip_subagent,
                guidance_fn=entry.guidance_fn,
                description=entry.description,
            )
        return entry

    # ── Read accessors ──────────────────────────────────────────

    @property
    def entries(self) -> Dict[str, ToolEntry]:
        """Shallow copy of the entry dict."""
        return dict(self._entries)

    def __getitem__(self, name: str) -> ToolEntry:
        return self._entries[name]

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    # ── Tool dict (for agent_turn) ──────────────────────────────

    @property
    def tools(self) -> Dict[str, Callable]:
        """``{name: callable}`` — raw (unwrapped) tool dict."""
        return {n: e.fn for n, e in self._entries.items()}

    def tools_by_group(self, group: str) -> Dict[str, Callable]:
        """Subset of ``tools`` belonging to *group*."""
        return {n: e.fn for n, e in self._entries.items() if e.group == group}

    # ── Compactor registry (derived from entries) ───────────────

    @property
    def compactor_registry(self) -> Dict[str, Callable]:
        """Merged compactor map: tool entries + extra compactors."""
        reg: Dict[str, Callable] = {}
        for n, e in self._entries.items():
            if e.compactor_fn and not e.skip_compactor:
                reg[n] = e.compactor_fn
        reg.update(self._extra_compactors)
        return reg

    # ── Internal ToolResultCompactor (lazy) ─────────────────────

    @property
    def _compactor(self):
        """Lazily builds and caches a ``ToolResultCompactor``."""
        if self._compactor_obj is None:
            self._compactor_obj = ToolResultCompactor(
                client_factory=self._client_factory,
                cfg=self._cfg,
                pipeline_label=self.pipeline_label,
                compactor_registry=self.compactor_registry,
            )
        return self._compactor_obj

    # ── Layer 1: hardcoded dict→markdown ────────────────────────

    def compact_tool_result(
        self,
        tool_name: str,
        data: dict,
        *,
        level: str = "full",
    ) -> str:
        """Apply the hardcoded compactor for *tool_name* (Layer 1).

        Parameters
        ----------
        tool_name : str
            Registered tool name.
        data : dict
            Raw tool output dict.
        level : str
            Condensation level: ``"full"`` (default), ``"condense"``,
            or ``"ultra_condense"``.  Falls through to the next available
            level when the requested one isn't registered.

        Falls back to truncated JSON when no compactor is registered
        or the compactor raises.
        """
        entry = self._entries.get(tool_name)

        # Pick the right compactor function for the requested level
        if entry and level != "full":
            fn = None
            if level == "ultra_condense" and entry.ultra_condense_fn:
                fn = entry.ultra_condense_fn
            elif level in ("condense", "ultra_condense") and entry.condense_fn:
                fn = entry.condense_fn
            if fn is not None:
                try:
                    return fn(data)
                except Exception as e:
                    log.warning("Condense compactor (%s) for %s failed: %s",
                                level, tool_name, e, exc_info=True)
            # Fall through to default compactor

        return self._compactor.compact_tool_result(tool_name, data)

    # ── Layer 2: agentic KEEP/DISCARD ───────────────────────────

    def call_subagent(
        self,
        tool_name: str,
        purpose: str,
        tasks: str,
        compact_md: str,
        raw: dict,
    ):
        """Send *compact_md* to the LLM subagent for KEEP/DISCARD (Layer 2)."""
        return self._compactor.call(tool_name, purpose, tasks, compact_md, raw)

    # ── Two-stage: compact → subagent (with skip logic) ─────────

    def compact_and_call(
        self,
        tool_name: str,
        purpose: str,
        tasks: str,
        raw: dict,
        *,
        level: str = "full",
    ):
        """Run the full two-stage pipeline respecting skip flags.

        Parameters
        ----------
        tool_name, purpose, tasks, raw
            Standard two-stage arguments.
        level : str
            Condensation level for Layer 1: ``"full"``, ``"condense"``,
            or ``"ultra_condense"``.  Tools with ``adaptive_condense``
            handle this internally through ``compactor_fn``.

        Returns
        -------
        ToolResult
            ``.raw`` = original dict, ``.text`` = final markdown,
            ``.discarded`` = True if subagent chose DISCARD.
        """
        entry = self._entries.get(tool_name)

        # Layer 1
        compact_md = self.compact_tool_result(tool_name, raw, level=level)

        # Layer 2 (skip when flagged)
        if entry and entry.skip_subagent:
            return ToolResult(raw=raw, text=compact_md)
        return self._compactor.call(tool_name, purpose, tasks, compact_md, raw)

    # ── Extensibility hooks ───────────────────────────────────

    def _on_raw_result(self, tool_name: str, raw: dict) -> None:
        """Called after a wrapped tool returns a dict/list, before compaction.

        Override in subclasses to add side-effects like stats logging.
        The default implementation is a no-op.
        """

    # ── Pre-execution batch validation ────────────────────────

    def validate_batch(
        self,
        tool_calls: list[dict],
        tools: dict[str, Callable],
        *,
        hooks=None,
    ) -> str | None:
        """Check all tool calls for guidance before execution.

        Fires the ``SYNC_TOOL_GUIDANCE_CHECK`` anchor for each tool
        call.  Guidance hooks bound to that anchor filter by
        ``tool_name`` and return:

        - ``None`` — hook does not handle this tool (no guidance).
        - ``""``   — handled OK (may have auto-filled kwargs).
        - non-empty ``str`` — blocked with guidance text.

        Builds a per-tool status report:

        - **blocked** tools with error detail
        - **ready** tools that passed (with auto-filled param notes)
        - **no-validation** tools held back by the batch

        If ANY tool emits guidance, returns a combined report string
        (replaces batch execution).  The agent can fix blocked tools
        and re-submit, or drop them and retry with the rest.
        Returns ``None`` when all tools pass.

        Parameters
        ----------
        tool_calls : list[dict]
            Parsed tool calls, each with ``name`` and ``arguments`` keys.
        tools : dict[str, Callable]
            The wrapped tools dict (for signature-based arg normalisation).
        hooks : EngineHooks or None
            Compiled engine hooks dict for anchor dispatch.

        Returns
        -------
        str or None
            Per-tool validation report, or None if all pass.
        """
        # Per-tool tracking
        blocked: list[tuple[str, str]] = []       # (name, guidance_text)
        ready_filled: list[tuple[str, dict]] = [] # (name, {param: new_val})
        ready_clean: list[str] = []               # names that passed as-is
        no_guidance: list[str] = []               # tools without guidance hook

        for tc in tool_calls:
            tool_name = tc.get("name", "")

            raw_args = tc.get("arguments", {})
            fn = tools.get(tool_name)
            if fn is not None:
                try:
                    from ...general_argo_engine_helpers import _normalize_args
                    call_kwargs = _normalize_args(tool_name, raw_args, fn)
                except Exception:
                    call_kwargs = dict(raw_args)
            else:
                call_kwargs = dict(raw_args)

            # Snapshot before anchor fires (for change detection)
            kwargs_before = dict(call_kwargs)

            # Fire per-tool guidance anchor — zero hardcoded hook calls.
            result = _anchor(
                _tool_anchor.SYNC_TOOL_GUIDANCE_CHECK,
                hooks,
                tool_name=tool_name,
                call_kwargs=call_kwargs,
            )

            if result is None:
                # No guidance hook handled this tool
                no_guidance.append(tool_name)
            elif result:
                # Non-empty string → blocked
                blocked.append((tool_name, result))
            else:
                # Empty string → handled OK, detect auto-filled params
                changes = {
                    k: call_kwargs[k]
                    for k in call_kwargs
                    if call_kwargs[k] != kwargs_before.get(k)
                }
                tc["arguments"] = call_kwargs
                if changes:
                    ready_filled.append((tool_name, changes))
                else:
                    ready_clean.append(tool_name)

        if not blocked:
            return None

        # ── Build per-tool status report ──────────────────────
        parts: list[str] = []

        for name, reason in blocked:
            parts.append(f"**\u2717 {name}** — needs correction:\n{reason}")

        if ready_filled:
            for name, changes in ready_filled:
                fills = ", ".join(
                    f"`{k}`=`{v}`" for k, v in changes.items()
                )
                parts.append(f"**\u2713 {name}** — ready (auto-filled: {fills})")

        if ready_clean:
            parts.append(f"**\u2713 {', '.join(ready_clean)}** — ready")

        if no_guidance:
            parts.append(
                f"**\u00B7 {', '.join(no_guidance)}** — "
                f"no validation needed (held back by batch)"
            )

        parts.append(
            "_Fix the blocked tool(s) and re-submit, "
            "or drop them and re-submit only the ready ones "
            "(you are able to add new tools to the batch if you really need to)._"
        )
        return "\n\n".join(parts)

    # ── Tool wrapping (adds purpose/tasks to signature) ─────────

    def wrap_tool(self, tool_name: str) -> Callable:
        """Return a wrapped callable that runs the two-stage pipeline.

        The wrapper:
        1. Pops ``purpose`` and ``tasks`` from kwargs.
        2. Calls the underlying function with remaining kwargs.
        3. If the result is a dict/list, runs ``compact_and_call``.
        4. Returns a ``ToolResult`` (or plain string for pass-through).

        Tools with both ``skip_compactor`` **and** ``skip_subagent``
        True are returned unwrapped.
        """
        entry = self._entries[tool_name]

        # Fully pass-through tools need no wrapper
        if entry.skip_compactor and entry.skip_subagent:
            return entry.fn

        fn = entry.fn
        sig = inspect.signature(fn)
        valid_params = set(sig.parameters)
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )

        catalog_ref = self  # closure

        def wrapped(**kwargs):
            purpose = kwargs.pop("purpose", "")
            tasks = kwargs.pop("tasks", "")

            # LLM must supply both
            if not purpose or not tasks:
                return (
                    f"ERROR: Tool '{tool_name}' requires both `purpose` and "
                    f"`tasks` parameters.  You MUST provide:\n"
                    f"  - purpose: why you are calling this tool\n"
                    f"  - tasks: what specific information to extract\n"
                    f"Re-call the tool with both parameters."
                )

            # Filter kwargs to the real function's signature
            if not has_var_kw:
                call_kwargs = {k: v for k, v in kwargs.items()
                               if k in valid_params}
            else:
                call_kwargs = kwargs

            try:
                result = fn(**call_kwargs)
            except Exception as exc:
                log.error(
                    "Tool %s raised in wrap_tool: %s", tool_name, exc,
                    exc_info=True,
                )
                result = {"error": str(exc)}

            # String results are already compact — pass through
            if isinstance(result, str):
                return result

            # Normalise to dict
            if isinstance(result, list):
                raw = {"results": result, "n_results": len(result)}
            elif isinstance(result, dict):
                raw = result
            else:
                return result

            # Optional subclass hook (e.g. stats logging)
            catalog_ref._on_raw_result(tool_name, raw)

            return catalog_ref.compact_and_call(
                tool_name, purpose, tasks, raw,
            )

        wrapped.__name__ = getattr(fn, "__name__", tool_name)
        wrapped.__doc__ = getattr(fn, "__doc__", "")

        # Preserve original signature + add purpose/tasks (dedup if already present)
        _EXTRA_NAMES = {"purpose", "tasks"}
        orig_params = [
            p for p in sig.parameters.values()
            if p.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ) and p.name not in _EXTRA_NAMES
        ]
        extra = [
            inspect.Parameter(
                "purpose", inspect.Parameter.KEYWORD_ONLY,
            ),
            inspect.Parameter(
                "tasks", inspect.Parameter.KEYWORD_ONLY,
            ),
        ]
        wrapped.__signature__ = sig.replace(parameters=orig_params + extra)
        return wrapped

    def wrapped_tools(self) -> Dict[str, Callable]:
        """Tool dict with compaction wrapping where applicable.

        Tools that skip both layers are returned unwrapped.
        """
        return {name: self.wrap_tool(name) for name in self._entries}

    # ── Helpers ─────────────────────────────────────────────────

    def groups(self) -> list[str]:
        """Sorted list of distinct group labels."""
        return sorted({e.group for e in self._entries.values() if e.group})

    def summary(self) -> str:
        """Human-readable summary of all entries."""
        lines = [f"AgentToolCatalog ({self.pipeline_label}) — {len(self)} tools"]
        for g in self.groups():
            members = [n for n, e in self._entries.items() if e.group == g]
            lines.append(f"  [{g}] {', '.join(members)}")
        ungrouped = [n for n, e in self._entries.items() if not e.group]
        if ungrouped:
            lines.append(f"  [ungrouped] {', '.join(ungrouped)}")
        return "\n".join(lines)
