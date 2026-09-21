"""Reusable build and audit helpers for post-evaluation statistics."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ..input_support_helpers.scan import scan_outputs

from . import aggregate as agg
from . import loader as claim_loader
from .loader import (
    DEFAULT_OUTPUT_EVAL,
    iter_claim_records,
    scan_payload_extras,
    write_incomplete_csv,
    write_long_csv,
)
from .section_policy import SectionPolicy, section_matches_prefix
_WORKSPACE_ROOT = Path(__file__).absolute().parents[4]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

DEFAULT_OUT = (_QUERY_EVAL_ROOT / "_build" / "posteval_stats")
_StatusPrinter = Callable[[str], None]
_EVALUATION_ANSWER_GAP_FIELDS = [
    "model",
    "question_id",
    "section",
    "eval_mode",
    "batch",
    "gap_type",
    "reason",
    "output_result_path",
    "eval_answer_path",
    "eval_claims_path",
]


@dataclass(slots=True)
class BuildStatsResult:
    eval_root: Path
    out_root: Path
    data_dir: Path
    csv_dir: Path
    json_dir: Path
    fig_dir: Path
    n_records: int
    n_incomplete_batches: int
    n_unknown_questions: int
    n_batches_scanned: int
    models: tuple[str, ...]
    questions: tuple[str, ...]


@dataclass(slots=True)
class AuditStatsResult:
    eval_root: Path
    out_root: Path
    audit_dir: Path
    json_dir: Path
    summary: list[dict]


@dataclass(slots=True)
class StatsRunResult:
    build: BuildStatsResult
    audit: AuditStatsResult | None


def _as_path(value: str | Path | None, default: Path) -> Path:
    if value is None:
        return default
    return Path(value)


def _filter_values(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = sorted({value for value in values if value})
    return cleaned or None


def _write_load_meta(
    *,
    path: Path,
    eval_root: Path,
    out_root: Path,
    records,
    incomplete,
    unknown_questions,
    include_models: list[str] | None,
    include_questions: list[str] | None,
    include_sections: list[str] | None,
    section_policy: SectionPolicy,
) -> Path:
    batch_keys = {(rec.model, rec.question_id, rec.batch) for rec in records}
    payload = {
        "eval_root": str(eval_root),
        "out_root": str(out_root),
        "n_records": len(records),
        "n_incomplete_batches": len(incomplete),
        "n_unknown_questions": len({question_id for question_id, _ in unknown_questions}),
        "n_batches_scanned": len(batch_keys) + len(incomplete),
        "models": sorted({rec.model for rec in records}),
        "questions": sorted({rec.question_id for rec in records}),
        "filters": {
            "models": include_models,
            "questions": include_questions,
            "sections": include_sections,
        },
        "section_policy": section_policy.to_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _resolve_output_root_for_eval(eval_root: Path) -> Path:
    output_root, default_eval_root = (_QUERY_OUTPUT_ROOT, _QUERY_EVAL_ROOT)
    if eval_root == default_eval_root:
        return output_root
    sibling = eval_root.parent
    if sibling.exists():
        return sibling
    return output_root


def _write_evaluation_answer_gap_csv(
    *,
    eval_root: Path,
    output_root: Path,
    path: Path,
    include_models: list[str] | None,
    include_questions: list[str] | None,
    include_sections: list[str] | None,
) -> Path:
    registry = claim_loader.load_prompt_registry()
    model_set = set(include_models) if include_models else None
    question_set = set(include_questions) if include_questions else None
    rows: list[dict[str, object]] = []

    for run in scan_outputs([output_root]):
        if run.result_path is None:
            continue
        if model_set is not None and run.model not in model_set:
            continue
        if question_set is not None and run.question_id not in question_set:
            continue

        spec = registry.get(run.question_id)
        section = spec.section if spec else "?"
        if include_sections and not any(section_matches_prefix(section, requested) for requested in include_sections):
            continue
        eval_mode = spec.eval_mode if spec else "unknown"

        eval_dir = eval_root / f"Model_{run.model}" / run.question_id
        answer_path = eval_dir / f"answer_batch{run.batch}.md"
        claims_path = eval_dir / f"claims_batch{run.batch}.json"

        row = {
            "model": run.model,
            "question_id": run.question_id,
            "section": section,
            "eval_mode": eval_mode,
            "batch": run.batch,
            "output_result_path": str(run.result_path),
            "eval_answer_path": str(answer_path),
            "eval_claims_path": str(claims_path),
        }

        if not answer_path.exists():
            rows.append({
                **row,
                "gap_type": "missing_answer",
                "reason": "answer markdown not found",
            })
            continue

        if not claims_path.exists():
            rows.append({
                **row,
                "gap_type": "missing_claims",
                "reason": "claims json not found",
            })
            continue

        try:
            payload = json.loads(claims_path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            rows.append({
                **row,
                "gap_type": "unreadable_claims",
                "reason": f"unreadable: {exc}",
            })
            continue

        if not bool(payload.get("complete", False)):
            rows.append({
                **row,
                "gap_type": "incomplete_claims",
                "reason": "complete=false",
            })

    rows.sort(key=lambda row: (row["model"], row["question_id"], int(row["batch"]), row["gap_type"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_EVALUATION_ANSWER_GAP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_stats_bundle(
    *,
    root: str | Path | None = None,
    out: str | Path | None = None,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    include_section_4: bool = False,
    separate_section_5: bool = True,
    separate_section_1: bool = False,
    separate_section_2: bool = False,
    separate_section_3: bool = False,
    with_plots: bool = False,
    print_fn: _StatusPrinter = print,
) -> BuildStatsResult:
    eval_root = _as_path(root, DEFAULT_OUTPUT_EVAL)
    out_root = _as_path(out, DEFAULT_OUT)
    data_dir = out_root / "_data"
    csv_dir = out_root / "csv"
    json_dir = out_root / "json"
    fig_dir = out_root / "figures"
    for directory in (data_dir, csv_dir, json_dir, fig_dir):
        directory.mkdir(parents=True, exist_ok=True)

    model_filters = _filter_values(include_models)
    question_filters = _filter_values(include_questions)
    section_filters = _filter_values(include_sections)
    section_policy = SectionPolicy(
        include_section_4=include_section_4,
        separate_section_5=separate_section_5,
        separate_section_1=separate_section_1,
        separate_section_2=separate_section_2,
        separate_section_3=separate_section_3,
    )

    print_fn(f"[build] eval root: {eval_root}")
    print_fn("[build] loading claim records …")
    result = iter_claim_records(
        eval_root,
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
        section_policy=section_policy,
    )
    print_fn(
        "  records: "
        f"{len(result.records)}  incomplete: {len(result.incomplete)}  "
        f"unknown_qs: {len({question_id for question_id, _ in result.unknown_questions})}"
    )

    write_long_csv(result.records, data_dir / "claims_long.csv")
    if result.incomplete:
        write_incomplete_csv(result.incomplete, data_dir / "incomplete_batches.csv")
    if result.unknown_questions:
        with (data_dir / "unknown_questions.json").open("w", encoding="utf-8") as fh:
            json.dump(sorted({question_id for question_id, _ in result.unknown_questions}), fh, indent=2)
    _write_load_meta(
        path=data_dir / "load_meta.json",
        eval_root=eval_root,
        out_root=out_root,
        records=result.records,
        incomplete=result.incomplete,
        unknown_questions=result.unknown_questions,
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
        section_policy=section_policy,
    )

    print_fn("[build] scanning evaluation-answer gaps …")
    _write_evaluation_answer_gap_csv(
        eval_root=eval_root,
        output_root=_resolve_output_root_for_eval(eval_root),
        path=data_dir / "evaluation_answer_gaps.csv",
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
    )

    print_fn("[build] scanning payload extras (canonical_ids / tools / claim text) …")
    extras = scan_payload_extras(
        eval_root,
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
        section_policy=section_policy,
    )

    recs = result.records
    print_fn("[build] phase 2.A claim-level grouped tables …")
    agg.emit_bucket_rates(recs, csv_dir, json_dir)
    agg.emit_class_marker(recs, csv_dir, json_dir)
    agg.emit_support_by_claim_type(recs, csv_dir, json_dir)
    agg.emit_claim_type_share_by_model_major_section(recs, csv_dir, json_dir)
    agg.emit_verified_share_by_claim_type_model_major_section(recs, csv_dir, json_dir)
    agg.emit_verified_share_by_claim_type_model_major_section_matrix(recs, csv_dir, json_dir)

    print_fn("[build] phase 2.B batch-as-repeated-sample analysis …")
    summaries = agg.summarize_batches(recs, claim_texts=extras.claim_texts)
    summaries_by_key = {(summary.model, summary.question_id, summary.batch): summary for summary in summaries}
    for key, canonical_ids in extras.canonical_by_batch.items():
        if key in summaries_by_key:
            summary = summaries_by_key[key]
            summary.canonical_ids = tuple(sorted(canonical_ids))
            summary.n_canonical_unique = len(canonical_ids)

    agg.emit_batch_stability(summaries, csv_dir, json_dir)
    agg.emit_batch_outliers(summaries, csv_dir, json_dir)
    agg.emit_batch_agreement_canonical(extras.canonical_by_batch, csv_dir, json_dir)
    agg.emit_pairwise_jaccard_by_model_major_section(extras.canonical_by_batch, summaries, csv_dir, json_dir)
    agg.emit_batch_agreement_numeric(summaries, csv_dir, json_dir)
    agg.emit_coverage_saturation(extras.canonical_by_batch, csv_dir, json_dir)
    agg.emit_best_vs_worst_batch(summaries, csv_dir, json_dir)
    agg.emit_claim_count_by_batch_position(summaries, csv_dir, json_dir)

    print_fn("[build] phase 2.C cross-model & prompt-difficulty …")
    agg.emit_prompt_difficulty(summaries, csv_dir, json_dir)
    agg.emit_prompt_instability(summaries, csv_dir, json_dir)
    agg.emit_cross_model_rank_correlation(summaries, csv_dir, json_dir)
    agg.emit_cross_model_agreement_canonical(extras.canonical_by_batch, csv_dir, json_dir)

    print_fn("[build] phase 2.D eval-mode profile …")
    agg.emit_eval_mode_profile(recs, csv_dir, json_dir)

    print_fn("[build] phase 2.E position & verbosity …")
    agg.emit_position_effects(recs, csv_dir, json_dir)
    agg.emit_verbosity(recs, csv_dir, json_dir)

    print_fn("[build] phase 2.F + 2.G tool & canonical-ID stats …")
    agg.emit_tool_usage(extras.tools_by_model_mode, csv_dir, json_dir)
    agg.emit_tools_per_support_class(recs, csv_dir, json_dir)
    agg.emit_canonical_id_frequency(extras.canonical_by_batch, csv_dir, json_dir)
    agg.emit_prompt_evidence_breadth(extras.canonical_by_batch, csv_dir, json_dir)

    if with_plots:
        try:
            from . import plots

            print_fn("[build] phase 3 plots …")
            plots.render_all(csv_dir, fig_dir)
        except Exception as exc:  # noqa: BLE001
            print_fn(f"[build] plots skipped: {exc}")

    try:
        from . import origin_export

        print_fn("[build] preparing Origin import bundle …")
        origin_export.populate_origin_import(csv_dir=csv_dir, out_root=out_root)
    except Exception as exc:  # noqa: BLE001
        print_fn(f"[build] origin import bundle skipped: {exc}")

    print_fn("[build] writing REPORT.md …")
    from . import report

    report.write_report(out_root)
    print_fn(f"[build] done. outputs under {out_root}")
    return BuildStatsResult(
        eval_root=eval_root,
        out_root=out_root,
        data_dir=data_dir,
        csv_dir=csv_dir,
        json_dir=json_dir,
        fig_dir=fig_dir,
        n_records=len(result.records),
        n_incomplete_batches=len(result.incomplete),
        n_unknown_questions=len({question_id for question_id, _ in result.unknown_questions}),
        n_batches_scanned=len({(rec.model, rec.question_id, rec.batch) for rec in result.records}) + len(result.incomplete),
        models=tuple(sorted({rec.model for rec in result.records})),
        questions=tuple(sorted({rec.question_id for rec in result.records})),
    )


def audit_stats_bundle(
    *,
    root: str | Path | None = None,
    out: str | Path | None = None,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    include_section_4: bool = False,
    separate_section_5: bool = True,
    separate_section_1: bool = False,
    separate_section_2: bool = False,
    separate_section_3: bool = False,
    print_fn: _StatusPrinter = print,
) -> AuditStatsResult:
    from . import revalidate, report

    eval_root = _as_path(root, DEFAULT_OUTPUT_EVAL)
    out_root = _as_path(out, DEFAULT_OUT)
    audit_dir = out_root / "audit"
    json_dir = out_root / "json"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    model_filters = _filter_values(include_models)
    question_filters = _filter_values(include_questions)
    section_filters = _filter_values(include_sections)
    section_policy = SectionPolicy(
        include_section_4=include_section_4,
        separate_section_5=separate_section_5,
        separate_section_1=separate_section_1,
        separate_section_2=separate_section_2,
        separate_section_3=separate_section_3,
    )

    print_fn(f"[audit] eval root: {eval_root}")
    summary = revalidate.run_audits(
        root=eval_root,
        out_dir=audit_dir,
        json_dir=json_dir,
        include_models=model_filters,
        include_questions=question_filters,
        include_sections=section_filters,
        section_policy=section_policy,
    )
    print_fn("[audit] summary:")
    for row in summary:
        print_fn(
            f"  {row['audit']:<35} checked={row['total_checked']:>6}  "
            f"flagged={row['total_flagged']:>5}  rate={row['flag_rate']:.3f}"
        )
    report.write_report(out_root)
    return AuditStatsResult(
        eval_root=eval_root,
        out_root=out_root,
        audit_dir=audit_dir,
        json_dir=json_dir,
        summary=summary,
    )


def run_stats_bundle(
    *,
    root: str | Path | None = None,
    out: str | Path | None = None,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    include_section_4: bool = False,
    separate_section_5: bool = True,
    separate_section_1: bool = False,
    separate_section_2: bool = False,
    separate_section_3: bool = False,
    with_plots: bool = False,
    with_audit: bool = False,
    print_fn: _StatusPrinter = print,
) -> StatsRunResult:
    build = build_stats_bundle(
        root=root,
        out=out,
        include_models=include_models,
        include_questions=include_questions,
        include_sections=include_sections,
        include_section_4=include_section_4,
        separate_section_5=separate_section_5,
        separate_section_1=separate_section_1,
        separate_section_2=separate_section_2,
        separate_section_3=separate_section_3,
        with_plots=with_plots,
        print_fn=print_fn,
    )
    audit = None
    if with_audit:
        audit = audit_stats_bundle(
            root=root,
            out=out,
            include_models=include_models,
            include_questions=include_questions,
            include_sections=include_sections,
            include_section_4=include_section_4,
            separate_section_5=separate_section_5,
            separate_section_1=separate_section_1,
            separate_section_2=separate_section_2,
            separate_section_3=separate_section_3,
            print_fn=print_fn,
        )
    return StatsRunResult(build=build, audit=audit)


__all__ = [
    "AuditStatsResult",
    "BuildStatsResult",
    "DEFAULT_OUT",
    "StatsRunResult",
    "audit_stats_bundle",
    "build_stats_bundle",
    "run_stats_bundle",
]
