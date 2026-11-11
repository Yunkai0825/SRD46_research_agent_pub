"""Phase-5 orchestrator + CLI entry point for posteval_stats.

Run::

    python -m SRD46_query_output_eval_pipeline.posteval_stats build [--root PATH] [--out DIR]
    python -m SRD46_query_output_eval_pipeline.posteval_stats audit [--root PATH] [--out DIR]
    python -m SRD46_query_output_eval_pipeline.posteval_stats all   [--root PATH] [--out DIR]
"""
from __future__ import annotations

import argparse

from .loader import DEFAULT_OUTPUT_EVAL
from .pipeline import DEFAULT_OUT, audit_stats_bundle, build_stats_bundle, run_stats_bundle


def cmd_build(args: argparse.Namespace) -> int:
    build_stats_bundle(
        root=args.root,
        out=args.out,
        include_models=args.models,
        include_questions=args.questions,
        include_sections=args.sections,
        include_section_4=args.include_section_4,
        separate_section_5=not args.merge_section_5,
        separate_section_1=args.separate_section_1,
        separate_section_2=args.separate_section_2,
        separate_section_3=args.separate_section_3,
        with_plots=args.with_plots,
    )
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    audit_stats_bundle(
        root=args.root,
        out=args.out,
        include_models=args.models,
        include_questions=args.questions,
        include_sections=args.sections,
        include_section_4=args.include_section_4,
        separate_section_5=not args.merge_section_5,
        separate_section_1=args.separate_section_1,
        separate_section_2=args.separate_section_2,
        separate_section_3=args.separate_section_3,
    )
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    run_stats_bundle(
        root=args.root,
        out=args.out,
        include_models=args.models,
        include_questions=args.questions,
        include_sections=args.sections,
        include_section_4=args.include_section_4,
        separate_section_5=not args.merge_section_5,
        separate_section_1=args.separate_section_1,
        separate_section_2=args.separate_section_2,
        separate_section_3=args.separate_section_3,
        with_plots=args.with_plots,
        with_audit=True,
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m SRD46_query_output_eval_pipeline.posteval_stats",
        description="Post-evaluation claim statistics & validation.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--root", default=str(DEFAULT_OUTPUT_EVAL),
                        help="Eval root directory containing Model_*/Q*/claims_batch*.json.")
        sp.add_argument("--out", default=str(DEFAULT_OUT),
                        help="Output directory for CSV/JSON/figures.")
        sp.add_argument("--models", action="append",
                        help="Restrict to model name (repeatable).")
        sp.add_argument("--questions", action="append",
                        help="Restrict to question id (repeatable).")
        sp.add_argument("--sections", action="append",
                        help="Restrict to section prefix (repeatable).")
        sp.add_argument("--include-section-4", action="store_true",
                help="Include section 4 prompts in the stats scope.")
        sp.add_argument("--merge-section-5", action="store_true",
                help="Pool sections 5.1 and 5.2 into section 5.")
        sp.add_argument("--separate-section-1", action="store_true",
                help="Keep sections 1.1 and 1.2 separate instead of pooling them into section 1.")
        sp.add_argument("--separate-section-2", action="store_true",
                help="Keep sections 2.1 and 2.2 separate instead of pooling them into section 2.")
        sp.add_argument("--separate-section-3", action="store_true",
                help="Keep sections 3.1 and 3.2 separate instead of pooling them into section 3.")

    sp_build = sub.add_parser("build", help="Run loader + aggregation [+ plots].")
    add_common(sp_build)
    sp_build.add_argument("--with-plots", action="store_true",
                          help="Also render PNG charts (requires matplotlib).")
    sp_build.set_defaults(func=cmd_build)

    sp_audit = sub.add_parser("audit", help="Run Phase-4 re-validation audits.")
    add_common(sp_audit)
    sp_audit.set_defaults(func=cmd_audit)

    sp_all = sub.add_parser("all", help="build then audit.")
    add_common(sp_all)
    sp_all.add_argument("--with-plots", action="store_true")
    sp_all.set_defaults(func=cmd_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
