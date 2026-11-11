from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import ModelTiming, ToolCall

STEP_RE = re.compile(
    r"^\*\*Step (?P<step>\d+):\*\* `(?P<tool>[^`]+)`(?P<rest>.*?)\*\[(?P<duration>[\d.]+)s @ (?P<elapsed>[\d.]+)s\]\*",
    re.MULTILINE,
)
ARGS_RE = re.compile(r"- Args:\s*```json\s*(?P<json>.*?)\s*```", re.DOTALL)
ERROR_RE = re.compile(r"- \*\*Error:\*\* (?P<error>.+)")
RESULT_CHARS_RE = re.compile(r"- Agent-facing result:\s*(?P<count>\d+)\s+chars")
RESULT_TEXT_RE = re.compile(
    r"<details><summary>Agent-facing result</summary>\s*(?P<result>.*?)\s*</details>",
    re.DOTALL,
)
ITERATION_RE = re.compile(r"\(iter (?P<iteration>\d+),")
MODEL_META_RE = re.compile(
    r"\[_meta:\s*model=(?P<model>[^,\]\n]+),\s*elapsed=(?P<elapsed>[\d.]+)s(?:,\s*revision=(?P<revision>True|False))?[^\]]*\]"
)


def parse_history(path: str | Path) -> list[ToolCall]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_history_text(text)


def parse_history_text(text: str) -> list[ToolCall]:
    matches = list(STEP_RE.finditer(text))
    calls: list[ToolCall] = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]

        raw_args = _extract_args_block(block)
        args = json.loads(raw_args) if raw_args is not None else {}
        error_match = ERROR_RE.search(block)
        result_chars_match = RESULT_CHARS_RE.search(block)
        result_text_match = RESULT_TEXT_RE.search(block)
        iteration_match = ITERATION_RE.search(block)
        header_rest = match.group("rest")
        model_timings = tuple(_extract_model_timings(block))

        calls.append(
            ToolCall(
                step_num=int(match.group("step")),
                tool_name=match.group("tool"),
                duration_sec=float(match.group("duration")),
                timestamp_sec=float(match.group("elapsed")),
                args=args,
                is_error="**[ERROR]**" in header_rest or error_match is not None,
                error_message=error_match.group("error").strip() if error_match else None,
                result_chars=int(result_chars_match.group("count")) if result_chars_match else None,
                result_text=result_text_match.group("result").strip() if result_text_match else None,
                is_parallel="parallel" in header_rest.lower(),
                iteration=int(iteration_match.group("iteration")) if iteration_match else None,
                model_timings=model_timings,
            )
        )

    return calls


def _extract_args_block(block: str) -> str | None:
    match = ARGS_RE.search(block)
    if not match:
        return None
    return match.group("json")


def _extract_model_timings(block: str) -> list[ModelTiming]:
    timings: list[ModelTiming] = []
    for match in MODEL_META_RE.finditer(block):
        revision_raw = match.group("revision")
        timings.append(
            ModelTiming(
                model_name=match.group("model").strip(),
                elapsed_sec=float(match.group("elapsed")),
                revision=(revision_raw == "True") if revision_raw is not None else None,
            )
        )
    return timings
