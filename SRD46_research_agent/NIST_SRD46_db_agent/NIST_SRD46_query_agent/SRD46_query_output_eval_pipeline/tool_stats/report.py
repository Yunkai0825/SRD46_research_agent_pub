"""Narrative report for the tool statistics bundle."""
from __future__ import annotations

import csv
import json
from pathlib import Path

TOP_N = 10


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(value: str | None) -> float:
    try:
        return float(value or "nan")
    except ValueError:
        return float("nan")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _top_rows(rows: list[dict[str, str]], *, sort_key: str, limit: int = TOP_N) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: _f(row.get(sort_key)), reverse=True)[:limit]


def write_report(out_root: str | Path) -> Path:
    root = Path(out_root)
    usage_overall = _read_csv(root / "csv" / "tool_usage_overall.csv")
    usage_model = _read_csv(root / "csv" / "tool_usage_by_model.csv")
    argo_timing_overall = _read_csv(root / "csv" / "tool_argo_timing_overall.csv")
    wall_timing_overall = _read_csv(root / "csv" / "tool_wall_timing_overall.csv")
    compactor_trigger_overall = _read_csv(root / "csv" / "compactor_trigger_summary_overall.csv")
    compactor_trigger_model = _read_csv(root / "csv" / "compactor_trigger_summary_by_model.csv")
    compactor_rounds_overall = _read_csv(root / "csv" / "compactor_rounds_overall.csv")
    compactor_rounds_model = _read_csv(root / "csv" / "compactor_rounds_by_model.csv")
    compactor_event_types_overall = _read_csv(root / "csv" / "compactor_event_types_overall.csv")
    failures = _read_csv(root / "csv" / "tool_failures_by_reason.csv")
    parallel = _read_csv(root / "csv" / "parallel_batch_patterns.csv")
    snippets = _read_csv(root / "csv" / "workflow_snippets.csv")
    run_timing_model = _read_csv(root / "csv" / "run_timing_by_model.csv")
    load_meta = {}
    meta_path = root / "_data" / "load_meta.json"
    if meta_path.exists():
        load_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    sections: list[str] = [
        "# Tool statistics report",
        "",
        "## Corpus",
        "",
        f"- Runs analysed: **{load_meta.get('n_runs_loaded', 0):,}**",
        f"- Tool calls analysed: **{load_meta.get('n_tool_calls', 0):,}**",
        f"- Workflow groups analysed: **{load_meta.get('n_workflow_groups', 0):,}**",
        f"- Load issues: **{load_meta.get('n_issues', 0):,}**",
        "- Tool-usage tables exclude planning tools prefixed with `0_`.",
        "- Step-header tool-duration metrics exclude failed tool calls and use the history header `[Xs @ Ys]` duration as mean seconds per successful call.",
        "- Wall-time plot/export metrics use the difference between consecutive tool-group end timestamps and exclude the final pre-answer workflow group in each run.",
        "- Argo analysis metrics use summed `_meta` elapsed timings per successful tool call when present; tools without recorded `_meta` timings are omitted from the Argo timing chart/export.",
        "- Session-compactor metrics are parsed from each history file's final `Compactor Activity` log; they cover context pressure, selection outcomes, task fan-out, and any retry/validator events that were actually emitted.",
        "",
    ]

    if usage_overall:
        sections.extend(
            [
                f"## Top {TOP_N} most-used tools",
                "",
                _table(
                    ["tool", "calls", "run_presence", "mean_sec", "error_rate"],
                    [
                        [
                            row["tool_name"],
                            row["n_calls"],
                            f"{_f(row['run_presence_rate']) * 100:0.1f}%",
                            f"{_f(row['duration_mean_sec']):0.2f}",
                            f"{_f(row['error_rate']) * 100:0.1f}%",
                        ]
                        for row in _top_rows(usage_overall, sort_key="n_calls")
                    ],
                ),
                "",
                f"## Top {TOP_N} slowest tools",
                "",
                _table(
                    ["tool", "step_header_mean_sec", "step_header_p95_sec", "calls"],
                    [
                        [
                            row["tool_name"],
                            f"{_f(row['duration_mean_sec']):0.2f}",
                            f"{_f(row['duration_p95_sec']):0.2f}",
                            row["n_calls"],
                        ]
                        for row in _top_rows(usage_overall, sort_key="duration_mean_sec")
                    ],
                ),
                "",
            ]
        )

    if wall_timing_overall:
        sections.extend(
            [
                f"## Top {TOP_N} slowest tools by deduced wall time",
                "",
                _table(
                    ["tool", "wall_mean_sec", "wall_p95_sec", "wall_timed_calls", "coverage"],
                    [
                        [
                            row["tool_name"],
                            f"{_f(row['wall_mean_sec']):0.2f}",
                            f"{_f(row['wall_p95_sec']):0.2f}",
                            row["wall_timed_calls"],
                            f"{_f(row['wall_coverage_rate']) * 100:0.1f}%",
                        ]
                        for row in _top_rows(wall_timing_overall, sort_key="wall_mean_sec")
                    ],
                ),
                "",
            ]
        )

    if argo_timing_overall:
        sections.extend(
            [
                f"## Top {TOP_N} slowest tools by Argo analysis time",
                "",
                _table(
                    ["tool", "argo_mean_sec", "argo_p95_sec", "timed_calls", "coverage"],
                    [
                        [
                            row["tool_name"],
                            f"{_f(row['argo_duration_mean_sec']):0.2f}",
                            f"{_f(row['argo_duration_p95_sec']):0.2f}",
                            row["argo_timed_calls"],
                            f"{_f(row['argo_coverage_rate']) * 100:0.1f}%",
                        ]
                        for row in _top_rows(argo_timing_overall, sort_key="argo_duration_mean_sec")
                    ],
                ),
                "",
            ]
        )

    if compactor_rounds_model:
        sections.extend(
            [
                "## Compactor turn summary by model",
                "",
                _table(
                    ["model", "triggered_rounds", "triggered_success_normal", "none_rounds", "l0_no_match_rounds", "runs_with_triggered", "run_trigger_rate", "runs_with_triggered_success", "triggered_success_run_rate"],
                    [
                        [
                            row["model"],
                            row["triggered_rounds"],
                            row.get("normal_run_triggered_rounds") or "0",
                            row["none_rounds"],
                            row["l0_no_match_rounds"],
                            row["runs_with_triggered_compaction"],
                            f"{_f(row['run_trigger_rate']) * 100:0.1f}%",
                            row.get("runs_with_triggered_success") or "0",
                            f"{_f(row['triggered_success_run_rate']) * 100:0.1f}%",
                        ]
                        for row in sorted(compactor_trigger_model, key=lambda item: item["model"])
                    ],
                ),
                "",
                "## Session compactor by model",
                "",
                _table(
                    ["model", "run_presence", "rounds/run", "ctx_chars_mean", "ctx_turns_mean", "selected_rate", "selected_candidates_mean", "parallel_tasks_mean", "retry_events"],
                    [
                        [
                            row["model"],
                            f"{_f(row['run_presence_rate']) * 100:0.1f}%",
                            f"{_f(row['mean_rounds_per_run']):0.2f}",
                            f"{_f(row['context_chars_mean']):0.0f}",
                            f"{_f(row['context_turns_mean']):0.1f}",
                            f"{_f(row['selected_round_rate']) * 100:0.1f}%",
                            f"{_f(row['selected_candidate_mean']):0.2f}",
                            f"{_f(row['parallel_task_mean']):0.2f}",
                            str(int(_f(row['retry_events_total'])) if not (_f(row['retry_events_total']) != _f(row['retry_events_total'])) else 0),
                        ]
                        for row in sorted(compactor_rounds_model, key=lambda item: item["model"])
                    ],
                ),
                "",
            ]
        )

    if compactor_trigger_overall:
        overall = compactor_trigger_overall[0]
        sections.extend(
            [
                f"- Overall triggered compaction turns: **{overall['triggered_rounds']}**; triggered-success turns on normal runs: **{overall.get('normal_run_triggered_rounds') or '0'}**; NONE turns: **{overall['none_rounds']}**; L0 no-match turns: **{overall['l0_no_match_rounds']}**; runs with >=1 triggered turn: **{overall['runs_with_triggered_compaction']} / {overall['n_runs']}** ({_f(overall['run_trigger_rate']) * 100:0.1f}%); runs with >=1 triggered-success turn: **{overall.get('runs_with_triggered_success') or '0'} / {overall['n_runs']}** ({_f(overall['triggered_success_run_rate']) * 100:0.1f}%).",
                "",
            ]
        )

    if compactor_rounds_overall:
        overall = compactor_rounds_overall[0]
        retry_total = _f(overall.get("retry_events_total"))
        accepted_total = _f(overall.get("accepted_events_total"))
        summary_total = _f(overall.get("summary_subagent_events_total"))
        if all(value == 0 or value != value for value in (retry_total, accepted_total, summary_total)):
            sections.extend(
                [
                    "- Current published histories contain strong compactor context and selection signals, but validator retry/accept/summary-subagent events are absent or effectively zero in this corpus.",
                    "",
                ]
            )

    if compactor_event_types_overall:
        sections.extend(
            [
                f"## Top {TOP_N} compactor event types",
                "",
                _table(
                    ["event_type", "events", "run_presence", "content_chars_mean", "context_chars_mean", "attempt_mean"],
                    [
                        [
                            row["event_type"],
                            row["n_events"],
                            f"{_f(row['run_presence_rate']) * 100:0.1f}%",
                            f"{_f(row['content_chars_mean']):0.1f}",
                            f"{_f(row['context_chars_mean']):0.1f}",
                            f"{_f(row['attempt_mean']):0.2f}",
                        ]
                        for row in _top_rows(compactor_event_types_overall, sort_key="n_events")
                    ],
                ),
                "",
            ]
        )

    if usage_model:
        top_model_rows = sorted(usage_model, key=lambda row: (row["model"], -_f(row["call_share"]), row["tool_name"]))
        by_model: dict[str, list[dict[str, str]]] = {}
        for row in top_model_rows:
            by_model.setdefault(row["model"], []).append(row)
        sections.append(f"## Top {TOP_N} tools by model\n")
        for model, rows in by_model.items():
            sections.append(f"### {model}\n")
            sections.append(
                _table(
                    ["tool", "call_share", "mean_calls/run", "mean_sec"],
                    [
                        [
                            row["tool_name"],
                            f"{_f(row['call_share']) * 100:0.1f}%",
                            f"{_f(row['mean_calls_per_run']):0.2f}",
                            f"{_f(row['duration_mean_sec']):0.2f}",
                        ]
                        for row in rows[:TOP_N]
                    ],
                )
            )
            sections.append("")

    if run_timing_model:
        sections.extend(
            [
                "## Run timing by model",
                "",
                _table(
                    ["model", "mean_total_sec", "mean_planning_sec", "mean_execution_sec", "error_run_rate"],
                    [
                        [
                            row["model"],
                            f"{_f(row['total_mean_sec']):0.1f}",
                            f"{_f(row['planning_mean_sec']):0.1f}",
                            f"{_f(row['execution_mean_sec']):0.1f}",
                            f"{_f(row['error_run_rate']) * 100:0.1f}%",
                        ]
                        for row in sorted(run_timing_model, key=lambda item: -_f(item["total_mean_sec"]))
                    ],
                ),
                "",
            ]
        )

    if failures:
        sections.extend(
            [
                f"## Top {TOP_N} tool failures",
                "",
                _table(
                    ["tool", "category", "reason", "failures"],
                    [
                        [row["tool_name"], row.get("error_category") or "", row.get("error_reason") or "", row["n_failures"]]
                        for row in _top_rows(failures, sort_key="n_failures")
                    ],
                ),
                "",
            ]
        )

    if parallel:
        sections.extend(
            [
                f"## Top {TOP_N} parallel batches",
                "",
                _table(
                    ["signature", "occurrences", "mean_wall_sec", "error_rate"],
                    [
                        [
                            row["group_signature"],
                            row["n_occurrences"],
                            f"{_f(row['mean_wall_sec']):0.2f}",
                            f"{_f(row['error_batch_rate']) * 100:0.1f}%",
                        ]
                        for row in _top_rows(parallel, sort_key="n_occurrences")
                    ],
                ),
                "",
            ]
        )

    if snippets:
        sections.extend(
            [
                f"## Top {TOP_N} workflow snippets",
                "",
                _table(
                    ["len", "snippet", "occurrences", "runs"],
                    [
                        [row["snippet_len"], row["snippet"], row["n_occurrences"], row["n_runs"]]
                        for row in _top_rows(snippets, sort_key="n_occurrences")
                    ],
                ),
                "",
            ]
        )

    figure_dir = root / "figures"
    figures = sorted(path.name for path in figure_dir.glob("*.png")) if figure_dir.exists() else []
    if figures:
        sections.extend(
            [
                "## Figures emitted",
                "",
                *[f"- `{name}`" for name in figures],
                "",
            ]
        )

    sections.extend(
        [
            "## Files emitted",
            "",
            f"- Data tables: `{root / '_data'}`",
            f"- Aggregated CSVs: `{root / 'csv'}`",
            f"- JSON mirrors: `{root / 'json'}`",
            f"- Figures: `{root / 'figures'}`",
            f"- OriginPro import bundle: `{root / 'origin_import'}`",
            "",
        ]
    )

    out_path = root / "REPORT.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    return out_path


__all__ = ["write_report"]