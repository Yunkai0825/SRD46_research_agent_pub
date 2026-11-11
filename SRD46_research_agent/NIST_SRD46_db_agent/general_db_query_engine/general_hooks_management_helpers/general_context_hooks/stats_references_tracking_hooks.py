"""
Side-logging helper — ``reference_stats.md``
=============================================
Thread-local, singleton-based recorder that accumulates:

- **Tool results** (pre-compaction): tool name, args, raw result chars,
  subagent output chars, KEEP/DISCARD verdict, timing.
- **Argo API calls**: per-tier tallies (system chars, prompt chars,
  response chars, call count, total time).
- **Compaction events**: before/after context size.

Everything is flushed to ``reference_stats.md`` inside the session
output directory.  This module is 100% harmless — it never modifies
conversation context, working memory, or any tool results.

Thread isolation
~~~~~~~~~~~~~~~~
The singleton ``recorder`` keeps per-thread state via
``threading.local()``.  Each thread that calls ``start_run()`` gets
its own ``_RunState`` dataclass — parallel test runners never
clobber each other.

Usage::

    from NIST_ThermoML_agents.general_db_query_engine.general_hooks_management_helpers.general_context_hooks.stats_references_tracking_hooks import recorder

    # After an Argo API call:
    recorder.log_argo_call(tier="L0-main", system_chars=..., prompt_chars=...,
                           response_chars=..., elapsed_s=..., model="...")

    # After a tool result is captured (react_loop):
    recorder.log_tool_result(iteration=..., tool_name=..., args=...,
                             raw_result_chars=..., elapsed_s=...)

    # After the subagent processes a tool result:
    recorder.log_subagent_verdict(tool_name=..., verdict="KEEP",
                                  subagent_output_chars=..., subagent_elapsed_s=...)

    # After compaction:
    recorder.log_compaction(before_chars=..., after_chars=..., trigger="interval")

    # At the end of a run:
    recorder.flush("/path/to/session_dir/reference_stats.md")
    recorder.reset()
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("stats-recorder")

from . import history_tracking_hooks as _hr_mod


# ═══════════════════════════════════════════════════════════════
#  Data containers
# ═══════════════════════════════════════════════════════════════

@dataclass
class _ToolEntry:
    """One tool invocation record."""
    iteration: int
    tool_name: str
    args_summary: str
    raw_result_chars: int
    elapsed_s: float
    # Filled later by log_subagent_verdict (analysis agent only)
    subagent_verdict: str = ""          # "KEEP" | "DISCARD" | "" (no subagent)
    subagent_output_chars: int = 0
    subagent_elapsed_s: float = 0.0


@dataclass
class _ArgoCallEntry:
    """One Argo API call record."""
    tier: str               # e.g. "L0-main", "L1-subagent", "compactor"
    model: str
    system_chars: int
    prompt_chars: int
    response_chars: int
    elapsed_s: float


@dataclass
class _CompactionEntry:
    """One compaction event."""
    trigger: str            # "interval" | "size" | "stage" | "rolling"
    before_chars: int
    after_chars: int


def _safe_int(v: Any) -> int:
    """Coerce a value to int; return 0 on failure."""
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


@dataclass
class _DoiBlockRef:
    """One DOI + block reference observed in a tool result."""
    doi: str
    block_number: str | int
    tool_name: str
    n_datapoints: int = 0
    system_type: str = ""
    n_components: int = 0

    def __post_init__(self) -> None:
        self.n_datapoints = _safe_int(self.n_datapoints)


@dataclass
class _EntityRef:
    """One resolved entity (compound, property, variable, constraint, phase)."""
    entity_type: str        # "compound", "property", "variable", "constraint", "phase"
    num_id: int | str
    name: str
    source_tool: str        # tool that produced this entity
    extra: Dict[str, Any] = field(default_factory=dict)   # e.g. score, formula


@dataclass
class _RawCounterEntry:
    """Raw item counts from one tool result, before any agent condensation."""
    tool_name: str
    n_compounds: int = 0
    n_properties: int = 0
    n_variables: int = 0
    n_constraints: int = 0
    n_dois: int = 0
    n_blocks: int = 0
    n_datapoints: int = 0


@dataclass
class _RunState:
    """Per-thread mutable state for one agent run."""
    tools: List[_ToolEntry] = field(default_factory=list)
    argo_calls: List[_ArgoCallEntry] = field(default_factory=list)
    compactions: List[_CompactionEntry] = field(default_factory=list)
    doi_blocks: List[_DoiBlockRef] = field(default_factory=list)
    entities: List[_EntityRef] = field(default_factory=list)
    raw_counters: List[_RawCounterEntry] = field(default_factory=list)
    run_started: Optional[dt.datetime] = None
    agent_label: str = ""
    out_path: Optional[Path] = None


# ═══════════════════════════════════════════════════════════════
#  Singleton recorder
# ═══════════════════════════════════════════════════════════════

class StatsRecorder:
    """Thread-local accumulator for reference stats during an agent run.

    Each thread gets its own ``_RunState`` via ``threading.local()``,
    so parallel test runners never clobber each other.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _state(self) -> _RunState:
        """Return the current thread's run state (create if absent)."""
        s = getattr(self._local, "state", None)
        if s is None:
            s = _RunState()
            self._local.state = s
        return s

    # ── Public API ──────────────────────────────────────────

    def reset(self) -> None:
        """Clear all accumulated data for a fresh run."""
        self._local.state = _RunState()

    def start_run(self, agent_label: str = "", out_path: str | Path | None = None) -> None:
        """Mark the beginning of a new agent run (also resets old data).

        Parameters
        ----------
        agent_label : str
            Human-readable label for this run (e.g. "query-agent").
        out_path : str or Path, optional
            If given, stats are auto-flushed to this file after every
            logging call so the file stays up-to-date in real time.
        """
        self._local.state = _RunState(
            run_started=dt.datetime.now(),
            agent_label=agent_label,
            out_path=Path(out_path) if out_path else None,
        )

    # ── Real-time auto-flush ────────────────────────────────

    def _auto_flush(self) -> None:
        """If *out_path* was set at start_run, re-write the stats file now."""
        s = self._state()
        if s.out_path and (s.tools or s.argo_calls):
            try:
                md = self._render_markdown()
                s.out_path.parent.mkdir(parents=True, exist_ok=True)
                s.out_path.write_text(md, encoding="utf-8")
            except Exception as exc:
                log.error("auto-flush failed: %s", exc, exc_info=True)

    # ── Logging methods (called from hooks) ─────────────────

    def log_tool_result(
        self,
        iteration: int,
        tool_name: str,
        args: Dict[str, Any],
        raw_result_chars: int,
        elapsed_s: float,
    ) -> None:
        """Record a tool invocation (raw result, before subagent)."""
        summary = ", ".join(
            f"{k}={_truncate_val(v)}" for k, v in sorted(args.items())[:4]
        )
        self._state().tools.append(_ToolEntry(
            iteration=iteration,
            tool_name=tool_name,
            args_summary=summary,
            raw_result_chars=raw_result_chars,
            elapsed_s=elapsed_s,
        ))
        self._auto_flush()

    def log_subagent_verdict(
        self,
        tool_name: str,
        verdict: str,
        subagent_output_chars: int,
        subagent_elapsed_s: float,
    ) -> None:
        """Attach subagent verdict to the most recent matching tool entry."""
        # Walk backwards to find the most recent entry for this tool
        for entry in reversed(self._state().tools):
            if entry.tool_name == tool_name and not entry.subagent_verdict:
                entry.subagent_verdict = verdict
                entry.subagent_output_chars = subagent_output_chars
                entry.subagent_elapsed_s = subagent_elapsed_s
                self._auto_flush()
                break

    def log_argo_call(
        self,
        tier: str,
        model: str,
        system_chars: int,
        prompt_chars: int,
        response_chars: int,
        elapsed_s: float,
    ) -> None:
        """Record a single Argo API call."""
        self._state().argo_calls.append(_ArgoCallEntry(
            tier=tier,
            model=model,
            system_chars=system_chars,
            prompt_chars=prompt_chars,
            response_chars=response_chars,
            elapsed_s=elapsed_s,
        ))
        self._auto_flush()

    def log_compaction(
        self,
        before_chars: int,
        after_chars: int,
        trigger: str = "",
    ) -> None:
        """Record a compaction event."""
        self._state().compactions.append(_CompactionEntry(
            trigger=trigger,
            before_chars=before_chars,
            after_chars=after_chars,
        ))
        self._auto_flush()

    def log_raw_counters(
        self,
        tool_name: str,
        raw_result: dict,
    ) -> None:
        """Count comp/prop/var/constraint/doi/block/datapoint items
        in a raw tool result dict *before* any agent condensation.
        """
        c = _RawCounterEntry(tool_name=tool_name)

        # --- resolved_compounds ---
        for _q, hits in raw_result.get("resolved_compounds", {}).items():
            if isinstance(hits, list):
                c.n_compounds += len(hits)

        # --- compound_resolved (from search_system_summary) ---
        comp_resolved = raw_result.get("compound_resolved")
        if isinstance(comp_resolved, list):
            c.n_compounds += len(comp_resolved)
        elif isinstance(comp_resolved, dict):
            c.n_compounds += 1

        # --- resolved_properties ---
        for _q, hits in raw_result.get("resolved_properties", {}).items():
            if isinstance(hits, list):
                c.n_properties += len(hits)

        # --- property_resolved ---
        prop_resolved = raw_result.get("property_resolved")
        if isinstance(prop_resolved, dict):
            c.n_properties += 1
        elif isinstance(prop_resolved, list):
            c.n_properties += len(prop_resolved)

        # --- results list (block-level or flat resolve hits) ---
        doi_set: set[str] = set()
        results_list = raw_result.get("results", [])
        for r in results_list:
            if not isinstance(r, dict):
                continue
            if "comp_num_id" in r and "compounds" not in r:
                c.n_compounds += 1
                continue
            if "prop_num_id" in r and "properties" not in r:
                c.n_properties += 1
                continue
            c.n_compounds += len(r.get("compounds", []))
            c.n_properties += len(r.get("properties", []))
            c.n_variables += len(r.get("variables", []))
            c.n_constraints += len(r.get("constraints", []))
            doi = r.get("doi", "")
            if doi:
                doi_set.add(doi)
                # Use per-result n_blocks when available (e.g. search_references
                # where each result is a paper); default 1 for per-block tools.
                c.n_blocks += r.get("n_blocks", 1)
            c.n_datapoints += _safe_int(r.get("n_datapoints", 0))
        c.n_dois += len(doi_set)

        # --- inspect_block (flat entity lists + columns present) ---
        if "compounds" in raw_result and "columns" in raw_result:
            c.n_compounds += len(raw_result.get("compounds", []))
            c.n_properties += len(raw_result.get("properties", []))
            c.n_variables += len(raw_result.get("variables", []))
            c.n_constraints += len(raw_result.get("constraints", []))
            c.n_blocks += 1

        # --- summary (from search_system_summary) ---
        # Must be parsed BEFORE top_papers to avoid double-counting datapoints.
        summary = raw_result.get("summary", {})
        _summary_has_totals = False
        if isinstance(summary, dict) and summary:
            c.n_blocks += summary.get("n_blocks", 0)
            c.n_dois += summary.get("n_papers", 0)
            c.n_datapoints += _safe_int(summary.get("total_datapoints", 0))
            c.n_compounds += len(summary.get("compound_cooccurrence", []))
            c.n_properties += len(summary.get("property_distribution", {}))
            _summary_has_totals = "total_datapoints" in summary

        # --- top_papers (from search_system_summary) ---
        # Skip when summary already provides totals to avoid double-counting.
        if not _summary_has_totals:
            for p in raw_result.get("top_papers", []):
                if p.get("doi"):
                    c.n_dois += 1
                    c.n_datapoints += _safe_int(p.get("total_datapoints", 0))

        # --- blocks_found (from L1 result) ---
        bf_doi_set: set[str] = set()
        for b in raw_result.get("blocks_found", []):
            c.n_blocks += 1
            doi = b.get("doi", "")
            if doi:
                bf_doi_set.add(doi)
            c.n_datapoints += _safe_int(b.get("datapoints",
                                    b.get("n_datapoints",
                                          b.get("n_points", 0))))
        c.n_dois += len(bf_doi_set)

        # --- id_updates (from L1 result) ---
        for upd in raw_result.get("id_updates", []):
            etype = upd.get("type", "")
            if etype == "compound":
                c.n_compounds += 1
            elif etype == "property":
                c.n_properties += 1
            elif etype == "variable":
                c.n_variables += 1
            elif etype == "constraint":
                c.n_constraints += 1

        self._state().raw_counters.append(c)
        self._auto_flush()

    def log_entity_references(
        self,
        tool_name: str,
        raw_result: dict,
    ) -> None:
        """Extract entity-level data (compounds, properties, variables,
        constraints, phases) from a raw tool result dict.

        Handles results from: resolve_compounds, resolve_properties,
        query_blocks (per-block compounds/properties/variables/constraints),
        inspect_block, query_system_summary.
        """
        s = self._state()
        # --- resolve_compounds result (dict-of-lists shape) ---
        resolved_comp = raw_result.get("resolved_compounds", {})
        if not isinstance(resolved_comp, dict):
            log.warning(
                "log_entity_references: resolved_compounds is %s, not dict  |  tool=%s  context_preview=%.300r",
                type(resolved_comp).__name__, tool_name, resolved_comp,
            )
            _hr_mod.history_recorder.log_internal_error(
                source="stats_references",
                error_type="type_mismatch",
                tool_name=tool_name,
                message=f"resolved_compounds is {type(resolved_comp).__name__}, expected dict",
                context_preview=repr(resolved_comp)[:500],
            )
            resolved_comp = {}
        for _query_name, hits in resolved_comp.items():
            if isinstance(hits, list):
                for h in hits:
                    nid = h.get("num_id") or h.get("comp_num_id", "")
                    name = h.get("name", h.get("standard_name", ""))
                    if nid:
                        s.entities.append(_EntityRef(
                            entity_type="compound", num_id=nid,
                            name=name, source_tool=tool_name,
                            extra={k: h[k] for k in ("score", "formula")
                                   if k in h},
                        ))

        # --- compound_resolved (list shape from search_system_summary) ---
        comp_resolved = raw_result.get("compound_resolved")
        if isinstance(comp_resolved, list):
            for h in comp_resolved:
                if isinstance(h, dict):
                    nid = h.get("comp_num_id") or h.get("num_id", "")
                    name = h.get("name", h.get("common_name", ""))
                    if nid:
                        s.entities.append(_EntityRef(
                            entity_type="compound", num_id=nid,
                            name=name, source_tool=tool_name,
                            extra={k: h[k] for k in ("score", "formula")
                                   if k in h},
                        ))

        # --- resolve_properties result (dict-of-lists shape) ---
        resolved_prop = raw_result.get("resolved_properties", {})
        if not isinstance(resolved_prop, dict):
            log.warning(
                "log_entity_references: resolved_properties is %s, not dict  |  tool=%s  context_preview=%.300r",
                type(resolved_prop).__name__, tool_name, resolved_prop,
            )
            _hr_mod.history_recorder.log_internal_error(
                source="stats_references",
                error_type="type_mismatch",
                tool_name=tool_name,
                message=f"resolved_properties is {type(resolved_prop).__name__}, expected dict",
                context_preview=repr(resolved_prop)[:500],
            )
            resolved_prop = {}
        for _query_name, hits in resolved_prop.items():
            if isinstance(hits, list):
                for h in hits:
                    nid = h.get("num_id") or h.get("prop_num_id", "")
                    name = h.get("name", h.get("standard_name", ""))
                    if nid:
                        s.entities.append(_EntityRef(
                            entity_type="property", num_id=nid,
                            name=name, source_tool=tool_name,
                            extra={k: h[k] for k in ("score", "group")
                                   if k in h},
                        ))

        # --- property_resolved (single dict from search_system_summary) ---
        prop_resolved = raw_result.get("property_resolved")
        if isinstance(prop_resolved, dict):
            nid = prop_resolved.get("prop_num_id") or prop_resolved.get("num_id", "")
            name = prop_resolved.get("name", "")
            if nid:
                s.entities.append(_EntityRef(
                    entity_type="property", num_id=nid,
                    name=name, source_tool=tool_name,
                ))
        elif isinstance(prop_resolved, list):
            for h in prop_resolved:
                if isinstance(h, dict):
                    nid = h.get("prop_num_id") or h.get("num_id", "")
                    name = h.get("name", "")
                    if nid:
                        s.entities.append(_EntityRef(
                            entity_type="property", num_id=nid,
                            name=name, source_tool=tool_name,
                        ))

        # --- query_blocks / search_blocks results list ---
        results_list = raw_result.get("results", [])
        for r in results_list:
            if not isinstance(r, dict):
                continue
            # Flat resolve-hit dicts (from wrapped resolve_compound_ids)
            if "comp_num_id" in r and "compounds" not in r:
                nid = r.get("comp_num_id") or r.get("num_id", "")
                name = r.get("name", r.get("common_name", ""))
                if nid:
                    s.entities.append(_EntityRef(
                        entity_type="compound", num_id=nid,
                        name=name, source_tool=tool_name,
                        extra={k: r[k] for k in ("score", "formula")
                               if k in r},
                    ))
                continue
            if "prop_num_id" in r and "properties" not in r:
                nid = r.get("prop_num_id") or r.get("num_id", "")
                name = r.get("name", "")
                if nid:
                    s.entities.append(_EntityRef(
                        entity_type="property", num_id=nid,
                        name=name, source_tool=tool_name,
                    ))
                continue
            # Block-style dicts with nested compounds/properties/variables
            for c in r.get("compounds", []):
                nid = c.get("comp_num_id", c.get("num_id", ""))
                name = c.get("name", "")
                if nid:
                    s.entities.append(_EntityRef(
                        entity_type="compound", num_id=nid,
                        name=name, source_tool=tool_name,
                    ))
            # Properties per block
            for p in r.get("properties", []):
                nid = p.get("prop_num_id", p.get("num_id", ""))
                name = p.get("name", "")
                if nid:
                    s.entities.append(_EntityRef(
                        entity_type="property", num_id=nid,
                        name=name, source_tool=tool_name,
                    ))
            # Variables per block
            for v in r.get("variables", []):
                vid = v.get("var_id", v.get("num_id", ""))
                vname = v.get("name", v.get("var_id", ""))
                if vid:
                    s.entities.append(_EntityRef(
                        entity_type="variable", num_id=vid,
                        name=vname, source_tool=tool_name,
                    ))
            # Constraints per block
            for con in r.get("constraints", []):
                cid = con.get("constr_id", con.get("num_id", ""))
                cname = con.get("name", con.get("constr_id", ""))
                if cid:
                    s.entities.append(_EntityRef(
                        entity_type="constraint", num_id=cid,
                        name=cname, source_tool=tool_name,
                    ))

        # --- inspect_block: flat entity lists ---
        if "compounds" in raw_result and "columns" in raw_result:
            for c in raw_result.get("compounds", []):
                if isinstance(c, dict):
                    nid = c.get("comp_num_id", c.get("num_id", ""))
                    name = c.get("name", "")
                else:
                    nid = ""
                    name = str(c)
                if nid or name:
                    s.entities.append(_EntityRef(
                        entity_type="compound", num_id=nid or name,
                        name=name, source_tool=tool_name,
                    ))
            for v in raw_result.get("variables", []):
                if isinstance(v, dict):
                    vid = v.get("var_id", v.get("num_id", ""))
                    vname = v.get("name", v.get("var_id", ""))
                else:
                    vid = str(v)
                    vname = str(v)
                if vid:
                    s.entities.append(_EntityRef(
                        entity_type="variable", num_id=vid,
                        name=vname, source_tool=tool_name,
                    ))
            for p in raw_result.get("properties", []):
                if isinstance(p, dict):
                    nid = p.get("prop_num_id", p.get("num_id", ""))
                    pname = p.get("name", "")
                else:
                    nid = str(p)
                    pname = str(p)
                if nid:
                    s.entities.append(_EntityRef(
                        entity_type="property", num_id=nid,
                        name=pname, source_tool=tool_name,
                    ))
            for con in raw_result.get("constraints", []):
                if isinstance(con, dict):
                    cid = con.get("constr_id", con.get("num_id", ""))
                    cname = con.get("name", con.get("constr_id", ""))
                else:
                    cid = str(con)
                    cname = str(con)
                if cid:
                    s.entities.append(_EntityRef(
                        entity_type="constraint", num_id=cid,
                        name=cname, source_tool=tool_name,
                    ))

        # --- query_system_summary: summary dict ---
        # summary is a dict (with compound_cooccurrence) for
        # search_system_summary results, but a plain string for
        # L1_query results.  Only extract entities when it's a dict.
        summary = raw_result.get("summary", {})
        if isinstance(summary, dict) and summary:
            for coc in summary.get("compound_cooccurrence", []):
                nid = coc.get("comp_id", "")
                name = coc.get("name", "")
                if nid:
                    s.entities.append(_EntityRef(
                        entity_type="compound", num_id=nid,
                        name=name, source_tool=tool_name,
                    ))

        # --- L1 result: id_updates list ---
        for upd in raw_result.get("id_updates", []):
            etype = upd.get("type", "")
            nid = upd.get("num_id", "")
            name = upd.get("name", upd.get("id", ""))
            if etype and nid:
                s.entities.append(_EntityRef(
                    entity_type=etype, num_id=nid,
                    name=name, source_tool=tool_name,
                ))
        self._auto_flush()

    def log_doi_block_references(
        self,
        tool_name: str,
        raw_result: dict,
    ) -> None:
        """Extract DOI + block_number pairs from a raw search result dict.

        Call this from _wrap_tool after obtaining the raw result dict:
        ``recorder.log_doi_block_references(tool_name, raw)``
        """
        results = raw_result.get("results", [])
        if not results:
            # search_system_summary puts DOIs in top_papers instead
            top = raw_result.get("top_papers", [])
            if top:
                s = self._state()
                for p in top:
                    doi = p.get("doi", "")
                    if doi:
                        s.doi_blocks.append(_DoiBlockRef(
                            doi=doi,
                            block_number="(summary)",
                            tool_name=tool_name,
                            n_datapoints=p.get("total_datapoints", 0),
                        ))

        # --- L1 result: blocks_found list ---
        blocks_found = raw_result.get("blocks_found", [])
        if blocks_found:
            s = self._state()
            for b in blocks_found:
                doi = b.get("doi", "")
                bn = b.get("block_number", b.get("block_count", ""))
                if doi:
                    s.doi_blocks.append(_DoiBlockRef(
                        doi=doi,
                        block_number=bn,
                        tool_name=tool_name,
                        n_datapoints=b.get("datapoints", b.get("n_datapoints", b.get("n_points", 0))),
                        system_type=b.get("system_type", ""),
                        n_components=b.get("n_components", 0),
                    ))

        if not results and not blocks_found:
            self._auto_flush()
            return

        if results:
            s = self._state()
            for r in results:
                doi = r.get("doi", "")
                bn = r.get("block_number", "")
                if doi:
                    s.doi_blocks.append(_DoiBlockRef(
                        doi=doi,
                        block_number=bn,
                        tool_name=tool_name,
                        n_datapoints=r.get("n_datapoints", 0),
                        system_type=r.get("system_type", ""),
                        n_components=r.get("n_components", 0),
                    ))
        self._auto_flush()

    # ── Flush to markdown ───────────────────────────────────

    def flush(self, output_path: str | Path) -> Optional[Path]:
        """Write all accumulated stats to ``reference_stats.md``.

        Returns the path written, or None if there is nothing to write.
        """
        s = self._state()
        if not s.tools and not s.argo_calls:
            return None
        md = self._render_markdown()

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_text(md, encoding="utf-8")
            log.info("Stats flushed to %s (%d chars)", out, len(md))
        except Exception as exc:
            log.error("Stats flush failed: %s", exc, exc_info=True)
            return None
        return out

    # ── Data complexity renderer (Section 2) ──────────────

    def _render_data_complexity(self, s: _RunState, lines: list[str]) -> None:
        """Append the Data Complexity Summary section to *lines*.

        Two sub-sections:
        - 2a: Raw Tool-Return Counters (direct counts from tool JSON results,
               before any agent condensation)
        - 2b: Agent-Condensed Data Complexity (deduplicated entity/DOI tables
               as curated by the agent pipeline)
        """
        lines.append("---")
        lines.append("")
        lines.append("## 2. Data Complexity Summary")
        lines.append("")

        # ── 2a: Raw Tool-Return Counters ────────────────────
        lines.append("### 2a. Raw Tool-Return Counters")
        lines.append("")
        lines.append("*Direct counts from raw tool results, before agent condensation.*")
        lines.append("")

        if not s.raw_counters:
            lines.append("*(no raw counter data recorded)*")
            lines.append("")
        else:
            # Per-tool breakdown
            lines.append("| Tool | Compounds | Properties | Variables | Constraints | DOIs | Blocks | Datapoints |")
            lines.append("|------|----------:|-----------:|----------:|------------:|-----:|-------:|-----------:|")
            tot_comp = tot_prop = tot_var = tot_con = tot_doi = tot_blk = tot_dp = 0
            for rc in s.raw_counters:
                lines.append(
                    f"| `{rc.tool_name}` | {rc.n_compounds} | {rc.n_properties} "
                    f"| {rc.n_variables} | {rc.n_constraints} "
                    f"| {rc.n_dois} | {rc.n_blocks} | {rc.n_datapoints:,} |"
                )
                tot_comp += rc.n_compounds
                tot_prop += rc.n_properties
                tot_var += rc.n_variables
                tot_con += rc.n_constraints
                tot_doi += rc.n_dois
                tot_blk += rc.n_blocks
                tot_dp += rc.n_datapoints
            lines.append(
                f"| **TOTAL** | **{tot_comp}** | **{tot_prop}** "
                f"| **{tot_var}** | **{tot_con}** "
                f"| **{tot_doi}** | **{tot_blk}** | **{tot_dp:,}** |"
            )
            lines.append("")

        # ── 2b: Agent-Condensed Data Complexity ─────────────
        lines.append("### 2b. Agent-Condensed Data Complexity")
        lines.append("")
        lines.append("*Deduplicated entities and DOI references after agent processing.*")
        lines.append("")

        if not s.entities:
            lines.append("*(no entity references recorded)*")
            lines.append("")
            return

        # Deduplicate by (entity_type, num_id) – keep first name & collect
        # all source tools that mentioned the entity.
        seen: Dict[tuple, dict] = OrderedDict()
        for e in s.entities:
            key = (e.entity_type, e.num_id)
            if key not in seen:
                seen[key] = {"name": e.name, "sources": set()}
            seen[key]["sources"].add(e.source_tool)

        # Group by entity_type, preserving insertion order
        groups: Dict[str, list] = OrderedDict()
        for (etype, nid), info in seen.items():
            groups.setdefault(etype, []).append((nid, info["name"], info["sources"]))

        # Render per-type tables
        type_labels = {
            "compound": "Compounds",
            "property": "Properties",
            "variable": "Variables",
            "constraint": "Constraints",
            "phase": "Phases",
        }
        for etype, entries in groups.items():
            label = type_labels.get(etype, etype.title() + "s")
            lines.append(f"#### {label} ({len(entries)} unique)")
            lines.append("")
            lines.append("| ID | Name | Source tools |")
            lines.append("|---:|------|-------------|")
            for nid, name, sources in entries:
                src_str = ", ".join(sorted(sources))
                lines.append(f"| {nid} | {name} | {src_str} |")
            lines.append("")

        # Aggregate totals
        total_dois = len({r.doi for r in s.doi_blocks}) if s.doi_blocks else 0
        total_blocks = len({(r.doi, str(r.block_number)) for r in s.doi_blocks}) if s.doi_blocks else 0
        total_dp = sum(
            _safe_int(r.n_datapoints) for r in s.doi_blocks if r.n_datapoints
        ) if s.doi_blocks else 0

        lines.append("#### Aggregate Counts (Condensed)")
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|--------|------:|")
        for etype, entries in groups.items():
            label = type_labels.get(etype, etype.title() + "s")
            lines.append(f"| Unique {label} | {len(entries)} |")
        lines.append(f"| Total DOIs | {total_dois} |")
        lines.append(f"| Total Blocks | {total_blocks} |")
        lines.append(f"| Total Data Points | {total_dp:,} |")
        lines.append("")

    # ── Markdown renderer ───────────────────────────────────

    def _render_markdown(self) -> str:
        """Build the full reference_stats.md content."""
        s = self._state()
        ts = s.run_started.strftime("%Y-%m-%d %H:%M:%S") if s.run_started else "unknown"
        lines: list[str] = []

        lines.append(f"# Reference Stats — {s.agent_label}")
        lines.append(f"")
        lines.append(f"**Run started:** {ts}")
        lines.append(f"")

        # ── Section 1: Argo API Summary ─────────────────────
        lines.append("---")
        lines.append("")
        lines.append("## 1. Argo API Call Summary")
        lines.append("")

        if s.argo_calls:
            # Aggregate by tier
            tier_stats: Dict[str, dict] = {}
            for c in s.argo_calls:
                ts_entry = tier_stats.setdefault(c.tier, {
                    "calls": 0, "system_chars": 0, "prompt_chars": 0,
                    "response_chars": 0, "total_s": 0.0, "models": set(),
                })
                ts_entry["calls"] += 1
                ts_entry["system_chars"] += c.system_chars
                ts_entry["prompt_chars"] += c.prompt_chars
                ts_entry["response_chars"] += c.response_chars
                ts_entry["total_s"] += c.elapsed_s
                ts_entry["models"].add(c.model)

            lines.append("| Tier | Calls | System (chars) | Prompt (chars) | Response (chars) | Total sent | Avg Context | Total time (s) | Model(s) |")
            lines.append("|------|------:|---------------:|---------------:|-----------------:|-----------:|------------:|---------------:|----------|")
            grand_calls = 0
            grand_sys = 0
            grand_prompt = 0
            grand_resp = 0
            grand_time = 0.0
            for tier in sorted(tier_stats):
                ts_entry = tier_stats[tier]
                total_sent = ts_entry["system_chars"] + ts_entry["prompt_chars"]
                avg_ctx = total_sent // ts_entry["calls"] if ts_entry["calls"] else 0
                models = ", ".join(sorted(ts_entry["models"]))
                lines.append(
                    f"| {tier} | {ts_entry['calls']} | {ts_entry['system_chars']:,} "
                    f"| {ts_entry['prompt_chars']:,} | {ts_entry['response_chars']:,} "
                    f"| {total_sent:,} | {avg_ctx:,} | {ts_entry['total_s']:.1f} | {models} |"
                )
                grand_calls += ts_entry["calls"]
                grand_sys += ts_entry["system_chars"]
                grand_prompt += ts_entry["prompt_chars"]
                grand_resp += ts_entry["response_chars"]
                grand_time += ts_entry["total_s"]
            grand_sent = grand_sys + grand_prompt
            grand_avg = grand_sent // grand_calls if grand_calls else 0
            lines.append(
                f"| **TOTAL** | **{grand_calls}** | **{grand_sys:,}** "
                f"| **{grand_prompt:,}** | **{grand_resp:,}** "
                f"| **{grand_sent:,}** | **{grand_avg:,}** | **{grand_time:.1f}** | |"
            )
            lines.append("")

            # Estimated tokens (rough: 1 token ≈ 4 chars)
            est_in = grand_sent // 4
            est_out = grand_resp // 4
            lines.append(f"**Estimated tokens:** ~{est_in:,} input + ~{est_out:,} output = ~{est_in + est_out:,} total")
            lines.append(f"*(rough estimate: 1 token ≈ 4 chars)*")
            lines.append("")
        else:
            lines.append("*(no Argo calls recorded)*")
            lines.append("")

        # ── Section 2: Data Complexity Summary ────────────
        self._render_data_complexity(s, lines)

        # ── Section 3: DOI & Block References ──────────────
        lines.append("---")
        lines.append("")
        lines.append("## 3. DOI & Block References")
        lines.append("")

        if s.doi_blocks:
            # Deduplicate: (doi, block_number) → aggregate
            seen: Dict[tuple, dict] = {}
            for ref in s.doi_blocks:
                key = (ref.doi, str(ref.block_number))
                if key not in seen:
                    seen[key] = {
                        "doi": ref.doi,
                        "block_number": ref.block_number,
                        "n_datapoints": ref.n_datapoints,
                        "system_type": ref.system_type,
                        "n_components": ref.n_components,
                        "tools": {ref.tool_name},
                    }
                else:
                    seen[key]["tools"].add(ref.tool_name)
                    # Keep the richest metadata
                    if ref.n_datapoints:
                        seen[key]["n_datapoints"] = ref.n_datapoints
                    if ref.system_type:
                        seen[key]["system_type"] = ref.system_type
                    if ref.n_components:
                        seen[key]["n_components"] = ref.n_components

            unique_dois = sorted({v["doi"] for v in seen.values()})
            total_blocks = sum(1 for v in seen.values()
                               if v["block_number"] != "(summary)")
            total_dp = sum(v["n_datapoints"] or 0 for v in seen.values())

            lines.append(f"**Unique DOIs:** {len(unique_dois)}  |  "
                         f"**Unique blocks:** {total_blocks}  |  "
                         f"**Total datapoints:** {total_dp:,}")
            lines.append("")

            # Per-DOI summary
            lines.append("| DOI | Blocks | Datapoints | System types | Source tools |")
            lines.append("|-----|-------:|-----------:|--------------|--------------|")
            for doi in unique_dois:
                entries = [v for v in seen.values() if v["doi"] == doi]
                n_blk = sum(1 for e in entries if e["block_number"] != "(summary)")
                dp = sum(e["n_datapoints"] or 0 for e in entries)
                sys_types = sorted({e["system_type"] for e in entries if e["system_type"]})
                tools = sorted({t for e in entries for t in e["tools"]})
                lines.append(
                    f"| {doi} | {n_blk} | {dp:,} "
                    f"| {', '.join(sys_types) or '—'} "
                    f"| {', '.join(tools)} |"
                )
            lines.append("")

            # Detailed block listing
            lines.append("<details><summary>Block detail</summary>")
            lines.append("")
            lines.append("| DOI | Block | Datapoints | System | nComp | Source tools |")
            lines.append("|-----|------:|-----------:|--------|------:|--------------|")
            for key in sorted(seen):
                v = seen[key]
                tools_str = ", ".join(sorted(v["tools"]))
                lines.append(
                    f"| {v['doi']} | {v['block_number']} | {(v['n_datapoints'] or 0):,} "
                    f"| {v['system_type'] or '—'} | {v['n_components'] or '—'} "
                    f"| {tools_str} |"
                )
            lines.append("")
            lines.append("</details>")
            lines.append("")
        else:
            lines.append("*(no DOI/block references recorded)*")
            lines.append("")

        # ── Section 4: Tool Results (pre-compaction) ────────
        lines.append("---")
        lines.append("")
        lines.append("## 4. Tool Results (pre-compaction)")
        lines.append("")

        if s.tools:
            lines.append("| # | Iter | Tool | Args | Raw (chars) | Subagent | Out (chars) | Time (s) |")
            lines.append("|--:|-----:|------|------|------------:|----------|------------:|---------:|")
            total_raw = 0
            total_sub = 0
            total_time = 0.0
            for i, t in enumerate(s.tools, 1):
                verdict_tag = t.subagent_verdict or "—"
                sub_chars = t.subagent_output_chars or "—"
                args_short = t.args_summary[:50] + ("…" if len(t.args_summary) > 50 else "")
                lines.append(
                    f"| {i} | {t.iteration} | `{t.tool_name}` | {args_short} "
                    f"| {t.raw_result_chars:,} | {verdict_tag} | {sub_chars} "
                    f"| {t.elapsed_s:.1f} |"
                )
                total_raw += t.raw_result_chars
                total_sub += t.subagent_output_chars
                total_time += t.elapsed_s
            lines.append(
                f"| | | **TOTAL ({len(s.tools)} tools)** | | "
                f"**{total_raw:,}** | | **{total_sub:,}** | **{total_time:.1f}** |"
            )
            lines.append("")
        else:
            lines.append("*(no tool results recorded)*")
            lines.append("")

        # ── Section 5: Compaction Events ────────────────────
        lines.append("---")
        lines.append("")
        lines.append("## 5. Compaction Events")
        lines.append("")

        if s.compactions:
            lines.append("| # | Trigger | Before (chars) | After (chars) | Saved (chars) | Saved (%) |")
            lines.append("|--:|---------|---------------:|--------------:|--------------:|----------:|")
            for i, c in enumerate(s.compactions, 1):
                saved = c.before_chars - c.after_chars
                pct = (saved / c.before_chars * 100) if c.before_chars > 0 else 0
                lines.append(
                    f"| {i} | {c.trigger} | {c.before_chars:,} "
                    f"| {c.after_chars:,} | {saved:,} | {pct:.1f}% |"
                )
            lines.append("")
        else:
            lines.append("*(no compaction events recorded)*")
            lines.append("")

        # ── Section 6: Argo Call Detail Log ─────────────────
        lines.append("---")
        lines.append("")
        lines.append("## 6. Argo Call Detail Log")
        lines.append("")

        if s.argo_calls:
            lines.append("| # | Tier | Model | System | Prompt | Context | Response | Time (s) |")
            lines.append("|--:|------|-------|-------:|-------:|--------:|---------:|---------:|")
            for i, c in enumerate(s.argo_calls, 1):
                ctx = c.system_chars + c.prompt_chars
                lines.append(
                    f"| {i} | {c.tier} | {c.model} | {c.system_chars:,} "
                    f"| {c.prompt_chars:,} | {ctx:,} | {c.response_chars:,} "
                    f"| {c.elapsed_s:.1f} |"
                )
            lines.append("")
        else:
            lines.append("*(no Argo calls recorded)*")
            lines.append("")

        return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════
#  Module-level singleton + thread-local active recorder
# ═══════════════════════════════════════════════════════════════

recorder = StatsRecorder()

# Thread-local "active" recorder — set by `set_active_recorder()` during
# start_tracking.  `get_active_recorder()` returns it (or the base
# `recorder` as fallback).  Consumed by `argo_client_caller.py` so that
# Argo API calls land in the *agent-specific* StatsRecorder instance.
_active_ref = threading.local()


def set_active_recorder(rec: StatsRecorder) -> None:
    """Designate *rec* as the active stats recorder for this thread."""
    _active_ref.recorder = rec


def get_active_recorder() -> StatsRecorder:
    """Return the active stats recorder (agent-specific or base fallback)."""
    return getattr(_active_ref, "recorder", None) or recorder


def clear_active_recorder() -> None:
    """Remove the thread-local active recorder reference."""
    _active_ref.recorder = None


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _truncate_val(v: Any, max_len: int = 30) -> str:
    """Truncate a value to a short string for the args summary."""
    s = str(v)
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"
