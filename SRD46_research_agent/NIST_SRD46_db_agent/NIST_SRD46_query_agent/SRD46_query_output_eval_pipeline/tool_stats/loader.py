"""Load per-run and per-tool-call statistics from `_output/Model_*/Q*/` histories."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Iterable

from ..input_support_helpers.parse_history import parse_history
from ..input_support_helpers.parse_result import parse_result
from ..input_support_helpers.scan import DEFAULT_OUTPUT_ROOT, scan_outputs
from ..models import ToolCall
from ..posteval_stats.prompt_registry import load_prompt_registry

_PHASE_MAP: dict[str, tuple[int, str]] = {
    "0_preplan_decision": (0, "Triage"),
    "search_metals": (1, "Discovery"),
    "search_ligands": (1, "Discovery"),
    "build_system_catalog": (1, "Discovery"),
    "0_plan_search_strategy": (2, "Planning"),
}
_EXECUTION_PHASE = (3, "Execution")


def _classify_phase(tool_name: str) -> tuple[int, str]:
    return _PHASE_MAP.get(tool_name, _EXECUTION_PHASE)


def _run_key(model: str, question_id: str, batch: int) -> tuple[str, str, int]:
    return model, question_id, batch


def _group_calls(calls: list[ToolCall]) -> list[list[ToolCall]]:
    groups: list[list[ToolCall]] = []
    index = 0
    while index < len(calls):
        call = calls[index]
        if call.is_parallel:
            group = [call]
            next_index = index + 1
            while next_index < len(calls):
                sibling = calls[next_index]
                if not sibling.is_parallel or sibling.timestamp_sec != call.timestamp_sec:
                    break
                group.append(sibling)
                next_index += 1
            groups.append(group)
            index = next_index
            continue
        groups.append([call])
        index += 1
    return groups


def _normalize_error_message(message: str | None) -> str | None:
    if not message:
        return None
    return " ".join(message.split())


def _error_category(message: str | None) -> str | None:
    normalized = (_normalize_error_message(message) or "").lower()
    if not normalized:
        return None
    if "[phase error]" in normalized:
        if "not available yet" in normalized:
            return "phase_tool_unavailable"
        if "cannot call planner yet" in normalized:
            return "planner_gate"
        if "must first call" in normalized or "you must call" in normalized:
            return "phase_gate"
        return "phase_error"
    if "timeout" in normalized:
        return "timeout"
    if "json" in normalized:
        return "json_error"
    if "not found" in normalized or "no such" in normalized:
        return "not_found"
    return "other_error"


def _error_reason(message: str | None) -> str | None:
    normalized = _normalize_error_message(message)
    if not normalized:
        return None
    lowered = normalized.lower()
    if "[phase error]" in lowered and "not available yet" in lowered:
        return "tool unavailable before planning phase"
    if "[phase error]" in lowered and "cannot call planner yet" in lowered:
        return "planner called before required l0 tools"
    if "[phase error]" in lowered and ("must first call" in lowered or "you must call" in lowered):
        return "tool called before prerequisite phase"
    return normalized


def _argo_analysis_sec(call: ToolCall) -> float | None:
    if not call.model_timings:
        return None
    return sum(timing.elapsed_sec for timing in call.model_timings)


@dataclass(slots=True)
class ToolCallRecord:
    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    prompt_text: str
    batch: int
    step_num: int
    call_position: int
    tool_name: str
    phase_id: int
    phase: str
    duration_sec: float
    timestamp_sec: float
    wall_sec: float
    result_chars: int | None
    is_error: bool
    error_category: str | None
    error_reason: str | None
    error_message: str | None
    is_parallel: bool
    parallel_group_id: int
    parallel_group_size: int
    parallel_group_signature: str
    group_token: str
    iteration: int | None
    run_total_tool_calls: int | None
    run_planning_time_sec: float | None
    run_execution_time_sec: float | None
    run_verdict_time_sec: float | None
    run_total_time_sec: float | None
    answer_word_count: int | None
    verdict_bucket: str | None
    source_history_path: str
    argo_analysis_sec: float | None = None


@dataclass(slots=True)
class WorkflowGroupRecord:
    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    prompt_text: str
    batch: int
    group_index: int
    phase_id: int
    phase: str
    group_size: int
    tool_names: str
    group_signature: str
    group_token: str
    wall_sec: float
    tool_duration_sum_sec: float
    start_timestamp_sec: float
    end_timestamp_sec: float
    has_error: bool
    source_history_path: str


@dataclass(slots=True)
class RunRecord:
    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    prompt_text: str
    batch: int
    total_tool_calls: int | None
    parsed_tool_calls: int
    planning_time_sec: float | None
    execution_time_sec: float | None
    verdict_time_sec: float | None
    total_time_sec: float | None
    answer_word_count: int
    verdict_bucket: str | None
    had_error: bool
    error_call_count: int
    unique_tools: int
    unique_parallel_groups: int
    history_path: str
    result_path: str


@dataclass(slots=True)
class LoadIssue:
    model: str
    question_id: str
    batch: int
    issue_type: str
    reason: str
    source_path: str


@dataclass(slots=True)
class LoadResult:
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    workflow_groups: list[WorkflowGroupRecord] = field(default_factory=list)
    runs: list[RunRecord] = field(default_factory=list)
    issues: list[LoadIssue] = field(default_factory=list)


def iter_tool_records(
    root: str | Path | None = None,
    *,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    registry: dict | None = None,
) -> LoadResult:
    output_root = Path(root) if root else DEFAULT_OUTPUT_ROOT
    registry = registry if registry is not None else load_prompt_registry()
    model_set = set(include_models) if include_models else None
    question_set = set(include_questions) if include_questions else None
    section_set = set(include_sections) if include_sections else None

    result = LoadResult()
    for run in scan_outputs([output_root]):
        if model_set is not None and run.model not in model_set:
            continue
        if question_set is not None and run.question_id not in question_set:
            continue

        spec = registry.get(run.question_id)
        section = spec.section if spec else "?"
        section_title = spec.section_title if spec else ""
        eval_mode = spec.eval_mode if spec else "unknown"
        if section_set is not None and section not in section_set:
            continue

        if run.history_path is None:
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "missing_history", "history markdown not found", "")
            )
            continue
        if run.result_path is None:
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "missing_result", "result markdown not found", str(run.history_path))
            )
            continue

        try:
            calls = parse_history(run.history_path)
        except Exception as exc:  # noqa: BLE001
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "history_parse_error", str(exc), str(run.history_path))
            )
            continue

        try:
            parsed_result = parse_result(run.result_path)
        except Exception as exc:  # noqa: BLE001
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "result_parse_error", str(exc), str(run.result_path))
            )
            continue

        groups = _group_calls(calls)
        previous_end = 0.0
        for group_index, group in enumerate(groups, start=1):
            end_timestamp_sec = max(call.timestamp_sec for call in group)
            start_timestamp_sec = min(call.timestamp_sec - call.duration_sec for call in group)
            wall_sec = max(0.0, end_timestamp_sec - previous_end)
            previous_end = end_timestamp_sec
            tool_names = sorted(call.tool_name for call in group)
            signature = " || ".join(tool_names)
            group_token = f"[{signature}]" if len(group) > 1 else group[0].tool_name
            phase_id, phase = max((_classify_phase(call.tool_name) for call in group), key=lambda item: item[0])
            has_error = any(call.is_error for call in group)
            result.workflow_groups.append(
                WorkflowGroupRecord(
                    model=run.model,
                    question_id=run.question_id,
                    section=section,
                    section_title=section_title,
                    eval_mode=eval_mode,
                    prompt_text=parsed_result.prompt_text,
                    batch=run.batch,
                    group_index=group_index,
                    phase_id=phase_id,
                    phase=phase,
                    group_size=len(group),
                    tool_names=signature,
                    group_signature=signature,
                    group_token=group_token,
                    wall_sec=wall_sec,
                    tool_duration_sum_sec=sum(call.duration_sec for call in group),
                    start_timestamp_sec=start_timestamp_sec,
                    end_timestamp_sec=end_timestamp_sec,
                    has_error=has_error,
                    source_history_path=str(run.history_path),
                )
            )
            for call_position, call in enumerate(group, start=1):
                call_phase_id, call_phase = _classify_phase(call.tool_name)
                normalized_error = _normalize_error_message(call.error_message)
                result.tool_calls.append(
                    ToolCallRecord(
                        model=run.model,
                        question_id=run.question_id,
                        section=section,
                        section_title=section_title,
                        eval_mode=eval_mode,
                        prompt_text=parsed_result.prompt_text,
                        batch=run.batch,
                        step_num=call.step_num,
                        call_position=call_position,
                        tool_name=call.tool_name,
                        phase_id=call_phase_id,
                        phase=call_phase,
                        duration_sec=call.duration_sec,
                        timestamp_sec=call.timestamp_sec,
                        wall_sec=wall_sec,
                        result_chars=call.result_chars,
                        is_error=call.is_error,
                        error_category=_error_category(normalized_error),
                        error_reason=_error_reason(normalized_error),
                        error_message=normalized_error,
                        is_parallel=call.is_parallel,
                        parallel_group_id=group_index,
                        parallel_group_size=len(group),
                        parallel_group_signature=signature,
                        group_token=group_token,
                        iteration=call.iteration,
                        run_total_tool_calls=parsed_result.total_tool_calls,
                        run_planning_time_sec=parsed_result.planning_time_sec,
                        run_execution_time_sec=parsed_result.execution_time_sec,
                        run_verdict_time_sec=parsed_result.verdict_time_sec,
                        run_total_time_sec=parsed_result.total_time_sec,
                        answer_word_count=parsed_result.answer_word_count,
                        verdict_bucket=parsed_result.verdict_bucket,
                        source_history_path=str(run.history_path),
                        argo_analysis_sec=_argo_analysis_sec(call),
                    )
                )

        result.runs.append(
            RunRecord(
                model=run.model,
                question_id=run.question_id,
                section=section,
                section_title=section_title,
                eval_mode=eval_mode,
                prompt_text=parsed_result.prompt_text,
                batch=run.batch,
                total_tool_calls=parsed_result.total_tool_calls,
                parsed_tool_calls=len(calls),
                planning_time_sec=parsed_result.planning_time_sec,
                execution_time_sec=parsed_result.execution_time_sec,
                verdict_time_sec=parsed_result.verdict_time_sec,
                total_time_sec=parsed_result.total_time_sec,
                answer_word_count=parsed_result.answer_word_count,
                verdict_bucket=parsed_result.verdict_bucket,
                had_error=any(call.is_error for call in calls),
                error_call_count=sum(1 for call in calls if call.is_error),
                unique_tools=len({call.tool_name for call in calls}),
                unique_parallel_groups=sum(1 for group in groups if len(group) > 1),
                history_path=str(run.history_path),
                result_path=str(run.result_path),
            )
        )
    return result


def _write_dataclass_rows(items: list[object], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(items[0])] if items else []
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            for item in items:
                writer.writerow(asdict(item))
    return out


def write_tool_calls_csv(rows: list[ToolCallRecord], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


def write_workflow_groups_csv(rows: list[WorkflowGroupRecord], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


def write_runs_csv(rows: list[RunRecord], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


def write_issues_csv(rows: list[LoadIssue], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "LoadIssue",
    "LoadResult",
    "RunRecord",
    "ToolCallRecord",
    "WorkflowGroupRecord",
    "iter_tool_records",
    "write_issues_csv",
    "write_runs_csv",
    "write_tool_calls_csv",
    "write_workflow_groups_csv",
]


def _normalize_error_message(message: str | None) -> str | None:
    if not message:
        return None
    return " ".join(message.split())


def _error_category(message: str | None) -> str | None:
    normalized = (_normalize_error_message(message) or "").lower()
    if not normalized:
        return None
    if "[phase error]" in normalized:
        if "not available yet" in normalized:
            return "phase_tool_unavailable"
        if "cannot call planner yet" in normalized:
            return "planner_gate"
        if "must first call" in normalized or "you must call" in normalized:
            return "phase_gate"
        return "phase_error"
    if "timeout" in normalized:
        return "timeout"
    if "json" in normalized:
        return "json_error"
    if "not found" in normalized or "no such" in normalized:
        return "not_found"
    return "other_error"


def _error_reason(message: str | None) -> str | None:
    normalized = _normalize_error_message(message)
    if not normalized:
        return None
    lowered = normalized.lower()
    if "[phase error]" in lowered and "not available yet" in lowered:
        return "tool unavailable before planning phase"
    if "[phase error]" in lowered and "cannot call planner yet" in lowered:
        return "planner called before required l0 tools"
    if "[phase error]" in lowered and ("must first call" in lowered or "you must call" in lowered):
        return "tool called before prerequisite phase"
    return normalized


def _argo_analysis_sec(call: ToolCall) -> float | None:
    if not call.model_timings:
        return None
    return sum(timing.elapsed_sec for timing in call.model_timings)


@dataclass(slots=True)
class ToolCallRecord:
    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    prompt_text: str
    batch: int
    step_num: int
    call_position: int
    tool_name: str
    phase_id: int
    phase: str
    duration_sec: float
    timestamp_sec: float
    wall_sec: float
    result_chars: int | None
    is_error: bool
    error_category: str | None
    error_reason: str | None
    error_message: str | None
    is_parallel: bool
    parallel_group_id: int
    parallel_group_size: int
    parallel_group_signature: str
    group_token: str
    iteration: int | None
    run_total_tool_calls: int | None
    run_planning_time_sec: float | None
    run_execution_time_sec: float | None
    run_verdict_time_sec: float | None
    run_total_time_sec: float | None
    answer_word_count: int | None
    verdict_bucket: str | None
    source_history_path: str
    argo_analysis_sec: float | None = None


@dataclass(slots=True)
class WorkflowGroupRecord:
    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    prompt_text: str
    batch: int
    group_index: int
    phase_id: int
    phase: str
    group_size: int
    tool_names: str
    group_signature: str
    group_token: str
    wall_sec: float
    tool_duration_sum_sec: float
    start_timestamp_sec: float
    end_timestamp_sec: float
    has_error: bool
    source_history_path: str


@dataclass(slots=True)
class RunRecord:
    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    prompt_text: str
    batch: int
    total_tool_calls: int | None
    parsed_tool_calls: int
    planning_time_sec: float | None
    execution_time_sec: float | None
    verdict_time_sec: float | None
    total_time_sec: float | None
    answer_word_count: int
    verdict_bucket: str | None
    had_error: bool
    error_call_count: int
    unique_tools: int
    unique_parallel_groups: int
    history_path: str
    result_path: str


@dataclass(slots=True)
class LoadIssue:
    model: str
    question_id: str
    batch: int
    issue_type: str
    reason: str
    source_path: str


@dataclass(slots=True)
class LoadResult:
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    workflow_groups: list[WorkflowGroupRecord] = field(default_factory=list)
    runs: list[RunRecord] = field(default_factory=list)
    issues: list[LoadIssue] = field(default_factory=list)


def iter_tool_records(
    root: str | Path | None = None,
    *,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    registry: dict | None = None,
) -> LoadResult:
    output_root = Path(root) if root else DEFAULT_OUTPUT_ROOT
    registry = registry if registry is not None else load_prompt_registry()
    model_set = set(include_models) if include_models else None
    question_set = set(include_questions) if include_questions else None
    section_set = set(include_sections) if include_sections else None

    result = LoadResult()
    for run in scan_outputs([output_root]):
        if model_set is not None and run.model not in model_set:
            continue
        if question_set is not None and run.question_id not in question_set:
            continue

        spec = registry.get(run.question_id)
        section = spec.section if spec else "?"
        section_title = spec.section_title if spec else ""
        eval_mode = spec.eval_mode if spec else "unknown"
        if section_set is not None and section not in section_set:
            continue

        if run.history_path is None:
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "missing_history", "history markdown not found", "")
            )
            continue
        if run.result_path is None:
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "missing_result", "result markdown not found", str(run.history_path))
            )
            continue

        try:
            calls = parse_history(run.history_path)
        except Exception as exc:  # noqa: BLE001
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "history_parse_error", str(exc), str(run.history_path))
            )
            continue

        try:
            parsed_result = parse_result(run.result_path)
        except Exception as exc:  # noqa: BLE001
            result.issues.append(
                LoadIssue(run.model, run.question_id, run.batch, "result_parse_error", str(exc), str(run.result_path))
            )
            continue

        groups = _group_calls(calls)
        previous_end = 0.0
        for group_index, group in enumerate(groups, start=1):
            end_timestamp_sec = max(call.timestamp_sec for call in group)
            start_timestamp_sec = min(call.timestamp_sec - call.duration_sec for call in group)
            wall_sec = max(0.0, end_timestamp_sec - previous_end)
            previous_end = end_timestamp_sec
            tool_names = sorted(call.tool_name for call in group)
            signature = " || ".join(tool_names)
            group_token = f"[{signature}]" if len(group) > 1 else group[0].tool_name
            phase_id, phase = max((_classify_phase(call.tool_name) for call in group), key=lambda item: item[0])
            has_error = any(call.is_error for call in group)
            result.workflow_groups.append(
                WorkflowGroupRecord(
                    model=run.model,
                    question_id=run.question_id,
                    section=section,
                    section_title=section_title,
                    eval_mode=eval_mode,
                    prompt_text=parsed_result.prompt_text,
                    batch=run.batch,
                    group_index=group_index,
                    phase_id=phase_id,
                    phase=phase,
                    group_size=len(group),
                    tool_names=signature,
                    group_signature=signature,
                    group_token=group_token,
                    wall_sec=wall_sec,
                    tool_duration_sum_sec=sum(call.duration_sec for call in group),
                    start_timestamp_sec=start_timestamp_sec,
                    end_timestamp_sec=end_timestamp_sec,
                    has_error=has_error,
                    source_history_path=str(run.history_path),
                )
            )
            for call_position, call in enumerate(group, start=1):
                call_phase_id, call_phase = _classify_phase(call.tool_name)
                normalized_error = _normalize_error_message(call.error_message)
                result.tool_calls.append(
                    ToolCallRecord(
                        model=run.model,
                        question_id=run.question_id,
                        section=section,
                        section_title=section_title,
                        eval_mode=eval_mode,
                        prompt_text=parsed_result.prompt_text,
                        batch=run.batch,
                        step_num=call.step_num,
                        call_position=call_position,
                        tool_name=call.tool_name,
                        phase_id=call_phase_id,
                        phase=call_phase,
                        duration_sec=call.duration_sec,
                        timestamp_sec=call.timestamp_sec,
                        wall_sec=wall_sec,
                        result_chars=call.result_chars,
                        is_error=call.is_error,
                        error_category=_error_category(normalized_error),
                        error_reason=_error_reason(normalized_error),
                        error_message=normalized_error,
                        is_parallel=call.is_parallel,
                        parallel_group_id=group_index,
                        parallel_group_size=len(group),
                        parallel_group_signature=signature,
                        group_token=group_token,
                        iteration=call.iteration,
                        run_total_tool_calls=parsed_result.total_tool_calls,
                        run_planning_time_sec=parsed_result.planning_time_sec,
                        run_execution_time_sec=parsed_result.execution_time_sec,
                        run_verdict_time_sec=parsed_result.verdict_time_sec,
                        run_total_time_sec=parsed_result.total_time_sec,
                        answer_word_count=parsed_result.answer_word_count,
                        verdict_bucket=parsed_result.verdict_bucket,
                        source_history_path=str(run.history_path),
                        argo_analysis_sec=_argo_analysis_sec(call),
                    )
                )

        result.runs.append(
            RunRecord(
                model=run.model,
                question_id=run.question_id,
                section=section,
                section_title=section_title,
                eval_mode=eval_mode,
                prompt_text=parsed_result.prompt_text,
                batch=run.batch,
                total_tool_calls=parsed_result.total_tool_calls,
                parsed_tool_calls=len(calls),
                planning_time_sec=parsed_result.planning_time_sec,
                execution_time_sec=parsed_result.execution_time_sec,
                verdict_time_sec=parsed_result.verdict_time_sec,
                total_time_sec=parsed_result.total_time_sec,
                answer_word_count=parsed_result.answer_word_count,
                verdict_bucket=parsed_result.verdict_bucket,
                had_error=any(call.is_error for call in calls),
                error_call_count=sum(1 for call in calls if call.is_error),
                unique_tools=len({call.tool_name for call in calls}),
                unique_parallel_groups=sum(1 for group in groups if len(group) > 1),
                history_path=str(run.history_path),
                result_path=str(run.result_path),
            )
        )
    return result


def _write_dataclass_rows(items: list[object], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(items[0])] if items else []
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            for item in items:
                writer.writerow(asdict(item))
    return out


def write_tool_calls_csv(rows: list[ToolCallRecord], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


def write_workflow_groups_csv(rows: list[WorkflowGroupRecord], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


def write_runs_csv(rows: list[RunRecord], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


def write_issues_csv(rows: list[LoadIssue], path: str | Path) -> Path:
    return _write_dataclass_rows(rows, path)


__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "LoadIssue",
    "LoadResult",
    "RunRecord",
    "ToolCallRecord",
    "WorkflowGroupRecord",
    "iter_tool_records",
    "write_issues_csv",
    "write_runs_csv",
    "write_tool_calls_csv",
    "write_workflow_groups_csv",
]
