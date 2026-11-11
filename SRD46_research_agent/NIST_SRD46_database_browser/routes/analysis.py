"""Analysis-agent results browser routes.

Blueprint: ``/analysis/``

Browses the per-prompt session directories written by the analysis-agent
runner under ``_outputs_user/<bucket>/SRD46/Analysis/<label>/``. Each session
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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
)

try:
    from ._analysis_timeline import build_agent_timeline
    from ._analysis_timing import analysis_timing
    from ._analysis_status import analysis_outcome, batch_outcomes
    from .debug_mode import is_debug_mode
except ImportError:  # running as a top-level module (app.py adds routes/ to path)
    from _analysis_timeline import build_agent_timeline
    from _analysis_timing import analysis_timing
    from _analysis_status import analysis_outcome, batch_outcomes
    from debug_mode import is_debug_mode

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_BROWSER_DIR = Path(__file__).absolute().parent.parent          # NIST_SRD46_database_browser/
_PROJECT_ROOT = _BROWSER_DIR.parent                            # SRD46_research_agent/
_REPO_ROOT = _PROJECT_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import output_paths as _op
from zip_images.output_zips.output_reader import output_path
from ._output_archives import send_output_file

_PROMPTS_MD = _op.SRD46_ANALYSIS_PROMPTS_FILE


def _io_path(path: Path) -> Path:
    """Use Windows extended paths only for filesystem access."""
    text = str(path.absolute())
    if sys.platform == "win32" and not text.startswith("\\\\?\\"):
        text = "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
    return output_path(Path(text))


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


_BENCHMARK_ANALYSIS_ROOT = _op.srd46_analysis_dir(
    bucket=_op.BENCHMARK_BUCKET
)


def _freeform_roots() -> List[Path]:
    """Active-user roots holding live ("freeform") analysis runs."""
    sources = _op.iter_srd46_analysis_roots(
        include_benchmark=False,
        include_temp=True,
        user_only=True,
    )
    return [output_path(src["path"]) for src in sources]


def _benchmark_roots() -> List[Path]:
    """Read-only Benchmark roots for curated/shared analysis runs."""
    _op.ensure_benchmark_seeded()
    return [output_path(_BENCHMARK_ANALYSIS_ROOT)]


def _diagnostics_roots() -> List[Path]:
    """Expose locally configured diagnostics sessions read-only."""
    root = _op.diagnostic_dir(
        _op.DB_SRD46, "analysis", "analysis_agent"
    )
    return [output_path(root)] if output_path(root).is_dir() else []


def _lookup_roots() -> List[Path]:
    sources = _op.iter_srd46_analysis_roots(
        include_benchmark=True,
        include_temp=True,
    )
    # Prefer locally generated sessions when labels are shared with examples.
    return _diagnostics_roots() + [output_path(src["path"]) for src in sources]



_MODEL_FOLDERS = frozenset({"Opus4.7", "GPT-5.5"})

# A run folder carries at least one of these files at its top level.  A folder
# that carries none (and no L1_call_* folder) is a model container such as
# "Sonnet5.5"; the two names above count as containers even while empty.
_RUN_MARKERS = ("manifest.json", "_run.log", "answer.md", "verdict.json", "run_history.jsonl")


def _is_model_folder(path: Path) -> bool:
    """A model container directly under a root: a folder that is not itself a run."""
    if path.name in _MODEL_FOLDERS:
        return True
    if path.name.startswith("_") or path.name == _op.DIAGNOSTICS_DIRNAME:
        return False
    try:
        if not path.is_dir():
            return False
        if any((path / marker).exists() for marker in _RUN_MARKERS):
            return False
        return not any(path.glob("L1_call_*"))
    except OSError:
        return False


def _valid_session_label(label: str) -> bool:
    """A direct run or one model/run pair (syntax; the container test is in _session_path)."""
    if not isinstance(label, str) or "\\" in label or ":" in label:
        return False
    parts = label.split("/")
    if any(not part or part in {".", ".."} or part.startswith("_") for part in parts):
        return False
    if len(parts) == 1:
        return parts[0] not in _MODEL_FOLDERS and parts[0] != _op.DIAGNOSTICS_DIRNAME
    return 2 <= len(parts) <= 4 and parts[-1] not in _MODEL_FOLDERS


def _resolved_compare_path(path: Path) -> Path:
    """Normalize Windows extended prefixes only after resolving linked paths."""
    text = str(path.resolve())
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return Path(text)


def _session_path(root: Path, label: str) -> Optional[Path]:
    if not _valid_session_label(label):
        return None
    target = _io_path(root / label)
    try:
        _resolved_compare_path(target).relative_to(_resolved_compare_path(root))
    except (OSError, ValueError):
        return None
    pieces = label.split("/")
    if len(pieces) == 2:
        if not _is_model_folder(root / pieces[0]):
            return None  # the first part must be a model container
    elif len(pieces) > 2:
        if target not in _session_dirs(root):
            return None
    elif _is_model_folder(target):
        return None  # a container is never a session
    return target if target.is_dir() else None


def _root_for_label(label: str) -> Optional[Path]:
    """Return a configured root containing the exact model-qualified run label."""
    for root in _lookup_roots():
        if _session_path(root, label) is not None:
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
    "llm_execution_failure": "danger",
}

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PHASE_SUFFIX_LINK = re.compile(r'<a href="((?:s|aq|l|g)(?:,[^"]*)?)">(.*?)</a>')


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
        # "[Fe(OH)3](s)" parses as a link to "s": give the formula back its text.
        body = _PHASE_SUFFIX_LINK.sub(r"[\2](\1)", body)
    except Exception:
        body = f"<pre>{html.escape(text)}</pre>"
    return f'<div class="{css_class}">{body}</div>'


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        txt = _io_path(path).read_text(encoding="utf-8", errors="replace")
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
    report in the user-facing browser. Calls without the enabled quality
    record use the raw answer first.
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
        return json.loads(_io_path(path).read_text(encoding="utf-8"))
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
    """Discover direct sessions and only manifest-declared campaign outputs."""
    if not root.exists():
        return []
    result = []
    def inside(path):
        try:
            _resolved_compare_path(path).relative_to(_resolved_compare_path(root))
        except (ValueError, OSError):
            return False
        return True
    def add(path):
        if inside(path) and _io_path(path).is_dir():
            result.append(path)
    def filename(value):
        return isinstance(value, str) and value not in {"", ".", ".."} and not any(char in value for char in "/\\:")
    for directory in sorted(root.iterdir()):
        if not inside(directory) or not directory.is_dir() or directory.name.startswith("_") or directory.name == _op.DIAGNOSTICS_DIRNAME:
            continue
        if directory.name == "batches":
            for campaign in sorted(directory.iterdir()):
                if not inside(campaign) or not campaign.is_dir():
                    continue
                doc = _read_json(campaign / "campaign.json") or {}
                if not isinstance(doc, dict) or doc.get("schema") != "srd46-portable-staged-batch/v1":
                    continue
                for item in doc.get("items", []) if isinstance(doc.get("items"), list) else []:
                    label = item.get("id") if isinstance(item, dict) else None
                    if filename(label) and re.fullmatch(r"L[1-4]_\d+_[A-Za-z0-9_]+", label):
                        mapping=doc.get('run_directories',{})
                        folder=mapping.get(label) if isinstance(mapping,dict) else None
                        if filename(folder) and re.fullmatch(r'L[1-4]_\d+_\d{8}',folder):
                            add(campaign / "runs" / folder)
        elif (directory / "ff1_campaign.json").is_file():
            doc = _read_json(directory / "ff1_campaign.json") or {}
            if not isinstance(doc, dict) or doc.get("schema") != "srd46-ff1-model-comparison/v1":
                continue
            for row in doc.get("runs", {}).values() if isinstance(doc.get("runs"), dict) else []:
                for attempt in row.get("attempts", []) if isinstance(row, dict) and isinstance(row.get("attempts"), list) else []:
                    label = attempt.get("session_dir") if isinstance(attempt, dict) else None
                    parts=label.split('/') if isinstance(label,str) else []
                    if len(parts)==2 and all(filename(part) for part in parts) and re.fullmatch(r'FF_1_\d{8}',parts[1]):
                        add(directory / label)
        elif _is_model_folder(directory):
            for child in sorted(directory.iterdir()):
                if not _is_model_folder(child) and not child.name.startswith("_"):
                    add(child)
        else:
            add(directory)
    return sorted(set(result))


def _latest_batch_summary(root: Path) -> Optional[Dict[str, Any]]:
    if not root.exists():
        return None
    summaries = sorted(root.glob("_batch_summary_*.json"))
    if not summaries:
        return None
    return _read_json(summaries[-1])


def _prompt_key(sdir: Path, meta: Dict[str, Dict[str, str]]) -> str:
    """Resolve catalog identity from saved metadata or an unambiguous compact ID."""
    saved_id = _read_text(sdir / "debug_prompt_id.txt", limit=400).strip()
    compact = re.fullmatch(r"(L[1-4]_\d+|FF_\d+)_\d{8}", sdir.name)
    if saved_id:
        if saved_id not in meta:
            return ""
        if compact and not (saved_id == compact[1] or saved_id.startswith(compact[1] + "_")):
            return ""
        return saved_id
    if sdir.name in meta:
        return sdir.name
    if compact:
        matches = [key for key in meta if key == compact[1] or key.startswith(compact[1] + "_")]
        if len(matches) == 1:
            return matches[0]
    return ""


_LIVE_RUNNING_S = 15 * 60    # newest write this recent: the run is still going
_LIVE_QUIET_S = 2 * 60 * 60  # ... this old: it may hang; older: it stopped without a verdict


def _newest_write(sdir: Path):
    """(mtime, relative path) of the newest write in a run: its own files, each L1 call
    folder, and the files one level inside the call's stage folders (a few dozen stats,
    never a full walk; the solver writes its progress files under L1_call_*/solver)."""
    newest = None

    def look(path: Path) -> None:
        nonlocal newest
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if newest is None or mtime >= newest[0]:   # on a tie the deeper, later-visited file wins
            newest = (mtime, path.relative_to(sdir).as_posix() if path != sdir else "")

    look(sdir)
    try:
        for child in sdir.iterdir():
            look(child)
            if child.is_dir() and child.name.startswith("L1_call_"):
                for sub in child.iterdir():
                    look(sub)
                    if sub.is_dir() and sub.name in ("LC1", "LC2", "LC3", "LD", "solver"):
                        for leaf in sub.iterdir():
                            look(leaf)
    except OSError:
        pass
    return newest


def _liveness(sdir: Path, has_verdict: bool) -> Dict[str, Any]:
    """State of a run without a verdict, from its newest write; {} once a verdict exists."""
    if has_verdict:
        return {}
    newest = _newest_write(sdir)
    if newest is None:
        return {"state": "incomplete", "label": "incomplete", "badge": "secondary",
                "age_s": None, "note": "no verdict.json"}
    age = max(0.0, time.time() - newest[0])
    minutes = int(age // 60)
    where = f"last write {newest[1]}" if newest[1] else "last write in the run folder"
    if age <= _LIVE_RUNNING_S:
        return {"state": "running", "label": f"running \u00b7 {minutes} min ago", "badge": "info",
                "age_s": age, "note": f"no verdict.json yet \u00b7 {where}"}
    if age <= _LIVE_QUIET_S:
        return {"state": "quiet", "label": f"no write for {minutes} min", "badge": "warning",
                "age_s": age, "note": f"no verdict.json yet \u00b7 {where}"}
    return {"state": "incomplete", "label": "incomplete", "badge": "secondary",
            "age_s": age, "note": f"no verdict.json \u00b7 {where}, {minutes // 60} h ago"}


def _session_card(label: str, meta: Dict[str, Dict[str, str]], root: Path) -> Dict[str, Any]:
    """Build the summary dict for one session, for the index list."""
    sdir = root / label
    prompt_key = _prompt_key(sdir, meta)
    verdict_doc = _read_json(sdir / "verdict.json") or {}
    manifest = _read_json(sdir / "manifest.json") or {}
    answer = _read_text(sdir / "answer.md", limit=400)
    n_l1 = len(list(sdir.glob("L1_call_*")))
    live = _liveness(sdir, bool(verdict_doc))
    outcome = analysis_outcome(manifest, verdict_doc)
    timing = analysis_timing(sdir, manifest)
    return {
        "label":      label,
        "prompt_key": prompt_key,
        "model":      label.split("/", 1)[0] if "/" in label else "",
        "live":       live,
        "layer":      meta.get(prompt_key, {}).get("layer", ""),
        "prompt":     meta.get(prompt_key, {}).get("prompt", "") or manifest.get("user_request", ""),
        "verdict":    live["label"] if live else outcome["label"],
        "badge":      live["badge"] if live else outcome["badge"],
        "outcome":    outcome,
        "elapsed_s":  timing["analysis_s"],
        "timing_note": timing["note"],
        "iterations": manifest.get("iterations"),
        "timed_out":  manifest.get("timed_out"),
        "n_l1_calls": n_l1,
        "answer_head": answer.strip()[:240],
        "has_answer": (sdir / "answer.md").exists(),
        "archived": output_path(sdir).archived,
    }


def _safe_target(label: str, relpath: str, root: Path) -> Path:
    """Resolve a file within one validated run, rejecting traversal and links out."""
    session = _session_path(root, label)
    if session is None:
        abort(404)
    base = session.resolve()
    rel = (relpath or "").strip().replace("\\", "/").lstrip("/")
    target = (base / rel).resolve()
    try:
        _resolved_compare_path(target).relative_to(_resolved_compare_path(base))
    except (OSError, ValueError):
        abort(403)
    if not target.exists() or not target.is_file():
        abort(404)
    return target


def _collect_l1_calls(sdir: Path, *, show_debug: bool = False) -> List[Dict[str, Any]]:
    """Build the per-L1-call view models for the detail page."""
    calls: List[Dict[str, Any]] = []
    for call_dir in sorted(sdir.glob("L1_call_*")):
        inp = _read_json(call_dir / "input.json") or {}
        # Runs with estimation enabled use the persisted, guarded report;
        # other calls use the raw agent response first.
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
    return _render_index(_freeform_roots() + _diagnostics_roots(), is_freeform=True)


@analysis_bp.route("/freeform/<path:label>/delete", methods=["POST"])
def analysis_freeform_delete(label: str):
    """Delete one active user's exact direct or model-qualified freeform run."""
    if not _valid_session_label(label):
        return jsonify(error="Invalid run identifier."), 400
    for root in _freeform_roots():
        target = _session_path(root, label)
        if target is None:
            continue
        if output_path(target).archived:
            return jsonify(error="Archived runs are read-only in the browser."), 409
        try:
            shutil.rmtree(target)
            return jsonify(ok=True)
        except OSError as exc:
            return jsonify(error=str(exc)), 500
    return jsonify(error="User freeform run not found."), 404


def _render_index(root, is_freeform: bool):
    # Accept a single root or a list of roots from output_paths.py.
    roots = root if isinstance(root, (list, tuple)) else [root]
    meta = _load_prompt_meta()
    sessions = []
    seen: set = set()
    any_exists = False
    for r in roots:
        if r.exists():
            any_exists = True
        for d in _session_dirs(r):
            label = d.relative_to(r).as_posix()
            if label in seen:
                continue
            seen.add(label)
            sessions.append(_session_card(label, meta, r))
    # Order by the prompt table when available, else alphabetically.
    order = {label: i for i, label in enumerate(meta.keys())}
    sessions.sort(key=lambda s: order.get(s["prompt_key"], 1_000 + ord(s["label"][:1] or "z")))
    models = sorted({s["model"] for s in sessions if s["model"]})
    filter_model = (request.args.get("model") or "").strip()
    filter_q = (request.args.get("q") or "").strip()
    if filter_model:
        sessions = [s for s in sessions if s["model"] == filter_model]
    if filter_q:
        needle = filter_q.casefold()
        sessions = [s for s in sessions
                    if needle in s["label"].casefold()
                    or needle in (s["prompt"] or "").casefold()
                    or needle in (s["prompt_key"] or "").casefold()]
    any_running = any(s["live"].get("state") == "running" for s in sessions)
    _mark_references(sessions, is_freeform)
    batch = None if is_freeform else batch_outcomes(_latest_batch_summary(roots[0]))
    return render_template(
        "analysis_index.html",
        sessions=sessions,
        models=models,
        filter_model=filter_model,
        filter_q=filter_q,
        any_running=any_running,
        batch=batch,
        output_exists=any_exists,
        is_freeform=is_freeform,
    )


@analysis_bp.route("/<path:label>")
def analysis_detail(label: str):
    root = _root_for_label(label)
    if root is None:
        abort(404)
    sdir = root / label
    is_freeform = _path_key(root) != _path_key(_BENCHMARK_ANALYSIS_ROOT)
    catalog = _load_prompt_meta()
    meta = catalog.get(_prompt_key(sdir, catalog), {})
    verdict_doc = _read_json(sdir / "verdict.json") or {}
    manifest = _read_json(sdir / "manifest.json") or {}
    outcome = analysis_outcome(manifest, verdict_doc)
    show_debug = is_debug_mode()

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
        live=_liveness(sdir, bool(verdict_doc)),
        verdict_notes=verdict_doc.get("notes") or [],
        answer_html=_render_markdown_doc(_read_text(sdir / "answer.md")),
        has_answer=(sdir / "answer.md").exists(),
        manifest=manifest,
        timing=analysis_timing(sdir, manifest),
        working_memory=working_memory,
        working_memory_json=json.dumps(working_memory, indent=2, default=str),
        show_debug=show_debug,
        tool_summary=tool_summary,
        l1_calls=_collect_l1_calls(sdir, show_debug=show_debug),
        traces=traces,
        timeline=build_agent_timeline(sdir) if show_debug else None,
        **_answer_context(root, label, _prompt_key(sdir, catalog)),
        **_excerpt_context(sdir),
    )


@analysis_bp.route("/<path:label>/file/<path:relpath>")
def analysis_file(label: str, relpath: str):
    """Serve a file from a session directory.

    Images render inline; text files (CSV / MD / JSON / LOG) are returned
    as ``text/plain`` so the browser displays them rather than downloading.
    """
    root = _root_for_label(label)
    if root is None:
        abort(404)
    if not is_debug_mode() and Path(relpath).name in {
        "run_history.md",
        "run_stats.md",
        "l0_tool_calls.md",
        "l1_tool_calls.md",
        "agent_response.md",
        "_run.log",
        "working_memory.json",
        "_working_memory.md",
        "working_memory.md",
    }:
        abort(404)
    target = _safe_target(label, relpath, root)
    suffix = target.suffix.lower()
    if suffix in _IMAGE_EXT:
        return send_output_file(target)
    if suffix in {".csv", ".md", ".json", ".log", ".txt", ".jsonl"}:
        return send_output_file(target, mimetype="text/plain")
    mime, _ = mimetypes.guess_type(str(target))
    return send_output_file(target, mimetype=mime or "application/octet-stream")


# ---------------------------------------------------------------------------
# Answer matrix, compare view and reference-answer selection
# ---------------------------------------------------------------------------
# One prompt, several answers: curated Benchmark runs ("bench:<label>"), the
# user's framework runs ("user:<label>") and Claude-web reference answers
# ("web:<config>/<folder>").  The chosen reference per prompt is stored in the
# active user's bucket file (_answer_selection.json); see _analysis_answers.py.

try:
    from . import _analysis_answers as _ans
except ImportError:  # running as a top-level module
    import _analysis_answers as _ans

from flask import url_for

_ANSWERS_CACHE_S = 60.0          # the scan stats every run folder: keep it for a minute
_answers_cache: Dict[str, Any] = {"at": 0.0, "data": None}


def _selection_write_root() -> Path:
    """The active user's stored analysis root: the only place the browser writes to."""
    return Path(_op.srd46_analysis_dir(stored=True, bucket=_op.active_bucket()))


def _references() -> Dict[str, Dict[str, Any]]:
    """pid -> reference entry; the user's own file wins over a Benchmark default."""
    return _ans.merged_references([_BENCHMARK_ANALYSIS_ROOT], _selection_write_root())


def _web_parsed_roots() -> List[Path]:
    roots: List[Path] = []
    seen: set = set()
    for root in _benchmark_roots() + _freeform_roots():
        parsed = _ans.web_parsed_dir(root)
        key = _path_key(parsed)
        if key in seen or not parsed.is_dir():
            continue
        seen.add(key)
        roots.append(parsed)
    return roots


def _is_benchmark_root(root: Path) -> bool:
    return _path_key(root) == _path_key(_BENCHMARK_ANALYSIS_ROOT)


def _source_of(root: Path, label: str):
    """(kind, source id, source name) of a framework run."""
    model = label.split("/", 1)[0] if "/" in label else ""
    if _is_benchmark_root(root):
        return ("bench", f"bench:{model}", model) if model else ("bench", "bench", "Benchmark")
    return "user", f"user:{model}", model or "your runs"


def _run_sort_key(label: str) -> str:
    name = label.rsplit("/", 1)[-1]
    match = re.search(r"_(\d{8})$", name)
    return (match.group(1) if match else "00000000") + " " + name


def _run_answer(root: Path, label: str, meta: Dict[str, Dict[str, str]],
                refs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """One framework run as an answer chip (matrix, switchers, compare header)."""
    card = _session_card(label, meta, root)
    kind, source_id, source_name = _source_of(root, label)
    pid = _ans.short_pid(card["prompt_key"]) or _ans.short_pid(label.rsplit("/", 1)[-1])
    answer_id = f"{kind}:{label}"
    ref = refs.get(pid) or {}
    return {
        "id": answer_id, "kind": kind, "source_id": source_id, "source_name": source_name,
        "label": label, "pid": pid, "prompt_key": card["prompt_key"], "layer": card["layer"],
        "url": url_for("analysis.analysis_detail", label=label),
        "verdict": card["verdict"], "badge": card["badge"], "outcome": card["outcome"],
        "live": card["live"], "elapsed_s": card["elapsed_s"], "has_answer": card["has_answer"],
        "timing_note": card["timing_note"],
        "chip": _ans.chip_text(label), "sort_key": _run_sort_key(label),
        "is_reference": ref.get("answer") == answer_id, "prompt": card["prompt"], "web": None,
    }


def _web_answer(config: str, folder: Path, refs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """One Claude-web reference answer as an answer chip."""
    fm = _ans.web_front_matter(folder)
    timing = _aw.solver_excluded_timing(folder.parent.parent, config, fm["pid"])
    answer_id = f"web:{config}/{folder.name}"
    ref = refs.get(fm["pid"]) or {}
    return {
        "id": answer_id, "kind": "web", "source_id": f"web:{config}",
        "source_name": _ans.web_source_name(config), "label": f"{config}/{folder.name}",
        "pid": fm["pid"], "prompt_key": "", "layer": "",
        "url": url_for("analysis.analysis_web_answer", config=config, folder=folder.name),
        "verdict": "web answer", "badge": "web", "outcome": {}, "live": {},
        "elapsed_s": timing["elapsed_s"], "timing_note": timing["note"], "has_answer": True,
        "chip": (fm["run"] or "web").replace("effort-", ""), "sort_key": fm["started"] or "",
        "is_reference": ref.get("answer") == answer_id, "prompt": fm["title"], "web": fm,
    }


def _all_answers(refresh: bool = False) -> Dict[str, Any]:
    """Every answer of every source (cached for a minute): answers, sources, catalog, references."""
    now = time.time()
    cached = _answers_cache["data"]
    if cached is not None and not refresh and now - _answers_cache["at"] < _ANSWERS_CACHE_S:
        return cached
    meta = _load_prompt_meta()
    refs = _references()
    answers: List[Dict[str, Any]] = []
    sources: Dict[str, Dict[str, Any]] = {}

    def add(answer: Dict[str, Any]) -> None:
        answers.append(answer)
        src = sources.setdefault(answer["source_id"], {
            "id": answer["source_id"], "kind": answer["kind"], "name": answer["source_name"], "n": 0})
        src["n"] += 1

    seen: set = set()
    for group_roots, kind in ((_benchmark_roots(), "bench"),
                              (_freeform_roots() + _diagnostics_roots(), "user")):
        for root in group_roots:
            for sdir in _session_dirs(root):
                label = sdir.relative_to(root).as_posix()
                if (kind, label) in seen:
                    continue
                seen.add((kind, label))
                add(_run_answer(root, label, meta, refs))
    for parsed in _web_parsed_roots():
        for config in _ans.web_configs(parsed):
            for folder in _ans.web_answer_dirs(parsed, config):
                if ("web", f"{config}/{folder.name}") in seen:
                    continue
                seen.add(("web", f"{config}/{folder.name}"))
                add(_web_answer(config, folder, refs))
    order = {"bench": 0, "user": 1, "web": 2}
    source_list = sorted(sources.values(), key=lambda s: (order[s["kind"]], s["name"].casefold()))
    data = {"answers": answers, "sources": source_list, "catalog": meta, "references": refs, "at": now}
    _answers_cache.update(at=now, data=data)
    return data


def _invalidate_answers() -> None:
    _answers_cache.update(at=0.0, data=None)


def _answers_for_pid(pid: str, data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    data = data or _all_answers()
    return [a for a in data["answers"] if pid and a["pid"] == pid]


def _find_answer(answer_id: str):
    """(kind, root, path) of an answer that exists on disk, else None."""
    parsed_id = _ans.parse_answer_id(answer_id)
    if parsed_id is None:
        return None
    kind, rest = parsed_id
    if kind == "web":
        config, folder = rest.split("/", 1)
        for parsed in _web_parsed_roots():
            path = parsed / config / folder
            if path.is_dir() and (path / "final_answer.md").is_file():
                return kind, parsed, path
        return None
    roots = _benchmark_roots() if kind == "bench" else _freeform_roots() + _diagnostics_roots()
    for root in roots:
        path = _session_path(root, rest)
        if path is not None:
            return kind, root, path
    return None


def _answer_view(answer_id: str) -> Optional[Dict[str, Any]]:
    """Everything the compare view shows for one answer: chip fields plus the rendered answer and plots."""
    found = _find_answer(answer_id)
    if found is None:
        return None
    kind, root, path = found
    refs = _references()
    if kind == "web":
        config, folder_name = path.parent.name, path.name
        view = _web_answer(config, path, refs)

        def file_url(name: str) -> str:
            return url_for("analysis.analysis_web_file", config=config, folder=folder_name, relpath=name)

        md = _ans.strip_front_matter(_read_text(path / "final_answer.md"))
        view.update({
            "answer_html": _render_markdown_doc(_ans.rewrite_relative_links(md, path, file_url)),
            "plots": [file_url(n) for n in view["web"]["images"]],
            "html_files": [(n, file_url(n)) for n in view["web"]["html_files"]],
            "l1": [],
        })
        return view
    label = _ans.parse_answer_id(answer_id)[1]
    view = _run_answer(root, label, _load_prompt_meta(), refs)
    calls = _collect_l1_calls(path)
    view.update({
        "answer_html": _render_markdown_doc(_read_text(path / "answer.md")),
        "plots": [url_for("analysis.analysis_file", label=label, relpath=p) for c in calls for p in c["plots"]],
        "html_files": [],
        "l1": [{"name": c["name"], "ld_verdict": c["ld_verdict"], "ld_badge": c["ld_badge"]} for c in calls],
    })
    return view


def _answer_context(root: Path, label: str, pid_hint: str = "") -> Dict[str, Any]:
    """Switcher data of a detail page: this answer, its prompt, the other answers and the reference."""
    kind, _source_id, _source_name = _source_of(root, label)
    answer_id = f"{kind}:{label}"
    data = _all_answers()
    me = next((a for a in data["answers"] if a["id"] == answer_id), None)
    pid = (me or {}).get("pid") or _ans.short_pid(pid_hint) or _ans.short_pid(label.rsplit("/", 1)[-1])
    siblings = [a for a in _answers_for_pid(pid, data) if a["id"] != answer_id]
    ref = data["references"].get(pid) or {}
    return {
        "answer_id": answer_id, "pid": pid, "me": me, "siblings": siblings,
        "reference": ref, "is_reference": ref.get("answer") == answer_id,
        "reference_answer": next((a for a in data["answers"] if a["id"] == ref.get("answer")), None) if ref else None,
        "matrix_url": url_for("analysis.analysis_matrix"),
    }


def _mark_references(sessions: List[Dict[str, Any]], is_freeform: bool) -> None:
    """Flag the index cards that are the reference answer of their prompt."""
    refs = _references()
    prefix = "user:" if is_freeform else "bench:"
    for s in sessions:
        pid = _ans.short_pid(s["prompt_key"]) or _ans.short_pid(s["label"].rsplit("/", 1)[-1])
        s["is_reference"] = bool(refs) and (refs.get(pid) or {}).get("answer") == prefix + s["label"]


def _matrix_rows(data: Dict[str, Any]):
    """(rows, other): catalog rows with their answers per source; answers without a prompt id."""
    rows = _ans.catalog_rows(data["catalog"])
    by_pid = {r["pid"]: r for r in rows}
    other: List[Dict[str, Any]] = []
    for a in data["answers"]:
        if not a["pid"]:
            other.append(a)
            continue
        row = by_pid.get(a["pid"])
        if row is None:   # carries a prompt id that is not in the catalog (an extra FF_n, say)
            row = {"pid": a["pid"], "key": "", "layer": a["layer"] or a["pid"].split("_")[0],
                   "title": (a["prompt"] or "")[:90], "prompt": a["prompt"] or "", "extra": True}
            by_pid[a["pid"]] = row
            rows.append(row)
        row.setdefault("cells", {}).setdefault(a["source_id"], []).append(a)
    answers_by_id = {a["id"]: a for a in data["answers"]}
    for row in rows:
        cells = row.setdefault("cells", {})
        for items in cells.values():
            items.sort(key=lambda a: a["sort_key"], reverse=True)   # newest first
        row["n"] = sum(len(v) for v in cells.values())
        ref = data["references"].get(row["pid"]) or {}
        row["reference"] = ref
        row["reference_answer"] = answers_by_id.get(ref.get("answer")) if ref else None
        labels = " ".join(a["label"] for items in cells.values() for a in items)
        row["search_text"] = " ".join((row["pid"], row.get("layer") or "", row["title"], row["prompt"], labels)).casefold()
    return rows, other


def _ago(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 90:
        return f"{seconds} s"
    return f"{seconds // 60} min"


@analysis_bp.route("/matrix/")
def analysis_matrix():
    """Every answer of every prompt: one row per catalog prompt, one column per source."""
    data = _all_answers(refresh=request.args.get("refresh") == "1")
    filter_layer = (request.args.get("layer") or "").strip().upper()
    filter_q = (request.args.get("q") or "").strip()
    cols = [c for c in request.args.getlist("col") if c]
    min_two = request.args.get("min2") == "1"
    show_empty = request.args.get("empty") == "1"
    ref_only = request.args.get("refonly") == "1"
    rows, other = _matrix_rows(data)
    n_rows_total = len(rows)
    layers = sorted({(r.get("layer") or "").upper() for r in rows if r.get("layer")},
                    key=lambda l: ({"DIAG": 0, "MULTI": 1, "HYPO": 2, "HALL": 3}.get(l, 9), l))
    if filter_layer:
        rows = [r for r in rows if (r.get("layer") or "").upper() == filter_layer]
    if filter_q:
        needle = filter_q.casefold()
        rows = [r for r in rows if needle in r["search_text"]]
    if min_two:
        rows = [r for r in rows if r["n"] >= 2]
    if ref_only:
        rows = [r for r in rows if not r["reference_answer"]]
    all_sources = data["sources"]
    selected_cols = set(cols) if cols else {s["id"] for s in all_sources}
    sources = [s for s in all_sources if s["id"] in selected_cols]
    counts = {s["id"]: sum(len(r["cells"].get(s["id"], [])) for r in rows) for s in all_sources}
    if not show_empty:
        sources = [s for s in sources if counts[s["id"]]]
    query = {}
    if filter_layer:
        query["layer"] = filter_layer
    if filter_q:
        query["q"] = filter_q
    if cols:
        query["col"] = cols
    for flag, name in ((min_two, "min2"), (show_empty, "empty"), (ref_only, "refonly")):
        if flag:
            query[name] = 1
    return render_template(
        "analysis_matrix.html",
        rows=rows, other=other, sources=sources, all_sources=all_sources, counts=counts,
        selected_cols=selected_cols, layers=layers, filter_layer=filter_layer, filter_q=filter_q,
        min_two=min_two, show_empty=show_empty, ref_only=ref_only, query=query,
        n_rows_total=n_rows_total, n_answers=sum(counts[s["id"]] for s in sources),
        scanned_ago=_ago(time.time() - data["at"]),
    )


@analysis_bp.route("/compare/")
def analysis_compare():
    """Two or three answers of one prompt side by side (?a=<id>&a=<id>...)."""
    ids: List[str] = []
    for value in request.args.getlist("a"):
        for part in value.split(","):
            if part and part not in ids:
                ids.append(part)
    ids = ids[:3]
    views = [v for v in (_answer_view(a) for a in ids) if v is not None]
    if not views:
        abort(404)
    missing = [a for a in ids if a not in {v["id"] for v in views}]
    pids = {v["pid"] for v in views}
    same_prompt = len(pids) == 1
    pid = views[0]["pid"] if same_prompt else ""
    data = _all_answers()
    options = _answers_for_pid(pid, data) if same_prompt else []
    present = [v["id"] for v in views]
    swap_urls = []
    for i in range(len(views)):
        urls = {}
        for o in options:
            replaced = list(present)
            replaced[i] = o["id"]
            urls[o["id"]] = url_for("analysis.analysis_compare", a=replaced)
        swap_urls.append(urls)
    row = next((r for r in _ans.catalog_rows(data["catalog"]) if r["pid"] == pid), {})
    return render_template(
        "analysis_compare.html",
        views=views, missing=missing, same_prompt=same_prompt, pid=pid,
        prompt=row.get("prompt", "") or (views[0]["prompt"] if same_prompt else ""),
        layer=row.get("layer", ""), options=options, swap_urls=swap_urls,
        reference=(data["references"].get(pid) or {}) if pid else {},
        full=request.args.get("full") == "1",
    )


@analysis_bp.route("/reference/")
def analysis_reference_list():
    """The merged reference choices (JSON)."""
    return jsonify(references=_references(), file=str(_ans.selection_path(_selection_write_root())))


@analysis_bp.route("/reference/<pid>", methods=["POST"])
def analysis_reference_set(pid: str):
    """Store {"answer": "<id>"} as the reference of a prompt, or {"answer": null} to clear it."""
    if not _ans.valid_pid(pid):
        return jsonify(error="Not a prompt id."), 400
    body = request.get_json(silent=True) or {}
    answer_id = body.get("answer")
    if answer_id is not None:
        if _ans.parse_answer_id(answer_id) is None:
            return jsonify(error="Not an answer id."), 400
        if _find_answer(answer_id) is None:
            return jsonify(error="That answer is not on disk (any more)."), 404
        known = next((a for a in _all_answers()["answers"] if a["id"] == answer_id), None)
        if known is None:
            known = next((a for a in _all_answers(refresh=True)["answers"] if a["id"] == answer_id), None)
        if known is not None and known["pid"] and known["pid"] != pid:
            return jsonify(error=f"{answer_id} answers {known['pid']}, not {pid}."), 400
    root = _selection_write_root()
    if _op.is_benchmark_path(root):
        return jsonify(error="The Benchmark bucket is read-only."), 403
    try:
        entry = _ans.set_reference(root, pid, answer_id, _op.active_username() or _op.active_bucket(),
                                   note=str(body.get("note") or ""))
    except (OSError, ValueError) as exc:
        return jsonify(error=str(exc)), 500
    _invalidate_answers()
    return jsonify(ok=True, pid=pid, answer=answer_id, entry=entry, file=str(_ans.selection_path(root)))


# ---------------------------------------------------------------------------
# Claude-web answers: the answer page (final answer, saved pages, files,
# working trace) and the overview tab.  The archives beside parsed/ are read
# in place by _analysis_web.py.
# ---------------------------------------------------------------------------
import io

try:
    from . import _analysis_web as _aw
except ImportError:  # imported as a top-level module, like _analysis_answers above
    import _analysis_web as _aw

_WEB_TABS = ("answer", "reports", "files", "trace")
# Pages and SVG pictures written by the model open as documents of their own.  The sandbox
# gives them an origin apart from this browser's and blocks requests and form posts, so a
# script in such a file cannot reach the routes that write (reference choice, run deletion).
_ACTIVE_CONTENT_HEADERS = {
    "Content-Security-Policy": "sandbox allow-scripts; connect-src 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
}
_PLAIN_TEXT_KINDS = {"table", "markdown", "json", "code", "text"}


def _guard_active_content(response, name: str):
    if _aw.is_active_content(name):
        response.headers.update(_ACTIVE_CONTENT_HEADERS)
    return response


def _web_mimetype(name: str) -> str:
    kind = _aw.file_kind(name)
    if kind == "html":
        return "text/html"
    if kind in _PLAIN_TEXT_KINDS:
        return "text/plain"
    mime, _ = mimetypes.guess_type(name)
    return mime or "application/octet-stream"


def _web_source(found) -> Dict[str, Any]:
    """Where the files of a web answer are read: its archived run, else the parsed folder."""
    _kind, parsed, path = found
    config, folder = path.parent.name, path.name
    run = _aw.find_run(parsed.parent, config, _ans.short_pid(folder))

    def raw_url(rel: str, **args: Any) -> str:
        if run is not None:
            return url_for("analysis.analysis_web_archive", config=config, folder=folder, member=rel, **args)
        return url_for("analysis.analysis_web_file", config=config, folder=folder, relpath=rel, **args)

    def view_url(rel: str) -> str:
        return url_for("analysis.analysis_web_answer", config=config, folder=folder, tab="files", f=rel,
                       _anchor="web-tabs")

    def read(rel: str, limit: Optional[int] = None) -> Optional[bytes]:
        rel = _aw.clean_member(rel)
        if run is not None:
            return _aw.read_member(run, rel, limit)
        if rel not in files:
            return None
        try:
            with _io_path(path.joinpath(*rel.split("/"))).open("rb") as handle:
                return handle.read() if limit is None else handle.read(limit)
        except OSError:
            return None

    files = run["files"] if run is not None else _aw.folder_files(path)
    return {"run": run, "files": files, "raw_url": raw_url, "view_url": view_url, "read": read,
            "config": config, "folder": folder, "parsed": parsed}


def _web_file_view(source: Dict[str, Any], rel: str) -> Optional[Dict[str, Any]]:
    """One file as the viewer shows it: a picture, a framed page, a table, text, or a download."""
    rel = _aw.clean_member(rel)
    files = source["files"]
    if rel not in files:
        return None
    kind = _aw.file_kind(rel)
    item: Dict[str, Any] = {
        "rel": rel, "kind": kind, "size_text": _aw.human_size(files[rel]),
        "raw_url": source["raw_url"](rel), "download_url": source["raw_url"](rel, download=1),
        "text": "", "html": "", "table": None, "cut": False,
    }
    if kind not in _PLAIN_TEXT_KINDS:
        return item
    data = source["read"](rel, _aw.TEXT_PREVIEW_BYTES + 1) or b""
    item["cut"] = len(data) > _aw.TEXT_PREVIEW_BYTES
    text = _aw.decode_text(data[:_aw.TEXT_PREVIEW_BYTES])
    if kind == "table":
        item["table"] = _aw.table_preview(text)
    elif kind == "markdown":
        base = rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""

        def target_url(target: str) -> str:
            other = _aw.clean_member(base + target.split("#", 1)[0])
            if other not in files:
                return ""
            return source["raw_url"](other) if _aw.file_kind(other) == "image" else source["view_url"](other)

        item["html"] = _render_markdown_doc(_aw.rewrite_links(_ans.strip_front_matter(text), target_url))
    elif kind == "json" and not item["cut"]:
        item["text"] = _aw.pretty_json(text)
    else:
        item["text"] = text
    return item


def _web_page_context(found, view: Dict[str, Any], tab: str) -> Dict[str, Any]:
    """What the answer page shows beyond the final answer: run facts, saved pages, files, trace."""
    source = _web_source(found)
    files, raw_url, view_url = source["files"], source["raw_url"], source["view_url"]
    config, folder = source["config"], source["folder"]
    stats = _aw.run_stats(source["parsed"]).get(view["label"], {})
    timing = _aw.solver_excluded_timing(source["parsed"], config, view.get("pid", ""))
    groups = _aw.group_files(files)
    for group in groups:
        for entry in group["files"]:
            entry["view_url"] = view_url(entry["rel"])
    pages = [dict(page, url=raw_url(page["rel"]),
                  screenshot_url=raw_url(page["screenshot"]) if page["screenshot"] else "")
             for page in _aw.reports(files)]
    view["answer_html"] = _aw.link_presented_files(view["answer_html"], files, view_url)
    context: Dict[str, Any] = {
        "tab": tab, "facts": _aw.stat_facts(stats, timing),
        "incomplete": (stats.get("incomplete") or "").strip().lower() == "true",
        "stop_reasons": (stats.get("stop_reasons_str") or "").replace("|", " → "),
        "pages": pages, "groups": groups, "n_files": sum(len(g["files"]) for g in groups),
        "archive_name": source["run"]["zip"].name if source["run"] and source["run"].get("zip") is not None else "",
        "selected": None, "trace": None, "has_trace": "conversation.json" in files,
        "tab_urls": {name: url_for("analysis.analysis_web_answer", config=config, folder=folder,
                                   tab=None if name == "answer" else name,
                                   _anchor=None if name == "answer" else "web-tabs")
                     for name in _WEB_TABS},
        "web_index_url": url_for("analysis.analysis_web_index"),
    }
    if tab == "files":
        wanted = request.args.get("f") or next((g["files"][0]["rel"] for g in groups), "")
        context["selected"] = _web_file_view(source, wanted)
    elif tab == "trace" and context["has_trace"]:
        try:
            conversation = json.loads((source["read"]("conversation.json") or b"{}").decode("utf-8", "replace"))
        except ValueError:
            conversation = {}
        if isinstance(conversation, dict) and conversation.get("chat_messages"):
            trace = _aw.build_trace(conversation, files, _render_markdown_doc, raw_url)
            for message in trace["messages"]:
                for step in message["steps"]:
                    for handed in step.get("handed", []):
                        handed["url"] = view_url(handed["rel"]) if handed["rel"] else ""
            context["trace"] = trace
    return context


@analysis_bp.route("/web/")
def analysis_web_index():
    """Every Claude-web answer by prompt and configuration, with the run statistics of the harness."""
    web_answers = [a for a in _all_answers()["answers"] if a["kind"] == "web"]
    sections = []
    for parsed in _web_parsed_roots():
        web_dir = parsed.parent

        def file_url(area: str):
            def build(target: str) -> str:
                if _aw.summary_file(web_dir, area, target) is None:
                    return ""
                return url_for("analysis.analysis_web_summary_file", area=area, rel=_aw.clean_member(target))
            return build

        own = [a for a in web_answers if (parsed / a["label"]).is_dir()]
        summary_md = _read_text(parsed / _aw.SUMMARY_DIRNAME / "summary.md")
        timing_md = _read_text(web_dir / _aw.TIMING_DIRNAME / "README.md")
        tables = _aw.summary_tables(web_dir)
        for table in tables:
            table["url"] = url_for("analysis.analysis_web_summary_file", area=table["area"], rel=table["name"])
        sections.append({
            "overview": _aw.overview(parsed, own),
            "summary_html": _render_markdown_doc(_aw.rewrite_links(summary_md, file_url("summary"))),
            "timing_html": _render_markdown_doc(_aw.rewrite_links(timing_md, file_url("timing"))),
            "timing_plots": [(name, url_for("analysis.analysis_web_summary_file", area="timing", rel=name))
                             for name in _aw.timing_plots(web_dir)],
            "readme_html": _render_markdown_doc(_aw.rewrite_links(_read_text(web_dir / "README.md"),
                                                                  lambda target: "")),
            "tables": tables,
            "archives": sorted(p.name for p in web_dir.glob("*.zip")),
        })
    return render_template("analysis_web_index.html", sections=sections, active="web",
                           matrix_url=url_for("analysis.analysis_matrix"))


@analysis_bp.route("/web-summary/<area>/<path:rel>")
def analysis_web_summary_file(area: str, rel: str):
    """A plot or table of the harness run summary or of the framework-versus-web timing comparison."""
    for parsed in _web_parsed_roots():
        target = _aw.summary_file(parsed.parent, area, rel)
        if target is not None:
            return _guard_active_content(send_output_file(target, mimetype=_web_mimetype(target.name)), target.name)
    abort(404)


@analysis_bp.route("/web/<config>/<folder>")
def analysis_web_answer(config: str, folder: str):
    """One Claude-web answer: final answer, saved pages, files and working trace (``?tab=``)."""
    found = _find_answer(f"web:{config}/{folder}")
    view = _answer_view(f"web:{config}/{folder}")
    if found is None or view is None:
        abort(404)
    tab = request.args.get("tab") or "answer"
    if tab not in _WEB_TABS:
        abort(404)
    data = _all_answers()
    ref = data["references"].get(view["pid"]) or {}
    row = next((r for r in _ans.catalog_rows(data["catalog"]) if r["pid"] == view["pid"]), {})
    return render_template(
        "analysis_web_answer.html",
        view=view, label=view["label"], answer_id=view["id"], pid=view["pid"], me=view,
        siblings=[a for a in _answers_for_pid(view["pid"], data) if a["id"] != view["id"]],
        reference=ref, is_reference=ref.get("answer") == view["id"],
        reference_answer=next((a for a in data["answers"] if a["id"] == ref.get("answer")), None) if ref else None,
        prompt=row.get("prompt", ""), layer=row.get("layer", ""),
        matrix_url=url_for("analysis.analysis_matrix"),
        **_web_page_context(found, view, tab),
    )


@analysis_bp.route("/web/<config>/<folder>/archive/<path:member>")
def analysis_web_archive(config: str, folder: str, member: str):
    """A file of a Claude-web run, read from its archive (``?download=1`` saves it)."""
    found = _find_answer(f"web:{config}/{folder}")
    if found is None:
        abort(404)
    source = _web_source(found)
    rel = _aw.clean_member(member)
    if source["run"] is None or rel not in source["files"]:
        abort(404)
    data = _aw.read_member(source["run"], rel)
    if data is None:
        abort(404)
    name = rel.rsplit("/", 1)[-1]
    download = bool(request.args.get("download")) or _aw.file_kind(rel) == "binary"
    response = send_file(io.BytesIO(data), mimetype=_web_mimetype(rel), as_attachment=download,
                         download_name=name, max_age=3600)
    return _guard_active_content(response, rel)


@analysis_bp.route("/web/<config>/<folder>/file/<path:relpath>")
def analysis_web_file(config: str, folder: str, relpath: str):
    """A file saved with a Claude-web answer (figure, published page, the markdown itself)."""
    found = _find_answer(f"web:{config}/{folder}")
    if found is None:
        abort(404)
    base = found[2].resolve()
    rel = (relpath or "").strip().replace("\\", "/").lstrip("/")
    target = (base / rel).resolve()
    try:
        _resolved_compare_path(target).relative_to(_resolved_compare_path(base))
    except (OSError, ValueError):
        abort(403)
    if not target.is_file():
        abort(404)
    download = bool(request.args.get("download"))
    response = send_output_file(target, mimetype=_web_mimetype(target.name), as_attachment=download,
                         download_name=target.name)
    return _guard_active_content(response, target.name)


# ---------------------------------------------------------------------------
# Run-local excerpts: eval mode of an answer
# ---------------------------------------------------------------------------
try:
    from . import _analysis_excerpts as _ax
except ImportError:  # imported as a top-level module, like _analysis_answers above
    import _analysis_excerpts as _ax


def _excerpts_editable(sdir: Path) -> bool:
    """Excerpt editing requires a physical run and its unpacked answer."""
    return _ax.editable_run(sdir)


def _excerpt_context(sdir: Path) -> Dict[str, Any]:
    """Template variables of the answer card: the eval view and the one button that switches it.

    A run with excerpts opens in eval view (?mode=raw shows the plain answer).  A run without
    them opens plain; ?mode=eval then opens an empty eval view where excerpts can be built."""
    entry = _ax.find_run(sdir)
    answer_path = sdir / "answer.md"
    editable = answer_path.is_file() and _excerpts_editable(sdir)
    mode = request.args.get("mode")
    context: Dict[str, Any] = {
        "eval_available": entry is not None or editable,
        "eval_has_file": entry is not None,
        "eval_view": None,
        "eval_edit": None,
    }
    if (entry is not None and mode != "raw") or (entry is None and editable and mode == "eval"):
        context["eval_view"] = _ax.eval_view(
            answer_path.read_bytes() if answer_path.is_file() else b"",
            _render_markdown_doc(_read_text(answer_path)),
            entry or {"excerpts": [], "core": []},
        )
        if editable:
            context["eval_edit"] = {"version": _ax.file_version(sdir)}
    return context


@analysis_bp.route("/excerpts/<path:label>", methods=["POST"])
def analysis_excerpt_edit(label: str):
    """Create, change or delete one excerpt row of a run; writes the run's _eval/excerpts.json."""
    root = _root_for_label(label)
    if root is None:
        return jsonify(error="Run not found."), 404
    sdir = root / label
    if not _excerpts_editable(sdir):
        return jsonify(error="Unpack this run and its answer before editing excerpts."), 403
    answer_path = sdir / "answer.md"
    if not answer_path.is_file():
        return jsonify(error="This run has no answer.md."), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Expected a JSON object."), 400
    try:
        result = _ax.apply_edit(sdir, answer_path.read_bytes(),
                                _render_markdown_doc(_read_text(answer_path)), body)
    except _ax.EditError as exc:
        return jsonify(error=str(exc)), exc.status
    except OSError as exc:
        return jsonify(error=str(exc)), 500
    return jsonify(ok=True, **result)
