"""
10-prompt chemistry test suite for SRD46_analysis_run.
======================================================

Designed to exercise the deterministic L0 stub (now equipped with
real metal db_ids) plus the new dedup subagent.  Each prompt targets
a different combination of metal(s) / ligand(s) / phase challenge.

Run from repo root::

    python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_10_chemistry_prompts
"""

from __future__ import annotations

import sys
from pathlib import Path



import json
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import SRD46_analysis_run  # noqa: E402


PROMPTS = [
    # 1. Single-metal mono-ligand baseline (matches test_01 fixture).
    ("Cu_glycine",
     "Pourbaix diagram of Cu in glycine, pH 0-14, 25 C, I=0.1, "
     "[Cu]=1 mM, [glycine]=5 mM."),
    # 2. Iron + citrate (matches a test_06 sub-network).
    ("Fe_citrate",
     "Speciation of Fe with citrate as a function of pH 1-12 at 25 C, "
     "I=0.1, [Fe]=1 mM, [citrate]=10 mM."),
    # 3. Cu + glycine + hydroxide (multi-ligand).
    ("Cu_glycine_OH",
     "Speciation of Cu with glycine and hydroxide across pH 0-14."),
    # 4. Multi-metal Cu + Zn with two ligands (matches test_04).
    ("CuZn_glycine_citrate",
     "Pourbaix-style speciation of a Cu and Zn mixture with glycine and "
     "citrate, pH 2-12, T=25 C, I=0.1."),
    # 5. Calcium + glyphosate-like ligand exercise (will fall back to
    #    glycine if ligand keyword absent).
    ("Ca_glycine",
     "Speciation of Ca with glycine, pH 4-12, 25 C, I=0.1."),
    # 6. Hg with glycine.
    ("Hg_glycine",
     "Pourbaix diagram of Hg in glycine, pH 0-14, T=25 C."),
    # 7. Mixed Fe + Cu + glycine + citrate (test_06 replica).
    ("FeCu_glycine_citrate",
     "Speciation of an Fe and Cu mixture with glycine and citrate, "
     "pH 0-14, 25 C, I=0.1, [Fe]=1 mM, [Cu]=1 mM, "
     "[glycine]=5 mM, [citrate]=5 mM."),
    # 8. Pb single-metal aquo (no ligand keyword) -- aquo-only system.
    ("Pb_aquo",
     "Pourbaix diagram of Pb in pure water, pH 0-14, 25 C, I=0.01."),
    # 9. Ni + EDTA strong chelate.
    ("Ni_edta",
     "Speciation of Ni with EDTA across pH 0-14 at 25 C, I=0.1, "
     "[Ni]=1 mM, [EDTA]=2 mM."),
    # 10. Negative -- unknown metal so L0 can't seed db_ids.
    ("Unknown_X",
     "Pourbaix diagram of element Xx in some_unknown_ligand, pH 0-14."),
]


def _summarize(result: dict) -> dict:
    """Build a per-prompt summary from the new L0 return shape.

    The new LLM-driven L0 returns
    ``{answer, iterations, elapsed_s, tool_history, session_dir,
       timed_out, verdict}``.
    Deterministic execution status lives in each call's
    ``pipeline_status.json`` sidecar; cross-call gates live in the root
    manifest. Legacy per-call manifests are still read when present.
    """
    sess = Path(result.get("session_dir") or "")
    v = result.get("verdict") or {}
    phase_status: dict[str, str] = {}
    first_failure: str | None = None
    l1_calls: list[str] = []
    if sess.exists():
        for call_dir in sorted(sess.glob("L1_call_*")):
            l1_calls.append(call_dir.name)
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


_OUTPUT_ROOT = Path(__file__).absolute().parents[3] / "_output" / "Diagnostics" / "Analysis"


def run_one(label: str, prompt: str) -> dict:
    sess = _OUTPUT_ROOT / label
    if sess.exists():
        import shutil
        shutil.rmtree(sess)
    sess.mkdir(parents=True, exist_ok=True)
    print(f"\n==== {label} ============================================")
    print(f"prompt: {prompt}")
    print(f"session: {sess}")
    try:
        res = SRD46_analysis_run(prompt, session_dir=sess, debug=False)
        summary = _summarize(res)
    except Exception as exc:
        traceback.print_exc()
        return {"label": label, "error": repr(exc),
                "session_dir": str(sess)}
    print(json.dumps(summary, indent=2, default=str))
    summary["label"] = label
    return summary


def main() -> int:
    rows = [run_one(label, prompt) for label, prompt in PROMPTS]
    print("\n==== AGGREGATE SUMMARY ==========================")
    for r in rows:
        v = r.get("verdict") or r.get("error", "?")
        first_fail = r.get("first_failure") or "-"
        print(f"  {r['label']:<25} verdict={v!s:<10} first_fail={first_fail}")
    n_pass    = sum(1 for r in rows if r.get("verdict") == "pass")
    n_partial = sum(1 for r in rows if r.get("verdict") == "partial")
    n_fail    = sum(1 for r in rows if r.get("verdict") == "fail")
    n_error   = sum(1 for r in rows if r.get("error"))
    print(f"\n  totals: pass={n_pass} partial={n_partial} "
          f"fail={n_fail} error={n_error}")
    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
