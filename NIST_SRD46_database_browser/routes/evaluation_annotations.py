from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, request

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.regex_support_helpers.models import (
    CLAIM_TYPES,
    SUPPORT_CLASSES,
    Claim,
    ClaimAnnotatedDocument,
    ClaimParagraph,
    GroundedClaim,
    claim_doc_from_dict,
    claim_doc_to_dict,
)


MAX_ANNOTATION_HISTORY_DEPTH = 50


def manual_claims_path(eval_data_dir, model: str, question_id: str, batch: int) -> Path:
    return eval_data_dir(model, question_id) / f"claims_batch{batch}.manual.json"


def annotation_history_path(eval_data_dir, model: str, question_id: str, batch: int) -> Path:
    return eval_data_dir(model, question_id) / f"claims_batch{batch}.manual.history.json"


def load_manual_claims_doc(
    eval_data_dir,
    model: str,
    question_id: str,
    batch: int,
) -> tuple[ClaimAnnotatedDocument | None, dict | None]:
    path = manual_claims_path(eval_data_dir, model, question_id, batch)
    if not path.exists():
        return None, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None

    if not isinstance(raw, dict) or not isinstance(raw.get("doc"), dict):
        return None, None

    try:
        return claim_doc_from_dict(raw["doc"]), raw
    except (KeyError, TypeError, ValueError):
        return None, None


def save_manual_claims_doc(
    eval_data_dir,
    model: str,
    question_id: str,
    batch: int,
    doc: ClaimAnnotatedDocument,
) -> dict:
    payload = {
        "manual_override": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_claims_cache": f"claims_batch{batch}.json",
        "doc": claim_doc_to_dict(doc),
    }
    _save_json(manual_claims_path(eval_data_dir, model, question_id, batch), payload)
    return payload


def load_claim_doc_for_annotation(
    eval_data_dir,
    model: str,
    question_id: str,
    batch: int,
) -> tuple[ClaimAnnotatedDocument | None, str | None, dict | None]:
    manual_doc, manual_meta = load_manual_claims_doc(eval_data_dir, model, question_id, batch)
    if manual_doc is not None:
        return manual_doc, "manual", manual_meta

    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher.enricher import load_renderable_claims_cache

    doc, cache_state = load_renderable_claims_cache(
        model=model,
        question_id=question_id,
        batch=batch,
        argo_model=None,
    )
    return doc, cache_state, None


def load_annotation_history(eval_data_dir, model: str, question_id: str, batch: int) -> dict:
    path = annotation_history_path(eval_data_dir, model, question_id, batch)
    empty_history = {"undo_stack": [], "redo_stack": [], "updated_at": ""}
    if not path.exists():
        return empty_history

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty_history

    if not isinstance(raw, dict):
        return empty_history

    undo_stack = [snapshot for snapshot in raw.get("undo_stack", []) if isinstance(snapshot, dict)]
    redo_stack = [snapshot for snapshot in raw.get("redo_stack", []) if isinstance(snapshot, dict)]
    return {
        "undo_stack": undo_stack,
        "redo_stack": redo_stack,
        "updated_at": str(raw.get("updated_at", "")),
    }


def annotation_history_counts(eval_data_dir, model: str, question_id: str, batch: int) -> tuple[int, int]:
    history = load_annotation_history(eval_data_dir, model, question_id, batch)
    return len(history["undo_stack"]), len(history["redo_stack"])


def record_annotation_undo_state(
    eval_data_dir,
    model: str,
    question_id: str,
    batch: int,
    snapshot: ClaimAnnotatedDocument | dict,
) -> dict:
    history = load_annotation_history(eval_data_dir, model, question_id, batch)
    undo_stack = list(history["undo_stack"])
    undo_stack.append(_snapshot_to_dict(snapshot))
    if len(undo_stack) > MAX_ANNOTATION_HISTORY_DEPTH:
        undo_stack = undo_stack[-MAX_ANNOTATION_HISTORY_DEPTH:]

    updated_history = {
        "undo_stack": undo_stack,
        "redo_stack": [],
        "updated_at": _annotation_timestamp(),
    }
    _save_json(annotation_history_path(eval_data_dir, model, question_id, batch), updated_history)
    return updated_history


def apply_annotation_undo(eval_data_dir, model: str, question_id: str, batch: int) -> tuple[dict, dict]:
    current_doc, _, _ = load_claim_doc_for_annotation(eval_data_dir, model, question_id, batch)
    if current_doc is None:
        raise ValueError("No claim annotations available for this run")

    history = load_annotation_history(eval_data_dir, model, question_id, batch)
    undo_stack = list(history["undo_stack"])
    if not undo_stack:
        raise ValueError("No saved annotation changes available to undo")

    target_snapshot = undo_stack.pop()
    redo_stack = list(history["redo_stack"])
    redo_stack.append(claim_doc_to_dict(current_doc))
    if len(redo_stack) > MAX_ANNOTATION_HISTORY_DEPTH:
        redo_stack = redo_stack[-MAX_ANNOTATION_HISTORY_DEPTH:]

    restored_doc = claim_doc_from_dict(target_snapshot)
    meta = save_manual_claims_doc(eval_data_dir, model, question_id, batch, restored_doc)
    updated_history = {
        "undo_stack": undo_stack,
        "redo_stack": redo_stack,
        "updated_at": _annotation_timestamp(),
    }
    _save_json(annotation_history_path(eval_data_dir, model, question_id, batch), updated_history)
    return meta, updated_history


def apply_annotation_redo(eval_data_dir, model: str, question_id: str, batch: int) -> tuple[dict, dict]:
    current_doc, _, _ = load_claim_doc_for_annotation(eval_data_dir, model, question_id, batch)
    if current_doc is None:
        raise ValueError("No claim annotations available for this run")

    history = load_annotation_history(eval_data_dir, model, question_id, batch)
    redo_stack = list(history["redo_stack"])
    if not redo_stack:
        raise ValueError("No saved annotation changes available to redo")

    target_snapshot = redo_stack.pop()
    undo_stack = list(history["undo_stack"])
    undo_stack.append(claim_doc_to_dict(current_doc))
    if len(undo_stack) > MAX_ANNOTATION_HISTORY_DEPTH:
        undo_stack = undo_stack[-MAX_ANNOTATION_HISTORY_DEPTH:]

    restored_doc = claim_doc_from_dict(target_snapshot)
    meta = save_manual_claims_doc(eval_data_dir, model, question_id, batch, restored_doc)
    updated_history = {
        "undo_stack": undo_stack,
        "redo_stack": redo_stack,
        "updated_at": _annotation_timestamp(),
    }
    _save_json(annotation_history_path(eval_data_dir, model, question_id, batch), updated_history)
    return meta, updated_history


def clear_manual_annotation_state(eval_data_dir, model: str, question_id: str, batch: int) -> None:
    for path in (
        manual_claims_path(eval_data_dir, model, question_id, batch),
        annotation_history_path(eval_data_dir, model, question_id, batch),
    ):
        if not path.exists():
            continue
        path.unlink()


def annotation_summary(doc: ClaimAnnotatedDocument | None) -> tuple[int, int, int, dict[str, int]]:
    support_counts = {support: 0 for support in SUPPORT_CLASSES}
    total_claims = 0
    supported_claims = 0
    unsupported_claims = 0

    if doc is None:
        return total_claims, supported_claims, unsupported_claims, support_counts

    for paragraph in doc.paragraphs:
        total_claims += len(paragraph.claims)
        grounded_map = {grounded.claim_index: grounded for grounded in paragraph.grounded_claims}
        for claim_index in range(len(paragraph.claims)):
            grounded = grounded_map.get(claim_index)
            support_class = grounded.support_class if grounded else "unsupported"
            support_counts[support_class] = support_counts.get(support_class, 0) + 1
            if support_class in {"unsupported", "no_tool_data"}:
                unsupported_claims += 1
            else:
                supported_claims += 1

    return total_claims, supported_claims, unsupported_claims, support_counts


def add_annotation_claim(
    doc: ClaimAnnotatedDocument,
    paragraph_index: int,
    *,
    start: int,
    end: int,
    text: str,
    claim_type: str,
    support_class: str,
    canonical_ids: list[str] | None = None,
    evidence_snippet: str = "",
) -> int:
    paragraph = _get_claim_paragraph(doc, paragraph_index)
    start_i, end_i, anchored_text = _normalize_annotation_span(paragraph.text, start, end, text)
    normalized_claim_type = _normalize_claim_type(claim_type)
    normalized_support_class = _normalize_support_class(support_class)
    conflicts = _find_claim_conflicts(paragraph, start_i, end_i)
    if conflicts:
        raise ValueError(f"Selected span overlaps existing claims: {conflicts}")

    claim = Claim(
        start=start_i,
        end=end_i,
        text=anchored_text,
        claim_type=normalized_claim_type,
        metadata={
            "created_in_browser": True,
            "edited_in_browser": True,
            "edited_at": _annotation_timestamp(),
        },
    )
    paragraph.claims.append(claim)
    paragraph.grounded_claims.append(
        GroundedClaim(
            claim_index=len(paragraph.claims) - 1,
            canonical_ids=list(canonical_ids or []),
            support_class=normalized_support_class,
            evidence_snippet=str(evidence_snippet or "")[:200],
            tool_snippets=[],
        )
    )
    _reindex_claim_paragraph(paragraph)
    return paragraph.claims.index(claim)


def update_annotation_claim(
    doc: ClaimAnnotatedDocument,
    paragraph_index: int,
    claim_index: int,
    *,
    start: int,
    end: int,
    text: str,
    claim_type: str,
    support_class: str,
    canonical_ids: list[str] | None = None,
    evidence_snippet: str = "",
) -> int:
    paragraph = _get_claim_paragraph(doc, paragraph_index)
    if not (0 <= claim_index < len(paragraph.claims)):
        raise ValueError(f"claim_index must be between 0 and {len(paragraph.claims) - 1}")

    start_i, end_i, anchored_text = _normalize_annotation_span(paragraph.text, start, end, text)
    normalized_claim_type = _normalize_claim_type(claim_type)
    normalized_support_class = _normalize_support_class(support_class)
    conflicts = _find_claim_conflicts(paragraph, start_i, end_i, ignore_index=claim_index)
    if conflicts:
        raise ValueError(f"Updated span overlaps existing claims: {conflicts}")

    claim = paragraph.claims[claim_index]
    claim.start = start_i
    claim.end = end_i
    claim.text = anchored_text
    claim.claim_type = normalized_claim_type
    claim.metadata = _claim_metadata(claim.metadata)

    grounded = next((item for item in paragraph.grounded_claims if item.claim_index == claim_index), None)
    if grounded is None:
        grounded = GroundedClaim(claim_index=claim_index)
        paragraph.grounded_claims.append(grounded)
    grounded.canonical_ids = list(canonical_ids or [])
    grounded.support_class = normalized_support_class
    grounded.evidence_snippet = str(evidence_snippet or "")[:200]

    _reindex_claim_paragraph(paragraph)
    return paragraph.claims.index(claim)


def delete_annotation_claim(
    doc: ClaimAnnotatedDocument,
    paragraph_index: int,
    claim_index: int,
) -> None:
    paragraph = _get_claim_paragraph(doc, paragraph_index)
    if not (0 <= claim_index < len(paragraph.claims)):
        raise ValueError(f"claim_index must be between 0 and {len(paragraph.claims) - 1}")

    paragraph.claims.pop(claim_index)
    paragraph.grounded_claims = [
        grounded for grounded in paragraph.grounded_claims
        if grounded.claim_index != claim_index
    ]
    for grounded in paragraph.grounded_claims:
        if grounded.claim_index > claim_index:
            grounded.claim_index -= 1
    _reindex_claim_paragraph(paragraph)


def claims_cache_state(eval_data_dir, model: str, question_id: str, batch: int) -> str | None:
    if manual_claims_path(eval_data_dir, model, question_id, batch).exists():
        return "manual"

    path = eval_data_dir(model, question_id) / f"claims_batch{batch}.json"
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(raw, dict) or not isinstance(raw.get("doc"), dict):
        return None

    complete = raw.get("complete")
    if complete is True:
        return "complete"
    if complete is False:
        return "partial"
    return "legacy"


def register_routes(eval_bp, eval_data_dir) -> None:
    @eval_bp.route("/api/annotations/<model>/<question_id>/<int:batch>", methods=["GET"])
    def get_annotations(model: str, question_id: str, batch: int):
        doc, source_state, manual_meta = load_claim_doc_for_annotation(
            eval_data_dir,
            model,
            question_id,
            batch,
        )
        if doc is None:
            return jsonify({"error": "No claim annotations available for this run"}), 404

        total_claims, supported_claims, unsupported_claims, support_counts = annotation_summary(doc)
        undo_depth, redo_depth = annotation_history_counts(eval_data_dir, model, question_id, batch)
        return jsonify({
            "ok": True,
            "source": source_state or "generated",
            "manual_override": source_state == "manual",
            "updated_at": str((manual_meta or {}).get("updated_at", "")),
            "doc": claim_doc_to_dict(doc),
            "total_claims": total_claims,
            "supported_claims": supported_claims,
            "unsupported_claims": unsupported_claims,
            "support_counts": support_counts,
            "undo_depth": undo_depth,
            "redo_depth": redo_depth,
        })

    @eval_bp.route(
        "/api/annotations/<model>/<question_id>/<int:batch>/claims/<int:paragraph_index>",
        methods=["POST"],
    )
    def add_annotation(model: str, question_id: str, batch: int, paragraph_index: int):
        doc, _, _ = load_claim_doc_for_annotation(eval_data_dir, model, question_id, batch)
        if doc is None:
            return jsonify({"error": "No claim annotations available for this run"}), 404

        data = request.get_json(force=True)
        baseline_snapshot = claim_doc_to_dict(doc)
        try:
            canonical_ids = _normalize_canonical_ids(data.get("canonical_ids", []))
            claim_index = add_annotation_claim(
                doc,
                paragraph_index,
                start=data.get("start"),
                end=data.get("end"),
                text=str(data.get("text", "")),
                claim_type=str(data.get("claim_type", "")),
                support_class=str(data.get("support_class", "unsupported")),
                canonical_ids=canonical_ids,
                evidence_snippet=str(data.get("evidence_snippet", "")),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        meta = save_manual_claims_doc(eval_data_dir, model, question_id, batch, doc)
        history = record_annotation_undo_state(eval_data_dir, model, question_id, batch, baseline_snapshot)
        return jsonify({
            "ok": True,
            "paragraph_index": paragraph_index,
            "claim_index": claim_index,
            "manual_override": True,
            "updated_at": meta.get("updated_at", ""),
            "undo_depth": len(history["undo_stack"]),
            "redo_depth": len(history["redo_stack"]),
        })

    @eval_bp.route(
        "/api/annotations/<model>/<question_id>/<int:batch>/claims/<int:paragraph_index>/<int:claim_index>",
        methods=["PUT"],
    )
    def update_annotation(model: str, question_id: str, batch: int, paragraph_index: int, claim_index: int):
        doc, _, _ = load_claim_doc_for_annotation(eval_data_dir, model, question_id, batch)
        if doc is None:
            return jsonify({"error": "No claim annotations available for this run"}), 404

        data = request.get_json(force=True)
        baseline_snapshot = claim_doc_to_dict(doc)
        try:
            canonical_ids = _normalize_canonical_ids(data.get("canonical_ids", []))
            new_claim_index = update_annotation_claim(
                doc,
                paragraph_index,
                claim_index,
                start=data.get("start"),
                end=data.get("end"),
                text=str(data.get("text", "")),
                claim_type=str(data.get("claim_type", "")),
                support_class=str(data.get("support_class", "unsupported")),
                canonical_ids=canonical_ids,
                evidence_snippet=str(data.get("evidence_snippet", "")),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        meta = save_manual_claims_doc(eval_data_dir, model, question_id, batch, doc)
        history = record_annotation_undo_state(eval_data_dir, model, question_id, batch, baseline_snapshot)
        return jsonify({
            "ok": True,
            "paragraph_index": paragraph_index,
            "claim_index": new_claim_index,
            "manual_override": True,
            "updated_at": meta.get("updated_at", ""),
            "undo_depth": len(history["undo_stack"]),
            "redo_depth": len(history["redo_stack"]),
        })

    @eval_bp.route(
        "/api/annotations/<model>/<question_id>/<int:batch>/claims/<int:paragraph_index>/<int:claim_index>",
        methods=["DELETE"],
    )
    def delete_annotation(model: str, question_id: str, batch: int, paragraph_index: int, claim_index: int):
        doc, _, _ = load_claim_doc_for_annotation(eval_data_dir, model, question_id, batch)
        if doc is None:
            return jsonify({"error": "No claim annotations available for this run"}), 404

        baseline_snapshot = claim_doc_to_dict(doc)
        try:
            delete_annotation_claim(doc, paragraph_index, claim_index)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        meta = save_manual_claims_doc(eval_data_dir, model, question_id, batch, doc)
        history = record_annotation_undo_state(eval_data_dir, model, question_id, batch, baseline_snapshot)
        return jsonify({
            "ok": True,
            "manual_override": True,
            "updated_at": meta.get("updated_at", ""),
            "undo_depth": len(history["undo_stack"]),
            "redo_depth": len(history["redo_stack"]),
        })

    @eval_bp.route("/api/annotations/<model>/<question_id>/<int:batch>/undo", methods=["POST"])
    def undo_annotation(model: str, question_id: str, batch: int):
        try:
            meta, history = apply_annotation_undo(eval_data_dir, model, question_id, batch)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({
            "ok": True,
            "manual_override": True,
            "updated_at": meta.get("updated_at", ""),
            "undo_depth": len(history["undo_stack"]),
            "redo_depth": len(history["redo_stack"]),
        })

    @eval_bp.route("/api/annotations/<model>/<question_id>/<int:batch>/redo", methods=["POST"])
    def redo_annotation(model: str, question_id: str, batch: int):
        try:
            meta, history = apply_annotation_redo(eval_data_dir, model, question_id, batch)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({
            "ok": True,
            "manual_override": True,
            "updated_at": meta.get("updated_at", ""),
            "undo_depth": len(history["undo_stack"]),
            "redo_depth": len(history["redo_stack"]),
        })

    @eval_bp.route("/api/annotations/<model>/<question_id>/<int:batch>/restore", methods=["POST"])
    @eval_bp.route("/api/annotations/<model>/<question_id>/<int:batch>/manual", methods=["DELETE"])
    def reset_manual_annotations(model: str, question_id: str, batch: int):
        try:
            clear_manual_annotation_state(eval_data_dir, model, question_id, batch)
        except OSError as exc:
            return jsonify({"error": f"Failed to remove manual override: {exc}"}), 500
        return jsonify({
            "ok": True,
            "manual_override": False,
            "restored_pristine": True,
            "undo_depth": 0,
            "redo_depth": 0,
        })


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_to_dict(snapshot: ClaimAnnotatedDocument | dict) -> dict:
    if isinstance(snapshot, ClaimAnnotatedDocument):
        return claim_doc_to_dict(snapshot)
    if isinstance(snapshot, dict):
        return snapshot
    raise TypeError("Annotation history snapshot must be a claim document or serialized dict")


def _annotation_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_claim_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in CLAIM_TYPES:
        raise ValueError(f"claim_type must be one of {', '.join(CLAIM_TYPES)}")
    return normalized


def _normalize_support_class(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in SUPPORT_CLASSES:
        raise ValueError(f"support_class must be one of {', '.join(SUPPORT_CLASSES)}")
    return normalized


def _normalize_annotation_span(
    paragraph_text: str,
    start: int,
    end: int,
    text: str,
) -> tuple[int, int, str]:
    try:
        start_i = int(start)
        end_i = int(end)
    except (TypeError, ValueError) as exc:
        raise ValueError("start and end must be integers") from exc

    if not (0 <= start_i < end_i <= len(paragraph_text)):
        raise ValueError("Selected claim span is out of bounds for the paragraph")

    anchored_text = paragraph_text[start_i:end_i]
    if anchored_text != str(text or ""):
        raise ValueError("Selected claim text does not match the paragraph source")
    return start_i, end_i, anchored_text


def _normalize_canonical_ids(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = re.split(r"[\n,]+", values)
    elif isinstance(values, list):
        raw_values = values
    else:
        raise ValueError("canonical_ids must be a JSON array or a comma-separated string")

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        token = str(raw_value or "").strip()
        if not token or token in seen:
            continue
        normalized.append(token)
        seen.add(token)
    return normalized


def _get_claim_paragraph(doc: ClaimAnnotatedDocument, paragraph_index: int) -> ClaimParagraph:
    for paragraph in doc.paragraphs:
        if paragraph.paragraph_index == paragraph_index:
            return paragraph
    raise ValueError(f"paragraph_index {paragraph_index} was not found")


def _find_claim_conflicts(
    paragraph: ClaimParagraph,
    start: int,
    end: int,
    *,
    ignore_index: int | None = None,
) -> list[int]:
    conflicts: list[int] = []
    for idx, claim in enumerate(paragraph.claims):
        if ignore_index is not None and idx == ignore_index:
            continue
        if not (end <= claim.start or start >= claim.end):
            conflicts.append(idx)
    return conflicts


def _claim_metadata(existing: dict | None = None) -> dict:
    metadata = dict(existing or {})
    metadata["edited_in_browser"] = True
    metadata["edited_at"] = _annotation_timestamp()
    return metadata


def _reindex_claim_paragraph(paragraph: ClaimParagraph) -> None:
    indexed_claims = list(enumerate(paragraph.claims))
    indexed_claims.sort(key=lambda item: (item[1].start, item[1].end))
    old_to_new = {old_idx: new_idx for new_idx, (old_idx, _) in enumerate(indexed_claims)}

    paragraph.claims = [claim for _, claim in indexed_claims]

    grounded_by_old = {grounded.claim_index: grounded for grounded in paragraph.grounded_claims}
    reindexed_grounded: list[GroundedClaim] = []
    for old_idx, _claim in indexed_claims:
        grounded = grounded_by_old.get(old_idx) or GroundedClaim(claim_index=0)
        grounded.claim_index = old_to_new[old_idx]
        reindexed_grounded.append(grounded)

    paragraph.grounded_claims = reindexed_grounded