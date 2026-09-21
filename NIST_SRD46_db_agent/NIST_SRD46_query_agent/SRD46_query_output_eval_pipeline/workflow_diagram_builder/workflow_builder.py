"""Generate Mermaid flowchart diagrams from parsed agent tool-call history.

Produces a Mermaid-syntax string showing the 4-phase agent pipeline
(Triage → Discovery → Planning → Execution) with tool-call nodes,
parallel fork/join diamonds, wall-time labels, per-tool durations,
model timing annotations, and error highlighting.

Parallel detection: consecutive calls with ``is_parallel=True`` **and**
the same ``timestamp_sec`` are rendered as a fork → N nodes → join group.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.models import ToolCall

# Phase classification based on tool names (mirrors query_agent.py logic)
_PHASE_MAP: dict[str, tuple[int, str]] = {
    "0_preplan_decision":       (0, "Triage"),
    "search_metals":            (1, "Discovery"),
    "search_ligands":           (1, "Discovery"),
    "build_system_catalog":     (1, "Discovery"),
    "0_plan_search_strategy":   (2, "Planning"),
}
_EXECUTION_PHASE = (3, "Execution")


def _classify_phase(tool_name: str) -> tuple[int, str]:
    return _PHASE_MAP.get(tool_name, _EXECUTION_PHASE)


# ---------------------------------------------------------------------------
# Grouping: consecutive parallel calls with the same timestamp → one batch
# ---------------------------------------------------------------------------

_CallGroup = list[ToolCall]  # 1-element = sequential, 2+ = parallel batch


def _group_calls(calls: Sequence[ToolCall]) -> list[_CallGroup]:
    """Group consecutive parallel calls that share ``timestamp_sec``.

    Returns a list of groups.  Each group is a list of ToolCalls:
    * length-1 → sequential call
    * length-2+ → parallel batch (fork/join)
    """
    groups: list[_CallGroup] = []
    i = 0
    n = len(calls)
    while i < n:
        c = calls[i]
        if c.is_parallel:
            batch: _CallGroup = [c]
            j = i + 1
            while j < n and calls[j].is_parallel and calls[j].timestamp_sec == c.timestamp_sec:
                batch.append(calls[j])
                j += 1
            groups.append(batch)
            i = j
        else:
            groups.append([c])
            i += 1
    return groups


def _phase_id_for_group(group: _CallGroup) -> int:
    return max(_classify_phase(c.tool_name)[0] for c in group)


def _phase_segments(all_groups: Sequence[_CallGroup]) -> list[tuple[int, list[_CallGroup]]]:
    """Split groups into chronological segments of the same phase.

    This preserves true tool history order. If the agent jumps from Discovery to
    Execution, back to Planning, and then to Execution again, the diagram should
    reflect that chronology instead of re-bucketing all groups into fixed phase
    columns.
    """
    if not all_groups:
        return []

    segments: list[tuple[int, list[_CallGroup]]] = []
    current_phase = _phase_id_for_group(all_groups[0])
    current_groups: list[_CallGroup] = [all_groups[0]]

    for group in all_groups[1:]:
        phase_id = _phase_id_for_group(group)
        if phase_id == current_phase:
            current_groups.append(group)
            continue

        segments.append((current_phase, current_groups))
        current_phase = phase_id
        current_groups = [group]

    segments.append((current_phase, current_groups))
    return segments


# ---------------------------------------------------------------------------
# Node-ID helpers (must be valid Mermaid identifiers)
# ---------------------------------------------------------------------------

def _node_id(call: ToolCall) -> str:
    safe = call.tool_name.replace(".", "_").replace("-", "_")
    return f"s{call.step_num}_{safe}"


def _fork_id(group: _CallGroup) -> str:
    return f"fork_s{group[0].step_num}"


def _join_id(group: _CallGroup) -> str:
    return f"join_s{group[-1].step_num}"


def _group_key(group: _CallGroup) -> tuple[int, ...]:
    return tuple(call.step_num for call in group)


def _group_end_sec(group: _CallGroup) -> float:
    return max(call.timestamp_sec for call in group)


def _format_seconds(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.1f}s"


def _format_model_timing_lines(call: ToolCall) -> list[str]:
    if not call.model_timings:
        return []

    per_model: OrderedDict[str, dict[str, int | float]] = OrderedDict()
    for timing in call.model_timings:
        stats = per_model.setdefault(
            timing.model_name,
            {"elapsed_sec": 0.0, "count": 0, "revision_count": 0},
        )
        stats["elapsed_sec"] = float(stats["elapsed_sec"]) + timing.elapsed_sec
        stats["count"] = int(stats["count"]) + 1
        if timing.revision:
            stats["revision_count"] = int(stats["revision_count"]) + 1

    lines: list[str] = []
    for model_name, stats in per_model.items():
        elapsed = _format_seconds(float(stats["elapsed_sec"]))
        count = int(stats["count"])
        revision_count = int(stats["revision_count"])
        suffix_parts: list[str] = []
        if count > 1:
            suffix_parts.append(f"{count}x")
        if revision_count:
            suffix_parts.append(f"{revision_count} rev")
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        lines.append(f"argo {model_name} {elapsed}{suffix}")
    return lines


def _sequential_label(call: ToolCall, wall_sec: float | None, end_sec: float | None) -> str:
    label_lines = [call.tool_name]
    if wall_sec is not None:
        label_lines.append(f"wall {_format_seconds(wall_sec)}")
    if end_sec is not None:
        label_lines.append(f"@ {_format_seconds(end_sec)}")
    if wall_sec is None or abs(wall_sec - call.duration_sec) > 0.05:
        label_lines.append(f"tool {_format_seconds(call.duration_sec)}")
    label_lines.extend(_format_model_timing_lines(call))
    return "\\n".join(label_lines)


def _parallel_label(call: ToolCall) -> str:
    label_lines = [call.tool_name, f"tool {_format_seconds(call.duration_sec)}"]
    label_lines.extend(_format_model_timing_lines(call))
    return "\\n".join(label_lines)


# ---------------------------------------------------------------------------
# Mermaid builder
# ---------------------------------------------------------------------------

def build_mermaid(calls: Sequence[ToolCall]) -> str:
    """Build a Mermaid flowchart from a list of tool calls.

    Returns a string suitable for ``<pre class="mermaid">…</pre>``.
    """
    if not calls:
        return "graph LR\n  empty[No tool calls recorded]"

    lines: list[str] = ["graph TD"]

    # 1) Group all calls (preserving order) into parallel batches / singles
    all_groups = _group_calls(calls)
    group_walls: dict[tuple[int, ...], float] = {}
    group_end_times: dict[tuple[int, ...], float] = {}
    prev_group_end = 0.0
    for group in all_groups:
        group_end = _group_end_sec(group)
        group_key = _group_key(group)
        group_walls[group_key] = max(0.0, group_end - prev_group_end)
        group_end_times[group_key] = group_end
        prev_group_end = group_end

    # 2) Split the call stream into chronological phase segments.
    phase_names = {0: "Triage", 1: "Discovery", 2: "Planning", 3: "Execution"}
    phase_segments = _phase_segments(all_groups)

    # 3) Render each phase subgraph
    prev_tail_nodes: list[str] = []  # last node-ids of the previous phase

    for segment_index, (phase_id, groups) in enumerate(phase_segments, start=1):
        phase_label = phase_names.get(phase_id, f"Phase {phase_id}")
        lines.append(f"  subgraph phase{phase_id}_seg{segment_index}[\"{phase_label}\"]")

        prev_nodes: list[str] = []  # trailing node-ids within this phase

        for grp in groups:
            group_key = _group_key(grp)
            group_wall_sec = group_walls.get(group_key)
            group_end_sec = group_end_times.get(group_key)
            if len(grp) == 1:
                # ── Sequential node ──────────────────────────────────
                call = grp[0]
                nid = _node_id(call)
                label = _sequential_label(call, group_wall_sec, group_end_sec)

                if call.is_error:
                    lines.append(f"    {nid}[\"{label}\"]:::errorNode")
                else:
                    lines.append(f"    {nid}[\"{label}\"]")

                # Connect from previous
                for pn in prev_nodes:
                    lines.append(f"    {pn} --> {nid}")

                prev_nodes = [nid]

            else:
                # ── Parallel fork / join ─────────────────────────────
                fid = _fork_id(grp)
                jid = _join_id(grp)
                count = len(grp)

                lines.append(f"    {fid}{{\"{count}x parallel\"}}:::forkNode")

                par_ids: list[str] = []
                for call in grp:
                    nid = _node_id(call)
                    label = _parallel_label(call)

                    if call.is_error:
                        lines.append(f"    {nid}[\"{label}\"]:::errorNode")
                    else:
                        lines.append(f"    {nid}([\"{label}\"]):::parallelNode")

                    # fork → each parallel node
                    lines.append(f"    {fid} --> {nid}")
                    par_ids.append(nid)

                # join node
                if group_wall_sec is not None and group_end_sec is not None:
                    join_label = f"join\\nwall {_format_seconds(group_wall_sec)}\\n@ {_format_seconds(group_end_sec)}"
                elif group_wall_sec is not None:
                    join_label = f"join\\nwall {_format_seconds(group_wall_sec)}"
                else:
                    join_label = "join"
                lines.append(f"    {jid}{{\"{join_label}\"}}:::forkNode")
                for pid in par_ids:
                    lines.append(f"    {pid} --> {jid}")

                # Connect from previous → fork
                for pn in prev_nodes:
                    lines.append(f"    {pn} --> {fid}")

                prev_nodes = [jid]

        lines.append("  end")

        # Inter-phase edges: previous phase tail → this phase head
        if prev_tail_nodes and groups:
            first_grp = groups[0]
            head = _fork_id(first_grp) if len(first_grp) > 1 else _node_id(first_grp[0])
            for pn in prev_tail_nodes:
                lines.append(f"  {pn} --> {head}")

        prev_tail_nodes = prev_nodes

    # Style classes
    lines.append("  classDef errorNode fill:#e74c3c,stroke:#c0392b,color:#fff")
    lines.append("  classDef forkNode fill:#f8f9fa,stroke:#6c757d,color:#333")
    lines.append("  classDef parallelNode fill:#17a2b8,stroke:#138496,color:#fff")
    lines.append("  classDef default fill:#3498db,stroke:#2980b9,color:#fff")

    return "\n".join(lines)
