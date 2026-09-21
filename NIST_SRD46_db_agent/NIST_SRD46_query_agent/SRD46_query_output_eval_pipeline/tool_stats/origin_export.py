from __future__ import annotations

import csv
import json
from pathlib import Path


def _section_sort_key(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return (10**9,)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def _sanitize_cell(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _copy_all_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    written: list[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(csv_dir.glob("*.csv")):
        fieldnames, rows = _read_csv(source)
        if not fieldnames:
            dest = target_dir / source.name
            dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(dest)
            continue
        cleaned_rows = [
            {field: _sanitize_cell(row.get(field)) for field in fieldnames}
            for row in rows
        ]
        written.append(_write_csv(target_dir / source.name, fieldnames, cleaned_rows))
    return written


def _write_run_timing_major_section_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "run_timing_by_model_major_section.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    row_by_key = {(row["major_section"], row["model"]): row for row in rows}
    matrix_rows: list[dict[str, str]] = []
    for major_section in major_sections:
        matrix_row = {
            "major_section": major_section,
            "warning_threshold_sec": _sanitize_cell(
                next((row.get("warning_threshold_sec") for row in rows if row["major_section"] == major_section), None)
            ),
        }
        for model in models:
            record = row_by_key.get((major_section, model), {})
            matrix_row[f"{model}_total_mean_sec"] = _sanitize_cell(record.get("total_mean_sec"))
            matrix_row[f"{model}_planning_mean_sec"] = _sanitize_cell(record.get("planning_mean_sec"))
        matrix_rows.append(matrix_row)
    fieldnames = ["major_section", "warning_threshold_sec"]
    for model in models:
        fieldnames.extend([f"{model}_total_mean_sec", f"{model}_planning_mean_sec"])
    return [
        _write_csv(
            target_dir / "run_timing_by_model_major_section_matrix.csv",
            fieldnames,
            matrix_rows,
        )
    ]


def _write_second_order_tool_chain_matrix(csv_dir: Path, target_dir: Path, *, limit: int = 15) -> list[Path]:
    overall_source = csv_dir / "tool_chain_second_order_overall.csv"
    model_source = csv_dir / "tool_chain_second_order_by_model.csv"
    if not overall_source.exists() or not model_source.exists():
        return []
    _overall_fields, overall_rows = _read_csv(overall_source)
    _model_fields, model_rows = _read_csv(model_source)
    models = sorted({row["model"] for row in model_rows})
    chains = [row["chain"] for row in sorted(overall_rows, key=lambda row: float(row.get("n_occurrences") or "0"), reverse=True)[:limit]]
    row_by_key = {(row["model"], row["chain"]): row for row in model_rows}
    matrix_rows: list[dict[str, str]] = []
    for chain in chains:
        matrix_row = {"chain": chain}
        for model in models:
            matrix_row[model] = _sanitize_cell((row_by_key.get((model, chain)) or {}).get("n_occurrences"))
        matrix_rows.append(matrix_row)
    return [
        _write_csv(
            target_dir / "tool_chain_second_order_top15_by_model.csv",
            ["chain", *models],
            matrix_rows,
        )
    ]


def _write_tool_duration_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "tool_usage_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    mean_by_tool: dict[str, list[float]] = {}
    for row in rows:
        value = row.get("duration_mean_sec")
        if not value:
            continue
        mean_by_tool.setdefault(row["tool_name"], []).append(float(value))
    tools = [
        tool_name
        for tool_name, values in sorted(
            mean_by_tool.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
        if values
    ]
    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    matrix_rows: list[dict[str, str]] = []
    for tool in tools:
        matrix_row = {"tool": tool}
        for model in models:
            matrix_row[model] = _sanitize_cell((row_by_key.get((model, tool)) or {}).get("duration_mean_sec"))
        matrix_rows.append(matrix_row)
    return [
        _write_csv(
            target_dir / "tool_duration_by_model.csv",
            ["tool", *models],
            matrix_rows,
        )
    ]


def _write_tool_wall_time_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "tool_wall_timing_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    mean_by_tool: dict[str, list[float]] = {}
    for row in rows:
        value = row.get("wall_mean_sec")
        if not value:
            continue
        mean_by_tool.setdefault(row["tool_name"], []).append(float(value))
    tools = [
        tool_name
        for tool_name, values in sorted(
            mean_by_tool.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
        if values
    ]
    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    matrix_rows: list[dict[str, str]] = []
    for tool in tools:
        matrix_row = {"tool": tool}
        for model in models:
            matrix_row[model] = _sanitize_cell((row_by_key.get((model, tool)) or {}).get("wall_mean_sec"))
        matrix_rows.append(matrix_row)
    return [
        _write_csv(
            target_dir / "tool_wall_time_by_model.csv",
            ["tool", *models],
            matrix_rows,
        )
    ]


def _write_tool_argo_duration_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "tool_argo_timing_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    mean_by_tool: dict[str, list[float]] = {}
    for row in rows:
        value = row.get("argo_duration_mean_sec")
        if not value:
            continue
        mean_by_tool.setdefault(row["tool_name"], []).append(float(value))
    tools = [
        tool_name
        for tool_name, values in sorted(
            mean_by_tool.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
        if values
    ]
    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    matrix_rows: list[dict[str, str]] = []
    for tool in tools:
        matrix_row = {"tool": tool}
        for model in models:
            matrix_row[model] = _sanitize_cell((row_by_key.get((model, tool)) or {}).get("argo_duration_mean_sec"))
        matrix_rows.append(matrix_row)
    return [
        _write_csv(
            target_dir / "tool_argo_duration_by_model.csv",
            ["tool", *models],
            matrix_rows,
        )
    ]


def _write_compactor_context_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "compactor_rounds_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    rows = [row for row in rows if row.get("model")]
    matrix_rows = [
        {
            "model": row["model"],
            "run_presence_rate": _sanitize_cell(row.get("run_presence_rate")),
            "mean_rounds_per_run": _sanitize_cell(row.get("mean_rounds_per_run")),
            "selected_rounds_eligible_for_next_context": _sanitize_cell(row.get("selected_rounds_eligible_for_next_context")),
            "selected_rounds_with_next_context": _sanitize_cell(row.get("selected_rounds_with_next_context")),
            "selected_next_context_coverage_rate": _sanitize_cell(row.get("selected_next_context_coverage_rate")),
            "selected_context_chars_mean": _sanitize_cell(row.get("selected_context_chars_mean")),
            "selected_next_context_chars_mean": _sanitize_cell(row.get("selected_next_context_chars_mean")),
            "context_chars_mean": _sanitize_cell(row.get("context_chars_mean")),
            "selected_context_turns_mean": _sanitize_cell(row.get("selected_context_turns_mean")),
            "selected_next_context_turns_mean": _sanitize_cell(row.get("selected_next_context_turns_mean")),
            "context_turns_mean": _sanitize_cell(row.get("context_turns_mean")),
        }
        for row in rows
    ]
    return [
        _write_csv(
            target_dir / "compactor_context_by_model.csv",
            [
                "model",
                "run_presence_rate",
                "mean_rounds_per_run",
                "selected_rounds_eligible_for_next_context",
                "selected_rounds_with_next_context",
                "selected_next_context_coverage_rate",
                "selected_context_chars_mean",
                "selected_next_context_chars_mean",
                "context_chars_mean",
                "selected_context_turns_mean",
                "selected_next_context_turns_mean",
                "context_turns_mean",
            ],
            matrix_rows,
        )
    ]


def _write_compactor_selection_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "compactor_rounds_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    rows = [row for row in rows if row.get("model")]
    matrix_rows = [
        {
            "model": row["model"],
            "mean_selection_rounds_per_run": _sanitize_cell(row.get("mean_selection_rounds_per_run")),
            "selected_round_rate": _sanitize_cell(row.get("selected_round_rate")),
            "none_round_rate": _sanitize_cell(row.get("none_round_rate")),
            "selected_candidate_mean": _sanitize_cell(row.get("selected_candidate_mean")),
            "parallel_task_mean": _sanitize_cell(row.get("parallel_task_mean")),
        }
        for row in rows
    ]
    return [
        _write_csv(
            target_dir / "compactor_selection_by_model.csv",
            [
                "model",
                "mean_selection_rounds_per_run",
                "selected_round_rate",
                "none_round_rate",
                "selected_candidate_mean",
                "parallel_task_mean",
            ],
            matrix_rows,
        )
    ]


def _write_compactor_retry_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "compactor_rounds_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    rows = [row for row in rows if row.get("model")]
    matrix_rows = [
        {
            "model": row["model"],
            "retry_events_total": _sanitize_cell(row.get("retry_events_total")),
            "accepted_events_total": _sanitize_cell(row.get("accepted_events_total")),
            "skipped_events_total": _sanitize_cell(row.get("skipped_events_total")),
            "retry_exhausted_events_total": _sanitize_cell(row.get("retry_exhausted_events_total")),
            "max_retry_keep_events_total": _sanitize_cell(row.get("max_retry_keep_events_total")),
            "summary_subagent_events_total": _sanitize_cell(row.get("summary_subagent_events_total")),
            "summary_failed_events_total": _sanitize_cell(row.get("summary_failed_events_total")),
            "retry_attempt_mean": _sanitize_cell(row.get("retry_attempt_mean")),
            "retry_attempt_max": _sanitize_cell(row.get("retry_attempt_max")),
        }
        for row in rows
    ]
    return [
        _write_csv(
            target_dir / "compactor_retry_by_model.csv",
            [
                "model",
                "retry_events_total",
                "accepted_events_total",
                "skipped_events_total",
                "retry_exhausted_events_total",
                "max_retry_keep_events_total",
                "summary_subagent_events_total",
                "summary_failed_events_total",
                "retry_attempt_mean",
                "retry_attempt_max",
            ],
            matrix_rows,
        )
    ]


def _write_compactor_trigger_summary_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "compactor_trigger_summary_by_model.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    rows = [row for row in rows if row.get("model")]
    matrix_rows = [
        {
            "model": row["model"],
            "triggered_rounds": _sanitize_cell(row.get("triggered_rounds")),
            "normal_run_triggered_rounds": _sanitize_cell(row.get("normal_run_triggered_rounds")),
            "none_rounds": _sanitize_cell(row.get("none_rounds")),
            "l0_no_match_rounds": _sanitize_cell(row.get("l0_no_match_rounds")),
            "runs_with_triggered_compaction": _sanitize_cell(row.get("runs_with_triggered_compaction")),
            "run_trigger_rate": _sanitize_cell(row.get("run_trigger_rate")),
            "runs_with_triggered_success": _sanitize_cell(row.get("runs_with_triggered_success")),
            "triggered_success_run_rate": _sanitize_cell(row.get("triggered_success_run_rate")),
        }
        for row in rows
    ]
    return [
        _write_csv(
            target_dir / "compactor_trigger_summary_by_model.csv",
            [
                "model",
                "triggered_rounds",
                "normal_run_triggered_rounds",
                "none_rounds",
                "l0_no_match_rounds",
                "runs_with_triggered_compaction",
                "run_trigger_rate",
                "runs_with_triggered_success",
                "triggered_success_run_rate",
            ],
            matrix_rows,
        )
    ]


def _script_text() -> str:
    return """from __future__ import annotations

import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / \"SRD46_query_output_eval_pipeline\").exists():
            return candidate
    raise RuntimeError(\"Could not locate repository root from origin_import folder\")


def main() -> int:
    here = Path(__file__).resolve().parent
    repo_root = _find_repo_root(here)
    sys.path.insert(0, str(repo_root))
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.tool_stats.origin_export import populate_origin_import

    result = populate_origin_import(csv_dir=here.parent / \"csv\", out_root=here.parent)
    print(f\"Wrote {len(result['all_csv'])} copy-ready CSVs to {here / 'all_csv'}\")
    print(f\"Wrote {len(result['plot_ready'])} plot-ready CSVs to {here / 'plot_ready'}\")
    return 0


if __name__ == \"__main__\":
    raise SystemExit(main())
"""


def populate_origin_import(*, csv_dir: Path, out_root: Path) -> dict[str, list[Path] | Path]:
    origin_dir = out_root / "origin_import"
    all_csv_dir = origin_dir / "all_csv"
    plot_ready_dir = origin_dir / "plot_ready"

    copied = _copy_all_csvs(csv_dir, all_csv_dir)
    plot_ready = _write_run_timing_major_section_matrix(csv_dir, plot_ready_dir)
    plot_ready.extend(_write_tool_duration_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_tool_wall_time_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_tool_argo_duration_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_compactor_trigger_summary_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_compactor_context_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_compactor_selection_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_compactor_retry_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_second_order_tool_chain_matrix(csv_dir, plot_ready_dir))

    script_path = origin_dir / "convert_tool_stats_csvs_for_origin.py"
    script_path.write_text(_script_text(), encoding="utf-8")

    readme_path = origin_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Origin Import Bundle",
                "",
                "- `all_csv/`: normalized copies of every CSV under `../csv/` with `nan` cells blanked for OriginPro import.",
                "- `plot_ready/`: wide tables for the major-section run-timing grouped-bar plot, the mean successful step-header tool-duration chart, the mean deduced wall-time-per-call chart excluding the final pre-answer group, the mean Argo `_meta` timing chart, the compactor trigger/context/selection/retry charts, and the top second-order tool-chain chart.",
                "- `convert_tool_stats_csvs_for_origin.py`: rerun the export after any CSV changes.",
                "",
                "Typical usage:",
                "",
                "```bash",
                "python convert_tool_stats_csvs_for_origin.py",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    manifest_path = origin_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_csv_dir": str(csv_dir),
                "all_csv": [path.name for path in copied],
                "plot_ready": [path.name for path in plot_ready],
                "script": script_path.name,
                "readme": readme_path.name,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return {
        "origin_dir": origin_dir,
        "all_csv": copied,
        "plot_ready": plot_ready,
        "script": script_path,
        "readme": readme_path,
        "manifest": manifest_path,
    }


__all__ = ["populate_origin_import"]
