"""Evaluation browser routes â€” annotated answer viewing with enrichment.

Blueprint: ``/eval/``
"""
from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, abort

eval_bp = Blueprint("evaluation", __name__, url_prefix="/eval")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_BROWSER_DIR = Path(__file__).absolute().parent.parent          # NIST_SRD46_database_browser/
_PROJECT_ROOT = _BROWSER_DIR.parent                            # SRD46_research_agent/
_QUERY_AGENT_ROOT = _PROJECT_ROOT / "NIST_SRD46_db_agent" / "NIST_SRD46_query_agent"
_SRD46_DB_DIR = _PROJECT_ROOT / "NIST_SRD46_core_db_storage"
_OUTPUT_ROOT = _PROJECT_ROOT / "_output" / "Query"
_EVAL_ROOT = _OUTPUT_ROOT / "_evaluation"


def _user_root_pairs() -> list[tuple[Path, Path]]:
    """Shared freeform roots, including earlier flat output layouts."""
    return [(_OUTPUT_ROOT, _EVAL_ROOT),
            (_PROJECT_ROOT / "_output", _PROJECT_ROOT / "_output" / "_evaluation")]


def _root_pairs() -> list[tuple[Path, Path]]:
    """Shared freeform and benchmark query results."""
    benchmark = _PROJECT_ROOT / "_benchmark"
    return _user_root_pairs() + [(benchmark / "Query", benchmark / "Query" / "_evaluation"),
                                 (benchmark, benchmark / "_evaluation")]


def _roots_for_run(model: str, question_id: str) -> tuple[Path, Path]:
    for out_root, eval_root in _root_pairs():
        if (out_root / f"Model_{model}" / question_id).is_dir():
            return out_root, eval_root
    return _OUTPUT_ROOT, _EVAL_ROOT

# The query-agent dir must be on sys.path so the nested eval pipeline
# (``SRD46_query_output_eval_pipeline``) and the modules it bare-imports
# (``argo_client`` / ``argo_config`` for claim classification) all resolve.
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_QUERY_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_QUERY_AGENT_ROOT))

from .evaluation_annotations import (
    CLAIM_TYPES,
    SUPPORT_CLASSES,
    add_annotation_claim,
    annotation_summary,
    annotation_history_counts,
    annotation_history_path,
    claims_cache_state,
    claim_doc_to_dict,
    clear_manual_annotation_state,
    delete_annotation_claim,
    load_annotation_history,
    load_claim_doc_for_annotation,
    load_manual_claims_doc,
    manual_claims_path,
    apply_annotation_redo,
    apply_annotation_undo,
    record_annotation_undo_state,
    register_routes as register_annotation_routes,
    save_manual_claims_doc,
    update_annotation_claim,
)
from .evaluation_comments import (
    load_markers,
    load_scoring,
    register_routes as register_comment_routes,
)


def _get_models(root_pairs: list[tuple[Path, Path]] | None = None) -> list[str]:
    """List available model directories across all run roots."""
    models: set[str] = set()
    for out_root, _ in (root_pairs or _root_pairs()):
        if not out_root.exists():
            continue
        for d in out_root.iterdir():
            if d.is_dir() and d.name.startswith("Model_"):
                models.add(d.name.removeprefix("Model_"))
    return sorted(models)


def _get_questions(model: str,
                   root_pairs: list[tuple[Path, Path]] | None = None) -> list[str]:
    """List question IDs for a model across all run roots."""
    qids: set[str] = set()
    for out_root, _ in (root_pairs or _root_pairs()):
        model_dir = out_root / f"Model_{model}"
        if not model_dir.exists():
            continue
        for d in model_dir.iterdir():
            if d.is_dir() and d.name.startswith("Q"):
                qids.add(d.name)
    return sorted(qids)


def _get_batches(model: str, question_id: str) -> list[int]:
    """List batch numbers for a model/question."""
    out_root, _ = _roots_for_run(model, question_id)
    question_dir = out_root / f"Model_{model}" / question_id
    return _get_batches_from_question_dir(question_dir, question_id)


def _get_batches_from_question_dir(question_dir: Path, question_id: str) -> list[int]:
    """List batch numbers from an already-resolved question directory."""
    if not question_dir.exists():
        return []
    batches = set()
    for f in question_dir.iterdir():
        m = re.match(rf"^{re.escape(question_id)}_result_batch(\d+)\.md$", f.name)
        if m:
            batches.add(int(m.group(1)))
    return sorted(batches)


# ---------------------------------------------------------------------------
# Freeform query identification
# ---------------------------------------------------------------------------
# Freeform (non-test-set) queries are stored alongside the curated test runs
# under `_output/Query/Model_<m>/<qid>/` but use a `Qfree_<timestamp>` prefix so the
# /eval/ index can hide them and the /freeform/ index can list them.
_FREEFORM_QID_PREFIX = "Qfree_"


def _is_freeform_qid(question_id: str) -> bool:
    return question_id.startswith(_FREEFORM_QID_PREFIX)


def _run_file_paths(question_dir: Path, question_id: str, batch: int) -> dict[str, Path]:
    """Collect available markdown files for a run."""
    files: dict[str, Path] = {}
    for kind in ("result", "history", "ref_ids"):
        p = question_dir / f"{question_id}_{kind}_batch{batch}.md"
        if p.exists():
            files[kind] = p
    return files


def _extract_prompt_text(model: str, question_id: str, batch: int) -> str:
    """Best-effort extraction of the prompt text sent for a given run batch.

    Returns an empty string if the result file or prompt block is missing.
    """
    out_root, _ = _roots_for_run(model, question_id)
    question_dir = out_root / f"Model_{model}" / question_id
    result_path = question_dir / f"{question_id}_result_batch{batch}.md"
    quick = _extract_prompt_text_from_result_path(result_path)
    if quick:
        return quick
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.input_support_helpers.parse_result import (
            parse_result_text,
        )
        return parse_result_text(
            result_path.read_text(encoding="utf-8", errors="replace")
        ).prompt_text or ""
    except Exception:
        return ""


def _extract_prompt_text_from_result_path(result_path: Path) -> str:
    """Cheap prompt extraction for index rows.

    Result files start with a short metadata header containing
    ``**Prompt:** ...``.  The index previously parsed the entire result file
    for every benchmark row, which made the benchmark landing page scale with
    total answer size.  A bounded read is enough for the listing.
    """
    if not result_path.exists():
        return ""
    try:
        with result_path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(16_384)
    except OSError:
        return ""
    match = re.search(r"^\*\*Prompt:\*\*\s*(.+?)\s*$", head, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _eval_data_dir(model: str, question_id: str) -> Path:
    """Per-run ``_output_eval`` dir, resolved across active/Benchmark roots."""
    _, eval_root = _roots_for_run(model, question_id)
    return eval_root / f"Model_{model}" / question_id


def _bind_claims_eval_root(model: str, question_id: str) -> None:
    """Point the eval pipeline's claims cache at this run's eval root.

    The generated ``claims_batch*.json`` caches + locks must live beside the
    run (per-user aware), matching where ``_eval_data_dir`` reads them.
    """
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.enricher import (
            set_claims_eval_root,
        )
        _, eval_root = _roots_for_run(model, question_id)
        set_claims_eval_root(eval_root)
    except Exception:  # noqa: BLE001
        pass


@eval_bp.before_request
def _eval_before_request() -> None:
    """Bind the eval pipeline's per-run claims-cache root for this request.

    Any eval route targeting a specific run (``<model>/<question_id>/...``)
    points the pipeline at that run's ``_output_eval`` so generated claim
    caches/locks land beside the run (active bucket or Benchmark).
    """
    va = request.view_args or {}
    model = va.get("model")
    question_id = va.get("question_id")
    if model and question_id:
        _bind_claims_eval_root(model, question_id)
    else:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.enricher import (
                set_claims_eval_root,
            )
            set_claims_eval_root(None)
        except Exception:  # noqa: BLE001
            pass


def _manual_claims_path(model: str, question_id: str, batch: int) -> Path:
    return manual_claims_path(_eval_data_dir, model, question_id, batch)


def _annotation_history_path(model: str, question_id: str, batch: int) -> Path:
    return annotation_history_path(_eval_data_dir, model, question_id, batch)


def _load_manual_claims_doc(
    model: str,
    question_id: str,
    batch: int,
) -> tuple[object | None, dict | None]:
    return load_manual_claims_doc(_eval_data_dir, model, question_id, batch)


def _save_manual_claims_doc(
    model: str,
    question_id: str,
    batch: int,
    doc,
) -> dict:
    return save_manual_claims_doc(_eval_data_dir, model, question_id, batch, doc)


def _load_claim_doc_for_annotation(
    model: str,
    question_id: str,
    batch: int,
) -> tuple[object | None, str | None, dict | None]:
    return load_claim_doc_for_annotation(_eval_data_dir, model, question_id, batch)


def _annotation_summary(doc) -> tuple[int, int, int, dict[str, int]]:
    return annotation_summary(doc)


def _load_annotation_history(model: str, question_id: str, batch: int) -> dict:
    return load_annotation_history(_eval_data_dir, model, question_id, batch)


def _annotation_history_counts(model: str, question_id: str, batch: int) -> tuple[int, int]:
    return annotation_history_counts(_eval_data_dir, model, question_id, batch)


def _record_annotation_undo_state(model: str, question_id: str, batch: int, snapshot) -> dict:
    return record_annotation_undo_state(_eval_data_dir, model, question_id, batch, snapshot)


def _apply_annotation_undo(model: str, question_id: str, batch: int) -> tuple[dict, dict]:
    return apply_annotation_undo(_eval_data_dir, model, question_id, batch)


def _apply_annotation_redo(model: str, question_id: str, batch: int) -> tuple[dict, dict]:
    return apply_annotation_redo(_eval_data_dir, model, question_id, batch)


def _clear_manual_annotation_state(model: str, question_id: str, batch: int) -> None:
    clear_manual_annotation_state(_eval_data_dir, model, question_id, batch)


def _add_annotation_claim(doc, paragraph_index: int, **kwargs) -> int:
    return add_annotation_claim(doc, paragraph_index, **kwargs)


def _update_annotation_claim(doc, paragraph_index: int, claim_index: int, **kwargs) -> int:
    return update_annotation_claim(doc, paragraph_index, claim_index, **kwargs)


def _delete_annotation_claim(doc, paragraph_index: int, claim_index: int) -> None:
    delete_annotation_claim(doc, paragraph_index, claim_index)


def _claims_cache_state(model: str, question_id: str, batch: int) -> str | None:
    return claims_cache_state(_eval_data_dir, model, question_id, batch)


def _index_claims_cache_state(
    eval_root: Path,
    model: str,
    question_id: str,
    batch: int,
) -> str | None:
    """Lightweight cache-state check for the benchmark index.

    Detailed run/API views still call ``claims_cache_state`` and parse the full
    claim document.  The index only needs a status badge, so it should not load
    every ``claims_batch*.json`` file in the benchmark corpus.
    """
    eval_dir = eval_root / f"Model_{model}" / question_id
    if (eval_dir / f"claims_batch{batch}.manual.json").exists():
        return "manual"

    path = eval_dir / f"claims_batch{batch}.json"
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(65_536)
    except OSError:
        return None

    lowered = head.lower()
    if '"complete": true' in lowered:
        return "complete"
    if '"complete": false' in lowered:
        return "partial"
    return "legacy"


register_comment_routes(eval_bp, _eval_data_dir)
register_annotation_routes(eval_bp, _eval_data_dir)


def _render_plain_doc(text: str) -> str:
    """Render raw markdown text quickly without running enrichment."""
    return f"<div class=\"plain-doc\"><pre>{html.escape(text)}</pre></div>"


def _render_markdown_doc(text: str, css_class: str = "md-doc") -> str:
    """Render markdown to HTML with proper table support."""
    try:
        import markdown as _md
        body = _md.markdown(
            text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    except ImportError:
        body = f"<pre>{html.escape(text)}</pre>"
    return f'<div class="{css_class}">{body}</div>'


def _render_tool_eval_doc(text: str) -> str:
    """Render tool_eval markdown with section IDs for claim linking."""
    import re as _re
    # Add id attributes to step headings so JS can scroll to them
    lines = text.split("\n")
    processed: list[str] = []
    step_re = _re.compile(r'^(#{2,3})\s+(?:Step\s+)?(\d+)\b(.*)$', _re.IGNORECASE)
    tool_re = _re.compile(r'`([^`]+)`')
    for line in lines:
        m = step_re.match(line)
        if m:
            level, step_num, rest = m.group(1), m.group(2), m.group(3)
            # Extract tool name if present
            tm = tool_re.search(rest)
            tool_name = tm.group(1) if tm else ""
            section_id = f"tool-step-{step_num}"
            processed.append(f'{level} <span id="{section_id}" data-step="{step_num}" data-tool="{html.escape(tool_name)}" class="tool-step-anchor">{level.replace("#","").strip()} Step {step_num}{rest}</span>')
        else:
            processed.append(line)
    return _render_markdown_doc("\n".join(processed), css_class="tool-eval-doc")


# ---------------------------------------------------------------------------
# Index route
# ---------------------------------------------------------------------------

def _iter_index_runs(roots: list[tuple[Path, Path]]) -> list[tuple[str, str, Path, Path]]:
    """Return unique ``(model, qid, question_dir, eval_root)`` runs.

    Root order is significant: active user roots precede Benchmark roots.
    De-duplicating while walking in that order preserves lookup precedence
    without repeatedly resolving paths for every row.
    """
    runs: list[tuple[str, str, Path, Path]] = []
    seen: set[tuple[str, str]] = set()
    for out_root, eval_root in roots:
        if not out_root.exists():
            continue
        try:
            model_dirs = list(out_root.iterdir())
        except OSError:
            continue
        for model_dir in model_dirs:
            if not (model_dir.is_dir() and model_dir.name.startswith("Model_")):
                continue
            model = model_dir.name.removeprefix("Model_")
            try:
                question_dirs = list(model_dir.iterdir())
            except OSError:
                continue
            for question_dir in question_dirs:
                if not (question_dir.is_dir() and question_dir.name.startswith("Q")):
                    continue
                qid = question_dir.name
                key = (model, qid)
                if key in seen:
                    continue
                seen.add(key)
                runs.append((model, qid, question_dir, eval_root))
    return sorted(runs, key=lambda item: (item[0], item[1]))


def _build_index_rows(*, freeform_only: bool, filter_model: str, filter_q: str) -> list[dict]:
    """Shared row-builder for /eval/ and /freeform/ index pages."""
    rows: list[dict] = []
    roots = _user_root_pairs() if freeform_only else _root_pairs()
    for model, qid, question_dir, eval_root in _iter_index_runs(roots):
        if filter_model and model != filter_model:
            continue
        if _is_freeform_qid(qid) != freeform_only:
            continue
        if filter_q and filter_q.lower() not in qid.lower():
            continue
        batches = _get_batches_from_question_dir(question_dir, qid)
        claim_cache_batches: list[int] = []
        completed_claim_batches: list[int] = []
        for b in batches:
            cache_state = _index_claims_cache_state(eval_root, model, qid, b)
            if cache_state is not None:
                claim_cache_batches.append(b)
            if cache_state in {"complete", "legacy", "manual"}:
                completed_claim_batches.append(b)
        first_result = (
            question_dir / f"{qid}_result_batch{batches[0]}.md"
            if batches else None
        )
        rows.append({
            "model": model,
            "question_id": qid,
            "batches": batches,
            "batch_count": len(batches),
            "enriched": bool(claim_cache_batches),
            "claim_cache_batches": claim_cache_batches,
            "completed_claim_batches": completed_claim_batches,
            "first_claims_batch": completed_claim_batches[0] if completed_claim_batches else None,
            "prompt_text": (
                _extract_prompt_text_from_result_path(first_result)
                if first_result is not None else ""
            ),
        })
    return rows


@eval_bp.route("/")
def eval_index():
    """Evaluation index: curated test-set runs (Qfree_* runs are listed at /freeform/)."""
    filter_model = request.args.get("model", "").strip()
    filter_q = request.args.get("q", "").strip()
    rows = _build_index_rows(freeform_only=False, filter_model=filter_model, filter_q=filter_q)
    return render_template(
        "eval_index.html",
        rows=rows,
        models=_get_models(),
        filter_model=filter_model,
        filter_q=filter_q,
    )


@eval_bp.route("/freeform/")
def freeform_index():
    """Freeform-query index: lists Qfree_<ts> runs only.

    Per-run viewing reuses the standard eval_run handler so the rendering
    interface is identical to test-set runs.
    """
    filter_model = request.args.get("model", "").strip()
    filter_q = request.args.get("q", "").strip()
    rows = _build_index_rows(freeform_only=True, filter_model=filter_model, filter_q=filter_q)
    return render_template(
        "eval_index.html",
        rows=rows,
        models=_get_models(_user_root_pairs()),
        filter_model=filter_model,
        filter_q=filter_q,
        page_title="Freeform Queries",
        is_freeform=True,
    )


@eval_bp.route("/freeform/<model>/<question_id>/delete", methods=["POST"])
def delete_freeform_run(model: str, question_id: str):
    """Delete a freeform run from active-user roots only."""
    if not _is_freeform_qid(question_id):
        return jsonify(error="Only freeform runs can be removed."), 400
    if Path(model).name != model or Path(question_id).name != question_id:
        return jsonify(error="Invalid run identifier."), 400

    removed = False
    for out_root, eval_root in _user_root_pairs():
        for root in (out_root, eval_root):
            model_root = root / f"Model_{model}"
            target = model_root / question_id
            if not target.is_dir():
                continue
            try:
                if target.resolve().parent != model_root.resolve():
                    return jsonify(error="Invalid run path."), 400
                shutil.rmtree(target)
                removed = True
            except OSError as exc:
                return jsonify(error=str(exc)), 500
    if not removed:
        return jsonify(error="User freeform run not found."), 404
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# Single-run evaluation page
# ---------------------------------------------------------------------------

@eval_bp.route("/<model>/<question_id>/<int:batch>")
def eval_run(model: str, question_id: str, batch: int):
    """Single-run evaluation: raw view by default, with manual claim/regex modes."""
    _output_root, _output_eval_root = _roots_for_run(model, question_id)
    question_dir = _output_root / f"Model_{model}" / question_id
    if not question_dir.exists():
        abort(404, f"Run not found: {model}/{question_id}/batch{batch}")

    files = _run_file_paths(question_dir, question_id, batch)
    if not files:
        abort(404, f"No files found for run: {model}/{question_id}/batch{batch}")

    # --- Extract the original prompt text from the result file -----------
    prompt_text = ""
    result_path = files.get("result")
    if result_path is not None:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.input_support_helpers.parse_result import (
                parse_result_text,
            )
            prompt_text = parse_result_text(
                result_path.read_text(encoding="utf-8", errors="replace")
            ).prompt_text or ""
        except Exception:
            prompt_text = ""

    # --- View mode -------------------------------------------------------
    mode = request.args.get("mode", "").strip()  # raw | claims | regex
    use_argo = request.args.get("argo", "1") != "0"
    claim_cache_state = _claims_cache_state(model, question_id, batch)
    claim_cache_exists = claim_cache_state is not None
    claim_cache_complete = claim_cache_state in {"complete", "legacy", "manual"}

    if not mode:
        mode = "claims" if claim_cache_complete else "raw"

    claim_doc = None
    claim_html = ""
    claim_mode_message = ""
    tool_eval_html = ""
    total_claims = 0
    supported_claims = 0
    unsupported_claims = 0
    support_counts = {support: 0 for support in SUPPORT_CLASSES}
    annotation_manual_override = False
    annotation_updated_at = ""
    annotation_doc_data = None
    annotation_undo_depth = 0
    annotation_redo_depth = 0
    rendered_html: dict[str, str] = {}

    if mode == "claims":
        manual_claim_doc, manual_claim_meta = _load_manual_claims_doc(model, question_id, batch)
        annotation_undo_depth, annotation_redo_depth = _annotation_history_counts(model, question_id, batch)
        annotation_manual_override = manual_claim_doc is not None
        if manual_claim_meta:
            annotation_updated_at = str(manual_claim_meta.get("updated_at", ""))

        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.enricher import (
            enrich_run_claims,
            is_claims_enrichment_in_progress,
            load_renderable_claims_cache,
        )
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.regex_support_helpers.html_renderer import render_claim_document

        if manual_claim_doc is not None:
            claim_doc = manual_claim_doc
            cache_state = "manual"
            claim_mode_message = (
                "Showing a manual browser annotation override. "
                "Generated claim caches remain unchanged until you revert the override."
            )
        else:
            claim_doc, cache_state = load_renderable_claims_cache(
                model=model,
                question_id=question_id,
                batch=batch,
                argo_model=None,
            )
            if claim_doc is None:
                claim_doc = enrich_run_claims(
                    model=model,
                    question_id=question_id,
                    batch=batch,
                    output_root=_output_root,
                    eval_root=_output_eval_root,
                    use_cache=True,
                    skip_if_locked=True,
                )
                cache_state = "complete" if claim_doc is not None else None

        if claim_doc:
            claim_html = render_claim_document(claim_doc)
            total_claims, supported_claims, unsupported_claims, support_counts = _annotation_summary(claim_doc)
            annotation_doc_data = claim_doc_to_dict(claim_doc)
            if cache_state == "partial":
                if is_claims_enrichment_in_progress(model, question_id, batch, None):
                    claim_mode_message = (
                        "Showing an in-progress claim-analysis checkpoint. "
                        "Grounding references and support totals may still change; reload shortly for the final cache."
                    )
                else:
                    claim_mode_message = (
                        "Showing a saved partial claim-analysis checkpoint from an interrupted or unfinished run. "
                        "Grounding references and support totals may be incomplete until annotation is rerun."
                    )
            elif cache_state == "legacy":
                claim_mode_message = (
                    "Showing a completed cached claim analysis produced under older annotation settings."
                )
        else:
            result_path = files.get("result")
            if result_path is not None:
                claim_html = _render_markdown_doc(
                    result_path.read_text(encoding="utf-8", errors="replace")
                )
            if is_claims_enrichment_in_progress(model, question_id, batch, None):
                claim_mode_message = (
                    "Claim analysis is already running in another process. "
                    "This page skipped a duplicate enrichment pass; reload shortly to see the cached result."
                )

        # Load tool_eval for the tool results panel
        tool_eval_path = (
            _output_eval_root / f"Model_{model}" / question_id
            / f"tool_eval_batch{batch}.md"
        )
        if tool_eval_path.exists():
            tool_eval_html = _render_tool_eval_doc(
                tool_eval_path.read_text(encoding="utf-8", errors="replace")
            )

        # Collect all canonical IDs referenced by grounded claims
        claim_ref_ids: set[str] = set()
        if claim_doc:
            for cp in claim_doc.paragraphs:
                for gc in cp.grounded_claims:
                    for cid in gc.canonical_ids:
                        claim_ref_ids.add(cid)

    elif mode == "regex":
        # Legacy enrichment mode
        enrich_started = True
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.enricher import enrich_run as _enrich
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.regex_support_helpers.html_renderer import (
            render_documents_side_by_side,
        )

        docs = _enrich(
            model=model,
            question_id=question_id,
            batch=batch,
            output_root=_output_root,
            use_argo=use_argo,
            use_cache=True,
            db_dir=_SRD46_DB_DIR,
        )
        rendered_html = render_documents_side_by_side(docs)

    else:
        # Raw fast view (default)
        for kind, path in files.items():
            text = path.read_text(encoding="utf-8", errors="replace")
            rendered_html[kind] = _render_markdown_doc(text)

    # --- Tool results panel (shown in ALL modes) ---------------------------
    if not tool_eval_html:
        tool_eval_path = (
            _output_eval_root / f"Model_{model}" / question_id
            / f"tool_eval_batch{batch}.md"
        )
        if tool_eval_path.exists():
            tool_eval_html = _render_tool_eval_doc(
                tool_eval_path.read_text(encoding="utf-8", errors="replace")
            )

    # --- Workflow diagram --------------------------------------------------
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.input_support_helpers.parse_history import parse_history
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.workflow_diagram_builder import build_mermaid

    mermaid_chart = ""
    history_path = question_dir / f"{question_id}_history_batch{batch}.md"
    tool_calls = []
    if history_path.exists():
        tool_calls = parse_history(history_path)
        mermaid_chart = build_mermaid(tool_calls)

    # --- Extract preplan + plan text from tool calls ----------------------
    preplan_text = ""
    plan_text = ""
    for tc in tool_calls:
        if tc.tool_name == "0_preplan_decision" and tc.result_text:
            preplan_text = tc.result_text
        elif tc.tool_name == "0_plan_search_strategy" and tc.result_text:
            plan_text = tc.result_text

    # --- Layout panels (configurable via ?panels= query param) -----------
    # Default panels: preplan, plan.  Options: ref_ids, history, preplan, plan
    panels_param = request.args.get("panels", "preplan,plan")
    active_panels = [p.strip() for p in panels_param.split(",") if p.strip()]
    available_panels = ["preplan", "plan", "ref_ids", "history"]
    active_panels = [p for p in active_panels if p in available_panels]
    if not active_panels:
        active_panels = ["preplan", "plan"]

    # Build panel content
    side_panels: list[dict] = []
    for panel_name in active_panels:
        if panel_name == "preplan":
            side_panels.append({
                "id": "preplan",
                "label": "Pre-Plan",
                "icon": "bi-lightbulb",
                "html": _render_markdown_doc(preplan_text) if preplan_text else "",
                "empty_msg": "No pre-plan found.",
            })
        elif panel_name == "plan":
            side_panels.append({
                "id": "plan",
                "label": "Plan",
                "icon": "bi-map",
                "html": _render_markdown_doc(plan_text) if plan_text else "",
                "empty_msg": "No plan found.",
            })
        elif panel_name == "ref_ids":
            ref_text = ""
            rp = question_dir / f"{question_id}_ref_ids_batch{batch}.md"
            if rp.exists():
                ref_text = rp.read_text(encoding="utf-8", errors="replace")
            side_panels.append({
                "id": "ref_ids",
                "label": "Ref IDs",
                "icon": "bi-tags",
                "html": _render_markdown_doc(ref_text) if ref_text else "",
                "empty_msg": "No ref_ids file found.",
            })
        elif panel_name == "history":
            hist_text = ""
            if history_path.exists():
                hist_text = history_path.read_text(encoding="utf-8", errors="replace")
            side_panels.append({
                "id": "history",
                "label": "History",
                "icon": "bi-clock-history",
                "html": _render_markdown_doc(hist_text) if hist_text else "",
                "empty_msg": "No history file found.",
            })

    # --- Entity references for right sidebar --------------------------------
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.input_support_helpers.parse_ref_ids import parse_ref_ids

    entity_refs = []
    ref_ids_path = question_dir / f"{question_id}_ref_ids_batch{batch}.md"
    if ref_ids_path.exists():
        entity_refs = parse_ref_ids(ref_ids_path)

    # In claims mode, filter sidebar to only claim-referenced IDs
    refs_by_type: dict[str, list[dict]] = {}
    seen_ids: set[str] = set()
    for ref in entity_refs:
        if ref.prefixed_id in seen_ids:
            continue
        seen_ids.add(ref.prefixed_id)
        refs_by_type.setdefault(ref.entity_type, []).append({
            "prefixed_id": ref.prefixed_id,
            "name": ref.name or "",
            "detail": ref.detail or "",
            "step_num": ref.step_num,
        })

    # In claims mode, also add any IDs from grounding that weren't in ref_ids
    if mode == "claims" and claim_doc:
        for cid in sorted(claim_ref_ids - seen_ids):
            m = re.match(r"^([a-z_]+?)_(\d+)$", cid)
            if m:
                etype = m.group(1)
                refs_by_type.setdefault(etype, []).append({
                    "prefixed_id": cid,
                    "name": "",
                    "detail": "",
                    "step_num": 0,
                })

    # --- Load scoring + markers --------------------------------------------
    scoring = load_scoring(_eval_data_dir, model, question_id, batch)
    markers = load_markers(_eval_data_dir, model, question_id, batch)

    return render_template(
        "eval_run.html",
        model=model,
        question_id=question_id,
        batch=batch,
        prompt_text=prompt_text,
        mode=mode,
        rendered_html=rendered_html,
        claim_html=claim_html,
        claim_mode_message=claim_mode_message,
        tool_eval_html=tool_eval_html,
        total_claims=total_claims,
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        support_counts=support_counts,
        mermaid_chart=mermaid_chart,
        refs_by_type=refs_by_type,
        use_argo=use_argo,
        side_panels=side_panels,
        active_panels=active_panels,
        available_panels=available_panels,
        scoring=scoring,
        markers=markers,
        claim_cache_exists=claim_cache_exists,
        claim_cache_complete=claim_cache_complete,
        claim_cache_state=claim_cache_state,
        annotation_doc_data=annotation_doc_data,
        annotation_manual_override=annotation_manual_override,
        annotation_updated_at=annotation_updated_at,
        annotation_undo_depth=annotation_undo_depth,
        annotation_redo_depth=annotation_redo_depth,
        claim_types=CLAIM_TYPES,
        support_classes=SUPPORT_CLASSES,
    )


# ---------------------------------------------------------------------------
# API: reference data card for a canonical ID
# ---------------------------------------------------------------------------

@eval_bp.route("/api/ref/<prefixed_id>")
def ref_card_api(prefixed_id: str):
    """Return a JSON data card for a canonical prefixed ID."""
    m = re.match(r"^([a-z_]+?)_(\d+)$", prefixed_id)
    if not m:
        return jsonify({"error": "Invalid ID format"}), 400

    prefix, raw_id = m.group(1), int(m.group(2))

    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.db_support_helpers.db_reference import open_reference_connection
    conn = open_reference_connection(_SRD46_DB_DIR)
    try:
        card = _fetch_entity_card(conn, prefix, raw_id)
    finally:
        conn.close()

    if card is None:
        return jsonify({"error": "Entity not found"}), 404
    return jsonify(card)


def _fetch_entity_card(conn, prefix: str, raw_id: int) -> dict | None:
    """Fetch key data for a single entity from the SQLite databases."""
    if prefix == "metal":
        row = conn.execute(
            "SELECT * FROM cards.metal_card WHERE metal_id = ?", (raw_id,)
        ).fetchone()
        if row:
            return {"type": "metal", "id": f"metal_{raw_id}", **dict(row)}

    elif prefix == "ligand":
        row = conn.execute(
            "SELECT * FROM cards.ligand_card WHERE ligand_id = ?", (raw_id,)
        ).fetchone()
        if row:
            return {"type": "ligand", "id": f"ligand_{raw_id}", **dict(row)}

    elif prefix == "vlm":
        row = conn.execute(
            """SELECT c.*, m.metal_name_SRD, m.symbol_pure, l.ligand_name_SRD
               FROM cards.ligandmetal_card c
               JOIN cards.metal_card m ON c.metal_id = m.metal_id
               JOIN cards.ligand_card l ON c.ligand_id = l.ligand_id
               WHERE c.complex_system_id = ?""",
            (raw_id,),
        ).fetchone()
        if row:
            d = dict(row)
            # Fetch associated measurements
            measurements = []
            for mrow in conn.execute(
                "SELECT * FROM cards.ligandmetal_stability_measured WHERE card_id = ?",
                (d.get("card_id"),),
            ):
                measurements.append(dict(mrow))
            d["measurements"] = measurements[:20]
            return {"type": "vlm", "id": f"vlm_{raw_id}", **d}

    elif prefix == "beta_def":
        row = conn.execute(
            """SELECT DISTINCT c.beta_definition_id, c.metal_id, c.ligand_id,
                      m.metal_name_SRD, l.ligand_name_SRD
               FROM cards.ligandmetal_card c
               JOIN cards.metal_card m ON c.metal_id = m.metal_id
               JOIN cards.ligand_card l ON c.ligand_id = l.ligand_id
               WHERE c.beta_definition_id = ?
               LIMIT 1""",
            (raw_id,),
        ).fetchone()
        if row:
            return {"type": "beta_def", "id": f"beta_def_{raw_id}", **dict(row)}

    elif prefix in ("ref_eq_net", "network"):
        row = conn.execute(
            """SELECT n.*, m.collection_id, m.map_key,
                      m.condition_temperature, m.condition_ionic_strength,
                      c.metal_name, c.ligand_name
               FROM maps.eq_network n
               JOIN maps.eq_map m ON n.map_id = m.map_id
               JOIN maps.eq_map_collection c ON m.collection_id = c.collection_id
               WHERE n.network_db_id = ?""",
            (raw_id,),
        ).fetchone()
        if row:
            return {"type": "network", "id": f"ref_eq_net_{raw_id}", **dict(row)}

    elif prefix in ("ref_eq_map", "map"):
        row = conn.execute(
            """SELECT m.*, c.metal_name, c.ligand_name,
                      c.total_entries, c.total_networks
               FROM maps.eq_map m
               JOIN maps.eq_map_collection c ON m.collection_id = c.collection_id
               WHERE m.map_id = ?""",
            (raw_id,),
        ).fetchone()
        if row:
            return {"type": "map", "id": f"ref_eq_map_{raw_id}", **dict(row)}

    elif prefix == "lit":
        row = conn.execute(
            "SELECT * FROM cards.ref_literature_alt WHERE literature_alt_id = ?",
            (raw_id,),
        ).fetchone()
        if row:
            return {"type": "literature", "id": f"lit_{raw_id}", **dict(row)}

    return None


