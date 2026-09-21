"""End-to-end LC1.3 tests with a plain-prose dummy QueryAgent."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest


THIS_FILE = Path(__file__).resolve()
for _path in (
    THIS_FILE.parents[3],
    THIS_FILE.parents[4],
    THIS_FILE.parents[4] / "NIST_SRD46_core_numcalc_pipeline",
    THIS_FILE.parents[6],
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.LC1_3_estimate_eq_stability_dispatch_orchestrator import (
    LC13Dependencies,
    run_lc1_3,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.candidate_schema import (
    ParserCycleResult,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_tools import (
    ParserToolbox,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (
    LC13Settings,
    QueryTurn,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.validate_support_eq_map.native_eq_map_schema import (
    NATIVE_TABLE_COLUMNS,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (
    load_native_support_eq_map,
    load_session_working_map,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.ref_eq_SRD46_json_cards_builder import (
    build_ref_cards_from_lc1_2_card,
)


EVIDENCE_SENTENCE = (
    "SRD-46 record vlm_133923 in ref_eq_net_13340, linked to lit_1704, "
    "reports the beta_def_894 one-to-four formation equilibrium at log10 K = "
    "12.60 at 25.0 C and ionic strength 0.10 M."
)
TARGET_SENTENCE = (
    "For target Cu(II) metal_41 with imidazole ligand_7795 and the same "
    "beta_def_894 M + 4L <=> ML4 topology, I estimate log10 K = 12.58 at "
    "25.0 C and ionic strength 0.00 M."
)
METHOD_SENTENCE = (
    "The estimation method is same-pair ionic-strength transfer calibrated by "
    "the three lower cumulative formation constants."
)
UNCERTAINTY_SENTENCE = "The uncertainty is 0.10 log10 units."
ASSUMPTION_SENTENCE = (
    "I assume the observed 0.02 shift from ionic strength 0.10 M to 0.00 M "
    "continues from beta1 through beta4."
)
RATIONALE_SENTENCE = (
    "The rationale is that beta1, beta2, and beta3 are each 0.02 lower at "
    "ionic strength 0.00 M, so 12.60 minus 0.02 gives 12.58."
)


def _answer(*, include_uncertainty: bool) -> str:
    rows = [EVIDENCE_SENTENCE, TARGET_SENTENCE, METHOD_SENTENCE]
    if include_uncertainty:
        rows.append(UNCERTAINTY_SENTENCE)
    rows.extend([ASSUMPTION_SENTENCE, RATIONALE_SENTENCE])
    return " ".join(rows)


def _settings() -> LC13Settings:
    return LC13Settings(
        max_query_runs=1,
        query_model="dummy-query",
        query_max_iterations=4,
        query_timeout_s=30.0,
        parser_max_rounds=10,
        parser_timeout_s=30.0,
        parser_model="dummy-parser",
        failure_policy="reference_only",
        parser_validation_retries=2,
        query_clarification_retries=2,
        query_clarification_total_timeout_s=5.0,
    )


class DummyPlainQueryAgent:
    """Translate one plain SRD-like record into ordinary chemistry prose."""

    def __init__(self, *, omit_initial_uncertainty: bool) -> None:
        self.omit_initial_uncertainty = omit_initial_uncertainty
        self.calls: list[dict[str, object]] = []
        self.memory_object: list[dict[str, str]] | None = None

    def __call__(self, message: str, *, memory: list[dict[str, str]], **kwargs) -> QueryTurn:
        lowered = message.lower()
        assert "json" not in lowered
        assert "schema" not in lowered
        if self.memory_object is None:
            self.memory_object = memory
        else:
            assert memory is self.memory_object
        if not self.calls:
            answer = _answer(include_uncertainty=not self.omit_initial_uncertainty)
            history = [{
                "tool": "search_stability",
                "is_error": False,
                "result_full": json.dumps({
                    "vlm_id": 133923,
                    "beta_definition_id": 894,
                    "network_db_id": 13340,
                    "literature_alt_id": 1704,
                    "reported_log10_K": 12.60,
                    "chemistry": "one-to-four Cu(II)-imidazole complex",
                }),
            }]
        else:
            assert "missing chemistry information" in lowered
            assert "uncertainty" in lowered
            answer = UNCERTAINTY_SENTENCE
            history = []
        memory.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ])
        self.calls.append({
            "message": message,
            "answer": answer,
            "memory": memory,
            "timeout": kwargs.get("timeout"),
        })
        return QueryTurn(answer=answer, memory=memory, tool_history=history)


def _source_excerpts(*, include_uncertainty: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "beta_definition_excerpt": TARGET_SENTENCE,
        "constant_value_excerpt": TARGET_SENTENCE,
        "evidence_excerpt": EVIDENCE_SENTENCE,
        "estimation_method_excerpt": METHOD_SENTENCE,
        "assumption_excerpts": [ASSUMPTION_SENTENCE],
        "rationale_excerpt": RATIONALE_SENTENCE,
    }
    if include_uncertainty:
        result["uncertainty_excerpt"] = UNCERTAINTY_SENTENCE
    return result


def dummy_tool_parser(*, service, settings, artifact_dir, feedback=None):
    """Extract prose with regex, then use exactly the production parser tools."""

    del settings, artifact_dir, feedback
    transcript = service.state.transcript
    beta = int(re.search(
        r"For target .*?beta_def_(\d+).*?I estimate", transcript
    ).group(1))
    constant = float(re.search(r"I estimate log10 K = ([0-9.]+)", transcript).group(1))
    vlm = int(re.search(r"vlm_(\d+)", transcript).group(1))
    network = int(re.search(r"ref_eq_net_(\d+)", transcript).group(1))
    citation = int(re.search(r"lit_(\d+)", transcript).group(1))
    uncertainty_match = re.search(r"uncertainty is ([0-9.]+)", transcript)
    toolbox = ParserToolbox(service)
    history: list[dict[str, object]] = []

    def call(name: str, **kwargs):
        result = getattr(toolbox, name)(**kwargs)
        history.append({"tool": name, "arguments": kwargs, "result_full": result})
        return json.loads(result)

    call("inspect_parser_context")
    if not service.state.drafts:
        draft = {
            "beta_definition_id": beta,
            "constant_value": constant,
            "evidence_vlm_ids": [vlm],
            "evidence_network_ids": [network],
            "evidence_citation_ids": [citation],
            "estimation_method": (
                "same-pair ionic-strength transfer calibrated by the three "
                "lower cumulative formation constants"
            ),
            "assumptions": [
                "the observed 0.02 shift from ionic strength 0.10 M to 0.00 M "
                "continues from beta1 through beta4"
            ],
            "rationale": (
                "beta1, beta2, and beta3 are each 0.02 lower at ionic strength "
                "0.00 M, so 12.60 minus 0.02 gives 12.58"
            ),
            "source_excerpts": _source_excerpts(
                include_uncertainty=uncertainty_match is not None
            ),
        }
        if uncertainty_match is not None:
            draft["uncertainty_log10"] = float(uncertainty_match.group(1))
        call("create_equilibrium_draft", draft_json=json.dumps(draft))
    elif uncertainty_match is not None:
        call(
            "update_equilibrium_draft",
            draft_id="d001",
            patch_json=json.dumps({
                "uncertainty_log10": float(uncertainty_match.group(1)),
                "source_excerpts": _source_excerpts(include_uncertainty=True),
            }),
        )
    completeness = call("check_draft", draft_id="d001")
    if completeness["status"] != "pass":
        topics = sorted({
            topic
            for issue in completeness["issues"]
            if issue["owner"] == "query_agent"
            for topic in issue["missing_topics"]
        })
        call(
            "finish_parser_cycle",
            action="request_followup",
            reason="the chemistry answer omitted required estimate context",
            missing_topics_csv=",".join(topics),
        )
    else:
        assert call("run_entry_gate", draft_id="d001")["status"] == "pass"
        assert call("run_network_gate")["status"] == "pass"
        annotation = {
            "discussion": (
                f"Same-pair ionic-strength transfer from ref_eq_net_{network}, "
                f"anchored by vlm_{vlm} and lit_{citation}: the three lower "
                f"cumulative constants each drop 0.02 between the two ionic "
                f"strengths, so the fourth constant lands at {constant}."
            ),
            "core_source_ids": [
                f"vlm_{vlm}", f"ref_eq_net_{network}", f"lit_{citation}",
            ],
        }
        annotated = call(
            "annotate_equilibrium_draft",
            draft_id="d001",
            annotation_json=json.dumps(annotation),
        )
        assert annotated["status"] == "annotated"
        call("finish_parser_cycle", action="commit", reason="all gates pass")
    return ParserCycleResult(
        action=service.state.terminal_action,
        reason=service.state.terminal_reason,
        missing_topics=list(service.state.terminal_missing_topics),
        tool_history=history,
    )


@pytest.mark.parametrize(
    (
        "base_card", "expected_selected", "omit_initial_uncertainty",
        "expected_base_reference_count", "preserves_overrides",
    ),
    [
        ({"equilibrium_networks": []}, [], False, 0, False),
        ({
            "equilibrium_networks": [{
                "metal_id": 41,
                "ligand_id": 7795,
                "eq_network": "ref_eq_net_13347",
                "temperature": 25.0,
                "ionic_strength": 0.0,
                "patch_notes": {"patches": []},
            }],
        }, [13347], True, 1, False),
        ({
            "pairs": [{
                "metal_id": 41,
                "ligand_id": 7795,
                "selected_network_ids": [13347],
                "vlm_overrides": [{
                    "beta_definition_id": 999,
                    "action": "drop_node",
                }],
            }],
        }, [13347], False, 1, True),
    ],
    ids=[
        "new_map",
        "production_flat_map_with_followup",
        "normalized_existing_map_preserves_overrides",
    ],
)
def test_plain_query_to_solver_ready_guessed_map(
    tmp_path: Path,
    base_card: dict,
    expected_selected: list[int],
    omit_initial_uncertainty: bool,
    expected_base_reference_count: int,
    preserves_overrides: bool,
) -> None:
    original_base = copy.deepcopy(base_card)
    query = DummyPlainQueryAgent(
        omit_initial_uncertainty=omit_initial_uncertainty
    )
    result = run_lc1_3(
        base_eq_map_card=base_card,
        target_chemical_system={
            "metals": [{"metal_id": 41}],
            "ligands": [{"ligand_id": 7795}],
        },
        purpose="estimate the missing Cu(II)-imidazole one-to-four equilibrium",
        tasks="use SRD-46 analogue chemistry",
        chemical_context_plan=None,
        request_T_C=25.0,
        request_I_M=0.00,
        output_dir=tmp_path,
        settings=_settings(),
        dependencies=LC13Dependencies(
            query_runner=query,
            query_system_prompt="ordinary chemistry assistant",
            parser_runner=dummy_tool_parser,
        ),
    )

    assert base_card == original_base
    assert result.status == "ok"
    assert result.estimation_search_complete is True
    assert result.reference_only_reason is None
    assert result.support_eq_map_path is not None
    assert result.session_working_map_path is not None
    assert len(query.calls) == (2 if omit_initial_uncertainty else 1)
    assert all(call["memory"] is query.memory_object for call in query.calls)
    assert "chemical_pairs" not in str(query.calls[0]["answer"])
    if omit_initial_uncertainty:
        assert 0.0 < float(query.calls[1]["timeout"]) <= 5.0

    support_payload = json.loads(
        Path(result.support_eq_map_path).read_text(encoding="utf-8")
    )
    assert set(support_payload) == set(NATIVE_TABLE_COLUMNS)
    assert len(support_payload["eq_map_collection"]) == 1
    assert len(support_payload["eq_map"]) == 1
    assert len(support_payload["eq_network"]) == 1
    assert len(support_payload["eq_node"]) == 1
    assert len(support_payload["eq_node_species"]) == 3
    assert not support_payload["eq_edge"]
    node = support_payload["eq_node"][0]
    assert node["node_db_id"] < 0 and node["vlm_id"] < 0
    assert node["beta_definition_id"] == 894
    assert node["beta_definition_name"] == "[ML<sub>4</sub>]/[M][L]<sup>4</sup>"
    assert node["equation_python"] == "[M] + [L]^4 <=> [ML4]"
    assert node["constant_value"] == pytest.approx(12.58)

    loaded_support = load_native_support_eq_map(
        result.support_eq_map_path,
        base_eq_map_card=base_card,
        allowed_system_pairs={(41, 7795)},
        expected_support_session_id=str(result.session_id),
        expected_support_eq_map_sha256=str(result.support_eq_map_sha256),
    )
    assert loaded_support.node_count == 1
    row = loaded_support.rows_by_pair[(41, 7795)][0]
    assert row["log_K"] == pytest.approx(12.58)
    assert row["temperature"] == pytest.approx(25.0)
    assert row["ionic_strength"] == pytest.approx(0.0)
    assert row["_estimated_provenance"]["query_id"] == "q001"
    assert row["_estimated_provenance"]["evidence_vlm_ids"] == ["vlm_133923"]
    annotation = row["_estimated_provenance"]["agent_annotation"]
    assert "12.58" in annotation["discussion"]
    assert annotation["core_source_ids"] == [
        "lit_1704", "ref_eq_net_13340", "vlm_133923",
    ]
    assert annotation["secondary_source_ids"] == []
    assert len(annotation["annotation_sha256"]) == 64

    loaded_working = load_session_working_map(
        result.session_working_map_path,
        expected_session_working_map_sha256=str(
            result.session_working_map_sha256
        ),
        support_rows_by_pair=loaded_support.rows_by_pair,
        base_eq_map_card=base_card,
        allowed_system_pairs={(41, 7795)},
    )
    working_pair = next(
        pair for pair in loaded_working.payload["pairs"]
        if (pair["metal_id"], pair["ligand_id"]) == (41, 7795)
    )
    assert working_pair["selected_network_ids"] == expected_selected
    assert working_pair["estimated_eq_nodes"][0]["log_K"] == pytest.approx(12.58)
    if preserves_overrides:
        assert working_pair["vlm_overrides"] == original_base["pairs"][0]["vlm_overrides"]

    parser_workspace = json.loads(
        (tmp_path / "parser_agents" / "q001" / "workspace.json").read_text(
            encoding="utf-8"
        )
    )
    assert parser_workspace["initial_answer_sha256"] == result.parse[
        "repair_audit"
    ]["queries"]["q001"]["initial_answer_sha256"]
    assert parser_workspace["terminal_action"] == "commit"
    assert parser_workspace["annotations"][0]["draft_id"] == "d001"
    assert parser_workspace["annotations"][0]["liveness"] == "annotated"
    assert parser_workspace["scope"]["base_reference_network_count"] == (
        expected_base_reference_count
    )
    assert parser_workspace["drafts"][0]["canonical_equilibrium"][
        "equation_python"
    ] == "[M] + [L]^4 <=> [ML4]"
    if omit_initial_uncertainty:
        assert parser_workspace["n_answer_turns"] == 2
        assert len(parser_workspace["clarification_history"]) == 1
        assert result.parse["repair_audit"]["queries"]["q001"][
            "query_clarification_rounds"
        ] == 1
        followup_manifest = json.loads(
            (
                tmp_path / "query_agents" / "q001" / "query_agent_followups"
                / "followup_01" / "clarification_manifest.json"
            ).read_text(encoding="utf-8")
        )
        assert followup_manifest["same_memory_object"] is True

    if expected_selected and not preserves_overrides:
        base_path = tmp_path / "lc1_2_eqmap_card.json"
        base_path.write_text(json.dumps(base_card, indent=2), encoding="utf-8")
        cards = build_ref_cards_from_lc1_2_card(
            base_path,
            storage_dir=tmp_path / "lc2_ref_cards",
            auto_hydroxide=False,
            auto_pka=False,
            support_eq_map_path=result.support_eq_map_path,
            expected_support_session_id=str(result.session_id),
            expected_support_eq_map_sha256=str(result.support_eq_map_sha256),
            session_working_map_path=result.session_working_map_path,
            expected_session_working_map_sha256=str(
                result.session_working_map_sha256
            ),
            allowed_system_pairs={(41, 7795)},
            system_catalog_sha256="c" * 64,
        )
        assert len(cards) == 1
        compiled = json.loads(cards[0].with_suffix(".json").read_text(encoding="utf-8"))
        equilibria = [
            row
            for blocks in compiled["equations"].values()
            for block in blocks
            for row in block["equilibria"]
        ]
        estimated = [
            row for row in equilibria
            if row["reference"]["source"] == "SRD46 query estimated values"
        ]
        assert len(estimated) == 1
        assert estimated[0]["patch_notes"]["beta_definition_id"] == 894
        assert sorted(row["log_K"] for row in equilibria) == pytest.approx(
            [4.19, 7.70, 10.55, 12.58]
        )
        assert any(
            term["power"] == 4 for term in estimated[0]["LHS"]
        )
