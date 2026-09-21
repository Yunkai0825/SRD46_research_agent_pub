from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building import (
    LC3_solver_para_card_orchestrator as orch,
)


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    fixed = tmp_path / "fixed_card.md"
    fixed.write_text("# fixed card\n", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"system_catalog": {}}), encoding="utf-8")
    return fixed, catalog


def _install_mock_pipeline(monkeypatch: pytest.MonkeyPatch, *, l3_4_run: Any) -> Dict[str, Any]:
    calls: Dict[str, Any] = {"l3_1": 0, "contexts": []}

    def _configure(**_: Any) -> None:
        return None

    def _write_card(output_dir: Any, stage: str, payload: Dict[str, Any]) -> Path:
        path = Path(output_dir) / f"{stage}_card.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _l3_1(**kwargs: Any) -> Dict[str, Any]:
        calls["l3_1"] += 1
        calls["contexts"].append(("LC3_1", kwargs.get("restart_context", "")))
        path = _write_card(kwargs["output_dir"], "l3_1", {
            "sweep_method": "pH_sweep",
            "_meta": {"dof": 1, "attempt": calls["l3_1"]},
        })
        return {
            "status": "ok", "sweep_method": "pH_sweep", "dof": 1,
            "calc_input_card_path": str(path),
        }

    def _l3_2(**kwargs: Any) -> Dict[str, Any]:
        calls["contexts"].append(("LC3_2", kwargs.get("restart_context", "")))
        path = _write_card(kwargs["output_dir"], "l3_2", {
            "sweep_method": "pH_sweep", "_meta": {"dof": 1},
            "constraint_settings": {},
        })
        return {
            "status": "ok", "calc_input_card_path": str(path),
            "initial_conditions_text": "inits", "inits": [],
            "constraint_settings": {},
        }

    def _l3_3(**kwargs: Any) -> Dict[str, Any]:
        calls["contexts"].append(("LC3_3", kwargs.get("restart_context", "")))
        path = _write_card(kwargs["output_dir"], "l3_3", {
            "sweep_method": "pH_sweep", "_meta": {"dof": 1},
            "constraint_settings": {},
            "constraint_spec": {"axes": ["pH_axis"]},
        })
        return {
            "status": "ok", "calc_input_card_path": str(path),
            "sweep_constraints": {"axes": ["pH_axis"]},
        }

    monkeypatch.setattr(orch, "configure_l3_1_session", _configure)
    monkeypatch.setattr(orch, "configure_l3_2_session", _configure)
    monkeypatch.setattr(orch, "configure_l3_3_session", _configure)
    monkeypatch.setattr(orch, "run_l3_1", _l3_1)
    monkeypatch.setattr(orch, "run_l3_2", _l3_2)
    monkeypatch.setattr(orch, "run_l3_3", _l3_3)
    monkeypatch.setattr(
        orch, "_load_optional_stage",
        lambda stage: {"run": l3_4_run, "configure": _configure},
    )
    return calls


def test_fatal_upstream_restarts_entire_lc3_and_promotes_only_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed, catalog = _inputs(tmp_path)
    root = tmp_path / "LC3"
    l3_4_calls = 0
    contexts: list[str] = []

    def _l3_4(**kwargs: Any) -> Dict[str, Any]:
        nonlocal l3_4_calls
        l3_4_calls += 1
        contexts.append(kwargs.get("restart_context", ""))
        if l3_4_calls == 1:
            candidate = Path(kwargs["output_dir"]) / "rejected_candidate.json"
            candidate.write_text(
                json.dumps({"validated": False, "bad": "constraint"}),
                encoding="utf-8",
            )
            return {
                "status": "failed",
                "_error": "upstream_calc_input_invalid:rank deficient",
                "failure_scope": "upstream",
                "latest_attempt_artifact_path": str(candidate),
            }
        final = Path(kwargs["output_dir"]) / "validated_final.json"
        final.write_text(json.dumps({"validated": True, "attempt": 2}), encoding="utf-8")
        return {
            "status": "ok", "calc_input_path": str(final),
            "sweep_axes": [{"name": "pH", "min": 0, "max": 14, "n_points": 15}],
            "grid_refine": {"mode": "none"}, "n_cells": 15,
        }

    calls = _install_mock_pipeline(monkeypatch, l3_4_run=_l3_4)
    result = orch.run_lc3(
        "speciation", "test",
        fixed_card_path=fixed, system_catalog_path=catalog,
        output_dir=root, max_restarts=2,
    )

    assert result["status"] == "ok"
    assert result["restart_count"] == 1
    assert len(result["attempts"]) == 2
    assert calls["l3_1"] == 2
    assert contexts[0] == ""
    assert "rank deficient" in contexts[1]
    assert '"bad": "constraint"' in contexts[1]
    assert '"constraint_spec"' in contexts[1]
    for stage, context in calls["contexts"][3:]:
        assert stage in {"LC3_1", "LC3_2", "LC3_3"}
        assert "rank deficient" in context
    assert Path(result["final_card_path"]) == root / "calc_input_card.json"
    assert json.loads(Path(result["final_card_path"]).read_text(encoding="utf-8"))["attempt"] == 2
    assert (root / "LC3_1").is_dir()
    assert (root / "restarts" / "LC3_restart_01" / "LC3_1").is_dir()
    manifest = json.loads(
        Path(result["restart_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["terminal_status"] == "ok"
    assert manifest["terminal_attempt"] == 2
    assert len(manifest["attempts"]) == 2


def test_restart_context_structures_failed_pass_gallery_notes_as_advisory() -> None:
    initial_note = {
        "stage": "initial_conditions",
        "best_example": None,
        "best_example_rationale": "",
        "inspected_examples": [{"example_id": "conserved-moles-dilution-path"}],
    }
    constraint_note = {
        "stage": "constraints",
        "best_example": "conserved-moles-dilution-path",
        "best_example_rationale": "closest failed-pass structure",
        "inspected_examples": [{"example_id": "conserved-moles-dilution-path"}],
    }
    attempt = {
        "status": "restart_requested",
        "sweep_method": "freeform_sweep",
        "dof": 1,
        "lc3_2": {
            "status": "ok",
            "freeform_gallery_note": initial_note,
        },
        "lc3_3": {
            "status": "failed",
            "_error": "constraint premise failed",
            "freeform_gallery_note": constraint_note,
            "restart_request": {
                "requested": True,
                "requested_by": "LC3_3",
                "error": "constraint premise failed",
            },
        },
    }

    request = orch._restart_request_from_attempt(attempt)
    assert request is not None
    records = request["failed_pass_gallery_notes"]
    assert [record["source_stage"] for record in records] == ["LC3_2", "LC3_3"]
    assert all(record["trust"] == "advisory_failed_pass" for record in records)
    assert records[0]["note"] == initial_note
    assert records[1]["note"] == constraint_note

    rendered = orch._render_restart_context(request, attempt)
    assert "FAILED-PASS FREEFORM GALLERY NOTES -- ADVISORY ONLY" in rendered
    assert "not automatically adopted" in rendered
    assert '"best_example": null' in rendered
    assert '"best_example": "conserved-moles-dilution-path"' in rendered


def test_restart_cap_allows_only_three_total_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed, catalog = _inputs(tmp_path)
    call_number = 0

    def _l3_4(**kwargs: Any) -> Dict[str, Any]:
        nonlocal call_number
        call_number += 1
        candidate = Path(kwargs["output_dir"]) / f"candidate_{call_number}.json"
        candidate.write_text(json.dumps({"attempt": call_number}), encoding="utf-8")
        return {
            "status": "failed", "_error": f"upstream_error_{call_number}",
            "failure_scope": "upstream",
            "latest_attempt_artifact_path": str(candidate),
        }

    calls = _install_mock_pipeline(monkeypatch, l3_4_run=_l3_4)
    result = orch.run_lc3(
        "speciation", "test",
        fixed_card_path=fixed, system_catalog_path=catalog,
        output_dir=tmp_path / "LC3", max_restarts=2,
    )

    assert result["status"] == "failed"
    assert result["restart_count"] == 2
    assert result["restart_exhausted"] is True
    assert result["restart_blocked_reason"] == "restart_limit_reached"
    assert len(result["attempts"]) == 3
    assert calls["l3_1"] == 3
    assert not (tmp_path / "LC3" / "restarts" / "LC3_restart_03").exists()


def test_nonrequested_stage_failure_does_not_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed, catalog = _inputs(tmp_path)

    def _l3_4(**_: Any) -> Dict[str, Any]:
        return {
            "status": "failed", "_error": "grid_invalid:bad range",
            "failure_scope": "grid",
        }

    calls = _install_mock_pipeline(monkeypatch, l3_4_run=_l3_4)
    result = orch.run_lc3(
        "speciation", "test",
        fixed_card_path=fixed, system_catalog_path=catalog,
        output_dir=tmp_path / "LC3", max_restarts=2,
    )
    assert result["status"] == "failed"
    assert result["restart_count"] == 0
    assert len(result["attempts"]) == 1
    assert calls["l3_1"] == 1


def test_agent_requested_l3_2_restart_stops_pass_and_restarts_at_l3_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed, catalog = _inputs(tmp_path)
    l3_4_calls = 0

    def _l3_4(**kwargs: Any) -> Dict[str, Any]:
        nonlocal l3_4_calls
        l3_4_calls += 1
        final = Path(kwargs["output_dir"]) / "final.json"
        final.write_text(json.dumps({"validated": True}), encoding="utf-8")
        return {"status": "ok", "calc_input_path": str(final)}

    calls = _install_mock_pipeline(monkeypatch, l3_4_run=_l3_4)
    successful_l3_2 = orch.run_l3_2
    l3_2_calls = 0

    def _l3_2(**kwargs: Any) -> Dict[str, Any]:
        nonlocal l3_2_calls
        l3_2_calls += 1
        if l3_2_calls == 1:
            candidate = Path(kwargs["output_dir"]) / "candidate.json"
            candidate.write_text(json.dumps({"inits": "bad"}), encoding="utf-8")
            return {
                "status": "failed", "_error": "undeclared_inputs:temperature",
                "latest_attempt_artifact_path": str(candidate),
                "restart_request": {
                    "requested": True, "requested_by": "LC3_2",
                    "error": "undeclared_inputs:temperature",
                    "latest_attempt_artifact_path": str(candidate),
                    "reason": "the method/role assumptions need redesign",
                },
            }
        return successful_l3_2(**kwargs)

    monkeypatch.setattr(orch, "run_l3_2", _l3_2)
    result = orch.run_lc3(
        "speciation", "test",
        fixed_card_path=fixed, system_catalog_path=catalog,
        output_dir=tmp_path / "LC3", max_restarts=2,
    )
    assert result["status"] == "ok"
    assert result["restart_count"] == 1
    assert calls["l3_1"] == 2
    assert l3_4_calls == 1
    assert result["attempts"][0]["failed_stage"] == "LC3_2"
    assert result["attempts"][0]["status"] == "restart_requested"


def test_duplicate_restart_fingerprint_stops_before_numeric_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed, catalog = _inputs(tmp_path)

    def _l3_4(**kwargs: Any) -> Dict[str, Any]:
        candidate = Path(kwargs["output_dir"]) / "candidate.json"
        candidate.write_text(json.dumps({"same": "candidate"}), encoding="utf-8")
        return {
            "status": "failed", "_error": "same_upstream_error",
            "failure_scope": "upstream",
            "latest_attempt_artifact_path": str(candidate),
        }

    calls = _install_mock_pipeline(monkeypatch, l3_4_run=_l3_4)
    result = orch.run_lc3(
        "speciation", "test",
        fixed_card_path=fixed, system_catalog_path=catalog,
        output_dir=tmp_path / "LC3", max_restarts=2,
    )
    assert result["status"] == "failed"
    assert result["restart_count"] == 1
    assert result["restart_exhausted"] is False
    assert result["restart_blocked_reason"] == "duplicate_restart_request"
    assert len(result["attempts"]) == 2
    assert calls["l3_1"] == 2


@pytest.mark.parametrize("bad_limit", [-1, 1.5, True, "2"])
def test_restart_limit_must_be_a_nonnegative_integer(
    tmp_path: Path, bad_limit: Any,
) -> None:
    fixed, catalog = _inputs(tmp_path)
    with pytest.raises(ValueError, match="non-negative integer"):
        orch.run_lc3(
            "speciation", "test",
            fixed_card_path=fixed, system_catalog_path=catalog,
            output_dir=tmp_path / "LC3", max_restarts=bad_limit,
        )
