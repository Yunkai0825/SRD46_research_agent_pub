"""Reusable build helper for canonical tool statistics."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from . import aggregate as agg
from .loader import (
    DEFAULT_OUTPUT_ROOT,
    iter_tool_records,
    write_issues_csv,
    write_runs_csv,
    write_tool_calls_csv,
    write_workflow_groups_csv,
)
_WORKSPACE_ROOT = Path(__file__).absolute().parents[4]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

DEFAULT_OUT = (_QUERY_EVAL_ROOT / "Tool_Stats")
_StatusPrinter = Callable[[str], None]


@dataclass(slots=True)
class ToolStatsBuildResult:
    output_root: Path
    out_root: Path
    data_dir: Path
    csv_dir: Path
    json_dir: Path
    fig_dir: Path
    n_runs: int
    n_tool_calls: int
    n_workflow_groups: int
    n_issues: int


def _resolve(path: str | Path | None, default: Path) -> Path:
    if path is None:
        return default
    return Path(path)


def _filters(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = sorted({value for value in values if value})
    return cleaned or None


def _write_meta(
    *,
    path: Path,
    output_root: Path,
    out_root: Path,
    bundle,
    include_models,
    include_questions,
    include_sections,
    with_plots: bool,
) -> None:
    payload = {
        "output_root": str(output_root),
        "out_root": str(out_root),
        "n_runs_loaded": len(bundle.runs),
        "n_tool_calls": len(bundle.tool_calls),
        "n_workflow_groups": len(bundle.workflow_groups),
        "n_issues": len(bundle.issues),
        "models": sorted({run.model for run in bundle.runs}),
        "questions": sorted({run.question_id for run in bundle.runs}),
        "filters": {
            "models": include_models,
            "questions": include_questions,
            "sections": include_sections,
        },
        "with_plots": with_plots,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_tool_stats_bundle(
    *,
    root: str | Path | None = None,
    out: str | Path | None = None,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    with_plots: bool = True,
    print_fn: _StatusPrinter = print,
) -> ToolStatsBuildResult:
    output_root = _resolve(root, DEFAULT_OUTPUT_ROOT)
    out_root = _resolve(out, DEFAULT_OUT)
    data_dir = out_root / "_data"
    csv_dir = out_root / "csv"
    json_dir = out_root / "json"
    fig_dir = out_root / "figures"
    for directory in (data_dir, csv_dir, json_dir):
        directory.mkdir(parents=True, exist_ok=True)
    if with_plots:
        fig_dir.mkdir(parents=True, exist_ok=True)

    model_filters = _filters(include_models)
    question_filters = _filters(include_questions)
    section_filters = _filters(include_sections)

    print_fn(f"[tool-stats] output root: {output_root}")
    print_fn("[tool-stats] loading tool history and result timing ...")
    bundle = iter_tool_records(
        output_root,
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
    )
    print_fn(
        f"  runs: {len(bundle.runs)}  tool_calls: {len(bundle.tool_calls)}  "
        f"workflow_groups: {len(bundle.workflow_groups)}  issues: {len(bundle.issues)}"
    )

    write_tool_calls_csv(bundle.tool_calls, data_dir / "tool_calls_long.csv")
    write_workflow_groups_csv(bundle.workflow_groups, data_dir / "workflow_groups_long.csv")
    write_runs_csv(bundle.runs, data_dir / "runs_long.csv")
    if bundle.issues:
        write_issues_csv(bundle.issues, data_dir / "load_issues.csv")
    _write_meta(
        path=data_dir / "load_meta.json",
        output_root=output_root,
        out_root=out_root,
        bundle=bundle,
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
        with_plots=with_plots,
    )

    print_fn("[tool-stats] aggregating tool usage and timing ...")
    agg.emit_tool_usage(bundle.tool_calls, bundle.runs, csv_dir, json_dir)
    agg.emit_tool_argo_timing(bundle.tool_calls, bundle.runs, csv_dir, json_dir)
    agg.emit_tool_wall_timing(bundle.tool_calls, bundle.runs, csv_dir, json_dir)
    agg.emit_run_timing(bundle.runs, csv_dir, json_dir)
    agg.emit_tool_failures(bundle.tool_calls, csv_dir, json_dir)
    agg.emit_parallel_stats(bundle.workflow_groups, csv_dir, json_dir)
    agg.emit_workflow_snippets(bundle.workflow_groups, csv_dir, json_dir)
    agg.emit_second_order_tool_chains(bundle.workflow_groups, csv_dir, json_dir)
    agg.emit_compactor_stats(bundle.runs, csv_dir, json_dir)

    if with_plots:
        try:
            from . import plots

            print_fn("[tool-stats] rendering figures ...")
            plots.render_all(csv_dir, fig_dir)
        except Exception as exc:  # noqa: BLE001
            print_fn(f"[tool-stats] plots skipped: {exc}")

    try:
        from . import origin_export

        print_fn("[tool-stats] preparing Origin import bundle ...")
        origin_export.populate_origin_import(csv_dir=csv_dir, out_root=out_root)
    except Exception as exc:  # noqa: BLE001
        print_fn(f"[tool-stats] origin import bundle skipped: {exc}")

    print_fn("[tool-stats] writing REPORT.md ...")
    from . import report

    report.write_report(out_root)
    print_fn(f"[tool-stats] done. outputs under {out_root}")
    return ToolStatsBuildResult(
        output_root=output_root,
        out_root=out_root,
        data_dir=data_dir,
        csv_dir=csv_dir,
        json_dir=json_dir,
        fig_dir=fig_dir,
        n_runs=len(bundle.runs),
        n_tool_calls=len(bundle.tool_calls),
        n_workflow_groups=len(bundle.workflow_groups),
        n_issues=len(bundle.issues),
    )


def run_tool_stats_bundle(
    *,
    root: str | Path | None = None,
    out: str | Path | None = None,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    scope: str = "full",
    with_plots: bool = True,
    print_fn: _StatusPrinter = print,
) -> ToolStatsBuildResult:
    out_root = _resolve(out, DEFAULT_OUT)
    requested_models = _filters(include_models)
    requested_questions = _filters(include_questions)
    requested_sections = _filters(include_sections)
    if scope not in {"full", "selection"}:
        raise ValueError(f"Unsupported tool-stats scope: {scope}")
    effective_models = requested_models if scope == "selection" else None
    effective_questions = requested_questions if scope == "selection" else None
    effective_sections = requested_sections if scope == "selection" else None
    if scope == "full" and any(value is not None for value in (requested_models, requested_questions, requested_sections)):
        print_fn("[tool-stats] scope=full: ignoring filters and rebuilding the full corpus")
    if scope == "full" and out_root.exists():
        shutil.rmtree(out_root)
    return build_tool_stats_bundle(
        root=root,
        out=out_root,
        include_models=effective_models,
        include_questions=effective_questions,
        include_sections=effective_sections,
        with_plots=with_plots,
        print_fn=print_fn,
    )


__all__ = ["DEFAULT_OUT", "ToolStatsBuildResult", "build_tool_stats_bundle", "run_tool_stats_bundle"]
