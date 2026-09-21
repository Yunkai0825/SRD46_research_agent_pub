from __future__ import annotations

import json
from pathlib import Path

import pytest

from NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers import (
    AgentTurnResult,
    ArgoPromptTooLargeError,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_orchestration.L1_subagent import (
    l1_subagent as l1,
)


def _state(tmp_path: Path) -> l1._L1State:
    call_dir = tmp_path / "L1_call_01"
    (call_dir / "solver").mkdir(parents=True)
    l1._SESSION["session_dir"] = tmp_path
    l1._SESSION["history"] = None
    return l1._L1State(
        purpose="test system",
        tasks_text="run the requested sweep",
        call_dir=call_dir,
        idx=1,
    )


def test_pipeline_result_supplies_complete_verdict_and_never_raw_topology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    verdict = state.call_dir / "solver" / "system_verdict.md"
    topology = state.call_dir / "solver" / "topology_system.json"
    full_text = "# Solver verdict\n\n" + ("evidence-line\n" * 7000) + "TAIL_SENTINEL"
    verdict.write_text(full_text, encoding="utf-8")
    topology.write_text(
        json.dumps({"raw_topology_secret": "RAW_JSON_SENTINEL"}),
        encoding="utf-8",
    )
    calls = 0

    def fake_pipeline(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {
            "status": "ok",
            "solver": {
                "sweep_method": "pH_sweep",
                "output_paths": [str(topology), str(verdict)],
            },
        }

    monkeypatch.setattr(l1, "run_pipeline", fake_pipeline)
    tool = l1._make_run_pipeline(state)

    first = tool()
    assert full_text in first
    assert "TAIL_SENTINEL" in first
    assert "full_untruncated" in first
    assert "RAW_JSON_SENTINEL" not in first

    cached = tool()
    assert full_text in cached
    assert '"already_ran": true' in cached
    assert calls == 1


def test_raw_topology_is_gated_but_section_and_id_record_are_available(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    solver = state.call_dir / "solver"
    topology = solver / "topology_demo.json"
    suffix_topology = solver / "demo_topology.json"
    verdict_md = solver / "topology_demo_verdict.md"
    verdict_json = solver / "topology_demo_verdict.json"
    topology.write_text(
        json.dumps({"secret_full_document": "RAW_JSON_SENTINEL"}),
        encoding="utf-8",
    )
    suffix_topology.write_text(
        json.dumps({"secret_full_document": "RAW_JSON_SENTINEL"}),
        encoding="utf-8",
    )
    verdict_md.write_text(
        "# Solver report (predominance)\n\n"
        "## System\n\nSystem facts.\n\n"
        "## Topology details\n\n### regions\n\n- DmsReg_1\n",
        encoding="utf-8",
    )
    verdict_json.write_text(
        json.dumps({
            "topology_details": {
                "regions": [{"id": "DmsReg_1", "label": "Cu2O"}],
                "edges_equilibria": [],
                "junctions_catalog": [],
            }
        }),
        encoding="utf-8",
    )
    state.solver_dir = solver
    state.default_verdicts = [(verdict_md, verdict_md.read_text(encoding="utf-8"))]

    raw = l1._make_read_output_file(state)(
        "L1_call_01/solver/topology_demo.json",
        max_chars=60000,
    )
    assert "raw topology JSON is not returned" in raw
    assert "RAW_JSON_SENTINEL" not in raw

    suffix_raw = l1._make_read_output_file(state)(
        "L1_call_01/solver/demo_topology.json",
        max_chars=60000,
    )
    assert "raw topology JSON is not returned" in suffix_raw
    assert "RAW_JSON_SENTINEL" not in suffix_raw

    section = l1._make_inspect_verdict_section(state)(
        "L1_call_01/solver/topology_demo_verdict.md",
        "System",
    )
    assert "System facts." in section
    assert "Topology details" not in section

    feature = l1._make_inspect_topology_feature(state)(
        "DmsReg_1",
        "L1_call_01/solver/topology_demo.json",
    )
    assert '"label": "Cu2O"' in feature
    assert "RAW_JSON_SENTINEL" not in feature


def test_unresolved_feature_id_returns_canonical_hints(tmp_path: Path) -> None:
    state = _state(tmp_path)
    solver = state.call_dir / "solver"
    (solver / "topology_demo_verdict.json").write_text(
        json.dumps({
            "topology_details": {
                "regions": [{"id": "DmsReg_1"}, {"id": "DmsReg_2"}],
            },
            "source_mapping": {
                "dominant_species": {"Dms_1": {"source_label_id": 3}},
                "regions": {
                    "DmsReg_1": {"source_id": 0},
                    "DmsReg_2": {"source_id": 1},
                },
                "boundary_manifolds": {
                    "DmsRegEq_1": {"intrinsic_dimension": 1, "source_id": 7},
                },
                "junction_features": {},
            },
        }),
        encoding="utf-8",
    )
    state.solver_dir = solver
    tool = l1._make_inspect_topology_feature(state)

    unknown = tool("DmsReg_99")
    assert "resolved to 0 records" in unknown
    for family in ("Dms_i", "DmsReg_i", "DmsRegEq_i", "DmsRegEqJnc_i"):
        assert family in unknown
    assert "DmsReg_1..DmsReg_2" in unknown  # available-ID roster

    source_id = tool("7")
    assert "resolved to 0 records" in source_id
    assert "'DmsRegEq_1'" in source_id  # source-id → canonical translation
    assert "retry with that canonical ID" in source_id

    empty = tool("")
    assert "feature_id is required" in empty
    assert "Dms_i" in empty


def test_prompt_size_error_retries_once_with_cached_truncated_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    verdict = state.call_dir / "solver" / "topology_demo_verdict.md"
    full_text = (
        "# Solver report\n"
        + "HEAD_SENTINEL\n"
        + ("middle-evidence\n" * 4000)
        + "TAIL_SENTINEL\n"
    )
    verdict.write_text(full_text, encoding="utf-8")
    solver_calls = 0
    turn_calls = 0

    def fake_pipeline(*_args, **_kwargs):
        nonlocal solver_calls
        solver_calls += 1
        return {
            "status": "ok",
            "solver": {
                "sweep_method": "pourbaix_sweep",
                "output_paths": [str(verdict)],
            },
        }

    def fake_agent_turn(*_args, tools, **_kwargs):
        nonlocal turn_calls
        turn_calls += 1
        delivered = tools["run_analysis_pipeline"]()
        if turn_calls == 1:
            assert full_text in delivered
            raise ArgoPromptTooLargeError(
                status_code=413,
                response_text="request entity too large",
                model="test-model",
                api_url="https://example.invalid",
            )
        assert "truncated_after_argo_prompt_rejection" in delivered
        assert "omitted only because Argo rejected" in delivered
        assert "HEAD_SENTINEL" in delivered
        assert "TAIL_SENTINEL" in delivered
        tools["record_analysis"](
            analysis_markdown="## Result\nRecovered with section tools.",
            artifact_paths="solver/topology_demo_verdict.md",
        )
        return AgentTurnResult(
            answer="done",
            iterations=1,
            elapsed_seconds=0.1,
        )

    monkeypatch.setattr(l1, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(l1, "agent_turn", fake_agent_turn)
    monkeypatch.setattr(
        l1.SRD46AnalysisClient,
        "for_l1",
        classmethod(lambda cls: object()),
    )

    result = l1._run_l1_agent(state)
    assert result is not None
    assert result.answer == "done"
    assert solver_calls == 1
    assert turn_calls == 2
    assert state.verdict_api_retry_used is True
    assert state.verdict_delivery_mode == "api_error_fallback"
    assert verdict.read_text(encoding="utf-8") == full_text


def test_non_size_argo_error_does_not_truncate_or_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    calls = 0

    def fail_turn(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("authentication or network failure")

    monkeypatch.setattr(l1, "agent_turn", fail_turn)
    monkeypatch.setattr(
        l1.SRD46AnalysisClient,
        "for_l1",
        classmethod(lambda cls: object()),
    )
    assert l1._run_l1_agent(state) is None
    assert calls == 1
    assert state.verdict_delivery_mode == "full"
    assert state.verdict_api_retry_used is False


def test_reference_constants_projection_is_persisted_and_injected(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    card = state.call_dir / "LC2" / "free_energy_card.md"
    card.parent.mkdir(parents=True)
    card.write_text(
        "# Final card\n\n"
        "| species_id | label | phase | log_beta | stoich | source | include |\n"
        "|---|---|---|---:|---|---|---|\n"
        "| [[H][L1]].[z+1] | [HAmmonia]+ | aqueous | +9.2600 | [H]:+1, [L1]:+1 | SRD-46 | true |\n"
        "| [M1].[L1] | masked | aqueous | +4.1000 | [M1]:+1, [L1]:+1 | SRD-46 | false |\n",
        encoding="utf-8",
    )

    state.default_reference_constants = l1._build_reference_constants_artifact(
        state,
        card,
    )
    assert state.default_reference_constants is not None
    path, text = state.default_reference_constants
    assert path.name == "thermodynamic_reference_constants.md"
    assert "+9.2600" in text
    assert "[HAmmonia]+" in text
    assert "x H+ + L <=> HxL" in text
    assert "[H]:+1, [L1]:+1" in text
    assert "SRD-46" in text
    assert "masked" not in text

    rendered = l1._render_pipeline_result(state, {"status": "ok"})
    assert "DEFAULT THERMODYNAMIC REFERENCE CONSTANTS" in rendered
    assert "+9.2600" in rendered
    assert "default_reference_constants_path" in rendered


def test_validation_handoff_preserves_recommendations_for_l0() -> None:
    report = "## Result\nNumerical result."
    revised = l1._append_validation_handoff(
        report,
        {
            "verdict": "inconclusive",
            "timed_out": False,
            "hints": [
                "Downstream synthesis recommendation: qualify the external "
                "oxygen-etching claim or verify it from an external source."
            ],
        },
    )

    assert "## LD validation handoff" in revised
    assert "oxygen-etching" in revised
    assert "not silently converted into solver evidence" in revised


@pytest.mark.parametrize("agent_timed_out", [False, True])
def test_uncommitted_l1_answer_fails_closed_and_skips_ld(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent_timed_out: bool,
) -> None:
    l1.configure_l1_session(
        session_dir=tmp_path,
        estimate_missing_equilibria=False,
    )
    ld_calls = 0

    def fake_run(state, **_kwargs):
        state.ran_ok = True
        return AgentTurnResult(
            answer="TRUNCATED_SCIENTIFIC_TEXT_THAT_MUST_NOT_PROPAGATE",
            iterations=4,
            elapsed_seconds=0.1,
            timed_out=agent_timed_out,
        )

    def fake_ld(*_args, **_kwargs):
        nonlocal ld_calls
        ld_calls += 1
        return {
            "verdict": "supported",
            "timed_out": False,
            "committed": True,
        }

    monkeypatch.setattr(l1, "_run_l1_agent", fake_run)
    monkeypatch.setattr(l1, "_validate_with_ld", fake_ld)

    report = l1.dispatch_l1_pipeline("test system", "run the sweep")

    assert ld_calls == 0
    assert "TRUNCATED_SCIENTIFIC_TEXT" not in report
    assert "did not commit a report" in report
    status = json.loads(
        (tmp_path / "L1_call_01" / "l1_report_status.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["status"] == "incomplete"
    assert status["l1_report_committed"] is False
    assert status["reason"] == "missing_l1_terminal_commit"
    assert status["agent_turn_timed_out"] is agent_timed_out
    assert not (tmp_path / "L1_call_01" / "l1_analysis.json").exists()


def test_failed_ld_revision_cannot_reuse_prior_committed_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    l1.configure_l1_session(
        session_dir=tmp_path,
        estimate_missing_equilibria=False,
    )
    turns = 0

    def fake_run(state, **_kwargs):
        nonlocal turns
        turns += 1
        state.ran_ok = True
        if turns == 1:
            receipt = l1._make_record_analysis(state)(
                analysis_markdown="## Result\nPrior report rejected by LD.",
            )
            assert receipt.startswith("OK")
            return AgentTurnResult(
                answer="committed",
                iterations=1,
                elapsed_seconds=0.1,
                timed_out=False,
            )
        return AgentTurnResult(
            answer="TRUNCATED_REVISED_REPORT",
            iterations=10,
            elapsed_seconds=0.1,
            timed_out=True,
        )

    monkeypatch.setattr(l1, "_run_l1_agent", fake_run)
    monkeypatch.setattr(
        l1,
        "_validate_with_ld",
        lambda *_args, **_kwargs: {
            "verdict": "contradicted",
            "hints": ["replace the report"],
            "timed_out": False,
            "committed": True,
        },
    )

    report = l1.dispatch_l1_pipeline("test system", "run the sweep")

    assert turns == 2
    assert "Prior report rejected" not in report
    assert "TRUNCATED_REVISED_REPORT" not in report
    assert "did not commit a report" in report
    status = json.loads(
        (tmp_path / "L1_call_01" / "l1_report_status.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["l1_report_committed"] is False
    assert status["agent_turn_timed_out"] is True


def test_completed_report_checkpoint_rejects_changed_report(tmp_path: Path) -> None:
    call_dir = tmp_path / "L1_call_01"
    call_dir.mkdir(parents=True)
    report_path = call_dir / "l1_report.md"
    report_path.write_text("## Result\ncommitted evidence\n", encoding="utf-8")
    (call_dir / "pipeline_status.json").write_text(
        json.dumps({"status": "ok"}), encoding="utf-8"
    )
    (call_dir / "l1_report_status.json").write_text(
        json.dumps({
            "schema_version": "l1_report_status.v2",
            "l1_report_committed": True,
            "report_sha256": l1.file_sha256(report_path),
        }),
        encoding="utf-8",
    )

    assert l1._load_completed_l1_report(call_dir) == (
        "## Result\ncommitted evidence"
    )

    report_path.write_text("truncated", encoding="utf-8")
    assert l1._load_completed_l1_report(call_dir) is None
