"""Regression tests for the plain QueryAgent/tool-parser trust boundary."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest


PACKAGE = (
    "NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
    "NIST_SRD46_calc_input_building_agentic_pipeline."
    "LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch"
)
THIS_FILE = Path(__file__).resolve()
LC13_ROOT = THIS_FILE.parents[1]
DB_AGENT_ROOT = next(
    parent for parent in THIS_FILE.parents if parent.name == "NIST_SRD46_db_agent"
)

PROTECTED_FILES = {
    DB_AGENT_ROOT / "NIST_SRD46_query_agent" / "agent_runtime.py": (
        "E29ABDA664B74CCE6468BEF536089A65542308A85B6D8C8B211EFB4DE2094F74"
    ),
    LC13_ROOT / "dispatch_srd46_query" / "query_estimation_system_prompt.md": (
        "A757B213154CF9D44A984E57F662254E52CBD0B808C89E52F1EAFF16C8B2D375"
    ),
    LC13_ROOT / "dispatch_srd46_query" / "query_estimation_planner_prompt.md": (
        "8665A541E3904D0C6E3F0572ABDD12AA4409FFFF9C68D835CB70AC86F8BF7473"
    ),
    LC13_ROOT / "dispatch_srd46_query" / "dispatch_query_prompt.md": (
        "23F4285645D06E252223413415B2C2642E46FDC347DB095ED719F98400A9D94B"
    ),
    LC13_ROOT / "dispatch_srd46_query" / "query_agent_runtime.py": (
        "F78C48370DB3146A12820CB1534E932FED78D4A948F926FF7186B09BFE471FB7"
    ),
    LC13_ROOT / "dispatch_srd46_query" / "dispatch_srd46_query_orchestrator.py": (
        "3839ED60C4C8CC0CB5760C66C19CD9F598AEB33E6514ACA034AE1CB02F7E1687"
    ),
}


def _module(relative_name: str):
    return importlib.import_module(f"{PACKAGE}.{relative_name}")


def _settings(runtime_models):
    return runtime_models.LC13Settings(
        max_query_runs=1,
        query_model="",
        query_max_iterations=8,
        query_timeout_s=30.0,
        parser_max_rounds=8,
        parser_timeout_s=30.0,
        parser_model="",
        failure_policy="reference_only",
        parser_validation_retries=1,
    )


def _scope() -> dict[str, object]:
    return {
        "metal_id": 61,
        "metal_name": "Fe^[3+]",
        "ligand_id": 11422,
        "ligand_name": "N,N-Dimethylformamide (DMF)",
        "base_reference_network_count": 0,
        "base_reference_networks": [],
    }


@pytest.mark.parametrize("path, expected", PROTECTED_FILES.items())
def test_query_agent_interfaces_remain_byte_identical(path: Path, expected: str) -> None:
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == expected


def test_first_query_call_remains_fresh_and_plain(tmp_path: Path) -> None:
    runtime_models = _module("runtime_support.runtime_models")
    dispatch = _module("dispatch_srd46_query.dispatch_srd46_query_orchestrator")
    session = runtime_models.QuerySession(
        query_id="q001",
        scope=_scope(),
        artifact_dir=tmp_path / "query_agents" / "q001",
        memory=[{"role": "assistant", "content": "stale planning text"}],
        request_T_C=25.0,
        request_I_M=0.1,
    )
    old_memory = session.memory
    calls = []

    def runner(prompt: str, *, memory: list[dict[str, str]], **kwargs):
        calls.append((prompt, memory, list(memory), kwargs))
        answer = "I estimate the target equilibrium from the inspected analogue."
        memory.extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ])
        return runtime_models.QueryTurn(answer=answer, memory=memory)

    dispatch.run_dispatch_srd46_query(
        sessions=[session],
        purpose="estimate missing equilibrium chemistry",
        tasks='parent-only {"schema": true}',
        chemical_context_plan="parent-only plan",
        request_T_C=25.0,
        request_I_M=0.1,
        output_dir=tmp_path,
        settings=_settings(runtime_models),
        query_runner=runner,
        query_system_prompt="ordinary chemistry assistant",
    )
    assert len(calls) == 1
    prompt, memory, before, _ = calls[0]
    assert before == []
    assert memory is session.memory
    assert session.memory is not old_memory
    assert "schema" not in prompt.lower()
    assert "json" not in prompt.lower()
    assert "parent-only" not in prompt


def test_parser_workspace_rejects_host_owned_fields() -> None:
    state_module = _module("parse_speciation_answer.parser_working_state")
    state = state_module.ParserWorkingState.create(
        query_id="q001",
        scope=_scope(),
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer="ordinary chemistry prose",
        evidence_snapshot={},
    )
    with pytest.raises(ValueError, match="host-owned fields"):
        state.create_draft({
            "beta_definition_id": 812,
            "equation_python": "invented reaction",
        })
    assert state.drafts == {}
    assert state.revision == 0


def test_parser_draft_mutations_are_atomic_and_ids_are_monotonic() -> None:
    state_module = _module("parse_speciation_answer.parser_working_state")
    state = state_module.ParserWorkingState.create(
        query_id="q001",
        scope=_scope(),
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer="ordinary chemistry prose",
        evidence_snapshot={},
    )
    first = state.create_draft({"beta_definition_id": 812})
    second = state.create_draft({"beta_definition_id": 840})
    second.constant_value = 0.7
    second.canonical_equilibrium = {"constant_value": 0.7}
    second.entry_gate_receipt_sha256 = "receipt"
    before_revision = state.revision

    with pytest.raises(ValueError, match="must be a list"):
        state.update_draft(second.draft_id, {
            "constant_value": 9.9,
            "evidence_vlm_ids": "invalid",
        })

    unchanged = state.drafts[second.draft_id]
    assert unchanged.constant_value == 0.7
    assert unchanged.canonical_equilibrium == {"constant_value": 0.7}
    assert unchanged.entry_gate_receipt_sha256 == "receipt"
    assert state.revision == before_revision

    state.discard_draft(first.draft_id)
    third = state.create_draft({"beta_definition_id": 872})
    assert second.draft_id == "d002"
    assert third.draft_id == "d003"
    assert state.drafts[second.draft_id].beta_definition_id == 840


def test_parser_rejects_unknown_source_excerpt_aliases_transactionally() -> None:
    state_module = _module("parse_speciation_answer.parser_working_state")
    state = state_module.ParserWorkingState.create(
        query_id="q001",
        scope=_scope(),
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer="ordinary chemistry prose",
        evidence_snapshot={},
    )
    with pytest.raises(ValueError, match="allowed keys"):
        state.create_draft({
            "beta_definition_id": 812,
            "source_excerpts": {"value": "not an allowed excerpt key"},
        })
    assert state.drafts == {}
    assert state.revision == 0


def test_parser_cannot_bind_an_invented_number() -> None:
    schema = _module("parse_speciation_answer.candidate_schema")
    grounding = _module("parse_speciation_answer.source_grounding")
    transcript = (
        "For beta_def_812 I estimate log10 K = 6.40. The uncertainty is 0.50. "
        "Evidence is vlm_95941. The method is analogue transfer. I assume the "
        "same reference state. The rationale is donor similarity."
    )
    draft = schema.EquilibriumDraft(
        draft_id="d001",
        beta_definition_id=812,
        constant_value=9.9,
        uncertainty_log10=0.5,
        evidence_vlm_ids=[95941],
        estimation_method="analogue transfer",
        assumptions=["the same reference state"],
        rationale="donor similarity",
        source_excerpts={
            "beta_definition_excerpt": "For beta_def_812 I estimate log10 K = 6.40.",
            "constant_value_excerpt": "For beta_def_812 I estimate log10 K = 6.40.",
            "uncertainty_excerpt": "The uncertainty is 0.50.",
            "evidence_excerpt": "Evidence is vlm_95941.",
            "estimation_method_excerpt": "The method is analogue transfer.",
            "assumption_excerpts": ["I assume the same reference state."],
            "rationale_excerpt": "The rationale is donor similarity.",
        },
    )
    with pytest.raises(grounding.SourceGroundingError, match="does not occur"):
        grounding.validate_draft_source_bindings(
            transcript=transcript,
            draft=draft,
        )


def test_parser_cannot_cross_bind_a_value_between_beta_definitions() -> None:
    schema = _module("parse_speciation_answer.candidate_schema")
    grounding = _module("parse_speciation_answer.source_grounding")
    row_812 = "beta_def_812 has estimated log10 K = 0.5 with uncertainty 0.7."
    row_840 = "beta_def_840 has estimated log10 K = 0.9 with uncertainty 1.0."
    transcript = (
        row_812 + " " + row_840
        + " Evidence is vlm_177390. The method is analogue transfer."
        + " I assume an aqueous reference state. The rationale is weak binding."
    )
    draft = schema.EquilibriumDraft(
        draft_id="d001",
        beta_definition_id=812,
        constant_value=0.9,
        uncertainty_log10=1.0,
        evidence_vlm_ids=[177390],
        estimation_method="analogue transfer",
        assumptions=["an aqueous reference state"],
        rationale="weak binding",
        source_excerpts={
            "beta_definition_excerpt": row_812,
            "constant_value_excerpt": row_840,
            "uncertainty_excerpt": row_840,
            "evidence_excerpt": "Evidence is vlm_177390.",
            "estimation_method_excerpt": "The method is analogue transfer.",
            "assumption_excerpts": ["I assume an aqueous reference state."],
            "rationale_excerpt": "The rationale is weak binding.",
        },
    )
    with pytest.raises(
        grounding.SourceGroundingError,
        match="does not identify its beta_definition_id",
    ):
        grounding.validate_draft_source_bindings(
            transcript=transcript,
            draft=draft,
        )


def test_source_binding_accepts_only_rendering_normalized_contiguous_spans() -> None:
    schema = _module("parse_speciation_answer.candidate_schema")
    grounding = _module("parse_speciation_answer.source_grounding")
    transcript = (
        "| **beta_def_812** | **\u22120.50** | **1.00** | **vlm_168275** |\n"
        "Method: **analogue transfer**.\n"
        "Assumption: _same aqueous reference state_.\n"
        "Rationale: `weak N-donor binding`."
    )
    draft = schema.EquilibriumDraft(
        draft_id="d001",
        beta_definition_id=812,
        constant_value=-0.5,
        uncertainty_log10=1.0,
        evidence_vlm_ids=[168275],
        estimation_method="analogue transfer",
        assumptions=["same aqueous reference state"],
        rationale="weak N-donor binding",
        source_excerpts={
            "beta_definition_excerpt": "beta_def_812 | -0.50",
            "constant_value_excerpt": "beta_def_812 | -0.50",
            "uncertainty_excerpt": "-0.50 | 1.00 | vlm_168275",
            "evidence_excerpt": "1.00 | vlm_168275",
            "estimation_method_excerpt": "Method: analogue\ttransfer.",
            "assumption_excerpts": [
                "Assumption: same aqueous reference state."
            ],
            "rationale_excerpt": "Rationale: weak N-donor binding.",
        },
    )

    receipts = grounding.validate_draft_source_bindings(
        transcript=transcript,
        draft=draft,
    )

    assert receipts[0]["source_binding_profile"] == (
        "contiguous_nfkc_whitespace_markdown_emphasis_v1"
    )


def test_source_binding_still_rejects_invented_or_stitched_content() -> None:
    schema = _module("parse_speciation_answer.candidate_schema")
    grounding = _module("parse_speciation_answer.source_grounding")
    transcript = (
        "beta_def_812 has log10 K = -0.5 and uncertainty 1.0. "
        "Evidence is vlm_168275. Method: analogue transfer. "
        "Assumption: same reference state. Rationale: weak binding."
    )
    draft = schema.EquilibriumDraft(
        draft_id="d001",
        beta_definition_id=812,
        constant_value=-0.5,
        uncertainty_log10=1.0,
        evidence_vlm_ids=[168275],
        estimation_method="analogue transfer",
        assumptions=["same reference state"],
        rationale="weak invented binding",
        source_excerpts={
            "beta_definition_excerpt": "beta_def_812 has log10 K = -0.5",
            "constant_value_excerpt": "beta_def_812 has log10 K = -0.5",
            "uncertainty_excerpt": "uncertainty 1.0",
            "evidence_excerpt": "Evidence is vlm_168275.",
            "estimation_method_excerpt": "Method: analogue transfer.",
            "assumption_excerpts": ["Assumption: same reference state."],
            "rationale_excerpt": "Rationale: weak invented binding.",
        },
    )

    with pytest.raises(
        grounding.SourceGroundingError,
        match="not traceable to one contiguous answer span",
    ):
        grounding.validate_draft_source_bindings(
            transcript=transcript,
            draft=draft,
        )


def test_parser_prompt_requires_tools_not_a_final_card() -> None:
    parser_agent = _module("parse_speciation_answer.parser_agent")
    prompt = parser_agent.PARSER_SYSTEM_PROMPT.lower()
    assert "finish_parser_cycle" in prompt
    assert "do not emit a card or json payload" in prompt
