from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ModelTiming:
    model_name: str
    elapsed_sec: float
    revision: bool | None = None


@dataclass(slots=True)
class RunArtifacts:
    output_root: str
    model: str
    question_id: str
    batch: int
    history_path: Path | None = None
    ref_ids_path: Path | None = None
    result_path: Path | None = None
    summary_path: Path | None = None
    is_complete: bool = False

    @property
    def missing_artifacts(self) -> list[str]:
        missing: list[str] = []
        if self.history_path is None:
            missing.append("history")
        if self.ref_ids_path is None:
            missing.append("ref_ids")
        if self.result_path is None:
            missing.append("result")
        return missing


@dataclass(slots=True)
class ToolCall:
    step_num: int
    tool_name: str
    duration_sec: float
    timestamp_sec: float
    args: dict[str, Any]
    is_error: bool = False
    error_message: str | None = None
    result_chars: int | None = None
    result_text: str | None = None
    is_parallel: bool = False
    iteration: int | None = None
    model_timings: tuple[ModelTiming, ...] = ()


@dataclass(slots=True)
class EntityRef:
    entity_type: str
    prefixed_id: str
    name: str | None
    detail: str | None
    step_num: int


@dataclass(slots=True)
class ResultDoc:
    section_label: str | None
    prompt_text: str
    total_tool_calls: int | None
    planning_time_sec: float | None
    execution_time_sec: float | None
    verdict_time_sec: float | None
    total_time_sec: float | None
    answer_markdown: str
    answer_text: str
    answer_word_count: int
    verdict_text: str | None
    verdict_bucket: str | None
    explanation_text: str | None
