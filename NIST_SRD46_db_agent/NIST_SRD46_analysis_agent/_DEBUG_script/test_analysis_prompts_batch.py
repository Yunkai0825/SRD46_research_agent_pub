"""
Batch debug runner for the SRD-46 analysis agent.
=================================================

Parses the prompt table in
``NIST_SRD46_analysis_agent/_DEBUG_input/TEST_PROMPTS.md`` and runs
each prompt through ``SRD46_analysis_run``. Writes one session
directory per prompt under ``NIST_SRD46_analysis_agent/Diagnostics/``
and an aggregate ``_batch_summary_<timestamp>.json``.

Usage (from repo root)::

    # full batch
    python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch

    # subset by label
    python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch \
        --only Cu_speciation_1D Fe_EDTA_vs_citrate

    # subset by reasoning layer
    python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch \
        --layer L3 L4 L5

    # don't wipe pre-existing per-prompt session dirs
    python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch --keep
"""

from __future__ import annotations

import sys
from pathlib import Path



import argparse
import contextlib
import io
import json
import logging
import re
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


# ---------------------------------------------------------------------------
# Logging: DEBUG by default so the per-prompt _run.log captures every
# agent-level message (L0 / L1 / L2_* / L3 etc.). Tee'd stderr below
# picks these up because logging.StreamHandler writes to stderr.
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
    force=True,
)
for _noisy in ("httpx", "urllib3", "openai", "matplotlib",
               "requests", "PIL", "numexpr"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Tee writer: mirror every write to console + per-prompt log file, line-flushed
# ---------------------------------------------------------------------------

class _TeeStream(io.TextIOBase):
    def __init__(self, primary, log_fh) -> None:
        self._primary = primary
        self._log = log_fh

    def write(self, s: str) -> int:  # type: ignore[override]
        try:
            self._primary.write(s)
            self._primary.flush()
        except Exception:
            pass
        try:
            self._log.write(s)
            self._log.flush()
        except Exception:
            pass
        return len(s)

    def flush(self) -> None:  # type: ignore[override]
        for fh in (self._primary, self._log):
            try:
                fh.flush()
            except Exception:
                pass

    def isatty(self) -> bool:  # type: ignore[override]
        try:
            return bool(self._primary.isatty())
        except Exception:
            return False


@contextlib.contextmanager
def _tee_to(log_path: Path):
    """Tee sys.stdout + sys.stderr to ``log_path`` (line-buffered, append).

    Also re-points any root-logger ``StreamHandler`` to the tee'd stderr
    so that ``logging.debug(...)`` calls from the agent land in the log
    file in real time.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(log_path, "a", encoding="utf-8", buffering=1)
    orig_out, orig_err = sys.stdout, sys.stderr
    tee_out = _TeeStream(orig_out, fh)
    tee_err = _TeeStream(orig_err, fh)
    sys.stdout = tee_out
    sys.stderr = tee_err

    # Re-point root logger handlers from the original stderr to the tee.
    root = logging.getLogger()
    saved_streams: List[Tuple[logging.StreamHandler, Any]] = []
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            saved_streams.append((h, h.stream))
            h.setStream(tee_err)

    try:
        yield
    finally:
        for h, original_stream in saved_streams:
            try:
                h.setStream(original_stream)
            except Exception:
                pass
        sys.stdout = orig_out
        sys.stderr = orig_err
        try:
            fh.close()
        except Exception:
            pass

# NOTE: use .absolute() (not .resolve()) so a short substituted drive root
# (e.g. Q:\ -> N:\..\SRD46_research_agent) is NOT expanded back to the long UNC
# path. Expanding to \\host\share\... re-inflates every output path past the
# Windows MAX_PATH (260) limit and breaks card writes / rmtree on deep dirs.
_HERE = Path(__file__).absolute()
_REPO = _HERE.parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import (  # noqa: E402
    SRD46_analysis_run,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.SRD46_analysis_argo_config import (  # noqa: E402
    AGENT_CONFIG,
)

_AGENT_ROOT  = _HERE.parents[1]
_PROMPTS_MD  = _AGENT_ROOT / "_DEBUG_input" / "TEST_PROMPTS.md"
# Flat benchmark layout (user order 2026-09-06): Benchmark/SRD46/Analysis/<label>,
# no Diagnostics/analysis_agent nesting.
_OUTPUT_ROOT = Path(__file__).absolute().parents[3] / "_benchmark" / "Analysis"


# ---------------------------------------------------------------------------
# Prompt-table parser
# ---------------------------------------------------------------------------

_BEGIN = "<!-- BEGIN PROMPTS -->"
_END   = "<!-- END PROMPTS -->"


def load_prompts(md_path: Path = _PROMPTS_MD) -> List[Dict[str, str]]:
    """Parse the ``| # | layer | label | prompt |`` markdown table.

    Returns a list of ``{"idx", "layer", "label", "prompt"}`` dicts in
    declaration order. Raises if the BEGIN/END markers or the header
    row are missing.
    """
    text = md_path.read_text(encoding="utf-8")
    if _BEGIN not in text or _END not in text:
        raise RuntimeError(
            f"{md_path} is missing BEGIN/END PROMPTS markers"
        )
    block = text.split(_BEGIN, 1)[1].split(_END, 1)[0]

    rows: List[Dict[str, str]] = []
    seen_labels: set[str] = set()
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        # skip header + separator rows
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0].lower() in {"#", ""}:
            continue
        if re.fullmatch(r":?-+:?", cells[0]):
            continue
        idx, layer, label, prompt = cells[0], cells[1], cells[2], cells[3]
        if not prompt or prompt.startswith("--"):
            continue
        if label in seen_labels:
            raise RuntimeError(f"duplicate prompt label: {label!r}")
        seen_labels.add(label)
        rows.append({
            "idx":    idx,
            "layer":  layer,
            "label":  label,
            "prompt": prompt,
        })
    if not rows:
        raise RuntimeError(f"no prompts parsed from {md_path}")
    return rows


# ---------------------------------------------------------------------------
# Result summariser (mirrors test_10_chemistry_prompts.py)
# ---------------------------------------------------------------------------

def summarize(result: Dict[str, Any]) -> Dict[str, Any]:
    sess = Path(result.get("session_dir") or "")
    v = result.get("verdict") or {}
    phase_status: Dict[str, str] = {}
    first_failure: str | None = None
    l1_calls: List[str] = []
    if sess.exists():
        for call_dir in sorted(sess.glob("L1_call_*")):
            l1_calls.append(call_dir.name)
            # Current L1 persists its deterministic execution status directly;
            # it does not emit the legacy per-call manifest expected below.
            # Read this first so a fatal LC stage becomes the actionable first
            # failure instead of silently producing an empty phase summary.
            status_path = call_dir / "pipeline_status.json"
            execution_status_found = False
            if status_path.exists():
                try:
                    pipeline_status = json.loads(
                        status_path.read_text(encoding="utf-8")
                    )
                except Exception:
                    pipeline_status = None
                if isinstance(pipeline_status, dict):
                    execution_status_found = True
                    stage = str(
                        pipeline_status.get("stage") or "pipeline"
                    ).strip()
                    key = f"{call_dir.name}/{stage}"
                    status = str(
                        pipeline_status.get("status") or "?"
                    ).strip().lower()
                    phase_status[key] = status
                    if (
                        first_failure is None
                        and status not in ("ok", "complete", "passed")
                    ):
                        first_failure = key
            if not execution_status_found:
                # Historical L1 calls predate pipeline_status.json. Recover
                # their deterministic stage outcome from LC summary sidecars.
                for stage in ("LC1", "LC2", "LC3"):
                    summary_path = (
                        call_dir / stage / "summary" / f"{stage}_summary.json"
                    )
                    if not summary_path.exists():
                        continue
                    try:
                        stage_summary = json.loads(
                            summary_path.read_text(encoding="utf-8")
                        )
                    except Exception:
                        continue
                    if not isinstance(stage_summary, dict):
                        continue
                    key = f"{call_dir.name}/{stage}"
                    status = str(
                        stage_summary.get("status") or "?"
                    ).strip().lower()
                    phase_status[key] = status
                    if (
                        first_failure is None
                        and status not in ("ok", "complete", "passed")
                    ):
                        first_failure = key
            mpath = call_dir / "manifest.json"
            if not mpath.exists():
                continue
            try:
                m = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            for pid, info in (m.get("phases") or {}).items():
                key = f"{call_dir.name}/{pid}"
                status = info.get("status", "?")
                phase_status[key] = status
                if (first_failure is None
                        and status not in ("ok", "complete", "passed")):
                    first_failure = key
        # Root phases include cross-call gates such as LD scientific review.
        # They complement, rather than replace, the stage-specific sidecar.
        root_manifest_path = sess / "manifest.json"
        if root_manifest_path.exists():
            try:
                root_manifest = json.loads(
                    root_manifest_path.read_text(encoding="utf-8")
                )
            except Exception:
                root_manifest = None
            if isinstance(root_manifest, dict):
                for pid, info in (root_manifest.get("phases") or {}).items():
                    if not isinstance(info, dict):
                        continue
                    key = str(pid)
                    status = str(info.get("status") or "?")
                    phase_status.setdefault(key, status)
                    if (
                        first_failure is None
                        and status not in ("ok", "complete", "passed")
                    ):
                        first_failure = key
    return {
        "session_dir":   str(sess),
        "verdict":       v.get("verdict"),
        "iterations":    result.get("iterations"),
        "elapsed_s":     round(float(result.get("elapsed_s") or 0.0), 1),
        "timed_out":     result.get("timed_out"),
        "n_l1_calls":    len(l1_calls),
        "n_l0_tools":    len(result.get("tool_history") or []),
        "phase_status":  phase_status,
        "first_failure": first_failure,
        "verdict_notes": (v.get("notes") or [])[:5],
        "answer_head":   (result.get("answer") or "")[:200].replace("\n", " "),
    }


# ---------------------------------------------------------------------------
# Per-prompt runner
# ---------------------------------------------------------------------------

def run_one(
    row: Dict[str, str],
    *,
    keep: bool = False,
    debug: bool = True,
) -> Dict[str, Any]:
    label  = row["label"]
    layer  = row["layer"]
    prompt = row["prompt"]
    sess   = _OUTPUT_ROOT / label

    if sess.exists() and not keep:
        # SMB shares raise transient WinError 145 (dir not empty) when
        # rmtree races delayed directory-handle release; retry briefly.
        for _attempt in range(4):
            try:
                shutil.rmtree(sess)
                break
            except OSError:
                if _attempt == 3:
                    raise
                time.sleep(2.0)
    sess.mkdir(parents=True, exist_ok=True)

    log_path = sess / "_run.log"
    # fresh log per run (unless --keep)
    if log_path.exists() and not keep:
        try:
            log_path.unlink()
        except Exception:
            pass

    with _tee_to(log_path):
        print(f"\n==== [{layer}] {label} "
              f"{'=' * max(0, 50 - len(label) - len(layer))}")
        print(f"prompt : {prompt}")
        print(f"session: {sess}")
        print(f"log    : {log_path}")
        print(f"argo   : {AGENT_CONFIG.API_USER}")
        print(f"started: {datetime.now().isoformat(timespec='seconds')}")

        t0 = time.time()
        try:
            res = SRD46_analysis_run(prompt, session_dir=sess, debug=debug)
            summary = summarize(res)
        except Exception as exc:
            traceback.print_exc()
            return {
                "label":       label,
                "layer":       layer,
                "error":       repr(exc),
                "session_dir": str(sess),
                "elapsed_s":   round(time.time() - t0, 1),
            }

        summary["label"] = label
        summary["layer"] = layer
        summary["argo_api_user"] = AGENT_CONFIG.API_USER
        print(json.dumps(summary, indent=2, default=str))
        return summary


# ---------------------------------------------------------------------------
# Filtering + CLI
# ---------------------------------------------------------------------------

def _filter(
    rows: List[Dict[str, str]],
    *,
    only: Iterable[str] | None,
    layers: Iterable[str] | None,
) -> List[Dict[str, str]]:
    out = list(rows)
    if only:
        wanted = {x for x in only}
        out = [r for r in out if r["label"] in wanted]
        missing = wanted - {r["label"] for r in out}
        if missing:
            raise SystemExit(f"unknown prompt label(s): {sorted(missing)}")
    if layers:
        wanted_layers = {x.upper() for x in layers}
        out = [r for r in out if r["layer"].upper() in wanted_layers]
    return out


def _print_aggregate(rows: List[Dict[str, Any]]) -> Tuple[int, int, int, int]:
    print("\n==== AGGREGATE SUMMARY ==========================")
    for r in rows:
        v = r.get("verdict") or r.get("error", "?")
        first_fail = r.get("first_failure") or "-"
        print(f"  [{r.get('layer','?'):<3}] {r['label']:<28} "
              f"verdict={v!s:<10} t={r.get('elapsed_s','?')}s "
              f"L1={r.get('n_l1_calls','?')} first_fail={first_fail}")
    n_pass    = sum(1 for r in rows if r.get("verdict") == "pass")
    n_partial = sum(1 for r in rows if r.get("verdict") == "partial")
    n_fail    = sum(1 for r in rows if r.get("verdict") == "fail")
    n_error   = sum(1 for r in rows if r.get("error"))
    print(f"\n  totals: pass={n_pass} partial={n_partial} "
          f"fail={n_fail} error={n_error} (of {len(rows)})")
    return n_pass, n_partial, n_fail, n_error


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Batch run analysis-agent test prompts.",
    )
    ap.add_argument(
        "--only", nargs="+", metavar="LABEL",
        help="Run only prompts with these labels.",
    )
    ap.add_argument(
        "--layer", nargs="+", metavar="LAYER",
        help="Run only prompts in these layers (e.g. L1 L3).",
    )
    ap.add_argument(
        "--keep", action="store_true",
        help="Do not wipe pre-existing per-prompt session dirs.",
    )
    ap.add_argument(
        "--debug", dest="debug", action="store_true", default=True,
        help="Forward debug=True to SRD46_analysis_run (default: on).",
    )
    ap.add_argument(
        "--no-debug", dest="debug", action="store_false",
        help="Disable debug=True forwarding.",
    )
    ap.add_argument(
        "--list", action="store_true",
        help="List parsed prompts and exit (no runs).",
    )
    args = ap.parse_args(argv)

    rows = _filter(load_prompts(), only=args.only, layers=args.layer)
    if not rows:
        print("no prompts matched the filters", file=sys.stderr)
        return 2

    if args.list:
        for r in rows:
            print(f"  [{r['layer']:<3}] {r['label']:<28}  {r['prompt']}")
        return 0

    _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = [run_one(r, keep=args.keep, debug=args.debug) for r in rows]
    n_pass, n_partial, n_fail, n_error = _print_aggregate(results)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = _OUTPUT_ROOT / f"_batch_summary_{stamp}.json"
    summary_path.write_text(
        json.dumps(
            {
                "timestamp": stamp,
                "totals": {
                    "pass": n_pass, "partial": n_partial,
                    "fail": n_fail, "error": n_error,
                    "n": len(results),
                },
                "results": results,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\n  wrote {summary_path}")

    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
