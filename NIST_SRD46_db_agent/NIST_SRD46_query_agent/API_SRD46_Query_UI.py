#!/usr/bin/env python3
"""SRD-46 unified API entry point.

Two modes are exposed via argparse subcommands:

* ``serve``  — launch the NIST_SRD46_database_browser Flask web UI
               (the default if no subcommand is given).
* ``query``  — invoke the SRD-46 query agent directly from the terminal
               using the same machinery as the browser's Agent page.

Examples
--------
Launch the browser on http://localhost:5046 (default)::

    python API_SRD46_Query_UI.py
    python API_SRD46_Query_UI.py serve --host 0.0.0.0 --port 8080 --debug

Run a single freeform conversation through the agent without the browser::

    python API_SRD46_Query_UI.py query "List Fe(III) ligands with logK > 20" -m gpt54
    python API_SRD46_Query_UI.py query @prompts/fe.txt -m claudeopus46 --max-turns 40
    python API_SRD46_Query_UI.py query "..." -m gpt54 --no-enrich --skip-claim-validation
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the project root is importable no matter where this script is
# invoked from (the freeform runner, query_agent, argo_config, and the
# Flask browser package all live at the project root).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).absolute().parent
REPO_ROOT = PROJECT_ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# serve: Flask browser
# ---------------------------------------------------------------------------

def _cmd_serve(args: argparse.Namespace) -> int:
    """Boot the NIST_SRD46_database_browser Flask app."""
    from NIST_SRD46_database_browser import app as browser_app
    from NIST_SRD46_database_browser import db as dbmod

    status = dbmod.verify_all_paths()
    for name, ok in status.items():
        print(f"  {'OK ' if ok else 'XX '} {name}")

    debug = bool(args.debug) or os.environ.get(
        "FLASK_DEBUG", "0"
    ) not in ("", "0", "false", "False")

    browser_app.app.run(
        host=args.host,
        port=args.port,
        debug=debug,
        use_reloader=debug,
    )
    return 0


# ---------------------------------------------------------------------------
# query: direct agent invocation
# ---------------------------------------------------------------------------

def _resolve_prompt(prompt_arg: str) -> str:
    """Allow ``@path`` syntax for reading a prompt from a file."""
    if prompt_arg.startswith("@"):
        return Path(prompt_arg[1:]).read_text(encoding="utf-8")
    return prompt_arg


def _cmd_query(args: argparse.Namespace) -> int:
    """Run a freeform agent conversation and write the standard artifacts."""
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.freeform_runner import run_freeform_query  # type: ignore

    prompt_text = _resolve_prompt(args.prompt)

    result = run_freeform_query(
        prompt_text,
        model=args.model,
        timeout=args.timeout,
        max_turns=args.max_turns,
        title=args.title,
        enrich=not args.no_enrich,
        enrich_claims=not args.skip_claim_validation,
        enable_sql=not args.disable_sql,
    )

    print(f"Freeform query complete: qid={result['qid']}")
    print(f"  Result : {result['result_path']}")
    print(f"  History: {result['history_path']}")
    if result.get("answer_path"):
        print(f"  Answer : {result['answer_path']}")
    if result.get("claims_path"):
        print(f"  Claims : {result['claims_path']}")
    print(f"\nView in browser: /freeform/{args.model}/{result['qid']}/1")
    return 0


# ---------------------------------------------------------------------------
# argparse plumbing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="API_SRD46_Query_UI",
        description="Unified API entry point for the SRD-46 browser and query agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    # serve --------------------------------------------------------------
    p_serve = sub.add_parser(
        "serve",
        help="Launch the NIST SRD-46 browser Flask app (default).",
    )
    p_serve.add_argument("--host", default="127.0.0.1",
                         help="Interface to bind (default: 127.0.0.1).")
    p_serve.add_argument("--port", type=int, default=5046,
                         help="TCP port to listen on (default: 5046).")
    p_serve.add_argument("--debug", action="store_true",
                         help="Enable Flask debug mode + auto-reloader.")
    p_serve.set_defaults(func=_cmd_serve)

    # query --------------------------------------------------------------
    p_query = sub.add_parser(
        "query",
        help="Run a single freeform conversation through the SRD-46 query agent.",
    )
    p_query.add_argument("prompt",
                         help="Prompt text, or @path/to/file to read it from disk.")
    p_query.add_argument("-m", "--model", required=True,
                         help="Argo model alias (e.g. gpt5, gpt54, claudeopus46).")
    p_query.add_argument("-t", "--timeout", type=int, default=None,
                         help="Per-turn timeout in seconds.")
    p_query.add_argument("--max-turns", type=int, default=None,
                         help="Maximum agent iterations / tool turns.")
    p_query.add_argument("--title", default="Freeform query",
                         help="Display title used by the browser index.")
    p_query.add_argument("--no-enrich", action="store_true",
                         help="Skip the eval-pipeline enrichment step.")
    p_query.add_argument("--skip-claim-validation", action="store_true",
                         help="Skip claim post-validation (regex enricher + classifier).")
    sql_grp = p_query.add_mutually_exclusive_group()
    sql_grp.add_argument("--enable-sql", action="store_true",
                         help="Deprecated no-op; execute_srd46_sql is enabled by default.")
    sql_grp.add_argument("--disable-sql", action="store_true",
                         help="Hide execute_srd46_sql for this run.")
    p_query.set_defaults(func=_cmd_query)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Default to the Flask browser if no subcommand was supplied.
    if not getattr(args, "cmd", None):
        args = parser.parse_args(["serve", *(argv or [])])

    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
