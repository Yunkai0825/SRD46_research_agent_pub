"""Analysis-agent results browser routes.

Blueprint: ``/analysis/``

Browses the per-prompt session directories written by the analysis-agent
runner under ``_output/Analysis/<label>/``. Each session
holds:

* ``answer.md``        — final L0 prose
* ``manifest.json``    — L0 run manifest (tool calls + working memory)
* ``verdict.json``     — deterministic pass/partial/fail verdict
* ``run_history.md`` / ``l0_tool_calls.md`` / ``_run.log`` — traces
* ``L1_call_NN/``      — one directory per L1 invocation, each with the
  ``l1_report.md`` analysis, an ``LD/`` validator verdict, and a
  ``solver/`` sub-tree of CSVs + PNG plots.

The index lists every session; the detail page renders the answer, the
per-L1-call analyses, and embeds the solver plots inline.
"""
from __future__ import annotations

import html
import json
import mimetypes
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    send_file,
)

try:
    from ._analysis_timeline import build_agent_timeline
    from ._analysis_status import analysis_outcome, batch_outcomes
except ImportError:  # running as a top-level module (app.py adds routes/ to path)
    from _analysis_timeline import build_agent_timeline
    from _analysis_status import analysis_outcome, batch_outcomes

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_BROWSER_DIR = Path(__file__).absolute().parent.parent          # NIST_SRD46_database_browser/
_PROJECT_ROOT = _BROWSER_DIR.parent                            # SRD46_research_agent/
_PROMPTS_MD = (_PROJECT_ROOT / "NIST_SRD46_db_agent" / "NIST_SRD46_analysis_agent"
               / "_DEBUG_input" / "TEST_PROMPTS.md")
_BENCHMARK_ANALYSIS_ROOT = _PROJECT_ROOT / "_benchmark"


def _path_key(path: Path) -> str:
    return str(path.absolute())


def _freeform_roots() -> List[Path]:
    return [_PROJECT_ROOT / "_output" / "Analysis", _PROJECT_ROOT / "_output"]


def _benchmark_roots() -> List[Path]:
    return [_BENCHMARK_ANALYSIS_ROOT / "Analysis", _BENCHMARK_ANALYSIS_ROOT]


def _lookup_roots() -> List[Path]:
    return _freeform_roots() + _benchmark_roots()


def _root_for_label(label: str) -> Optional[Path]:
    """Return the storage root (freeform variants or eval) that holds ``label``."""
    for root in _lookup_roots():
        if (root / label).is_dir():
            return root
    return None

_VERDICT_BADGE = {
    "pass":         "success",
    "partial":      "warning",
    "skipped_some": "warning",
    "fail":         "danger",
    "supported":    "success",
    "contradicted": "danger",
    "inconclusive": "secondary",
    "unknown":      "secondary",
}

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_markdown_doc(text: str, css_class: str = "md-doc") -> str:
    """Render markdown to HTML with table + fenced-code support.

    Mirrors ``routes/evaluation.py``: falls back to an escaped ``<pre>``
    block when the ``markdown`` package is unavailable.
    """
    if not text:
        return ""
    try:
        import markdown as _md
        body = _md.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    except Exception:
        body = f"<pre>{html.escape(text)}</pre>"
    return f'<div class="{css_class}">{body}</div>'


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return txt[:limit]


_TOOLCALL_TAGS = re.compile(
    r"</?(?:tool_call|answer|summary|reasoning|wait)\s*/?>", re.IGNORECASE
)


def _loads_first_json(text: str) -> Optional[Any]:
    """Parse the first balanced ``{...}`` JSON object found in ``text``."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def _unwrap_record_analysis(text: str) -> Optional[str]:
    """If ``text`` is a raw ``record_analysis`` tool-call, return its markdown.

    When an L1 call hits a hard stop the agent emits its final answer as a
    bare ``{"name": "record_analysis", "arguments": {"analysis_markdown":
    ...}}`` blob instead of clean prose. Pull the markdown back out so it
    renders properly; return ``None`` when ``text`` is not such a blob.
    """
    s = _TOOLCALL_TAGS.sub("", text).strip()
    if "record_analysis" not in s:
        return None
    obj = _loads_first_json(s)
    if isinstance(obj, dict) and obj.get("name") == "record_analysis":
        args = obj.get("arguments") or {}
        md = args.get("analysis_markdown")
        if isinstance(md, str) and md.strip():
            return md
    return None


def _extract_l1_answer(call_dir: Path) -> str:
    """Return the L1 sub-agent's final answer markdown from agent_response.md.

    Slices out just the "Final answer" section (dropping the trailing
    context / system-prompt dump that follows it) and unwraps a
    ``record_analysis`` tool-call blob when the agent emitted one.
    """
    raw = _read_text(call_dir / "agent_response.md")
    if not raw:
        return ""
    body = raw
    marker = "## Final answer (text emitted by the agent)"
    if marker in body:
        body = body.split(marker, 1)[1]
    for end in ("## Final context", "## System Prompt"):
        if end in body:
            body = body.split(end, 1)[0]
    body = body.strip()
    unwrapped = _unwrap_record_analysis(body)
    return unwrapped if unwrapped is not None else body


def _select_l1_report(call_dir: Path) -> str:
    """Select the report that is authoritative for this L1 call.

    Estimation-enabled runs persist deterministic scientific-quality facts in
    ``l1_scientific_quality.json`` and a guarded report in ``l1_report.md``.
    Their raw ``agent_response.md`` remains an audit artifact and may contain
    an unexecuted hard-stop tool call, so it must not override the guarded
    report in the user-facing browser.  Preserve the legacy raw-answer-first
    behavior for calls without the enabled quality record.
    """

    quality = _read_json(call_dir / "l1_scientific_quality.json") or {}
    if quality.get("estimation_enabled") is True:
        guarded = _read_text(call_dir / "l1_report.md")
        if guarded.strip():
            return guarded

    raw_answer = _extract_l1_answer(call_dir)
    if raw_answer.strip():
        return raw_answer
    return _read_text(call_dir / "l1_report.md")


def _select_final_plots(solver_dir: Path, sdir: Path) -> List[str]:
    """Pick only the final diagram(s) for a solver run.

    If the pipeline finished, the converged Pourbaix / speciation PNGs sit
    at the solver-dir root (one per element); show those. Otherwise fall
    back to the most-refined snapshot per element under ``_snapshots/``,
    skipping the intermediate refinement layers.
    """
    if not solver_dir.exists():
        return []
    root_pngs = sorted(p for p in solver_dir.glob("*.png") if p.is_file())
    if root_pngs:
        return [p.relative_to(sdir).as_posix() for p in root_pngs]
    snap_dir = solver_dir / "_snapshots"
    if snap_dir.exists():
        by_element: Dict[str, Path] = {}
        for p in sorted(snap_dir.glob("*.png")):
            if not p.is_file():
                continue
            element = p.stem.rsplit("_", 1)[-1]
            by_element[element] = p  # sorted() => last wins = most refined
        return [p.relative_to(sdir).as_posix() for p in by_element.values()]
    return []


def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_prompt_meta() -> Dict[str, Dict[str, str]]:
    """Map label -> {layer, prompt} by parsing the TEST_PROMPTS.md table."""
    meta: Dict[str, Dict[str, str]] = {}
    text = _read_text(_PROMPTS_MD)
    if not text:
        return meta
    begin, end = "<!-- BEGIN PROMPTS -->", "<!-- END PROMPTS -->"
    if begin in text and end in text:
        text = text.split(begin, 1)[1].split(end, 1)[0]
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or cells[0].lower() in {"#", ""}:
            continue
        if re.fullmatch(r":?-+:?", cells[0]):
            continue
        _idx, layer, label, prompt = cells[0], cells[1], cells[2], cells[3]
        if label:
            meta[label] = {"layer": layer, "prompt": prompt}
    return meta


def _session_dirs(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return sorted(
        d for d in root.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and d.name != "Diagnostics"  # container, never a session
    )


def _latest_batch_summary(root: Path) -> Optional[Dict[str, Any]]:
    if not root.exists():
        return None
    summaries = sorted(root.glob("_batch_summary_*.json"))
    if not summaries:
        return None
    return _read_json(summaries[-1])


def _session_card(label: str, meta: Dict[str, Dict[str, str]], root: Path) -> Dict[str, Any]:
    """Build the summary dict for one session, for the index list."""
    sdir = root / label
    verdict_doc = _read_json(sdir / "verdict.json") or {}
    manifest = _read_json(sdir / "manifest.json") or {}
    answer = _read_text(sdir / "answer.md", limit=400)
    n_l1 = len(list(sdir.glob("L1_call_*")))
    outcome = analysis_outcome(manifest, verdict_doc)
    return {
        "label":      label,
        "layer":      meta.get(label, {}).get("layer", ""),
        "prompt":     meta.get(label, {}).get("prompt", "") or manifest.get("user_request", ""),
        "verdict":    outcome["label"],
        "badge":      outcome["badge"],
        "outcome":    outcome,
        "elapsed_s":  manifest.get("elapsed_s"),
        "iterations": manifest.get("iterations"),
        "timed_out":  manifest.get("timed_out"),
        "n_l1_calls": n_l1,
        "answer_head": answer.strip()[:240],
        "has_answer": (sdir / "answer.md").exists(),
    }


def _safe_target(label: str, relpath: str, root: Path) -> Path:
    """Resolve ``relpath`` within the session dir, rejecting traversal."""
    base = (root / label).resolve()
    if not base.exists():
        abort(404)
    rel = (relpath or "").strip().replace("\\", "/").lstrip("/")
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        abort(403)
    if not target.exists() or not target.is_file():
        abort(404)
    return target


def _collect_l1_calls(sdir: Path, *, show_debug: bool = False) -> List[Dict[str, Any]]:
    """Build the per-L1-call view models for the detail page."""
    calls: List[Dict[str, Any]] = []
    for call_dir in sorted(sdir.glob("L1_call_*")):
        inp = _read_json(call_dir / "input.json") or {}
        # Enabled runs use the persisted, guarded report; legacy calls retain
        # the historical raw-agent-response-first display behavior.
        report_md = _select_l1_report(call_dir)
        ld_doc = _read_json(call_dir / "LD" / "verdict.json") or {}
        # also accept retry-suffixed verdicts if the base is absent
        if not ld_doc:
            for vp in sorted((call_dir / "LD").glob("verdict*.json")) \
                    if (call_dir / "LD").exists() else []:
                ld_doc = _read_json(vp) or {}
        solver_dir = call_dir / "solver"
        plots = _select_final_plots(solver_dir, sdir)
        csvs: List[str] = []
        if solver_dir.exists():
            for p in sorted(solver_dir.rglob("*.csv")):
                if p.is_file():
                    csvs.append(p.relative_to(sdir).as_posix())
        # ``tasks`` is a single brief string; tolerate the legacy list form.
        tasks_raw = inp.get("tasks", "")
        if isinstance(tasks_raw, (list, tuple)):
            tasks_text = "\n".join(str(t) for t in tasks_raw)
        else:
            tasks_text = str(tasks_raw or "")
        # auxiliary docs
        aux: List[Dict[str, str]] = []
        if show_debug:
            for fname in ("agent_response.md", "l1_tool_calls.md"):
                if (call_dir / fname).exists():
                    aux.append({
                        "name": fname,
                        "rel":  (call_dir / fname).relative_to(sdir).as_posix(),
                    })
        verdict = (ld_doc.get("verdict") or "")
        calls.append({
            "name":        call_dir.name,
            "purpose":     inp.get("purpose", ""),
            "tasks_text":  tasks_text,
            "report_html": _render_markdown_doc(report_md),
            "has_report":  bool(report_md.strip()),
            "ld_verdict":  verdict,
            "ld_badge":    _VERDICT_BADGE.get(verdict, "secondary"),
            "ld_hints":    ld_doc.get("hints", []),
            "plots":       plots,
            "csvs":        csvs,
            "aux":         aux,
        })
    return calls


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@analysis_bp.route("/")
def analysis_index():
    """Shared Benchmark analysis runs."""
    return _render_index(_benchmark_roots(), is_freeform=False)


@analysis_bp.route("/freeform/")
def analysis_freeform_index():
    """Freeform analysis runs — live-runner sessions across all buckets."""
    return _render_index(_freeform_roots() + _diagnostics_roots(), is_freeform=True)  # TEMP


@analysis_bp.route("/freeform/<label>/delete", methods=["POST"])
def analysis_freeform_delete(label: str):
    """Delete one active user's freeform analysis session."""
    if Path(label).name != label:
        return jsonify(error="Invalid run identifier."), 400
    for root in _freeform_roots():
        target = root / label
        if not target.is_dir():
            continue
        try:
            if target.resolve().parent != root.resolve():
                return jsonify(error="Invalid run path."), 400
            shutil.rmtree(target)
            return jsonify(ok=True)
        except OSError as exc:
            return jsonify(error=str(exc)), 500
    return jsonify(error="User freeform run not found."), 404


def _render_index(root, is_freeform: bool):
    # Accept a single root or a list of roots from the local result directories.
    roots = root if isinstance(root, (list, tuple)) else [root]
    meta = _load_prompt_meta()
    sessions = []
    seen: set = set()
    any_exists = False
    for r in roots:
        if r.exists():
            any_exists = True
        for d in _session_dirs(r):
            if d.name in seen:
                continue
            seen.add(d.name)
            sessions.append(_session_card(d.name, meta, r))
    # Order by the prompt table when available, else alphabetically.
    order = {label: i for i, label in enumerate(meta.keys())}
    sessions.sort(key=lambda s: order.get(s["label"], 1_000 + ord(s["label"][:1] or "z")))
    batch = None if is_freeform else batch_outcomes(_latest_batch_summary(roots[0]))
    return render_template(
        "analysis_index.html",
        sessions=sessions,
        batch=batch,
        output_exists=any_exists,
        is_freeform=is_freeform,
    )


@analysis_bp.route("/<label>")
def analysis_detail(label: str):
    root = _root_for_label(label)
    if root is None:
        abort(404)
    sdir = root / label
    is_freeform = _path_key(root) != _path_key(_BENCHMARK_ANALYSIS_ROOT)
    meta = _load_prompt_meta().get(label, {})
    verdict_doc = _read_json(sdir / "verdict.json") or {}
    manifest = _read_json(sdir / "manifest.json") or {}
    outcome = analysis_outcome(manifest, verdict_doc)
    show_debug = True

    working_memory = (manifest.get("working_memory") or {}) if show_debug else {}
    tool_summary = (manifest.get("tool_call_summary") or []) if show_debug else []

    # trace docs available at the session root
    traces: List[Dict[str, str]] = []
    if show_debug:
        for fname in ("answer.md", "run_history.md", "run_stats.md",
                      "l0_tool_calls.md", "_run.log"):
            if (sdir / fname).exists():
                traces.append({"name": fname, "rel": fname})

    return render_template(
        "analysis_detail.html",
        label=label,
        is_freeform=is_freeform,
        layer=meta.get("layer", ""),
        prompt=meta.get("prompt", "") or manifest.get("user_request", ""),
        verdict=outcome["label"],
        verdict_badge=outcome["badge"],
        outcome=outcome,
        verdict_notes=verdict_doc.get("notes") or [],
        answer_html=_render_markdown_doc(_read_text(sdir / "answer.md")),
        has_answer=(sdir / "answer.md").exists(),
        manifest=manifest,
        working_memory=working_memory,
        working_memory_json=json.dumps(working_memory, indent=2, default=str),
        show_debug=show_debug,
        tool_summary=tool_summary,
        l1_calls=_collect_l1_calls(sdir, show_debug=show_debug),
        traces=traces,
        timeline=build_agent_timeline(sdir) if show_debug else None,
    )


@analysis_bp.route("/<label>/file/<path:relpath>")
def analysis_file(label: str, relpath: str):
    """Serve a file from a session directory.

    Images render inline; text files (CSV / MD / JSON / LOG) are returned
    as ``text/plain`` so the browser displays them rather than downloading.
    """
    root = _root_for_label(label)
    if root is None:
        abort(404)
    target = _safe_target(label, relpath, root)
    suffix = target.suffix.lower()
    if suffix in _IMAGE_EXT:
        return send_file(target)
    if suffix in {".csv", ".md", ".json", ".log", ".txt", ".jsonl"}:
        return send_file(target, mimetype="text/plain")
    mime, _ = mimetypes.guess_type(str(target))
    return send_file(target, mimetype=mime or "application/octet-stream")
