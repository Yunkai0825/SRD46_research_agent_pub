"""Publish canonical post-evaluation outputs into `_output_eval/Eval_Stats`."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .input_support_helpers.scan import REPO_ROOT
from .posteval_stats.pipeline import audit_stats_bundle, build_stats_bundle
from .posteval_stats.section_policy import SectionPolicy
_WORKSPACE_ROOT = Path(__file__).absolute().parents[3]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

DEFAULT_EVAL_ROOT = _QUERY_EVAL_ROOT
DEFAULT_STATS_ROOT = (_QUERY_EVAL_ROOT / "Eval_Stats")
BUILD_SUBPATH = Path("_build") / "posteval_stats"
MANIFEST_SUBPATH = Path("_build") / "orchestrator_manifest.json"
SUPPORT_CLASS_KEYS = ("direct", "inferred", "domain_knowledge", "unsupported", "no_tool_data")
BUCKET_KEYS = ("verified", "domain", "unverified", "filler")
_StatusPrinter = Callable[[str], None]


@dataclass(slots=True)
class PublishResult:
	eval_root: Path
	stats_root: Path
	build_root: Path
	manifest_path: Path
	n_published_pairs: int
	scope: str


def _resolve_root(path: str | Path | None, default: Path) -> Path:
	if path is None:
		return default
	resolved = Path(path)
	if not resolved.is_absolute():
		resolved = REPO_ROOT / resolved
	return resolved


def _filters(values: Iterable[str] | None) -> list[str] | None:
	if values is None:
		return None
	cleaned = sorted({value for value in values if value})
	return cleaned or None


def _reset_dir(path: Path) -> None:
	if path.exists():
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def _read_csv(path: Path) -> list[dict[str, str]]:
	if not path.exists():
		return []
	with path.open("r", encoding="utf-8", newline="") as fh:
		return list(csv.DictReader(fh))


def _to_int(value: str | None) -> int | None:
	if value in {None, ""}:
		return None
	try:
		return int(float(value))
	except (TypeError, ValueError):
		return None


def _to_float(value: str | None) -> float | None:
	if value in {None, ""}:
		return None
	try:
		parsed = float(value)
	except (TypeError, ValueError):
		return None
	if parsed != parsed:
		return None
	return parsed


def _index_by_pair(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
	return {(row["model"], row["question_id"]): row for row in rows}


def _group_by_pair(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
	grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
	for row in rows:
		key = (row["model"], row["question_id"])
		grouped.setdefault(key, []).append(row)
	return grouped


def _bucket_summary(row: dict[str, str]) -> dict[str, object]:
	summary: dict[str, object] = {
		"n_claims": _to_int(row.get("n_claims")),
		"n_nonfiller": _to_int(row.get("n_nonfiller")),
		"n_batches": _to_int(row.get("n_batches")),
		"filler_share": _to_float(row.get("filler_share")),
	}
	for bucket in ("verified", "domain", "unverified"):
		summary[bucket] = {
			"count": _to_int(row.get(f"{bucket}_count")),
			"share": _to_float(row.get(f"{bucket}_share")),
			"ci_lo": _to_float(row.get(f"{bucket}_ci_lo")),
			"ci_hi": _to_float(row.get(f"{bucket}_ci_hi")),
		}
	return summary


def _claim_type_bucket_rows(rows: list[dict[str, str]]) -> tuple[dict[str, int], list[dict[str, object]]]:
	claim_type_counts: dict[str, int] = {}
	matrix: list[dict[str, object]] = []
	for row in sorted(rows, key=lambda item: item["claim_type"]):
		claim_type = row["claim_type"]
		row_total = _to_int(row.get("row_total")) or 0
		claim_type_counts[claim_type] = row_total
		matrix.append(
			{
				"claim_type": claim_type,
				"row_total": row_total,
				"bucket_counts": {
					f"{bucket}_count": _to_int(row.get(f"{bucket}_count")) or 0
					for bucket in BUCKET_KEYS
				},
				"bucket_shares": {
					f"{bucket}_share": _to_float(row.get(f"{bucket}_share")) or 0.0
					for bucket in BUCKET_KEYS
				},
			}
		)
	return claim_type_counts, matrix


def _claim_type_support_rows(rows: list[dict[str, str]]) -> tuple[dict[str, int], list[dict[str, object]]]:
	support_totals = {key: 0 for key in SUPPORT_CLASS_KEYS}
	matrix: list[dict[str, object]] = []
	for row in sorted(rows, key=lambda item: item["claim_type"]):
		support_counts = {key: _to_int(row.get(key)) or 0 for key in SUPPORT_CLASS_KEYS}
		for key, value in support_counts.items():
			support_totals[key] += value
		matrix.append(
			{
				"claim_type": row["claim_type"],
				"row_total": _to_int(row.get("row_total")) or 0,
				"support_class_counts": support_counts,
			}
		)
	return support_totals, matrix


def _clean_row(row: dict[str, str] | None) -> dict[str, object] | None:
	if row is None:
		return None
	cleaned: dict[str, object] = {}
	for key, value in row.items():
		if value == "":
			cleaned[key] = None
			continue
		parsed_int = _to_int(value)
		if parsed_int is not None and str(parsed_int) == value:
			cleaned[key] = parsed_int
			continue
		parsed_float = _to_float(value)
		if parsed_float is not None:
			cleaned[key] = parsed_float
			continue
		cleaned[key] = value
	return cleaned


def _relative_to_stats_root(path: Path, stats_root: Path) -> str:
	return path.relative_to(stats_root).as_posix()


def _payload_paths(stats_root: Path, build_root: Path) -> dict[str, object]:
	return {
		"relative_to_stats_root": {
			"build_root": _relative_to_stats_root(build_root, stats_root),
			"report": _relative_to_stats_root(build_root / "REPORT.md", stats_root),
			"csv_dir": _relative_to_stats_root(build_root / "csv", stats_root),
			"json_dir": _relative_to_stats_root(build_root / "json", stats_root),
			"figures_dir": _relative_to_stats_root(build_root / "figures", stats_root),
			"audit_dir": _relative_to_stats_root(build_root / "audit", stats_root),
			"bucket_rates_by_model_prompt": _relative_to_stats_root(build_root / "csv" / "bucket_rates_by_model_prompt.csv", stats_root),
			"support_by_claim_type_model_prompt": _relative_to_stats_root(build_root / "csv" / "support_by_claim_type_model_prompt.csv", stats_root),
			"class_marker_model_prompt": _relative_to_stats_root(build_root / "csv" / "class_marker_model_prompt.csv", stats_root),
			"batch_stability": _relative_to_stats_root(build_root / "csv" / "batch_stability.csv", stats_root),
			"prompt_evidence_breadth": _relative_to_stats_root(build_root / "csv" / "prompt_evidence_breadth.csv", stats_root),
			"batch_agreement_canonical": _relative_to_stats_root(build_root / "csv" / "batch_agreement_canonical.csv", stats_root),
			"batch_agreement_numeric": _relative_to_stats_root(build_root / "csv" / "batch_agreement_numeric.csv", stats_root),
			"best_vs_worst_batch": _relative_to_stats_root(build_root / "csv" / "best_vs_worst_batch.csv", stats_root),
		}
	}


def _build_pair_payloads(build_root: Path, stats_root: Path) -> list[tuple[str, str, dict[str, object]]]:
	csv_root = build_root / "csv"
	bucket_rows = _read_csv(csv_root / "bucket_rates_by_model_prompt.csv")
	support_rows = _group_by_pair(_read_csv(csv_root / "support_by_claim_type_model_prompt.csv"))
	class_rows = _group_by_pair(_read_csv(csv_root / "class_marker_model_prompt.csv"))
	stability_rows = _index_by_pair(_read_csv(csv_root / "batch_stability.csv"))
	breadth_rows = _index_by_pair(_read_csv(csv_root / "prompt_evidence_breadth.csv"))
	canonical_rows = _index_by_pair(_read_csv(csv_root / "batch_agreement_canonical.csv"))
	numeric_rows = _index_by_pair(_read_csv(csv_root / "batch_agreement_numeric.csv"))
	best_rows = _index_by_pair(_read_csv(csv_root / "best_vs_worst_batch.csv"))
	common_paths = _payload_paths(stats_root, build_root)

	payloads: list[tuple[str, str, dict[str, object]]] = []
	for bucket_row in sorted(bucket_rows, key=lambda row: (row["model"], row["question_id"])):
		model = bucket_row["model"]
		question_id = bucket_row["question_id"]
		key = (model, question_id)
		claim_type_counts, claim_type_bucket_matrix = _claim_type_bucket_rows(support_rows.get(key, []))
		support_class_counts, claim_type_support_matrix = _claim_type_support_rows(class_rows.get(key, []))
		payloads.append(
			(
				model,
				question_id,
				{
					"model": model,
					"question_id": question_id,
					"section": bucket_row.get("section"),
					"eval_mode": bucket_row.get("eval_mode"),
					"coverage": {
						**_bucket_summary(bucket_row),
						"n_unique_canonical_ids": _to_int((breadth_rows.get(key) or {}).get("n_unique_canonical_ids")),
					},
					"claim_type_counts": claim_type_counts,
					"support_class_counts": support_class_counts,
					"claim_type_bucket_matrix": claim_type_bucket_matrix,
					"claim_type_support_matrix": claim_type_support_matrix,
					"batch_summary": {
						"stability": _clean_row(stability_rows.get(key)),
						"canonical_agreement": _clean_row(canonical_rows.get(key)),
						"numeric_agreement": _clean_row(numeric_rows.get(key)),
						"best_vs_worst": _clean_row(best_rows.get(key)),
					},
					"paths": common_paths,
				},
			)
		)
	return payloads


def _write_payload(path: Path, payload: dict[str, object]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _publish_views(
	*,
	build_root: Path,
	stats_root: Path,
	scope: str,
	print_fn: _StatusPrinter,
) -> list[dict[str, str]]:
	model_root = stats_root / "Model_prompt_question"
	prompt_root = stats_root / "Prompt_model_question"
	if scope == "full":
		_reset_dir(model_root)
		_reset_dir(prompt_root)
	else:
		model_root.mkdir(parents=True, exist_ok=True)
		prompt_root.mkdir(parents=True, exist_ok=True)

	published_pairs: list[dict[str, str]] = []
	for model, question_id, payload in _build_pair_payloads(build_root, stats_root):
		model_path = model_root / f"Model_{model}" / question_id / "stats.json"
		prompt_path = prompt_root / question_id / f"Model_{model}" / "stats.json"
		_write_payload(model_path, payload)
		_write_payload(prompt_path, payload)
		published_pairs.append({"model": model, "question_id": question_id})

	print_fn(f"[publish] materialized {len(published_pairs)} model/question summaries")
	return published_pairs


def run_publish(
	*,
	eval_root: str | Path | None = None,
	stats_root: str | Path | None = None,
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
	scope: str = "full",
	print_fn: _StatusPrinter = print,
) -> PublishResult:
	resolved_eval_root = _resolve_root(eval_root, DEFAULT_EVAL_ROOT)
	resolved_stats_root = _resolve_root(stats_root, DEFAULT_STATS_ROOT)
	build_root = resolved_stats_root / BUILD_SUBPATH
	manifest_path = resolved_stats_root / MANIFEST_SUBPATH

	requested_models = _filters(include_models)
	requested_questions = _filters(include_questions)
	requested_sections = _filters(include_sections)
	section_policy = SectionPolicy(
		include_section_4=include_section_4,
		separate_section_5=separate_section_5,
		separate_section_1=separate_section_1,
		separate_section_2=separate_section_2,
		separate_section_3=separate_section_3,
	)
	if scope not in {"full", "selection"}:
		raise ValueError(f"Unsupported publish scope: {scope}")

	effective_models = requested_models if scope == "selection" else None
	effective_questions = requested_questions if scope == "selection" else None
	effective_sections = requested_sections if scope == "selection" else None

	if scope == "full" and any(value is not None for value in (requested_models, requested_questions, requested_sections)):
		print_fn("[publish] scope=full: ignoring model/question/section filters and rebuilding the full eval corpus")

	resolved_stats_root.mkdir(parents=True, exist_ok=True)
	if scope == "full" and build_root.exists():
		shutil.rmtree(build_root)

	print_fn(f"[publish] eval root: {resolved_eval_root}")
	print_fn(f"[publish] stats root: {resolved_stats_root}")
	build_result = build_stats_bundle(
		root=resolved_eval_root,
		out=build_root,
		include_models=effective_models,
		include_questions=effective_questions,
		include_sections=effective_sections,
		include_section_4=include_section_4,
		separate_section_5=separate_section_5,
		separate_section_1=separate_section_1,
		separate_section_2=separate_section_2,
		separate_section_3=separate_section_3,
		with_plots=with_plots,
		print_fn=print_fn,
	)
	if with_audit:
		audit_stats_bundle(
			root=resolved_eval_root,
			out=build_root,
			include_models=effective_models,
			include_questions=effective_questions,
			include_sections=effective_sections,
			include_section_4=include_section_4,
			separate_section_5=separate_section_5,
			separate_section_1=separate_section_1,
			separate_section_2=separate_section_2,
			separate_section_3=separate_section_3,
			print_fn=print_fn,
		)

	published_pairs = _publish_views(
		build_root=build_result.out_root,
		stats_root=resolved_stats_root,
		scope=scope,
		print_fn=print_fn,
	)

	manifest_path.parent.mkdir(parents=True, exist_ok=True)
	manifest = {
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"eval_root": str(resolved_eval_root),
		"stats_root": str(resolved_stats_root),
		"scope": scope,
		"requested_filters": {
			"models": requested_models,
			"questions": requested_questions,
			"sections": requested_sections,
		},
		"effective_filters": {
			"models": effective_models,
			"questions": effective_questions,
			"sections": effective_sections,
		},
		"section_policy": section_policy.to_dict(),
		"with_plots": with_plots,
		"with_audit": with_audit,
		"build_root": _relative_to_stats_root(build_result.out_root, resolved_stats_root),
		"n_records": build_result.n_records,
		"n_batches_scanned": build_result.n_batches_scanned,
		"n_models": len(build_result.models),
		"n_questions": len(build_result.questions),
		"n_published_pairs": len(published_pairs),
		"published_pairs": published_pairs,
	}
	manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
	print_fn(f"[publish] wrote manifest: {manifest_path}")
	return PublishResult(
		eval_root=resolved_eval_root,
		stats_root=resolved_stats_root,
		build_root=build_result.out_root,
		manifest_path=manifest_path,
		n_published_pairs=len(published_pairs),
		scope=scope,
	)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="python -m SRD46_query_output_eval_pipeline.posteval_stats_orchestrator",
		description="Build posteval stats and publish canonical Eval_Stats browse views.",
	)
	parser.add_argument("--eval-root", default=str(DEFAULT_EVAL_ROOT), help="Eval artifact root (default: repository-local query eval root)")
	parser.add_argument("--stats-root", default=str(DEFAULT_STATS_ROOT), help="Published Eval_Stats root (default: repository-local query Eval_Stats root)")
	parser.add_argument("--models", action="append", help="Restrict to model name (selection scope only).")
	parser.add_argument("--questions", action="append", help="Restrict to question id (selection scope only).")
	parser.add_argument("--sections", action="append", help="Restrict to section prefix (selection scope only).")
	parser.add_argument("--include-section-4", action="store_true", help="Include section 4 prompts in the stats scope.")
	parser.add_argument("--merge-section-5", action="store_true", help="Pool sections 5.1 and 5.2 into section 5.")
	parser.add_argument("--separate-section-1", action="store_true", help="Keep sections 1.1 and 1.2 separate.")
	parser.add_argument("--separate-section-2", action="store_true", help="Keep sections 2.1 and 2.2 separate.")
	parser.add_argument("--separate-section-3", action="store_true", help="Keep sections 3.1 and 3.2 separate.")
	parser.add_argument("--with-plots", action="store_true", help="Render PNG charts into the canonical build output.")
	parser.add_argument("--with-audit", action="store_true", help="Run posteval audits after the stats build.")
	parser.add_argument(
		"--scope",
		choices=("full", "selection"),
		default="full",
		help="`full` rebuilds the full corpus into the canonical root; `selection` publishes only filtered slices.",
	)
	return parser


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	run_publish(
		eval_root=args.eval_root,
		stats_root=args.stats_root,
		include_models=args.models,
		include_questions=args.questions,
		include_sections=args.sections,
		include_section_4=args.include_section_4,
		separate_section_5=not args.merge_section_5,
		separate_section_1=args.separate_section_1,
		separate_section_2=args.separate_section_2,
		separate_section_3=args.separate_section_3,
		with_plots=args.with_plots,
		with_audit=args.with_audit,
		scope=args.scope,
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())


__all__ = [
	"BUILD_SUBPATH",
	"DEFAULT_EVAL_ROOT",
	"DEFAULT_STATS_ROOT",
	"MANIFEST_SUBPATH",
	"PublishResult",
	"build_parser",
	"main",
	"run_publish",
]
