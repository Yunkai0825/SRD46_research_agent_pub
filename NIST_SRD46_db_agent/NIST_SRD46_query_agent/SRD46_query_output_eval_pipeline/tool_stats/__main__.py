"""CLI entry point for the canonical tool statistics bundle."""
from __future__ import annotations

import argparse

from .loader import DEFAULT_OUTPUT_ROOT
from .pipeline import DEFAULT_OUT, run_tool_stats_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m SRD46_query_output_eval_pipeline.tool_stats",
        description="Build canonical tool statistics from `_output/Model_*/Q*/` histories and results.",
    )
    parser.add_argument("--root", default=str(DEFAULT_OUTPUT_ROOT), help="Run artifact root (default: repository-local query output root)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory (default: repository-local query tool stats root)")
    parser.add_argument("--models", action="append", help="Restrict to model name (selection scope only).")
    parser.add_argument("--questions", action="append", help="Restrict to question id (selection scope only).")
    parser.add_argument("--sections", action="append", help="Restrict to section prefix (selection scope only).")
    parser.add_argument("--no-plots", action="store_true", help="Skip figure generation.")
    parser.add_argument(
        "--scope",
        choices=("full", "selection"),
        default="full",
        help="`full` rebuilds the full canonical bundle; `selection` keeps only filtered slices.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_tool_stats_bundle(
        root=args.root,
        out=args.out,
        include_models=args.models,
        include_questions=args.questions,
        include_sections=args.sections,
        scope=args.scope,
        with_plots=not args.no_plots,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())