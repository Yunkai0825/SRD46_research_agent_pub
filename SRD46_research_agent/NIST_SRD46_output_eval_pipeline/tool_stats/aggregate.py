"""Aggregate tool-call and workflow statistics into CSV/JSON outputs."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config

from .loader import RunRecord, ToolCallRecord, WorkflowGroupRecord


_COMPACTOR_DETAILS_RE = re.compile(
    r"<details><summary>Full compactor log</summary>\s*(?P<body>.*?)\s*</details>",
    re.DOTALL,
)
_COMPACTOR_LINE_RE = re.compile(
    r"^- \*\*\[(?P<level>[A-Z]+)\]\*\* \(after iter (?P<after_iteration>\d+)\)\s+(?P<message>.+)$",
    re.MULTILINE,
)
_COMPACTOR_CHANNEL_RE = re.compile(r"^\[(?P<channel>[^\]]+)\]\s*(?P<body>.*)$")
_CONTEXT_WINDOW_RE = re.compile(r"Context window:\s*(?P<chars>\d+)\s+chars across\s+(?P<turns>\d+)\s+turns")
_SELECTED_RE = re.compile(r"Argo selected candidates \[(?P<candidates>[0-9,\s]+)\] for compression")
_CHOOSE_NONE_RE = re.compile(r"Argo chose NONE\b")
_RUNNING_TASKS_RE = re.compile(r"Running (?P<count>\d+) compression task\(s\) in parallel")
_L0_RUNNING_TASKS_RE = re.compile(r"Running (?P<count>\d+) L0 hint-driven compression\(s\) in parallel")
_HARDCODED_RE = re.compile(r"Hardcoded compactor used for (?P<tool>.+?) \((?P<chars>\d+) chars\)")
_GENERIC_RE = re.compile(r"Generic markdown renderer used for (?P<tool>.+?) \((?P<chars>\d+) chars\)")
_SUMMARY_OK_RE = re.compile(
    r"Summary sub-agent produced (?P<summary_chars>\d+)-char summary \(budget=(?P<budget>\d+), tokens=(?P<tokens>\d+)\)"
)
_SUMMARY_FAIL_RE = re.compile(
    r"Summary sub-agent failed: (?P<reason>.+?)\s+(?:\u2014|-)\s+falling back to preview"
)
_ACCEPTED_RE = re.compile(
    r"Compacted memory\[(?P<memory_idx>\d+)\]: (?P<before_chars>\d+)(?:\u2192|->)(?P<after_chars>\d+) chars \(ACCEPTED, attempt (?P<attempt>\d+)/(?P<max_attempt>\d+)\)"
)
_SKIPPED_RE = re.compile(
    r"memory\[(?P<memory_idx>\d+)\] SKIPPED by validator \(attempt (?P<attempt>\d+)/(?P<max_attempt>\d+), (?P<chars>\d+) chars\)"
)
_RETRY_RE = re.compile(
    r"memory\[(?P<memory_idx>\d+)\] RETRY attempt (?P<attempt>\d+)/(?P<max_attempt>\d+): (?P<reason>.+)"
)
_EXHAUSTED_RE = re.compile(
    r"memory\[(?P<memory_idx>\d+)\] exhausted (?P<inner_retries>\d+) inner retries, marked RETRY:(?P<marked_retry>\d+) \((?P<chars>\d+) chars\)"
)
_MAX_RETRY_KEEP_RE = re.compile(
    r"memory\[(?P<memory_idx>\d+)\] hit MAX_RETRY=(?P<max_retry>\d+)\s+(?:\u2014|-)\s+permanently keeping original \((?P<chars>\d+) chars\)"
)
_L0_NO_MATCH_RE = re.compile(r"No L0 results matched compression hints\b")


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    fraction = rank - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def _mean(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def _warning_threshold_sec() -> float:
    return float(getattr(argo_config, "MAX_TURN_SECONDS", 600))


def _planning_reference_sec(runs: list[RunRecord]) -> float | None:
    values = [run.planning_time_sec for run in runs if run.planning_time_sec is not None]
    return _mean(values)


def _major_section(section: str) -> str:
    text = section or ""
    # Section 5 is split into 5.1 (ambiguous) and 5.2 (negative-edge), which are
    # categorically different evaluation modes and must not be merged.
    if text.startswith("5."):
        return ".".join(text.split(".")[:2])
    return text.split(".", 1)[0]


def _annotate_run_timing_rows(rows: list[dict[str, object]], runs: list[RunRecord]) -> list[dict[str, object]]:
    warning_threshold = _warning_threshold_sec()
    planning_reference = _planning_reference_sec(runs)
    for row in rows:
        row["warning_threshold_sec"] = warning_threshold
        row["planning_reference_sec"] = planning_reference
    return rows


def _run_key(model: str, question_id: str, batch: int) -> tuple[str, str, int]:
    return model, question_id, batch


def _include_usage_tool(tool_name: str) -> bool:
    return bool(tool_name) and not tool_name.startswith("0_")


def _write_rows(base_name: str, rows: list[dict[str, object]], fieldnames: list[str], out_dir: Path, json_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{base_name}.csv"
    json_path = json_dir / f"{base_name}.json"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return csv_path


def _tool_usage_rows(
    tool_calls: list[ToolCallRecord],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0, "sample": run})
        stats["n_runs"] += 1

    total_calls_by_group: dict[tuple, int] = defaultdict(int)

    usage: dict[tuple, dict[str, object]] = {}
    for call in tool_calls:
        if not _include_usage_tool(call.tool_name):
            continue
        group_key = tuple(getattr(call, field) for field in group_fields)
        total_calls_by_group[group_key] += 1
        key = group_key + (call.tool_name,)
        stats = usage.setdefault(
            key,
            {
                "sample": call,
                "n_calls": 0,
                "successful_calls": 0,
                "error_calls": 0,
                "durations": [],
                "walls": [],
                "runs": set(),
            },
        )
        stats["n_calls"] += 1
        stats["error_calls"] += int(call.is_error)
        if not call.is_error:
            stats["successful_calls"] += 1
            stats["durations"].append(call.duration_sec)
            stats["walls"].append(call.wall_sec)
        stats["runs"].add(_run_key(call.model, call.question_id, call.batch))

    rows: list[dict[str, object]] = []
    for key, stats in sorted(usage.items(), key=lambda item: (-item[1]["n_calls"], item[0])):
        group_key = key[:-1]
        tool_name = key[-1]
        sample = stats["sample"]
        total = run_totals.get(group_key, {"n_runs": 0})
        n_runs = int(total["n_runs"])
        total_calls = total_calls_by_group.get(group_key, 0)
        row: dict[str, object] = {field: value for field, value in zip(group_fields, group_key)}
        if "question_id" in group_fields:
            row["section"] = sample.section
            row["section_title"] = sample.section_title
            row["eval_mode"] = sample.eval_mode
            row["prompt_text"] = sample.prompt_text
        row.update(
            {
                "tool_name": tool_name,
                "n_runs": n_runs,
                "runs_with_tool": len(stats["runs"]),
                "run_presence_rate": (len(stats["runs"]) / n_runs) if n_runs else None,
                "n_calls": stats["n_calls"],
                "call_share": (stats["n_calls"] / total_calls) if total_calls else None,
                "mean_calls_per_run": (stats["n_calls"] / n_runs) if n_runs else None,
                "successful_calls": stats["successful_calls"],
                "error_calls": stats["error_calls"],
                "error_rate": (stats["error_calls"] / stats["n_calls"]) if stats["n_calls"] else None,
                "duration_total_sec": sum(stats["durations"]) if stats["durations"] else None,
                "duration_mean_sec": _mean(stats["durations"]),
                "duration_p50_sec": _percentile(stats["durations"], 0.50),
                "duration_p95_sec": _percentile(stats["durations"], 0.95),
                "wall_total_sec": sum(stats["walls"]) if stats["walls"] else None,
                "wall_mean_sec": _mean(stats["walls"]),
                "wall_p50_sec": _percentile(stats["walls"], 0.50),
                "wall_p95_sec": _percentile(stats["walls"], 0.95),
            }
        )
        rows.append(row)
    return rows


def emit_tool_usage(tool_calls: list[ToolCallRecord], runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    specs = {
        "overall": tuple(),
        "model": ("model",),
        "prompt": ("question_id",),
        "eval_mode": ("eval_mode",),
        "model_prompt": ("model", "question_id"),
    }
    fieldnames = {
        "overall": [
            "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "call_share",
            "mean_calls_per_run", "successful_calls", "error_calls", "error_rate", "duration_total_sec", "duration_mean_sec",
            "duration_p50_sec", "duration_p95_sec", "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "model": [
            "model", "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "call_share",
            "mean_calls_per_run", "successful_calls", "error_calls", "error_rate", "duration_total_sec", "duration_mean_sec",
            "duration_p50_sec", "duration_p95_sec", "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "prompt": [
            "question_id", "section", "section_title", "eval_mode", "prompt_text", "tool_name", "n_runs",
            "runs_with_tool", "run_presence_rate", "n_calls", "call_share", "mean_calls_per_run", "successful_calls", "error_calls",
            "error_rate", "duration_total_sec", "duration_mean_sec", "duration_p50_sec", "duration_p95_sec",
            "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "eval_mode": [
            "eval_mode", "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "call_share",
            "mean_calls_per_run", "successful_calls", "error_calls", "error_rate", "duration_total_sec", "duration_mean_sec",
            "duration_p50_sec", "duration_p95_sec", "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "model_prompt": [
            "model", "question_id", "section", "section_title", "eval_mode", "prompt_text", "tool_name", "n_runs",
            "runs_with_tool", "run_presence_rate", "n_calls", "call_share", "mean_calls_per_run", "successful_calls", "error_calls",
            "error_rate", "duration_total_sec", "duration_mean_sec", "duration_p50_sec", "duration_p95_sec",
            "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
    }
    written: dict[str, Path] = {}
    for name, group_fields in specs.items():
        rows = _tool_usage_rows(tool_calls, runs, group_fields=group_fields)
        filename = f"tool_usage_{name}" if name == "overall" else f"tool_usage_by_{name}"
        written[name] = _write_rows(filename, rows, fieldnames[name], out_dir, json_dir)
    return written


def _tool_argo_timing_rows(
    tool_calls: list[ToolCallRecord],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0, "sample": run})
        stats["n_runs"] += 1

    timing: dict[tuple, dict[str, object]] = {}
    for call in tool_calls:
        group_key = tuple(getattr(call, field) for field in group_fields)
        key = group_key + (call.tool_name,)
        stats = timing.setdefault(
            key,
            {
                "sample": call,
                "n_calls": 0,
                "successful_calls": 0,
                "error_calls": 0,
                "argo_timed_calls": 0,
                "argo_durations": [],
                "runs": set(),
                "timed_runs": set(),
            },
        )
        stats["n_calls"] += 1
        stats["error_calls"] += int(call.is_error)
        stats["runs"].add(_run_key(call.model, call.question_id, call.batch))
        if not call.is_error:
            stats["successful_calls"] += 1
            if call.argo_analysis_sec is not None:
                stats["argo_timed_calls"] += 1
                stats["argo_durations"].append(call.argo_analysis_sec)
                stats["timed_runs"].add(_run_key(call.model, call.question_id, call.batch))

    rows: list[dict[str, object]] = []
    for key, stats in sorted(timing.items(), key=lambda item: (-item[1]["argo_timed_calls"], item[0])):
        if not stats["argo_timed_calls"]:
            continue
        group_key = key[:-1]
        tool_name = key[-1]
        sample = stats["sample"]
        total = run_totals.get(group_key, {"n_runs": 0})
        n_runs = int(total["n_runs"])
        row: dict[str, object] = {field: value for field, value in zip(group_fields, group_key)}
        row.update(
            {
                "tool_name": tool_name,
                "n_runs": n_runs,
                "runs_with_tool": len(stats["runs"]),
                "run_presence_rate": (len(stats["runs"]) / n_runs) if n_runs else None,
                "n_calls": stats["n_calls"],
                "successful_calls": stats["successful_calls"],
                "error_calls": stats["error_calls"],
                "argo_timed_calls": stats["argo_timed_calls"],
                "argo_coverage_rate": (stats["argo_timed_calls"] / stats["successful_calls"]) if stats["successful_calls"] else None,
                "runs_with_argo_timing": len(stats["timed_runs"]),
                "argo_run_presence_rate": (len(stats["timed_runs"]) / n_runs) if n_runs else None,
                "argo_duration_total_sec": sum(stats["argo_durations"]) if stats["argo_durations"] else None,
                "argo_duration_mean_sec": _mean(stats["argo_durations"]),
                "argo_duration_p50_sec": _percentile(stats["argo_durations"], 0.50),
                "argo_duration_p95_sec": _percentile(stats["argo_durations"], 0.95),
            }
        )
        rows.append(row)
    return rows


def emit_tool_argo_timing(tool_calls: list[ToolCallRecord], runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    specs = {
        "overall": tuple(),
        "model": ("model",),
    }
    fieldnames = {
        "overall": [
            "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "successful_calls", "error_calls",
            "argo_timed_calls", "argo_coverage_rate", "runs_with_argo_timing", "argo_run_presence_rate",
            "argo_duration_total_sec", "argo_duration_mean_sec", "argo_duration_p50_sec", "argo_duration_p95_sec",
        ],
        "model": [
            "model", "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "successful_calls", "error_calls",
            "argo_timed_calls", "argo_coverage_rate", "runs_with_argo_timing", "argo_run_presence_rate",
            "argo_duration_total_sec", "argo_duration_mean_sec", "argo_duration_p50_sec", "argo_duration_p95_sec",
        ],
    }
    written: dict[str, Path] = {}
    for name, group_fields in specs.items():
        rows = _tool_argo_timing_rows(tool_calls, runs, group_fields=group_fields)
        filename = f"tool_argo_timing_{name}" if name == "overall" else f"tool_argo_timing_by_{name}"
        written[name] = _write_rows(filename, rows, fieldnames[name], out_dir, json_dir)
    return written


def _tool_wall_timing_rows(
    tool_calls: list[ToolCallRecord],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0, "sample": run})
        stats["n_runs"] += 1

    last_group_by_run: dict[tuple[str, str, int], int] = {}
    for call in tool_calls:
        run_key = _run_key(call.model, call.question_id, call.batch)
        previous = last_group_by_run.get(run_key)
        if previous is None or call.parallel_group_id > previous:
            last_group_by_run[run_key] = call.parallel_group_id

    timing: dict[tuple, dict[str, object]] = {}
    for call in tool_calls:
        if not _include_usage_tool(call.tool_name):
            continue
        group_key = tuple(getattr(call, field) for field in group_fields)
        key = group_key + (call.tool_name,)
        stats = timing.setdefault(
            key,
            {
                "sample": call,
                "n_calls": 0,
                "successful_calls": 0,
                "error_calls": 0,
                "wall_timed_calls": 0,
                "wall_durations": [],
                "runs": set(),
                "timed_runs": set(),
            },
        )
        stats["n_calls"] += 1
        stats["error_calls"] += int(call.is_error)
        stats["runs"].add(_run_key(call.model, call.question_id, call.batch))
        if not call.is_error:
            stats["successful_calls"] += 1
            if call.parallel_group_id != last_group_by_run.get(_run_key(call.model, call.question_id, call.batch)):
                stats["wall_timed_calls"] += 1
                stats["wall_durations"].append(call.wall_sec)
                stats["timed_runs"].add(_run_key(call.model, call.question_id, call.batch))

    rows: list[dict[str, object]] = []
    for key, stats in sorted(timing.items(), key=lambda item: (-item[1]["wall_timed_calls"], item[0])):
        group_key = key[:-1]
        tool_name = key[-1]
        total = run_totals.get(group_key, {"n_runs": 0})
        n_runs = int(total["n_runs"])
        row: dict[str, object] = {field: value for field, value in zip(group_fields, group_key)}
        row.update(
            {
                "tool_name": tool_name,
                "n_runs": n_runs,
                "runs_with_tool": len(stats["runs"]),
                "run_presence_rate": (len(stats["runs"]) / n_runs) if n_runs else None,
                "n_calls": stats["n_calls"],
                "successful_calls": stats["successful_calls"],
                "error_calls": stats["error_calls"],
                "wall_timed_calls": stats["wall_timed_calls"],
                "wall_coverage_rate": (stats["wall_timed_calls"] / stats["successful_calls"]) if stats["successful_calls"] else None,
                "runs_with_wall_timing": len(stats["timed_runs"]),
                "wall_run_presence_rate": (len(stats["timed_runs"]) / n_runs) if n_runs else None,
                "wall_total_sec": sum(stats["wall_durations"]) if stats["wall_durations"] else None,
                "wall_mean_sec": _mean(stats["wall_durations"]),
                "wall_p50_sec": _percentile(stats["wall_durations"], 0.50),
                "wall_p95_sec": _percentile(stats["wall_durations"], 0.95),
            }
        )
        rows.append(row)
    return rows


def emit_tool_wall_timing(tool_calls: list[ToolCallRecord], runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    specs = {
        "overall": tuple(),
        "model": ("model",),
    }
    fieldnames = {
        "overall": [
            "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "successful_calls",
            "error_calls", "wall_timed_calls", "wall_coverage_rate", "runs_with_wall_timing", "wall_run_presence_rate",
            "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "model": [
            "model", "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "successful_calls",
            "error_calls", "wall_timed_calls", "wall_coverage_rate", "runs_with_wall_timing", "wall_run_presence_rate",
            "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
    }
    written: dict[str, Path] = {}
    for name, group_fields in specs.items():
        rows = _tool_wall_timing_rows(tool_calls, runs, group_fields=group_fields)
        filename = f"tool_wall_timing_{name}" if name == "overall" else f"tool_wall_timing_by_{name}"
        written[name] = _write_rows(filename, rows, fieldnames[name], out_dir, json_dir)
    return written


def _run_timing_rows(runs: list[RunRecord], *, group_fields: tuple[str, ...]) -> list[dict[str, object]]:
    grouped: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(_major_section(run.section) if field == "major_section" else getattr(run, field) for field in group_fields)
        stats = grouped.setdefault(
            key,
            {
                "sample": run,
                "runs": [],
                "planning": [],
                "execution": [],
                "verdict": [],
                "total": [],
                "tool_calls": [],
                "parsed_tool_calls": [],
                "answer_words": [],
                "error_runs": 0,
                "questions": set(),
            },
        )
        stats["runs"].append(run)
        stats["questions"].add(run.question_id)
        if run.planning_time_sec is not None:
            stats["planning"].append(run.planning_time_sec)
        if run.execution_time_sec is not None:
            stats["execution"].append(run.execution_time_sec)
        if run.verdict_time_sec is not None:
            stats["verdict"].append(run.verdict_time_sec)
        if run.total_time_sec is not None:
            stats["total"].append(run.total_time_sec)
        if run.total_tool_calls is not None:
            stats["tool_calls"].append(float(run.total_tool_calls))
        stats["parsed_tool_calls"].append(float(run.parsed_tool_calls))
        stats["answer_words"].append(float(run.answer_word_count))
        stats["error_runs"] += int(run.had_error)

    rows: list[dict[str, object]] = []
    for key, stats in sorted(grouped.items(), key=lambda item: item[0]):
        sample = stats["sample"]
        row: dict[str, object] = {field: value for field, value in zip(group_fields, key)}
        if "question_id" in group_fields:
            row["section"] = sample.section
            row["section_title"] = sample.section_title
            row["eval_mode"] = sample.eval_mode
            row["prompt_text"] = sample.prompt_text
        elif "section" in group_fields:
            row["section_title"] = sample.section_title
            row["n_questions"] = len(stats["questions"])
        elif "major_section" in group_fields:
            row["n_questions"] = len(stats["questions"])
        n_runs = len(stats["runs"])
        row.update(
            {
                "n_runs": n_runs,
                "error_run_rate": (stats["error_runs"] / n_runs) if n_runs else None,
                "mean_total_tool_calls": _mean(stats["tool_calls"]),
                "mean_parsed_tool_calls": _mean(stats["parsed_tool_calls"]),
                "planning_mean_sec": _mean(stats["planning"]),
                "execution_mean_sec": _mean(stats["execution"]),
                "verdict_mean_sec": _mean(stats["verdict"]),
                "total_mean_sec": _mean(stats["total"]),
                "total_p50_sec": _percentile(stats["total"], 0.50),
                "total_p95_sec": _percentile(stats["total"], 0.95),
                "answer_word_mean": _mean(stats["answer_words"]),
            }
        )
        rows.append(row)
    return rows


def emit_run_timing(runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    specs = {
        "overall": tuple(),
        "model": ("model",),
        "section": ("section",),
        "major_section": ("major_section",),
        "prompt": ("question_id",),
        "eval_mode": ("eval_mode",),
        "model_section": ("model", "section"),
        "model_major_section": ("model", "major_section"),
        "model_prompt": ("model", "question_id"),
    }
    fieldnames = {
        "overall": [
            "n_runs", "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec",
            "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec",
            "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
        "model": [
            "model", "n_runs", "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls",
            "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec",
            "total_p95_sec", "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
        "section": [
            "section", "section_title", "n_questions", "n_runs", "error_run_rate", "mean_total_tool_calls",
            "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec",
            "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean", "warning_threshold_sec",
            "planning_reference_sec",
        ],
        "major_section": [
            "major_section", "n_questions", "n_runs", "error_run_rate", "mean_total_tool_calls",
            "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec",
            "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean", "warning_threshold_sec",
            "planning_reference_sec",
        ],
        "prompt": [
            "question_id", "section", "section_title", "eval_mode", "prompt_text", "n_runs", "error_run_rate",
            "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec",
            "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean",
            "warning_threshold_sec", "planning_reference_sec",
        ],
        "eval_mode": [
            "eval_mode", "n_runs", "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls",
            "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec",
            "total_p95_sec", "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
        "model_section": [
            "model", "section", "section_title", "n_questions", "n_runs", "error_run_rate",
            "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec",
            "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean",
            "warning_threshold_sec", "planning_reference_sec",
        ],
        "model_major_section": [
            "model", "major_section", "n_questions", "n_runs", "error_run_rate", "mean_total_tool_calls",
            "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec",
            "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean", "warning_threshold_sec",
            "planning_reference_sec",
        ],
        "model_prompt": [
            "model", "question_id", "section", "section_title", "eval_mode", "prompt_text", "n_runs",
            "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec",
            "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec",
            "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
    }
    written: dict[str, Path] = {}
    for name, group_fields in specs.items():
        rows = _annotate_run_timing_rows(_run_timing_rows(runs, group_fields=group_fields), runs)
        filename = f"run_timing_{name}" if name == "overall" else f"run_timing_by_{name}"
        written[name] = _write_rows(filename, rows, fieldnames[name], out_dir, json_dir)
    return written


def emit_tool_failures(tool_calls: list[ToolCallRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    detailed_rows = []
    grouped: dict[tuple[str, str | None, str | None], dict[str, object]] = {}
    for call in tool_calls:
        if not call.is_error:
            continue
        detailed_rows.append(
            {
                "model": call.model,
                "question_id": call.question_id,
                "section": call.section,
                "eval_mode": call.eval_mode,
                "batch": call.batch,
                "step_num": call.step_num,
                "tool_name": call.tool_name,
                "phase": call.phase,
                "error_category": call.error_category,
                "error_reason": call.error_reason,
                "error_message": call.error_message,
                "duration_sec": call.duration_sec,
                "parallel_group_signature": call.parallel_group_signature,
            }
        )
        key = (call.tool_name, call.error_category, call.error_reason)
        stats = grouped.setdefault(
            key,
            {
                "count": 0,
                "models": set(),
                "prompts": set(),
                "sample": call,
            },
        )
        stats["count"] += 1
        stats["models"].add(call.model)
        stats["prompts"].add(call.question_id)

    summary_rows = []
    for (tool_name, error_category, error_reason), stats in sorted(grouped.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        summary_rows.append(
            {
                "tool_name": tool_name,
                "error_category": error_category,
                "error_reason": error_reason,
                "n_failures": stats["count"],
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "example_model": sample.model,
                "example_question_id": sample.question_id,
                "example_message": sample.error_message,
            }
        )

    return {
        "detailed": _write_rows(
            "tool_failures_detailed",
            detailed_rows,
            [
                "model", "question_id", "section", "eval_mode", "batch", "step_num", "tool_name", "phase",
                "error_category", "error_reason", "error_message", "duration_sec", "parallel_group_signature",
            ],
            out_dir,
            json_dir,
        ),
        "summary": _write_rows(
            "tool_failures_by_reason",
            summary_rows,
            [
                "tool_name", "error_category", "error_reason", "n_failures", "n_models", "n_prompts",
                "example_model", "example_question_id", "example_message",
            ],
            out_dir,
            json_dir,
        ),
    }


def emit_parallel_stats(workflow_groups: list[WorkflowGroupRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    batches = [group for group in workflow_groups if group.group_size > 1]
    batch_summary: dict[tuple[str, int], dict[str, object]] = {}
    pair_summary: dict[tuple[str, str], dict[str, object]] = {}
    for group in batches:
        key = (group.group_signature, group.group_size)
        stats = batch_summary.setdefault(
            key,
            {
                "count": 0,
                "models": set(),
                "prompts": set(),
                "walls": [],
                "tool_sums": [],
                "error_batches": 0,
                "sample": group,
            },
        )
        stats["count"] += 1
        stats["models"].add(group.model)
        stats["prompts"].add(group.question_id)
        stats["walls"].append(group.wall_sec)
        stats["tool_sums"].append(group.tool_duration_sum_sec)
        stats["error_batches"] += int(group.has_error)

        names = group.tool_names.split(" || ")
        for left_index, right_index in combinations(range(len(names)), 2):
            pair = tuple(sorted((names[left_index], names[right_index])))
            pair_stats = pair_summary.setdefault(
                pair,
                {
                    "count": 0,
                    "models": set(),
                    "prompts": set(),
                    "walls": [],
                },
            )
            pair_stats["count"] += 1
            pair_stats["models"].add(group.model)
            pair_stats["prompts"].add(group.question_id)
            pair_stats["walls"].append(group.wall_sec)

    batch_rows = []
    for (signature, group_size), stats in sorted(batch_summary.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        batch_rows.append(
            {
                "group_signature": signature,
                "batch_size": group_size,
                "n_occurrences": stats["count"],
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "mean_wall_sec": _mean(stats["walls"]),
                "mean_tool_duration_sum_sec": _mean(stats["tool_sums"]),
                "error_batch_rate": (stats["error_batches"] / stats["count"]) if stats["count"] else None,
                "example_model": sample.model,
                "example_question_id": sample.question_id,
            }
        )

    pair_rows = []
    for (tool_a, tool_b), stats in sorted(pair_summary.items(), key=lambda item: (-item[1]["count"], item[0])):
        pair_rows.append(
            {
                "tool_a": tool_a,
                "tool_b": tool_b,
                "n_occurrences": stats["count"],
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "mean_wall_sec": _mean(stats["walls"]),
            }
        )

    return {
        "batches": _write_rows(
            "parallel_batch_patterns",
            batch_rows,
            [
                "group_signature", "batch_size", "n_occurrences", "n_models", "n_prompts", "mean_wall_sec",
                "mean_tool_duration_sum_sec", "error_batch_rate", "example_model", "example_question_id",
            ],
            out_dir,
            json_dir,
        ),
        "pairs": _write_rows(
            "parallel_tool_pairs",
            pair_rows,
            ["tool_a", "tool_b", "n_occurrences", "n_models", "n_prompts", "mean_wall_sec"],
            out_dir,
            json_dir,
        ),
    }


def emit_workflow_snippets(workflow_groups: list[WorkflowGroupRecord], out_dir: Path, json_dir: Path) -> Path:
    by_run: dict[tuple[str, str, int], list[WorkflowGroupRecord]] = defaultdict(list)
    for group in workflow_groups:
        by_run[_run_key(group.model, group.question_id, group.batch)].append(group)

    snippets: dict[tuple[int, str], dict[str, object]] = {}
    for run_key, groups in by_run.items():
        ordered = sorted(groups, key=lambda item: item.group_index)
        tokens = [group.group_token for group in ordered]
        model, question_id, _batch = run_key
        for size in (2, 3, 4):
            if len(tokens) < size:
                continue
            for index in range(len(tokens) - size + 1):
                snippet = " -> ".join(tokens[index:index + size])
                key = (size, snippet)
                stats = snippets.setdefault(
                    key,
                    {
                        "count": 0,
                        "runs": set(),
                        "models": set(),
                        "prompts": set(),
                        "sample": ordered[index],
                    },
                )
                stats["count"] += 1
                stats["runs"].add(run_key)
                stats["models"].add(model)
                stats["prompts"].add(question_id)

    rows = []
    for (snippet_len, snippet), stats in sorted(snippets.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        rows.append(
            {
                "snippet_len": snippet_len,
                "snippet": snippet,
                "n_occurrences": stats["count"],
                "n_runs": len(stats["runs"]),
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "example_model": sample.model,
                "example_question_id": sample.question_id,
            }
        )
    return _write_rows(
        "workflow_snippets",
        rows,
        ["snippet_len", "snippet", "n_occurrences", "n_runs", "n_models", "n_prompts", "example_model", "example_question_id"],
        out_dir,
        json_dir,
    )


def _token_contains_zero_tool(token: str) -> bool:
    text = (token or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    parts = [part.strip() for part in text.split("||")]
    return any(part.startswith("0_") for part in parts if part)


def emit_second_order_tool_chains(workflow_groups: list[WorkflowGroupRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    by_run: dict[tuple[str, str, int], list[WorkflowGroupRecord]] = defaultdict(list)
    for group in workflow_groups:
        by_run[_run_key(group.model, group.question_id, group.batch)].append(group)

    overall: dict[str, dict[str, object]] = {}
    by_model: dict[tuple[str, str], dict[str, object]] = {}
    for run_key, groups in by_run.items():
        ordered = sorted(groups, key=lambda item: item.group_index)
        filtered = [group for group in ordered if not _token_contains_zero_tool(group.group_token)]
        if len(filtered) < 2:
            continue
        model, question_id, _batch = run_key
        for index in range(len(filtered) - 1):
            left = filtered[index]
            right = filtered[index + 1]
            chain = f"{left.group_token} -> {right.group_token}"

            overall_stats = overall.setdefault(
                chain,
                {
                    "count": 0,
                    "runs": set(),
                    "models": set(),
                    "prompts": set(),
                    "sample": left,
                },
            )
            overall_stats["count"] += 1
            overall_stats["runs"].add(run_key)
            overall_stats["models"].add(model)
            overall_stats["prompts"].add(question_id)

            model_stats = by_model.setdefault(
                (model, chain),
                {
                    "count": 0,
                    "runs": set(),
                    "prompts": set(),
                    "sample": left,
                },
            )
            model_stats["count"] += 1
            model_stats["runs"].add(run_key)
            model_stats["prompts"].add(question_id)

    overall_rows = []
    for chain, stats in sorted(overall.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        overall_rows.append(
            {
                "chain_order": 2,
                "chain": chain,
                "n_occurrences": stats["count"],
                "n_runs": len(stats["runs"]),
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "example_model": sample.model,
                "example_question_id": sample.question_id,
            }
        )

    model_rows = []
    for (model, chain), stats in sorted(by_model.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        model_rows.append(
            {
                "model": model,
                "chain_order": 2,
                "chain": chain,
                "n_occurrences": stats["count"],
                "n_runs": len(stats["runs"]),
                "n_prompts": len(stats["prompts"]),
                "example_question_id": sample.question_id,
            }
        )

    return {
        "overall": _write_rows(
            "tool_chain_second_order_overall",
            overall_rows,
            ["chain_order", "chain", "n_occurrences", "n_runs", "n_models", "n_prompts", "example_model", "example_question_id"],
            out_dir,
            json_dir,
        ),
        "model": _write_rows(
            "tool_chain_second_order_by_model",
            model_rows,
            ["model", "chain_order", "chain", "n_occurrences", "n_runs", "n_prompts", "example_question_id"],
            out_dir,
            json_dir,
        ),
    }


def _parse_compactor_events_for_run(run: RunRecord) -> list[dict[str, object]]:
    history_path = Path(run.history_path)
    if not history_path.exists():
        return []
    text = history_path.read_text(encoding="utf-8", errors="replace")
    details_match = _COMPACTOR_DETAILS_RE.search(text)
    if not details_match:
        return []

    events: list[dict[str, object]] = []
    for event_index, match in enumerate(_COMPACTOR_LINE_RE.finditer(details_match.group("body")), start=1):
        raw_message = match.group("message").strip()
        channel_match = _COMPACTOR_CHANNEL_RE.match(raw_message)
        channel = channel_match.group("channel") if channel_match else ""
        body = channel_match.group("body").strip() if channel_match else raw_message
        row: dict[str, object] = {
            "model": run.model,
            "question_id": run.question_id,
            "section": run.section,
            "section_title": run.section_title,
            "eval_mode": run.eval_mode,
            "batch": run.batch,
            "history_path": run.history_path,
            "event_index": event_index,
            "after_iteration": int(match.group("after_iteration")),
            "level": match.group("level"),
            "channel": channel,
            "event_type": "other",
            "message": raw_message,
            "detail_message": body,
            "target_tool_name": None,
            "content_chars": None,
            "context_chars": None,
            "context_turns": None,
            "selected_candidates": None,
            "selected_candidate_count": None,
            "parallel_task_count": None,
            "attempt_num": None,
            "max_attempt_num": None,
            "memory_idx": None,
            "before_chars": None,
            "after_chars": None,
            "summary_chars": None,
            "summary_budget_chars": None,
            "summary_budget_tokens": None,
            "inner_retry_count": None,
            "marked_retry_count": None,
            "retry_reason": None,
        }

        if context_match := _CONTEXT_WINDOW_RE.search(body):
            row["event_type"] = "context_window"
            row["context_chars"] = int(context_match.group("chars"))
            row["context_turns"] = int(context_match.group("turns"))
        elif selected_match := _SELECTED_RE.search(body):
            candidates = [token.strip() for token in selected_match.group("candidates").split(",") if token.strip()]
            row["event_type"] = "selected_candidates"
            row["selected_candidates"] = ",".join(candidates)
            row["selected_candidate_count"] = len(candidates)
        elif _CHOOSE_NONE_RE.search(body):
            row["event_type"] = "chose_none"
        elif running_match := _RUNNING_TASKS_RE.search(body):
            row["event_type"] = "running_tasks"
            row["parallel_task_count"] = int(running_match.group("count"))
        elif l0_running_match := _L0_RUNNING_TASKS_RE.search(body):
            row["event_type"] = "l0_running_tasks"
            row["parallel_task_count"] = int(l0_running_match.group("count"))
        elif hardcoded_match := _HARDCODED_RE.search(body):
            row["event_type"] = "hardcoded_compactor"
            row["target_tool_name"] = hardcoded_match.group("tool")
            row["content_chars"] = int(hardcoded_match.group("chars"))
        elif generic_match := _GENERIC_RE.search(body):
            row["event_type"] = "generic_renderer"
            row["target_tool_name"] = generic_match.group("tool")
            row["content_chars"] = int(generic_match.group("chars"))
        elif summary_ok_match := _SUMMARY_OK_RE.search(body):
            row["event_type"] = "summary_subagent_produced"
            row["summary_chars"] = int(summary_ok_match.group("summary_chars"))
            row["summary_budget_chars"] = int(summary_ok_match.group("budget"))
            row["summary_budget_tokens"] = int(summary_ok_match.group("tokens"))
        elif summary_fail_match := _SUMMARY_FAIL_RE.search(body):
            row["event_type"] = "summary_subagent_failed"
            row["retry_reason"] = summary_fail_match.group("reason")
        elif accepted_match := _ACCEPTED_RE.search(body):
            row["event_type"] = "validator_accepted"
            row["memory_idx"] = int(accepted_match.group("memory_idx"))
            row["before_chars"] = int(accepted_match.group("before_chars"))
            row["after_chars"] = int(accepted_match.group("after_chars"))
            row["attempt_num"] = int(accepted_match.group("attempt"))
            row["max_attempt_num"] = int(accepted_match.group("max_attempt"))
        elif skipped_match := _SKIPPED_RE.search(body):
            row["event_type"] = "validator_skipped"
            row["memory_idx"] = int(skipped_match.group("memory_idx"))
            row["attempt_num"] = int(skipped_match.group("attempt"))
            row["max_attempt_num"] = int(skipped_match.group("max_attempt"))
            row["content_chars"] = int(skipped_match.group("chars"))
        elif retry_match := _RETRY_RE.search(body):
            row["event_type"] = "validator_retry"
            row["memory_idx"] = int(retry_match.group("memory_idx"))
            row["attempt_num"] = int(retry_match.group("attempt"))
            row["max_attempt_num"] = int(retry_match.group("max_attempt"))
            row["retry_reason"] = retry_match.group("reason")
        elif exhausted_match := _EXHAUSTED_RE.search(body):
            row["event_type"] = "validator_retry_exhausted"
            row["memory_idx"] = int(exhausted_match.group("memory_idx"))
            row["inner_retry_count"] = int(exhausted_match.group("inner_retries"))
            row["marked_retry_count"] = int(exhausted_match.group("marked_retry"))
            row["content_chars"] = int(exhausted_match.group("chars"))
        elif max_retry_match := _MAX_RETRY_KEEP_RE.search(body):
            row["event_type"] = "validator_max_retry_keep"
            row["memory_idx"] = int(max_retry_match.group("memory_idx"))
            row["max_attempt_num"] = int(max_retry_match.group("max_retry"))
            row["content_chars"] = int(max_retry_match.group("chars"))
        elif _L0_NO_MATCH_RE.search(body):
            row["event_type"] = "l0_no_match"

        events.append(row)
    return events


def _build_compactor_round_rows(events: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int, int], list[dict[str, object]]] = defaultdict(list)
    for event in events:
        key = (
            str(event["model"]),
            str(event["question_id"]),
            int(event["batch"]),
            int(event["after_iteration"]),
        )
        grouped[key].append(event)

    rows: list[dict[str, object]] = []
    for (_model, _question_id, _batch, after_iteration), items in sorted(grouped.items(), key=lambda item: item[0]):
        sample = items[0]
        context_chars = next((event["context_chars"] for event in items if event.get("context_chars") is not None), None)
        context_turns = next((event["context_turns"] for event in items if event.get("context_turns") is not None), None)
        selected_counts = [int(event["selected_candidate_count"]) for event in items if event.get("selected_candidate_count") is not None]
        selected_ids = next((event["selected_candidates"] for event in items if event.get("selected_candidates")), None)
        running_counts = [int(event["parallel_task_count"]) for event in items if event["event_type"] == "running_tasks" and event.get("parallel_task_count") is not None]
        l0_running_counts = [int(event["parallel_task_count"]) for event in items if event["event_type"] == "l0_running_tasks" and event.get("parallel_task_count") is not None]
        retry_attempts = [int(event["attempt_num"]) for event in items if event.get("attempt_num") is not None]
        rendered_sizes = [int(event["content_chars"]) for event in items if event["event_type"] in {"hardcoded_compactor", "generic_renderer"} and event.get("content_chars") is not None]
        selected_rounds = sum(1 for event in items if event["event_type"] == "selected_candidates")
        none_rounds = sum(1 for event in items if event["event_type"] == "chose_none")
        if selected_rounds:
            decision = "selected"
            round_type = "selection"
        elif none_rounds:
            decision = "none"
            round_type = "selection"
        elif any(event["event_type"] in {"l0_running_tasks", "l0_no_match"} for event in items):
            decision = "l0_hint"
            round_type = "l0_hint"
        else:
            decision = "other"
            round_type = "other"
        rows.append(
            {
                "model": sample["model"],
                "question_id": sample["question_id"],
                "section": sample["section"],
                "section_title": sample["section_title"],
                "eval_mode": sample["eval_mode"],
                "batch": sample["batch"],
                "history_path": sample["history_path"],
                "after_iteration": after_iteration,
                "round_type": round_type,
                "decision": decision,
                "selection_round": int(round_type == "selection"),
                "event_count": len(items),
                "context_chars": context_chars,
                "context_turns": context_turns,
                "selected_candidates": selected_ids,
                "selected_candidate_count": sum(selected_counts) if selected_counts else None,
                "parallel_task_count": sum(running_counts) if running_counts else None,
                "l0_parallel_task_count": sum(l0_running_counts) if l0_running_counts else None,
                "hardcoded_event_count": sum(1 for event in items if event["event_type"] == "hardcoded_compactor"),
                "generic_renderer_event_count": sum(1 for event in items if event["event_type"] == "generic_renderer"),
                "rendered_content_chars_total": sum(rendered_sizes) if rendered_sizes else None,
                "retry_event_count": sum(1 for event in items if event["event_type"] == "validator_retry"),
                "accepted_event_count": sum(1 for event in items if event["event_type"] == "validator_accepted"),
                "skipped_event_count": sum(1 for event in items if event["event_type"] == "validator_skipped"),
                "l0_no_match_event_count": sum(1 for event in items if event["event_type"] == "l0_no_match"),
                "retry_exhausted_event_count": sum(1 for event in items if event["event_type"] == "validator_retry_exhausted"),
                "max_retry_keep_event_count": sum(1 for event in items if event["event_type"] == "validator_max_retry_keep"),
                "summary_subagent_event_count": sum(1 for event in items if event["event_type"] == "summary_subagent_produced"),
                "summary_failed_event_count": sum(1 for event in items if event["event_type"] == "summary_subagent_failed"),
                "retry_attempt_mean": _mean(retry_attempts),
                "retry_attempt_p95": _percentile(retry_attempts, 0.95),
                "retry_attempt_max": max(retry_attempts) if retry_attempts else None,
            }
        )
    return rows


def _compactor_trigger_summary_rows(
    round_rows: list[dict[str, object]],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    normal_run_keys = {
        _run_key(run.model, run.question_id, run.batch)
        for run in runs
        if not run.had_error
    }
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0, "sample": run})
        stats["n_runs"] += 1

    grouped: dict[tuple, dict[str, object]] = {}
    for row in round_rows:
        key = tuple(row[field] for field in group_fields)
        stats = grouped.setdefault(
            key,
            {
                "triggered_rounds": 0,
                "normal_run_triggered_rounds": 0,
                "none_rounds": 0,
                "l0_no_match_rounds": 0,
                "selection_rounds": 0,
                "runs_with_triggered": set(),
                "runs_with_triggered_success": set(),
            },
        )
        run_key = _run_key(str(row["model"]), str(row["question_id"]), int(row["batch"]))
        if row.get("decision") == "selected":
            stats["triggered_rounds"] += 1
            stats["runs_with_triggered"].add(run_key)
            if run_key in normal_run_keys:
                stats["normal_run_triggered_rounds"] += 1
                stats["runs_with_triggered_success"].add(run_key)
        if row.get("decision") == "none":
            stats["none_rounds"] += 1
        if row.get("selection_round"):
            stats["selection_rounds"] += 1
        if int(row.get("l0_no_match_event_count") or 0) > 0:
            stats["l0_no_match_rounds"] += 1

    rows: list[dict[str, object]] = []
    for key, total in sorted(run_totals.items(), key=lambda item: item[0]):
        sample = total["sample"]
        stats = grouped.get(
            key,
            {
                "triggered_rounds": 0,
                "normal_run_triggered_rounds": 0,
                "none_rounds": 0,
                "l0_no_match_rounds": 0,
                "selection_rounds": 0,
                "runs_with_triggered": set(),
                "runs_with_triggered_success": set(),
            },
        )
        n_runs = int(total["n_runs"])
        row: dict[str, object] = {field: value for field, value in zip(group_fields, key)}
        row.update(
            {
                "n_runs": n_runs,
                "triggered_rounds": stats["triggered_rounds"],
                "normal_run_triggered_rounds": stats["normal_run_triggered_rounds"],
                "none_rounds": stats["none_rounds"],
                "l0_no_match_rounds": stats["l0_no_match_rounds"],
                "selection_rounds": stats["selection_rounds"],
                "runs_with_triggered_compaction": len(stats["runs_with_triggered"]),
                "run_trigger_rate": (len(stats["runs_with_triggered"]) / n_runs) if n_runs else None,
                "runs_with_triggered_success": len(stats["runs_with_triggered_success"]),
                "triggered_success_run_rate": (len(stats["runs_with_triggered_success"]) / n_runs) if n_runs else None,
                "mean_triggered_rounds_per_run": (stats["triggered_rounds"] / n_runs) if n_runs else None,
                "mean_none_rounds_per_run": (stats["none_rounds"] / n_runs) if n_runs else None,
                "mean_l0_no_match_rounds_per_run": (stats["l0_no_match_rounds"] / n_runs) if n_runs else None,
                "triggered_share_of_selection_rounds": (stats["triggered_rounds"] / stats["selection_rounds"]) if stats["selection_rounds"] else None,
            }
        )
        rows.append(row)
    return rows


def _load_compactor_rows(runs: list[RunRecord]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    event_rows: list[dict[str, object]] = []
    for run in runs:
        event_rows.extend(_parse_compactor_events_for_run(run))
    return event_rows, _build_compactor_round_rows(event_rows)


def _exclude_selected_round_from_followup_context(row: dict[str, object]) -> bool:
    return any(
        int(row.get(field) or 0) > 0
        for field in ("skipped_event_count", "retry_exhausted_event_count", "max_retry_keep_event_count")
    )


def _selected_round_followup_context(
    round_rows: list[dict[str, object]],
) -> dict[tuple[str, str, int, int], dict[str, float | None]]:
    grouped: dict[tuple[str, str, int], list[dict[str, object]]] = defaultdict(list)
    for row in round_rows:
        grouped[(str(row["model"]), str(row["question_id"]), int(row["batch"]))].append(row)

    followups: dict[tuple[str, str, int, int], dict[str, float | None]] = {}
    for key, items in grouped.items():
        ordered = sorted(items, key=lambda item: int(item["after_iteration"]))
        for index, row in enumerate(ordered):
            if row.get("decision") != "selected":
                continue
            if _exclude_selected_round_from_followup_context(row):
                continue
            next_row = next(
                (
                    candidate
                    for candidate in ordered[index + 1 :]
                    if candidate.get("context_chars") is not None or candidate.get("context_turns") is not None
                ),
                None,
            )
            if next_row is None:
                continue
            followups[(key[0], key[1], key[2], int(row["after_iteration"]))] = {
                "selected_context_chars": float(row["context_chars"]) if row.get("context_chars") is not None else None,
                "selected_context_turns": float(row["context_turns"]) if row.get("context_turns") is not None else None,
                "next_context_chars": float(next_row["context_chars"]) if next_row.get("context_chars") is not None else None,
                "next_context_turns": float(next_row["context_turns"]) if next_row.get("context_turns") is not None else None,
            }
    return followups


def _compactor_round_summary_rows(
    round_rows: list[dict[str, object]],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    followup_context = _selected_round_followup_context(round_rows)
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0, "sample": run})
        stats["n_runs"] += 1

    grouped: dict[tuple, dict[str, object]] = {}
    for row in round_rows:
        key = tuple(row[field] for field in group_fields)
        stats = grouped.setdefault(
            key,
            {
                "runs": set(),
                "rounds_total": 0,
                "selection_rounds": 0,
                "selected_rounds": 0,
                "none_rounds": 0,
                "context_chars": [],
                "context_turns": [],
                "selected_rounds_eligible_for_next_context": 0,
                "selected_context_chars": [],
                "selected_context_turns": [],
                "next_context_chars": [],
                "next_context_turns": [],
                "selected_candidates": [],
                "parallel_tasks": [],
                "retry_events_total": 0,
                "accepted_events_total": 0,
                "skipped_events_total": 0,
                "retry_exhausted_events_total": 0,
                "max_retry_keep_events_total": 0,
                "summary_subagent_events_total": 0,
                "summary_failed_events_total": 0,
                "retry_attempts": [],
                "hardcoded_events_total": 0,
                "generic_renderer_events_total": 0,
            },
        )
        stats["runs"].add(_run_key(str(row["model"]), str(row["question_id"]), int(row["batch"])))
        stats["rounds_total"] += 1
        stats["selection_rounds"] += int(row.get("selection_round") or 0)
        stats["selected_rounds"] += int(row.get("decision") == "selected")
        stats["none_rounds"] += int(row.get("decision") == "none")
        if row.get("decision") == "selected" and not _exclude_selected_round_from_followup_context(row):
            stats["selected_rounds_eligible_for_next_context"] += 1
        if row.get("context_chars") is not None:
            stats["context_chars"].append(float(row["context_chars"]))
        if row.get("context_turns") is not None:
            stats["context_turns"].append(float(row["context_turns"]))
        followup = followup_context.get((str(row["model"]), str(row["question_id"]), int(row["batch"]), int(row["after_iteration"])))
        if followup is not None:
            if followup.get("selected_context_chars") is not None:
                stats["selected_context_chars"].append(float(followup["selected_context_chars"]))
            if followup.get("selected_context_turns") is not None:
                stats["selected_context_turns"].append(float(followup["selected_context_turns"]))
            if followup.get("next_context_chars") is not None:
                stats["next_context_chars"].append(float(followup["next_context_chars"]))
            if followup.get("next_context_turns") is not None:
                stats["next_context_turns"].append(float(followup["next_context_turns"]))
        if row.get("selected_candidate_count") is not None:
            stats["selected_candidates"].append(float(row["selected_candidate_count"]))
        if row.get("parallel_task_count") is not None:
            stats["parallel_tasks"].append(float(row["parallel_task_count"]))
        stats["retry_events_total"] += int(row.get("retry_event_count") or 0)
        stats["accepted_events_total"] += int(row.get("accepted_event_count") or 0)
        stats["skipped_events_total"] += int(row.get("skipped_event_count") or 0)
        stats["retry_exhausted_events_total"] += int(row.get("retry_exhausted_event_count") or 0)
        stats["max_retry_keep_events_total"] += int(row.get("max_retry_keep_event_count") or 0)
        stats["summary_subagent_events_total"] += int(row.get("summary_subagent_event_count") or 0)
        stats["summary_failed_events_total"] += int(row.get("summary_failed_event_count") or 0)
        stats["hardcoded_events_total"] += int(row.get("hardcoded_event_count") or 0)
        stats["generic_renderer_events_total"] += int(row.get("generic_renderer_event_count") or 0)
        if row.get("retry_attempt_mean") is not None:
            stats["retry_attempts"].append(float(row["retry_attempt_mean"]))

    rows: list[dict[str, object]] = []
    for key, total in sorted(run_totals.items(), key=lambda item: item[0]):
        sample = total["sample"]
        stats = grouped.get(
            key,
            {
                "runs": set(),
                "rounds_total": 0,
                "selection_rounds": 0,
                "selected_rounds": 0,
                "none_rounds": 0,
                "context_chars": [],
                "context_turns": [],
                "selected_rounds_eligible_for_next_context": 0,
                "selected_context_chars": [],
                "selected_context_turns": [],
                "next_context_chars": [],
                "next_context_turns": [],
                "selected_candidates": [],
                "parallel_tasks": [],
                "retry_events_total": 0,
                "accepted_events_total": 0,
                "skipped_events_total": 0,
                "retry_exhausted_events_total": 0,
                "max_retry_keep_events_total": 0,
                "summary_subagent_events_total": 0,
                "summary_failed_events_total": 0,
                "retry_attempts": [],
                "hardcoded_events_total": 0,
                "generic_renderer_events_total": 0,
            },
        )
        n_runs = int(total["n_runs"])
        row: dict[str, object] = {field: value for field, value in zip(group_fields, key)}
        if "question_id" in group_fields:
            row["section"] = sample.section
            row["section_title"] = sample.section_title
            row["eval_mode"] = sample.eval_mode
            row["prompt_text"] = sample.prompt_text
        row.update(
            {
                "n_runs": n_runs,
                "runs_with_compactor_events": len(stats["runs"]),
                "run_presence_rate": (len(stats["runs"]) / n_runs) if n_runs else None,
                "rounds_total": stats["rounds_total"],
                "mean_rounds_per_run": (stats["rounds_total"] / n_runs) if n_runs else None,
                "selection_rounds": stats["selection_rounds"],
                "mean_selection_rounds_per_run": (stats["selection_rounds"] / n_runs) if n_runs else None,
                "selected_rounds": stats["selected_rounds"],
                "none_rounds": stats["none_rounds"],
                "selected_round_rate": (stats["selected_rounds"] / stats["selection_rounds"]) if stats["selection_rounds"] else None,
                "none_round_rate": (stats["none_rounds"] / stats["selection_rounds"]) if stats["selection_rounds"] else None,
                "context_observed_rounds": len(stats["context_chars"]),
                "context_chars_mean": _mean(stats["context_chars"]),
                "context_chars_p50": _percentile(stats["context_chars"], 0.50),
                "context_chars_p95": _percentile(stats["context_chars"], 0.95),
                "context_chars_max": max(stats["context_chars"]) if stats["context_chars"] else None,
                "context_turns_mean": _mean(stats["context_turns"]),
                "context_turns_p50": _percentile(stats["context_turns"], 0.50),
                "context_turns_p95": _percentile(stats["context_turns"], 0.95),
                "context_turns_max": max(stats["context_turns"]) if stats["context_turns"] else None,
                "selected_rounds_eligible_for_next_context": stats["selected_rounds_eligible_for_next_context"],
                "selected_rounds_with_next_context": len(stats["next_context_chars"]),
                "selected_next_context_coverage_rate": (
                    len(stats["next_context_chars"]) / stats["selected_rounds_eligible_for_next_context"]
                ) if stats["selected_rounds_eligible_for_next_context"] else None,
                "selected_context_chars_mean": _mean(stats["selected_context_chars"]),
                "selected_next_context_chars_mean": _mean(stats["next_context_chars"]),
                "selected_context_turns_mean": _mean(stats["selected_context_turns"]),
                "selected_next_context_turns_mean": _mean(stats["next_context_turns"]),
                "selected_candidate_total": sum(stats["selected_candidates"]) if stats["selected_candidates"] else 0,
                "selected_candidate_mean": _mean(stats["selected_candidates"]),
                "selected_candidate_p95": _percentile(stats["selected_candidates"], 0.95),
                "parallel_task_total": sum(stats["parallel_tasks"]) if stats["parallel_tasks"] else 0,
                "parallel_task_mean": _mean(stats["parallel_tasks"]),
                "parallel_task_p95": _percentile(stats["parallel_tasks"], 0.95),
                "retry_events_total": stats["retry_events_total"],
                "accepted_events_total": stats["accepted_events_total"],
                "skipped_events_total": stats["skipped_events_total"],
                "retry_exhausted_events_total": stats["retry_exhausted_events_total"],
                "max_retry_keep_events_total": stats["max_retry_keep_events_total"],
                "summary_subagent_events_total": stats["summary_subagent_events_total"],
                "summary_failed_events_total": stats["summary_failed_events_total"],
                "retry_attempt_mean": _mean(stats["retry_attempts"]),
                "retry_attempt_p95": _percentile(stats["retry_attempts"], 0.95),
                "retry_attempt_max": max(stats["retry_attempts"]) if stats["retry_attempts"] else None,
                "hardcoded_events_total": stats["hardcoded_events_total"],
                "generic_renderer_events_total": stats["generic_renderer_events_total"],
            }
        )
        rows.append(row)
    return rows


def _compactor_event_type_rows(
    event_rows: list[dict[str, object]],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0})
        stats["n_runs"] += 1

    grouped: dict[tuple, dict[str, object]] = {}
    for row in event_rows:
        group_key = tuple(row[field] for field in group_fields)
        key = group_key + (row["event_type"],)
        stats = grouped.setdefault(
            key,
            {
                "n_events": 0,
                "runs": set(),
                "prompts": set(),
                "tools": set(),
                "content_chars": [],
                "context_chars": [],
                "context_turns": [],
                "selected_counts": [],
                "parallel_tasks": [],
                "attempts": [],
                "sample": row,
            },
        )
        stats["n_events"] += 1
        stats["runs"].add(_run_key(str(row["model"]), str(row["question_id"]), int(row["batch"])))
        stats["prompts"].add(row["question_id"])
        if row.get("target_tool_name"):
            stats["tools"].add(row["target_tool_name"])
        if row.get("content_chars") is not None:
            stats["content_chars"].append(float(row["content_chars"]))
        if row.get("context_chars") is not None:
            stats["context_chars"].append(float(row["context_chars"]))
        if row.get("context_turns") is not None:
            stats["context_turns"].append(float(row["context_turns"]))
        if row.get("selected_candidate_count") is not None:
            stats["selected_counts"].append(float(row["selected_candidate_count"]))
        if row.get("parallel_task_count") is not None:
            stats["parallel_tasks"].append(float(row["parallel_task_count"]))
        if row.get("attempt_num") is not None:
            stats["attempts"].append(float(row["attempt_num"]))

    rows: list[dict[str, object]] = []
    for key, stats in sorted(grouped.items(), key=lambda item: (-item[1]["n_events"], item[0])):
        group_key = key[:-1]
        event_type = key[-1]
        n_runs = int(run_totals.get(group_key, {"n_runs": 0})["n_runs"])
        row: dict[str, object] = {field: value for field, value in zip(group_fields, group_key)}
        row.update(
            {
                "event_type": event_type,
                "n_runs": n_runs,
                "runs_with_event": len(stats["runs"]),
                "run_presence_rate": (len(stats["runs"]) / n_runs) if n_runs else None,
                "n_events": stats["n_events"],
                "mean_events_per_run": (stats["n_events"] / n_runs) if n_runs else None,
                "n_prompts": len(stats["prompts"]),
                "n_tools": len(stats["tools"]),
                "content_chars_mean": _mean(stats["content_chars"]),
                "context_chars_mean": _mean(stats["context_chars"]),
                "context_turns_mean": _mean(stats["context_turns"]),
                "selected_candidate_mean": _mean(stats["selected_counts"]),
                "parallel_task_mean": _mean(stats["parallel_tasks"]),
                "attempt_mean": _mean(stats["attempts"]),
                "example_message": stats["sample"]["message"],
            }
        )
        rows.append(row)
    return rows


def emit_compactor_stats(runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    event_rows, round_rows = _load_compactor_rows(runs)
    written: dict[str, Path] = {}

    event_fieldnames = [
        "model", "question_id", "section", "section_title", "eval_mode", "batch", "history_path",
        "event_index", "after_iteration", "level", "channel", "event_type", "message", "detail_message",
        "target_tool_name", "content_chars", "context_chars", "context_turns", "selected_candidates",
        "selected_candidate_count", "parallel_task_count", "attempt_num", "max_attempt_num", "memory_idx",
        "before_chars", "after_chars", "summary_chars", "summary_budget_chars", "summary_budget_tokens",
        "inner_retry_count", "marked_retry_count", "retry_reason",
    ]
    round_fieldnames = [
        "model", "question_id", "section", "section_title", "eval_mode", "batch", "history_path",
        "after_iteration", "round_type", "decision", "selection_round", "event_count", "context_chars",
        "context_turns", "selected_candidates", "selected_candidate_count", "parallel_task_count",
        "l0_parallel_task_count", "hardcoded_event_count", "generic_renderer_event_count",
        "rendered_content_chars_total", "retry_event_count", "accepted_event_count", "skipped_event_count",
        "l0_no_match_event_count",
        "retry_exhausted_event_count", "max_retry_keep_event_count", "summary_subagent_event_count",
        "summary_failed_event_count", "retry_attempt_mean", "retry_attempt_p95", "retry_attempt_max",
    ]
    written["events_long"] = _write_rows("compactor_events_long", event_rows, event_fieldnames, out_dir, json_dir)
    written["rounds_long"] = _write_rows("compactor_rounds_long", round_rows, round_fieldnames, out_dir, json_dir)

    round_specs = {
        "overall": tuple(),
        "model": ("model",),
        "prompt": ("question_id",),
        "model_prompt": ("model", "question_id"),
    }
    round_summary_fieldnames = {
        "overall": [
            "n_runs", "runs_with_compactor_events", "run_presence_rate", "rounds_total", "mean_rounds_per_run",
            "selection_rounds", "mean_selection_rounds_per_run", "selected_rounds", "none_rounds",
            "selected_round_rate", "none_round_rate", "context_observed_rounds", "context_chars_mean",
            "context_chars_p50", "context_chars_p95", "context_chars_max", "context_turns_mean",
            "context_turns_p50", "context_turns_p95", "context_turns_max", "selected_candidate_total",
            "selected_rounds_eligible_for_next_context", "selected_rounds_with_next_context", "selected_next_context_coverage_rate", "selected_context_chars_mean",
            "selected_next_context_chars_mean", "selected_context_turns_mean", "selected_next_context_turns_mean",
            "selected_candidate_mean", "selected_candidate_p95", "parallel_task_total", "parallel_task_mean",
            "parallel_task_p95", "retry_events_total", "accepted_events_total", "skipped_events_total",
            "retry_exhausted_events_total", "max_retry_keep_events_total", "summary_subagent_events_total",
            "summary_failed_events_total", "retry_attempt_mean", "retry_attempt_p95", "retry_attempt_max",
            "hardcoded_events_total", "generic_renderer_events_total",
        ],
        "model": [
            "model", "n_runs", "runs_with_compactor_events", "run_presence_rate", "rounds_total", "mean_rounds_per_run",
            "selection_rounds", "mean_selection_rounds_per_run", "selected_rounds", "none_rounds",
            "selected_round_rate", "none_round_rate", "context_observed_rounds", "context_chars_mean",
            "context_chars_p50", "context_chars_p95", "context_chars_max", "context_turns_mean",
            "context_turns_p50", "context_turns_p95", "context_turns_max", "selected_candidate_total",
            "selected_rounds_eligible_for_next_context", "selected_rounds_with_next_context", "selected_next_context_coverage_rate", "selected_context_chars_mean",
            "selected_next_context_chars_mean", "selected_context_turns_mean", "selected_next_context_turns_mean",
            "selected_candidate_mean", "selected_candidate_p95", "parallel_task_total", "parallel_task_mean",
            "parallel_task_p95", "retry_events_total", "accepted_events_total", "skipped_events_total",
            "retry_exhausted_events_total", "max_retry_keep_events_total", "summary_subagent_events_total",
            "summary_failed_events_total", "retry_attempt_mean", "retry_attempt_p95", "retry_attempt_max",
            "hardcoded_events_total", "generic_renderer_events_total",
        ],
        "prompt": [
            "question_id", "section", "section_title", "eval_mode", "prompt_text", "n_runs",
            "runs_with_compactor_events", "run_presence_rate", "rounds_total", "mean_rounds_per_run",
            "selection_rounds", "mean_selection_rounds_per_run", "selected_rounds", "none_rounds",
            "selected_round_rate", "none_round_rate", "context_observed_rounds", "context_chars_mean",
            "context_chars_p50", "context_chars_p95", "context_chars_max", "context_turns_mean",
            "context_turns_p50", "context_turns_p95", "context_turns_max", "selected_candidate_total",
            "selected_rounds_eligible_for_next_context", "selected_rounds_with_next_context", "selected_next_context_coverage_rate", "selected_context_chars_mean",
            "selected_next_context_chars_mean", "selected_context_turns_mean", "selected_next_context_turns_mean",
            "selected_candidate_mean", "selected_candidate_p95", "parallel_task_total", "parallel_task_mean",
            "parallel_task_p95", "retry_events_total", "accepted_events_total", "skipped_events_total",
            "retry_exhausted_events_total", "max_retry_keep_events_total", "summary_subagent_events_total",
            "summary_failed_events_total", "retry_attempt_mean", "retry_attempt_p95", "retry_attempt_max",
            "hardcoded_events_total", "generic_renderer_events_total",
        ],
        "model_prompt": [
            "model", "question_id", "section", "section_title", "eval_mode", "prompt_text", "n_runs",
            "runs_with_compactor_events", "run_presence_rate", "rounds_total", "mean_rounds_per_run",
            "selection_rounds", "mean_selection_rounds_per_run", "selected_rounds", "none_rounds",
            "selected_round_rate", "none_round_rate", "context_observed_rounds", "context_chars_mean",
            "context_chars_p50", "context_chars_p95", "context_chars_max", "context_turns_mean",
            "context_turns_p50", "context_turns_p95", "context_turns_max", "selected_candidate_total",
            "selected_rounds_eligible_for_next_context", "selected_rounds_with_next_context", "selected_next_context_coverage_rate", "selected_context_chars_mean",
            "selected_next_context_chars_mean", "selected_context_turns_mean", "selected_next_context_turns_mean",
            "selected_candidate_mean", "selected_candidate_p95", "parallel_task_total", "parallel_task_mean",
            "parallel_task_p95", "retry_events_total", "accepted_events_total", "skipped_events_total",
            "retry_exhausted_events_total", "max_retry_keep_events_total", "summary_subagent_events_total",
            "summary_failed_events_total", "retry_attempt_mean", "retry_attempt_p95", "retry_attempt_max",
            "hardcoded_events_total", "generic_renderer_events_total",
        ],
    }
    for name, group_fields in round_specs.items():
        rows = _compactor_round_summary_rows(round_rows, runs, group_fields=group_fields)
        filename = f"compactor_rounds_{name}" if name == "overall" else f"compactor_rounds_by_{name}"
        written[f"rounds_{name}"] = _write_rows(filename, rows, round_summary_fieldnames[name], out_dir, json_dir)

    event_specs = {
        "overall": tuple(),
        "model": ("model",),
    }
    event_summary_fieldnames = {
        "overall": [
            "event_type", "n_runs", "runs_with_event", "run_presence_rate", "n_events", "mean_events_per_run",
            "n_prompts", "n_tools", "content_chars_mean", "context_chars_mean", "context_turns_mean",
            "selected_candidate_mean", "parallel_task_mean", "attempt_mean", "example_message",
        ],
        "model": [
            "model", "event_type", "n_runs", "runs_with_event", "run_presence_rate", "n_events", "mean_events_per_run",
            "n_prompts", "n_tools", "content_chars_mean", "context_chars_mean", "context_turns_mean",
            "selected_candidate_mean", "parallel_task_mean", "attempt_mean", "example_message",
        ],
    }
    for name, group_fields in event_specs.items():
        rows = _compactor_event_type_rows(event_rows, runs, group_fields=group_fields)
        filename = f"compactor_event_types_{name}" if name == "overall" else f"compactor_event_types_by_{name}"
        written[f"event_types_{name}"] = _write_rows(filename, rows, event_summary_fieldnames[name], out_dir, json_dir)

    trigger_specs = {
        "overall": tuple(),
        "model": ("model",),
    }
    trigger_fieldnames = {
        "overall": [
            "n_runs", "triggered_rounds", "normal_run_triggered_rounds", "none_rounds", "l0_no_match_rounds", "selection_rounds",
            "runs_with_triggered_compaction", "run_trigger_rate", "runs_with_triggered_success", "triggered_success_run_rate", "mean_triggered_rounds_per_run",
            "mean_none_rounds_per_run", "mean_l0_no_match_rounds_per_run", "triggered_share_of_selection_rounds",
        ],
        "model": [
            "model", "n_runs", "triggered_rounds", "normal_run_triggered_rounds", "none_rounds", "l0_no_match_rounds", "selection_rounds",
            "runs_with_triggered_compaction", "run_trigger_rate", "runs_with_triggered_success", "triggered_success_run_rate", "mean_triggered_rounds_per_run",
            "mean_none_rounds_per_run", "mean_l0_no_match_rounds_per_run", "triggered_share_of_selection_rounds",
        ],
    }
    for name, group_fields in trigger_specs.items():
        rows = _compactor_trigger_summary_rows(round_rows, runs, group_fields=group_fields)
        filename = f"compactor_trigger_summary_{name}" if name == "overall" else f"compactor_trigger_summary_by_{name}"
        written[f"trigger_summary_{name}"] = _write_rows(filename, rows, trigger_fieldnames[name], out_dir, json_dir)
    return written


__all__ = [
    "emit_compactor_stats",
    "emit_second_order_tool_chains",
    "emit_tool_argo_timing",
    "emit_tool_wall_timing",
    "emit_parallel_stats",
    "emit_run_timing",
    "emit_tool_failures",
    "emit_tool_usage",
    "emit_workflow_snippets",
]


def _tool_usage_rows(
    tool_calls: list[ToolCallRecord],
    runs: list[RunRecord],
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    run_totals: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(getattr(run, field) for field in group_fields)
        stats = run_totals.setdefault(key, {"n_runs": 0, "sample": run})
        stats["n_runs"] += 1

    total_calls_by_group: dict[tuple, int] = defaultdict(int)

    usage: dict[tuple, dict[str, object]] = {}
    for call in tool_calls:
        if not _include_usage_tool(call.tool_name):
            continue
        group_key = tuple(getattr(call, field) for field in group_fields)
        total_calls_by_group[group_key] += 1
        key = group_key + (call.tool_name,)
        stats = usage.setdefault(
            key,
            {
                "sample": call,
                "n_calls": 0,
                "successful_calls": 0,
                "error_calls": 0,
                "durations": [],
                "walls": [],
                "runs": set(),
            },
        )
        stats["n_calls"] += 1
        stats["error_calls"] += int(call.is_error)
        if not call.is_error:
            stats["successful_calls"] += 1
            stats["durations"].append(call.duration_sec)
            stats["walls"].append(call.wall_sec)
        stats["runs"].add(_run_key(call.model, call.question_id, call.batch))

    rows: list[dict[str, object]] = []
    for key, stats in sorted(usage.items(), key=lambda item: (-item[1]["n_calls"], item[0])):
        group_key = key[:-1]
        tool_name = key[-1]
        sample = stats["sample"]
        total = run_totals.get(group_key, {"n_runs": 0})
        n_runs = int(total["n_runs"])
        total_calls = total_calls_by_group.get(group_key, 0)
        row: dict[str, object] = {field: value for field, value in zip(group_fields, group_key)}
        if "question_id" in group_fields:
            row["section"] = sample.section
            row["section_title"] = sample.section_title
            row["eval_mode"] = sample.eval_mode
            row["prompt_text"] = sample.prompt_text
        row.update(
            {
                "tool_name": tool_name,
                "n_runs": n_runs,
                "runs_with_tool": len(stats["runs"]),
                "run_presence_rate": (len(stats["runs"]) / n_runs) if n_runs else None,
                "n_calls": stats["n_calls"],
                "call_share": (stats["n_calls"] / total_calls) if total_calls else None,
                "mean_calls_per_run": (stats["n_calls"] / n_runs) if n_runs else None,
                "successful_calls": stats["successful_calls"],
                "error_calls": stats["error_calls"],
                "error_rate": (stats["error_calls"] / stats["n_calls"]) if stats["n_calls"] else None,
                "duration_total_sec": sum(stats["durations"]) if stats["durations"] else None,
                "duration_mean_sec": _mean(stats["durations"]),
                "duration_p50_sec": _percentile(stats["durations"], 0.50),
                "duration_p95_sec": _percentile(stats["durations"], 0.95),
                "wall_total_sec": sum(stats["walls"]) if stats["walls"] else None,
                "wall_mean_sec": _mean(stats["walls"]),
                "wall_p50_sec": _percentile(stats["walls"], 0.50),
                "wall_p95_sec": _percentile(stats["walls"], 0.95),
            }
        )
        rows.append(row)
    return rows


def emit_tool_usage(tool_calls: list[ToolCallRecord], runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    specs = {
        "overall": tuple(),
        "model": ("model",),
        "prompt": ("question_id",),
        "eval_mode": ("eval_mode",),
        "model_prompt": ("model", "question_id"),
    }
    fieldnames = {
        "overall": [
            "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "call_share",
            "mean_calls_per_run", "successful_calls", "error_calls", "error_rate", "duration_total_sec", "duration_mean_sec",
            "duration_p50_sec", "duration_p95_sec", "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "model": [
            "model", "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "call_share",
            "mean_calls_per_run", "successful_calls", "error_calls", "error_rate", "duration_total_sec", "duration_mean_sec",
            "duration_p50_sec", "duration_p95_sec", "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "prompt": [
            "question_id", "section", "section_title", "eval_mode", "prompt_text", "tool_name", "n_runs",
            "runs_with_tool", "run_presence_rate", "n_calls", "call_share", "mean_calls_per_run", "successful_calls", "error_calls",
            "error_rate", "duration_total_sec", "duration_mean_sec", "duration_p50_sec", "duration_p95_sec",
            "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "eval_mode": [
            "eval_mode", "tool_name", "n_runs", "runs_with_tool", "run_presence_rate", "n_calls", "call_share",
            "mean_calls_per_run", "successful_calls", "error_calls", "error_rate", "duration_total_sec", "duration_mean_sec",
            "duration_p50_sec", "duration_p95_sec", "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
        "model_prompt": [
            "model", "question_id", "section", "section_title", "eval_mode", "prompt_text", "tool_name", "n_runs",
            "runs_with_tool", "run_presence_rate", "n_calls", "call_share", "mean_calls_per_run", "successful_calls", "error_calls",
            "error_rate", "duration_total_sec", "duration_mean_sec", "duration_p50_sec", "duration_p95_sec",
            "wall_total_sec", "wall_mean_sec", "wall_p50_sec", "wall_p95_sec",
        ],
    }
    written: dict[str, Path] = {}
    for name, group_fields in specs.items():
        rows = _tool_usage_rows(tool_calls, runs, group_fields=group_fields)
        filename = f"tool_usage_{name}" if name == "overall" else f"tool_usage_by_{name}"
        written[name] = _write_rows(filename, rows, fieldnames[name], out_dir, json_dir)
    return written


def _run_timing_rows(runs: list[RunRecord], *, group_fields: tuple[str, ...]) -> list[dict[str, object]]:
    grouped: dict[tuple, dict[str, object]] = {}
    for run in runs:
        key = tuple(_major_section(run.section) if field == "major_section" else getattr(run, field) for field in group_fields)
        stats = grouped.setdefault(
            key,
            {
                "sample": run,
                "runs": [],
                "planning": [],
                "execution": [],
                "verdict": [],
                "total": [],
                "tool_calls": [],
                "parsed_tool_calls": [],
                "answer_words": [],
                "error_runs": 0,
                "questions": set(),
            },
        )
        stats["runs"].append(run)
        stats["questions"].add(run.question_id)
        if run.planning_time_sec is not None:
            stats["planning"].append(run.planning_time_sec)
        if run.execution_time_sec is not None:
            stats["execution"].append(run.execution_time_sec)
        if run.verdict_time_sec is not None:
            stats["verdict"].append(run.verdict_time_sec)
        if run.total_time_sec is not None:
            stats["total"].append(run.total_time_sec)
        if run.total_tool_calls is not None:
            stats["tool_calls"].append(float(run.total_tool_calls))
        stats["parsed_tool_calls"].append(float(run.parsed_tool_calls))
        stats["answer_words"].append(float(run.answer_word_count))
        stats["error_runs"] += int(run.had_error)

    rows: list[dict[str, object]] = []
    for key, stats in sorted(grouped.items(), key=lambda item: item[0]):
        sample = stats["sample"]
        row: dict[str, object] = {field: value for field, value in zip(group_fields, key)}
        if "question_id" in group_fields:
            row["section"] = sample.section
            row["section_title"] = sample.section_title
            row["eval_mode"] = sample.eval_mode
            row["prompt_text"] = sample.prompt_text
        elif "section" in group_fields:
            row["section_title"] = sample.section_title
            row["n_questions"] = len(stats["questions"])
        elif "major_section" in group_fields:
            row["n_questions"] = len(stats["questions"])
        n_runs = len(stats["runs"])
        row.update(
            {
                "n_runs": n_runs,
                "error_run_rate": (stats["error_runs"] / n_runs) if n_runs else None,
                "mean_total_tool_calls": _mean(stats["tool_calls"]),
                "mean_parsed_tool_calls": _mean(stats["parsed_tool_calls"]),
                "planning_mean_sec": _mean(stats["planning"]),
                "execution_mean_sec": _mean(stats["execution"]),
                "verdict_mean_sec": _mean(stats["verdict"]),
                "total_mean_sec": _mean(stats["total"]),
                "total_p50_sec": _percentile(stats["total"], 0.50),
                "total_p95_sec": _percentile(stats["total"], 0.95),
                "answer_word_mean": _mean(stats["answer_words"]),
            }
        )
        rows.append(row)
    return rows


def emit_run_timing(runs: list[RunRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    specs = {
        "overall": tuple(),
        "model": ("model",),
        "section": ("section",),
        "major_section": ("major_section",),
        "prompt": ("question_id",),
        "eval_mode": ("eval_mode",),
        "model_section": ("model", "section"),
        "model_major_section": ("model", "major_section"),
        "model_prompt": ("model", "question_id"),
    }
    fieldnames = {
        "overall": [
            "n_runs", "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec",
            "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec",
            "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
        "model": [
            "model", "n_runs", "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls",
            "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec",
            "total_p95_sec", "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
        "section": [
            "section", "section_title", "n_questions", "n_runs", "error_run_rate", "mean_total_tool_calls",
            "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec",
            "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean", "warning_threshold_sec",
            "planning_reference_sec",
        ],
        "major_section": [
            "major_section", "n_questions", "n_runs", "error_run_rate", "mean_total_tool_calls",
            "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec",
            "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean", "warning_threshold_sec",
            "planning_reference_sec",
        ],
        "prompt": [
            "question_id", "section", "section_title", "eval_mode", "prompt_text", "n_runs", "error_run_rate",
            "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec",
            "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean",
            "warning_threshold_sec", "planning_reference_sec",
        ],
        "eval_mode": [
            "eval_mode", "n_runs", "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls",
            "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec",
            "total_p95_sec", "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
        "model_section": [
            "model", "section", "section_title", "n_questions", "n_runs", "error_run_rate",
            "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec",
            "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean",
            "warning_threshold_sec", "planning_reference_sec",
        ],
        "model_major_section": [
            "model", "major_section", "n_questions", "n_runs", "error_run_rate", "mean_total_tool_calls",
            "mean_parsed_tool_calls", "planning_mean_sec", "execution_mean_sec", "verdict_mean_sec",
            "total_mean_sec", "total_p50_sec", "total_p95_sec", "answer_word_mean", "warning_threshold_sec",
            "planning_reference_sec",
        ],
        "model_prompt": [
            "model", "question_id", "section", "section_title", "eval_mode", "prompt_text", "n_runs",
            "error_run_rate", "mean_total_tool_calls", "mean_parsed_tool_calls", "planning_mean_sec",
            "execution_mean_sec", "verdict_mean_sec", "total_mean_sec", "total_p50_sec", "total_p95_sec",
            "answer_word_mean", "warning_threshold_sec", "planning_reference_sec",
        ],
    }
    written: dict[str, Path] = {}
    for name, group_fields in specs.items():
        rows = _annotate_run_timing_rows(_run_timing_rows(runs, group_fields=group_fields), runs)
        filename = f"run_timing_{name}" if name == "overall" else f"run_timing_by_{name}"
        written[name] = _write_rows(filename, rows, fieldnames[name], out_dir, json_dir)
    return written


def emit_tool_failures(tool_calls: list[ToolCallRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    detailed_rows = []
    grouped: dict[tuple[str, str | None, str | None], dict[str, object]] = {}
    for call in tool_calls:
        if not call.is_error:
            continue
        detailed_rows.append(
            {
                "model": call.model,
                "question_id": call.question_id,
                "section": call.section,
                "eval_mode": call.eval_mode,
                "batch": call.batch,
                "step_num": call.step_num,
                "tool_name": call.tool_name,
                "phase": call.phase,
                "error_category": call.error_category,
                "error_reason": call.error_reason,
                "error_message": call.error_message,
                "duration_sec": call.duration_sec,
                "parallel_group_signature": call.parallel_group_signature,
            }
        )
        key = (call.tool_name, call.error_category, call.error_reason)
        stats = grouped.setdefault(
            key,
            {
                "count": 0,
                "models": set(),
                "prompts": set(),
                "sample": call,
            },
        )
        stats["count"] += 1
        stats["models"].add(call.model)
        stats["prompts"].add(call.question_id)

    summary_rows = []
    for (tool_name, error_category, error_reason), stats in sorted(grouped.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        summary_rows.append(
            {
                "tool_name": tool_name,
                "error_category": error_category,
                "error_reason": error_reason,
                "n_failures": stats["count"],
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "example_model": sample.model,
                "example_question_id": sample.question_id,
                "example_message": sample.error_message,
            }
        )

    return {
        "detailed": _write_rows(
            "tool_failures_detailed",
            detailed_rows,
            [
                "model", "question_id", "section", "eval_mode", "batch", "step_num", "tool_name", "phase",
                "error_category", "error_reason", "error_message", "duration_sec", "parallel_group_signature",
            ],
            out_dir,
            json_dir,
        ),
        "summary": _write_rows(
            "tool_failures_by_reason",
            summary_rows,
            [
                "tool_name", "error_category", "error_reason", "n_failures", "n_models", "n_prompts",
                "example_model", "example_question_id", "example_message",
            ],
            out_dir,
            json_dir,
        ),
    }


def emit_parallel_stats(workflow_groups: list[WorkflowGroupRecord], out_dir: Path, json_dir: Path) -> dict[str, Path]:
    batches = [group for group in workflow_groups if group.group_size > 1]
    batch_summary: dict[tuple[str, int], dict[str, object]] = {}
    pair_summary: dict[tuple[str, str], dict[str, object]] = {}
    for group in batches:
        key = (group.group_signature, group.group_size)
        stats = batch_summary.setdefault(
            key,
            {
                "count": 0,
                "models": set(),
                "prompts": set(),
                "walls": [],
                "tool_sums": [],
                "error_batches": 0,
                "sample": group,
            },
        )
        stats["count"] += 1
        stats["models"].add(group.model)
        stats["prompts"].add(group.question_id)
        stats["walls"].append(group.wall_sec)
        stats["tool_sums"].append(group.tool_duration_sum_sec)
        stats["error_batches"] += int(group.has_error)

        names = group.tool_names.split(" || ")
        for left_index, right_index in combinations(range(len(names)), 2):
            pair = tuple(sorted((names[left_index], names[right_index])))
            pair_stats = pair_summary.setdefault(
                pair,
                {
                    "count": 0,
                    "models": set(),
                    "prompts": set(),
                    "walls": [],
                },
            )
            pair_stats["count"] += 1
            pair_stats["models"].add(group.model)
            pair_stats["prompts"].add(group.question_id)
            pair_stats["walls"].append(group.wall_sec)

    batch_rows = []
    for (signature, group_size), stats in sorted(batch_summary.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        batch_rows.append(
            {
                "group_signature": signature,
                "batch_size": group_size,
                "n_occurrences": stats["count"],
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "mean_wall_sec": _mean(stats["walls"]),
                "mean_tool_duration_sum_sec": _mean(stats["tool_sums"]),
                "error_batch_rate": (stats["error_batches"] / stats["count"]) if stats["count"] else None,
                "example_model": sample.model,
                "example_question_id": sample.question_id,
            }
        )

    pair_rows = []
    for (tool_a, tool_b), stats in sorted(pair_summary.items(), key=lambda item: (-item[1]["count"], item[0])):
        pair_rows.append(
            {
                "tool_a": tool_a,
                "tool_b": tool_b,
                "n_occurrences": stats["count"],
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "mean_wall_sec": _mean(stats["walls"]),
            }
        )

    return {
        "batches": _write_rows(
            "parallel_batch_patterns",
            batch_rows,
            [
                "group_signature", "batch_size", "n_occurrences", "n_models", "n_prompts", "mean_wall_sec",
                "mean_tool_duration_sum_sec", "error_batch_rate", "example_model", "example_question_id",
            ],
            out_dir,
            json_dir,
        ),
        "pairs": _write_rows(
            "parallel_tool_pairs",
            pair_rows,
            ["tool_a", "tool_b", "n_occurrences", "n_models", "n_prompts", "mean_wall_sec"],
            out_dir,
            json_dir,
        ),
    }


def emit_workflow_snippets(workflow_groups: list[WorkflowGroupRecord], out_dir: Path, json_dir: Path) -> Path:
    by_run: dict[tuple[str, str, int], list[WorkflowGroupRecord]] = defaultdict(list)
    for group in workflow_groups:
        by_run[_run_key(group.model, group.question_id, group.batch)].append(group)

    snippets: dict[tuple[int, str], dict[str, object]] = {}
    for run_key, groups in by_run.items():
        ordered = sorted(groups, key=lambda item: item.group_index)
        tokens = [group.group_token for group in ordered]
        model, question_id, _batch = run_key
        for size in (2, 3, 4):
            if len(tokens) < size:
                continue
            for index in range(len(tokens) - size + 1):
                snippet = " -> ".join(tokens[index:index + size])
                key = (size, snippet)
                stats = snippets.setdefault(
                    key,
                    {
                        "count": 0,
                        "runs": set(),
                        "models": set(),
                        "prompts": set(),
                        "sample": ordered[index],
                    },
                )
                stats["count"] += 1
                stats["runs"].add(run_key)
                stats["models"].add(model)
                stats["prompts"].add(question_id)

    rows = []
    for (snippet_len, snippet), stats in sorted(snippets.items(), key=lambda item: (-item[1]["count"], item[0])):
        sample = stats["sample"]
        rows.append(
            {
                "snippet_len": snippet_len,
                "snippet": snippet,
                "n_occurrences": stats["count"],
                "n_runs": len(stats["runs"]),
                "n_models": len(stats["models"]),
                "n_prompts": len(stats["prompts"]),
                "example_model": sample.model,
                "example_question_id": sample.question_id,
            }
        )
    return _write_rows(
        "workflow_snippets",
        rows,
        ["snippet_len", "snippet", "n_occurrences", "n_runs", "n_models", "n_prompts", "example_model", "example_question_id"],
        out_dir,
        json_dir,
    )


__all__ = [
    "emit_parallel_stats",
    "emit_run_timing",
    "emit_tool_failures",
    "emit_tool_usage",
    "emit_workflow_snippets",
]