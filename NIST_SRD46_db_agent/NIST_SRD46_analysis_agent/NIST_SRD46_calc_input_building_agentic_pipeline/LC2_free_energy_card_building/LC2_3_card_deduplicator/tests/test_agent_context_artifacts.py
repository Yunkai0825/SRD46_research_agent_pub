import json
from types import SimpleNamespace

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.card_management_helpers.dedup_md_card_reader import (
    DedupGroup,
    DedupReport,
    DedupSpecies,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.agent_context_artifacts import (
    write_agent_context_bundle,
    write_agent_context_index,
)
import NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_3_card_deduplicator.lc2_3_dedup_agent as dedup_module
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_free_energy_card_orchestrator import (
    _write_summary,
)


def test_context_bundle_preserves_audit_inputs_and_full_tool_results(tmp_path):
    long_value = "x" * 500
    result = SimpleNamespace(
        answer="committed",
        final_context="visible final context",
        iterations=2,
        elapsed_seconds=1.25,
        timed_out=False,
        tool_history=[{
            "iteration": 1,
            "tool": "commit",
            "arguments": {"payload": long_value},
            "result_full": "OK " + long_value,
            "reasoning": "internal model reasoning must not be exported",
        }],
    )

    write_agent_context_bundle(
        tmp_path / "turn",
        stage_id="LC2_3.test",
        stage_label="test turn",
        role="test agent",
        phase="review",
        system_prompt="EXACT SYSTEM",
        user_message="EXACT USER",
        tools={"commit": lambda json_payload="": json_payload},
        required_tools={"commit"},
        memory=[],
        result=result,
        runtime={"model": "test-model", "max_tool_iterations": 3},
    )

    assert (tmp_path / "turn/system_prompt.md").read_text() == "EXACT SYSTEM"
    assert (tmp_path / "turn/user_message.md").read_text() == "EXACT USER"
    calls = json.loads((tmp_path / "turn/tool_calls.json").read_text())
    assert calls[0]["arguments"]["payload"] == long_value
    assert calls[0]["result_full"] == "OK " + long_value
    assert "reasoning" not in calls[0]
    manifest = json.loads(
        (tmp_path / "turn/agent_context_manifest.json").read_text()
    )
    assert manifest["runtime"]["model"] == "test-model"
    assert manifest["context"]["file_integrity"]["system_prompt"]["bytes"]
    assert len(
        manifest["context"]["file_integrity"]["system_prompt"]["sha256"]
    ) == 64

    index_json, _ = write_agent_context_index(tmp_path)
    index = json.loads(index_json.read_text())
    assert index["agent_turn_count"] == 1
    assert index["complete_agent_turn_count"] == 1
    assert index["all_context_bundles_complete"] is True
    assert index["agent_turns"][0]["fresh_context"] is True

    (tmp_path / "turn/system_prompt.md").write_text("TAMPERED")
    index_json, _ = write_agent_context_index(tmp_path)
    tampered = json.loads(index_json.read_text())
    assert tampered["agent_turn_count"] == 1
    assert tampered["complete_agent_turn_count"] == 0
    assert tampered["all_context_bundles_complete"] is False


def test_targeted_plan_reaches_singleton_redispatch(monkeypatch, tmp_path):
    captured = {}

    def fake_singletons_agent(**kwargs):
        captured.update(kwargs)
        return {
            "decisions": [{
                "phase": "solid",
                "core_label": "Fe$+2:1 H:-2",
                "keep_species": [{"name": "Fe(OH)2", "source": "Atlas"}],
                "rationale": "Retain the requested hydrated phase.",
            }],
            "error": None,
            "iterations": 1,
            "n_tools": 1,
        }

    monkeypatch.setattr(dedup_module, "run_singletons_agent", fake_singletons_agent)
    report = DedupReport(
        system_name="Fe test",
        baseline_source="SRD-46",
        sources_present=["Atlas"],
        component_mapping=[],
        groups=[DedupGroup(
            phase="solid",
            core_label="Fe$+2:1 H:-2",
            species=[DedupSpecies(
                name="Fe(OH)2",
                source="Atlas",
                charge=0,
                multiplier=1,
                mu_aligned_kJ=1.0,
                phase="solid",
                core_label="Fe$+2:1 H:-2",
            )],
        )],
        totals={},
    )

    dedup_module._run_dedup_pass(
        report_obj=report,
        inventory=[],
        plan="[Targeted supervisor guidance]\nKEEP THIS SINGLETON",
        element_instructions={"Fe": "Retain supported hydrated phases."},
        generation_dir=tmp_path / "targeted",
        debug=False,
    )

    assert "KEEP THIS SINGLETON" in captured["plan"]
    assert "Retain supported hydrated phases" in captured["plan"]
    assert "purpose" not in captured
    assert "tasks" not in captured
    manifest = json.loads(
        (tmp_path / "targeted/generation_manifest.json").read_text()
    )
    assert "original_request" not in manifest
    assert manifest["singleton_worker"]["receives_general_or_targeted_plan"]
    assert "receives_original_request" not in manifest["singleton_worker"]


def test_reconfigured_lc2_3_session_never_reuses_stale_call_directory(tmp_path):
    prior = dict(dedup_module._SESSION)
    try:
        dedup_module.configure_lc2_3_session(session_dir=tmp_path)
        first = dedup_module._per_call_dir()
        assert first.name == "LC2_3_call_01"

        dedup_module.configure_lc2_3_session(session_dir=tmp_path)
        second = dedup_module._per_call_dir()
        assert second.name == "LC2_3_call_02"
        assert second != first
    finally:
        dedup_module._SESSION.clear()
        dedup_module._SESSION.update(prior)


def test_lc2_root_artifact_manifest_aggregates_verified_contexts(tmp_path):
    write_agent_context_bundle(
        tmp_path / "LC2_3/context_01",
        stage_id="LC2_3.test",
        stage_label="test",
        role="test",
        phase="review",
        system_prompt="SYSTEM",
        user_message="USER",
        tools={},
        required_tools=[],
        memory=[],
        result=SimpleNamespace(
            answer="done",
            final_context="FINAL",
            iterations=1,
            elapsed_seconds=0.1,
            timed_out=False,
            tool_history=[],
        ),
    )
    (tmp_path / "LC2_1").mkdir()
    (tmp_path / "LC2_1/lc2_1_manifest.json").write_text(json.dumps({
        "agent_context": {
            "expected_calls": 0,
            "documented_calls": 0,
            "complete": True,
        }
    }))
    (tmp_path / "LC2_3/lc2_3_manifest.json").write_text(json.dumps({
        "agent_context": {
            "expected_calls": 1,
            "documented_calls": 1,
            "complete": True,
        }
    }))
    out = {
        "status": "ok",
        "stages_run": ["LC2_1", "LC2_3"],
        "inputs": {},
        "final_card_path": None,
    }

    _write_summary(tmp_path, out)

    manifest = json.loads(
        (tmp_path / "summary/LC2_artifact_manifest.json").read_text()
    )
    assert manifest["agent_context_audit"] == {
        "expected_calls": 1,
        "documented_calls": 1,
        "indexed_manifests": 1,
        "verified_bundles": 1,
        "complete": True,
        "stage_audits": manifest["agent_context_audit"]["stage_audits"],
    }
    assert out["artifact_manifest_path"].endswith(
        "LC2_artifact_manifest.json"
    )
