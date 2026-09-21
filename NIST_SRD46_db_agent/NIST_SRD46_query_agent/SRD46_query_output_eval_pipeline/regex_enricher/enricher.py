"""Main enrichment orchestrator.

Loads the 3 markdown files per run (result, history, ref_ids), strips
header/verdict sections from the result, splits into paragraphs, runs
token extraction (regex + Argo), queries the DB for top-10 closest
numeric matches, and caches the output.
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..db_support_helpers.db_reference import open_reference_connection
from .regex_support_helpers.models import (
    Claim,
    ClaimAnnotatedDocument,
    ClaimParagraph,
    GroundedClaim,
    claim_doc_from_dict,
    claim_doc_to_dict,
)
from ..input_support_helpers.parse_ref_ids import parse_ref_ids
from ..input_support_helpers.scan import DEFAULT_OUTPUT_ROOT
_WORKSPACE_ROOT = Path(__file__).absolute().parents[4]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

from .argo_enricher import enrich_paragraph_with_argo, merge_spans
from .regex_support_helpers.models import (
    EnrichedDocument,
    NumericSpan,
    ParagraphAnnotation,
    TokenSpan,
    document_from_dict,
    document_to_dict,
)
from .regex_support_helpers.numeric_matcher import (
    collect_ref_ids_by_prefix,
    find_closest_matches,
)
from .regex_support_helpers.token_extractor import extract_all_spans

log = logging.getLogger("regex_enricher")

# ---------------------------------------------------------------------------
# Header / verdict stripping for result files
# ---------------------------------------------------------------------------

_RESULT_HEADER_RE = re.compile(
    r"^#\s+Q[\d.]+\s+--\s+Result.*?^---\s*$",
    re.MULTILINE | re.DOTALL,
)
_VERDICT_SECTION_RE = re.compile(
    r"^#{1,3}\s+Verdict\s*&?\s*Explanation.*",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def _strip_result_envelope(text: str) -> str:
    """Remove the header block and verdict section from a result file."""
    text = _RESULT_HEADER_RE.sub("", text, count=1).lstrip()
    text = _VERDICT_SECTION_RE.sub("", text).rstrip()
    return text


# ---------------------------------------------------------------------------
# Section splitting (section-by-section, not paragraph-by-paragraph)
# ---------------------------------------------------------------------------

_PARAGRAPH_SEP = re.compile(r"\n{2,}")

# Match markdown headings (## or ### or ####), or --- horizontal rules
_SECTION_HEAD_RE = re.compile(r"^(#{2,4}\s+.+)$", re.MULTILINE)


def _split_paragraphs(text: str) -> list[str]:
    """Split answer into semantic sections, keeping heading + body + tables
    together as one unit.

    Strategy: split on markdown headings (##/###/####).  Each heading starts
    a new section that includes everything until the next heading or EOF.
    Standalone ``---`` separators are dropped.  Heading-only sections are
    merged into the following section.
    """
    sections: list[str] = []

    # Find all heading positions
    heading_positions: list[int] = []
    for m in _SECTION_HEAD_RE.finditer(text):
        heading_positions.append(m.start())

    if not heading_positions:
        # No headings — fall back to blank-line splitting
        return [p.strip() for p in _PARAGRAPH_SEP.split(text) if p.strip()]

    # Content before first heading (preamble)
    preamble = text[:heading_positions[0]].strip()
    if preamble and preamble != "---":
        sections.append(preamble)

    # Each heading starts a section up to next heading
    for i, start in enumerate(heading_positions):
        end = heading_positions[i + 1] if i + 1 < len(heading_positions) else len(text)
        chunk = text[start:end].strip()
        # Remove trailing --- separators
        chunk = re.sub(r"\n---\s*$", "", chunk).strip()
        if chunk and chunk != "---":
            sections.append(chunk)

    # Merge heading-only sections into the next section (forward merge)
    merged: list[str] = []
    pending_heading: str | None = None
    for s in sections:
        body = re.sub(r"^#{2,4}\s+.+$", "", s, flags=re.MULTILINE).strip()
        if not body:
            # Heading-only section — save to prepend to next
            if pending_heading:
                pending_heading = pending_heading + "\n\n" + s
            else:
                pending_heading = s
        else:
            if pending_heading:
                s = pending_heading + "\n\n" + s
                pending_heading = None
            merged.append(s)

    # If there's a trailing heading-only with no following section, keep it
    if pending_heading:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + pending_heading
        else:
            merged.append(pending_heading)

    return [s for s in merged if s.strip()]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_dir() -> Path:
    d = (_QUERY_OUTPUT_ROOT / "_enrichment_cache")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(
    model: str,
    question_id: str,
    batch: int,
    argo: bool,
    argo_model: str | None = None,
) -> str:
    if argo:
        model_tag = re.sub(r"[^a-zA-Z0-9_.-]+", "_", argo_model or "default").strip("_")
        tag = f"argo_{model_tag or 'default'}"
    else:
        tag = "regex"
    return f"{model}__{question_id}__batch{batch}__{tag}"


def _cache_path(
    model: str,
    question_id: str,
    batch: int,
    argo: bool,
    argo_model: str | None = None,
) -> Path:
    return _cache_dir() / f"{_cache_key(model, question_id, batch, argo, argo_model)}.json"


def _load_cache(
    model: str,
    question_id: str,
    batch: int,
    argo: bool,
    argo_model: str | None = None,
) -> dict[str, EnrichedDocument] | None:
    p = _cache_path(model, question_id, batch, argo, argo_model)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            return {k: document_from_dict(v) for k, v in raw.items()}
        except (json.JSONDecodeError, OSError, KeyError):
            log.warning("Cache corrupt, ignoring: %s", p)
            return None
    return None


def _save_cache(
    model: str,
    question_id: str,
    batch: int,
    argo: bool,
    argo_model: str | None,
    docs: dict[str, EnrichedDocument],
) -> None:
    p = _cache_path(model, question_id, batch, argo, argo_model)
    payload = {k: document_to_dict(v) for k, v in docs.items()}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Load extra chemical names from DB for better extraction
# ---------------------------------------------------------------------------

def _load_extra_chem_names(conn) -> list[str]:
    """Pull ligand and metal names from the DB for regex matching."""
    names: list[str] = []
    for row in conn.execute(
        "SELECT DISTINCT ligand_name_SRD FROM cards.ligand_card "
        "WHERE ligand_name_SRD IS NOT NULL"
    ):
        name = row[0] if not isinstance(row, dict) else row["ligand_name_SRD"]
        if name and len(name) >= 3:
            names.append(name)
    for row in conn.execute(
        "SELECT DISTINCT metal_name_SRD FROM cards.metal_card "
        "WHERE metal_name_SRD IS NOT NULL"
    ):
        name = row[0] if not isinstance(row, dict) else row["metal_name_SRD"]
        if name and len(name) >= 3:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Core enrichment
# ---------------------------------------------------------------------------

def _enrich_single_doc(
    text: str,
    doc_type: str,
    source_file: str,
    ref_ids_by_prefix: dict[str, list[int]],
    conn,
    extra_chem_names: list[str],
    *,
    use_argo: bool = True,
    argo_model: str | None = None,
) -> EnrichedDocument:
    """Enrich a single markdown document."""
    if doc_type == "result":
        text = _strip_result_envelope(text)

    paragraphs_text = _split_paragraphs(text)
    paragraphs: list[ParagraphAnnotation] = []

    for pidx, para_text in enumerate(paragraphs_text):
        # Step 1: regex extraction
        regex_spans = extract_all_spans(para_text, extra_chem_names)

        # Step 2: Argo LLM extraction (optional)
        if use_argo:
            argo_spans = enrich_paragraph_with_argo(
                para_text, model=argo_model,
            )
            merged = merge_spans(regex_spans, argo_spans)
        else:
            merged = regex_spans

        # Step 3: numeric matching for each NumericSpan
        numeric_matches: dict[int, list] = {}
        for span_idx, span in enumerate(merged):
            if isinstance(span, NumericSpan) and ref_ids_by_prefix:
                matches = find_closest_matches(span, ref_ids_by_prefix, conn)
                if matches:
                    numeric_matches[span_idx] = matches

        paragraphs.append(ParagraphAnnotation(
            paragraph_index=pidx,
            text=para_text,
            spans=merged,
            numeric_matches=numeric_matches,
        ))
        log.info(
            "  [%s] para %d: %d spans (%d numeric matches)",
            doc_type, pidx, len(merged),
            sum(len(v) for v in numeric_matches.values()),
        )

    return EnrichedDocument(
        source_file=source_file,
        doc_type=doc_type,
        paragraphs=paragraphs,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_run(
    model: str,
    question_id: str,
    batch: int,
    *,
    output_root: str | Path | None = None,
    use_argo: bool = True,
    argo_model: str | None = None,
    use_cache: bool = True,
    db_dir: str | Path | None = None,
) -> dict[str, EnrichedDocument]:
    """Enrich all 3 markdown files for a single run.

    Returns ``{"result": EnrichedDocument, "history": ..., "ref_ids": ...}``.

     If *use_cache* is True (default), results are loaded from
     ``eval_cache/enrichment/`` when available. Freshly generated results are
     always written back to cache so forced reruns refresh stored output.
     Cache keys include argo mode and argo model, so regex/argo and different
     argo models coexist.
    """
    # ── resolve argo_model default ──────────────────────────
    if argo_model is None:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import ENRICHER_MODEL
            argo_model = ENRICHER_MODEL
        except ImportError:
            pass  # fall back to argo_config.MODEL inside call_argo

    # ── try cache first ─────────────────────────────────────
    if use_cache:
        cached = _load_cache(
            model,
            question_id,
            batch,
            argo=use_argo,
            argo_model=argo_model if use_argo else None,
        )
        if cached is not None:
            log.info(
                "Cache HIT for %s/%s/batch%d (argo=%s, model=%s)",
                model, question_id, batch, use_argo, argo_model,
            )
            return cached

    root = Path(output_root) if output_root else DEFAULT_OUTPUT_ROOT
    model_dir = root / f"Model_{model}"
    question_dir = model_dir / question_id

    # Locate files
    files: dict[str, Path] = {}
    for kind in ("result", "history", "ref_ids"):
        p = question_dir / f"{question_id}_{kind}_batch{batch}.md"
        if p.exists():
            files[kind] = p

    if not files:
        log.warning("No files found for %s/%s/batch%d", model, question_id, batch)
        return {}

    # Parse ref_ids to get the entity references for numeric matching
    ref_ids_by_prefix: dict[str, list[int]] = {}
    if "ref_ids" in files:
        from ..input_support_helpers.parse_ref_ids import parse_ref_ids
        entity_refs = parse_ref_ids(files["ref_ids"])
        ref_ids_by_prefix = collect_ref_ids_by_prefix(entity_refs)

    # Open DB connection for numeric matching and chem-name lookup
    conn = open_reference_connection(db_dir)
    try:
        extra_chem_names = _load_extra_chem_names(conn)

        docs: dict[str, EnrichedDocument] = {}
        for kind, path in files.items():
            log.info("Enriching %s/%s/batch%d/%s …", model, question_id, batch, kind)
            text = path.read_text(encoding="utf-8", errors="replace")
            docs[kind] = _enrich_single_doc(
                text=text,
                doc_type=kind,
                source_file=str(path),
                ref_ids_by_prefix=ref_ids_by_prefix,
                conn=conn,
                extra_chem_names=extra_chem_names,
                use_argo=use_argo,
                argo_model=argo_model,
            )
    finally:
        conn.close()

    # ── persist to cache ────────────────────────────────────
    if docs:
        try:
            _save_cache(
                model,
                question_id,
                batch,
                argo=use_argo,
                argo_model=argo_model if use_argo else None,
                docs=docs,
            )
            log.info("Cache SAVED for %s/%s/batch%d (argo=%s, model=%s)",
                     model, question_id, batch, use_argo, argo_model)
        except OSError:
            log.warning("Failed to write cache for %s/%s/batch%d",
                        model, question_id, batch)

    return docs


# ═══════════════════════════════════════════════════════════════════════
# Claim-based enrichment pipeline  (v2)
# ═══════════════════════════════════════════════════════════════════════

_CLAIMS_CACHE_FORMAT = 6
_CLAIMS_LOCK_STALE_SECS = 6 * 60 * 60

# ---------------------------------------------------------------------------
# Per-run claims-cache base directory (thread-local override)
# ---------------------------------------------------------------------------
# The claims cache + lock files for a run live beside the run's _output_eval.
# The browser and freeform runner set this thread-local to the run's actual
# eval root before reading/writing claims caches. Without an override, use the
# repository-local query evaluation directory.
_claims_eval_tls = threading.local()


def set_claims_eval_root(eval_root) -> None:
    """Set the per-run claims-cache base ``_output_eval`` dir for this thread.

    Pass ``None`` to restore the active production default.
    """
    _claims_eval_tls.root = Path(eval_root) if eval_root else None


def _claims_eval_base() -> Path:
    root = getattr(_claims_eval_tls, "root", None)
    return root if root is not None else _QUERY_EVAL_ROOT


def _claims_cache_dir(model: str, question_id: str) -> Path:
    d = _claims_eval_base() / f"Model_{model}" / question_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _claims_cache_key(model: str, question_id: str, batch: int, argo_model: str | None) -> str:
    return f"claims_batch{batch}"


def _claims_cache_path(model: str, question_id: str, batch: int, argo_model: str | None) -> Path:
    return _claims_cache_dir(model, question_id) / f"{_claims_cache_key(model, question_id, batch, argo_model)}.json"


def _claims_lock_path(model: str, question_id: str, batch: int, argo_model: str | None) -> Path:
    cache_path = _claims_cache_path(model, question_id, batch, argo_model)
    return cache_path.with_suffix(f"{cache_path.suffix}.lock")


def _claims_cache_metadata(
    argo_model: str | None,
    claim_review_rounds: int | None,
) -> dict[str, Any]:
    from .claim_classifier.claim_classifier import (
        CLAIM_CLASSIFIER_STRATEGY_VERSION,
        resolve_claim_classifier_review_rounds,
    )
    from .claim_grounder.claim_grounder_ReAct import resolve_grounder_react_rounds

    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import GROUNDER_MODEL

        grounder_model = GROUNDER_MODEL or argo_model or "default"
    except (ImportError, AttributeError):
        grounder_model = argo_model or "default"

    return {
        "cache_format": _CLAIMS_CACHE_FORMAT,
        "classifier_strategy_version": CLAIM_CLASSIFIER_STRATEGY_VERSION,
        "classifier_review_rounds": resolve_claim_classifier_review_rounds(claim_review_rounds),
        "grounder_react_rounds": resolve_grounder_react_rounds(None),
        "classifier_model": argo_model or "default",
        "grounder_model": grounder_model,
    }


def _resolve_claim_paragraph_workers() -> int:
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import CLAIM_PARAGRAPH_WORKERS

        value = CLAIM_PARAGRAPH_WORKERS
    except (ImportError, AttributeError):
        value = 4

    try:
        workers = int(value)
    except (TypeError, ValueError):
        workers = 4

    return max(1, min(workers, 32))


def _claims_lock_payload(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
    claim_review_rounds: int | None,
) -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "created_at": time.time(),
        "model": model,
        "question_id": question_id,
        "batch": batch,
        "classifier_model": argo_model or "default",
        "classifier_review_rounds": claim_review_rounds,
    }


def _read_claims_lock(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except (json.JSONDecodeError, OSError):
        pass
    try:
        return {"created_at": path.stat().st_mtime}
    except OSError:
        return {"created_at": None}


def _claims_lock_age_seconds(path: Path, payload: dict[str, Any] | None) -> float | None:
    created_at = None if payload is None else payload.get("created_at")
    if not isinstance(created_at, (int, float)):
        try:
            created_at = path.stat().st_mtime
        except OSError:
            return None
    return max(0.0, time.time() - float(created_at))


def _claims_lock_process_is_alive(payload: dict[str, Any] | None) -> bool | None:
    if not isinstance(payload, dict):
        return None

    pid = payload.get("pid")
    host = payload.get("host")
    if not isinstance(pid, int) or pid <= 0:
        return None
    if not isinstance(host, str) or host.lower() != socket.gethostname().lower():
        return None
    if pid == os.getpid():
        return True

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _claims_lock_is_stale(path: Path, payload: dict[str, Any] | None) -> bool:
    process_alive = _claims_lock_process_is_alive(payload)
    if process_alive is False:
        return True
    age_seconds = _claims_lock_age_seconds(path, payload)
    return age_seconds is not None and age_seconds > _CLAIMS_LOCK_STALE_SECS


def _release_claims_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        log.warning("Failed to remove claims lock: %s", path)


def _try_acquire_claims_lock(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
    claim_review_rounds: int | None,
) -> tuple[bool, Path, dict[str, Any] | None]:
    path = _claims_lock_path(model, question_id, batch, argo_model)
    payload = _claims_lock_payload(model, question_id, batch, argo_model, claim_review_rounds)

    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = _read_claims_lock(path)
            if _claims_lock_is_stale(path, existing):
                _release_claims_lock(path)
                log.warning("Removed stale claims lock: %s", path)
                continue
            return False, path, existing
        else:
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
            except Exception:
                _release_claims_lock(path)
                raise
            return True, path, payload

    return False, path, _read_claims_lock(path)


def is_claims_enrichment_in_progress(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
) -> bool:
    path = _claims_lock_path(model, question_id, batch, argo_model)
    payload = _read_claims_lock(path)
    if payload is None:
        return False
    if _claims_lock_is_stale(path, payload):
        _release_claims_lock(path)
        log.warning("Removed stale claims lock during status check: %s", path)
        return False
    return True


def _read_claims_cache_payload(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
) -> tuple[dict[str, Any] | None, ClaimAnnotatedDocument | None]:
    p = _claims_cache_path(model, question_id, batch, argo_model)
    if not p.exists():
        return None, None

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log.warning("Claims cache corrupt: %s", p)
        return None, None

    if not isinstance(raw, dict):
        log.warning("Claims cache corrupt: %s", p)
        return None, None

    doc_payload = raw.get("doc")
    if not isinstance(doc_payload, dict):
        log.warning("Claims cache corrupt: %s", p)
        return None, None

    try:
        return raw, claim_doc_from_dict(doc_payload)
    except (KeyError, TypeError, ValueError):
        log.warning("Claims cache corrupt: %s", p)
        return None, None


def _load_claims_cache(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
    claim_review_rounds: int | None = None,
) -> ClaimAnnotatedDocument | None:
    p = _claims_cache_path(model, question_id, batch, argo_model)
    raw, doc = _read_claims_cache_payload(model, question_id, batch, argo_model)
    if raw is not None and doc is not None:
        expected = _claims_cache_metadata(argo_model, claim_review_rounds)
        if raw.get("cache_format") != expected["cache_format"]:
            log.info("Claims cache stale (format): %s", p)
            return None
        if raw.get("classifier_strategy_version") != expected["classifier_strategy_version"]:
            log.info("Claims cache stale (strategy): %s", p)
            return None
        if raw.get("classifier_review_rounds") != expected["classifier_review_rounds"]:
            log.info("Claims cache stale (review rounds): %s", p)
            return None
        if raw.get("grounder_react_rounds") != expected["grounder_react_rounds"]:
            log.info("Claims cache stale (grounder react rounds): %s", p)
            return None
        if raw.get("classifier_model") != expected["classifier_model"]:
            log.info("Claims cache stale (classifier model): %s", p)
            return None
        if raw.get("grounder_model") != expected["grounder_model"]:
            log.info("Claims cache stale (grounder model): %s", p)
            return None
        if raw.get("complete") is not True:
            log.info("Claims cache incomplete: %s", p)
            return None
        return doc
    return None


def load_renderable_claims_cache(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
) -> tuple[ClaimAnnotatedDocument | None, str | None]:
    """Load any parseable claims cache for browser rendering.

    This is intentionally more permissive than ``_load_claims_cache``:
    - completed legacy caches still render,
    - in-progress checkpoints still render,
    - current config/model mismatches do not block display.
    """
    raw, doc = _read_claims_cache_payload(model, question_id, batch, argo_model)
    if raw is None or doc is None:
        return None, None

    if raw.get("complete") is False:
        return doc, "partial"
    if raw.get("complete") is True:
        return doc, "complete"
    return doc, "legacy"


def _save_claims_cache(
    model: str,
    question_id: str,
    batch: int,
    argo_model: str | None,
    claim_review_rounds: int | None,
    doc: ClaimAnnotatedDocument,
    *,
    complete: bool = True,
) -> None:
    p = _claims_cache_path(model, question_id, batch, argo_model)
    payload = {
        **_claims_cache_metadata(argo_model, claim_review_rounds),
        "complete": complete,
        "doc": claim_doc_to_dict(doc),
    }
    p.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def enrich_run_claims(
    model: str,
    question_id: str,
    batch: int,
    *,
    output_root: str | Path | None = None,
    eval_root: str | Path | None = None,
    argo_model: str | None = None,
    claim_review_rounds: int | None = None,
    use_cache: bool = True,
    skip_if_locked: bool = False,
) -> ClaimAnnotatedDocument | None:
    """Run claim classification + grounding for a single answer.

    1. Ensure tool_eval and answer files exist in ``_output_eval/``.
    2. Split answer into paragraphs.
     3. Classify all paragraphs first, then ground all paragraphs.
         Both phases can run in parallel across paragraphs.
     4. Persist and return a ``ClaimAnnotatedDocument``. If *use_cache* is
         True, an existing claims cache is reused before recomputing.

    If *skip_if_locked* is True and another process is already computing the
    claims cache for the same run, return ``None`` instead of starting a
    duplicate enrichment pass.
    """
    # Bind the per-run claims-cache location for this thread so cache reads,
    # writes, and locks all live beside the run's _output_eval (per-user aware).
    set_claims_eval_root(eval_root)

    # ── resolve argo models ─────────────────────────────────
    if argo_model is None:
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import CLAIM_CLASSIFIER_MODEL
            argo_model = CLAIM_CLASSIFIER_MODEL
        except (ImportError, AttributeError):
            try:
                from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import ENRICHER_MODEL
                argo_model = ENRICHER_MODEL
            except ImportError:
                pass
    # Use a separate (larger) model for grounding — needs big context
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import GROUNDER_MODEL
        grounder_model = GROUNDER_MODEL
    except (ImportError, AttributeError):
        grounder_model = argo_model
    from .claim_classifier.claim_classifier import resolve_claim_classifier_review_rounds

    claim_review_rounds = resolve_claim_classifier_review_rounds(claim_review_rounds)

    # ── cache check ─────────────────────────────────────────
    if use_cache:
        cached = _load_claims_cache(
            model,
            question_id,
            batch,
            argo_model,
            claim_review_rounds,
        )
        if cached is not None:
            log.info("Claims cache HIT for %s/%s/batch%d", model, question_id, batch)
            return cached

    lock_acquired = False
    lock_path: Path | None = None
    existing_lock: dict[str, Any] | None = None
    try:
        lock_acquired, lock_path, existing_lock = _try_acquire_claims_lock(
            model,
            question_id,
            batch,
            argo_model,
            claim_review_rounds,
        )
        if not lock_acquired:
            age_seconds = _claims_lock_age_seconds(lock_path, existing_lock)
            age_text = ""
            if age_seconds is not None:
                age_text = f" (age={age_seconds:.1f}s)"
            message = (
                f"Claims enrichment already in progress for {model}/{question_id}/batch{batch}{age_text}"
            )
            if skip_if_locked:
                log.info("%s; skipping duplicate request", message)
                return None
            raise RuntimeError(message)

        if use_cache:
            cached = _load_claims_cache(
                model,
                question_id,
                batch,
                argo_model,
                claim_review_rounds,
            )
            if cached is not None:
                log.info("Claims cache HIT after lock acquisition for %s/%s/batch%d", model, question_id, batch)
                return cached

        root = Path(output_root) if output_root else DEFAULT_OUTPUT_ROOT
        eval_dir = Path(eval_root) if eval_root else _QUERY_EVAL_ROOT

        # ── ensure extraction has run ──────────────────────────
        from ..input_support_helpers.extract_tool_results import extract_run as _extract

        tool_eval_path = eval_dir / f"Model_{model}" / question_id / f"tool_eval_batch{batch}.md"
        answer_path = eval_dir / f"Model_{model}" / question_id / f"answer_batch{batch}.md"

        if not tool_eval_path.exists() or not answer_path.exists():
            _extract(model, question_id, batch, output_root=root, eval_root=eval_dir)

        if not answer_path.exists():
            log.warning("No answer found for %s/%s/batch%d", model, question_id, batch)
            return None

        answer_text = answer_path.read_text(encoding="utf-8", errors="replace")
        tool_eval_text = ""
        if tool_eval_path.exists():
            tool_eval_text = tool_eval_path.read_text(encoding="utf-8", errors="replace")

        # ── split into paragraphs ──────────────────────────────
        paragraphs_text = _split_paragraphs(answer_text)
        if not paragraphs_text:
            log.warning("Empty answer for %s/%s/batch%d", model, question_id, batch)
            return None

        # ── classify + ground per paragraph ─────────────────────
        from .claim_classifier.claim_classifier import classify_claims
        from .claim_grounder.claim_grounder import ground_claims

        paragraph_workers = min(len(paragraphs_text), _resolve_claim_paragraph_workers())
        indexed_paragraphs = list(enumerate(paragraphs_text))

        def _classify_paragraph(item: tuple[int, str]) -> tuple[int, str, list[Claim]]:
            pidx, para_text = item
            claims = classify_claims(
                para_text,
                model=argo_model,
                max_review_rounds=claim_review_rounds,
            )
            log.info("  [para %d] %d claims classified", pidx, len(claims))
            return pidx, para_text, claims

        def _ground_paragraph(item: tuple[int, str, list[Claim]]) -> ClaimParagraph:
            pidx, para_text, claims = item
            grounded: list[GroundedClaim] = []
            if claims and tool_eval_text:
                grounded = ground_claims(
                    para_text,
                    claims,
                    tool_eval_text,
                    model=grounder_model,
                )
                log.info("  [para %d] %d claims grounded", pidx, len(grounded))

            grounded_indices = {g.claim_index for g in grounded}
            for ci in range(len(claims)):
                if ci not in grounded_indices:
                    support_class = "no_tool_data" if claims[ci].claim_type == "filler" else "unsupported"
                    grounded.append(GroundedClaim(
                        claim_index=ci,
                        support_class=support_class,
                    ))

            return ClaimParagraph(
                paragraph_index=pidx,
                text=para_text,
                claims=claims,
                grounded_claims=sorted(grounded, key=lambda g: g.claim_index),
            )

        if paragraph_workers > 1:
            log.info(
                "Running classifier phase for %d paragraph(s) with %d worker(s)",
                len(indexed_paragraphs),
                paragraph_workers,
            )
            with ThreadPoolExecutor(
                max_workers=paragraph_workers,
                thread_name_prefix="claim-classify",
            ) as executor:
                classified_rows = list(executor.map(_classify_paragraph, indexed_paragraphs))
        else:
            classified_rows = [_classify_paragraph(item) for item in indexed_paragraphs]

        classified_rows = sorted(classified_rows, key=lambda item: item[0])

        result_path = root / f"Model_{model}" / question_id / f"{question_id}_result_batch{batch}.md"
        claim_paragraphs_by_index: dict[int, ClaimParagraph] = {
            pidx: ClaimParagraph(
                paragraph_index=pidx,
                text=para_text,
                claims=claims,
                grounded_claims=[],
            )
            for pidx, para_text, claims in classified_rows
        }

        checkpoint_doc = ClaimAnnotatedDocument(
            source_file=str(result_path),
            doc_type="answer",
            paragraphs=[claim_paragraphs_by_index[index] for index in sorted(claim_paragraphs_by_index)],
        )
        try:
            _save_claims_cache(
                model,
                question_id,
                batch,
                argo_model,
                claim_review_rounds,
                checkpoint_doc,
                complete=False,
            )
            log.info(
                "Claims cache checkpoint SAVED for %s/%s/batch%d (classification complete: %d paragraph(s))",
                model,
                question_id,
                batch,
                len(classified_rows),
            )
        except OSError:
            log.warning(
                "Failed to save claims cache checkpoint for %s/%s/batch%d after classification",
                model,
                question_id,
                batch,
            )

        if paragraph_workers > 1:
            log.info(
                "Running grounder phase for %d paragraph(s) with %d worker(s)",
                len(classified_rows),
                paragraph_workers,
            )
            with ThreadPoolExecutor(
                max_workers=paragraph_workers,
                thread_name_prefix="claim-ground",
            ) as executor:
                future_to_index = {
                    executor.submit(_ground_paragraph, item): item[0]
                    for item in classified_rows
                }
                grounded_done = 0
                for future in as_completed(future_to_index):
                    claim_paragraph = future.result()
                    claim_paragraphs_by_index[claim_paragraph.paragraph_index] = claim_paragraph
                    grounded_done += 1

                    checkpoint_doc = ClaimAnnotatedDocument(
                        source_file=str(result_path),
                        doc_type="answer",
                        paragraphs=[claim_paragraphs_by_index[index] for index in sorted(claim_paragraphs_by_index)],
                    )
                    try:
                        _save_claims_cache(
                            model,
                            question_id,
                            batch,
                            argo_model,
                            claim_review_rounds,
                            checkpoint_doc,
                            complete=False,
                        )
                        log.info(
                            "Claims cache checkpoint SAVED for %s/%s/batch%d (%d/%d paragraph(s) grounded)",
                            model,
                            question_id,
                            batch,
                            grounded_done,
                            len(classified_rows),
                        )
                    except OSError:
                        log.warning(
                            "Failed to save claims cache checkpoint for %s/%s/batch%d after grounding paragraph %d",
                            model,
                            question_id,
                            batch,
                            claim_paragraph.paragraph_index,
                        )
        else:
            for grounded_done, item in enumerate(classified_rows, start=1):
                claim_paragraph = _ground_paragraph(item)
                claim_paragraphs_by_index[claim_paragraph.paragraph_index] = claim_paragraph

                checkpoint_doc = ClaimAnnotatedDocument(
                    source_file=str(result_path),
                    doc_type="answer",
                    paragraphs=[claim_paragraphs_by_index[index] for index in sorted(claim_paragraphs_by_index)],
                )
                try:
                    _save_claims_cache(
                        model,
                        question_id,
                        batch,
                        argo_model,
                        claim_review_rounds,
                        checkpoint_doc,
                        complete=False,
                    )
                    log.info(
                        "Claims cache checkpoint SAVED for %s/%s/batch%d (%d/%d paragraph(s) grounded)",
                        model,
                        question_id,
                        batch,
                        grounded_done,
                        len(classified_rows),
                    )
                except OSError:
                    log.warning(
                        "Failed to save claims cache checkpoint for %s/%s/batch%d after grounding paragraph %d",
                        model,
                        question_id,
                        batch,
                        claim_paragraph.paragraph_index,
                    )

        claim_paragraphs = [claim_paragraphs_by_index[index] for index in sorted(claim_paragraphs_by_index)]

        doc = ClaimAnnotatedDocument(
            source_file=str(result_path),
            doc_type="answer",
            paragraphs=claim_paragraphs,
        )

        # ── persist cache ──────────────────────────────────────
        try:
            _save_claims_cache(
                model,
                question_id,
                batch,
                argo_model,
                claim_review_rounds,
                doc,
                complete=True,
            )
            log.info("Claims cache SAVED for %s/%s/batch%d", model, question_id, batch)
        except OSError:
            log.warning("Failed to save claims cache for %s/%s/batch%d",
                        model, question_id, batch)

        return doc
    finally:
        if lock_acquired and lock_path is not None:
            _release_claims_lock(lock_path)


