"""Batch orchestrator for the regex-enricher claim-evaluation pipeline.

Run::

	python -m SRD46_query_output_eval_pipeline.regex_enricher_orchestrator --model gpt5 --question Q1.1.1 --workers 1 --force
"""
from __future__ import annotations

import argparse
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .input_support_helpers.extract_tool_results import extract_run
from .input_support_helpers.scan import DEFAULT_OUTPUT_ROOT, REPO_ROOT, scan_outputs
from .models import RunArtifacts
from .posteval_stats_orchestrator import DEFAULT_STATS_ROOT, run_publish
from .regex_enricher.enricher import enrich_run_claims
from .regex_enricher.validation import write_validation, write_validation_summary
from .tool_stats.pipeline import DEFAULT_OUT as DEFAULT_TOOL_STATS_ROOT, run_tool_stats_bundle
_WORKSPACE_ROOT = Path(__file__).absolute().parents[3]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

log = logging.getLogger("regex_enricher_orchestrator")

DEFAULT_EVAL_ROOT = _QUERY_EVAL_ROOT
_VALIDATION_SUMMARY_LOCK = threading.Lock()
_StatusPrinter = Callable[[str], None]


def _resolve_root(path: str | Path) -> Path:
	resolved = Path(path)
	if not resolved.is_absolute():
		resolved = REPO_ROOT / resolved
	return resolved


def _qid_sort_key(question_id: str) -> tuple[int, ...]:
	return tuple(int(part) for part in re.findall(r"\d+", question_id))


def _coerce_positive_int(value: int | None, fallback: int) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		parsed = fallback
	return max(1, parsed)


def _normalize_batches(
	batches: int | str | list[int | str] | tuple[int | str, ...] | None,
) -> tuple[int, ...] | None:
	if batches is None:
		return None
	if isinstance(batches, (int, str)):
		raw_values: list[int | str] = [batches]
	else:
		raw_values = list(batches)

	parsed: set[int] = set()
	for raw in raw_values:
		parts = str(raw).split(",") if isinstance(raw, str) else [raw]
		for part in parts:
			text = str(part).strip()
			if not text:
				continue
			if text.lower().startswith("batch"):
				text = text[5:]
			parsed.add(int(text))

	return tuple(sorted(parsed)) if parsed else None


def _resolve_argo_parallelism(
	*,
	workers: int,
	claim_paragraph_workers: int | None,
	argo_http_workers: int | None,
) -> tuple[int, int]:
	from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config

	outer_workers = _coerce_positive_int(workers, 1)
	configured_claim_workers = _coerce_positive_int(
		getattr(argo_config, "CLAIM_PARAGRAPH_WORKERS", outer_workers),
		outer_workers,
	)
	configured_http_workers = _coerce_positive_int(
		getattr(argo_config, "ARGO_MAX_CONCURRENT_REQUESTS", outer_workers),
		outer_workers,
	)
	resolved_claim_workers = _coerce_positive_int(
		claim_paragraph_workers,
		min(configured_claim_workers, outer_workers),
	)
	resolved_http_workers = _coerce_positive_int(
		argo_http_workers,
		min(configured_http_workers, outer_workers),
	)
	return resolved_claim_workers, resolved_http_workers


def _apply_argo_parallelism(
	*,
	workers: int,
	claim_paragraph_workers: int | None,
	argo_http_workers: int | None,
) -> tuple[int, int, int, int]:
	from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config
	from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import configure_argo_request_limit, get_argo_request_limit

	previous_claim_workers = _coerce_positive_int(
		getattr(argo_config, "CLAIM_PARAGRAPH_WORKERS", workers),
		workers,
	)
	previous_http_workers = get_argo_request_limit()
	resolved_claim_workers, resolved_http_workers = _resolve_argo_parallelism(
		workers=workers,
		claim_paragraph_workers=claim_paragraph_workers,
		argo_http_workers=argo_http_workers,
	)
	argo_config.CLAIM_PARAGRAPH_WORKERS = resolved_claim_workers
	configure_argo_request_limit(resolved_http_workers)
	return (
		previous_claim_workers,
		previous_http_workers,
		resolved_claim_workers,
		resolved_http_workers,
	)


def _restore_argo_parallelism(previous_claim_workers: int, previous_http_workers: int) -> None:
	from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config
	from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import configure_argo_request_limit

	argo_config.CLAIM_PARAGRAPH_WORKERS = previous_claim_workers
	configure_argo_request_limit(previous_http_workers)


def configure_logging(*, verbose: bool = True, logfile: str | Path | None = None) -> None:
	handlers: list[logging.Handler] = [logging.StreamHandler()]
	if logfile:
		file_handler = logging.FileHandler(logfile, encoding="utf-8")
		file_handler.setLevel(logging.DEBUG)
		handlers.append(file_handler)

	logging.basicConfig(
		level=logging.DEBUG if verbose else logging.INFO,
		format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
		handlers=handlers,
		force=True,
	)


def discover_runs(
	*,
	output_root: str | Path = DEFAULT_OUTPUT_ROOT,
	model: str | None = None,
	question: str | None = None,
	batches: int | str | list[int | str] | tuple[int | str, ...] | None = None,
) -> list[RunArtifacts]:
	resolved_output_root = _resolve_root(output_root)
	runs = scan_outputs([resolved_output_root])
	if model:
		runs = [run for run in runs if run.model == model]
	if question:
		runs = [run for run in runs if run.question_id == question]
	batch_filter = _normalize_batches(batches)
	if batch_filter:
		allowed_batches = set(batch_filter)
		runs = [run for run in runs if run.batch in allowed_batches]
	return sorted(runs, key=lambda run: (run.batch, _qid_sort_key(run.question_id), run.model))


def _extract_one(run: RunArtifacts, *, output_root: Path, eval_root: Path) -> str:
	written = extract_run(run.model, run.question_id, run.batch, output_root=output_root, eval_root=eval_root)
	return f"extract {run.model}/{run.question_id}/batch{run.batch}: {len(written)} files"


def _process_one(run: RunArtifacts, *, output_root: Path, eval_root: Path, force: bool) -> str:
	doc = enrich_run_claims(
		model=run.model,
		question_id=run.question_id,
		batch=run.batch,
		output_root=output_root,
		eval_root=eval_root,
		use_cache=not force,
	)
	if doc is None:
		return f"SKIP {run.model}/{run.question_id}/batch{run.batch}: no answer found"

	total = sum(len(paragraph.claims) for paragraph in doc.paragraphs)
	unsupported = sum(
		1
		for paragraph in doc.paragraphs
		for grounded in paragraph.grounded_claims
		if grounded.support_class == "unsupported"
	)

	write_validation(doc, run.model, run.question_id, run.batch, eval_root)
	with _VALIDATION_SUMMARY_LOCK:
		write_validation_summary(run.model, eval_root)

	return (
		f"OK {run.model}/{run.question_id}/batch{run.batch}: "
		f"{total} claims, {unsupported} unsupported"
	)


def _run_extract_phase(
	runs: list[RunArtifacts],
	*,
	workers: int,
	output_root: Path,
	eval_root: Path,
	verbose: bool,
	print_fn: _StatusPrinter,
) -> int:
	print_fn("\n-- Phase 1: Extracting tool results --")
	with ThreadPoolExecutor(max_workers=min(workers, 8)) as pool:
		futures = {pool.submit(_extract_one, run, output_root=output_root, eval_root=eval_root): run for run in runs}
		done = 0
		for future in as_completed(futures):
			done += 1
			try:
				message = future.result()
				if verbose:
					print_fn(f"  [{done}/{len(runs)}] {message}")
			except Exception as exc:  # noqa: BLE001
				run = futures[future]
				print_fn(f"  [{done}/{len(runs)}] ERROR {run.model}/{run.question_id}/batch{run.batch}: {exc}")
	print_fn(f"Extraction complete: {done} runs.")
	return done


def _run_claim_phase(
	runs: list[RunArtifacts],
	*,
	workers: int,
	output_root: Path,
	eval_root: Path,
	force: bool,
	print_fn: _StatusPrinter,
) -> int:
	print_fn(f"\n-- Phase 2+3: Claim classification + grounding (workers={workers}) --")
	started_at = time.time()
	with ThreadPoolExecutor(max_workers=workers) as pool:
		futures = {
			pool.submit(_process_one, run, output_root=output_root, eval_root=eval_root, force=force): run
			for run in runs
		}
		done = 0
		for future in as_completed(futures):
			done += 1
			elapsed = time.time() - started_at
			try:
				message = future.result()
				print_fn(f"  [{done}/{len(runs)}] ({elapsed:.1f}s) {message}")
			except Exception as exc:  # noqa: BLE001
				run = futures[future]
				print_fn(
					f"  [{done}/{len(runs)}] ({elapsed:.1f}s) "
					f"ERROR {run.model}/{run.question_id}/batch{run.batch}: {exc}"
				)

	total_elapsed = time.time() - started_at
	print_fn(f"Classification + grounding complete: {done} runs in {total_elapsed:.1f}s")
	return done


def _run_summary_phase(runs: list[RunArtifacts], *, eval_root: Path, print_fn: _StatusPrinter) -> None:
	print_fn("\n-- Phase 4: Validation summaries --")
	models_processed = {run.model for run in runs}
	for model in sorted(models_processed):
		path = write_validation_summary(model, eval_root)
		if path:
			print_fn(f"  Summary: {path}")
		else:
			print_fn(f"  {model}: no unsupported claims found (or no validation files)")


def run_pipeline(
	*,
	model: str | None = None,
	question: str | None = None,
	batches: int | str | list[int | str] | tuple[int | str, ...] | None = None,
	workers: int = 20,
	claim_paragraph_workers: int | None = None,
	argo_http_workers: int | None = None,
	force: bool = False,
	extract_only: bool = False,
	publish_eval_stats: bool = False,
	publish_tool_stats: bool = False,
	posteval_with_plots: bool = False,
	posteval_with_audit: bool = False,
	posteval_scope: str = "full",
	tool_stats_scope: str = "full",
	verbose: bool = True,
	output_root: str | Path = DEFAULT_OUTPUT_ROOT,
	eval_root: str | Path = DEFAULT_EVAL_ROOT,
	stats_root: str | Path = DEFAULT_STATS_ROOT,
	tool_stats_root: str | Path = DEFAULT_TOOL_STATS_ROOT,
	print_fn: _StatusPrinter = print,
) -> int:
	resolved_output_root = _resolve_root(output_root)
	resolved_eval_root = _resolve_root(eval_root)
	resolved_stats_root = _resolve_root(stats_root)
	resolved_tool_stats_root = _resolve_root(tool_stats_root)
	previous_claim_workers = previous_http_workers = None
	resolved_claim_workers = resolved_http_workers = None
	runs = discover_runs(
		output_root=resolved_output_root,
		model=model,
		question=question,
		batches=batches,
	)

	if not runs:
		print_fn("No matching runs found.")
		return 0

	(
		previous_claim_workers,
		previous_http_workers,
		resolved_claim_workers,
		resolved_http_workers,
	) = _apply_argo_parallelism(
		workers=workers,
		claim_paragraph_workers=claim_paragraph_workers,
		argo_http_workers=argo_http_workers,
	)

	try:
		print_fn(f"Found {len(runs)} runs to process.")
		print_fn(
			"Configured Argo parallelism: "
			f"batch_workers={workers}, "
			f"claim_paragraph_workers={resolved_claim_workers}, "
			f"argo_http_workers={resolved_http_workers}"
		)
		_run_extract_phase(
			runs,
			workers=workers,
			output_root=resolved_output_root,
			eval_root=resolved_eval_root,
			verbose=verbose,
			print_fn=print_fn,
		)

		if extract_only:
			print_fn("--extract-only: stopping after extraction.")
			return 0

		_run_claim_phase(
			runs,
			workers=workers,
			output_root=resolved_output_root,
			eval_root=resolved_eval_root,
			force=force,
			print_fn=print_fn,
		)
		_run_summary_phase(runs, eval_root=resolved_eval_root, print_fn=print_fn)
		if publish_eval_stats:
			print_fn("\n-- Phase 5: Publish Eval_Stats --")
			publish_result = run_publish(
				eval_root=resolved_eval_root,
				stats_root=resolved_stats_root,
				include_models=[model] if model else None,
				include_questions=[question] if question else None,
				with_plots=posteval_with_plots,
				with_audit=posteval_with_audit,
				scope=posteval_scope,
				print_fn=print_fn,
			)
			print_fn(
				f"Published {publish_result.n_published_pairs} model/question summaries "
				f"under {publish_result.stats_root}"
			)
		if publish_tool_stats:
			print_fn("\n-- Phase 6: Publish Tool Statistics --")
			tool_stats_result = run_tool_stats_bundle(
				root=resolved_output_root,
				out=resolved_tool_stats_root,
				include_models=[model] if model else None,
				include_questions=[question] if question else None,
				scope=tool_stats_scope,
				print_fn=print_fn,
			)
			print_fn(
				f"Published tool statistics for {tool_stats_result.n_runs} runs "
				f"and {tool_stats_result.n_tool_calls} tool calls under {tool_stats_result.out_root}"
			)
		print_fn("\nDone.")
		return 0
	finally:
		if previous_claim_workers is not None and previous_http_workers is not None:
			_restore_argo_parallelism(previous_claim_workers, previous_http_workers)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="python -m SRD46_query_output_eval_pipeline.regex_enricher_orchestrator",
		description="Batch claim evaluation pipeline.",
	)
	parser.add_argument("--model", help="Filter to a specific model name")
	parser.add_argument("--question", help="Filter to a specific question ID")
	parser.add_argument(
		"--batch",
		dest="batches",
		action="append",
		help="Filter to specific batch number(s); repeat or use comma-separated values",
	)
	parser.add_argument("--workers", type=int, default=20, help="Thread pool size (default: 20)")
	parser.add_argument(
		"--claim-paragraph-workers",
		type=int,
		default=None,
		help="Per-answer classifier/grounder paragraph workers (defaults to min(config, --workers))",
	)
	parser.add_argument(
		"--argo-http-workers",
		type=int,
		default=None,
		help="Process-wide concurrent Argo HTTP requests (defaults to min(config, --workers))",
	)
	parser.add_argument("--force", action="store_true", help="Ignore cache, re-run all")
	parser.add_argument("--extract-only", action="store_true", help="Only extract tool results (no API calls)")
	parser.add_argument("--publish-eval-stats", action="store_true", help="Publish canonical posteval outputs into Eval_Stats after claim evaluation")
	parser.add_argument("--publish-tool-stats", action="store_true", help="Publish canonical tool statistics after claim evaluation")
	parser.add_argument("--posteval-with-plots", action="store_true", help="Render plots during Eval_Stats publication")
	parser.add_argument("--posteval-with-audit", action="store_true", help="Run posteval audits during Eval_Stats publication")
	parser.add_argument(
		"--posteval-scope",
		choices=("full", "selection"),
		default="full",
		help="Eval_Stats publication scope (default: full)",
	)
	parser.add_argument(
		"--tool-stats-scope",
		choices=("full", "selection"),
		default="full",
		help="Tool statistics publication scope (default: full)",
	)
	parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Run artifact root (default: repository-local query output root)")
	parser.add_argument("--eval-root", default=str(DEFAULT_EVAL_ROOT), help="Eval artifact root (default: repository-local query eval root)")
	parser.add_argument("--stats-root", default=str(DEFAULT_STATS_ROOT), help="Published Eval_Stats root (default: repository-local query Eval_Stats root)")
	parser.add_argument("--tool-stats-root", default=str(DEFAULT_TOOL_STATS_ROOT), help="Published tool-stats root (default: repository-local query tool stats root)")
	parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging (default: on)")
	parser.add_argument("--quiet", dest="verbose", action="store_false", help="Reduce logging to INFO level")
	parser.add_argument("--logfile", default="batch_claim_eval.log", help="Write logs to file")
	parser.set_defaults(verbose=True)
	return parser


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	configure_logging(verbose=args.verbose, logfile=args.logfile)
	return run_pipeline(
		model=args.model,
		question=args.question,
		batches=args.batches,
		workers=args.workers,
		claim_paragraph_workers=args.claim_paragraph_workers,
		argo_http_workers=args.argo_http_workers,
		force=args.force,
		extract_only=args.extract_only,
		publish_eval_stats=args.publish_eval_stats,
		publish_tool_stats=args.publish_tool_stats,
		posteval_with_plots=args.posteval_with_plots,
		posteval_with_audit=args.posteval_with_audit,
		posteval_scope=args.posteval_scope,
		tool_stats_scope=args.tool_stats_scope,
		verbose=args.verbose,
		output_root=args.output_root,
		eval_root=args.eval_root,
		stats_root=args.stats_root,
		tool_stats_root=args.tool_stats_root,
	)


if __name__ == "__main__":
	raise SystemExit(main())


__all__ = [
	"DEFAULT_EVAL_ROOT",
	"DEFAULT_OUTPUT_ROOT",
	"DEFAULT_STATS_ROOT",
	"DEFAULT_TOOL_STATS_ROOT",
	"build_parser",
	"configure_logging",
	"discover_runs",
	"main",
	"run_pipeline",
]
