"""Run a single ad-hoc (non-test-set) query through the SRD-46 agent and
produce the same on-disk artifacts the batch test runner produces, so the
existing eval pipeline + browser can render and annotate the result.

Storage layout (mixed in with the test-set runs, distinguished by the
``Qfree_`` prefix on the question id)::

    _output/Query/Model_<m>/Qfree_<ts>/
        Qfree_<ts>_result_batch1.md
        Qfree_<ts>_history_batch1.md
        Qfree_<ts>_ref_ids_batch1.md

    _output/Query/_evaluation/Model_<m>/Qfree_<ts>/
        answer_batch1.md
        tool_eval_batch1.md
        claims_batch1.json

The browser's /eval/ index hides ``Qfree_*`` runs and a dedicated /freeform/
index lists them — the per-run renderer is shared (identical interface).
"""
from __future__ import annotations

import datetime as _dt
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).absolute().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
REPO_ROOT = PROJECT_ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The batch test-runner module lives under BATCH_run_scripts/ now; expose it
# on sys.path so the existing top-level import name still resolves.
_BATCH_SCRIPTS_DIR = PROJECT_ROOT / "BATCH_run_scripts"
if _BATCH_SCRIPTS_DIR.is_dir() and str(_BATCH_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_BATCH_SCRIPTS_DIR))

from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config  # noqa: E402
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.input_support_helpers.extract_tool_results import (  # noqa: E402
    extract_run as _extract_run,
)
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.enricher import (  # noqa: E402
    enrich_run_claims as _enrich_run_claims,
)

log = logging.getLogger("freeform-runner")

# Shared freeform results for all local users.
FREEFORM_QID_PREFIX = "Qfree_"
_OUTPUT_ROOT = REPO_ROOT / "_output" / "Query"
_EVAL_ROOT = _OUTPUT_ROOT / "_evaluation"


def resolve_roots(stored: bool | None = None) -> tuple[Path, Path]:
    """Return shared freeform and evaluation directories under ``_output``.

    ``stored`` is retained for callers from older browser versions.
    """
    _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    _EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    return _OUTPUT_ROOT, _EVAL_ROOT


def _configure_sql_tool(enable_sql: bool) -> None:
    blocked_tools = set(argo_config.MCP_BLOCKED_TOOLS)
    if enable_sql:
        blocked_tools.discard("execute_srd46_sql")
    else:
        blocked_tools.add("execute_srd46_sql")

    blocked_csv = ",".join(sorted(blocked_tools))
    os.environ["SRD46_BLOCKED_MCP_TOOLS"] = blocked_csv
    argo_config.MCP_BLOCKED_TOOLS = frozenset(blocked_tools)


def _load_runtime_helpers() -> tuple:
    module_names = (
        "server",
        "agent_runtime",
        "run_batch_SRD46_query_db_subagent",
        "query_agent",
    )
    loaded = {}
    for name in module_names:
        module_path = "NIST_SRD46_db_agent.NIST_SRD46_query_agent." + (
            "BATCH_run_scripts." + name if name.startswith("run_batch_") else name
        )
        if module_path in sys.modules:
            loaded[name] = importlib.reload(sys.modules[module_path])
        else:
            loaded[name] = importlib.import_module(module_path)

    batch_module = loaded["run_batch_SRD46_query_db_subagent"]
    query_module = loaded["query_agent"]
    return (
        query_module.run_agent_query_sync,
        batch_module.write_single_result,
        batch_module.write_single_history,
    )


def _new_freeform_qid(now: _dt.datetime | None = None) -> str:
    ts = (now or _dt.datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"{FREEFORM_QID_PREFIX}{ts}"


def run_freeform_query(
    prompt: str,
    *,
    model: str,
    timeout: Optional[int] = None,
    max_turns: Optional[int] = None,
    qid: Optional[str] = None,
    title: str = "Freeform query",
    enrich: bool = True,
    enrich_claims: bool = True,
    enable_sql: bool = True,
) -> dict:
    """Execute *prompt* through the agent and write all artifacts.

    Returns ``{"qid": ..., "out_dir": Path, "result_path": Path,
    "history_path": Path, "answer_path": Path, "claims_path": Path|None}``.

    The bare ``Qfree_<ts>`` qid (no leading ``Q.``-style dotted id) is the
    only thing distinguishing freeform runs from test-set runs on disk.
    """
    qid = qid or _new_freeform_qid()
    if not qid.startswith(FREEFORM_QID_PREFIX):
        raise ValueError(f"freeform qid must start with {FREEFORM_QID_PREFIX!r}")

    output_root, eval_root = resolve_roots()
    model_dir = output_root / f"Model_{model}"
    model_dir.mkdir(parents=True, exist_ok=True)

    # CRITICAL: argo_config.MODEL is hardcoded ("gpt54" by default) and is the
    # actual model the agent loop sends to Argo. The CLI -m flag must be wired
    # through here or the run silently uses the default model.
    argo_config.MODEL = model
    argo_config.PLANNER_MODEL = model
    argo_config.VERDICT_MODEL = model
    _configure_sql_tool(enable_sql)
    run_agent_query_sync, write_single_result, write_single_history = _load_runtime_helpers()

    log.info(
        "Freeform query starting: model=%s (argo_config.MODEL=%s) qid=%s timeout=%s max_turns=%s sql=%s",
        model, argo_config.MODEL, qid, timeout, max_turns, enable_sql,
    )
    api_result = run_agent_query_sync(
        prompt,
        timeout=timeout,
        max_tool_iterations=max_turns,
    )

    # Build a dict in the shape write_single_result/write_single_history expect.
    # ``id`` is stored WITHOUT the leading "Q" because _qid() re-adds it.
    record = {
        "id": qid[1:],  # strip leading "Q" so _qid("free_<ts>") -> "Qfree_<ts>"
        "prompt": prompt,
        "section": "freeform",
        "section_title": title,
        "tool_count": len(api_result.tool_history),
        "elapsed": api_result.elapsed,
        "verdict_elapsed": 0.0,
        "tool_history": api_result.tool_history,
        "compactor_events": api_result.compactor_events,
        "answer": api_result.answer,
        "verdict": "",
    }

    result_path = write_single_result(record, model_dir, batch=1)
    history_path = write_single_history(record, model_dir, batch=1)

    out_dir = model_dir / qid
    log.info("Freeform query artifacts written under %s", out_dir)

    answer_path = None
    claims_path = None
    if enrich:
        try:
            _extract_run(model, qid, 1, output_root=output_root, eval_root=eval_root)
            answer_path = eval_root / f"Model_{model}" / qid / "answer_batch1.md"
        except Exception:
            log.exception("extract_run failed for %s/%s", model, qid)
        if enrich_claims:
            try:
                _enrich_run_claims(model, qid, 1, output_root=output_root, eval_root=eval_root)
                claims_path = eval_root / f"Model_{model}" / qid / "claims_batch1.json"
            except Exception:
                log.exception("enrich_run_claims failed for %s/%s", model, qid)
        else:
            log.info("Skipping claim post-validation (enrich_claims=False) for %s/%s", model, qid)

    return {
        "qid": qid,
        "out_dir": out_dir,
        "result_path": result_path,
        "history_path": history_path,
        "answer_path": answer_path,
        "claims_path": claims_path,
    }


def _main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prompt", help="Free-form prompt text (or @path to a file).")
    p.add_argument("-m", "--model", required=True, help="Model name, e.g. claudeopus46")
    p.add_argument("-t", "--timeout", type=int, default=None,
                   help="Per-turn timeout in seconds (matches MAX_TURN_SECONDS env)")
    p.add_argument("--max-turns", type=int, default=None,
                   help="Maximum agent iterations/tool turns for this run.")
    sql_group = p.add_mutually_exclusive_group()
    sql_group.add_argument("--enable-sql", action="store_true",
                           help="Deprecated no-op; execute_srd46_sql is enabled by default.")
    sql_group.add_argument("--disable-sql", action="store_true",
                           help="Hide execute_srd46_sql for this freeform run.")
    p.add_argument("--no-enrich", action="store_true",
                   help="Skip the eval-pipeline enrichment step (just write raw artifacts).")
    p.add_argument("--skip-claim-validation", action="store_true",
                   help="Skip claim post-validation (regex enricher + classifier Argo calls); answer extraction still runs.")
    p.add_argument("--title", default="Freeform query", help="Display title for the index page.")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    prompt_text = args.prompt
    if prompt_text.startswith("@"):
        prompt_text = Path(prompt_text[1:]).read_text(encoding="utf-8")

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


if __name__ == "__main__":
    _main()
