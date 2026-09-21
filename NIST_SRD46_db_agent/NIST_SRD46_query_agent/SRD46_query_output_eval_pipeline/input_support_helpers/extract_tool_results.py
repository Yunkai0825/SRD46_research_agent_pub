"""Extract tool results from history files and answer bodies from result files.

Produces two files per run in ``_output_eval/``:
- ``tool_eval_batch{N}.md`` — structured markdown with each tool call's result
- ``answer_batch{N}.md`` — stripped answer body (no header/verdict)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .parse_history import parse_history
from .scan import DEFAULT_OUTPUT_ROOT
_WORKSPACE_ROOT = Path(__file__).absolute().parents[4]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

# Reuse header/verdict stripping from the enricher
_RESULT_HEADER_RE = re.compile(
    r"^#\s+Q[\d.]+\s+--\s+Result.*?^---\s*$",
    re.MULTILINE | re.DOTALL,
)
_VERDICT_SECTION_RE = re.compile(
    r"^#{1,3}\s+Verdict\s*&?\s*Explanation.*",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def _strip_result_envelope(text: str) -> str:
    text = _RESULT_HEADER_RE.sub("", text, count=1).lstrip()
    text = _VERDICT_SECTION_RE.sub("", text).rstrip()
    return text


def _format_args(args: dict) -> str:
    """Render full tool args as stable pretty-printed JSON."""
    if not args:
        return "{}"
    try:
        return json.dumps(args, ensure_ascii=False, indent=2)
    except TypeError:
        return json.dumps({k: str(v) for k, v in args.items()}, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def extract_run(
    model: str,
    question_id: str,
    batch: int,
    *,
    output_root: str | Path | None = None,
    eval_root: str | Path | None = None,
) -> dict[str, Path]:
    """Extract tool results and answer body for one run.

    Returns ``{"tool_eval": Path, "answer": Path}`` of written files.
    """
    root = Path(output_root) if output_root else DEFAULT_OUTPUT_ROOT
    eval_dir = Path(eval_root) if eval_root else _QUERY_EVAL_ROOT

    question_dir = root / f"Model_{model}" / question_id
    out_dir = eval_dir / f"Model_{model}" / question_id
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}

    # ── tool_eval ────────────────────────────────────────────
    history_path = question_dir / f"{question_id}_history_batch{batch}.md"
    if history_path.exists():
        tool_calls = parse_history(history_path)
        lines: list[str] = [
            f"# {question_id} — Tool Results (batch {batch})\n",
        ]
        for tc in tool_calls:
            if tc.result_text is None:
                continue
            # Skip internal planning tools that don't return DB data
            if tc.tool_name.startswith("0_"):
                continue
            args_text = _format_args(tc.args)
            lines.append(f"### Step {tc.step_num}: `{tc.tool_name}`")
            lines.append("**Args:**")
            lines.append("```json")
            lines.extend(args_text.splitlines())
            lines.append("```")
            lines.append("")
            lines.append(tc.result_text)
            lines.append("")
            lines.append("---\n")

        tool_eval_path = out_dir / f"tool_eval_batch{batch}.md"
        tool_eval_path.write_text("\n".join(lines), encoding="utf-8")
        written["tool_eval"] = tool_eval_path

    # ── answer ───────────────────────────────────────────────
    result_path = question_dir / f"{question_id}_result_batch{batch}.md"
    if result_path.exists():
        raw = result_path.read_text(encoding="utf-8", errors="replace")
        answer_body = _strip_result_envelope(raw)
        answer_path = out_dir / f"answer_batch{batch}.md"
        answer_path.write_text(answer_body, encoding="utf-8")
        written["answer"] = answer_path

    return written


def extract_all(
    model: str | None = None,
    question_id: str | None = None,
    output_root: str | Path | None = None,
    eval_root: str | Path | None = None,
) -> int:
    """Bulk-extract tool results for all matching runs. Returns count."""
    from .scan import scan_outputs

    root = Path(output_root) if output_root else DEFAULT_OUTPUT_ROOT
    runs = scan_outputs([root])
    count = 0
    for run in runs:
        if model and run.model != model:
            continue
        if question_id and run.question_id != question_id:
            continue
        extract_run(
            run.model, run.question_id, run.batch,
            output_root=output_root, eval_root=eval_root,
        )
        count += 1
    return count
