from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.dispatch_srd46_query import pair_scopes
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.dispatch_srd46_query.dispatch_srd46_query_orchestrator import (
    _render_prompt,
    run_dispatch_srd46_query,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.dispatch_srd46_query.query_agent_runtime import (
    get_query_agent_system_prompt,
    render_query_estimation_mode_prompt,
    render_query_estimation_planner_prompt,
    run_query_agent,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (
    LC13Settings,
    QuerySession,
    QueryTurn,
)


def _settings() -> LC13Settings:
    return LC13Settings(
        max_query_runs=8,
        query_model="test",
        query_max_iterations=9,
        query_timeout_s=10.0,
        parser_max_rounds=3,
        parser_timeout_s=10.0,
        parser_model="test",
        failure_policy="reference_only",
    )


def test_estimation_system_prompt_is_chemistry_only_and_has_no_json_contract() -> None:
    system_extension = render_query_estimation_mode_prompt()
    assert "chemistry reasoning" in system_extension.lower()
    assert "json" not in system_extension.lower()
    assert "parsed_speciation" not in system_extension
    assert '"outcome"' not in system_extension
    system_prompt = get_query_agent_system_prompt()
    assert system_prompt.endswith("\n\n" + system_extension)
    assert "MANDATORY WORKFLOW:" not in system_prompt
    assert "MEMORY COMPRESSION:" not in system_prompt
    assert "Never invent numeric values" not in system_prompt
    assert "do not restart compound discovery" in system_extension.lower()
    assert "0_plan_search_strategy" in system_extension

    planner_extension = render_query_estimation_planner_prompt()
    assert "analogue-selection" in planner_extension
    assert "target metal and ligand ids" in planner_extension.lower()
    assert "reaction-frame" in planner_extension
    assert "json" not in planner_extension.lower()


def test_embedded_dummy_session_requires_fresh_analogue_plan(
    monkeypatch,
) -> None:
    """LC1.3 must select the QueryAgent's enforced fresh-plan mode."""

    query_agent_module = importlib.import_module(
        "NIST_SRD46_db_agent.NIST_SRD46_query_agent.query_agent"
    )
    captured: dict[str, object] = {}

    def fake_run_agent_query_sync(
        message: str,
        *,
        memory: list[dict[str, str]],
        **kwargs: object,
    ) -> QueryTurn:
        captured.update({"message": message, "memory": memory, **kwargs})
        memory.extend([
            {"role": "assistant", "content": "<tool_call>planner</tool_call>"},
            {"role": "user", "content": "<tool_result>[PLAN] dummy</tool_result>"},
            {"role": "assistant", "content": "dummy chemistry answer"},
        ])
        return QueryTurn(
            answer="dummy chemistry answer",
            memory=memory,
            tool_history=[{
                "tool": "0_plan_search_strategy",
                "is_error": False,
                "result_full": "[PLAN] dummy",
            }],
        )

    monkeypatch.setattr(
        query_agent_module,
        "run_agent_query_sync",
        fake_run_agent_query_sync,
    )
    memory: list[dict[str, str]] = []
    result = run_query_agent(
        "estimate the resolved dummy pair",
        memory=memory,
        timeout=10.0,
        max_tool_iterations=5,
        model="dummy-model",
    )

    assert result.answer == "dummy chemistry answer"
    assert result.memory is memory
    assert captured["pre_resolved_workflow"] is True
    assert captured["require_fresh_plan"] is True
    assert captured["enable_memory_compaction"] is False
    assert captured["model_override"] == "dummy-model"
    assert captured["planner_system_prompt_module"] == (
        render_query_estimation_planner_prompt()
    )


def test_dispatch_prompt_pairs_names_and_ids_for_single_and_multi_scopes() -> None:
    prompt = _render_prompt(
        purpose="aqueous speciation",
        scope={
            "metal_id": 41,
            "metal_name": "Cu(II)",
            "ligand_id": 10103,
            "ligand_name": "ammonia",
        },
        request_T_C=25.0,
        request_I_M=0.1,
    )
    assert "\n" not in prompt
    assert "JSON" not in prompt
    assert "tool" not in prompt.lower()
    assert "estimate" in prompt.lower()
    assert "Cu(II) (metal_41)" in prompt
    assert "ammonia (ligand_10103)" in prompt

    multi_prompt = _render_prompt(
        purpose="comparative aqueous speciation",
        scope={
            "metal_id_list": [41, 42],
            "metal_name_list": ["Cu(II)", "Cu(I)"],
            "ligand_id_list": [10103, 10012],
            "ligand_name_list": ["ammonia", "glycine"],
        },
        request_T_C=25.0,
        request_I_M=0.1,
    )
    assert "Cu(II) (metal_41)" in multi_prompt
    assert "Cu(I) (metal_42)" in multi_prompt
    assert "ammonia (ligand_10103)" in multi_prompt
    assert "glycine (ligand_10012)" in multi_prompt

    with pytest.raises(ValueError, match="aligned lists"):
        _render_prompt(
            purpose="invalid",
            scope={
                "metal_id_list": [41],
                "metal_name_list": ["Cu(II)", "Cu(I)"],
                "ligand_id": 10103,
                "ligand_name": "ammonia",
            },
            request_T_C=25.0,
            request_I_M=0.1,
        )


def test_dispatch_makes_exactly_one_unrestricted_call(tmp_path: Path) -> None:
    calls: list[dict] = []
    session = QuerySession(
        query_id="q001",
        scope={
            "metal_id": 41,
            "metal_name": "Cu(II)",
            "ligand_id": 10103,
            "ligand_name": "ammonia",
        },
        artifact_dir=tmp_path / "query_agents" / "q001",
        request_T_C=25.0,
        request_I_M=0.1,
    )

    def runner(message: str, **kwargs: object) -> QueryTurn:
        calls.append({"message": message, **kwargs})
        memory = kwargs["memory"]
        assert isinstance(memory, list)
        memory.append({"role": "assistant", "content": "Estimated log K = 4.2."})
        return QueryTurn(answer="Estimated log K = 4.2.", memory=memory)

    result = run_dispatch_srd46_query(
        sessions=[session],
        purpose="test",
        tasks="ignored parent task text",
        chemical_context_plan="ignored parent plan text",
        request_T_C=25.0,
        request_I_M=0.1,
        output_dir=tmp_path,
        settings=_settings(),
        query_runner=runner,
        query_system_prompt="standard tools plus one chemistry paragraph",
    )

    assert len(calls) == 1
    assert set(calls[0]) == {
        "message", "memory", "timeout", "max_tool_iterations"
    }
    assert "ignored parent" not in calls[0]["message"]
    assert result.dispatched_sessions == [session]
    receipts = json.loads(
        (session.artifact_dir / "evidence_receipts.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipts["authorization_version"] == 3
    assert receipts["tool_receipts"] == []
    assert not (session.artifact_dir / "authorization_policy.json").exists()
    assert not (session.artifact_dir / "planning_gate.json").exists()
    assert not (session.artifact_dir / "parser_requested_clarifications").exists()


@pytest.mark.parametrize(
    "turn, message",
    [
        (QueryTurn(answer="partial", memory=[], timed_out=True), "timeout"),
        (QueryTurn(answer="partial", memory=[], error="upstream 500"), "error"),
        (QueryTurn(answer="   ", memory=[]), "empty answer"),
    ],
)
def test_initial_query_failures_are_persisted_and_block_dispatch(
    tmp_path: Path, turn: QueryTurn, message: str
) -> None:
    session = QuerySession(
        query_id="q001",
        scope={
            "metal_id": 41,
            "metal_name": "Cu(II)",
            "ligand_id": 10103,
            "ligand_name": "ammonia",
        },
        artifact_dir=tmp_path / "query_agents" / "q001",
        request_T_C=25.0,
        request_I_M=0.1,
    )

    def runner(_message: str, *, memory: list[dict[str, str]], **_kwargs) -> QueryTurn:
        turn.memory = memory
        return turn

    with pytest.raises(RuntimeError, match=message):
        run_dispatch_srd46_query(
            sessions=[session],
            purpose="test",
            tasks="",
            chemical_context_plan=None,
            request_T_C=25.0,
            request_I_M=0.1,
            output_dir=tmp_path,
            settings=_settings(),
            query_runner=runner,
            query_system_prompt="chemistry context",
        )

    query_dir = session.artifact_dir / "01_dispatch_srd46_query"
    assert (query_dir / "user_prompt.md").is_file()
    failure = json.loads((query_dir / "dispatch_failure.json").read_text())
    assert failure["status"] == "failed"
    manifest = json.loads((query_dir / "turn_manifest.json").read_text())
    assert manifest["timed_out"] is turn.timed_out
    assert manifest["error"] == turn.error
    assert manifest["answer_nonempty"] is bool(turn.answer.strip())


def test_every_canonical_pair_is_selected_even_when_base_map_has_rows(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pair_scopes,
        "target_metals",
        lambda _system: [(41, "Cu(II)"), (42, "Cu(I)")],
    )
    monkeypatch.setattr(
        pair_scopes,
        "target_ligands",
        lambda _system: [(10103, "ammonia"), (10012, "glycine")],
    )
    rows = pair_scopes.build_pair_scopes(
        chemical_system={},
        base_eq_map_card={
            "equilibrium_networks": [
                {"metal_id": 41, "ligand_id": 10103, "network": "existing"}
            ]
        },
    )
    assert [(row["metal_id"], row["ligand_id"]) for row in rows] == [
        (41, 10103),
        (41, 10012),
        (42, 10103),
        (42, 10012),
    ]
    assert rows[0]["base_reference_network_count"] == 1
    assert rows[1]["base_reference_network_count"] == 0
    assert all(
        not isinstance(row["metal_id"], list)
        and not isinstance(row["ligand_id"], list)
        for row in rows
    )


@pytest.mark.parametrize(
    "base_card",
    [
        {
            "equilibrium_networks": [{
                "metal_id": "metal_41",
                "ligand_id": "ligand_7795",
                "eq_network": "ref_eq_net_13347",
            }],
        },
        {
            "pairs": [{
                "metal_id": 41,
                "ligand_id": 7795,
                "selected_network_ids": [13347],
            }],
        },
    ],
    ids=["prefixed_flat_card", "normalized_pairs_card"],
)
def test_pair_scope_counts_reference_networks_in_both_card_grammars(
    monkeypatch, base_card: dict
) -> None:
    monkeypatch.setattr(
        pair_scopes, "target_metals", lambda _system: [(41, "Cu(II)")]
    )
    monkeypatch.setattr(
        pair_scopes, "target_ligands", lambda _system: [(7795, "imidazole")]
    )
    rows = pair_scopes.build_pair_scopes(
        chemical_system={},
        base_eq_map_card=base_card,
    )
    assert len(rows) == 1
    assert rows[0]["base_reference_network_count"] == 1
    assert rows[0]["base_reference_networks"][0]["eq_network"] == (
        "ref_eq_net_13347"
    )
