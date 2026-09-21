"""Trust-boundary tests for parser-authorized QueryAgent clarification."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.candidate_schema import (
    GateIssue,
    GateOwner,
    GateReport,
    ParserAction,
    ParserCycleResult,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parse_speciation_answer_orchestrator import (
    _revise_feedback,
    run_parse_speciation_answer,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer import (
    parser_agent,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_gate_service import (
    ParserGateService,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_tools import (
    ParserToolbox,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_working_state import (
    ParserWorkingState,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.dispatch_srd46_query.query_clarification_coordinator import (
    QueryClarificationFailure,
    run_query_clarification,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (
    LC13Settings,
    QuerySession,
    QueryTurn,
    normalize_query_turn,
)


def _scope() -> dict[str, object]:
    return {
        "metal_id": 27,
        "metal_name": "Ce^[3+]",
        "ligand_id": 6204,
        "ligand_name": "N-(2-Hydroxyethyl)iminodiacetic acid (HIDA)",
        "base_reference_network_count": 0,
        "base_reference_networks": [],
    }


def _settings(**updates: object) -> LC13Settings:
    values = {
        "max_query_runs": 1,
        "query_model": "dummy-query",
        "query_max_iterations": 4,
        "query_timeout_s": 30.0,
        "parser_max_rounds": 8,
        "parser_timeout_s": 30.0,
        "parser_model": "dummy-parser",
        "failure_policy": "reference_only",
        "parser_validation_retries": 0,
        "query_clarification_retries": 1,
        "query_clarification_total_timeout_s": 5.0,
    }
    values.update(updates)
    return LC13Settings(**values)


def _service(tmp_path: Path) -> ParserGateService:
    state = ParserWorkingState.create(
        query_id="q001",
        scope=_scope(),
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer=(
            "For beta_def_872 I estimate log10 K = 20.4 by analogue transfer. "
            "Evidence is vlm_93785. I assume the same reference state because "
            "HIDA chelates the metal."
        ),
        evidence_snapshot={},
    )
    state.create_draft({
        "beta_definition_id": 872,
        "constant_value": 20.4,
        "evidence_vlm_ids": [93785],
        "estimation_method": "analogue transfer",
        "assumptions": ["the same reference state"],
        "rationale": "HIDA chelates the metal",
    })
    return ParserGateService(
        state=state,
        base_eq_map_card={"equilibrium_networks": []},
        session_id="test-session",
        artifact_dir=tmp_path,
    )


def test_real_parser_runner_installs_required_engine_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool-result builders must be present in the shared ReAct engine."""

    service = _service(tmp_path)
    captured: dict[str, object] = {}

    def fake_agent_turn(*_args, **kwargs):
        captured["hooks"] = kwargs.get("hooks")
        captured["uncompacted_tools"] = kwargs.get("uncompacted_tools")
        return SimpleNamespace(tool_history=[], answer="", final_context="")

    monkeypatch.setattr(parser_agent, "agent_turn", fake_agent_turn)
    monkeypatch.setattr(
        parser_agent,
        "SRD46AnalysisClient",
        lambda **_kwargs: object(),
    )

    parser_agent.run_parser_agent(
        service=service,
        settings=_settings(),
        artifact_dir=tmp_path,
    )

    hooks = captured["hooks"]
    assert isinstance(hooks, dict)
    assert hooks
    assert captured["uncompacted_tools"] == set(ParserToolbox(service).tools())


def test_parser_context_exposes_only_prose_cited_authorized_ids(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.state.evidence_snapshot = {
        "observed_beta_definition_ids": [812, 840, 872, 894],
        "observed_vlm_ids": [93785, 100001, 100002],
        "observed_network_ids": [77, 78],
        "observed_literature_ids": [88, 89],
    }

    context = service.parser_context()

    assert context["prose_cited_authorized_ids"] == {
        "beta_definition_ids": [872],
        "vlm_ids": [93785],
        "network_ids": [],
        "literature_ids": [],
    }
    assert context["authorization_totals"] == {
        "beta_definition_ids": 4,
        "vlm_ids": 3,
        "network_ids": 2,
        "literature_ids": 2,
    }
    contract = context["parser_writable_contract"]
    assert contract["top_level_keys"] == [
        "beta_definition_id",
        "constant_value",
        "evidence_vlm_ids",
        "evidence_network_ids",
        "evidence_citation_ids",
        "uncertainty_log10",
        "estimation_method",
        "assumptions",
        "rationale",
        "source_excerpts",
    ]
    assert set(contract["source_excerpts"]) == {
        "topology_excerpt",
        "beta_definition_excerpt",
        "constant_value_excerpt",
        "uncertainty_excerpt",
        "evidence_excerpt",
        "estimation_method_excerpt",
        "assumption_excerpts",
        "rationale_excerpt",
    }


def test_request_followup_topics_are_latest_gate_owned(tmp_path: Path) -> None:
    service = _service(tmp_path)
    toolbox = ParserToolbox(service)
    report = service.check_draft("d001")
    assert service.query_agent_followup_topics(report) == ["uncertainty"]

    with pytest.raises(ValueError, match="exactly match"):
        toolbox.finish_parser_cycle(
            action="request_followup",
            missing_topics_csv="rationale",
        )
    with pytest.raises(ValueError, match="exactly match"):
        toolbox.finish_parser_cycle(action="request_followup")

    payload = toolbox.finish_parser_cycle(
        action="request_followup",
        reason="uncertainty is absent from the chemistry answer",
        missing_topics_csv="uncertainty",
    )
    assert '"uncertainty"' in payload
    assert service.state.terminal_missing_topics == ["uncertainty"]


def test_request_followup_survives_parser_cleanup_and_superseding_report(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    toolbox = ParserToolbox(service)
    report = service.check_draft("d001")
    receipt = service.state.query_followup_authorizations[0]
    assert receipt["gate_state_revision"] == report.state_revision
    assert receipt["topics"] == ["uncertainty"]

    # Parser-only workspace changes cannot add the chemistry that was absent
    # from the unchanged QueryAgent transcript.
    service.state.update_draft("d001", {"rationale": "updated parser text"})
    service.check_draft("does-not-exist")
    service.state.discard_draft("d001")

    assert service.query_agent_followup_topics() == ["uncertainty"]
    payload = toolbox.finish_parser_cycle(
        action="request_followup",
        missing_topics_csv="uncertainty",
    )
    assert '"status": "query_followup_requested"' in payload


def test_new_query_answer_invalidates_prior_followup_authorization(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    toolbox = ParserToolbox(service)
    old_report = service.check_draft("d001")
    assert service.query_agent_followup_topics() == ["uncertainty"]

    service.state.add_answer_turn(
        answer="For beta_def_872 the uncertainty is 0.5 log10 units.",
        evidence_snapshot=service.state.evidence_snapshot,
        prompt_sha256="f" * 64,
    )

    assert service.query_agent_followup_topics() == []
    assert service.query_agent_followup_topics(old_report) == []
    with pytest.raises(ValueError, match="not authorized"):
        toolbox.finish_parser_cycle(
            action="request_followup",
            missing_topics_csv="uncertainty",
        )


def test_parser_owned_source_failure_never_authorizes_query_followup(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    toolbox = ParserToolbox(service)
    service.state.update_draft("d001", {"uncertainty_log10": 0.5})

    report = service.run_entry_gate("d001")
    assert not report.passed
    assert {issue.owner.value for issue in report.issues} == {"parser"}
    assert service.state.query_followup_authorizations == []

    service.state.discard_draft("d001")
    assert service.query_agent_followup_topics() == []
    with pytest.raises(ValueError, match="not authorized"):
        toolbox.finish_parser_cycle(
            action="request_followup",
            missing_topics_csv="uncertainty",
        )


def test_gate_owned_evidence_gap_survives_failed_draft_discard(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    toolbox = ParserToolbox(service)
    service.record_query_agent_gap(
        code="missing_authorized_evidence",
        message="the answer does not identify usable SRD-46 support",
        missing_topics=["supporting_evidence"],
    )

    service.state.discard_draft("d001")

    assert service.query_agent_followup_topics() == ["supporting_evidence"]
    payload = toolbox.finish_parser_cycle(
        action="request_followup",
        missing_topics_csv="supporting_evidence",
    )
    assert '"supporting_evidence"' in payload


def test_normalize_query_turn_preserves_timeout_error_and_elapsed() -> None:
    memory: list[dict[str, str]] = []
    turn = normalize_query_turn(SimpleNamespace(
        answer="partial",
        memory=memory,
        elapsed_seconds=2.75,
        timed_out=True,
        _error="upstream failure",
    ))
    assert turn.elapsed_s == pytest.approx(2.75)
    assert turn.timed_out is True
    assert turn.error == "upstream failure"


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("empty", "empty_answer"),
        ("timed_out", "timeout"),
        ("error", "agent_error"),
        ("raise_timeout", "timeout"),
        ("raise_error", "runner_error"),
    ],
)
def test_bad_clarification_turn_fails_before_session_mutation(
    tmp_path: Path, mode: str, expected_code: str
) -> None:
    memory: list[dict[str, str]] = []
    initial = QueryTurn(answer="initial chemistry", memory=memory)
    session = QuerySession(
        query_id="q001",
        scope=_scope(),
        artifact_dir=tmp_path / "query_agents" / "q001",
        memory=memory,
        request_T_C=25.0,
        request_I_M=0.1,
        dispatch_turn=initial,
        evidence_authorization={"sentinel": "unchanged"},
    )
    seen: dict[str, float] = {}

    def runner(_prompt: str, *, memory, timeout: float, **_kwargs):
        seen["timeout"] = timeout
        if mode == "raise_timeout":
            raise TimeoutError("dummy deadline")
        if mode == "raise_error":
            raise RuntimeError("dummy failure")
        return QueryTurn(
            answer="" if mode == "empty" else "additional chemistry",
            memory=memory,
            timed_out=mode == "timed_out",
            error="dummy error" if mode == "error" else None,
        )

    with pytest.raises(QueryClarificationFailure) as captured:
        run_query_clarification(
            session=session,
            missing_topics=["uncertainty"],
            settings=_settings(),
            query_runner=runner,
            query_system_prompt="ordinary chemistry assistant",
            timeout_s=5.0,
        )
    assert captured.value.code == expected_code
    assert seen["timeout"] == pytest.approx(5.0)
    assert session.followup_turns == []
    assert session.evidence_authorization == {"sentinel": "unchanged"}
    assert not (session.artifact_dir / "query_agent_followups").exists()


def test_custom_parser_cannot_dispatch_an_ungated_followup(tmp_path: Path) -> None:
    memory: list[dict[str, str]] = []
    session = QuerySession(
        query_id="q001",
        scope=_scope(),
        artifact_dir=tmp_path / "query_agents" / "q001",
        memory=memory,
        request_T_C=25.0,
        request_I_M=0.1,
        dispatch_turn=QueryTurn(answer="ordinary chemistry prose", memory=memory),
        evidence_authorization={},
    )
    query_calls = 0

    def parser_runner(**_kwargs):
        return ParserCycleResult(
            action=ParserAction.REQUEST_FOLLOWUP,
            missing_topics=["rationale"],
        )

    def query_runner(*_args, **_kwargs):
        nonlocal query_calls
        query_calls += 1
        raise AssertionError("ungated follow-up must not reach QueryAgent")

    result = run_parse_speciation_answer(
        sessions=[session],
        output_dir=tmp_path,
        settings=_settings(),
        base_eq_map_card={"equilibrium_networks": []},
        query_runner=query_runner,
        query_system_prompt="ordinary chemistry assistant",
        parser_runner=parser_runner,
    )
    assert query_calls == 0
    assert result.parsed_queries == []
    assert result.failures[0]["failure_kind"] == "parser_revise"


def test_empty_authorized_clarification_is_a_per_query_failure(tmp_path: Path) -> None:
    memory: list[dict[str, str]] = []
    session = QuerySession(
        query_id="q001",
        scope=_scope(),
        artifact_dir=tmp_path / "query_agents" / "q001",
        memory=memory,
        request_T_C=25.0,
        request_I_M=0.1,
        dispatch_turn=QueryTurn(answer="ordinary chemistry prose", memory=memory),
        evidence_authorization={},
    )

    def parser_runner(*, service, **_kwargs):
        service.record_query_agent_gap(
            code="missing_uncertainty",
            message="uncertainty is absent",
            missing_topics=["uncertainty"],
        )
        service.state.set_terminal(
            ParserAction.REQUEST_FOLLOWUP,
            "uncertainty is absent",
            ["uncertainty"],
        )
        return ParserCycleResult(
            action=ParserAction.REQUEST_FOLLOWUP,
            missing_topics=["uncertainty"],
        )

    def query_runner(_prompt: str, *, memory, **_kwargs):
        return QueryTurn(answer=" ", memory=memory)

    result = run_parse_speciation_answer(
        sessions=[session],
        output_dir=tmp_path,
        settings=_settings(),
        base_eq_map_card={"equilibrium_networks": []},
        query_runner=query_runner,
        query_system_prompt="ordinary chemistry assistant",
        parser_runner=parser_runner,
    )
    assert result.parsed_queries == []
    assert result.failures[0]["failure_kind"] == "fatal_host"
    assert "empty_answer" in result.failures[0]["error"]
    assert result.failures[0]["query_clarification_rounds"] == 1


def test_parser_revise_feedback_carries_gate_findings(tmp_path: Path) -> None:
    memory: list[dict[str, str]] = []
    session = QuerySession(
        query_id="q001",
        scope=_scope(),
        artifact_dir=tmp_path / "query_agents" / "q001",
        memory=memory,
        request_T_C=25.0,
        request_I_M=0.1,
        dispatch_turn=QueryTurn(answer="ordinary chemistry prose", memory=memory),
        evidence_authorization={},
    )
    captured: list[str | None] = []

    def parser_runner(*, service, feedback=None, **_kwargs):
        captured.append(feedback)
        if len(captured) == 1:
            service.state.create_draft({
                "beta_definition_id": 872,
                "constant_value": 20.4,
                "evidence_vlm_ids": [93785],
                "estimation_method": "analogue transfer",
                "assumptions": ["the same reference state"],
                "rationale": "HIDA chelates the metal",
            })
            service.check_draft("d001")
            return ParserCycleResult(
                action=ParserAction.PARSER_REVISE, reason="draft is incomplete",
            )
        return ParserCycleResult(
            action=ParserAction.PARSER_REVISE, reason="still incomplete",
        )

    result = run_parse_speciation_answer(
        sessions=[session],
        output_dir=tmp_path,
        settings=_settings(parser_validation_retries=1),
        base_eq_map_card={"equilibrium_networks": []},
        query_system_prompt="ordinary chemistry assistant",
        parser_runner=parser_runner,
    )
    assert result.parsed_queries == []
    assert result.failures[0]["parser_cycles"] == 2
    assert captured[0] is None
    digest = captured[1]
    assert digest is not None
    assert "Previous cycle: draft is incomplete" in digest
    assert "Workspace at cycle end (revision 1): d001=draft/unannotated" in digest
    assert "Drafts and annotations persist across cycles" in digest
    assert "gate=draft_completeness, revision 1" in digest
    assert "[d001] missing_uncertainty_log10" in digest
    assert "workspace changed after this report" not in digest


def test_revise_feedback_digest_bounds(tmp_path: Path) -> None:
    state = ParserWorkingState.create(
        query_id="q001",
        scope=_scope(),
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer="ordinary chemistry prose",
        evidence_snapshot={},
    )
    empty = _revise_feedback(state, "engine timeout")
    assert "Previous cycle: engine timeout" in empty
    assert "no drafts exist yet" in empty
    assert "Last failed gate report" not in empty

    state.record_report(GateReport(
        gate="entry",
        status="fail",
        state_revision=state.revision,
        issues=[
            GateIssue(
                code=f"issue_{index:02d}",
                owner=GateOwner.PARSER,
                message="x" * 700 if index == 0 else "short message",
                draft_id="d001",
            )
            for index in range(12)
        ],
    ))
    state.create_draft({"constant_value": 1.0})
    digest = _revise_feedback(state, "parser ended without a terminal tool commit")
    assert "d001=draft" in digest
    assert "workspace changed after this report" in digest
    assert "issue_09" in digest
    assert "issue_10" not in digest
    assert "(+2 more issues; re-run the gates for the rest)" in digest
    assert " [truncated]" in digest
    assert "x" * 601 not in digest


def test_source_excerpt_patches_merge_per_key() -> None:
    state = ParserWorkingState.create(
        query_id="q001",
        scope=_scope(),
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer="ordinary chemistry prose",
        evidence_snapshot={},
    )
    draft = state.create_draft({
        "constant_value": 1.0,
        "source_excerpts": {
            "topology_excerpt": "Fe2+ + L = FeL2+",
            "constant_value_excerpt": "Fe2+ + L = FeL2+, log10 K = 1.0",
        },
    })
    patched = state.update_draft(draft.draft_id, {
        "source_excerpts": {"estimation_method_excerpt": "by analogue transfer"},
    })
    assert patched.source_excerpts == {
        "topology_excerpt": "Fe2+ + L = FeL2+",
        "constant_value_excerpt": "Fe2+ + L = FeL2+, log10 K = 1.0",
        "estimation_method_excerpt": "by analogue transfer",
    }
    removed = state.update_draft(draft.draft_id, {
        "source_excerpts": {"constant_value_excerpt": None},
    })
    assert "constant_value_excerpt" not in removed.source_excerpts
    assert removed.source_excerpts["topology_excerpt"] == "Fe2+ + L = FeL2+"
    with pytest.raises(ValueError, match="send null to delete"):
        state.update_draft(draft.draft_id, {
            "source_excerpts": {"rationale_excerpt": ["not", "a", "string"]},
        })
    survivor = state.drafts[draft.draft_id]
    assert "rationale_excerpt" not in survivor.source_excerpts
    assert survivor.source_excerpts["estimation_method_excerpt"] == (
        "by analogue transfer"
    )
