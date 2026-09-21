from __future__ import annotations

import json
import re
from pathlib import Path

from flask import jsonify, request


def scoring_path(eval_data_dir, model: str, question_id: str, batch: int) -> Path:
    return eval_data_dir(model, question_id) / f"scoring_batch{batch}.json"


def markers_path(eval_data_dir, model: str, question_id: str, batch: int) -> Path:
    return eval_data_dir(model, question_id) / f"markers_batch{batch}.json"


def load_json(path: Path) -> list | dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return [] if "markers" in path.name else {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_scoring(eval_data_dir, model: str, question_id: str, batch: int) -> dict:
    return load_json(scoring_path(eval_data_dir, model, question_id, batch))


def load_markers(eval_data_dir, model: str, question_id: str, batch: int) -> list:
    return load_json(markers_path(eval_data_dir, model, question_id, batch))


def register_routes(eval_bp, eval_data_dir) -> None:
    @eval_bp.route("/api/scoring/<model>/<question_id>/<int:batch>", methods=["GET"])
    def get_scoring(model: str, question_id: str, batch: int):
        return jsonify(load_scoring(eval_data_dir, model, question_id, batch))

    @eval_bp.route("/api/scoring/<model>/<question_id>/<int:batch>", methods=["POST"])
    def save_scoring(model: str, question_id: str, batch: int):
        data = request.get_json(force=True)
        note = str(data.get("note", ""))[:500]
        score = data.get("score")
        if score is not None:
            score = int(score)
        save_json(
            scoring_path(eval_data_dir, model, question_id, batch),
            {"note": note, "score": score},
        )
        return jsonify({"ok": True})

    @eval_bp.route("/api/markers/<model>/<question_id>/<int:batch>", methods=["GET"])
    def get_markers(model: str, question_id: str, batch: int):
        return jsonify(load_markers(eval_data_dir, model, question_id, batch))

    @eval_bp.route("/api/markers/<model>/<question_id>/<int:batch>", methods=["POST"])
    def add_marker(model: str, question_id: str, batch: int):
        data = request.get_json(force=True)
        text = re.sub(r"\s+", " ", str(data.get("text", ""))).strip()[:100]
        color = str(data.get("color", "info"))[:20]
        if not text:
            return jsonify({"error": "Empty text"}), 400

        markers = load_markers(eval_data_dir, model, question_id, batch)
        new_id = max((marker.get("id", 0) for marker in markers), default=0) + 1
        markers.append({"id": new_id, "text": text, "color": color, "source": "manual"})
        save_json(markers_path(eval_data_dir, model, question_id, batch), markers)
        return jsonify({
            "ok": True,
            "id": new_id,
            "text": text,
            "color": color,
            "source": "manual",
        })

    @eval_bp.route(
        "/api/markers/<model>/<question_id>/<int:batch>/<int:marker_id>",
        methods=["DELETE"],
    )
    def delete_marker(model: str, question_id: str, batch: int, marker_id: int):
        markers = load_markers(eval_data_dir, model, question_id, batch)
        target = next((marker for marker in markers if marker.get("id") == marker_id), None)
        if not target:
            return jsonify({"error": "Not found"}), 404
        if target.get("source") == "agent":
            return jsonify({"error": "Cannot delete agent-generated marker"}), 403
        filtered = [marker for marker in markers if marker.get("id") != marker_id]
        save_json(markers_path(eval_data_dir, model, question_id, batch), filtered)
        return jsonify({"ok": True})