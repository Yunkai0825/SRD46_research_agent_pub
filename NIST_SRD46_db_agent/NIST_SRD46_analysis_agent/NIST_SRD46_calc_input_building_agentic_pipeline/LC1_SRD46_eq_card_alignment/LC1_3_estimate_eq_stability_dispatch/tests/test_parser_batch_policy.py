"""Regression tests for LC1_3 parser transaction sequencing."""

from __future__ import annotations

import json
from pathlib import Path

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.candidate_schema import (
    GateReport,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_batch_policy import (
    ParserBatchPolicy,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_gate_service import (
    ParserGateService,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_working_state import (
    ParserWorkingState,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_tools import (
    ParserToolbox,
)


def _service(tmp_path: Path) -> ParserGateService:
    base = {"equilibrium_networks": []}
    state = ParserWorkingState.create(
        query_id="q001",
        scope={"metal_id": 61, "ligand_id": 9825},
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card=base,
        initial_answer=(
            "For beta_def_812 I estimate log10 K = -0.5 with uncertainty "
            "1.0 using vlm_168275 by analogue transfer."
        ),
        evidence_snapshot={},
    )
    return ParserGateService(
        state=state,
        base_eq_map_card=base,
        session_id="parser-batch-test",
        artifact_dir=tmp_path,
    )


def _call(name: str, **arguments: object) -> dict[str, object]:
    return {"name": name, "arguments": arguments}


def test_mixed_batch_executes_revision_and_discards_later_phases(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.state.create_draft({"rationale": "old rationale"})
    policy = ParserBatchPolicy(service)
    revision = service.state.revision
    calls = [
        _call(
            "update_equilibrium_draft",
            draft_id="d001",
            patch_json=json.dumps({"rationale": "revised rationale"}),
        ),
        _call("check_draft", draft_id="d001"),
        _call("run_entry_gate", draft_id="d001"),
        _call("run_network_gate"),
        _call("finish_parser_cycle", action="commit"),
    ]

    result = policy.validate(calls, ParserToolbox(service).tools())

    assert result is None
    assert [call["name"] for call in calls] == ["update_equilibrium_draft"]
    tools = ParserToolbox(service).tools()
    for call in calls:
        tools[str(call["name"])](**call["arguments"])
    assert service.state.drafts["d001"].rationale == "revised rationale"
    assert service.state.revision == revision + 1
    assert service.state.gate_reports == []
    assert service.state.terminal_action is None


def test_badly_ordered_batch_selects_minimum_transaction_phase(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.state.create_draft({"rationale": "old rationale"})
    policy = ParserBatchPolicy(service)
    calls = [
        _call("check_draft", draft_id="d001"),
        _call(
            "update_equilibrium_draft",
            draft_id="d001",
            patch_json=json.dumps({"rationale": "first revision"}),
        ),
        _call("run_network_gate"),
        _call(
            "update_equilibrium_draft",
            draft_id="d001",
            patch_json=json.dumps({"rationale": "second revision"}),
        ),
    ]

    assert policy.validate(calls, ParserToolbox(service).tools()) is None
    assert [call["name"] for call in calls] == [
        "update_equilibrium_draft",
        "update_equilibrium_draft",
    ]


def test_independent_calls_from_one_phase_remain_batchable(tmp_path: Path) -> None:
    policy = ParserBatchPolicy(_service(tmp_path))

    assert policy.validate(
        [
            _call("check_draft", draft_id="d001"),
            _call("check_draft", draft_id="d002"),
        ],
        {},
    ) is None
    assert policy.validate(
        [
            _call("run_entry_gate", draft_id="d001"),
            _call("run_entry_gate", draft_id="d002"),
        ],
        {},
    ) is None


def test_network_and_finish_phases_are_singletons(tmp_path: Path) -> None:
    policy = ParserBatchPolicy(_service(tmp_path))

    network_calls = [_call("run_network_gate"), _call("run_network_gate")]
    assert policy.validate(network_calls, {}) is None
    assert len(network_calls) == 1

    finish_calls = [
        _call("finish_parser_cycle", action="no_estimate"),
        _call("finish_parser_cycle", action="no_estimate"),
    ]
    assert policy.validate(finish_calls, {}) is None
    assert len(finish_calls) == 1


def test_commit_requires_current_revision_network_pass(tmp_path: Path) -> None:
    service = _service(tmp_path)
    policy = ParserBatchPolicy(service)
    commit = [_call("finish_parser_cycle", action="commit")]

    assert "current workspace revision" in (policy.validate(commit, {}) or "")

    service.state.record_report(GateReport(
        gate="network",
        status="pass",
        state_revision=service.state.revision,
    ))
    assert policy.validate(commit, {}) is None

    service.state.create_draft({"beta_definition_id": 812})
    assert "current workspace revision" in (policy.validate(commit, {}) or "")


def test_noncommit_terminal_actions_do_not_require_network_gate(
    tmp_path: Path,
) -> None:
    policy = ParserBatchPolicy(_service(tmp_path))

    assert policy.validate(
        [_call("finish_parser_cycle", action="request_followup")],
        {},
    ) is None
    assert policy.validate(
        [_call("finish_parser_cycle", action="no_estimate")],
        {},
    ) is None
